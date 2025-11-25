#!/usr/bin/env python3
"""Clear any stuck analysis and provide instructions."""
import os
import requests

print("🔧 CLEARING STUCK ANALYSIS")
print("="*60)

# Check for any analysis checkpoint files
print("\n1️⃣ Checking for checkpoint files...")
checkpoint_files = [
    "sot_analysis_checkpoint.json",
    "analysis_checkpoint.json",
    ".checkpoint"
]

for cf in checkpoint_files:
    if os.path.exists(cf):
        print(f"   Found: {cf}")
        os.remove(cf)
        print(f"   ✅ Removed {cf}")
    else:
        print(f"   ✓ No {cf} found")

print("\n2️⃣ Browser Cache Issue")
print("-"*60)
print("The 'Resuming analysis progress' message is likely from browser cache.")
print("\nTo fix this:")
print("1. Go to the browser tab showing the message")
print("2. Press Ctrl+Shift+R (Windows) or Cmd+Shift+R (Mac) to hard refresh")
print("   OR")
print("3. Open Developer Tools (F12)")
print("4. Go to Application/Storage tab")
print("5. Find 'Local Storage' for localhost:5000")
print("6. Look for any keys like 'analysis_job_id' or similar")
print("7. Delete them")
print("   OR")
print("8. Simply close that tab and open a new one")

print("\n3️⃣ Fresh Analysis Page")
print("-"*60)
print("Open a NEW browser tab and go to:")
print("➡️  http://localhost:5000/analyze")
print("\nThis will give you a fresh analysis form without any cached state.")

print("\n✅ SOLUTION SUMMARY")
print("="*60)
print("1. Close the tab with 'Resuming analysis'")
print("2. Open NEW tab: http://localhost:5000/analyze")
print("3. Configure your shiny analysis:")
print("   • Check 'Shiny Only' ✅")
print("   • Set batch: 1000")
print("   • Click 'Start Analysis'")
print("\nThe system is clean - it's just browser cache!")
print("="*60)
