# Safe Zone Analysis Run - 100 Eligible SOT Posters

**Date:** November 17, 2025  
**Time:** 13:56 - 14:09 PST (13 minutes)  
**Status:** ✅ COMPLETED SUCCESSFULLY

---

## 📊 Analysis Summary

### Overall Statistics
- **Total Posters Analyzed:** 100
- **Success Rate:** 100% (no errors)
- **Processing Rate:** 7.7 posters/minute
- **Average Time per Poster:** 7.8 seconds
- **Total Duration:** 13.1 minutes (784 seconds)

### Results Breakdown
- **✅ Passed (No Elements in Red Zone):** 75 posters (75%)
- **❌ Failed (Has Elements in Red Zone):** 25 posters (25%)
- **Average Confidence:** 95.1%

### Source of Truth (SOT) Breakdown
All 100 posters were from the **"award"** SOT type:
- 25 failed (25.0% fail rate)
- 75 passed (75.0% pass rate)

---

## 📁 Files Generated

### 1. Analysis Results (JSON)
- **File:** `sot_analysis_100_posters.json`
- **Size:** 62,100 bytes
- **Format:** JSON array with full analysis data for each poster
- **Location:** `/Users/fchen/Code/content/`

### 2. Composite Images
- **Directory:** `debug_composite_images/`
- **Count:** 100 new images (117 total in directory)
- **Format:** PNG images with red zone overlay
- **Total Size:** ~654 MB for all images
- **Location:** `/Users/fchen/Code/content/debug_composite_images/`

Each composite image shows:
- Original poster image
- Red zone overlay (top 10% of image)
- Border highlighting the safe zone boundaries

### 3. Dashboard Database
- **File:** `red-zone-dashboard/red_zone_analysis.db`
- **Run ID:** 16
- **Tables Updated:**
  - `analysis_runs` - Analysis run metadata
  - `poster_results` - Individual poster results

---

## 🎯 Sample Results

### Failed Posters (Has Elements in Red Zone)
1. **Dead Heat on a Merry-Go-Round** (ID: 100007801) - 100% confidence
2. **Everybody Dance** (ID: 100008806) - 100% confidence
3. **Glory** (ID: 100003413) - 100% confidence
4. **The Seven Year Itch** (ID: 100006011) - 100% confidence
5. **A Farewell to Arms** (ID: 100008712) - 95% confidence

### Passing Posters (No Elements in Red Zone)
1. **The Producers** (ID: 100006508) - 100% confidence
2. **A Night to Remember** (ID: 100006408) - 95% confidence
3. **A Promise Kept: The Oksana Baiul Story** (ID: 100010164) - 95% confidence
4. **A Star Is Born** (ID: 100008713) - 95% confidence
5. **All Quiet on the Western Front** (ID: 100007563) - 95% confidence

---

## 🚀 How to View Results

### Option 1: Dashboard Web Interface

1. **Navigate to the dashboard directory:**
   ```bash
   cd /Users/fchen/Code/content/red-zone-dashboard
   ```

2. **Start the dashboard:**
   ```bash
   python3 dashboard.py
   ```
   or use the convenience script:
   ```bash
   ./restart_dashboard.sh
   ```

3. **Access the dashboard:**
   - Open browser to: http://localhost:5000
   - View the main dashboard with statistics
   - Browse individual poster results
   - Filter by pass/fail status
   - View composite images directly in the browser

### Option 2: Command Line Query

View statistics from the command line:
```bash
cd /Users/fchen/Code/content/red-zone-dashboard
python3 -c "
from database import AnalysisRun, PosterResult
import json

# Get run 16 details
run = AnalysisRun.get_by_id(16)
stats = PosterResult.get_stats(16)

print(json.dumps({
    'run': run,
    'stats': stats
}, indent=2, default=str))
"
```

### Option 3: Direct Database Access

```bash
cd /Users/fchen/Code/content/red-zone-dashboard
sqlite3 red_zone_analysis.db

# Example queries:
SELECT * FROM analysis_runs WHERE id = 16;
SELECT * FROM poster_results WHERE run_id = 16 LIMIT 10;
SELECT COUNT(*) as failed FROM poster_results WHERE run_id = 16 AND has_elements = 1;
```

---

## 📈 Key Insights

1. **High Confidence Results:** Average confidence of 95.1% indicates reliable analysis
2. **Award Category Performance:** 75% pass rate for award-winning titles
3. **Processing Efficiency:** 7.7 posters/minute throughput is suitable for production use
4. **Zero Errors:** 100% success rate with no processing failures

---

## 🔍 Next Steps

### To Analyze More Posters:
```bash
cd /Users/fchen/Code/content
python3 main.py analyze-eligible \
  --limit 500 \
  --json-array \
  --output sot_analysis_500_posters.json
```

### To Import Additional Results:
```bash
cd /Users/fchen/Code/content/red-zone-dashboard
python3 -c "
from database import import_json_results
from pathlib import Path

run_id = import_json_results(
    Path('../sot_analysis_500_posters.json'),
    description='Analysis of 500 SOT posters'
)
print(f'Imported as run {run_id}')
"
```

### To Filter by Specific SOT Types:
```bash
python3 main.py analyze-eligible \
  --limit 100 \
  --sot-type imdb \
  --sot-type rt \
  --json-array \
  --output sot_analysis_imdb_rt.json
```

---

## 📝 Technical Details

### Analysis Pipeline
- **Provider:** OpenAI GPT-4o-mini
- **Prompt:** Safe zone analysis prompt (built-in)
- **Red Zone Definition:** Top 10% of poster image
- **Image Processing:** 
  - Downloads images to base64
  - Adds red zone overlay to composite images
  - Maintains original aspect ratios

### Database Schema
- **analysis_runs:** Stores metadata about each analysis run
- **poster_results:** Individual poster results with full analysis data
- **Indexes:** Optimized for filtering by run_id, has_elements, sot_name

### File Locations
- Main codebase: `/Users/fchen/Code/content/`
- Dashboard: `/Users/fchen/Code/content/red-zone-dashboard/`
- Composite images: `/Users/fchen/Code/content/debug_composite_images/`
- Database: `/Users/fchen/Code/content/red-zone-dashboard/red_zone_analysis.db`

---

## ✅ Completion Checklist

- [x] Run safe zone analysis on 100 eligible SOT posters
- [x] Save composite images with red zone overlays
- [x] Generate JSON results file
- [x] Import results into dashboard database
- [x] Verify dashboard is populated with the run
- [x] Create summary documentation

---

**Analysis completed successfully on November 17, 2025 at 14:09 PST**

