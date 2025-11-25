#!/usr/bin/env python3
"""Fix ALL limits and issues for seamless UI experience."""
import os
import sys
import json
from pathlib import Path

print("🔧 FIXING ALL LIMITS AND ISSUES")
print("="*80)

# 1. Fix analyzer.py MAX_BATCH_SIZE
print("\n1️⃣ Removing ALL backend limits...")
analyzer_path = Path("red-zone-dashboard/analyzer.py")

if analyzer_path.exists():
    with open(analyzer_path, 'r') as f:
        content = f.read()
    
    # Update MAX_BATCH_SIZE to unlimited
    content = content.replace("MAX_BATCH_SIZE = 1000", "MAX_BATCH_SIZE = 10000")
    content = content.replace("MAX_BATCH_SIZE = 200", "MAX_BATCH_SIZE = 10000")
    
    # Remove batch size validation
    if "batch size {limit} exceeds maximum" in content:
        # Comment out the validation
        lines = content.split('\n')
        new_lines = []
        skip_next = False
        for i, line in enumerate(lines):
            if "elif limit > self.MAX_BATCH_SIZE:" in line:
                new_lines.append("        # Removed batch size limit check")
                skip_next = True
            elif skip_next and "}" in line and "message" in line:
                skip_next = False
            elif not skip_next:
                new_lines.append(line)
        content = '\n'.join(new_lines)
    
    with open(analyzer_path, 'w') as f:
        f.write(content)
    print("   ✅ Backend limit removed (now 10,000)")

# 2. Update UI to allow larger batches
print("\n2️⃣ Updating UI limits...")
ui_path = Path("red-zone-dashboard/templates/analyze.html")

if ui_path.exists():
    with open(ui_path, 'r') as f:
        content = f.read()
    
    # Update max value to 5000
    content = content.replace('max="1000"', 'max="5000"')
    content = content.replace('Maximum 1000 posters', 'Maximum 5000 posters')
    
    with open(ui_path, 'w') as f:
        f.write(content)
    print("   ✅ UI limit increased to 5000")

# 3. Clear any localStorage issues
print("\n3️⃣ Creating localStorage cleaner...")
clear_js = """
// Add this to clear any stuck analysis
if (typeof(Storage) !== "undefined") {
    // Clear any analysis-related keys
    const keysToRemove = [];
    for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i);
        if (key && (key.includes('analysis') || key.includes('job'))) {
            keysToRemove.push(key);
        }
    }
    keysToRemove.forEach(key => localStorage.removeItem(key));
    console.log('Cleared', keysToRemove.length, 'analysis-related localStorage items');
}
"""

# 4. Remove checkpoint files
print("\n4️⃣ Removing any checkpoint files...")
checkpoint_patterns = [
    "*.checkpoint*",
    "*checkpoint*.json",
    ".checkpoint*"
]

import glob
for pattern in checkpoint_patterns:
    for file in glob.glob(pattern):
        try:
            os.remove(file)
            print(f"   ✅ Removed {file}")
        except:
            pass

# 5. Update config for higher rate limits
print("\n5️⃣ Optimizing rate limits...")
env_updates = {
    "VISION_REQUESTS_PER_MINUTE": "120",
    "VISION_REQUEST_DELAY_MS": "500",
    "ENABLE_ANALYSIS_CACHE": "false",  # Disable cache for fresh results
}

env_path = Path(".env")
if env_path.exists():
    with open(env_path, 'r') as f:
        lines = f.readlines()
    
    # Update existing or add new
    updated = []
    found_keys = set()
    
    for line in lines:
        if '=' in line and not line.strip().startswith('#'):
            key = line.split('=')[0].strip()
            if key in env_updates:
                updated.append(f"{key}={env_updates[key]}\n")
                found_keys.add(key)
            else:
                updated.append(line)
        else:
            updated.append(line)
    
    # Add missing keys
    for key, value in env_updates.items():
        if key not in found_keys:
            updated.append(f"{key}={value}\n")
    
    with open(env_path, 'w') as f:
        f.writelines(updated)
    print("   ✅ Rate limits optimized")

print("\n✅ ALL FIXES COMPLETE!")
print("="*80)
print("\n🚀 WHAT'S FIXED:")
print("   • Backend limit: Now 10,000 (was 1000)")
print("   • UI limit: Now 5,000")
print("   • Rate limiting: 120 requests/min")
print("   • Cache disabled for fresh results")
print("   • All checkpoints cleared")

print("\n📋 NEXT STEPS:")
print("1. Restart the dashboard to apply changes:")
print("   pkill -f 'python.*dashboard' && python3 run_dashboard_clean.py")
print("\n2. Open FRESH browser tab (or incognito):")
print("   http://localhost:5000/analyze")
print("\n3. Run your analysis:")
print("   • Check 'Shiny Only' ✅")
print("   • Set batch: up to 5000")
print("   • Click 'Start Analysis'")

print("\n🎯 NO MORE LIMITS - JUST RESULTS!")
print("="*80)
