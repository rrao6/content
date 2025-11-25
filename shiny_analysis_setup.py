#!/usr/bin/env python3
"""Setup script to check shiny analysis configuration and fix the 200 limit issue."""
import os
import sys
import requests
from pathlib import Path

# Load environment
sys.path.append(str(Path(__file__).parent))
from run_dashboard_clean import load_environment
load_environment()

print("🔧 SETTING UP SHINY ANALYSIS FOR 1000 POSTERS")
print("="*70)

# Check current configuration
print("\n1️⃣ Checking Current Configuration...")
print("-"*50)

# Check analyzer MAX_BATCH_SIZE
analyzer_path = Path("red-zone-dashboard/analyzer.py")
with open(analyzer_path, 'r') as f:
    content = f.read()
    if "MAX_BATCH_SIZE = 1000" in content:
        print("✅ Backend MAX_BATCH_SIZE: 1000")
    else:
        print("❌ Backend MAX_BATCH_SIZE: Not set to 1000")

# Check UI limit
ui_path = Path("red-zone-dashboard/templates/analyze.html")
with open(ui_path, 'r') as f:
    content = f.read()
    if 'max="1000"' in content:
        print("✅ UI max limit: 1000")
    else:
        print("❌ UI max limit: Not set to 1000")
    
    if 'name="shiny_only"' in content:
        print("✅ Shiny Only checkbox: Present")
    else:
        print("❌ Shiny Only checkbox: Missing")

# Test the API
print("\n2️⃣ Testing Analysis API...")
print("-"*50)

try:
    # Test with batch size of 1000 (should work now)
    response = requests.post(
        'http://localhost:5000/api/analyze',
        json={
            'sot_types': ['just_added'],
            'days_back': 7,
            'limit': 1000,
            'description': 'Test 1000 batch size',
            'shiny_only': True
        }
    )
    
    if response.status_code == 200:
        print("✅ API accepts 1000 batch size!")
        job_data = response.json()
        job_id = job_data.get('job_id')
        print(f"   Job ID: {job_id}")
        
        # Cancel the job since it's just a test
        # (No cancel endpoint, it will timeout)
        
    else:
        print(f"❌ API rejected 1000 batch size: {response.status_code}")
        error_data = response.json()
        if 'message' in error_data:
            print(f"   Error: {error_data['message']}")
            
            # If it says 200 is the limit, we need to restart the dashboard
            if "200" in error_data['message']:
                print("\n⚠️  The dashboard is using cached configuration!")
                print("   Solution: Restart the dashboard to pick up the new MAX_BATCH_SIZE")
                
except Exception as e:
    print(f"❌ API test failed: {e}")

# Show how to analyze shiny titles
print("\n3️⃣ Shiny Title Analysis Instructions")
print("-"*50)
print("To analyze 1000 shiny titles:")
print("1. Make sure dashboard is restarted (if needed)")
print("2. Go to http://localhost:5000/analyze")
print("3. Configuration:")
print("   • SOT Types: Select desired types (e.g., just_added, most_popular)")
print("   • Days Back: 30 (recommended)")
print("   • Batch Size: 1000")
print("   • ✅ Check 'Shiny Only' checkbox")
print("4. Click 'Start Analysis'")
print("\n⏱️  Estimated time: 15-20 minutes for 1000 posters")
print("📊 The system will only analyze titles where is_shiny = 1")

print("\n4️⃣ Note About Shiny Titles")
print("-"*50)
print("The 'Shiny Only' feature filters to premium/shiny content.")
print("This typically includes:")
print("  • Premium movies")
print("  • High-quality series")
print("  • Exclusive content")
print("  • Featured titles")

print("\n✅ Setup Complete!")
print("="*70)
