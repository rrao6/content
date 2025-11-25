#!/usr/bin/env python3
"""Remove all duplicate entries from the database immediately."""
import os
import sys
import sqlite3
from pathlib import Path
from datetime import datetime

# Add paths
sys.path.append(str(Path(__file__).parent))
sys.path.append(str(Path(__file__).parent / 'red-zone-dashboard'))

# Load environment
from run_dashboard_clean import load_environment
load_environment()

from database import get_db_connection

print("🚨 DUPLICATE REMOVAL SCRIPT")
print("="*80)

# Connect to database
db_path = Path("red-zone-dashboard/red_zone_analysis.db")

if not db_path.exists():
    print("❌ Database not found!")
    sys.exit(1)

print(f"\n📊 Database: {db_path}")

# First, analyze the duplicates
with get_db_connection() as conn:
    cursor = conn.cursor()
    
    # 1. Find all duplicates
    print("\n1️⃣ Finding all duplicates...")
    print("-"*60)
    
    cursor.execute("""
        SELECT 
            content_id, 
            sot_name, 
            COUNT(*) as count,
            GROUP_CONCAT(id) as ids,
            GROUP_CONCAT(run_id) as run_ids
        FROM poster_results
        GROUP BY content_id, sot_name
        HAVING count > 1
        ORDER BY count DESC
    """)
    
    duplicates = cursor.fetchall()
    
    if not duplicates:
        print("✅ No duplicates found!")
        sys.exit(0)
    
    print(f"❌ Found {len(duplicates)} duplicate groups")
    
    # Show sample duplicates
    print("\nSample duplicates:")
    total_duplicate_records = 0
    for i, (content_id, sot_name, count, ids, run_ids) in enumerate(duplicates[:10]):
        total_duplicate_records += count - 1  # -1 because we keep one
        print(f"{i+1:3d}. Content {content_id}, SOT '{sot_name}': {count} copies")
        print(f"     IDs: {ids}")
        print(f"     Runs: {run_ids}")
    
    # Calculate total duplicate records
    cursor.execute("""
        SELECT SUM(count - 1) as total_duplicates
        FROM (
            SELECT content_id, sot_name, COUNT(*) as count
            FROM poster_results
            GROUP BY content_id, sot_name
            HAVING count > 1
        )
    """)
    
    total_to_remove = cursor.fetchone()[0]
    print(f"\n📊 Total duplicate records to remove: {total_to_remove}")
    
    # 2. Create backup
    print("\n2️⃣ Creating backup...")
    print("-"*60)
    
    backup_path = db_path.with_suffix('.backup.' + datetime.now().strftime('%Y%m%d_%H%M%S') + '.db')
    
    cursor.execute("VACUUM INTO ?", (str(backup_path),))
    print(f"✅ Backup created: {backup_path}")
    
    # 3. Remove duplicates (keep the most recent one)
    print("\n3️⃣ Removing duplicates (keeping most recent)...")
    print("-"*60)
    
    # Get IDs to delete (keep the one with highest ID for each duplicate group)
    cursor.execute("""
        WITH duplicates AS (
            SELECT 
                id,
                content_id,
                sot_name,
                created_at,
                ROW_NUMBER() OVER (
                    PARTITION BY content_id, sot_name 
                    ORDER BY created_at DESC, id DESC
                ) as rn
            FROM poster_results
        )
        SELECT id 
        FROM duplicates 
        WHERE rn > 1
    """)
    
    ids_to_delete = [row[0] for row in cursor.fetchall()]
    
    if ids_to_delete:
        print(f"   Deleting {len(ids_to_delete)} duplicate records...")
        
        # Delete in batches
        batch_size = 100
        for i in range(0, len(ids_to_delete), batch_size):
            batch = ids_to_delete[i:i+batch_size]
            placeholders = ','.join('?' * len(batch))
            cursor.execute(f"DELETE FROM poster_results WHERE id IN ({placeholders})", batch)
            print(f"   Deleted batch {i//batch_size + 1}/{(len(ids_to_delete) + batch_size - 1)//batch_size}")
        
        conn.commit()
        print(f"✅ Removed {len(ids_to_delete)} duplicate records")
    
    # 4. Verify no duplicates remain
    print("\n4️⃣ Verifying cleanup...")
    print("-"*60)
    
    cursor.execute("""
        SELECT COUNT(*) FROM (
            SELECT content_id, sot_name, COUNT(*) as count
            FROM poster_results
            GROUP BY content_id, sot_name
            HAVING count > 1
        )
    """)
    
    remaining_dups = cursor.fetchone()[0]
    
    if remaining_dups == 0:
        print("✅ All duplicates removed successfully!")
    else:
        print(f"❌ Still {remaining_dups} duplicate groups remaining")
    
    # 5. Update statistics
    cursor.execute("SELECT COUNT(*) FROM poster_results")
    final_count = cursor.fetchone()[0]
    
    print(f"\n📊 Final record count: {final_count:,}")
    
    # 6. Add unique constraint to prevent future duplicates
    print("\n5️⃣ Adding protection against future duplicates...")
    print("-"*60)
    
    try:
        # Create unique index
        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_content_sot 
            ON poster_results(content_id, sot_name)
        """)
        conn.commit()
        print("✅ Added unique index on (content_id, sot_name)")
    except sqlite3.IntegrityError as e:
        print(f"❌ Could not create unique index: {e}")
        print("   This means there are still duplicates!")
    
    # 7. Update run statistics
    print("\n6️⃣ Updating run statistics...")
    print("-"*60)
    
    cursor.execute("""
        UPDATE analysis_runs
        SET total_analyzed = (
            SELECT COUNT(*) FROM poster_results WHERE run_id = analysis_runs.id
        )
    """)
    
    cursor.execute("""
        UPDATE analysis_runs
        SET pass_count = (
            SELECT COUNT(*) FROM poster_results 
            WHERE run_id = analysis_runs.id AND has_elements = 0
        )
    """)
    
    cursor.execute("""
        UPDATE analysis_runs
        SET fail_count = (
            SELECT COUNT(*) FROM poster_results 
            WHERE run_id = analysis_runs.id AND has_elements = 1
        )
    """)
    
    conn.commit()
    print("✅ Updated run statistics")

print("\n✨ DUPLICATE CLEANUP COMPLETE!")
print("="*80)
print("\n📋 Summary:")
print(f"   • Removed: {total_to_remove} duplicate records")
print(f"   • Backup saved: {backup_path}")
print(f"   • Unique constraint added")
print(f"   • Run statistics updated")
print("\n🎯 Your database is now clean and protected against future duplicates!")
print("="*80)
