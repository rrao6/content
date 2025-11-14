"""Verify all backend systems are working properly."""
import os
import sys
import json
import asyncio
from pathlib import Path
from datetime import datetime, timedelta
import base64
import requests
from typing import Optional

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from connection import get_cursor
from config import get_config
from repository import ContentRepository
from sot_repository import SOTRepository
from analysis import SafeZoneAnalyzer, PosterAnalysisPipeline, _download_image_to_base64
from service import ContentService, EligibleTitlesService
import openai


class BackendVerifier:
    """Verify all backend systems are operational."""
    
    def __init__(self):
        self.config = get_config()
        self.test_results = []
        self.all_passed = True
    
    def log_test(self, name: str, passed: bool, details: str = ""):
        """Log test result."""
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {name}")
        if details:
            print(f"   {details}")
        self.test_results.append({
            "name": name,
            "passed": passed,
            "details": details
        })
        if not passed:
            self.all_passed = False
    
    def test_environment(self):
        """Test environment variables."""
        print("\n🔍 Testing Environment Variables...")
        
        required = {
            "DATABRICKS_HOST": self.config.host,
            "DATABRICKS_TOKEN": "***" if self.config.token else None,
            "DATABRICKS_HTTP_PATH": self.config.http_path,
            "OPENAI_API_KEY": "***" if self.config.openai_api_key else None,
        }
        
        for var, value in required.items():
            if value:
                self.log_test(f"Environment: {var}", True, f"Set ({value[:20]}...)" if value != "***" else "Set")
            else:
                self.log_test(f"Environment: {var}", False, "Not set")
    
    def test_databricks_connection(self):
        """Test Databricks connection and queries."""
        print("\n🔌 Testing Databricks Connection...")
        
        try:
            with get_cursor() as cursor:
                # Test basic connection
                cursor.execute("SELECT 1 as test")
                result = cursor.fetchone()
                self.log_test("Databricks Connection", True, f"Connected successfully")
                
                # Test content_info table
                cursor.execute(f"""
                    SELECT COUNT(*) as count 
                    FROM {self.config.catalog}.{self.config.schema_}.content_info
                    WHERE poster_img_url IS NOT NULL
                """)
                count = cursor.fetchone()[0]
                self.log_test("Content Table Access", True, f"Found {count:,} posters with URLs")
                
                # Test actual poster URL
                cursor.execute(f"""
                    SELECT content_id, content_name, poster_img_url
                    FROM {self.config.catalog}.{self.config.schema_}.content_info
                    WHERE poster_img_url IS NOT NULL
                        AND poster_img_url != ''
                    LIMIT 1
                """)
                row = cursor.fetchone()
                if row:
                    self.log_test("Sample Poster URL", True, 
                                f"ID: {row[0]}, Title: {row[1]}\n   URL: {row[2]}")
                    return row  # Return for further testing
                else:
                    self.log_test("Sample Poster URL", False, "No poster URLs found")
                    return None
                    
        except Exception as e:
            self.log_test("Databricks Connection", False, str(e))
            return None
    
    def test_openai_connection(self):
        """Test OpenAI API connection."""
        print("\n🤖 Testing OpenAI Connection...")
        
        api_key = self.config.openai_api_key
        if not api_key:
            self.log_test("OpenAI API Key", False, "Not set in environment")
            return False
        
        try:
            client = openai.OpenAI(api_key=api_key)
            
            # Simple test
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a test assistant."},
                    {"role": "user", "content": "Reply with exactly: CONNECTION_OK"}
                ],
                max_tokens=10
            )
            
            result = response.choices[0].message.content.strip()
            if "CONNECTION_OK" in result:
                self.log_test("OpenAI Connection", True, f"Model: gpt-4o-mini working")
            else:
                self.log_test("OpenAI Connection", False, f"Unexpected response: {result}")
            
            # Test vision model
            try:
                # Create a simple test image
                test_image = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
                
                response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": "What color is this image?"},
                                {"type": "image_url", "image_url": {"url": test_image}}
                            ]
                        }
                    ],
                    max_tokens=50
                )
                self.log_test("OpenAI Vision Model", True, "gpt-4o vision capabilities working")
                return True
            except Exception as e:
                self.log_test("OpenAI Vision Model", False, str(e))
                return False
                
        except Exception as e:
            self.log_test("OpenAI Connection", False, str(e))
            return False
    
    async def test_poster_analysis(self, sample_poster=None):
        """Test the complete poster analysis pipeline."""
        print("\n🎬 Testing Poster Analysis Pipeline...")
        
        if not sample_poster:
            self.log_test("Poster Analysis", False, "No sample poster available")
            return
        
        content_id, title, poster_url = sample_poster
        
        try:
            # Test image download
            image_data = None
            try:
                image_data = _download_image_to_base64(poster_url)
            except Exception as e:
                self.log_test("Image Download", False, f"Failed: {e}")
                return
            
            if image_data:
                self.log_test("Image Download", True, f"Downloaded image successfully")
                
                # Test red zone analysis
                analyzer = SafeZoneAnalyzer()
                
                # image_data is already a base64 data URI
                image_input = image_data
                
                result = analyzer.analyze(image_input)
                
                if result:
                    red_zone = result.red_safe_zone
                    self.log_test("Red Zone Analysis", True, 
                                f"Result: {'FAIL' if red_zone.contains_key_elements else 'PASS'} "
                                f"({red_zone.confidence}%)\n   {red_zone.justification}")
                else:
                    self.log_test("Red Zone Analysis", False, "No result returned")
            else:
                self.log_test("Image Download", False, f"Could not download from {poster_url}")
                
        except Exception as e:
            self.log_test("Poster Analysis Pipeline", False, str(e))
            import traceback
            traceback.print_exc()
    
    def test_sot_integration(self):
        """Test SOT repository integration."""
        print("\n📊 Testing SOT Integration...")
        
        try:
            sot_repo = SOTRepository()
            
            # Test eligible titles query
            titles = sot_repo.get_eligible_titles(
                sot_types=["just_added"],
                start_date=(datetime.now().date() - timedelta(days=30)).isoformat(),
                end_date=datetime.now().date().isoformat(),
                limit=5
            )
            
            if titles:
                self.log_test("SOT Query", True, f"Found {len(titles)} eligible titles")
                for title in titles[:2]:
                    print(f"   - {title.title} (ID: {title.content_id}, SOT: {title.sot_name})")
            else:
                self.log_test("SOT Query", False, "No eligible titles found")
                
        except Exception as e:
            self.log_test("SOT Integration", False, str(e))
    
    def test_cache_and_monitoring(self):
        """Test caching and monitoring systems."""
        print("\n💾 Testing Cache and Monitoring...")
        
        try:
            from analysis_cache import AnalysisCache
            from monitoring import AnalysisMonitor
            
            # Test cache
            cache = AnalysisCache()
            test_key = "test_poster_123"
            test_result = {
                "red_safe_zone": {
                    "contains_key_elements": False,
                    "confidence": 95,
                    "justification": "Test result"
                }
            }
            
            cache.set(test_key, test_result)
            cached = cache.get(test_key)
            
            if cached == test_result:
                self.log_test("Cache System", True, "Cache working correctly")
            else:
                self.log_test("Cache System", False, "Cache not returning correct data")
            
            # Test monitoring
            monitor = AnalysisMonitor()
            monitor.record_analysis(
                content_id="test_123",
                duration=1.5,
                success=True,
                cache_hit=False
            )
            
            stats = monitor.get_stats()
            if stats["total_analyses"] > 0:
                self.log_test("Monitoring System", True, f"Recorded {stats['total_analyses']} analyses")
            else:
                self.log_test("Monitoring System", False, "No analyses recorded")
                
        except Exception as e:
            self.log_test("Cache/Monitoring", False, str(e))
    
    async def run_all_tests(self):
        """Run all backend verification tests."""
        print("🚀 Backend System Verification")
        print("="*50)
        
        # 1. Environment
        self.test_environment()
        
        # 2. Databricks
        sample_poster = self.test_databricks_connection()
        
        # 3. OpenAI
        openai_ok = self.test_openai_connection()
        
        # 4. Full pipeline test
        if sample_poster and openai_ok:
            await self.test_poster_analysis(sample_poster)
        
        # 5. SOT Integration
        self.test_sot_integration()
        
        # 6. Supporting systems
        self.test_cache_and_monitoring()
        
        # Summary
        print("\n" + "="*50)
        print("📋 Test Summary")
        print("="*50)
        
        passed = sum(1 for r in self.test_results if r["passed"])
        failed = sum(1 for r in self.test_results if not r["passed"])
        
        print(f"\nTotal Tests: {len(self.test_results)}")
        print(f"✅ Passed: {passed}")
        print(f"❌ Failed: {failed}")
        
        if self.all_passed:
            print("\n🎉 All backend systems are operational!")
            print("\n✨ You can now:")
            print("1. Run the dashboard: python dashboard.py")
            print("2. Use production integration: python production_integration.py")
            print("3. All poster analysis will use REAL data from your content database")
        else:
            print("\n⚠️  Some systems need attention:")
            for result in self.test_results:
                if not result["passed"]:
                    print(f"   - {result['name']}: {result['details']}")
            
            print("\n📝 To fix:")
            print("1. Ensure all environment variables are set in .env")
            print("2. Check your Databricks and OpenAI credentials")
            print("3. Verify network connectivity")


async def main():
    """Run backend verification."""
    verifier = BackendVerifier()
    await verifier.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())
