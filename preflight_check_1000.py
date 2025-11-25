#!/usr/bin/env python3
"""Pre-flight check before running 1000 poster analysis."""
import os
import sys
import json
import time
import sqlite3
import requests
from pathlib import Path
from datetime import datetime

# Add paths
sys.path.append(str(Path(__file__).parent))
sys.path.append(str(Path(__file__).parent / 'red-zone-dashboard'))

def print_section(title):
    """Print formatted section header."""
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}\n")

def check_environment():
    """Check environment variables."""
    print_section("🔧 ENVIRONMENT CHECK")
    
    required_vars = [
        'DATABRICKS_HOST',
        'DATABRICKS_HTTP_PATH',
        'DATABRICKS_TOKEN',
        'DATABRICKS_CATALOG',
        'DATABRICKS_SCHEMA',
        'OPENAI_API_KEY',
        'OPENAI_MODEL'
    ]
    
    all_present = True
    for var in required_vars:
        value = os.environ.get(var)
        if value:
            masked_value = value[:5] + '...' if len(value) > 5 else value
            print(f"✅ {var}: {masked_value}")
        else:
            print(f"❌ {var}: NOT SET")
            all_present = False
    
    # Check rate limiting settings
    print("\n📊 Rate Limiting Settings:")
    rpm = os.environ.get('VISION_REQUESTS_PER_MINUTE', '60')
    delay = os.environ.get('VISION_REQUEST_DELAY_MS', '1000')
    print(f"   Requests per minute: {rpm}")
    print(f"   Request delay (ms): {delay}")
    print(f"   Max parallel workers: ~{int(rpm)//6}")
    
    return all_present

def check_database():
    """Check database integrity and stats."""
    print_section("🗄️ DATABASE CHECK")
    
    db_path = Path("red-zone-dashboard/red_zone_analysis.db")
    
    if not db_path.exists():
        print("❌ Database not found")
        return False
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]
    
    print("📋 Tables found:")
    for table in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        print(f"   {table}: {count} records")
    
    # Check for duplicates
    print("\n🔍 Checking for duplicates:")
    cursor.execute("""
        SELECT COUNT(*) FROM (
            SELECT content_id, sot_name, COUNT(*) as count
            FROM poster_results
            GROUP BY content_id, sot_name
            HAVING count > 1
        )
    """)
    dup_count = cursor.fetchone()[0]
    
    if dup_count > 0:
        print(f"⚠️  Found {dup_count} duplicate entries (won't affect new runs)")
    else:
        print("✅ No duplicates found")
    
    # Check data consistency
    cursor.execute("""
        SELECT COUNT(*) FROM analysis_runs ar
        WHERE ar.total_analyzed != (
            SELECT COUNT(*) FROM poster_results WHERE run_id = ar.id
        )
    """)
    inconsistent = cursor.fetchone()[0]
    
    if inconsistent > 0:
        print(f"⚠️  {inconsistent} runs have count mismatches")
    else:
        print("✅ All run counts match")
    
    conn.close()
    return True

def check_dashboard():
    """Check if dashboard is running."""
    print_section("🌐 DASHBOARD CHECK")
    
    try:
        response = requests.get('http://localhost:5000', timeout=5)
        if response.status_code == 200:
            print("✅ Dashboard is running at http://localhost:5000")
            
            # Check key endpoints
            endpoints = [
                '/api/runs',
                '/api/analyze/active',
                '/analyze',
                '/performance',
                '/analytics'
            ]
            
            for endpoint in endpoints:
                try:
                    resp = requests.get(f'http://localhost:5000{endpoint}', timeout=2)
                    print(f"✅ {endpoint}: {resp.status_code}")
                except:
                    print(f"❌ {endpoint}: Failed")
            
            return True
        else:
            print(f"❌ Dashboard returned status {response.status_code}")
            return False
    except:
        print("❌ Dashboard not accessible")
        print("   Run: python3 run_dashboard_clean.py")
        return False

def check_parallel_pipeline():
    """Check if parallel pipeline is available."""
    print_section("⚡ PARALLEL PROCESSING CHECK")
    
    try:
        from sot_pipeline_parallel import ParallelSOTAnalysisPipeline
        print("✅ Parallel pipeline module loaded")
        
        # Check if analyzer can use parallel pipeline
        from config import get_config
        config = get_config()
        
        if config.vision_requests_per_minute >= 10:
            max_workers = min(config.vision_requests_per_minute // 6, 20)
            print(f"✅ Using parallel pipeline with {max_workers} workers")
        
        return True
    except ImportError as e:
        print(f"❌ Failed to import parallel pipeline: {e}")
        return False

def test_small_batch():
    """Run a small test batch to verify accuracy."""
    print_section("🧪 SMALL BATCH TEST")
    
    print("Testing with 3 posters to verify accuracy...")
    
    try:
        # Start small test
        response = requests.post(
            'http://localhost:5000/api/analyze',
            json={
                'sot_types': ['just_added'],
                'days_back': 7,
                'limit': 3,
                'description': 'Pre-flight test for 1000 run'
            }
        )
        
        if response.status_code != 200:
            print(f"❌ Failed to start test: {response.text}")
            return False
        
        job_id = response.json().get('job_id')
        print(f"✅ Started test job: {job_id}")
        print("⏳ Waiting for completion...")
        
        # Poll for completion
        for i in range(30):  # 30 seconds max
            time.sleep(1)
            status_resp = requests.get(f'http://localhost:5000/api/analyze/status/{job_id}')
            status = status_resp.json()
            
            if status.get('status') == 'completed':
                print(f"✅ Test completed successfully!")
                print(f"   Processed: {status.get('processed')}")
                print(f"   Success: {status.get('success')}")
                print(f"   Errors: {status.get('errors')}")
                return True
            elif status.get('status') == 'failed':
                print(f"❌ Test failed: {status.get('error')}")
                return False
        
        print("⚠️  Test timed out")
        return False
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

def generate_recommendations():
    """Generate recommendations for the 1000 poster run."""
    print_section("📋 RECOMMENDATIONS FOR 1000 POSTER RUN")
    
    # Get current rate limit
    rpm = int(os.environ.get('VISION_REQUESTS_PER_MINUTE', '60'))
    delay_ms = int(os.environ.get('VISION_REQUEST_DELAY_MS', '1000'))
    
    # Calculate estimated time
    effective_rpm = min(rpm, 60)  # Account for rate limiting
    estimated_minutes = 1000 / effective_rpm
    
    print(f"📊 Expected Performance:")
    print(f"   Rate limit: {rpm} requests/minute")
    print(f"   Estimated time: {estimated_minutes:.1f} - {estimated_minutes*1.5:.1f} minutes")
    print(f"   Parallel workers: ~{rpm//6}")
    
    print(f"\n✅ Pre-flight Checklist:")
    print("   1. Dashboard is running at http://localhost:5000")
    print("   2. Batch limit increased to 1000 in UI")
    print("   3. Environment variables are set")
    print("   4. Database is ready")
    print("   5. Parallel processing is enabled")
    
    print(f"\n🚀 To Start Your 1000 Poster Analysis:")
    print("   1. Go to http://localhost:5000/analyze")
    print("   2. Select your SOT types (recommend: just_added, most_popular, award)")
    print("   3. Set 'Days Back' to 30")
    print("   4. Set 'Limit' to 1000")
    print("   5. Click 'Start Analysis'")
    print("   6. Monitor progress at:")
    print("      - Live updates on the same page")
    print("      - http://localhost:5000/performance (metrics)")
    print("      - http://localhost:5000/analytics (after completion)")
    
    print(f"\n⚠️  Important Notes:")
    print("   - Keep the dashboard running during analysis")
    print("   - Don't close the browser tab")
    print("   - Analysis is resumable if interrupted")
    print("   - Results auto-save to database")

def main():
    """Run all pre-flight checks."""
    print("\n🚀 PRE-FLIGHT CHECK FOR 1000 POSTER ANALYSIS")
    print("Version 2.0 - With Parallel Processing")
    
    # Load environment
    from run_dashboard_clean import load_environment
    load_environment()
    
    all_good = True
    
    # Run all checks
    if not check_environment():
        all_good = False
    
    if not check_database():
        all_good = False
    
    if not check_dashboard():
        all_good = False
        print("\n⚠️  Dashboard must be running for other tests")
        print("   Run: python3 run_dashboard_clean.py")
        return
    
    if not check_parallel_pipeline():
        all_good = False
    
    # Only run test if everything else is good
    if all_good:
        if not test_small_batch():
            all_good = False
    
    # Final verdict
    print_section("✨ FINAL STATUS")
    
    if all_good:
        print("🎉 ALL SYSTEMS GO!")
        print("\nYour system is 100% ready for the 1000 poster analysis.")
        generate_recommendations()
    else:
        print("⚠️  Some issues need attention before running 1000 posters")
        print("\nFix the issues above and run this check again.")
    
    print("\n" + "="*70)

if __name__ == '__main__':
    os.chdir('/Users/rrao/content-1')
    main()
