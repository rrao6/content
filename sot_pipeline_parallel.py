"""Parallel processing implementation for SOT pipeline."""
import json
import time
import threading
import queue
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable, Set, Tuple
from dataclasses import dataclass, field

import structlog

from config import DatabricksConfig, get_config
from service import ContentService, EligibleTitlesService
from analysis import SafeZoneAnalyzer, _download_image_to_base64
from sot_repository import EligibleTitle
from sot_pipeline import SOTAnalysisResult, SOTAnalysisCheckpoint

logger = structlog.get_logger(__name__)


class ParallelSOTAnalysisPipeline:
    """Pipeline for analyzing eligible titles with parallel processing support."""
    
    def __init__(
        self,
        eligible_service: EligibleTitlesService,
        content_service: ContentService,
        analyzer: SafeZoneAnalyzer,
        config: Optional[DatabricksConfig] = None,
        max_workers: int = 10,
    ):
        self.eligible_service = eligible_service
        self.content_service = content_service
        self.analyzer = analyzer
        self.config = config or get_config()
        self.checkpoint_path = Path("sot_analysis_checkpoint.json")
        self.max_workers = max_workers
        
        # Thread-safe components
        self.progress_lock = threading.Lock()
        self.checkpoint_lock = threading.Lock()
        self.rate_limit_lock = threading.Lock()
        self.last_request_times = []
        
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
        """Run parallel analysis on eligible titles."""
        
        # Load or create checkpoint
        checkpoint = None
        if resume and self.checkpoint_path.exists():
            checkpoint = SOTAnalysisCheckpoint.load(self.checkpoint_path)
            if checkpoint:
                logger.info(
                    "resuming_from_checkpoint",
                    processed=checkpoint.processed_count,
                    success=checkpoint.success_count,
                    errors=checkpoint.error_count,
                )
        
        if not checkpoint:
            checkpoint = SOTAnalysisCheckpoint(
                start_time=datetime.now(),
                last_updated=datetime.now(),
                total_titles=0,
                processed_count=0,
                success_count=0,
                error_count=0,
            )
        
        # Setup progress reporting
        def report_progress(event: str, result: Optional[SOTAnalysisResult] = None, message: Optional[str] = None):
            if not progress_callback:
                return
            
            with self.progress_lock:
                payload: Dict[str, Any] = {
                    "event": event,
                    "processed": checkpoint.processed_count,
                    "success": checkpoint.success_count,
                    "errors": checkpoint.error_count,
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
        
        # Fetch eligible titles
        print(f"\n🚀 Starting Parallel SOT Analysis Pipeline")
        print(f"{'='*70}")
        print(f"📅 Days back: {days_back}")
        print(f"🎯 SOT types: {sot_types if sot_types else 'ALL'}")
        print(f"📊 Limit: {limit if limit else 'No limit'}")
        print(f"⚡ Parallel workers: {self.max_workers}")
        print(f"💾 Save composite images: {save_composite_images}")
        print(f"{'='*70}\n")
        
        report_progress("started", message=f"Starting parallel analysis with {self.max_workers} workers")
        
        # Get eligible titles
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
        
        # Process with parallel execution
        results = []
        processed_pairs_set = set(checkpoint.processed_pairs)
        start_time = time.time()
        
        # Collect eligible titles into batches
        current_batch = []
        total_to_process = 0
        
        for eligible_title in eligible_gen:
            content_id = eligible_title.content_id if eligible_title.content_id is not None else eligible_title.program_id
            key = self._make_result_key(content_id, eligible_title.sot_name)
            
            # Skip if already processed
            if key in processed_pairs_set:
                continue
                
            current_batch.append(eligible_title)
            total_to_process += 1
            
            # Process when batch is full
            if len(current_batch) >= batch_size:
                batch_results = self._process_batch_parallel(
                    current_batch,
                    download_images=download_images,
                    download_timeout=download_timeout,
                    save_composite_images=save_composite_images,
                    composite_image_dir=composite_image_dir,
                    checkpoint=checkpoint,
                    processed_pairs_set=processed_pairs_set,
                    report_progress=report_progress,
                    start_time=start_time,
                    total_limit=limit,
                )
                
                results.extend(batch_results)
                self._save_checkpoint(checkpoint)
                self._print_progress_summary(checkpoint, start_time, limit)
                
                current_batch = []
        
        # Process remaining batch
        if current_batch:
            batch_results = self._process_batch_parallel(
                current_batch,
                download_images=download_images,
                download_timeout=download_timeout,
                save_composite_images=save_composite_images,
                composite_image_dir=composite_image_dir,
                checkpoint=checkpoint,
                processed_pairs_set=processed_pairs_set,
                report_progress=report_progress,
                start_time=start_time,
                total_limit=limit,
            )
            
            results.extend(batch_results)
            self._save_checkpoint(checkpoint)
        
        # Clean up checkpoint on successful completion
        if not limit or checkpoint.processed_count >= limit:
            self.checkpoint_path.unlink(missing_ok=True)
            logger.info("checkpoint_removed_on_completion")
        
        # Final summary
        duration_seconds = time.time() - start_time
        duration_minutes = duration_seconds / 60
        
        print(f"\n{'='*70}")
        print(f"✨ Parallel Analysis Complete!")
        print(f"{'='*70}")
        print(f"📊 Total processed: {len(results)}")
        print(f"✅ Success: {checkpoint.success_count}")
        print(f"❌ Errors: {checkpoint.error_count}")
        print(f"⏱️  Duration: {duration_minutes:.1f} minutes ({duration_seconds:.0f} seconds)")
        if checkpoint.success_count > 0:
            avg_time = duration_seconds / checkpoint.success_count
            print(f"📈 Avg time per poster: {avg_time:.1f} seconds")
            print(f"🚀 Processing rate: {60 / avg_time:.1f} posters/minute")
        print(f"{'='*70}\n")
        
        report_progress("completed", message=f"Analysis complete: {checkpoint.success_count} success, {checkpoint.error_count} errors")
        
        return results
    
    def _process_batch_parallel(
        self,
        batch: List[EligibleTitle],
        download_images: bool,
        download_timeout: int,
        save_composite_images: bool,
        composite_image_dir: str,
        checkpoint: SOTAnalysisCheckpoint,
        processed_pairs_set: Set[str],
        report_progress: Callable,
        start_time: float,
        total_limit: Optional[int],
    ) -> List[SOTAnalysisResult]:
        """Process a batch of eligible titles in parallel."""
        import os
        import re
        import base64
        
        # Create composite image directory if needed
        if save_composite_images:
            os.makedirs(composite_image_dir, exist_ok=True)
        
        results = []
        
        # Create a thread pool executor
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            future_to_title = {}
            
            for title in batch:
                if not title.poster_img_url:
                    continue
                
                # Submit task to thread pool
                future = executor.submit(
                    self._process_single_poster,
                    title,
                    download_images,
                    download_timeout,
                    save_composite_images,
                    composite_image_dir,
                )
                future_to_title[future] = title
            
            # Process results as they complete
            for future in as_completed(future_to_title):
                title = future_to_title[future]
                
                try:
                    result = future.result()
                    
                    # Update checkpoint thread-safely
                    with self.checkpoint_lock:
                        key = self._make_result_key(result.content_id, result.sot_name)
                        if key not in processed_pairs_set:
                            processed_pairs_set.add(key)
                            checkpoint.processed_pairs.append(key)
                        
                        checkpoint.processed_count += 1
                        checkpoint.processed_ids.append(result.content_id)
                        
                        if result.error:
                            checkpoint.error_count += 1
                            checkpoint.errors[result.content_id] = result.error
                        else:
                            checkpoint.success_count += 1
                    
                    results.append(result)
                    
                    # Report progress
                    human_name = result.content_name or f"ID {result.content_id}"
                    progress_message = f"Processed {human_name} ({checkpoint.processed_count}/{total_limit or '∞'})"
                    
                    # Show real-time progress
                    elapsed = time.time() - start_time
                    rate = checkpoint.processed_count / elapsed if elapsed > 0 else 0
                    status = "❌ FAIL" if result.analysis and result.analysis.get("red_safe_zone", {}).get("contains_key_elements") else "✅ PASS"
                    confidence = result.analysis.get("red_safe_zone", {}).get("confidence", 0) if result.analysis else 0
                    
                    print(f"[Worker] {status} {human_name} (confidence: {confidence}%) | Total: {checkpoint.processed_count}/{total_limit} | Rate: {rate * 60:.1f}/min")
                    
                    report_progress("processed", result=result, message=progress_message)
                    
                except Exception as e:
                    logger.error(
                        "parallel_processing_error",
                        error=str(e),
                        title=title.content_name,
                    )
                    # Create error result
                    content_id = title.content_id if title.content_id is not None else title.program_id
                    error_result = SOTAnalysisResult(
                        content_id=content_id,
                        program_id=title.program_id,
                        sot_name=title.sot_name,
                        content_name=title.content_name,
                        content_type=title.content_type,
                        poster_img_url=title.poster_img_url,
                        analysis=None,
                        error=str(e),
                    )
                    results.append(error_result)
        
        return results
    
    def _process_single_poster(
        self,
        title: EligibleTitle,
        download_images: bool,
        download_timeout: int,
        save_composite_images: bool,
        composite_image_dir: str,
    ) -> SOTAnalysisResult:
        """Process a single poster (thread-safe)."""
        import os
        import re
        import base64
        
        content_id = title.content_id if title.content_id is not None else title.program_id
        
        try:
            # Apply rate limiting
            self._apply_rate_limiting()
            
            # Download and analyze the image
            image_data = _download_image_to_base64(title.poster_img_url, timeout=download_timeout)
            
            # Save composite image if debug mode enabled
            if save_composite_images:
                base64_match = re.match(r'data:image/[^;]+;base64,(.+)', image_data)
                if base64_match:
                    base64_data = base64_match.group(1)
                    image_bytes = base64.b64decode(base64_data)
                    save_path = os.path.join(composite_image_dir, f"content_{content_id}.png")
                    with open(save_path, 'wb') as f:
                        f.write(image_bytes)
            
            # Analyze the image
            result = self.analyzer.analyze_with_fallback(image_data)
            
            return SOTAnalysisResult(
                content_id=content_id,
                program_id=title.program_id,
                sot_name=title.sot_name,
                content_name=title.content_name,
                content_type=title.content_type,
                poster_img_url=title.poster_img_url,
                analysis=result,
                error=None,
            )
            
        except Exception as e:
            logger.error(
                "poster_analysis_failed",
                content_id=content_id,
                error=str(e),
            )
            
            return SOTAnalysisResult(
                content_id=content_id,
                program_id=title.program_id,
                sot_name=title.sot_name,
                content_name=title.content_name,
                content_type=title.content_type,
                poster_img_url=title.poster_img_url,
                analysis=None,
                error=str(e),
            )
    
    def _apply_rate_limiting(self):
        """Apply thread-safe rate limiting."""
        with self.rate_limit_lock:
            current_time = time.time()
            
            # Clean up old request times (outside 1-minute window)
            cutoff_time = current_time - 60.0
            self.last_request_times = [t for t in self.last_request_times if t > cutoff_time]
            
            # Check rate limit
            requests_per_minute = self.config.vision_requests_per_minute
            if len(self.last_request_times) >= requests_per_minute:
                # Calculate wait time
                oldest_request = min(self.last_request_times)
                wait_seconds = 60.0 - (current_time - oldest_request) + 0.1
                if wait_seconds > 0:
                    logger.info(
                        "rate_limit_wait",
                        wait_seconds=wait_seconds,
                        current_rpm=len(self.last_request_times),
                    )
                    time.sleep(wait_seconds)
            
            # Record this request
            self.last_request_times.append(time.time())
    
    def _save_checkpoint(self, checkpoint: SOTAnalysisCheckpoint):
        """Save checkpoint thread-safely."""
        with self.checkpoint_lock:
            checkpoint.last_updated = datetime.now()
            checkpoint.save(self.checkpoint_path)
    
    def _print_progress_summary(self, checkpoint: SOTAnalysisCheckpoint, start_time: float, limit: Optional[int]):
        """Print progress summary."""
        elapsed = time.time() - start_time
        rate = checkpoint.processed_count / elapsed if elapsed > 0 else 0
        eta_seconds = (limit - checkpoint.processed_count) / rate if rate > 0 and limit else 0
        
        pct_complete = (checkpoint.processed_count / limit * 100) if limit else 0
        
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
    
    @staticmethod
    def _make_result_key(content_id: Optional[int], sot_name: Optional[str]) -> str:
        """Create a unique key for tracking processed items."""
        base_id = content_id if content_id is not None else "unknown"
        return f"{base_id}:{sot_name or 'unknown'}"
