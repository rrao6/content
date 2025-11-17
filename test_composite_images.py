#!/usr/bin/env python3
"""
Test script to verify composite images with red zone overlay.

This script runs analysis on a small number of posters and saves 
the composite images (with red zone overlay) to disk for visual verification.
"""
import sys
from pathlib import Path

from config import get_config
from service import ContentService
from analysis import SafeZoneAnalyzer, PosterAnalysisPipeline, SAFE_ZONE_PROMPT


def main():
    """Run test analysis with composite image saving."""
    print("=" * 70)
    print("Testing Composite Image Generation")
    print("=" * 70)
    print()
    
    # Get configuration
    config = get_config()
    
    if not config.openai_api_key:
        print("❌ ERROR: OPENAI_API_KEY not configured")
        print("   Please set it in your .env file")
        sys.exit(1)
    
    print(f"✓ OpenAI API Key: configured")
    print(f"✓ Model: {config.openai_model}")
    print()
    
    # Setup analyzer and pipeline
    analyzer = SafeZoneAnalyzer(
        provider="openai",
        model=config.openai_model,
        prompt=SAFE_ZONE_PROMPT,
        api_key=config.openai_api_key,
    )
    
    service = ContentService()
    pipeline = PosterAnalysisPipeline(service, analyzer, config=config)
    
    # Run analysis with composite image saving enabled
    output_dir = "./debug_composite_images"
    limit = 5  # Just test with 5 posters
    
    print(f"Running analysis on {limit} posters...")
    print(f"Composite images will be saved to: {output_dir}/")
    print()
    
    results = pipeline.run(
        limit=limit,
        batch_size=10,
        include_inactive=False,
        allow_null_urls=False,
        download_images=True,
        download_timeout=20,
        save_composite_images=True,  # Enable composite image saving
        composite_image_dir=output_dir,
    )
    
    # Print results
    print()
    print("=" * 70)
    print("Results Summary")
    print("=" * 70)
    print(f"Total processed: {len(results)}")
    print(f"Successful: {sum(1 for r in results if r.analysis is not None)}")
    print(f"Failed: {sum(1 for r in results if r.error is not None)}")
    print()
    
    # Show details
    for i, result in enumerate(results, 1):
        print(f"\n{i}. Content ID: {result.content_id}")
        print(f"   Poster URL: {result.poster_img_url[:60]}...")
        
        if result.error:
            print(f"   ❌ Error: {result.error}")
        elif result.analysis:
            red_zone = result.analysis.get("red_safe_zone", {})
            contains = red_zone.get("contains_key_elements", None)
            confidence = red_zone.get("confidence", 0)
            justification = red_zone.get("justification", "N/A")
            
            status = "⚠️  Contains Elements" if contains else "✅ Safe"
            print(f"   {status}")
            print(f"   Confidence: {confidence}%")
            print(f"   Reason: {justification}")
            
            # Show composite image path
            image_path = Path(output_dir) / f"content_{result.content_id}.png"
            if image_path.exists():
                print(f"   🖼️  Composite: {image_path}")
    
    print()
    print("=" * 70)
    print("✅ Test Complete!")
    print("=" * 70)
    print()
    print(f"Review the composite images in: {output_dir}/")
    print("Each image should have a RED RECTANGLE in the top-left corner")
    print("showing the 60% width × 10% height safe zone region.")
    print()


if __name__ == "__main__":
    main()

