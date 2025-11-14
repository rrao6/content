"""Test the image proxy functionality."""
import requests

def test_proxy():
    """Test the image proxy endpoint."""
    print("🧪 Testing Image Proxy\n")
    
    # Test URLs
    test_cases = [
        {
            "name": "Valid HTTP image",
            "url": "http://img.adrise.tv/movie/100001/poster_v2.jpg",
            "expected": "success"
        },
        {
            "name": "No URL parameter",
            "url": None,
            "expected": "placeholder"
        },
        {
            "name": "Invalid domain",
            "url": "http://example.com/image.jpg",
            "expected": "placeholder"
        }
    ]
    
    base_url = "http://localhost:5000/proxy/image"
    
    print("⚠️  Make sure the Flask server is running on http://localhost:5000")
    print("Press Enter to continue...")
    input()
    
    for test in test_cases:
        print(f"\nTesting: {test['name']}")
        print(f"URL: {test['url']}")
        
        try:
            if test['url']:
                response = requests.get(base_url, params={'url': test['url']}, timeout=5)
            else:
                response = requests.get(base_url, timeout=5)
            
            print(f"Status: {response.status_code}")
            print(f"Content-Type: {response.headers.get('content-type')}")
            print(f"Content Length: {len(response.content)} bytes")
            
            if response.status_code == 200:
                if test['expected'] == 'placeholder' and 'svg' in response.headers.get('content-type', ''):
                    print("✅ Correctly returned placeholder")
                elif test['expected'] == 'success':
                    print("✅ Image proxy working")
                else:
                    print("❌ Unexpected result")
            else:
                print("❌ Request failed")
                
        except Exception as e:
            print(f"❌ Error: {e}")
    
    print("\n✨ Test complete!")
    print("\nTo fully test:")
    print("1. Start the dashboard: python dashboard.py")
    print("2. Visit: http://localhost:5000/results")
    print("3. Check if poster images are loading")
    print("4. Open browser console to see fallback strategies in action")

if __name__ == "__main__":
    test_proxy()
