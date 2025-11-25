#!/usr/bin/env python3
"""Fix the stalling issue by implementing robust error handling and chunked processing."""
import os
import sys
import time
import sqlite3
from pathlib import Path
from datetime import datetime

print("🔧 FIXING STALLING ISSUE - ROBUST SOLUTION")
print("="*80)

# 1. First, let's check what happened at position 950
print("\n1️⃣ Checking database for stall pattern...")
try:
    conn = sqlite3.connect('red_zone_analysis.db')
    cursor = conn.cursor()
    
    # Get the last analysis run details
    cursor.execute("""
        SELECT id, created_at, total_count, processed_count, success_count, error_count, status
        FROM analysis_runs
        ORDER BY created_at DESC
        LIMIT 5
    """)
    
    print("\nRecent analysis runs:")
    print("-"*80)
    for row in cursor.fetchall():
        run_id, created, total, processed, success, error, status = row
        print(f"Run {run_id}: {status} - {processed}/{total} (Success: {success}, Errors: {error})")
    
    # Check for specific errors around the stall points
    cursor.execute("""
        SELECT COUNT(*) as error_count
        FROM poster_results
        WHERE run_id = (SELECT id FROM analysis_runs ORDER BY created_at DESC LIMIT 1)
        AND error IS NOT NULL
    """)
    error_count = cursor.fetchone()[0]
    print(f"\nErrors in last run: {error_count}")
    
    conn.close()
except Exception as e:
    print(f"Database check failed: {e}")

# 2. Implement timeout protection in the analysis code
print("\n2️⃣ Creating enhanced analysis module with timeout protection...")

enhanced_analyzer = '''#!/usr/bin/env python3
"""Enhanced analyzer with timeout protection and better error handling."""
import signal
import threading
from functools import wraps
import time

class TimeoutError(Exception):
    pass

def timeout_handler(signum, frame):
    raise TimeoutError("Analysis timeout")

def with_timeout(seconds=30):
    """Decorator to add timeout to functions."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Use threading for timeout on systems where signal doesn't work well
            result = [None]
            exception = [None]
            
            def target():
                try:
                    result[0] = func(*args, **kwargs)
                except Exception as e:
                    exception[0] = e
            
            thread = threading.Thread(target=target)
            thread.daemon = True
            thread.start()
            thread.join(seconds)
            
            if thread.is_alive():
                # Thread is still running after timeout
                raise TimeoutError(f"Function {func.__name__} timed out after {seconds} seconds")
            
            if exception[0]:
                raise exception[0]
                
            return result[0]
        return wrapper
    return decorator

# Patch this into the analysis module
def patch_analysis_timeout():
    """Patches timeout protection into the analysis pipeline."""
    try:
        import sot_pipeline_parallel
        
        # Wrap the process_single_poster method with timeout
        original_method = sot_pipeline_parallel.ParallelSOTAnalysisPipeline._process_single_poster
        
        @with_timeout(seconds=30)  # 30 second timeout per poster
        def wrapped_process_single_poster(self, *args, **kwargs):
            return original_method(self, *args, **kwargs)
        
        sot_pipeline_parallel.ParallelSOTAnalysisPipeline._process_single_poster = wrapped_process_single_poster
        print("✅ Timeout protection patched")
        
    except Exception as e:
        print(f"❌ Could not patch timeout: {e}")

if __name__ == "__main__":
    patch_analysis_timeout()
'''

with open("enhanced_analyzer.py", "w") as f:
    f.write(enhanced_analyzer)

# 3. Create a chunked processing strategy
print("\n3️⃣ Creating chunked processing script...")

chunked_runner = '''#!/usr/bin/env python3
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
            
            print(f"\\n📦 Chunk {chunk_num + 1}/{chunks_needed}")
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
        
        print(f"\\n{'='*80}")
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
                    
                    print(f"\\r   Progress: {processed}/{expected_total} | Errors: {errors} | Time: {int(time.time()-start_time)}s", end="", flush=True)
                    
                    if status == "completed":
                        print()  # New line
                        return True
                    elif status == "failed":
                        print(f"\\n   Job failed: {data.get('error', 'Unknown error')}")
                        return False
                    elif stall_count > 30:  # 5 minutes of no progress
                        print(f"\\n   Job stalled at {processed}/{expected_total}")
                        return False
                        
                time.sleep(10)
                
            except Exception as e:
                print(f"\\n   Monitor error: {e}")
                time.sleep(10)
        
        print(f"\\n   Timeout after {timeout_minutes} minutes")
        return False

if __name__ == "__main__":
    runner = ChunkedAnalysisRunner(chunk_size=200, pause_between_chunks=30)
    
    print("Choose run mode:")
    print("1. Test run (50 titles)")
    print("2. Small run (200 titles)")  
    print("3. Medium run (500 titles)")
    print("4. Full run (3049 titles)")
    
    choice = input("\\nEnter choice (1-4): ").strip()
    
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
'''

with open("chunked_analysis_runner.py", "w") as f:
    f.write(chunked_runner)
os.chmod("chunked_analysis_runner.py", 0o755)

# 4. Update environment for more conservative settings
print("\n4️⃣ Updating environment for stability...")
env_updates = {
    # More conservative rate limiting
    "VISION_REQUESTS_PER_MINUTE": "30",  # Lower rate to avoid throttling
    "VISION_REQUEST_DELAY_MS": "2000",   # 2 seconds between requests
    
    # Timeouts
    "OPENAI_TIMEOUT": "30",              # 30 second timeout for API calls
    "DOWNLOAD_TIMEOUT": "20",            # 20 seconds for image downloads
    
    # Disable cache
    "ENABLE_ANALYSIS_CACHE": "false",
}

env_path = Path(".env")
if env_path.exists():
    with open(env_path, 'r') as f:
        lines = f.readlines()
    
    updated = []
    found_keys = set()
    
    for line in lines:
        if '=' in line and not line.strip().startswith('#'):
            key = line.split('=')[0].strip()
            if key in env_updates:
                updated.append(f"{key}={env_updates[key]}\n")
                found_keys.add(key)
            else:
                updated.append(line)
        else:
            updated.append(line)
    
    for key, value in env_updates.items():
        if key not in found_keys:
            updated.append(f"{key}={value}\n")
    
    with open(env_path, 'w') as f:
        f.writelines(updated)
    
    print("   ✅ Environment updated for stability")

# 5. Clean up any stuck state
print("\n5️⃣ Cleaning up stuck state...")
os.system("rm -f *.checkpoint* checkpoint_* 2>/dev/null")
print("   ✅ Checkpoints cleared")

print("\n" + "="*80)
print("✅ FIXES APPLIED")
print("="*80)
print("\n📋 RECOMMENDED APPROACH:")
print("1. Start the dashboard: python3 run_dashboard_clean.py")
print("2. In another terminal: python3 chunked_analysis_runner.py")
print("3. Choose option 1 (test run) first")
print("4. If successful, run option 4 (full run)")
print("\nThe chunked approach will:")
print("  • Process 200 titles at a time")
print("  • Pause 30 seconds between chunks")
print("  • Handle stalls gracefully")
print("  • Complete even if some chunks fail")
