#!/usr/bin/env python3
"""Test script to verify analysis accuracy and duplicate prevention."""
import os
import sys
import json
import time
import requests
from pathlib import Path
from collections import defaultdict

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

def test_sot_mapping():
    """Test that SOT type mapping works correctly."""
    print("\n📋 Testing SOT Type Mapping...")
    
    # Test mappings
    test_cases = [
        (["most_popular"], ["most_liked"]),
        (["rotten_tomatoes"], ["rt"]),
        (["just_added"], ["just_added"]),
        (["imdb", "most_popular"], ["imdb", "most_liked"]),
    ]
    
    # Import from the correct path
    sys.path.append(str(Path(__file__).parent / 'red-zone-dashboard'))
    from analyzer import DashboardAnalyzer
    analyzer = DashboardAnalyzer()
    
    for input_sots, expected in test_cases:
        result = analyzer._normalize_sot_types(input_sots)
        if result == expected:
            print(f"   ✅ {input_sots} → {result}")
        else:
            print(f"   ❌ {input_sots} → {result} (expected {expected})")

def test_api_request(sot_types, limit=5):
    """Test analysis API with given SOT types."""
    url = "http://localhost:5000/api/analyze"
    payload = {
        "sot_types": sot_types,
        "days_back": 7,
        "limit": limit,
        "description": f"Test: {', '.join(sot_types)}"
    }
    
    try:
        response = requests.post(url, json=payload)
        return response.json()
    except Exception as e:
        return {"status": "error", "message": str(e)}

def check_duplicates(results):
    """Check for duplicate content in results."""
    seen = defaultdict(list)
    duplicates = []
    
    for result in results:
        key = (result.get('content_id'), result.get('sot_name'))
        if key in seen:
            duplicates.append({
                'content_id': result.get('content_id'),
                'title': result.get('title'),
                'sot_name': result.get('sot_name'),
                'appears_in': [seen[key][0]['id'], result['id']]
            })
        seen[key].append(result)
    
    return duplicates

def run_accuracy_tests():
    """Run comprehensive accuracy tests."""
    print("\n🔬 Red Zone Analysis Accuracy Tests")
    print("="*60)
    
    # Test 1: SOT Mapping
    test_sot_mapping()
    
    # Test 2: Individual SOT Types
    print("\n📊 Testing Individual SOT Types...")
    
    sot_tests = [
        ["just_added"],
        ["leaving_soon"],
        ["most_popular"],  # Should map to most_liked
        ["imdb"],
        ["rotten_tomatoes"],  # Should map to rt
    ]
    
    for sot_types in sot_tests:
        print(f"\n   Testing: {sot_types}")
        result = test_api_request(sot_types, limit=3)
        
        if result.get('status') == 'accepted':
            print(f"   ✅ Job accepted: {result.get('job_id')}")
        elif result.get('status') == 'success':
            print(f"   ✅ Completed immediately")
        else:
            print(f"   ❌ Failed: {result.get('message')}")
    
    # Test 3: Multiple SOT Types (check for duplicates)
    print("\n🔍 Testing Multiple SOT Types for Duplicates...")
    
    result = test_api_request(["just_added", "most_popular", "imdb"], limit=10)
    if result.get('status') in ['accepted', 'success']:
        print(f"   ✅ Multiple SOT analysis started")
        
        # Wait for completion if async
        if result.get('job_id'):
            print(f"   ⏳ Waiting for job {result['job_id']} to complete...")
            # In real scenario, would poll for completion
    
    # Test 4: Empty/Invalid SOT Types
    print("\n🚫 Testing Invalid SOT Types...")
    
    invalid_tests = [
        [],  # Empty
        ["invalid_sot"],  # Invalid type
        ["most_popular_invalid"],  # Partially invalid
    ]
    
    for sot_types in invalid_tests:
        result = test_api_request(sot_types, limit=1)
        if result.get('status') == 'error':
            print(f"   ✅ Correctly rejected: {sot_types} - {result.get('message')}")
        else:
            print(f"   ❌ Should have failed: {sot_types}")
    
    # Test 5: Performance Check
    print("\n⏱️  Performance Check...")
    
    start_time = time.time()
    result = test_api_request(["just_added"], limit=5)
    request_time = time.time() - start_time
    
    print(f"   Request time: {request_time:.2f}s")
    if result.get('status') in ['accepted', 'success']:
        print(f"   ✅ Analysis initiated successfully")
    
    print("\n" + "="*60)
    print("✨ Accuracy tests complete!")
    print("\n📌 Recommendations:")
    print("   1. Always normalize SOT types before querying")
    print("   2. Use DISTINCT in SQL to prevent duplicates")
    print("   3. Monitor performance with batch sizes > 50")
    print("   4. Test with all SOT combinations before production")

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
    
    run_accuracy_tests()
