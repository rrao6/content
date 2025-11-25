#!/usr/bin/env python3
"""Test the analysis pipeline directly."""
import sys
import os
import json
from pathlib import Path

# Add paths
sys.path.append(str(Path(__file__).parent))
sys.path.append(str(Path(__file__).parent / 'red-zone-dashboard'))

# Load environment
from run_dashboard_clean import load_environment
load_environment()

from config import get_config
from service import ContentService, EligibleTitlesService
from analysis import SafeZoneAnalyzer

# Check parallel pipeline
try:
    from sot_pipeline_parallel import ParallelSOTAnalysisPipeline
    use_parallel = True
    print("✅ Using parallel pipeline")
except ImportError:
    from sot_pipeline import SOTAnalysisPipeline
    use_parallel = False
    print("⚠️  Using sequential pipeline")

# Initialize services
config = get_config()
print(f"\n📊 Configuration:")
print(f"   Databricks Host: {config.host[:20]}...")
print(f"   OpenAI Model: {config.openai_model}")
print(f"   RPM Limit: {config.vision_requests_per_minute}")

# Test database connection
print("\n🔍 Testing Database Connection...")
try:
    eligible_service = EligibleTitlesService(config)
    content_service = ContentService(config)
    
    # Test count
    counts = eligible_service.count_eligible_titles_by_sot(days_back=7)
    print(f"✅ Database connected. Eligible titles by SOT:")
    for sot, count in counts.items():
        print(f"   {sot}: {count:,}")
    
    # Create analyzer
    analyzer = SafeZoneAnalyzer(config)
    
    # Create pipeline
    if use_parallel:
        pipeline = ParallelSOTAnalysisPipeline(
            eligible_service=eligible_service,
            content_service=content_service,
            analyzer=analyzer,
            config=config,
            max_workers=3
        )
    else:
        pipeline = SOTAnalysisPipeline(
            eligible_service=eligible_service,
            content_service=content_service,
            analyzer=analyzer,
            config=config
        )
    
    # Test with 1 poster
    print("\n🧪 Testing with 1 poster...")
    results = pipeline.run(
        days_back=7,
        sot_types=['just_added'],
        limit=1,
        batch_size=1,
        resume=False,
        download_images=True,
        save_composite_images=False
    )
    
    if results:
        print(f"✅ Analysis successful! Got {len(results)} result(s)")
        result = results[0]
        print(f"\n📋 First Result:")
        print(f"   Content: {result.content_name}")
        print(f"   ID: {result.content_id}")
        print(f"   SOT: {result.sot_name}")
        print(f"   Poster URL: {result.poster_img_url[:50]}...")
        if result.analysis:
            red_zone = result.analysis.get('red_safe_zone', {})
            print(f"   Has Elements: {red_zone.get('contains_key_elements')}")
            print(f"   Confidence: {red_zone.get('confidence')}%")
        if result.error:
            print(f"   ❌ Error: {result.error}")
    else:
        print("❌ No results returned")
        
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n✅ Direct test complete")
