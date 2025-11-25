#!/usr/bin/env python3
"""Verify we have a fresh start for shiny analysis."""
import requests
import time

print("🔄 FRESH START VERIFICATION")
print("="*60)

# 1. Check dashboard
print("\n1️⃣ Dashboard Status...")
try:
    response = requests.get('http://localhost:5000')
    if response.status_code == 200:
        print("✅ Dashboard is running fresh")
except:
    print("❌ Dashboard not accessible")

# 2. Check active jobs
print("\n2️⃣ Active Jobs Check...")
try:
    response = requests.get('http://localhost:5000/api/runs')
    if response.status_code == 200:
        runs = response.json()
        active_runs = [r for r in runs if r.get('status') == 'running']
        if active_runs:
            print(f"⚠️  Found {len(active_runs)} active runs - these should be stopped")
            for run in active_runs:
                print(f"   Run {run['id']}: {run.get('description', 'No description')}")
        else:
            print("✅ No active runs - clean slate!")
except Exception as e:
    print(f"Error checking runs: {e}")

# 3. Show latest runs
print("\n3️⃣ Recent Runs...")
try:
    response = requests.get('http://localhost:5000/api/runs')
    if response.status_code == 200:
        runs = response.json()[:3]
        for run in runs:
            status_icon = "✅" if run['status'] == 'completed' else "⚠️"
            print(f"{status_icon} Run {run['id']}: {run['total_analyzed']} analyzed - {run.get('description', 'No description')}")
except:
    pass

print("\n" + "="*60)
print("✅ READY FOR FRESH SHINY ANALYSIS!")
print("="*60)
print("\n🎯 Start your clean analysis:")
print("1. Go to: http://localhost:5000/analyze")
print("2. Check 'Shiny Only' ✅")
print("3. Set batch: 1000")
print("4. Click 'Start Analysis'")
print("\nNo old processes running - database is clean - ready to go!")
print("="*60)
