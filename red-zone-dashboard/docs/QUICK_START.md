# Red Zone Dashboard - Quick Start Guide

## 🚀 Start the Dashboard

```bash
cd /Users/fchen/Code/content/red-zone-dashboard
python3 dashboard.py
```

Then open your browser to: **http://localhost:5000**

## 📊 Latest Run (Run ID: 16)

- **Date:** November 17, 2025
- **Posters Analyzed:** 100
- **Source:** Award-winning titles from SOT
- **Pass Rate:** 75% (75 passed, 25 failed)
- **Average Confidence:** 95.1%

## 🔍 Quick Views

### Main Dashboard
- http://localhost:5000/
- Shows overall statistics and recent runs

### Browse All Results from Run 16
- http://localhost:5000/results?run_id=16

### View Only Failed Posters (has elements in red zone)
- http://localhost:5000/results?run_id=16&filter=fail

### View Only Passing Posters (no elements in red zone)
- http://localhost:5000/results?run_id=16&filter=pass

### View Individual Poster Details
- http://localhost:5000/poster/<content_id>
- Example: http://localhost:5000/poster/100000031

## 📁 Composite Images

All composite images are stored in:
```
/Users/fchen/Code/content/debug_composite_images/
```

Each image shows the poster with a red overlay on the top 10% (red zone).

## 🔧 Useful Commands

### Check Database Status
```bash
cd /Users/fchen/Code/content/red-zone-dashboard
sqlite3 red_zone_analysis.db "SELECT COUNT(*) FROM poster_results WHERE run_id = 16;"
```

### Export Run Results
```bash
curl http://localhost:5000/api/export/16 -o run_16_export.json
```

### View Latest Statistics
```bash
python3 -c "from database import PosterResult; import json; print(json.dumps(PosterResult.get_stats(16), indent=2))"
```

## 📝 Features Available

✅ View analysis runs  
✅ Browse poster results with thumbnails  
✅ Filter by pass/fail status  
✅ Search by title or content  
✅ View detailed analysis for each poster  
✅ Display composite images with red zone overlay  
✅ Export results as JSON  
✅ View trends over time  
✅ SOT-specific statistics  

## 🎯 Sample Failed Posters to Review

1. Glory (100003413) - 100% confidence
2. Dead Heat on a Merry-Go-Round (100007801) - 100% confidence
3. Everybody Dance (100008806) - 100% confidence
4. The Seven Year Itch (100006011) - 100% confidence

## 📞 Need Help?

- Main documentation: `/Users/fchen/Code/content/red-zone-dashboard/README.md`
- Full analysis report: `/Users/fchen/Code/content/ANALYSIS_RUN_100_SOT_POSTERS.md`
- System guide: `/Users/fchen/Code/content/README.md`

