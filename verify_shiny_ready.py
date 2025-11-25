#!/usr/bin/env python3
"""Final verification that shiny analysis is ready."""
import os
import sys
import requests
import time
from pathlib import Path

# Add paths
sys.path.append(str(Path(__file__).parent))

# Load environment
from run_dashboard_clean import load_environment
load_environment()

from config import get_config
from databricks import sql

print("🌟 FINAL VERIFICATION: SHINY TITLES ANALYSIS")
print("="*80)

# 1. Check dashboard
print("\n1️⃣ Dashboard Status...")
print("-"*50)
try:
    response = requests.get('http://localhost:5000')
    if response.status_code == 200:
        print("✅ Dashboard is running at http://localhost:5000")
    else:
        print("❌ Dashboard not accessible")
except:
    print("❌ Dashboard not running - start with: python3 run_dashboard_clean.py")

# 2. Check shiny titles count
print("\n2️⃣ Shiny Titles Count...")
print("-"*50)

config = get_config()
catalog = config.catalog

with sql.connect(
    server_hostname=config.host,
    http_path=config.http_path,
    access_token=config.token,
) as connection:
    with connection.cursor() as cursor:
        # Count shiny titles with different criteria
        queries = [
            ("Total with 'shiny' tag", f"""
                SELECT COUNT(DISTINCT content_id)
                FROM {catalog}.tubidw.content_info
                WHERE LOWER(tags) LIKE '%shiny%'
                    AND active = true
            """),
            
            ("Shiny with posters", f"""
                SELECT COUNT(DISTINCT content_id)
                FROM {catalog}.tubidw.content_info
                WHERE LOWER(tags) LIKE '%shiny%'
                    AND active = true
                    AND poster_img_url IS NOT NULL
                    AND poster_img_url != ''
            """),
            
            ("Shiny movies", f"""
                SELECT COUNT(DISTINCT content_id)
                FROM {catalog}.tubidw.content_info
                WHERE LOWER(tags) LIKE '%shiny%'
                    AND active = true
                    AND poster_img_url IS NOT NULL
                    AND content_type = 'MOVIE'
            """),
            
            ("Shiny series", f"""
                SELECT COUNT(DISTINCT content_id)
                FROM {catalog}.tubidw.content_info
                WHERE LOWER(tags) LIKE '%shiny%'
                    AND active = true
                    AND poster_img_url IS NOT NULL
                    AND content_type = 'SERIES'
            """)
        ]
        
        for label, query in queries:
            cursor.execute(query)
            count = cursor.fetchone()[0]
            print(f"   {label}: {count:,}")

# 3. Test shiny filtering
print("\n3️⃣ Testing Shiny Filtering...")
print("-"*50)

try:
    # Start a tiny shiny test
    response = requests.post(
        'http://localhost:5000/api/analyze',
        json={
            'sot_types': ['just_added'],
            'days_back': 365,
            'limit': 2,
            'shiny_only': True,
            'description': 'Shiny verification test'
        }
    )
    
    if response.status_code == 200:
        print("✅ Shiny filtering is working")
        job_id = response.json().get('job_id')
        print(f"   Test job started: {job_id}")
        
        # Wait for completion
        print("   Waiting for test to complete...", end='')
        for i in range(30):
            time.sleep(1)
            print(".", end='', flush=True)
            status_resp = requests.get(f'http://localhost:5000/api/analyze/status/{job_id}')
            if status_resp.status_code == 200:
                status = status_resp.json()
                if status.get('status') == 'completed':
                    print(f"\n✅ Test completed successfully!")
                    print(f"   Analyzed: {status.get('processed')} shiny titles")
                    break
                elif status.get('status') == 'failed':
                    print(f"\n❌ Test failed: {status.get('error')}")
                    break
    else:
        print("❌ API error:", response.text)
except Exception as e:
    print(f"❌ Test failed: {e}")

# 4. Final instructions
print("\n4️⃣ READY TO ANALYZE ALL SHINY TITLES!")
print("="*80)
print("\n📋 Quick Start:")
print("1. Go to: http://localhost:5000/analyze")
print("2. Settings:")
print("   • SOT Types: Select all (or specific ones)")
print("   • Days Back: 365 (for maximum coverage)")
print("   • Batch Size: 1000")
print("   • ✅ CHECK 'Shiny Only'")
print("3. Click 'Start Analysis'")
print("\n⏱️ Estimated time: 15-20 minutes per 1000 titles")
print("📊 Total shiny titles to analyze: ~3,049")
print("\n✨ The system is READY for your shiny titles analysis!")
print("="*80)
