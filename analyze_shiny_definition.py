#!/usr/bin/env python3
"""Analyze how 'shiny' is defined in the content_info table."""
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

print("🔍 ANALYZING 'SHINY' DEFINITION IN CONTENT_INFO")
print("="*80)

config = get_config()
catalog = config.catalog
schema = config.schema_

with sql.connect(
    server_hostname=config.host,
    http_path=config.http_path,
    access_token=config.token,
) as connection:
    with connection.cursor() as cursor:
        # First, check table schema for tags column
        print("\n1️⃣ Checking content_info table structure...")
        print("-"*60)
        
        query_schema = f"""
        DESCRIBE {catalog}.tubidw.content_info
        """
        
        try:
            cursor.execute(query_schema)
            columns = cursor.fetchall()
            
            # Look for tags column
            tags_col = None
            for col in columns:
                if 'tags' in col[0].lower() or 'tag' in col[0].lower():
                    print(f"   Found column: {col[0]} - Type: {col[1]}")
                    tags_col = col[0]
            
            if not tags_col:
                print("   ⚠️ No 'tags' column found. Looking for other indicators...")
                # Show all columns that might be relevant
                for col in columns:
                    if any(word in col[0].lower() for word in ['shiny', 'premium', 'feature', 'badge', 'label']):
                        print(f"   Possible column: {col[0]} - Type: {col[1]}")
        except Exception as e:
            print(f"   Error checking schema: {e}")
        
        # Check for content with 'shiny' in tags
        print("\n2️⃣ Searching for 'shiny' in tags column...")
        print("-"*60)
        
        query_tags = f"""
        SELECT 
            content_id,
            content_name,
            tags,
            content_type
        FROM {catalog}.tubidw.content_info
        WHERE LOWER(tags) LIKE '%shiny%'
        LIMIT 10
        """
        
        try:
            cursor.execute(query_tags)
            results = cursor.fetchall()
            
            if results:
                print(f"   Found {len(results)} titles with 'shiny' in tags:")
                for i, (cid, name, tags, ctype) in enumerate(results, 1):
                    print(f"   {i}. {name} ({ctype})")
                    print(f"      Tags: {tags}")
                    print()
            else:
                print("   ❌ No titles found with 'shiny' in tags column")
        except Exception as e:
            print(f"   Error: {e}")
            print("   (tags column might not exist)")
        
        # Count total shiny titles
        print("\n3️⃣ Counting shiny titles in SOT...")
        print("-"*60)
        
        # First, let's see what makes a title "shiny" in SOT context
        query_sot_shiny = f"""
        WITH sot_titles AS (
            SELECT DISTINCT
                sot.program_id,
                sot.sot_name,
                ci.content_id,
                ci.content_name,
                ci.content_type,
                ci.tags,
                ci.poster_img_url
            FROM {catalog}.{schema}.source_of_truth sot
            JOIN {catalog}.tubidw.content_info ci
                ON sot.program_id = ci.content_id
            WHERE sot.ds >= DATE_SUB(CURRENT_DATE(), 30)
                AND ci.active = true
                AND ci.poster_img_url IS NOT NULL
        )
        SELECT 
            COUNT(DISTINCT content_id) as total_sot_titles,
            SUM(CASE WHEN LOWER(tags) LIKE '%shiny%' THEN 1 ELSE 0 END) as shiny_tag_count
        FROM sot_titles
        """
        
        try:
            cursor.execute(query_sot_shiny)
            result = cursor.fetchone()
            total_sot, shiny_count = result
            
            print(f"   Total SOT titles (last 30 days): {total_sot:,}")
            print(f"   Titles with 'shiny' tag: {shiny_count:,}")
            print(f"   Percentage: {shiny_count/total_sot*100:.1f}%" if total_sot > 0 else "   No SOT titles found")
        except Exception as e:
            print(f"   Error counting shiny titles: {e}")
        
        # Check SOT distribution by shiny status
        print("\n4️⃣ SOT Distribution by Shiny Status...")
        print("-"*60)
        
        query_sot_dist = f"""
        WITH sot_titles AS (
            SELECT DISTINCT
                sot.sot_name,
                ci.content_id,
                CASE WHEN LOWER(ci.tags) LIKE '%shiny%' THEN 1 ELSE 0 END as is_shiny
            FROM {catalog}.{schema}.source_of_truth sot
            JOIN {catalog}.tubidw.content_info ci
                ON sot.program_id = ci.content_id
            WHERE sot.ds >= DATE_SUB(CURRENT_DATE(), 30)
                AND ci.active = true
                AND ci.poster_img_url IS NOT NULL
        )
        SELECT 
            sot_name,
            COUNT(DISTINCT content_id) as total,
            SUM(is_shiny) as shiny_count
        FROM sot_titles
        GROUP BY sot_name
        ORDER BY total DESC
        LIMIT 10
        """
        
        try:
            cursor.execute(query_sot_dist)
            results = cursor.fetchall()
            
            print(f"{'SOT Type':20} {'Total':>10} {'Shiny':>10} {'%':>8}")
            print("-"*50)
            for sot_name, total, shiny in results:
                pct = shiny/total*100 if total > 0 else 0
                print(f"{sot_name:20} {total:>10,} {shiny:>10,} {pct:>7.1f}%")
        except Exception as e:
            print(f"   Error: {e}")
        
        # Sample some shiny titles
        print("\n5️⃣ Sample Shiny Titles from SOT...")
        print("-"*60)
        
        query_sample = f"""
        SELECT DISTINCT
            ci.content_id,
            ci.content_name,
            ci.content_type,
            ci.tags,
            sot.sot_name
            FROM {catalog}.{schema}.source_of_truth sot
        JOIN {catalog}.tubidw.content_info ci
            ON sot.program_id = ci.content_id
        WHERE sot.ds >= DATE_SUB(CURRENT_DATE(), 7)
            AND ci.active = true
            AND ci.poster_img_url IS NOT NULL
            AND LOWER(ci.tags) LIKE '%shiny%'
        LIMIT 5
        """
        
        try:
            cursor.execute(query_sample)
            results = cursor.fetchall()
            
            if results:
                for i, (cid, name, ctype, tags, sot_name) in enumerate(results, 1):
                    print(f"{i}. {name} ({ctype})")
                    print(f"   ID: {cid}")
                    print(f"   SOT: {sot_name}")
                    print(f"   Tags: {tags}")
                    print()
            else:
                print("   No shiny titles found in recent SOT data")
        except Exception as e:
            print(f"   Error: {e}")

print("\n✅ Analysis Complete!")
print("="*80)
