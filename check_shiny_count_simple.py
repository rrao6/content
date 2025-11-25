#!/usr/bin/env python3
"""Simple check for shiny titles count."""
import os
import sys
from pathlib import Path

# Add paths
sys.path.append(str(Path(__file__).parent))

# Load environment
from run_dashboard_clean import load_environment
load_environment()

from config import get_config
from databricks import sql

print("🔍 CHECKING SHINY TITLES COUNT")
print("="*70)

config = get_config()

# Direct SQL query to count shiny titles
with sql.connect(
    server_hostname=config.host,
    http_path=config.http_path,
    access_token=config.token,
) as connection:
    with connection.cursor() as cursor:
        # Count total shiny titles
        query = f"""
        SELECT 
            COUNT(DISTINCT content_id) as total_shiny
        FROM {config.catalog}.tubidw.content_info
        WHERE active = true
            AND poster_img_url IS NOT NULL
            AND poster_img_url != ''
            AND is_shiny = 1
        """
        
        cursor.execute(query)
        result = cursor.fetchone()
        total_shiny = result[0]
        
        print(f"\n📊 Total Shiny Titles in Database: {total_shiny:,}")
        
        # Count by content type
        query2 = f"""
        SELECT 
            content_type,
            COUNT(DISTINCT content_id) as count
        FROM {config.catalog}.tubidw.content_info
        WHERE active = true
            AND poster_img_url IS NOT NULL
            AND poster_img_url != ''
            AND is_shiny = 1
        GROUP BY content_type
        ORDER BY count DESC
        """
        
        cursor.execute(query2)
        results = cursor.fetchall()
        
        print("\n📊 Shiny Titles by Content Type:")
        print("-"*40)
        for content_type, count in results:
            print(f"{content_type:15}: {count:,}")
        
        # Count eligible shiny titles from SOT (last 30 days)
        query3 = f"""
        SELECT COUNT(DISTINCT ci.content_id) as eligible_shiny
        FROM {config.catalog}.{config.content_schema}.source_of_truth sot
        JOIN {config.catalog}.tubidw.content_info ci
            ON sot.program_id = ci.content_id
        WHERE sot.ds >= DATE_SUB(CURRENT_DATE(), 30)
            AND ci.active = true
            AND ci.poster_img_url IS NOT NULL
            AND ci.poster_img_url != ''
            AND ci.is_available = 1
            AND ci.is_shiny = 1
        """
        
        cursor.execute(query3)
        result = cursor.fetchone()
        eligible_shiny = result[0]
        
        print(f"\n📊 Eligible Shiny Titles (last 30 days): {eligible_shiny:,}")
        
        # Sample of shiny titles
        query4 = f"""
        SELECT 
            content_id,
            content_name,
            content_type
        FROM {config.catalog}.tubidw.content_info
        WHERE active = true
            AND poster_img_url IS NOT NULL
            AND is_shiny = 1
        LIMIT 10
        """
        
        cursor.execute(query4)
        results = cursor.fetchall()
        
        print("\n📋 Sample Shiny Titles:")
        print("-"*60)
        for i, (content_id, name, content_type) in enumerate(results, 1):
            print(f"{i:2d}. {name} ({content_type}) - ID: {content_id}")

print("\n✅ Analysis Summary:")
print(f"   • Total shiny titles: {total_shiny:,}")
print(f"   • Eligible (last 30 days): {eligible_shiny:,}")
print(f"   • You can analyze up to 1000 shiny titles per batch")
print("\n📍 To analyze shiny titles:")
print("   1. Go to http://localhost:5000/analyze")
print("   2. Check the 'Shiny Only' checkbox")
print("   3. Set batch size (up to 1000)")
print("   4. Click 'Start Analysis'")
print("="*70)
