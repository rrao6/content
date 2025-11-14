#!/usr/bin/env python
"""Production test script to validate the complete pipeline."""
import os
import sys
import time
import json
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from config import get_config
from service import ContentService
from analysis import SafeZoneAnalyzer, PosterAnalysisPipeline
from monitoring import get_analysis_monitor
import structlog

# Configure logging
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer()
    ]
)
logger = structlog.get_logger()


def test_single_poster():
    """Test analyzing a single poster with detailed debugging."""
    print("\n=== Testing Single Poster Analysis ===\n")
    
    try:
        # Initialize components
        config = get_config()
        analyzer = SafeZoneAnalyzer(
            provider="openai",
            model=config.openai_model,
            api_key=config.openai_api_key,
        )
        
        # Test URL (replace with actual poster URL)
        test_url = "http://img.adrise.tv/42af1eca-d15a-4f1f-86fd-80912e1e77ff.png"
        
        print(f"Testing with URL: {test_url}")
        
        # Test direct analysis (will download and convert to base64)
        from analysis import _download_image_to_base64
        
        print("\n1. Downloading image...")
        start = time.time()
        try:
            image_data = _download_image_to_base64(test_url)
            print(f"   ✓ Download successful ({time.time() - start:.2f}s)")
            print(f"   ✓ Data URI length: {len(image_data)} chars")
        except Exception as e:
            print(f"   ✗ Download failed: {e}")
            return
        
        print("\n2. Analyzing image...")
        start = time.time()
        try:
            result = analyzer.analyze(image_data)
            print(f"   ✓ Analysis successful ({time.time() - start:.2f}s)")
            print("\nResult:")
            print(json.dumps(result, indent=2))
        except Exception as e:
            print(f"   ✗ Analysis failed: {e}")
            import traceback
            traceback.print_exc()
            
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()


def test_batch_with_monitoring():
    """Test batch processing with full monitoring."""
    print("\n=== Testing Batch Processing with Monitoring ===\n")
    
    try:
        # Initialize
        config = get_config()
        service = ContentService()
        analyzer = SafeZoneAnalyzer(
            provider="openai",
            model=config.openai_model,
            api_key=config.openai_api_key,
        )
        pipeline = PosterAnalysisPipeline(service, analyzer)
        monitor = get_analysis_monitor()
        
        # Run small batch
        print("Running analysis on 3 posters...")
        start = time.time()
        results = pipeline.run(
            limit=3,
            batch_size=10,
            download_images=True,  # Enable image download
            download_timeout=30,
        )
        duration = time.time() - start
        
        print(f"\nCompleted in {duration:.2f}s")
        print(f"Results: {len(results)} posters analyzed")
        
        # Show results
        success_count = sum(1 for r in results if r.analysis is not None)
        print(f"  - Successful: {success_count}")
        print(f"  - Failed: {len(results) - success_count}")
        
        # Show sample result
        if results:
            print("\nSample result:")
            print(json.dumps(results[0].to_dict(), indent=2))
        
        # Show monitoring metrics
        print("\n=== Monitoring Metrics ===")
        metrics = monitor.get_health_status()
        print(json.dumps(metrics, indent=2))
        
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()


def test_json_cleaning():
    """Test the JSON response cleaning functionality."""
    print("\n=== Testing JSON Response Cleaning ===\n")
    
    from analysis import SafeZoneAnalyzer
    
    test_cases = [
        # Case 1: Markdown wrapped
        ('```json\n{"top_safe_zone": {"contains_key_elements": true}, "bottom_safe_zone": {"contains_key_elements": false}}\n```',
         '{"top_safe_zone": {"contains_key_elements": true}, "bottom_safe_zone": {"contains_key_elements": false}}'),
        
        # Case 2: Plain JSON
        ('{"top_safe_zone": {"contains_key_elements": true}, "bottom_safe_zone": {"contains_key_elements": false}}',
         '{"top_safe_zone": {"contains_key_elements": true}, "bottom_safe_zone": {"contains_key_elements": false}}'),
        
        # Case 3: Error message
        ("I'm unable to analyze this image.",
         '{"error": "I\'m unable to analyze this image."}'),
    ]
    
    for i, (input_text, expected) in enumerate(test_cases):
        print(f"Test case {i+1}:")
        print(f"  Input: {input_text[:50]}...")
        
        cleaned = SafeZoneAnalyzer._clean_json_response(input_text)
        print(f"  Cleaned: {cleaned[:50]}...")
        
        try:
            parsed = json.loads(cleaned)
            print(f"  ✓ Valid JSON")
        except:
            print(f"  ✗ Invalid JSON")
        print()


def main():
    """Run all tests."""
    print("=" * 60)
    print("POSTER ANALYSIS PRODUCTION TEST")
    print("=" * 60)
    
    # Check configuration
    try:
        config = get_config()
        print(f"\nConfiguration:")
        print(f"  - Databricks Host: {config.host}")
        print(f"  - OpenAI Model: {config.openai_model}")
        print(f"  - Cache Enabled: {config.enable_analysis_cache}")
        print(f"  - Rate Limit: {config.vision_requests_per_minute} req/min")
    except Exception as e:
        print(f"\nConfiguration Error: {e}")
        return
    
    # Run tests
    if "--json-clean" in sys.argv:
        test_json_cleaning()
    elif "--single" in sys.argv:
        test_single_poster()
    elif "--batch" in sys.argv:
        test_batch_with_monitoring()
    else:
        # Run all tests
        test_json_cleaning()
        test_single_poster()
        test_batch_with_monitoring()


if __name__ == "__main__":
    main()
