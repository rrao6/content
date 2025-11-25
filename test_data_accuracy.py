#!/usr/bin/env python3
"""Comprehensive accuracy testing for Red Zone Analysis system."""
import os
import sys
import json
import time
import sqlite3
from pathlib import Path
from collections import defaultdict, Counter
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from config import get_config
from service import EligibleTitlesService
sys.path.append(str(Path(__file__).parent / 'red-zone-dashboard'))
from database import get_db_connection, PosterResult, AnalysisRun


class DataAccuracyTester:
    """Test data accuracy and integrity across the system."""
    
    def __init__(self):
        self.config = get_config()
        self.service = EligibleTitlesService()
        self.results = []
        self.errors = []
        
    def run_all_tests(self):
        """Run comprehensive accuracy tests."""
        print("\n🔬 Red Zone Analysis - Data Accuracy Test Suite")
        print("="*70)
        
        # Test 1: SOT Type Mapping Accuracy
        self.test_sot_mapping_accuracy()
        
        # Test 2: Duplicate Detection
        self.test_duplicate_prevention()
        
        # Test 3: Data Consistency
        self.test_data_consistency()
        
        # Test 4: Aggregation Accuracy
        self.test_aggregation_accuracy()
        
        # Test 5: Pass/Fail Accuracy
        self.test_pass_fail_accuracy()
        
        # Test 6: Database Integrity
        self.test_database_integrity()
        
        # Generate Report
        self.generate_accuracy_report()
    
    def test_sot_mapping_accuracy(self):
        """Test that SOT types are mapped correctly."""
        print("\n📋 Test 1: SOT Type Mapping Accuracy")
        print("-"*50)
        
        # Test mapping from UI labels to database values
        mappings = {
            "most_popular": "most_liked",
            "rotten_tomatoes": "rt",
            "just_added": "just_added",
            "leaving_soon": "leaving_soon",
            "imdb": "imdb",
            "awards": "award"
        }
        
        errors = 0
        for ui_label, db_value in mappings.items():
            # Query database for each SOT type
            counts = self.service.count_eligible_titles_by_sot(days_back=30)
            
            # Check if mapping exists
            if db_value in counts:
                print(f"✅ {ui_label} → {db_value}: {counts[db_value]} titles")
            else:
                print(f"❌ {ui_label} → {db_value}: NOT FOUND")
                errors += 1
        
        if errors == 0:
            print("\n✅ All SOT mappings are correct")
        else:
            print(f"\n❌ Found {errors} mapping errors")
            self.errors.append(f"SOT mapping errors: {errors}")
    
    def test_duplicate_prevention(self):
        """Test that duplicate prevention is working correctly."""
        print("\n🔍 Test 2: Duplicate Prevention")
        print("-"*50)
        
        # Get recent analysis runs
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, total_analyzed, parameters 
                FROM analysis_runs 
                WHERE status = 'completed' 
                ORDER BY created_at DESC 
                LIMIT 5
            """)
            runs = cursor.fetchall()
        
        duplicate_found = False
        
        for run in runs:
            run_id = run[0]
            
            # Check for duplicates within each run
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT content_id, sot_name, COUNT(*) as count
                    FROM poster_results
                    WHERE run_id = ?
                    GROUP BY content_id, sot_name
                    HAVING count > 1
                """, (run_id,))
                
                duplicates = cursor.fetchall()
                
                if duplicates:
                    duplicate_found = True
                    print(f"\n❌ Run {run_id}: Found {len(duplicates)} duplicate entries:")
                    for dup in duplicates[:5]:  # Show first 5
                        print(f"   - Content {dup[0]}, SOT {dup[1]}: {dup[2]} occurrences")
                else:
                    print(f"✅ Run {run_id}: No duplicates found")
        
        if not duplicate_found:
            print("\n✅ Duplicate prevention is working correctly")
        else:
            self.errors.append("Duplicate entries found in results")
    
    def test_data_consistency(self):
        """Test data consistency across tables."""
        print("\n🔒 Test 3: Data Consistency")
        print("-"*50)
        
        # Check that all poster_results have valid run_ids
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Orphaned results
            cursor.execute("""
                SELECT COUNT(*) 
                FROM poster_results pr
                LEFT JOIN analysis_runs ar ON pr.run_id = ar.id
                WHERE ar.id IS NULL
            """)
            orphaned = cursor.fetchone()[0]
            
            if orphaned > 0:
                print(f"❌ Found {orphaned} orphaned poster results")
                self.errors.append(f"Orphaned poster results: {orphaned}")
            else:
                print("✅ All poster results have valid run IDs")
            
            # Check run totals match actual counts
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
                print(f"\n❌ Found {len(mismatches)} runs with count mismatches:")
                for mismatch in mismatches[:5]:
                    print(f"   - Run {mismatch[0]}: Expected {mismatch[1]}, Found {mismatch[2]}")
                self.errors.append(f"Count mismatches in {len(mismatches)} runs")
            else:
                print("✅ All run counts match actual results")
    
    def test_aggregation_accuracy(self):
        """Test that aggregated statistics are accurate."""
        print("\n📊 Test 4: Aggregation Accuracy")
        print("-"*50)
        
        # Get aggregated stats
        stats = PosterResult.get_stats()
        
        # Verify manually
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Total count
            cursor.execute("SELECT COUNT(*) FROM poster_results")
            actual_total = cursor.fetchone()[0]
            
            # Pass/Fail counts
            cursor.execute("SELECT COUNT(*) FROM poster_results WHERE has_elements = 0")
            actual_pass = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM poster_results WHERE has_elements = 1")
            actual_fail = cursor.fetchone()[0]
            
            # Average confidence
            cursor.execute("SELECT AVG(confidence) FROM poster_results WHERE confidence IS NOT NULL")
            actual_avg_conf = cursor.fetchone()[0] or 0
        
        # Compare
        issues = []
        
        if stats['total'] != actual_total:
            issues.append(f"Total: reported {stats['total']}, actual {actual_total}")
        
        if stats.get('pass_count', 0) != actual_pass:
            issues.append(f"Pass count: reported {stats.get('pass_count', 0)}, actual {actual_pass}")
        
        if stats.get('fail_count', 0) != actual_fail:
            issues.append(f"Fail count: reported {stats.get('fail_count', 0)}, actual {actual_fail}")
        
        if abs(stats.get('avg_confidence', 0) - actual_avg_conf) > 0.1:
            issues.append(f"Avg confidence: reported {stats.get('avg_confidence', 0):.1f}, actual {actual_avg_conf:.1f}")
        
        if issues:
            print("❌ Aggregation issues found:")
            for issue in issues:
                print(f"   - {issue}")
            self.errors.extend(issues)
        else:
            print("✅ All aggregations are accurate")
            print(f"   - Total: {actual_total}")
            print(f"   - Pass: {actual_pass} ({actual_pass/actual_total*100:.1f}%)")
            print(f"   - Fail: {actual_fail} ({actual_fail/actual_total*100:.1f}%)")
            print(f"   - Avg Confidence: {actual_avg_conf:.1f}%")
    
    def test_pass_fail_accuracy(self):
        """Test pass/fail logic accuracy."""
        print("\n✅❌ Test 5: Pass/Fail Logic Accuracy")
        print("-"*50)
        
        # Sample recent results
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    id,
                    has_elements,
                    confidence,
                    justification,
                    analysis_json
                FROM poster_results
                ORDER BY created_at DESC
                LIMIT 100
            """)
            results = cursor.fetchall()
        
        logic_errors = 0
        confidence_issues = 0
        
        for result in results:
            result_id, has_elements, confidence, justification, analysis_json = result
            
            # Parse analysis JSON
            try:
                analysis = json.loads(analysis_json) if analysis_json else {}
                red_zone = analysis.get('red_safe_zone', {})
                
                # Check logic consistency
                api_has_elements = red_zone.get('contains_key_elements')
                
                if api_has_elements is not None and api_has_elements != bool(has_elements):
                    logic_errors += 1
                    print(f"❌ Logic mismatch in result {result_id}")
                
                # Check confidence range
                if confidence is not None and (confidence < 0 or confidence > 100):
                    confidence_issues += 1
                    print(f"❌ Invalid confidence {confidence} in result {result_id}")
                    
            except json.JSONDecodeError:
                print(f"⚠️  Invalid JSON in result {result_id}")
        
        if logic_errors == 0 and confidence_issues == 0:
            print("\n✅ Pass/Fail logic is consistent")
        else:
            print(f"\n❌ Found {logic_errors} logic errors and {confidence_issues} confidence issues")
            self.errors.append(f"Pass/Fail logic errors: {logic_errors}")
    
    def test_database_integrity(self):
        """Test database integrity and indexes."""
        print("\n🗄️  Test 6: Database Integrity")
        print("-"*50)
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Check indexes exist
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type = 'index' AND tbl_name = 'poster_results'
            """)
            indexes = [row[0] for row in cursor.fetchall()]
            
            required_indexes = [
                'idx_run_id',
                'idx_content_id',
                'idx_has_elements',
                'idx_sot_name'
            ]
            
            missing_indexes = []
            for req_idx in required_indexes:
                if req_idx not in indexes:
                    missing_indexes.append(req_idx)
            
            if missing_indexes:
                print(f"❌ Missing indexes: {', '.join(missing_indexes)}")
                self.errors.append(f"Missing indexes: {missing_indexes}")
            else:
                print("✅ All required indexes present")
            
            # Check for NULL values in critical fields
            cursor.execute("""
                SELECT COUNT(*) FROM poster_results
                WHERE content_id IS NULL OR sot_name IS NULL
            """)
            null_criticals = cursor.fetchone()[0]
            
            if null_criticals > 0:
                print(f"❌ Found {null_criticals} records with NULL critical fields")
                self.errors.append(f"NULL critical fields: {null_criticals}")
            else:
                print("✅ No NULL values in critical fields")
    
    def generate_accuracy_report(self):
        """Generate comprehensive accuracy report."""
        print("\n" + "="*70)
        print("📋 Accuracy Test Report")
        print("="*70)
        
        if not self.errors:
            print("\n✅ ALL TESTS PASSED - System is accurate and consistent!")
            
            # Show summary statistics
            with get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Overall stats
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total,
                        SUM(CASE WHEN has_elements = 0 THEN 1 ELSE 0 END) as pass,
                        SUM(CASE WHEN has_elements = 1 THEN 1 ELSE 0 END) as fail,
                        AVG(confidence) as avg_conf
                    FROM poster_results
                """)
                total, pass_count, fail_count, avg_conf = cursor.fetchone()
                
                # By SOT stats
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
                sot_stats = cursor.fetchall()
            
            print("\n📊 System Statistics:")
            print(f"   Total Analyzed: {total:,}")
            print(f"   Pass Rate: {pass_count/total*100:.1f}%")
            print(f"   Fail Rate: {fail_count/total*100:.1f}%")
            print(f"   Avg Confidence: {avg_conf:.1f}%")
            
            print("\n📊 By Source of Truth:")
            for sot, count, fails, sot_conf in sot_stats:
                fail_rate = fails/count*100 if count > 0 else 0
                print(f"   {sot}: {count:,} posters, {fail_rate:.1f}% fail rate, {sot_conf:.1f}% confidence")
        
        else:
            print(f"\n❌ FOUND {len(self.errors)} ISSUES:")
            for error in self.errors:
                print(f"   - {error}")
            
            print("\n⚠️  RECOMMENDATIONS:")
            print("   1. Review and fix data inconsistencies")
            print("   2. Re-run affected analyses")
            print("   3. Update validation logic")
            print("   4. Monitor future runs for accuracy")
        
        # Save report
        report_path = Path("accuracy_test_report.json")
        with open(report_path, 'w') as f:
            json.dump({
                "test_date": datetime.now().isoformat(),
                "passed": len(self.errors) == 0,
                "errors": self.errors,
                "recommendations": [
                    "Enable duplicate prevention in pipeline",
                    "Validate SOT mappings before analysis",
                    "Monitor aggregation accuracy",
                    "Regular database integrity checks"
                ]
            }, f, indent=2)
        
        print(f"\n📄 Report saved to: {report_path}")


def test_live_analysis_accuracy():
    """Test accuracy of a live analysis run."""
    print("\n🔴 Live Analysis Accuracy Test")
    print("-"*50)
    
    import requests
    
    # Start a small test analysis
    response = requests.post(
        "http://localhost:5000/api/analyze",
        json={
            "sot_types": ["just_added"],
            "days_back": 7,
            "limit": 5,
            "description": "Accuracy test batch"
        }
    )
    
    if response.status_code != 200:
        print("❌ Failed to start test analysis")
        return
    
    job_id = response.json().get('job_id')
    print(f"✅ Started test job: {job_id}")
    
    # Wait for completion
    print("⏳ Waiting for analysis to complete...")
    time.sleep(30)
    
    # Get results and verify
    status = requests.get(f"http://localhost:5000/api/analyze/status/{job_id}").json()
    
    if status.get('status') == 'completed':
        print(f"✅ Analysis completed: {status.get('processed')} posters")
        print(f"   - Success: {status.get('success')}")
        print(f"   - Errors: {status.get('errors')}")
    else:
        print(f"❌ Analysis status: {status.get('status')}")


if __name__ == '__main__':
    # Initialize tester
    tester = DataAccuracyTester()
    
    # Run all tests
    tester.run_all_tests()
    
    # Optional: Test live analysis
    try:
        test_live_analysis_accuracy()
    except Exception as e:
        print(f"\n⚠️  Live test skipped: {e}")
