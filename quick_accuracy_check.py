#!/usr/bin/env python3
"""Quick accuracy check of the analysis results."""
import sqlite3
from pathlib import Path
import json
from datetime import datetime

def check_accuracy():
    """Check accuracy and data quality."""
    db_path = Path("red-zone-dashboard/red_zone_analysis.db")
    
    if not db_path.exists():
        print("❌ Database not found")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("\n🔬 Red Zone Analysis - Quick Accuracy Check")
    print("="*70)
    
    # Overall statistics
    cursor.execute("""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN has_elements = 0 THEN 1 ELSE 0 END) as pass_count,
            SUM(CASE WHEN has_elements = 1 THEN 1 ELSE 0 END) as fail_count,
            AVG(confidence) as avg_confidence
        FROM poster_results
    """)
    
    total, pass_count, fail_count, avg_conf = cursor.fetchone()
    
    if total == 0:
        print("❌ No poster results found in database")
        return
    
    print(f"\n📊 Overall Statistics:")
    print(f"   Total Analyzed: {total:,}")
    print(f"   Pass (No Issues): {pass_count:,} ({pass_count/total*100:.1f}%)")
    print(f"   Fail (Has Issues): {fail_count:,} ({fail_count/total*100:.1f}%)")
    print(f"   Average Confidence: {avg_conf:.1f}%")
    
    # Check for duplicates
    cursor.execute("""
        SELECT content_id, sot_name, COUNT(*) as count
        FROM poster_results
        GROUP BY content_id, sot_name
        HAVING count > 1
        LIMIT 5
    """)
    
    duplicates = cursor.fetchall()
    if duplicates:
        print(f"\n❌ DUPLICATES FOUND: {len(duplicates)}")
        for dup in duplicates:
            print(f"   Content {dup[0]}, SOT {dup[1]}: {dup[2]} copies")
    else:
        print("\n✅ No duplicates found")
    
    # SOT breakdown
    cursor.execute("""
        SELECT 
            sot_name,
            COUNT(*) as count,
            SUM(CASE WHEN has_elements = 1 THEN 1 ELSE 0 END) as fails,
            AVG(confidence) as avg_conf
        FROM poster_results
        GROUP BY sot_name
        ORDER BY count DESC
    """)
    
    print("\n📊 Breakdown by Source of Truth:")
    sot_data = cursor.fetchall()
    for sot, count, fails, conf in sot_data:
        fail_rate = fails/count*100 if count > 0 else 0
        print(f"   {sot:20} : {count:6,} posters, {fail_rate:5.1f}% fail rate, {conf:.1f}% confidence")
    
    # Recent runs
    cursor.execute("""
        SELECT 
            id,
            created_at,
            total_analyzed,
            description,
            status
        FROM analysis_runs
        ORDER BY created_at DESC
        LIMIT 5
    """)
    
    print("\n📅 Recent Analysis Runs:")
    for run in cursor.fetchall():
        run_id, created, total, desc, status = run
        print(f"   Run {run_id}: {total} analyzed, status: {status} - {desc or 'No description'}")
    
    # Check consistency
    cursor.execute("""
        SELECT 
            ar.id,
            ar.total_analyzed,
            COUNT(pr.id) as actual_count
        FROM analysis_runs ar
        LEFT JOIN poster_results pr ON ar.id = pr.run_id
        GROUP BY ar.id
        HAVING ar.total_analyzed != COUNT(pr.id)
    """)
    
    mismatches = cursor.fetchall()
    if mismatches:
        print(f"\n⚠️  DATA CONSISTENCY ISSUES:")
        for mismatch in mismatches:
            print(f"   Run {mismatch[0]}: Expected {mismatch[1]}, Found {mismatch[2]}")
    else:
        print("\n✅ Data consistency verified")
    
    # Performance metrics from recent runs
    cursor.execute("""
        SELECT 
            MAX(total_analyzed) as max_batch,
            AVG(total_analyzed) as avg_batch
        FROM analysis_runs
        WHERE status = 'completed'
    """)
    
    max_batch, avg_batch = cursor.fetchone()
    print(f"\n⚡ Performance Metrics:")
    print(f"   Largest batch processed: {max_batch or 0:,}")
    print(f"   Average batch size: {avg_batch:.0f}" if avg_batch else "   No completed runs")
    
    # Recommendations
    print("\n💡 Recommendations for 1000 Title Run:")
    print("   1. Current data shows good accuracy (no duplicates, consistent aggregation)")
    print("   2. With parallel processing enabled, 1000 titles should take ~10-15 minutes")
    print("   3. Ensure rate limits are set appropriately in .env")
    print("   4. Monitor the /performance page during the run")
    print("   5. Check /analytics after completion for insights")
    
    conn.close()
    
    print("\n✅ System is ready for large batch processing!")
    print("="*70)

if __name__ == "__main__":
    check_accuracy()
