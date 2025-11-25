#!/usr/bin/env python3
"""Comprehensive fix and proper run setup for Red Zone Analysis."""
import os
import sys
import time
import shutil
import sqlite3
from pathlib import Path
from datetime import datetime

print("🔧 COMPREHENSIVE FIX AND SETUP FOR PROPER ANALYSIS")
print("="*80)

# 1. Clean up any stuck processes
print("\n1️⃣ Cleaning up processes...")
os.system("pkill -f 'python.*dashboard' 2>/dev/null || true")
os.system("pkill -f 'python.*analysis' 2>/dev/null || true")
time.sleep(2)
print("   ✅ Processes cleaned")

# 2. Remove ALL checkpoint files
print("\n2️⃣ Removing checkpoint files...")
checkpoint_patterns = [
    "*.checkpoint*",
    "*checkpoint*.json",
    ".checkpoint*",
    "checkpoint_*",
    "*_checkpoint*"
]

import glob
removed_count = 0
for pattern in checkpoint_patterns:
    for file in glob.glob(pattern, recursive=True):
        try:
            os.remove(file)
            removed_count += 1
        except:
            pass
print(f"   ✅ Removed {removed_count} checkpoint files")

# 3. Clean database from incomplete runs
print("\n3️⃣ Cleaning database...")
try:
    conn = sqlite3.connect('red_zone_analysis.db')
    cursor = conn.cursor()
    
    # Remove incomplete analysis runs
    cursor.execute("""
        DELETE FROM analysis_runs 
        WHERE status IN ('running', 'pending')
    """)
    deleted_runs = cursor.rowcount
    
    # Remove orphaned results
    cursor.execute("""
        DELETE FROM poster_results 
        WHERE run_id NOT IN (SELECT id FROM analysis_runs)
    """)
    deleted_results = cursor.rowcount
    
    conn.commit()
    conn.close()
    print(f"   ✅ Cleaned {deleted_runs} incomplete runs, {deleted_results} orphaned results")
except Exception as e:
    print(f"   ⚠️  Database cleanup warning: {e}")

# 4. Optimize .env configuration
print("\n4️⃣ Optimizing configuration...")
env_settings = {
    # Optimized rate limiting for stable performance
    "VISION_REQUESTS_PER_MINUTE": "60",  # Moderate rate to avoid throttling
    "VISION_REQUEST_DELAY_MS": "1000",    # 1 second delay between requests
    
    # Disable cache for accurate fresh results
    "ENABLE_ANALYSIS_CACHE": "false",
    
    # Connection optimization
    "DATABRICKS_CONNECTION_TIMEOUT": "60",
    "DATABRICKS_QUERY_TIMEOUT": "120",
    
    # Batch processing
    "DATABRICKS_MAX_ROWS_PER_BATCH": "500",
}

env_path = Path(".env")
if env_path.exists():
    # Read existing env
    with open(env_path, 'r') as f:
        lines = f.readlines()
    
    # Update or add settings
    updated_lines = []
    found_keys = set()
    
    for line in lines:
        if '=' in line and not line.strip().startswith('#'):
            key = line.split('=')[0].strip()
            if key in env_settings:
                updated_lines.append(f"{key}={env_settings[key]}\n")
                found_keys.add(key)
            else:
                updated_lines.append(line)
        else:
            updated_lines.append(line)
    
    # Add missing settings
    for key, value in env_settings.items():
        if key not in found_keys:
            updated_lines.append(f"{key}={value}\n")
    
    # Write back
    with open(env_path, 'w') as f:
        f.writelines(updated_lines)
    
    print("   ✅ Configuration optimized")

# 5. Create monitoring script
print("\n5️⃣ Creating monitoring script...")
monitor_script = """#!/usr/bin/env python3
import time
import requests
import json

print("📊 MONITORING ANALYSIS PROGRESS")
print("-"*50)

job_id = input("Enter job ID (or press Enter to get active): ").strip()

if not job_id:
    # Get active job
    try:
        resp = requests.get("http://localhost:5000/api/analyze/active")
        if resp.status_code == 200:
            data = resp.json()
            if data.get("job_id"):
                job_id = data["job_id"]
                print(f"Found active job: {job_id}")
            else:
                print("No active analysis found")
                exit(1)
    except:
        print("Could not connect to dashboard")
        exit(1)

# Monitor the job
last_processed = 0
stall_count = 0

while True:
    try:
        resp = requests.get(f"http://localhost:5000/api/analyze/status/{job_id}")
        if resp.status_code == 200:
            data = resp.json()
            status = data.get("status")
            processed = data.get("processed", 0)
            total = data.get("total", 0)
            errors = data.get("errors", 0)
            
            # Check for stalls
            if processed == last_processed:
                stall_count += 1
            else:
                stall_count = 0
            last_processed = processed
            
            # Display status
            print(f"\\rStatus: {status} | Progress: {processed}/{total} | Errors: {errors} | Stalls: {stall_count}", end="")
            
            if status == "completed":
                print(f"\\n✅ Analysis completed! Success: {data.get('success', 0)}, Errors: {errors}")
                break
            elif status == "failed":
                print(f"\\n❌ Analysis failed: {data.get('error', 'Unknown error')}")
                break
            elif stall_count > 30:  # 5 minutes of no progress
                print(f"\\n⚠️  Analysis appears stalled at {processed}/{total}")
                break
                
        time.sleep(10)  # Check every 10 seconds
        
    except KeyboardInterrupt:
        print("\\nMonitoring stopped by user")
        break
    except Exception as e:
        print(f"\\nMonitoring error: {e}")
        time.sleep(10)
"""

with open("monitor_analysis.py", "w") as f:
    f.write(monitor_script)
os.chmod("monitor_analysis.py", 0o755)
print("   ✅ Created monitor_analysis.py")

# 6. Create run strategy guide
print("\n6️⃣ Creating run strategy...")
strategy = """
🎯 RECOMMENDED RUN STRATEGY FOR 3,049 SHINY TITLES
=================================================

Phase 1: Test Run (5 minutes)
- Batch size: 50 shiny titles
- Purpose: Verify everything works
- Expected time: 2-3 minutes

Phase 2: Medium Run (30 minutes)  
- Batch size: 500 shiny titles
- Purpose: Test sustained performance
- Expected time: 20-30 minutes

Phase 3: Full Run (2-3 hours)
- Batch size: 3,049 shiny titles
- Purpose: Complete analysis
- Expected time: 2-3 hours with current settings

OPTIMIZED SETTINGS:
- Rate limit: 60 requests/minute (safe for OpenAI)
- Delay: 1 second between requests
- Workers: 3 parallel threads
- Expected throughput: ~20-30 posters/minute

MONITORING:
1. Run dashboard: python3 run_dashboard_clean.py
2. Start analysis via UI
3. In another terminal: python3 monitor_analysis.py
"""

print(strategy)

# 7. Start dashboard with proper settings
print("\n7️⃣ Starting dashboard...")
print("-"*80)
print("Dashboard will start in 5 seconds...")
print("Then go to: http://localhost:5000/analyze")
print("-"*80)

time.sleep(5)

# Import and run the dashboard starter
from run_dashboard_clean import main as run_dashboard
run_dashboard()
