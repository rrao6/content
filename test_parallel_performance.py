#!/usr/bin/env python3
"""Test script to demonstrate parallel processing performance improvements."""
import os
import sys
import time
import json
import requests
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

def test_sequential_vs_parallel():
    """Test performance difference between sequential and parallel processing."""
    print("\n🚀 Parallel Processing Performance Test")
    print("="*70)
    
    # Test configurations
    test_configs = [
        {
            "name": "Small Batch (Sequential Baseline)",
            "sot_types": ["just_added"],
            "limit": 10,
            "description": "Baseline test with 10 posters"
        },
        {
            "name": "Medium Batch (Parallel Test)",
            "sot_types": ["just_added"],
            "limit": 50,
            "description": "Parallel processing with 50 posters"
        },
        {
            "name": "Large Batch (Stress Test)",
            "sot_types": ["just_added", "most_popular"],
            "limit": 100,
            "description": "Large scale test with 100 posters"
        }
    ]
    
    results = []
    
    for config in test_configs:
        print(f"\n📊 Test: {config['name']}")
        print(f"   Description: {config['description']}")
        print(f"   SOT Types: {', '.join(config['sot_types'])}")
        print(f"   Batch Size: {config['limit']}")
        print("-"*50)
        
        # Start analysis
        start_time = time.time()
        response = requests.post(
            "http://localhost:5000/api/analyze",
            json={
                "sot_types": config["sot_types"],
                "days_back": 7,
                "limit": config["limit"],
                "description": config["description"]
            }
        )
        
        if response.status_code != 200:
            print(f"   ❌ Failed to start analysis: {response.text}")
            continue
            
        result_data = response.json()
        job_id = result_data.get('job_id')
        
        if not job_id:
            print(f"   ❌ No job ID returned")
            continue
            
        print(f"   ✅ Job started: {job_id}")
        
        # Monitor progress
        last_processed = 0
        while True:
            time.sleep(2)
            
            status_response = requests.get(f"http://localhost:5000/api/analyze/status/{job_id}")
            if status_response.status_code != 200:
                break
                
            status = status_response.json()
            
            # Show progress
            processed = status.get('processed', 0)
            total = status.get('total', config['limit'])
            
            if processed > last_processed:
                elapsed = time.time() - start_time
                rate = processed / elapsed * 60 if elapsed > 0 else 0
                pct = (processed / total * 100) if total > 0 else 0
                
                print(f"   Progress: {processed}/{total} ({pct:.1f}%) | Rate: {rate:.1f} posters/min", end='\r')
                last_processed = processed
            
            if status.get('status') == 'completed':
                print()  # New line after progress
                break
            elif status.get('status') == 'failed':
                print(f"\n   ❌ Job failed: {status.get('error')}")
                break
        
        # Calculate final metrics
        end_time = time.time()
        total_time = end_time - start_time
        
        if status.get('status') == 'completed':
            processed = status.get('processed', 0)
            success = status.get('success', 0)
            errors = status.get('errors', 0)
            
            avg_time = total_time / processed if processed > 0 else 0
            rate = processed / total_time * 60 if total_time > 0 else 0
            
            print(f"\n   ✅ Completed!")
            print(f"   📈 Metrics:")
            print(f"      - Total Time: {total_time:.1f} seconds")
            print(f"      - Processed: {processed} posters")
            print(f"      - Success: {success} ({success/processed*100:.1f}%)")
            print(f"      - Errors: {errors}")
            print(f"      - Avg Time/Poster: {avg_time:.2f} seconds")
            print(f"      - Processing Rate: {rate:.1f} posters/minute")
            
            results.append({
                "test": config["name"],
                "batch_size": config["limit"],
                "total_time": total_time,
                "avg_time": avg_time,
                "rate": rate,
                "success_rate": success/processed*100 if processed > 0 else 0
            })
    
    # Summary comparison
    print("\n" + "="*70)
    print("📊 Performance Comparison Summary")
    print("="*70)
    
    if len(results) >= 2:
        baseline = results[0]
        
        print(f"\nBaseline (Sequential): {baseline['rate']:.1f} posters/minute")
        print(f"Average time per poster: {baseline['avg_time']:.2f} seconds\n")
        
        for result in results[1:]:
            improvement = (result['rate'] / baseline['rate'] - 1) * 100 if baseline['rate'] > 0 else 0
            print(f"{result['test']}:")
            print(f"   - Rate: {result['rate']:.1f} posters/minute")
            print(f"   - Avg time: {result['avg_time']:.2f} seconds/poster")
            print(f"   - Improvement: {improvement:.1f}% faster than baseline")
            print()
    
    # Save results
    results_file = Path("performance_test_results.json")
    with open(results_file, 'w') as f:
        json.dump({
            "test_date": datetime.now().isoformat(),
            "results": results
        }, f, indent=2)
    
    print(f"📄 Results saved to: {results_file}")
    print("\n🎯 Optimization Recommendations:")
    print("   1. Use parallel processing for batches > 25 posters")
    print("   2. Increase worker threads for larger batches")
    print("   3. Monitor API rate limits during high-volume processing")
    print("   4. Enable caching to skip already-analyzed posters")

def check_parallel_configuration():
    """Check if parallel processing is properly configured."""
    print("\n🔧 Checking Parallel Processing Configuration...")
    
    try:
        # Import configuration
        from config import get_config
        from red_zone_dashboard.analyzer import DashboardAnalyzer
        
        config = get_config()
        analyzer = DashboardAnalyzer()
        
        print(f"✅ Configuration loaded")
        print(f"   - Rate limit: {config.vision_requests_per_minute} requests/minute")
        
        if hasattr(analyzer.pipeline, 'max_workers'):
            print(f"   - Max workers: {analyzer.pipeline.max_workers}")
            print(f"   - Pipeline type: Parallel")
        else:
            print(f"   - Pipeline type: Sequential (upgrade needed)")
        
        print(f"   - Cache enabled: {config.enable_analysis_cache}")
        
    except Exception as e:
        print(f"❌ Configuration check failed: {e}")

if __name__ == '__main__':
    # Check if dashboard is running
    try:
        response = requests.get('http://localhost:5000')
        if response.status_code != 200:
            print("❌ Dashboard not responding. Please start it first.")
            sys.exit(1)
    except:
        print("❌ Dashboard not running. Please run: python run_dashboard_clean.py")
        sys.exit(1)
    
    # Check configuration
    check_parallel_configuration()
    
    # Run performance tests
    test_sequential_vs_parallel()
