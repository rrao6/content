"""Test all dashboard functionality to ensure everything works."""
import requests
import json
import time
from datetime import datetime

# Base URL for testing
BASE_URL = "http://localhost:5000"

def test_endpoint(name, method, url, data=None, expected_status=200):
    """Test a single endpoint."""
    try:
        if method == "GET":
            response = requests.get(url)
        elif method == "POST":
            response = requests.post(url, json=data)
        else:
            return f"❌ {name}: Unknown method {method}"
        
        if response.status_code == expected_status:
            return f"✅ {name}: OK ({response.status_code})"
        else:
            return f"❌ {name}: Expected {expected_status}, got {response.status_code}"
    except Exception as e:
        return f"❌ {name}: Failed - {str(e)}"

def run_tests():
    """Run all functionality tests."""
    print("🧪 Testing Red Zone Dashboard Functionality\n")
    
    # Test endpoints
    tests = [
        ("Homepage", "GET", f"{BASE_URL}/", None, 200),
        ("Results Page", "GET", f"{BASE_URL}/results", None, 302),  # Redirects to latest
        ("Results Page (Run 4)", "GET", f"{BASE_URL}/results/4", None, 200),
        ("Detail Page", "GET", f"{BASE_URL}/detail/1", None, 200),
        ("Analyze Page", "GET", f"{BASE_URL}/analyze", None, 200),
        ("Import Page", "GET", f"{BASE_URL}/import", None, 200),
        ("QA Guide", "GET", f"{BASE_URL}/qa-guide", None, 200),
        ("API Runs", "GET", f"{BASE_URL}/api/runs", None, 200),
        ("API Results", "GET", f"{BASE_URL}/api/results?run_id=4", None, 200),
        ("API Trending", "GET", f"{BASE_URL}/api/stats/trending", None, 200),
        ("Export Run", "GET", f"{BASE_URL}/export/4", None, 200),
    ]
    
    for test in tests:
        result = test_endpoint(*test)
        print(result)
    
    # Test new analysis
    print("\n📊 Testing New Analysis Creation:")
    analysis_data = {
        "sot_types": ["just_added", "most_popular"],
        "days_back": 7,
        "limit": 10,
        "description": f"Test Analysis - {datetime.now().strftime('%H:%M:%S')}",
        "model": "gpt-4o",
        "use_cache": True
    }
    
    result = test_endpoint("Create Analysis", "POST", f"{BASE_URL}/api/analyze", analysis_data, 200)
    print(result)
    
    # Test API responses
    print("\n🔍 Testing API Response Content:")
    
    # Check runs API
    try:
        response = requests.get(f"{BASE_URL}/api/runs")
        runs = response.json()
        print(f"✅ API Runs: Found {len(runs)} runs")
        if runs:
            latest = runs[0]
            print(f"   Latest: Run #{latest['id']} - {latest['description']}")
    except Exception as e:
        print(f"❌ API Runs: {e}")
    
    # Check results API
    try:
        response = requests.get(f"{BASE_URL}/api/results?run_id=4")
        results = response.json()
        print(f"✅ API Results: Found {len(results)} results for run 4")
        if results:
            print(f"   Sample: {results[0]['title']} - {'FAIL' if results[0]['has_elements'] else 'PASS'}")
    except Exception as e:
        print(f"❌ API Results: {e}")
    
    # Check trending API
    try:
        response = requests.get(f"{BASE_URL}/api/stats/trending")
        trending = response.json()
        print(f"✅ API Trending: Found {len(trending)} days of data")
    except Exception as e:
        print(f"❌ API Trending: {e}")
    
    print("\n✨ Testing complete!")
    print("\nManual checks needed:")
    print("1. Visit dashboard and check if numbers are correct")
    print("2. Click on poster images to see detail view")
    print("3. Test filters on results page")
    print("4. Check if images load properly (using picsum.photos)")
    print("5. Verify red zone overlay appears on posters")

if __name__ == "__main__":
    print("⚠️  Make sure Flask server is running on http://localhost:5000")
    print("Press Enter to continue...")
    input()
    
    run_tests()
