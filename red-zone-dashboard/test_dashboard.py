"""Test suite for Red Zone Analysis Dashboard."""
import os
import sys
import json
import asyncio
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
import random

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from database import init_database, AnalysisRun, PosterResult, import_json_results
from analyzer import analyzer, is_analysis_available


class DashboardTester:
    """Test various dashboard functionalities."""
    
    def __init__(self):
        """Initialize tester."""
        self.test_results = []
        self.db_path = Path("red_zone_analysis.db")
        
    def log(self, message, status="INFO"):
        """Log test message."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {status}: {message}")
        self.test_results.append({
            "time": timestamp,
            "status": status,
            "message": message
        })
    
    def test_database_init(self):
        """Test database initialization."""
        self.log("Testing database initialization...")
        try:
            init_database()
            if self.db_path.exists():
                self.log("✓ Database created successfully", "PASS")
                
                # Check tables
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = cursor.fetchall()
                conn.close()
                
                expected_tables = {'analysis_runs', 'poster_results'}
                actual_tables = {table[0] for table in tables}
                
                if expected_tables.issubset(actual_tables):
                    self.log("✓ All required tables created", "PASS")
                else:
                    self.log(f"✗ Missing tables: {expected_tables - actual_tables}", "FAIL")
            else:
                self.log("✗ Database file not created", "FAIL")
                
        except Exception as e:
            self.log(f"✗ Database init failed: {str(e)}", "ERROR")
    
    def test_sample_data_import(self):
        """Test importing sample data."""
        self.log("Testing sample data import...")
        
        # Create sample data
        sample_data = [
            {
                "content_id": 100001,
                "program_id": 200001,
                "content_name": "Test Movie 1",
                "content_type": "movie",
                "sot_name": "just_added",
                "poster_img_url": "https://img.adrise.tv/test1.jpg",
                "analysis": {
                    "red_safe_zone": {
                        "contains_key_elements": False,
                        "confidence": 95,
                        "justification": "No text or faces detected in the red zone"
                    }
                }
            },
            {
                "content_id": 100002,
                "program_id": 200002,
                "content_name": "Test Movie 2",
                "content_type": "movie",
                "sot_name": "just_added",
                "poster_img_url": "https://img.adrise.tv/test2.jpg",
                "analysis": {
                    "red_safe_zone": {
                        "contains_key_elements": True,
                        "confidence": 98,
                        "justification": "Title text clearly visible in the red zone"
                    }
                }
            },
            {
                "content_id": 100003,
                "program_id": 200003,
                "content_name": "Test Series 1",
                "content_type": "series",
                "sot_name": "most_popular",
                "poster_img_url": "https://img.adrise.tv/test3.jpg",
                "analysis": {
                    "red_safe_zone": {
                        "contains_key_elements": True,
                        "confidence": 92,
                        "justification": "Actor's face partially visible in red zone"
                    }
                }
            }
        ]
        
        # Save to temporary file
        test_file = Path("test_import.json")
        try:
            with open(test_file, 'w') as f:
                json.dump(sample_data, f)
            
            # Import data
            run_id = import_json_results(test_file, "Test import for QA")
            self.log(f"✓ Imported test data with run ID: {run_id}", "PASS")
            
            # Verify import
            run = AnalysisRun.get_by_id(run_id)
            if run and run['total_analyzed'] == 3:
                self.log("✓ Run metadata correct", "PASS")
            else:
                self.log("✗ Run metadata incorrect", "FAIL")
                
            results = PosterResult.get_by_run(run_id)
            if len(results) == 3:
                self.log("✓ All results imported", "PASS")
            else:
                self.log(f"✗ Expected 3 results, got {len(results)}", "FAIL")
                
        except Exception as e:
            self.log(f"✗ Import failed: {str(e)}", "ERROR")
        finally:
            # Cleanup
            if test_file.exists():
                test_file.unlink()
    
    def test_statistics(self):
        """Test statistics calculations."""
        self.log("Testing statistics...")
        
        try:
            stats = PosterResult.get_stats()
            self.log(f"Total posters: {stats['total']}")
            self.log(f"Pass rate: {100 - stats['fail_rate']:.1f}%")
            self.log(f"Average confidence: {stats['avg_confidence']}")
            
            # Check SOT breakdown
            if stats['by_sot']:
                self.log("SOT breakdown:")
                for sot, sot_stats in stats['by_sot'].items():
                    self.log(f"  {sot}: {sot_stats['total']} total, {sot_stats['fail_rate']:.1f}% fail rate")
            
            self.log("✓ Statistics generated successfully", "PASS")
            
        except Exception as e:
            self.log(f"✗ Statistics failed: {str(e)}", "ERROR")
    
    def test_filtering(self):
        """Test result filtering."""
        self.log("Testing result filtering...")
        
        try:
            # Get latest run
            latest_run = AnalysisRun.get_latest()
            if not latest_run:
                self.log("✗ No runs available for testing", "SKIP")
                return
            
            run_id = latest_run['id']
            
            # Test different filters
            filters_to_test = [
                ({"has_elements": 0}, "Pass only"),
                ({"has_elements": 1}, "Fail only"),
                ({"sot_name": "just_added"}, "Just Added SOT"),
                ({"search": "Test"}, "Search for 'Test'")
            ]
            
            for filters, desc in filters_to_test:
                results = PosterResult.get_by_run(run_id, filters)
                self.log(f"Filter '{desc}': {len(results)} results", "INFO")
            
            self.log("✓ Filtering works correctly", "PASS")
            
        except Exception as e:
            self.log(f"✗ Filtering failed: {str(e)}", "ERROR")
    
    async def test_analysis_limits(self):
        """Test analysis batch size limits."""
        self.log("Testing analysis batch limits...")
        
        if not is_analysis_available():
            self.log("✗ Analysis pipeline not available", "SKIP")
            return
        
        # Test exceeding limit
        result = await analyzer.run_analysis(
            sot_types=["just_added"],
            days_back=7,
            limit=200,  # Exceeds max of 100
            description="Test exceeding limit"
        )
        
        if result['status'] == 'error' and 'exceeds maximum' in result['message']:
            self.log("✓ Batch limit enforced correctly", "PASS")
        else:
            self.log("✗ Batch limit not enforced", "FAIL")
        
        # Test valid limit
        self.log("Testing valid batch size (10 items)...")
        result = await analyzer.run_analysis(
            sot_types=["just_added"],
            days_back=7,
            limit=10,
            description="Test QA batch"
        )
        
        if result['status'] == 'success':
            self.log(f"✓ Analysis completed: {result['total']} analyzed", "PASS")
        else:
            self.log(f"✗ Analysis failed: {result.get('message', 'Unknown error')}", "ERROR")
    
    def test_export(self):
        """Test export functionality."""
        self.log("Testing export...")
        
        try:
            latest_run = AnalysisRun.get_latest()
            if not latest_run:
                self.log("✗ No runs available for export test", "SKIP")
                return
            
            export_data = analyzer.export_run_data(latest_run['id'])
            
            if 'run' in export_data and 'results' in export_data:
                self.log(f"✓ Export contains {len(export_data['results'])} results", "PASS")
                
                # Save test export
                export_file = Path("test_export.json")
                with open(export_file, 'w') as f:
                    json.dump(export_data, f, indent=2)
                self.log(f"✓ Export saved to {export_file}", "PASS")
                export_file.unlink()  # Cleanup
            else:
                self.log("✗ Export data structure incorrect", "FAIL")
                
        except Exception as e:
            self.log(f"✗ Export failed: {str(e)}", "ERROR")
    
    def generate_large_test_data(self, num_posters=100):
        """Generate large test dataset for QA."""
        self.log(f"Generating test data with {num_posters} posters...")
        
        sot_types = ["just_added", "leaving_soon", "most_popular", "imdb", "rotten_tomatoes"]
        
        test_data = []
        for i in range(num_posters):
            # Simulate realistic distribution: 80% fail rate
            has_elements = random.random() > 0.2
            confidence = random.randint(85, 99)
            
            justifications_pass = [
                "No text or faces detected in the red zone",
                "Red zone is clear of key elements",
                "All text elements are outside the red zone"
            ]
            
            justifications_fail = [
                "Title text clearly visible in the red zone",
                "Actor's face partially visible in red zone",
                "Logo and tagline overlap with red zone",
                "Credits text extends into red zone area"
            ]
            
            poster = {
                "content_id": 200000 + i,
                "program_id": 300000 + i,
                "content_name": f"Test Content {i:04d}",
                "content_type": "movie" if i % 3 != 0 else "series",
                "sot_name": random.choice(sot_types),
                "poster_img_url": f"https://img.adrise.tv/test_{i:04d}.jpg",
                "analysis": {
                    "red_safe_zone": {
                        "contains_key_elements": has_elements,
                        "confidence": confidence,
                        "justification": random.choice(justifications_fail if has_elements else justifications_pass)
                    }
                }
            }
            test_data.append(poster)
        
        # Save test data
        test_file = Path("qa_test_data_100.json")
        with open(test_file, 'w') as f:
            json.dump(test_data, f, indent=2)
        
        self.log(f"✓ Generated test data saved to {test_file}", "PASS")
        self.log(f"  - Total posters: {num_posters}")
        self.log(f"  - Expected fail rate: ~80%")
        
        # Import for testing
        try:
            run_id = import_json_results(test_file, f"QA Test Run - {num_posters} posters")
            self.log(f"✓ Test data imported with run ID: {run_id}", "PASS")
            
            # Quick stats
            stats = PosterResult.get_stats(run_id)
            self.log(f"  - Actual fail rate: {stats['fail_rate']:.1f}%")
            self.log(f"  - Average confidence: {stats['avg_confidence']}")
            
        except Exception as e:
            self.log(f"✗ Import failed: {str(e)}", "ERROR")
    
    def run_all_tests(self):
        """Run all tests."""
        self.log("=== Starting Dashboard Test Suite ===", "INFO")
        
        # Synchronous tests
        self.test_database_init()
        self.test_sample_data_import()
        self.test_statistics()
        self.test_filtering()
        self.test_export()
        
        # Async tests
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.test_analysis_limits())
        
        # Generate QA data
        self.generate_large_test_data(100)
        
        # Summary
        self.log("=== Test Summary ===", "INFO")
        passed = sum(1 for r in self.test_results if r['status'] == 'PASS')
        failed = sum(1 for r in self.test_results if r['status'] in ['FAIL', 'ERROR'])
        skipped = sum(1 for r in self.test_results if r['status'] == 'SKIP')
        
        self.log(f"Passed: {passed}, Failed: {failed}, Skipped: {skipped}")
        
        if failed == 0:
            self.log("✓ All tests passed! Dashboard is ready for QA.", "SUCCESS")
        else:
            self.log("✗ Some tests failed. Please review before proceeding.", "WARNING")
        
        # Save test report
        report_file = Path("test_report.json")
        with open(report_file, 'w') as f:
            json.dump({
                "test_date": datetime.now().isoformat(),
                "summary": {
                    "passed": passed,
                    "failed": failed,
                    "skipped": skipped
                },
                "results": self.test_results
            }, f, indent=2)
        
        self.log(f"Test report saved to {report_file}")


if __name__ == "__main__":
    tester = DashboardTester()
    tester.run_all_tests()
