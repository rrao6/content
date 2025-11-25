#!/usr/bin/env python3
"""Comprehensive diagnostic for UI issues."""
import os
import sys
import time
import requests
import json
from pathlib import Path

print("🔍 COMPREHENSIVE UI DIAGNOSTIC")
print("="*80)

# Wait for dashboard to start
print("\n⏳ Waiting for dashboard to start...")
time.sleep(5)

# 1. Check dashboard is running
print("\n1️⃣ Dashboard Status Check...")
print("-"*60)
try:
    response = requests.get('http://localhost:5000')
    if response.status_code == 200:
        print("✅ Dashboard is running")
    else:
        print(f"❌ Dashboard returned status: {response.status_code}")
except Exception as e:
    print(f"❌ Dashboard not accessible: {e}")
    print("\nTry manually starting:")
    print("   cd /Users/rrao/content-1")
    print("   python3 run_dashboard_clean.py")
    sys.exit(1)

# 2. Check analyzer configuration
print("\n2️⃣ Backend Configuration Check...")
print("-"*60)

analyzer_path = Path("red-zone-dashboard/analyzer.py")
if analyzer_path.exists():
    with open(analyzer_path, 'r') as f:
        content = f.read()
        
    # Check MAX_BATCH_SIZE
    import re
    match = re.search(r'MAX_BATCH_SIZE\s*=\s*(\d+)', content)
    if match:
        max_batch = int(match.group(1))
        if max_batch >= 5000:
            print(f"✅ MAX_BATCH_SIZE: {max_batch}")
        else:
            print(f"❌ MAX_BATCH_SIZE: {max_batch} (should be >= 5000)")
    else:
        print("❌ MAX_BATCH_SIZE not found")

# 3. Check UI configuration
print("\n3️⃣ UI Configuration Check...")
print("-"*60)

ui_path = Path("red-zone-dashboard/templates/analyze.html")
if ui_path.exists():
    with open(ui_path, 'r') as f:
        content = f.read()
        
    # Check max value
    if 'max="5000"' in content:
        print("✅ UI max limit: 5000")
    else:
        match = re.search(r'max="(\d+)"', content)
        if match:
            print(f"❌ UI max limit: {match.group(1)} (should be 5000)")
        else:
            print("❌ UI max limit not found")

# 4. Test analysis API with large batch
print("\n4️⃣ Testing Analysis API...")
print("-"*60)

test_configs = [
    {"limit": 10, "desc": "Small test"},
    {"limit": 100, "desc": "Medium test"},
    {"limit": 1000, "desc": "Large test"},
    {"limit": 3049, "desc": "All shiny titles"}
]

for config in test_configs:
    print(f"\n   Testing {config['desc']} (limit={config['limit']})...")
    
    try:
        response = requests.post(
            'http://localhost:5000/api/analyze',
            json={
                'sot_types': ['just_added'],
                'days_back': 365,
                'limit': config['limit'],
                'shiny_only': True,
                'description': f"Diagnostic test - {config['desc']}"
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ API accepts batch size {config['limit']}")
            print(f"      Job ID: {data.get('job_id')}")
            
            # Cancel/check job status
            if data.get('job_id'):
                time.sleep(1)
                status_resp = requests.get(f"http://localhost:5000/api/analyze/status/{data['job_id']}")
                if status_resp.status_code == 200:
                    status = status_resp.json()
                    print(f"      Status: {status.get('status')}")
        else:
            print(f"   ❌ API rejected batch size {config['limit']}")
            try:
                error_data = response.json()
                print(f"      Error: {error_data.get('message', 'Unknown error')}")
            except:
                print(f"      Response: {response.text[:200]}")
                
    except Exception as e:
        print(f"   ❌ Test failed: {e}")

# 5. Check for JavaScript errors
print("\n5️⃣ JavaScript Console Fix...")
print("-"*60)

js_fix = """
<script>
// Add this to your browser console if analysis page is stuck:
localStorage.clear();
sessionStorage.clear();
location.reload();
</script>
"""

print("If the analyze page shows 'Resuming analysis' or is stuck:")
print("1. Open browser DevTools (F12)")
print("2. Go to Console tab")
print("3. Paste and run:")
print("   localStorage.clear();")
print("   location.reload();")

# 6. Direct link test
print("\n6️⃣ Direct Link Test...")
print("-"*60)
print("Try this direct link in an INCOGNITO/PRIVATE browser window:")
print("➡️  http://localhost:5000/analyze")
print("\nIncognito mode bypasses all cache issues.")

# Summary
print("\n" + "="*80)
print("📋 DIAGNOSTIC SUMMARY")
print("="*80)

print("\nIf still having issues:")
print("1. Use INCOGNITO MODE (Cmd+Shift+N on Chrome)")
print("2. Go directly to: http://localhost:5000/analyze")
print("3. The form should be fresh with no 'Resuming' message")
print("4. Set your batch size and click 'Start Analysis'")

print("\n💡 Common Issues:")
print("   • Browser cache → Use incognito mode")
print("   • Old localStorage → Clear browser data")
print("   • Backend not restarted → Run: python3 run_dashboard_clean.py")

print("\n🆘 If STILL not working, the issue might be:")
print("   • A specific error message (check browser console)")
print("   • Database connection issue")
print("   • Need to check the specific error you're seeing")

print("="*80)
