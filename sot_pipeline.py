"""Pipeline for analyzing eligible titles from Sources of Truth."""
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

import structlog

from config import DatabricksConfig, get_config
from service import ContentService, EligibleTitlesService
from analysis import SafeZoneAnalyzer, PosterAnalysisPipeline, PosterAnalysisResult
from sot_repository import EligibleTitle

logger = structlog.get_logger(__name__)


@dataclass
class SOTAnalysisResult:
    """Result of analyzing an eligible title."""
    
    content_id: int
    program_id: int
    sot_name: str
    content_name: Optional[str]
    content_type: Optional[str]
    poster_img_url: Optional[str]
    analysis: Optional[Dict[str, Any]]
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "content_id": self.content_id,
            "program_id": self.program_id,
            "sot_name": self.sot_name,
            "content_name": self.content_name,
            "content_type": self.content_type,
            "poster_img_url": self.poster_img_url,
            "analysis": self.analysis,
            "error": self.error,
        }


@dataclass
class SOTAnalysisCheckpoint:
    """Checkpoint for resumable processing."""
    
    start_time: datetime
    last_updated: datetime
    total_titles: int
    processed_count: int
    success_count: int
    error_count: int
    processed_ids: List[int] = field(default_factory=list)
    errors: Dict[int, str] = field(default_factory=dict)
    
    def save(self, path: Path) -> None:
        """Save checkpoint to file."""
        data = {
            "start_time": self.start_time.isoformat(),
            "last_updated": self.last_updated.isoformat(),
            "total_titles": self.total_titles,
            "processed_count": self.processed_count,
            "success_count": self.success_count,
            "error_count": self.error_count,
            "processed_ids": self.processed_ids,
            "errors": self.errors,
        }
        path.write_text(json.dumps(data, indent=2))
    
    @classmethod
    def load(cls, path: Path) -> Optional["SOTAnalysisCheckpoint"]:
        """Load checkpoint from file."""
        if not path.exists():
            return None
            
        try:
            data = json.loads(path.read_text())
            return cls(
                start_time=datetime.fromisoformat(data["start_time"]),
                last_updated=datetime.fromisoformat(data["last_updated"]),
                total_titles=data["total_titles"],
                processed_count=data["processed_count"],
                success_count=data["success_count"],
                error_count=data["error_count"],
                processed_ids=data["processed_ids"],
                errors=data["errors"],
            )
        except Exception as exc:
            logger.error("checkpoint_load_failed", error=str(exc))
            return None


class SOTAnalysisPipeline:
    """Pipeline for analyzing eligible titles with checkpoint support."""
    
    def __init__(
        self,
        eligible_service: EligibleTitlesService,
        content_service: ContentService,
        analyzer: SafeZoneAnalyzer,
        config: Optional[DatabricksConfig] = None,
    ):
        self.eligible_service = eligible_service
        self.content_service = content_service
        self.analyzer = analyzer
        self.config = config or get_config()
        self.checkpoint_path = Path("sot_analysis_checkpoint.json")
    
    def run(
        self,
        days_back: int = 7,
        sot_types: Optional[List[str]] = None,
        batch_size: int = 100,
        limit: Optional[int] = None,
        resume: bool = True,
        download_images: bool = True,
        download_timeout: int = 20,
    ) -> List[SOTAnalysisResult]:
        """
        Run analysis on eligible titles.
        
        Args:
            days_back: Number of days to look back
            sot_types: Filter by specific SOT types
            batch_size: Number of titles to process per batch
            limit: Maximum number of titles to process
            resume: Whether to resume from checkpoint if available
            download_images: Whether to download images to base64
            download_timeout: Timeout for image downloads
            
        Returns:
            List of analysis results
        """
        # Load checkpoint if resuming
        checkpoint = None
        processed_set = set()
        
        if resume and self.checkpoint_path.exists():
            checkpoint = SOTAnalysisCheckpoint.load(self.checkpoint_path)
            if checkpoint:
                processed_set = set(checkpoint.processed_ids)
                logger.info(
                    "resuming_from_checkpoint",
                    processed=checkpoint.processed_count,
                    success=checkpoint.success_count,
                    errors=checkpoint.error_count,
                )
        
        # Create new checkpoint if needed
        if not checkpoint:
            checkpoint = SOTAnalysisCheckpoint(
                start_time=datetime.now(),
                last_updated=datetime.now(),
                total_titles=0,
                processed_count=0,
                success_count=0,
                error_count=0,
            )
        
        # Get eligible titles
        logger.info(
            "fetching_eligible_titles_pipeline",
            days_back=days_back,
            sot_types=sot_types,
        )
        
        eligible_gen = self.eligible_service.iter_eligible_poster_images(
            days_back=days_back,
            sot_types=sot_types,
            batch_size=batch_size,
            max_items=limit,
        )
        
        # Process titles
        results = []
        batch = []
        start_time = time.time()
        
        for eligible_title in eligible_gen:
            # Skip if already processed
            if eligible_title.content_id in processed_set:
                continue
            
            batch.append(eligible_title)
            
            # Process batch when full
            if len(batch) >= batch_size:
                batch_results = self._process_batch(
                    batch,
                    download_images=download_images,
                    download_timeout=download_timeout,
                )
                
                # Update checkpoint
                for result in batch_results:
                    checkpoint.processed_count += 1
                    checkpoint.processed_ids.append(result.content_id)
                    
                    if result.error:
                        checkpoint.error_count += 1
                        checkpoint.errors[result.content_id] = result.error
                    else:
                        checkpoint.success_count += 1
                    
                    results.append(result)
                
                # Save checkpoint
                checkpoint.last_updated = datetime.now()
                checkpoint.save(self.checkpoint_path)
                
                # Show progress
                elapsed = time.time() - start_time
                rate = checkpoint.processed_count / elapsed if elapsed > 0 else 0
                eta_seconds = (limit - checkpoint.processed_count) / rate if rate > 0 and limit else 0
                
                logger.info(
                    "batch_processed",
                    processed=checkpoint.processed_count,
                    success=checkpoint.success_count,
                    errors=checkpoint.error_count,
                    rate_per_minute=rate * 60,
                    eta_minutes=eta_seconds / 60,
                )
                
                batch = []
        
        # Process remaining batch
        if batch:
            batch_results = self._process_batch(
                batch,
                download_images=download_images,
                download_timeout=download_timeout,
            )
            
            for result in batch_results:
                checkpoint.processed_count += 1
                checkpoint.processed_ids.append(result.content_id)
                
                if result.error:
                    checkpoint.error_count += 1
                    checkpoint.errors[result.content_id] = result.error
                else:
                    checkpoint.success_count += 1
                
                results.append(result)
            
            checkpoint.last_updated = datetime.now()
            checkpoint.save(self.checkpoint_path)
        
        # Clean up checkpoint on successful completion
        if not limit or checkpoint.processed_count >= limit:
            self.checkpoint_path.unlink(missing_ok=True)
            logger.info("checkpoint_removed_on_completion")
        
        # Log final summary
        logger.info(
            "sot_analysis_complete",
            total_processed=len(results),
            success=checkpoint.success_count,
            errors=checkpoint.error_count,
            duration_minutes=(time.time() - start_time) / 60,
        )
        
        return results
    
    def _process_batch(
        self,
        batch: List[EligibleTitle],
        download_images: bool = True,
        download_timeout: int = 20,
    ) -> List[SOTAnalysisResult]:
        """Process a batch of eligible titles."""
        results = []
        
        # Create poster analysis pipeline
        pipeline = PosterAnalysisPipeline(self.content_service, self.analyzer)
        
        # Import needed modules
        from analysis import _download_image_to_base64, PosterAnalysisResult
        
        # Map content IDs to eligible titles (content_id might be same as program_id)
        content_map = {t.content_id if t.content_id else t.program_id: t for t in batch}
        
        # Analyze specific posters
        analysis_results = []
        for t in batch:
            if not t.poster_img_url:
                continue
                
            # Use content_id if available, otherwise use program_id
            content_id = t.content_id if t.content_id else t.program_id
            
            try:
                # Download and analyze the image
                image_data = _download_image_to_base64(t.poster_img_url)
                result = self.analyzer.analyze_with_fallback(image_data)
                
                analysis_results.append(PosterAnalysisResult(
                    content_id=content_id,
                    poster_img_url=t.poster_img_url,
                    analysis=result,
                    error=None
                ))
            except Exception as e:
                logger.error(
                    "poster_analysis_failed",
                    content_id=content_id,
                    error=str(e),
                )
                analysis_results.append(PosterAnalysisResult(
                    content_id=content_id,
                    poster_img_url=t.poster_img_url,
                    analysis=None,
                    error=str(e)
                ))
        
        # Convert to SOT results
        for analysis_result in analysis_results:
            eligible_title = content_map.get(analysis_result.content_id)
            
            if eligible_title:
                sot_result = SOTAnalysisResult(
                    content_id=analysis_result.content_id,
                    program_id=eligible_title.program_id,
                    sot_name=eligible_title.sot_name,
                    content_name=eligible_title.content_name,
                    content_type=eligible_title.content_type,
                    poster_img_url=analysis_result.poster_img_url,
                    analysis=analysis_result.analysis,
                    error=analysis_result.error,
                )
                results.append(sot_result)
        
        return results
    
    def get_summary_by_sot(self, results: List[SOTAnalysisResult]) -> Dict[str, Dict[str, Any]]:
        """
        Get summary statistics by SOT type.
        
        Returns:
            Dictionary mapping SOT name to statistics
        """
        summary = {}
        
        for result in results:
            sot = result.sot_name
            if sot not in summary:
                summary[sot] = {
                    "total": 0,
                    "analyzed": 0,
                    "errors": 0,
                    "with_key_elements": 0,
                    "without_key_elements": 0,
                    "high_confidence": 0,
                    "medium_confidence": 0,
                    "low_confidence": 0,
                }
            
            summary[sot]["total"] += 1
            
            if result.error:
                summary[sot]["errors"] += 1
            elif result.analysis:
                summary[sot]["analyzed"] += 1
                
                red_zone = result.analysis.get("red_safe_zone", {})
                if red_zone.get("contains_key_elements"):
                    summary[sot]["with_key_elements"] += 1
                else:
                    summary[sot]["without_key_elements"] += 1
                
                confidence = red_zone.get("confidence", 0)
                if confidence >= 90:
                    summary[sot]["high_confidence"] += 1
                elif confidence >= 60:
                    summary[sot]["medium_confidence"] += 1
                elif confidence > 0:
                    summary[sot]["low_confidence"] += 1
        
        return summary
