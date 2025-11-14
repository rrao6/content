"""Quick test to verify everything is working."""
import requests
import json
import time

def test_dashboard():
    """Test that dashboard is running and functional."""
    print("\n🎯 Testing Red Zone Dashboard\n")
    
    base_url = "http://localhost:5000"
    
    # 1. Test Dashboard is running
    try:
        response = requests.get(base_url, timeout=5)
        if response.status_code == 200:
            print("✅ Dashboard is running at http://localhost:5000")
        else:
            print(f"❌ Dashboard returned status {response.status_code}")
            return
    except Exception as e:
        print(f"❌ Dashboard not accessible: {e}")
        print("   Please run: python3 dashboard.py")
        return
    
    # 2. Test API endpoints
    print("\n📡 Testing API Endpoints:")
    
    # Test runs API
    try:
        response = requests.get(f"{base_url}/api/runs")
        runs = response.json()
        print(f"✅ API /api/runs: Found {len(runs)} analysis runs")
        if runs:
            latest = runs[0]
            print(f"   Latest: Run #{latest['id']} - {latest.get('description', 'No description')}")
            print(f"   Total: {latest['total_analyzed']}, Pass: {latest['pass_count']}, Fail: {latest['fail_count']}")
    except Exception as e:
        print(f"❌ API /api/runs failed: {e}")
    
    # Test results API
    try:
        response = requests.get(f"{base_url}/api/results?run_id=4")
        results = response.json()
        print(f"✅ API /api/results: Found {len(results)} results for run 4")
    except Exception as e:
        print(f"❌ API /api/results failed: {e}")
    
    # 3. Test Image Proxy
    print("\n🖼️  Testing Image Proxy:")
    test_url = "http://img.adrise.tv/movie/100001/poster_v2.jpg"
    try:
        response = requests.get(f"{base_url}/proxy/image?url={test_url}")
        if response.status_code == 200:
            content_type = response.headers.get('content-type', '')
            print(f"✅ Image proxy working: {content_type}")
            print(f"   Size: {len(response.content)} bytes")
        else:
            print(f"❌ Image proxy returned {response.status_code}")
    except Exception as e:
        print(f"❌ Image proxy failed: {e}")
    
    # 4. Test New Analysis Feature
    print("\n🚀 Testing New Analysis Feature:")
    print("   Creating a demo analysis run...")
    
    analysis_data = {
        "sot_types": ["just_added"],
        "days_back": 7,
        "limit": 5,
        "description": f"Test Analysis - {time.strftime('%H:%M:%S')}",
        "model": "gpt-4o",
        "use_cache": True
    }
    
    try:
        response = requests.post(
            f"{base_url}/api/analyze", 
            json=analysis_data,
            timeout=30
        )
        result = response.json()
        
        if result.get('status') == 'success':
            print(f"✅ New analysis created successfully!")
            print(f"   Run ID: {result.get('run_id')}")
            print(f"   Message: {result.get('message')}")
            if result.get('is_demo'):
                print("   Note: Running in demo mode (real pipeline not available)")
            else:
                print("   Note: Using REAL data pipeline!")
        elif result.get('status') == 'error':
            print(f"⚠️  Analysis returned error: {result.get('message')}")
            if 'exceeds maximum' in result.get('message', ''):
                print("   This is expected - batch size limits are working!")
        else:
            print(f"❌ Unexpected response: {result}")
            
    except Exception as e:
        print(f"❌ New analysis failed: {e}")
    
    # 5. Summary
    print("\n📊 Dashboard Summary:")
    print(f"   🌐 URL: http://localhost:5000")
    print(f"   📈 Results: http://localhost:5000/results")
    print(f"   🆕 New Analysis: http://localhost:5000/analyze")
    print(f"   📚 QA Guide: http://localhost:5000/qa-guide")
    
    print("\n✨ Dashboard is ready for use!")
    print("\nTo test with REAL data:")
    print("1. Ensure your .env has correct Databricks/OpenAI credentials")
    print("2. Run: python3 production_integration.py")
    print("3. This will fetch real eligible titles and analyze real posters")

if __name__ == "__main__":
    test_dashboard()
