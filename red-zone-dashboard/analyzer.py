"""Integration with the main analysis pipeline for the dashboard."""
import os
import sys
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional, Callable

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

try:
    from sot_pipeline import SOTAnalysisPipeline, SOTAnalysisResult
    from service import EligibleTitlesService
    from config import get_config
    from database import AnalysisRun, PosterResult
except ImportError as e:
    print(f"Warning: Could not import analysis modules: {e}")
    print("Dashboard will run in view-only mode")
    SOTAnalysisPipeline = None
    EligibleTitlesService = None


class DashboardAnalyzer:
    """Wrapper for running analysis from the dashboard."""
    
    # Safety limits for QA
    MAX_BATCH_SIZE = 100
    DEFAULT_BATCH_SIZE = 50
    VALID_SOTS = {
        "imdb",
        "rt",
        "award",
        "vibe",
        "narrative",
        "most_liked",
        "just_added",
        "leaving_soon",
    }
    SOT_TYPE_MAP = {
        "imdb": "imdb",
        "rotten_tomatoes": "rt",
        "rt": "rt",
        "just_added": "just_added",
        "leaving_soon": "leaving_soon",
        "most_popular": "most_liked",
        "most_liked": "most_liked",
        "awards": "award",
        "award": "award",
        "top_rated": "narrative",
        "narrative": "narrative",
        "vibe": "vibe",
    }
    
    def __init__(self):
        """Initialize the analyzer."""
        self.pipeline = None
        self.service = None
        
        if SOTAnalysisPipeline and EligibleTitlesService:
            try:
                from service import ContentService
                from analysis import SafeZoneAnalyzer
                
                self.config = get_config()
                self.service = EligibleTitlesService()
                content_service = ContentService()
                analyzer = SafeZoneAnalyzer(
                    provider="openai",
                    model=self.config.openai_model,
                    api_key=self.config.openai_api_key
                )
                self.pipeline = SOTAnalysisPipeline(
                    eligible_service=self.service,
                    content_service=content_service,
                    analyzer=analyzer
                )
            except Exception as e:
                print(f"Warning: Could not initialize analysis pipeline: {e}")
    
    def is_available(self) -> bool:
        """Check if analysis functionality is available."""
        return self.pipeline is not None and self.service is not None
    
    def run_analysis(
        self, 
        sot_types: List[str],
        days_back: int = 7,
        limit: Optional[int] = None,
        description: str = "",
        use_cache: bool = True,
        batch_size: Optional[int] = None,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> Dict[str, Any]:
        """Run analysis and store results in database."""
        if not self.is_available():
            return {
                "status": "error",
                "message": "Analysis pipeline not available"
            }
        
        normalized_sots = self._normalize_sot_types(sot_types)
        if not normalized_sots:
            return {
                "status": "error",
                "message": "No valid Source of Truth selections were provided."
            }
        
        # Enforce batch size limits for QA
        if limit is None:
            limit = self.DEFAULT_BATCH_SIZE
        elif limit > self.MAX_BATCH_SIZE:
            return {
                "status": "error",
                "message": f"Batch size {limit} exceeds maximum allowed ({self.MAX_BATCH_SIZE}). For QA purposes, please run smaller batches first."
            }
        
        try:
            # Run analysis through pipeline
            results = self.pipeline.run(
                sot_types=normalized_sots,
                days_back=days_back,
                limit=limit,
                batch_size=min(batch_size or self.pipeline.config.sot_batch_size, self.MAX_BATCH_SIZE),
                progress_callback=progress_callback,
            )
            
            if not results:
                return {
                    "status": "error",
                    "message": "No results returned from analysis"
                }
            
            # Calculate statistics
            total = len(results)
            passed = sum(1 for r in results if not r.analysis.get("red_safe_zone", {}).get("contains_key_elements", True))
            failed = total - passed
            
            # Create analysis run in database
            parameters = {
                "requested_sot_types": sot_types,
                "sot_types": normalized_sots,
                "days_back": days_back,
                "limit": limit,
                "use_cache": use_cache
            }
            
            run_id = AnalysisRun.create(
                total=total,
                passed=passed,
                failed=failed,
                parameters=parameters,
                description=description
            )
            
            # Convert results to database format
            db_results = []
            for result in results:
                analysis_payload = result.analysis or {}
                db_results.append({
                    "content_id": result.content_id,
                    "program_id": result.program_id,
                    "content_name": result.content_name,
                    "content_type": result.content_type,
                    "sot_name": result.sot_name,
                    "poster_img_url": result.poster_img_url,
                    "poster_url": result.poster_img_url,
                    "analysis": analysis_payload,
                    "error": result.error,
                })
            
            # Store results in database
            PosterResult.create_batch(run_id, db_results)
            
            return {
                "status": "success",
                "run_id": run_id,
                "total": total,
                "passed": passed,
                "failed": failed
            }
            
        except Exception as e:
            return {
                "status": "error",
                "message": f"Analysis failed: {str(e)}"
            }
    
    def get_available_sot_types(self) -> List[str]:
        """Get list of available SOT types."""
        # These should match the SOT types in your SQL query
        return [
            "imdb",
            "rotten_tomatoes", 
            "just_added",
            "leaving_soon",
            "most_popular",
            "most_liked",
            "awards",
            "top_rated"
        ]
    
    def _normalize_sot_types(self, sot_types: List[str]) -> List[str]:
        normalized: List[str] = []
        for sot in sot_types or []:
            mapped = self.SOT_TYPE_MAP.get(sot, sot)
            if mapped in self.VALID_SOTS and mapped not in normalized:
                normalized.append(mapped)
        return normalized
    
    def export_run_data(self, run_id: int) -> Dict[str, Any]:
        """Export all data for a specific run."""
        run = AnalysisRun.get_by_id(run_id)
        if not run:
            raise ValueError(f"Run {run_id} not found")
        
        results = PosterResult.get_by_run(run_id)
        
        # Parse parameters if JSON
        if run['parameters']:
            try:
                run['parameters'] = json.loads(run['parameters'])
            except:
                pass
        
        return {
            "run": dict(run),
            "results": results,
            "export_date": datetime.now().isoformat()
        }


# Singleton instance
analyzer = DashboardAnalyzer()


# Helper functions for use in dashboard.py
def is_analysis_available() -> bool:
    """Check if analysis functionality is available."""
    return analyzer.is_available()


def run_dashboard_analysis(**kwargs) -> Dict[str, Any]:
    """Run analysis from dashboard."""
    return analyzer.run_analysis(**kwargs)


def get_sot_types() -> List[str]:
    """Get available SOT types."""
    return analyzer.get_available_sot_types()
