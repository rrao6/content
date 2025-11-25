#!/usr/bin/env python3
"""Check how many shiny titles are available in the database."""
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

print("🔍 CHECKING SHINY TITLES IN DATABASE")
print("="*70)

config = get_config()
eligible_service = EligibleTitlesService(config)

# Check for different time periods
time_periods = [7, 14, 30, 60, 90]

print("\n📊 Shiny Title Counts by Time Period:")
print("-"*50)

for days in time_periods:
    try:
        # Get shiny titles count using the iter_shiny_eligible_poster_images method
        count = 0
        batch_count = 0
        
        # Count by iterating through batches
        for batch in eligible_service.iter_shiny_eligible_poster_images(
            days_back=days,
            batch_size=1000,
            max_items=None  # Count all
        ):
            count += 1
            batch_count += 1
            
            # Show progress every 1000 items
            if count % 1000 == 0:
                print(f"   Counting... {count:,} so far", end='\r')
                
            # Stop at 20000 for quick estimate
            if count >= 20000:
                break
        
        if count >= 20000:
            print(f"Last {days:3d} days: {count:,}+ shiny titles (stopped counting at 20k)")
        else:
            print(f"Last {days:3d} days: {count:,} shiny titles")
            
    except Exception as e:
        print(f"Last {days:3d} days: Error - {e}")

# Also check by SOT type
print("\n📊 Shiny Titles by Source of Truth (last 30 days):")
print("-"*50)

try:
    # Direct SQL query to get counts by SOT
    with sql.connect(
        server_hostname=config.host,
        http_path=config.http_path,
        access_token=config.token,
    ) as connection:
        with connection.cursor() as cursor:
            # Query to count shiny titles by SOT
            query = f"""
            WITH shiny_titles AS (
                SELECT DISTINCT
                    ci.content_id,
                    ci.program_id,
                    sot.sot_name,
                    ci.content_name,
                    ci.poster_img_url
                FROM {config.catalog}.{config.schema}.source_of_truth sot
                JOIN {config.catalog}.tubidw.content_info ci
                    ON sot.program_id = ci.content_id
                WHERE sot.ds >= DATE_SUB(CURRENT_DATE(), 30)
                    AND ci.active = true
                    AND ci.poster_img_url IS NOT NULL
                    AND ci.poster_img_url != ''
                    AND ci.is_available = 1
                    AND ci.is_shiny = 1
            )
            SELECT 
                sot_name,
                COUNT(DISTINCT content_id) as count
            FROM shiny_titles
            GROUP BY sot_name
            ORDER BY count DESC
            """
            
            cursor.execute(query)
            results = cursor.fetchall()
            
            total_shiny = 0
            for sot_name, count in results:
                print(f"{sot_name:20}: {count:,} shiny titles")
                total_shiny += count
            
            print("-"*50)
            print(f"{'TOTAL UNIQUE':20}: ~{total_shiny//2:,} shiny titles (estimate)")
            
except Exception as e:
    print(f"Error querying by SOT: {e}")

# Show sample shiny titles
print("\n📋 Sample Shiny Titles (first 10):")
print("-"*50)

count = 0
for title in eligible_service.iter_shiny_eligible_poster_images(
    days_back=30,
    batch_size=10,
    max_items=10
):
    count += 1
    print(f"{count:2d}. {title.content_name} (ID: {title.content_id}, SOT: {title.sot_name})")

print("\n✅ To analyze ONLY shiny titles:")
print("   1. Go to http://localhost:5000/analyze")
print("   2. Check the 'Shiny Only' checkbox")
print("   3. Set your desired batch size (up to 1000)")
print("   4. Click 'Start Analysis'")
print("="*70)
