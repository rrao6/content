# SOT Analysis Run Summary - 20 Posters

**Date**: November 17, 2025  
**Run ID**: 15  
**Status**: ✅ Complete

## Overview

Successfully analyzed 20 SOT eligible posters with enhanced progress tracking, saved composite debug images, and imported results into the dashboard.

## Results Summary

- **Total Analyzed**: 20 posters
- **Success Rate**: 100% (20/20)
- **Pass Rate**: 80% (16/20 have NO elements in red zone)
- **Fail Rate**: 20% (4/20 have elements in red zone)
- **Duration**: 3.1 minutes (184 seconds)
- **Average Time**: 9.2 seconds per poster
- **SOT Types**: award

## Enhanced Progress Tracking

The analysis pipeline now includes:

### 1. Initial Status Display
```
🎬 Starting SOT Analysis Pipeline
======================================================================
📅 Days back: 7
🎯 SOT types: ALL
📊 Limit: 20
💾 Save composite images: True
======================================================================
```

### 2. Real-time Progress Updates
- Percentage complete
- Success/error counts
- Processing rate (posters/minute)
- Estimated time remaining (ETA)

Example:
```
======================================================================
Progress: 10/20 (50.0% complete)
======================================================================
✅ Success: 9
❌ Errors:  1
⚡ Rate:    6.5 posters/minute
⏱️  ETA:     1.5 minutes (92 seconds)
======================================================================
```

### 3. Final Summary
```
======================================================================
✨ Analysis Complete!
======================================================================
📊 Total processed: 20
✅ Success: 20
❌ Errors: 0
⏱️  Duration: 3.1 minutes (184 seconds)
📈 Avg time per poster: 9.2 seconds
======================================================================
```

## Composite Images Saved

All 20 composite images (poster + red zone overlay) were saved to:
```
/Users/fchen/Code/content/debug_composite_images/
```

Files created:
- content_100000031.png - Rocky (FAIL - title in red zone)
- content_100000045.png - Moonlight (PASS)
- content_100000171.png - Bohemian Rhapsody
- content_100000218.png
- content_100000363.png
- content_100000783.png
- content_100000868.png
- content_100001489.png
- content_100002002.png
- content_100002087.png
- content_100002124.png
- content_100002156.png
- content_100002195.png
- content_100002270.png
- content_100002324.png
- content_100002410.png
- content_100002546.png
- content_100002549.png
- content_100002688.png
- content_100002769.png

## Dashboard Integration

Results successfully imported into dashboard database:

- **Database**: `red-zone-dashboard/red_zone_analysis.db`
- **Run ID**: 15
- **Description**: "SOT Analysis - 20 Eligible Posters (Enhanced Progress Tracking)"
- **View URL**: http://localhost:5000/results/15

## Sample Results

### Failed (Elements in Red Zone)

**Rocky (content_id: 100000031)**
- Confidence: 95%
- Justification: "The red safe zone contains the text 'ROCKY', which is likely the movie title, clearly visible and readable."
- Status: ❌ FAIL

### Passed (No Elements in Red Zone)

**Moonlight (content_id: 100000045)**
- Confidence: 95%
- Justification: "The red safe zone contains a portion of the background with no text or facial features visible, indicating a clear absence of key elements."
- Status: ✅ PASS

## Files Generated

1. **Analysis Results**: `sot_analysis_20_posters.json` (12.5 KB)
   - Complete JSON array with all 20 results
   - Includes analysis, confidence scores, justifications
   - Ready for import/export

2. **Composite Images**: 20 PNG files in `debug_composite_images/`
   - Original poster with red zone overlay
   - Visual verification of red zone placement
   - File sizes range from 1.1 MB to 6.9 MB

3. **Database Import**: Run #15 in dashboard database
   - 20 poster results stored
   - Filterable by status, SOT, search
   - Full analysis details preserved

## Code Enhancements Made

### 1. sot_pipeline.py
- Added initial status display with configuration
- Enhanced batch progress with percentage, rate, ETA
- Added final summary with duration and averages
- Composite image directory notification

### 2. main.py
- Enhanced CLI output with emojis and formatting
- Better progress messages during pipeline run
- File size reporting on save
- Improved results summary by SOT

## How to View Results

### Option 1: Dashboard (Recommended)

```bash
# Dashboard should already be running at:
http://localhost:5000

# Navigate to specific run:
http://localhost:5000/results/15

# Or view dashboard home for all runs:
http://localhost:5000
```

### Option 2: JSON File

```bash
# View raw JSON
cat sot_analysis_20_posters.json | python3 -m json.tool

# Count pass/fail
cat sot_analysis_20_posters.json | jq '[.[] | select(.analysis.red_safe_zone.contains_key_elements == true)] | length'
```

### Option 3: Composite Images

```bash
# View all composite images
open debug_composite_images/

# View specific image
open debug_composite_images/content_100000031.png
```

## Usage for Future Runs

### Run Another Analysis

```bash
# Analyze more posters (e.g., 50)
python3 main.py analyze-eligible \
  --days-back 7 \
  --limit 50 \
  --json-array \
  --output sot_analysis_50_posters.json

# Import to dashboard
cd red-zone-dashboard
python3 -c "from database import import_json_results; from pathlib import Path; \
import_json_results(Path('../sot_analysis_50_posters.json'), 'SOT Analysis - 50 Posters')"
```

### Analyze Specific SOT Types

```bash
# See available SOT types
python3 main.py eligible-titles --days-back 7

# Analyze specific types
python3 main.py analyze-eligible \
  --days-back 30 \
  --sot-type just_added \
  --sot-type most_popular \
  --limit 100 \
  --json-array \
  --output specific_sot.json
```

## Performance Metrics

- **Throughput**: ~6.5 posters per minute
- **Average Analysis Time**: 9.2 seconds per poster
- **Success Rate**: 100% (no errors)
- **Network Performance**: All images downloaded successfully
- **OpenAI API**: All 20 calls successful (95% confidence on 19, 90% on 1)

## Next Steps

1. ✅ Analysis complete
2. ✅ Composite images saved
3. ✅ Results imported to dashboard
4. ✅ Dashboard running
5. 📊 **View results at http://localhost:5000/results/15**
6. 🔍 Review composite images in `debug_composite_images/`
7. 📈 Analyze patterns in failed posters
8. 🚀 Run larger batches if needed

## Technical Details

**Command Used**:
```bash
python3 main.py analyze-eligible \
  --days-back 7 \
  --limit 20 \
  --json-array \
  --output sot_analysis_20_posters.json
```

**Configuration**:
- Days back: 7
- Batch size: 100 (default)
- Download images: Yes
- Download timeout: 20 seconds
- Save composite images: Yes
- Composite directory: ./debug_composite_images
- Resume from checkpoint: No

**Environment**:
- Python: 3.9
- OpenAI Model: gpt-4o
- Databricks: tubi-dev.cloud.databricks.com
- Vision API Rate Limit: 30 requests/minute

## Success Indicators

✅ All 20 posters analyzed successfully  
✅ All images downloaded without errors  
✅ All composite images saved  
✅ All OpenAI API calls succeeded  
✅ Results file created (12.5 KB)  
✅ Dashboard import successful  
✅ Enhanced progress tracking working  
✅ No timeout or network errors  

---

**Generated**: November 17, 2025  
**System**: SOT Poster Analysis Pipeline v1.0  
**Status**: Ready for Production Use

