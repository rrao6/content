"""Pipeline for analyzing eligible titles from Sources of Truth."""
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field

import structlog

from config import DatabricksConfig, get_config
from service import ContentService, EligibleTitlesService
from analysis import SafeZoneAnalyzer
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
        save_composite_images: bool = False,
        composite_image_dir: str = "./debug_composite_images",
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
        shiny_only: bool = False,
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
            save_composite_images: Whether to save composite images with red zone overlay for debugging
            composite_image_dir: Directory to save composite images (default: ./debug_composite_images)
            
        Args:
            progress_callback: Optional callable to receive progress updates with keys
                (event, processed, total, message, etc.)
        
        Returns:
            List of analysis results
        """
        checkpoint: Optional[SOTAnalysisCheckpoint] = None

        def report_progress(event: str, result: Optional[SOTAnalysisResult] = None, message: Optional[str] = None):
            if not progress_callback:
                return
            
            payload: Dict[str, Any] = {
                "event": event,
                "processed": checkpoint.processed_count if checkpoint else 0,
                "success": checkpoint.success_count if checkpoint else 0,
                "errors": checkpoint.error_count if checkpoint else 0,
                "total": limit,
            }
            if message:
                payload["message"] = message
            
            if result:
                payload.update(
                    content_id=result.content_id,
                    content_name=result.content_name,
                    sot_name=result.sot_name,
                    has_key_elements=None,
                )
                if result.analysis:
                    red_zone = result.analysis.get("red_safe_zone", {})
                    payload["has_key_elements"] = red_zone.get("contains_key_elements")
                    payload["confidence"] = red_zone.get("confidence")
                if result.error:
                    payload["error"] = result.error
            progress_callback(payload)
        
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
        print(f"\n🎬 Starting SOT Analysis Pipeline")
        print(f"{'='*70}")
        print(f"📅 Days back: {days_back}")
        print(f"🎯 SOT types: {sot_types if sot_types else 'ALL'}")
        print(f"📊 Limit: {limit if limit else 'No limit'}")
        print(f"💾 Save composite images: {save_composite_images}")
        print(f"{'='*70}\n")
        report_progress(
            event="started",
            message=f"Starting {'shiny ' if shiny_only else ''}analysis for {limit or 'unknown'} titles",
        )
        
        logger.info(
            "fetching_eligible_titles_pipeline",
            days_back=days_back,
            sot_types=sot_types,
        )
        
        print("🔍 Fetching eligible titles from database...")
        report_progress("fetching_titles", message="Fetching eligible titles from database...")
        if shiny_only:
            eligible_gen = self.eligible_service.iter_shiny_eligible_poster_images(
                days_back=days_back,
                sot_types=sot_types,
                batch_size=batch_size,
                max_items=limit,
            )
        else:
            eligible_gen = self.eligible_service.iter_eligible_poster_images(
                days_back=days_back,
                sot_types=sot_types,
                batch_size=batch_size,
                max_items=limit,
            )
        
        # Process titles
        results: List[SOTAnalysisResult] = []
        batch: List[EligibleTitle] = []
        start_time = time.time()
        
        def handle_result(result: SOTAnalysisResult) -> None:
            checkpoint.processed_count += 1
            checkpoint.processed_ids.append(result.content_id)
            
            if result.error:
                checkpoint.error_count += 1
                checkpoint.errors[result.content_id] = result.error
            else:
                checkpoint.success_count += 1
            
            results.append(result)
            
            human_name = result.content_name or f"ID {result.content_id}"
            progress_message = f"Processed {human_name} ({checkpoint.processed_count}/{limit or '∞'})"
            if result.error:
                progress_message += f" - error: {result.error}"
            report_progress("processed", result=result, message=progress_message)
        
        for eligible_title in eligible_gen:
            # Skip if already processed
            if eligible_title.content_id in processed_set:
                continue
            
            batch.append(eligible_title)
            
            # Process batch when full
            if len(batch) >= batch_size:
                self._process_batch(
                    batch,
                    download_images=download_images,
                    download_timeout=download_timeout,
                    save_composite_images=save_composite_images,
                    composite_image_dir=composite_image_dir,
                    current_count=checkpoint.processed_count,
                    total_limit=limit,
                    start_time=start_time,
                    on_result=handle_result,
                )
                
                # Save checkpoint
                checkpoint.last_updated = datetime.now()
                checkpoint.save(self.checkpoint_path)
                
                # Show progress
                elapsed = time.time() - start_time
                rate = checkpoint.processed_count / elapsed if elapsed > 0 else 0
                eta_seconds = (limit - checkpoint.processed_count) / rate if rate > 0 and limit else 0
                
                # Calculate percentage
                pct_complete = (checkpoint.processed_count / limit * 100) if limit else 0
                
                # User-friendly progress message
                print(f"\n{'='*70}")
                print(f"Progress: {checkpoint.processed_count}/{limit} ({pct_complete:.1f}% complete)")
                print(f"{'='*70}")
                print(f"✅ Success: {checkpoint.success_count}")
                print(f"❌ Errors:  {checkpoint.error_count}")
                print(f"⚡ Rate:    {rate * 60:.1f} posters/minute")
                if eta_seconds > 0:
                    eta_mins = eta_seconds / 60
                    print(f"⏱️  ETA:     {eta_mins:.1f} minutes ({eta_seconds:.0f} seconds)")
                print(f"{'='*70}\n")
                
                logger.info(
                    "batch_processed",
                    processed=checkpoint.processed_count,
                    success=checkpoint.success_count,
                    errors=checkpoint.error_count,
                    rate_per_minute=rate * 60,
                    eta_minutes=eta_seconds / 60,
                    percent_complete=pct_complete,
                )
                
                batch = []
        
        # Process remaining batch
        if batch:
            self._process_batch(
                batch,
                download_images=download_images,
                download_timeout=download_timeout,
                save_composite_images=save_composite_images,
                composite_image_dir=composite_image_dir,
                current_count=checkpoint.processed_count,
                total_limit=limit,
                start_time=start_time,
                on_result=handle_result,
            )
            
            checkpoint.last_updated = datetime.now()
            checkpoint.save(self.checkpoint_path)
        
        # Clean up checkpoint on successful completion
        if not limit or checkpoint.processed_count >= limit:
            self.checkpoint_path.unlink(missing_ok=True)
            logger.info("checkpoint_removed_on_completion")
        
        # Log final summary
        duration_seconds = time.time() - start_time
        duration_minutes = duration_seconds / 60
        
        # Print final summary
        print(f"\n{'='*70}")
        print(f"✨ Analysis Complete!")
        print(f"{'='*70}")
        print(f"📊 Total processed: {len(results)}")
        print(f"✅ Success: {checkpoint.success_count}")
        print(f"❌ Errors: {checkpoint.error_count}")
        print(f"⏱️  Duration: {duration_minutes:.1f} minutes ({duration_seconds:.0f} seconds)")
        if checkpoint.success_count > 0:
            avg_time = duration_seconds / checkpoint.success_count
            print(f"📈 Avg time per poster: {avg_time:.1f} seconds")
        print(f"{'='*70}\n")
        completion_message = (
            f"Analysis complete in {duration_minutes:.1f} minutes. "
            f"{checkpoint.success_count} success, {checkpoint.error_count} errors."
        )
        report_progress("completed", message=completion_message)
        
        logger.info(
            "sot_analysis_complete",
            total_processed=len(results),
            success=checkpoint.success_count,
            errors=checkpoint.error_count,
            duration_minutes=duration_minutes,
        )
        
        return results
    
    def _process_batch(
        self,
        batch: List[EligibleTitle],
        download_images: bool = True,
        download_timeout: int = 20,
        save_composite_images: bool = False,
        composite_image_dir: str = "./debug_composite_images",
        current_count: int = 0,
        total_limit: Optional[int] = None,
        start_time: Optional[float] = None,
        on_result: Optional[Callable[[SOTAnalysisResult], None]] = None,
    ) -> None:
        """Process a batch of eligible titles."""
        
        # Import needed modules
        import os
        import re
        import base64
        from analysis import _download_image_to_base64
        
        # Create composite image directory if needed
        if save_composite_images:
            os.makedirs(composite_image_dir, exist_ok=True)
            print(f"📸 Composite images will be saved to: {composite_image_dir}")
        # Analyze specific posters
        batch_item_count = 0
        for t in batch:
            if not t.poster_img_url:
                continue
                
            # Use content_id if available, otherwise use program_id
            content_id = t.content_id if t.content_id else t.program_id
            
            # Calculate current position
            item_number = current_count + batch_item_count + 1
            
            try:
                # Show individual progress
                if total_limit:
                    pct = (item_number / total_limit * 100)
                    print(f"🔄 Processing {item_number}/{total_limit} ({pct:.1f}%) - {t.content_name or 'Unknown'} (ID: {content_id})")
                else:
                    print(f"🔄 Processing item {item_number} - {t.content_name or 'Unknown'} (ID: {content_id})")
                
                # Download and analyze the image
                image_data = _download_image_to_base64(t.poster_img_url)
                
                # Save composite image if debug mode enabled
                if save_composite_images:
                    base64_match = re.match(r'data:image/[^;]+;base64,(.+)', image_data)
                    if base64_match:
                        base64_data = base64_match.group(1)
                        image_bytes = base64.b64decode(base64_data)
                        save_path = os.path.join(composite_image_dir, f"content_{content_id}.png")
                        with open(save_path, 'wb') as f:
                            f.write(image_bytes)
                        logger.info(
                            "composite_image_saved",
                            path=save_path,
                            content_id=content_id,
                        )
                
                result = self.analyzer.analyze_with_fallback(image_data)
                
                # Determine pass/fail status
                status = "❌ FAIL" if result.get("red_safe_zone", {}).get("contains_key_elements") else "✅ PASS"
                confidence = result.get("red_safe_zone", {}).get("confidence", 0)
                
                # Show completion with status
                if total_limit and start_time:
                    elapsed = time.time() - start_time
                    rate = item_number / elapsed if elapsed > 0 else 0
                    remaining = total_limit - item_number
                    eta_seconds = remaining / rate if rate > 0 else 0
                    print(f"   {status} (confidence: {confidence}%) | Rate: {rate * 60:.1f}/min | ETA: {eta_seconds:.0f}s\n")
                else:
                    print(f"   {status} (confidence: {confidence}%)\n")
                
                sot_result = SOTAnalysisResult(
                    content_id=content_id,
                    program_id=t.program_id,
                    sot_name=t.sot_name,
                    content_name=t.content_name,
                    content_type=t.content_type,
                    poster_img_url=t.poster_img_url,
                    analysis=result,
                    error=None,
                )
                if on_result:
                    on_result(sot_result)
                
                batch_item_count += 1
                
            except Exception as e:
                logger.error(
                    "poster_analysis_failed",
                    content_id=content_id,
                    error=str(e),
                )
                print(f"   ❌ ERROR: {str(e)}\n")
                
                sot_result = SOTAnalysisResult(
                    content_id=content_id,
                    program_id=t.program_id,
                    sot_name=t.sot_name,
                    content_name=t.content_name,
                    content_type=t.content_type,
                    poster_img_url=t.poster_img_url,
                    analysis=None,
                    error=str(e),
                )
                if on_result:
                    on_result(sot_result)
                
                batch_item_count += 1
        
        return None
    
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
