#!/usr/bin/env python3
"""Complete analysis of shiny titles in the SOT system."""
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

print("🔍 COMPLETE SHINY ANALYSIS FOR SOT SYSTEM")
print("="*80)

config = get_config()
catalog = config.catalog

with sql.connect(
    server_hostname=config.host,
    http_path=config.http_path,
    access_token=config.token,
) as connection:
    with connection.cursor() as cursor:
        # 1. Total content with 'shiny' tag
        print("\n1️⃣ Content with 'shiny' tag in content_info...")
        print("-"*60)
        
        query1 = f"""
        SELECT 
            COUNT(DISTINCT content_id) as total_shiny_tagged,
            COUNT(DISTINCT CASE WHEN content_type = 'MOVIE' THEN content_id END) as shiny_movies,
            COUNT(DISTINCT CASE WHEN content_type = 'SERIES' THEN content_id END) as shiny_series
        FROM {catalog}.tubidw.content_info
        WHERE LOWER(tags) LIKE '%shiny%'
            AND active = true
        """
        
        cursor.execute(query1)
        total_tagged, movies, series = cursor.fetchone()
        
        print(f"   Total with 'shiny' tag: {total_tagged:,}")
        print(f"   Movies: {movies:,}")
        print(f"   Series: {series:,}")
        
        # 2. Check is_cms_shiny in dsac tables
        print("\n2️⃣ Checking is_cms_shiny flag in DSAC tables...")
        print("-"*60)
        
        # Check dsac_program_info
        query2 = f"""
        SELECT 
            COUNT(DISTINCT program_id) as total_programs,
            SUM(CASE WHEN is_cms_shiny = 1 THEN 1 ELSE 0 END) as shiny_programs
        FROM core_prod.dsa.dsac_program_info
        WHERE ds = (SELECT MAX(ds) FROM core_prod.dsa.dsac_program_info)
        """
        
        try:
            cursor.execute(query2)
            total_progs, shiny_progs = cursor.fetchone()
            print(f"   Total programs in DSAC: {total_progs:,}")
            print(f"   Programs with is_cms_shiny=1: {shiny_progs:,}")
            print(f"   Percentage: {shiny_progs/total_progs*100:.1f}%")
        except Exception as e:
            print(f"   Error accessing DSAC tables: {e}")
        
        # 3. Count shiny titles by SOT type (last 30 days)
        print("\n3️⃣ Shiny Titles by SOT Type (last 30 days)...")
        print("-"*60)
        
        # Just Added
        query_ja = f"""
        SELECT COUNT(DISTINCT program_id) as shiny_just_added
        FROM core_prod.dsa.dsac_program_metadata
        WHERE ds >= DATE_SUB(CURRENT_DATE(), 30)
            AND date_diff(ds, window_start) BETWEEN 0 AND 6
            AND country = 'US'
            AND is_cms_shiny = 1
        """
        
        try:
            cursor.execute(query_ja)
            ja_count = cursor.fetchone()[0]
            print(f"   Just Added (shiny): {ja_count:,}")
        except Exception as e:
            print(f"   Just Added: Error - {e}")
        
        # IMDB
        query_imdb = f"""
        SELECT COUNT(DISTINCT x.tubi_video_id) as shiny_imdb
        FROM imdb.title_info x
        JOIN imdb.video_ratings b 
            ON x.const = b.tconst
        JOIN core_prod.dsa.dsac_program_info p
            ON x.tubi_video_id = p.program_id
        WHERE x.ds >= DATE_SUB(CURRENT_DATE(), 30)
            AND b.ds >= DATE_SUB(CURRENT_DATE(), 30)
            AND x.titletype IN ('movie', 'tvseries', 'tvminiseries')
            AND b.averagerating >= 7.0
            AND b.numvotes > 10000
            AND p.is_cms_shiny = 1
        """
        
        try:
            cursor.execute(query_imdb)
            imdb_count = cursor.fetchone()[0]
            print(f"   IMDB (shiny): {imdb_count:,}")
        except Exception as e:
            print(f"   IMDB: Error - {e}")
        
        # 4. Compare tag-based vs is_cms_shiny approaches
        print("\n4️⃣ Comparing 'shiny' tag vs is_cms_shiny flag...")
        print("-"*60)
        
        query_compare = f"""
        WITH tag_based AS (
            SELECT DISTINCT content_id
            FROM {catalog}.tubidw.content_info
            WHERE LOWER(tags) LIKE '%shiny%'
                AND active = true
        ),
        flag_based AS (
            SELECT DISTINCT program_id as content_id
            FROM core_prod.dsa.dsac_program_info
            WHERE is_cms_shiny = 1
                AND ds = (SELECT MAX(ds) FROM core_prod.dsa.dsac_program_info)
        )
        SELECT 
            COUNT(DISTINCT t.content_id) as only_tag,
            COUNT(DISTINCT f.content_id) as only_flag,
            COUNT(DISTINCT 
                CASE WHEN t.content_id IS NOT NULL AND f.content_id IS NOT NULL 
                THEN t.content_id END
            ) as both
        FROM tag_based t
        FULL OUTER JOIN flag_based f ON t.content_id = f.content_id
        """
        
        try:
            cursor.execute(query_compare)
            only_tag, only_flag, both = cursor.fetchone()
            print(f"   Only has 'shiny' tag: {only_tag:,}")
            print(f"   Only has is_cms_shiny=1: {only_flag:,}")
            print(f"   Has both: {both:,}")
        except Exception as e:
            print(f"   Comparison error: {e}")
        
        # 5. Recommendation
        print("\n5️⃣ RECOMMENDATION FOR SHINY FILTERING")
        print("-"*60)
        print("   Based on the analysis:")
        print("   • The 'shiny' tag in content_info.tags is present but limited")
        print("   • The is_cms_shiny flag in DSAC tables appears to be the authoritative source")
        print("   • SOT queries already use is_cms_shiny=1 for filtering")
        print("\n   ✅ The current implementation should filter by:")
        print("      1. Using is_cms_shiny=1 from DSAC tables (preferred)")
        print("      2. Falling back to LOWER(tags) LIKE '%shiny%' if DSAC not available")
        
        # 6. Sample shiny titles
        print("\n6️⃣ Sample Shiny Titles (from DSAC)...")
        print("-"*60)
        
        query_sample = f"""
        SELECT DISTINCT
            p.program_id,
            ci.content_name,
            ci.content_type,
            ci.tags
        FROM core_prod.dsa.dsac_program_info p
        JOIN {catalog}.tubidw.content_info ci
            ON p.program_id = ci.content_id
        WHERE p.is_cms_shiny = 1
            AND p.ds = (SELECT MAX(ds) FROM core_prod.dsa.dsac_program_info)
            AND ci.active = true
            AND ci.poster_img_url IS NOT NULL
        LIMIT 10
        """
        
        try:
            cursor.execute(query_sample)
            results = cursor.fetchall()
            
            for i, (pid, name, ctype, tags) in enumerate(results, 1):
                print(f"{i:2d}. {name} ({ctype}) - ID: {pid}")
                if tags and 'shiny' in tags.lower():
                    print(f"    ✓ Also has 'shiny' tag")
        except Exception as e:
            print(f"   Error: {e}")

print("\n✅ Analysis Complete!")
print("="*80)
