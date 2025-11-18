#!/usr/bin/env python3
"""
Script to analyze top 200 shiny SOT eligible titles and publish to dashboard.

This script:
1. Queries the top 200 shiny titles that are SOT eligible
2. Runs safe zone analysis on their posters
3. Saves results to the dashboard database
"""
import sys
import json
from pathlib import Path
from datetime import datetime

# Add dashboard directory to path
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "red-zone-dashboard"))

from config import get_config
from service import EligibleTitlesService, ContentService
from analysis import SafeZoneAnalyzer
from sot_pipeline import SOTAnalysisPipeline
from database import init_database, AnalysisRun, PosterResult


def main():
    """Run analysis on top 200 shiny SOT eligible titles."""
    
    print("=" * 80)
    print("🌟 SHINY SOT POSTER ANALYSIS")
    print("=" * 80)
    print()
    print("This script will:")
    print("  1. Query top 200 shiny titles that are SOT eligible")
    print("  2. Run safe zone analysis on their posters")
    print("  3. Save results to the dashboard database")
    print()
    print("=" * 80)
    print()
    
    # Initialize configuration
    config = get_config()
    
    if not config.openai_api_key:
        print("❌ ERROR: OpenAI API key not configured")
        print("Please set OPENAI_API_KEY in your .env file")
        sys.exit(1)
    
    # Initialize services
    print("🔧 Initializing services...")
    eligible_service = EligibleTitlesService()
    content_service = ContentService()
    
    # Create analyzer
    analyzer = SafeZoneAnalyzer(
        provider="openai",
        model=config.openai_model,
        api_key=config.openai_api_key,
    )
    
    # Create modified SOT pipeline that uses shiny filtering
    class ShinySOTAnalysisPipeline(SOTAnalysisPipeline):
        """Modified pipeline that uses shiny eligible titles iterator."""
        
        def run(self, *args, **kwargs):
            """Override run to use shiny filtering."""
            # Store original method
            original_iter = self.eligible_service.iter_eligible_poster_images
            
            # Replace with shiny version
            self.eligible_service.iter_eligible_poster_images = (
                self.eligible_service.iter_shiny_eligible_poster_images
            )
            
            try:
                # Run the parent implementation
                return super().run(*args, **kwargs)
            finally:
                # Restore original method
                self.eligible_service.iter_eligible_poster_images = original_iter
    
    # Create pipeline with shiny support
    pipeline = ShinySOTAnalysisPipeline(
        eligible_service=eligible_service,
        content_service=content_service,
        analyzer=analyzer,
    )
    
    # Configure parameters
    days_back = 7
    limit = 200
    sot_types = None  # All SOT types
    
    print(f"📊 Parameters:")
    print(f"   - Days back: {days_back}")
    print(f"   - Limit: {limit} posters")
    print(f"   - SOT types: ALL (with shiny filter)")
    print(f"   - Save composite images: Yes")
    print()
    
    # Run the analysis
    print("🚀 Starting analysis pipeline...")
    print()
    
    try:
        results = pipeline.run(
            days_back=days_back,
            sot_types=sot_types,
            batch_size=50,
            limit=limit,
            resume=False,
            download_images=True,
            download_timeout=20,
            save_composite_images=True,
            composite_image_dir="./debug_composite_images",
        )
        
        if not results:
            print("❌ No results returned from analysis")
            sys.exit(1)
        
        print()
        print("=" * 80)
        print("💾 Saving results to dashboard...")
        print("=" * 80)
        
        # Initialize dashboard database
        dashboard_db_path = Path(__file__).parent / "red-zone-dashboard" / "red_zone_analysis.db"
        init_database()
        
        # Calculate stats
        total = len(results)
        passed = sum(
            1 for r in results 
            if r.analysis and not r.analysis.get("red_safe_zone", {}).get("contains_key_elements", True)
        )
        failed = total - passed
        
        # Create analysis run
        parameters = {
            "source": "shiny_sot_analysis",
            "days_back": days_back,
            "limit": limit,
            "sot_types": "ALL (shiny filtered)",
            "timestamp": datetime.now().isoformat(),
        }
        
        description = f"Top {limit} Shiny SOT Eligible Titles Analysis"
        
        run_id = AnalysisRun.create(
            total=total,
            passed=passed,
            failed=failed,
            parameters=parameters,
            description=description,
        )
        
        # Convert results for database
        db_results = []
        for result in results:
            db_results.append({
                "content_id": result.content_id,
                "program_id": result.program_id,
                "content_name": result.content_name,
                "title": result.content_name,
                "content_type": result.content_type,
                "sot_name": result.sot_name,
                "poster_img_url": result.poster_img_url,
                "poster_url": result.poster_img_url,
                "analysis": result.analysis,
            })
        
        # Save to database
        PosterResult.create_batch(run_id, db_results)
        
        print()
        print("✅ Results saved successfully!")
        print()
        print("=" * 80)
        print("📊 ANALYSIS SUMMARY")
        print("=" * 80)
        print(f"Run ID:        {run_id}")
        print(f"Total:         {total}")
        print(f"Passed:        {passed} ({passed/total*100:.1f}%)")
        print(f"Failed:        {failed} ({failed/total*100:.1f}%)")
        print(f"Database:      {dashboard_db_path}")
        print()
        print("View results at: http://localhost:5000/results/{}".format(run_id))
        print("=" * 80)
        
        # Export to JSON file as well
        output_file = Path(f"shiny_sot_analysis_{limit}_posters.json")
        with open(output_file, "w") as f:
            json.dump([r.to_dict() for r in results], f, indent=2)
        
        print()
        print(f"📁 Results also exported to: {output_file}")
        print()
        
        # Show SOT breakdown
        sot_summary = pipeline.get_summary_by_sot(results)
        print()
        print("📈 Results by SOT Type:")
        print("-" * 80)
        print(f"{'SOT Type':<20} {'Total':<8} {'Passed':<8} {'Failed':<8} {'Fail Rate':<10}")
        print("-" * 80)
        
        for sot_name, stats in sorted(sot_summary.items()):
            total_sot = stats["total"]
            passed_sot = stats["without_key_elements"]  # "without" means passed
            failed_sot = stats["with_key_elements"]
            fail_rate = failed_sot / total_sot * 100 if total_sot > 0 else 0
            
            print(f"{sot_name:<20} {total_sot:<8} {passed_sot:<8} {failed_sot:<8} {fail_rate:<10.1f}%")
        
        print("-" * 80)
        print()
        
        return run_id
        
    except KeyboardInterrupt:
        print("\n\n❌ Analysis interrupted by user")
        sys.exit(1)
    except Exception as exc:
        print(f"\n\n❌ Analysis failed: {exc}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

