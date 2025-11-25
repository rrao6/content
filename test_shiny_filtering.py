#!/usr/bin/env python3
"""Test shiny filtering with the updated query."""
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add paths
sys.path.append(str(Path(__file__).parent))

# Load environment
from run_dashboard_clean import load_environment
load_environment()

from config import get_config
from service import EligibleTitlesService
from databricks import sql

print("🧪 TESTING SHINY FILTERING")
print("="*70)

config = get_config()

# Test 1: Direct SQL query for shiny titles
print("\n1️⃣ Testing direct shiny query...")
print("-"*50)

with sql.connect(
    server_hostname=config.host,
    http_path=config.http_path,
    access_token=config.token,
) as connection:
    with connection.cursor() as cursor:
        # Simple count of shiny titles in content_info
        query = f"""
        SELECT COUNT(DISTINCT content_id) as shiny_count
        FROM {config.catalog}.tubidw.content_info
        WHERE LOWER(tags) LIKE '%shiny%'
            AND active = true
            AND poster_img_url IS NOT NULL
        """
        
        cursor.execute(query)
        count = cursor.fetchone()[0]
        print(f"   Total shiny titles with posters: {count:,}")

# Test 2: Test the service layer
print("\n2️⃣ Testing EligibleTitlesService shiny filtering...")
print("-"*50)

try:
    service = EligibleTitlesService(config)
    
    # Try to iterate shiny titles
    count = 0
    sample_titles = []
    
    for title in service.iter_shiny_eligible_poster_images(
        days_back=30,
        batch_size=100,
        max_items=10
    ):
        count += 1
        if count <= 5:
            sample_titles.append(title)
    
    print(f"   Found {count} shiny titles")
    
    if sample_titles:
        print("\n   Sample titles:")
        for i, title in enumerate(sample_titles, 1):
            print(f"   {i}. {title.content_name} (ID: {title.content_id})")
            
except Exception as e:
    print(f"   Error: {e}")
    import traceback
    traceback.print_exc()

# Test 3: Check if shiny checkbox works in analyzer
print("\n3️⃣ Testing shiny_only parameter...")
print("-"*50)

import requests

try:
    response = requests.post(
        'http://localhost:5000/api/analyze',
        json={
            'sot_types': ['just_added'],
            'days_back': 7,
            'limit': 5,
            'shiny_only': True,
            'description': 'Test shiny filtering'
        }
    )
    
    if response.status_code == 200:
        print("   ✅ API accepts shiny_only parameter")
        job_id = response.json().get('job_id')
        print(f"   Job ID: {job_id}")
    else:
        print(f"   ❌ API error: {response.status_code}")
        print(f"   Response: {response.text}")
        
except Exception as e:
    print(f"   Error: {e}")

print("\n✅ Test Complete!")
print("="*70)
