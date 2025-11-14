"""Production integration for Red Zone Dashboard with REAL data."""
import os
import sys
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from repository import ContentRepository
from sot_repository import SOTRepository
from sot_pipeline import SOTAnalysisPipeline
from service import ContentService, EligibleTitlesService
from database import AnalysisRun, PosterResult, import_json_results
from connection import get_cursor
from config import get_config
from analysis import SafeZoneAnalyzer


class ProductionDashboardIntegration:
    """Real production integration - no fake data."""
    
    def __init__(self):
        """Initialize with real connections."""
        self.config = get_config()
        self.content_repo = ContentRepository()
        self.sot_repo = SOTRepository()
        self.content_service = ContentService()
        self.eligible_service = EligibleTitlesService()
        
        # Initialize analyzer
        analyzer = SafeZoneAnalyzer(
            provider="openai",
            model=self.config.openai_model,
            api_key=self.config.openai_api_key
        )
        
        # Initialize pipeline with required services
        self.pipeline = SOTAnalysisPipeline(
            eligible_service=self.eligible_service,
            content_service=self.content_service,
            analyzer=analyzer
        )
    
    def test_databricks_connection(self):
        """Test real Databricks connection."""
        print("🔌 Testing Databricks connection...")
        try:
            with get_cursor() as cursor:
                # Test query to content_info table
                cursor.execute(f"""
                    SELECT COUNT(*) as total_content 
                    FROM {self.config.catalog}.{self.config.schema_}.content_info
                """)
                result = cursor.fetchone()
                print(f"✅ Connected! Total content in database: {result[0]:,}")
                return True
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            return False
    
    def fetch_real_poster_urls(self, limit=10):
        """Fetch real poster URLs from content_info table."""
        print(f"\n📸 Fetching real poster URLs from content_info...")
        try:
            with get_cursor() as cursor:
                cursor.execute(f"""
                    SELECT 
                        content_id,
                        program_id,
                        content_name,
                        content_type,
                        poster_img_url
                    FROM {self.config.catalog}.{self.config.schema_}.content_info
                    WHERE poster_img_url IS NOT NULL
                        AND poster_img_url != ''
                        AND content_name IS NOT NULL
                    ORDER BY created_dt DESC
                    LIMIT {limit}
                """)
                
                results = cursor.fetchall()
                print(f"✅ Found {len(results)} posters with URLs")
                
                for row in results[:5]:  # Show first 5
                    print(f"   - {row[2]}: {row[4]}")
                
                return results
        except Exception as e:
            print(f"❌ Failed to fetch poster URLs: {e}")
            return []
    
    def run_real_analysis(self, sot_types: List[str], days_back: int = 7, limit: int = 50):
        """Run analysis on REAL eligible titles with REAL poster URLs."""
        print(f"\n🎬 Running REAL analysis on eligible titles...")
        print(f"   SOT Types: {sot_types}")
        print(f"   Days Back: {days_back}")
        print(f"   Limit: {limit}")
        
        try:
            # Get eligible titles from SOT
            eligible_titles = self.eligible_service.fetch_eligible_titles(
                sot_types=sot_types,
                days_back=days_back,
                limit=limit
            )
            
            print(f"\n✅ Found {len(eligible_titles)} eligible titles")
            
            if not eligible_titles:
                print("❌ No eligible titles found")
                return []
            
            # Show sample of what we're analyzing
            print("\n📋 Sample titles to analyze:")
            for title in eligible_titles[:5]:
                print(f"   - {title.title} (ID: {title.content_id}, SOT: {title.sot_name})")
            
            # Run the actual pipeline analysis
            results = self.pipeline.run(
                sot_types=sot_types,
                days_back=days_back,
                limit=limit
            )
            
            print(f"\n✅ Analysis complete! Processed {len(results)} posters")
            
            # Show sample results
            if results:
                passed = sum(1 for r in results if not r.analysis.get("red_safe_zone", {}).get("contains_key_elements", True))
                failed = len(results) - passed
                print(f"   Pass: {passed}, Fail: {failed}")
                
                print("\n📊 Sample analysis results:")
                for result in results[:3]:
                    red_zone = result.analysis.get("red_safe_zone", {})
                    status = "FAIL" if red_zone.get("contains_key_elements") else "PASS"
                    print(f"   - {result.eligible_title.title}: {status} ({red_zone.get('confidence')}%)")
                    print(f"     Poster: {result.poster_image.url if result.poster_image else 'N/A'}")
                    print(f"     Justification: {red_zone.get('justification', 'N/A')}")
            
            return results
            
        except Exception as e:
            print(f"❌ Analysis failed: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def save_results_to_dashboard(self, results: List[Any], description: str = ""):
        """Save real analysis results to dashboard database."""
        if not results:
            print("❌ No results to save")
            return None
        
        print(f"\n💾 Saving {len(results)} results to dashboard...")
        
        # Calculate stats
        total = len(results)
        passed = sum(1 for r in results if not r.analysis.get("red_safe_zone", {}).get("contains_key_elements", True))
        failed = total - passed
        
        # Create analysis run
        parameters = {
            "source": "production_pipeline",
            "timestamp": datetime.now().isoformat()
        }
        
        run_id = AnalysisRun.create(total, passed, failed, parameters, description)
        
        # Convert results for database
        db_results = []
        for result in results:
            eligible = result.eligible_title
            analysis = result.analysis
            
            db_results.append({
                "content_id": eligible.content_id,
                "program_id": eligible.program_id,
                "title": eligible.title,
                "content_type": eligible.content_type,
                "sot_name": eligible.sot_name,
                "poster_url": result.poster_image.url if result.poster_image else eligible.poster_img_url,
                "analysis": analysis
            })
        
        # Save to database
        PosterResult.create_batch(run_id, db_results)
        
        print(f"✅ Saved to dashboard! Run ID: {run_id}")
        print(f"   View at: http://localhost:5000/results/{run_id}")
        
        return run_id


def main():
    """Run production integration."""
    print("🚀 Red Zone Dashboard - PRODUCTION Integration\n")
    
    # Initialize
    integration = ProductionDashboardIntegration()
    
    # Test connection
    if not integration.test_databricks_connection():
        print("\n❌ Cannot proceed without database connection")
        print("   Please check your .env file has correct Databricks credentials")
        return
    
    # Show real poster URLs
    integration.fetch_real_poster_urls(limit=5)
    
    # Run real analysis
    print("\n" + "="*60)
    print("Running REAL analysis on production data...")
    print("="*60)
    
    results = integration.run_real_analysis(
        sot_types=["just_added", "most_popular"],
        days_back=7,
        limit=25  # Start small for testing
    )
    
    # Save to dashboard
    if results:
        run_id = integration.save_results_to_dashboard(
            results, 
            f"Production Analysis - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        )
        
        print("\n✨ Production integration complete!")
        print(f"\n🎯 Next steps:")
        print(f"1. Make sure dashboard is running: python dashboard.py")
        print(f"2. View results at: http://localhost:5000/results/{run_id}")
        print(f"3. All data is REAL from your content database!")


if __name__ == "__main__":
    # Load environment variables from .env file
    from dotenv import load_dotenv
    env_path = Path(__file__).parent / '.env'
    if not env_path.exists():
        env_path = Path(__file__).parent.parent / '.env'
    load_dotenv(env_path)
    
    # Check for required environment variables
    required_vars = [
        "DATABRICKS_HOST",
        "DATABRICKS_HTTP_PATH", 
        "DATABRICKS_TOKEN",
        "OPENAI_API_KEY"
    ]
    
    missing = [var for var in required_vars if not os.environ.get(var)]
    if missing:
        print(f"❌ Missing required environment variables: {missing}")
        print(f"   Checked .env at: {env_path}")
        print("   Please set these in your .env file")
        sys.exit(1)
    
    # Run
    main()
