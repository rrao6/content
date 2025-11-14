"""Comprehensive test script for the entire Red Zone Analysis system."""
import os
import sys
import json
import time
import requests
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))


class SystemTester:
    """Test all components of the Red Zone Analysis system."""
    
    def __init__(self):
        self.results = []
        self.passed = 0
        self.failed = 0
        self.dashboard_url = "http://localhost:5000"
    
    def test(self, name, condition, details=""):
        """Log a test result."""
        status = "✅ PASS" if condition else "❌ FAIL"
        print(f"{status}: {name}")
        if details:
            print(f"   {details}")
        
        self.results.append({
            "name": name,
            "passed": condition,
            "details": details
        })
        
        if condition:
            self.passed += 1
        else:
            self.failed += 1
    
    def test_environment(self):
        """Test environment setup."""
        print("\n🔍 Testing Environment Setup...")
        
        # Check Python version
        import sys
        py_version = sys.version_info
        self.test(
            "Python Version",
            py_version.major == 3 and py_version.minor >= 8,
            f"Python {py_version.major}.{py_version.minor}.{py_version.micro}"
        )
        
        # Check .env files
        self.test("Parent .env exists", Path("../.env").exists())
        self.test("Dashboard .env exists", Path(".env").exists())
        
        # Check required environment variables
        required_vars = [
            "DATABRICKS_HOST",
            "DATABRICKS_TOKEN", 
            "DATABRICKS_HTTP_PATH",
            "OPENAI_API_KEY"
        ]
        
        for var in required_vars:
            self.test(f"Environment: {var}", os.environ.get(var) is not None)
    
    def test_imports(self):
        """Test that all modules can be imported."""
        print("\n📦 Testing Module Imports...")
        
        modules = [
            ("Flask", "flask"),
            ("Databricks SQL", "databricks.sql"),
            ("OpenAI", "openai"),
            ("Requests", "requests"),
            ("Pydantic", "pydantic"),
            ("Structlog", "structlog"),
        ]
        
        for name, module in modules:
            try:
                __import__(module)
                self.test(f"Import {name}", True)
            except ImportError as e:
                self.test(f"Import {name}", False, str(e))
    
    def test_database_connection(self):
        """Test Databricks connection."""
        print("\n🗄️ Testing Database Connection...")
        
        try:
            from connection import get_cursor
            from config import get_config
            
            config = get_config()
            
            with get_cursor() as cursor:
                # Test basic connectivity
                cursor.execute("SELECT 1 as test")
                result = cursor.fetchone()
                self.test("Databricks Connection", result[0] == 1)
                
                # Test content_info table access
                cursor.execute(f"""
                    SELECT COUNT(*) 
                    FROM {config.catalog}.{config.schema_}.content_info
                    WHERE poster_img_url IS NOT NULL
                """)
                count = cursor.fetchone()[0]
                self.test(
                    "Content Table Access",
                    count > 0,
                    f"Found {count:,} records with poster URLs"
                )
                
        except Exception as e:
            self.test("Databricks Connection", False, str(e))
    
    def test_openai_api(self):
        """Test OpenAI API connectivity."""
        print("\n🤖 Testing OpenAI API...")
        
        try:
            import openai
            from config import get_config
            
            config = get_config()
            client = openai.OpenAI(api_key=config.openai_api_key)
            
            # Test with a simple completion
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": "Say 'API working'"}],
                max_tokens=10
            )
            
            self.test(
                "OpenAI API",
                "working" in response.choices[0].message.content.lower(),
                "API responded successfully"
            )
            
        except Exception as e:
            self.test("OpenAI API", False, str(e))
    
    def test_dashboard_running(self):
        """Test if dashboard is running."""
        print("\n🌐 Testing Dashboard...")
        
        try:
            response = requests.get(self.dashboard_url, timeout=5)
            self.test(
                "Dashboard Running",
                response.status_code == 200,
                f"Status code: {response.status_code}"
            )
            
            # Test key endpoints
            endpoints = [
                "/api/runs",
                "/api/stats/trending",
            ]
            
            for endpoint in endpoints:
                try:
                    response = requests.get(f"{self.dashboard_url}{endpoint}", timeout=5)
                    self.test(
                        f"Endpoint {endpoint}",
                        response.status_code == 200,
                        f"Status: {response.status_code}"
                    )
                except Exception as e:
                    self.test(f"Endpoint {endpoint}", False, str(e))
                    
        except requests.exceptions.ConnectionError:
            self.test("Dashboard Running", False, "Connection refused - is dashboard running?")
        except Exception as e:
            self.test("Dashboard Running", False, str(e))
    
    def test_image_proxy(self):
        """Test image proxy functionality."""
        print("\n🖼️ Testing Image Proxy...")
        
        if not hasattr(self, 'dashboard_url'):
            print("   Skipping - dashboard not available")
            return
            
        try:
            # Test with a known CDN pattern
            test_url = "http://img.adrise.tv/movie/123456/poster_v2.jpg"
            proxy_url = f"{self.dashboard_url}/proxy/image?url={test_url}"
            
            response = requests.get(proxy_url, timeout=10)
            self.test(
                "Image Proxy Endpoint",
                response.status_code in [200, 404],  # 404 is ok for non-existent image
                f"Status: {response.status_code}, Content-Type: {response.headers.get('content-type', 'none')}"
            )
            
        except Exception as e:
            self.test("Image Proxy", False, str(e))
    
    def test_analysis_pipeline(self):
        """Test the analysis pipeline components."""
        print("\n🔬 Testing Analysis Pipeline...")
        
        try:
            from analyzer import is_analysis_available
            
            available = is_analysis_available()
            self.test(
                "Analysis Pipeline Available",
                available,
                "Pipeline initialized successfully" if available else "Pipeline not available"
            )
            
            if available:
                # Test that we can get SOT types
                from analyzer import get_sot_types
                sot_types = get_sot_types()
                self.test(
                    "SOT Types Available",
                    len(sot_types) > 0,
                    f"Found {len(sot_types)} SOT types: {', '.join(sot_types[:3])}..."
                )
                
        except Exception as e:
            self.test("Analysis Pipeline", False, str(e))
    
    def test_full_integration(self):
        """Test a full integration flow."""
        print("\n🎯 Testing Full Integration...")
        
        try:
            # This would run a small analysis if everything is connected
            from production_integration import ProductionDashboardIntegration
            
            integration = ProductionDashboardIntegration()
            
            # Test DB connection through integration
            db_ok = integration.test_databricks_connection()
            self.test("Integration: Database", db_ok)
            
            # Test fetching some poster URLs
            if db_ok:
                posters = integration.fetch_real_poster_urls(limit=3)
                self.test(
                    "Integration: Fetch Posters",
                    len(posters) > 0,
                    f"Fetched {len(posters)} poster URLs"
                )
            
        except Exception as e:
            self.test("Full Integration", False, str(e))
    
    def generate_report(self):
        """Generate a test report."""
        print("\n" + "="*60)
        print("📊 TEST SUMMARY")
        print("="*60)
        print(f"Total Tests: {self.passed + self.failed}")
        print(f"✅ Passed: {self.passed}")
        print(f"❌ Failed: {self.failed}")
        
        if self.failed == 0:
            print("\n🎉 ALL TESTS PASSED! System is ready for production.")
        else:
            print(f"\n⚠️  {self.failed} tests failed. Please fix issues before deployment.")
        
        # Save detailed report
        report = {
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total": self.passed + self.failed,
                "passed": self.passed,
                "failed": self.failed
            },
            "tests": self.results
        }
        
        report_path = Path("test_report.json")
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2)
        
        print(f"\n📄 Detailed report saved to: {report_path}")


def main():
    """Run all system tests."""
    print("🧪 Red Zone Analysis System - Comprehensive Test Suite")
    print("="*60)
    
    tester = SystemTester()
    
    # Run all test suites
    tester.test_environment()
    tester.test_imports()
    tester.test_database_connection()
    tester.test_openai_api()
    tester.test_dashboard_running()
    tester.test_image_proxy()
    tester.test_analysis_pipeline()
    tester.test_full_integration()
    
    # Generate report
    tester.generate_report()


if __name__ == "__main__":
    # Load environment from parent directory
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
    
    # Also load local .env
    local_env = Path(__file__).parent / '.env'
    if local_env.exists():
        load_dotenv(local_env, override=True)
    
    main()
