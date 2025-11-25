#!/usr/bin/env python3
"""Run analysis in manageable chunks to prevent stalling."""
import requests
import time
import json
from datetime import datetime

class ChunkedAnalysisRunner:
    def __init__(self, chunk_size=200, pause_between_chunks=30):
        self.chunk_size = chunk_size
        self.pause_between_chunks = pause_between_chunks
        self.base_url = "http://localhost:5000"
        
    def run_analysis_in_chunks(self, total_titles=3049, sot_types=None, shiny_only=True):
        """Run analysis in chunks to prevent stalling."""
        if sot_types is None:
            sot_types = ["just_added", "most_liked", "imdb", "rt"]
        
        chunks_needed = (total_titles + self.chunk_size - 1) // self.chunk_size
        successful_chunks = 0
        total_processed = 0
        
        print(f"🎯 Running {total_titles} titles in {chunks_needed} chunks of {self.chunk_size}")
        print("="*80)
        
        for chunk_num in range(chunks_needed):
            chunk_start = chunk_num * self.chunk_size
            chunk_limit = min(self.chunk_size, total_titles - chunk_start)
            
            print(f"\n📦 Chunk {chunk_num + 1}/{chunks_needed}")
            print(f"   Range: {chunk_start + 1} to {chunk_start + chunk_limit}")
            
            # Start the chunk
            response = requests.post(
                f"{self.base_url}/api/analyze",
                json={
                    "sot_types": sot_types,
                    "days_back": 365,
                    "limit": chunk_limit,
                    "shiny_only": shiny_only,
                    "description": f"Chunk {chunk_num + 1} of {chunks_needed} - Shiny titles"
                }
            )
            
            if response.status_code != 200:
                print(f"   ❌ Failed to start chunk: {response.text}")
                continue
                
            job_id = response.json()["job_id"]
            print(f"   Job ID: {job_id}")
            
            # Monitor the chunk
            if self._monitor_job(job_id, chunk_limit):
                successful_chunks += 1
                total_processed += chunk_limit
                print(f"   ✅ Chunk completed successfully")
            else:
                print(f"   ❌ Chunk failed or stalled")
                # Continue anyway to try remaining chunks
            
            # Pause between chunks
            if chunk_num < chunks_needed - 1:
                print(f"   ⏸️  Pausing {self.pause_between_chunks}s before next chunk...")
                time.sleep(self.pause_between_chunks)
        
        print(f"\n{'='*80}")
        print(f"📊 FINAL RESULTS:")
        print(f"   Total chunks: {chunks_needed}")
        print(f"   Successful chunks: {successful_chunks}")
        print(f"   Total titles processed: {total_processed}/{total_titles}")
        print(f"   Success rate: {(successful_chunks/chunks_needed)*100:.1f}%")
        
    def _monitor_job(self, job_id, expected_total, timeout_minutes=15):
        """Monitor a job until completion or timeout."""
        start_time = time.time()
        timeout_seconds = timeout_minutes * 60
        last_processed = -1
        stall_count = 0
        
        while time.time() - start_time < timeout_seconds:
            try:
                resp = requests.get(f"{self.base_url}/api/analyze/status/{job_id}")
                if resp.status_code == 200:
                    data = resp.json()
                    status = data.get("status")
                    processed = data.get("processed", 0)
                    errors = data.get("errors", 0)
                    
                    # Check for progress
                    if processed == last_processed:
                        stall_count += 1
                    else:
                        stall_count = 0
                    last_processed = processed
                    
                    print(f"\r   Progress: {processed}/{expected_total} | Errors: {errors} | Time: {int(time.time()-start_time)}s", end="", flush=True)
                    
                    if status == "completed":
                        print()  # New line
                        return True
                    elif status == "failed":
                        print(f"\n   Job failed: {data.get('error', 'Unknown error')}")
                        return False
                    elif stall_count > 30:  # 5 minutes of no progress
                        print(f"\n   Job stalled at {processed}/{expected_total}")
                        return False
                        
                time.sleep(10)
                
            except Exception as e:
                print(f"\n   Monitor error: {e}")
                time.sleep(10)
        
        print(f"\n   Timeout after {timeout_minutes} minutes")
        return False

if __name__ == "__main__":
    runner = ChunkedAnalysisRunner(chunk_size=200, pause_between_chunks=30)
    
    print("Choose run mode:")
    print("1. Test run (50 titles)")
    print("2. Small run (200 titles)")  
    print("3. Medium run (500 titles)")
    print("4. Full run (3049 titles)")
    
    choice = input("\nEnter choice (1-4): ").strip()
    
    if choice == "1":
        runner.chunk_size = 50
        runner.run_analysis_in_chunks(50)
    elif choice == "2":
        runner.run_analysis_in_chunks(200)
    elif choice == "3":
        runner.run_analysis_in_chunks(500)
    elif choice == "4":
        runner.run_analysis_in_chunks(3049)
    else:
        print("Invalid choice")
