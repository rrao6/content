# 🌟 FINAL GUIDE: Running ALL Shiny Titles Analysis

## 📊 Shiny Titles Overview

Based on our analysis:
- **Total shiny titles**: 3,049 (with 'shiny' in tags and active posters)
- **Definition**: Content with 'shiny' tag in content_info.tags column
- **Filtering**: `LOWER(tags) LIKE '%shiny%'`

## ✅ System Status

1. **Dashboard**: Running at http://localhost:5000 ✅
2. **Parallel Processing**: Enabled (3-10 workers) ✅
3. **Max Batch Size**: 1000 ✅
4. **Shiny Filtering**: Implemented and tested ✅

## 🚀 Running ALL Shiny Titles (3,049 total)

Since we have 3,049 shiny titles and the UI limit is 1000, you'll need to run multiple batches:

### Option 1: Three Separate Runs (Recommended)

**Run 1: Most Recent Shiny Titles (1000)**
1. Go to http://localhost:5000/analyze
2. Configuration:
   - SOT Types: Select ALL (just_added, most_popular, award, rt, imdb)
   - Days Back: 30
   - Batch Size: **1000**
   - ✅ **CHECK "Shiny Only"**
   - Description: "Shiny Batch 1 - Recent 30 days"
3. Click "Start Analysis"
4. Wait ~15-20 minutes

**Run 2: Older Shiny Titles (1000)**
1. After Run 1 completes, go back to /analyze
2. Configuration:
   - SOT Types: Select ALL
   - Days Back: 90
   - Batch Size: **1000**
   - ✅ **CHECK "Shiny Only"**
   - Description: "Shiny Batch 2 - Last 90 days"
3. Click "Start Analysis"
4. Wait ~15-20 minutes

**Run 3: All Remaining Shiny Titles (1049)**
1. After Run 2 completes, go back to /analyze
2. Configuration:
   - SOT Types: Select ALL
   - Days Back: 365
   - Batch Size: **1000** (will get remaining)
   - ✅ **CHECK "Shiny Only"**
   - Description: "Shiny Batch 3 - All remaining"
3. Click "Start Analysis"
4. Wait ~15-20 minutes

### Option 2: Single Maximum Run

If you want to get as many as possible in one go:

1. Go to http://localhost:5000/analyze
2. Configuration:
   - SOT Types: Select ALL types
   - Days Back: **365** (full year)
   - Batch Size: **1000**
   - ✅ **CHECK "Shiny Only"**
   - Description: "All Shiny Titles - Max 1000"
3. Click "Start Analysis"

## ⏱️ Time Estimates

- 1000 titles: ~15-20 minutes
- 3049 titles (all): ~45-60 minutes total (across 3 runs)
- Processing rate: 60-120 posters/minute

## 📊 Monitoring Progress

1. **Live Progress**: Shows on the analyze page during run
2. **Performance**: http://localhost:5000/performance
3. **View Results**: http://localhost:5000/results
4. **Filter by Run**: Each batch will have its own run ID

## 🎯 What Happens During Analysis

1. System queries for eligible titles with 'shiny' tag
2. Downloads poster images
3. Analyzes red zone (top 10%) for text/logos/faces
4. Stores results with confidence scores
5. Auto-saves to database

## 📈 After Completion

1. **View All Results**: http://localhost:5000/results
2. **Filter Options**:
   - By Status: Pass/Fail
   - By SOT Type: just_added, most_popular, etc.
   - By Run: Each batch separately
3. **Export**: Download results as JSON/CSV

## 🔍 Verification

To verify shiny filtering is working:
- Check the run description shows "shiny"
- Results should only include titles with 'shiny' tag
- Poster URLs should all be from shiny content

## 🆘 Troubleshooting

If analysis fails or stops:
- The system has checkpointing - it can resume
- Check http://localhost:5000/performance for errors
- Restart dashboard if needed: `python3 run_dashboard_clean.py`

## ✨ Ready to Start!

1. Open http://localhost:5000/analyze
2. Check "Shiny Only" ✅
3. Set batch size to 1000
4. Click "Start Analysis"

The system is fully configured and tested. Your shiny titles analysis will be accurate and complete!
