#!/usr/bin/env python3
"""Verify that shiny titles query returns no duplicates."""
import os
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from run_dashboard_clean import load_environment
load_environment()

from config import get_config
from databricks import sql
from sot_query import get_shiny_eligible_titles_with_content_query

config = get_config()

print("🔍 Verifying No Duplicates in Shiny Titles Query")
print("="*70)

# Run the query
query = get_shiny_eligible_titles_with_content_query(sot_types=['just_added', 'most_liked', 'imdb', 'rt'])
query += " LIMIT 100"  # Just check first 100

print("Running query to check for duplicates...")
print("-"*70)

try:
    with sql.connect(
        server_hostname=config.host,
        http_path=config.http_path,
        access_token=config.token,
    ) as connection:
        with connection.cursor() as cursor:
            cursor.execute(query)
            results = cursor.fetchall()
            
            # Track content_ids to check for duplicates
            content_ids = {}
            duplicates = []
            
            for row in results:
                content_id = row[2]  # content_id is 3rd column
                content_name = row[3]  # content_name is 4th column
                sot_name = row[1]  # sot_name is 2nd column
                
                if content_id in content_ids:
                    duplicates.append({
                        'content_id': content_id,
                        'content_name': content_name,
                        'sot_names': [content_ids[content_id]['sot'], sot_name]
                    })
                else:
                    content_ids[content_id] = {
                        'name': content_name,
                        'sot': sot_name
                    }
            
            print(f"✅ Total rows returned: {len(results)}")
            print(f"✅ Unique content_ids: {len(content_ids)}")
            
            if duplicates:
                print(f"\n❌ Found {len(duplicates)} duplicates:")
                for dup in duplicates[:5]:  # Show first 5
                    print(f"   - {dup['content_name']} (ID: {dup['content_id']})")
                    print(f"     SOTs: {', '.join(dup['sot_names'])}")
            else:
                print("\n✅ NO DUPLICATES FOUND! Each content appears only once.")
            
            # Show sample of results
            print("\n📋 Sample Results (first 5):")
            print("-"*70)
            for i, row in enumerate(results[:5], 1):
                print(f"{i}. {row[3]} (ID: {row[2]}, SOT: {row[1]})")
                
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*70)
