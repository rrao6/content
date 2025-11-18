# SOT Poster Analysis System

A comprehensive system for analyzing movie posters from Sources of Truth (SOT) to detect if key elements fall within the "red zone" safe area guidelines.

## Table of Contents
- [Overview](#overview)
- [Quick Start](#quick-start)
- [Complete Step-by-Step Guide](#complete-step-by-step-guide)
- [Advanced Usage](#advanced-usage)
- [Data Flow](#data-flow)
- [Troubleshooting](#troubleshooting)
- [Quick Reference](#quick-reference)

## Overview

This system integrates:
- **Databricks**: Sources content metadata and poster URLs from SOT tables
- **OpenAI Vision API**: Analyzes posters for red zone compliance
- **Dashboard**: Web interface for viewing and filtering analysis results

## Quick Start

```bash
# 1. Set up environment
cp .env.example .env  # Edit with your credentials

# 2. Initialize dashboard database
cd red-zone-dashboard
python database.py

# 3. Run analysis (shows individual progress: 1/50, 2/50, etc.)
cd ..
python main.py analyze-eligible --days-back 7 --limit 50 --json-array --output results.json

# 4. Import to dashboard
cd red-zone-dashboard
python -c "from database import import_json_results; from pathlib import Path; \
run_id = import_json_results(Path('../results.json'), 'SOT Analysis'); \
print(f'View at: http://localhost:5000/results/{run_id}')"

# 5. Start dashboard
python dashboard.py
# Open http://localhost:5000
```

**✨ NEW**: Real-time individual progress tracking! See "1/50, 2/50, 3/50..." with pass/fail results, confidence scores, and ETA for each poster as it's analyzed.

## Complete Step-by-Step Guide

### Step 1: Set Up Your Environment

Create or update your `.env` file in the root directory with the required credentials:

```bash
# Databricks Configuration
DATABRICKS_HOST=tubi-dev.cloud.databricks.com
DATABRICKS_HTTP_PATH=/sql/1.0/warehouses/34148fb208740945
DATABRICKS_TOKEN=<your-personal-access-token>
DATABRICKS_CATALOG=core_prod
DATABRICKS_SCHEMA=tubidw
DATABRICKS_CONTENT_TABLE=content_info

# OpenAI Configuration
OPENAI_API_KEY=<your-openai-api-key>
OPENAI_MODEL=gpt-4o

# Optional: Performance Tuning
VISION_REQUESTS_PER_MINUTE=30
VISION_REQUEST_DELAY_MS=100
ENABLE_ANALYSIS_CACHE=true
CACHE_EXPIRY_HOURS=24
```

### Step 2: Initialize the Dashboard Database

```bash
cd red-zone-dashboard
python database.py
```

This creates `red_zone_analysis.db` with the proper schema for storing analysis runs and results.

### Step 3: Run SOT Analysis

You have **two main approaches**:

#### Option A: Using CLI Command (Recommended)

From the root directory (`/Users/fchen/Code/content/`):

```bash
# Analyze SOT eligible posters with output saved to file
python main.py analyze-eligible \
  --days-back 7 \
  --sot-type just_added \
  --sot-type most_popular \
  --limit 50 \
  --json-array \
  --output sot_analysis_results.json
```

**Key Parameters:**
- `--days-back 7`: Look at eligible titles from the last 7 days
- `--sot-type`: Specify which Sources of Truth to analyze (can specify multiple)
- `--limit 50`: Analyze first 50 eligible posters
- `--json-array`: Output as JSON array (easier to import)
- `--output`: Save results to file

**What This Does:**
- Queries Databricks for eligible titles from SOT
- Downloads poster images
- Analyzes them with OpenAI Vision API
- Saves composite debug images to `./debug_composite_images/`
- Outputs results to `sot_analysis_results.json`

#### Option B: Using Production Integration Script

From the `red-zone-dashboard` directory:

```bash
cd red-zone-dashboard
python production_integration.py
```

**What This Does:**
- Tests Databricks connection
- Fetches eligible titles
- Runs analysis
- **Automatically imports results into the dashboard database**
- Returns a run ID for immediate viewing

### Step 4: Import Results into Dashboard

**(Only needed if using Option A - skip if using Option B)**

#### Via Command Line:
```bash
cd red-zone-dashboard
python -c "from database import import_json_results; from pathlib import Path; \
run_id = import_json_results(Path('../sot_analysis_results.json'), \
'SOT Analysis - Just Added & Most Popular'); \
print(f'Imported as run ID: {run_id}')"
```

#### Via Dashboard UI:
1. Start the dashboard (see Step 5)
2. Navigate to http://localhost:5000/import
3. Upload your `sot_analysis_results.json` file
4. Click "Import Results"

### Step 5: Start the Dashboard

```bash
cd red-zone-dashboard
python dashboard.py
```

The dashboard will start at **http://localhost:5000**

### Step 6: View Your Results

1. **Dashboard Home** (`/`): 
   - Overview with statistics
   - Pass/fail rates by SOT type
   - Recent analysis runs

2. **Results Page** (`/results/<run_id>`): 
   - Grid view of all analyzed posters
   - Filter by pass/fail status
   - Filter by SOT type
   - Search by title
   - Click any poster for details

3. **Detail View** (`/detail/<result_id>`):
   - Individual poster with red zone overlay
   - Analysis justification
   - Confidence score
   - SOT information

## Advanced Usage

### View Available SOT Types

To see which SOT types are available and their eligible title counts:

```bash
python main.py eligible-titles --days-back 7
```

Output example:
```
Eligible Titles Summary (last 7 days):
--------------------------------------------------
just_added          1,234 titles
most_popular          856 titles
trending              432 titles
--------------------------------------------------
TOTAL               2,522 titles
```

### Analyze All SOT Types

```bash
python main.py analyze-eligible \
  --days-back 7 \
  --limit 100 \
  --json-array \
  --output all_sot_analysis.json
```

### Enable Composite Image Debugging

The analysis automatically saves composite images (poster + red zone overlay) to `debug_composite_images/` directory. These help you verify the red zone detection visually.

```bash
# Composite images are saved by default when using analyze-eligible
# They're saved as: debug_composite_images/content_<content_id>.png
```

### Export Results from Dashboard

```bash
# Export a specific run
curl http://localhost:5000/export/<run_id> > exported_results.json
```

### Monitor Analysis Progress

The system now shows **individual item progress** in real-time! You'll see progress for each poster as it's analyzed:

```
🔄 Processing 1/20 (5.0%) - Rocky (ID: 100000031)
   ❌ FAIL (confidence: 95%) | Rate: 6.0/min | ETA: 190s

🔄 Processing 2/20 (10.0%) - Moonlight (ID: 100000045)
   ✅ PASS (confidence: 95%) | Rate: 5.8/min | ETA: 186s

🔄 Processing 3/20 (15.0%) - Bohemian Rhapsody (ID: 100000171)
   ✅ PASS (confidence: 95%) | Rate: 5.9/min | ETA: 173s
```

**Each line shows:**
- Current progress (e.g., "3/20" = processing item 3 of 20)
- Percentage complete (e.g., "15.0%")
- Movie name and content ID
- Instant result (✅ PASS or ❌ FAIL)
- Confidence score
- Current processing rate (posters/minute)
- Estimated time remaining (seconds)

Works with any limit - whether you're processing 5, 20, 50, or 100 posters!

### Check System Health

Before running large analyses:

```bash
python main.py health
```

This verifies:
- Databricks connection
- OpenAI API configuration
- Cache status
- Monitoring system

Output example:
```json
{
  "databricks": "ok",
  "cache": "ok (size: 45/1000)",
  "openai": "configured",
  "monitoring": "healthy (alerts: 0)",
  "overall": "healthy"
}
```

### Resume Failed Runs

If an analysis is interrupted, it uses checkpoints to automatically resume:

```bash
# The pipeline automatically resumes if sot_analysis_checkpoint.json exists
python main.py analyze-eligible --limit 100 --output results.json
```

The checkpoint tracks:
- Processed content IDs
- Success/error counts
- Processing rate
- Errors by content ID

### Batch Processing Options

```bash
# Adjust batch size for performance
python main.py analyze-eligible --batch-size 200 --limit 1000

# Increase download timeout for slow networks
python main.py analyze-eligible --download-timeout 60

# Use different output format (NDJSON)
python main.py analyze-eligible --limit 100 --output results.jsonl
```

## Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Databricks SOT Tables                                    │
│    - just_added, most_popular, trending, etc.               │
└──────────────────────┬──────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. EligibleTitlesService (sot_repository.py)                │
│    - Queries eligible titles from SOT tables                │
│    - Filters by days_back and sot_types                     │
└──────────────────────┬──────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. ContentService (service.py)                              │
│    - Fetches poster URLs from content_info                  │
│    - Downloads and converts images to base64                │
└──────────────────────┬──────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────────┐
│ 4. SOTAnalysisPipeline (sot_pipeline.py)                    │
│    - SafeZoneAnalyzer calls OpenAI Vision API               │
│    - Creates composite debug images with overlay            │
│    - Checkpointing for resumable processing                 │
└──────────────────────┬──────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────────┐
│ 5. Results JSON File                                        │
│    - Contains analysis results for each poster              │
│    - Red zone analysis with confidence scores               │
└──────────────────────┬──────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────────┐
│ 6. Dashboard Database (red_zone_analysis.db)                │
│    - analysis_runs: metadata about each run                 │
│    - poster_results: individual poster results              │
└──────────────────────┬──────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────────┐
│ 7. Dashboard Web UI (dashboard.py)                          │
│    - Visual display with filtering                          │
│    - Search and drill-down capabilities                     │
│    - Export functionality                                   │
└─────────────────────────────────────────────────────────────┘
```

## Understanding Analysis Results

Each poster analysis includes:

```json
{
  "content_id": 123456,
  "program_id": 654321,
  "content_name": "Example Movie",
  "content_type": "movie",
  "sot_name": "just_added",
  "poster_img_url": "https://...",
  "analysis": {
    "red_safe_zone": {
      "contains_key_elements": true,     // FAIL if true, PASS if false
      "confidence": 95,                  // 0-100 confidence score
      "justification": "The movie title and main actor's face are positioned in the red zone...",
      "detected_elements": [
        "Title text",
        "Actor's face",
        "Logo"
      ]
    }
  },
  "error": null
}
```

**Status Interpretation:**
- `contains_key_elements: false` → **PASS** (no key elements in red zone)
- `contains_key_elements: true` → **FAIL** (key elements detected in red zone)

**Confidence Levels:**
- 90-100: High confidence
- 60-89: Medium confidence
- 0-59: Low confidence

## Troubleshooting

### No Eligible Titles Found
**Problem**: `✅ Found 0 eligible titles`

**Solutions:**
- Increase `--days-back` value (try 30 or 60)
- Check available SOT types: `python main.py eligible-titles`
- Verify Databricks connection: `python main.py health`
- Check SOT table data directly in Databricks

### Analysis Errors
**Problem**: High error rate during analysis

**Solutions:**
- Check OpenAI API key validity and quota: `echo $OPENAI_API_KEY`
- Verify poster URLs are accessible (check one manually)
- Increase `--download-timeout` if network is slow: `--download-timeout 60`
- Check recent errors: `python main.py metrics`

### Dashboard Shows No Results
**Problem**: Dashboard is empty after import

**Solutions:**
- Verify import completed: Check console output for run_id
- Confirm database exists: `ls red-zone-dashboard/red_zone_analysis.db`
- Check dashboard logs for errors when starting
- Verify JSON file format matches expected schema

### Images Not Displaying
**Problem**: Poster images don't load in dashboard

**Solutions:**
- Dashboard proxies images through `/poster-image?url=...`
- Verify poster URLs are HTTPS (HTTP may have CORS issues)
- Check composite images saved: `ls debug_composite_images/`
- Try restarting dashboard with: `python dashboard.py`

### Import Failures
**Problem**: JSON import fails with format errors

**Solutions:**
```bash
# Validate JSON format
python -c "import json; json.load(open('results.json'))"

# Check expected format
cat examples/analysis_sample.jsonl

# View existing exports for reference
ls red-zone-dashboard/uploads/
```

### Connection Issues
**Problem**: Cannot connect to Databricks

**Solutions:**
```bash
# Test connection
python main.py health

# Verify environment variables
env | grep DATABRICKS

# Test with simple query
python -c "from connection import get_cursor; \
with get_cursor() as c: c.execute('SELECT 1'); print('OK')"
```

### Performance Issues
**Problem**: Analysis is very slow

**Solutions:**
```bash
# Increase batch size
--batch-size 200

# Use caching
export ENABLE_ANALYSIS_CACHE=true

# Run smaller batches with limit
--limit 50

# Check system resources
python main.py metrics
```

## Quick Reference

### Common Commands

```bash
# See eligible titles count by SOT
python main.py eligible-titles --days-back 7

# Run small test analysis (10 posters)
python main.py analyze-eligible --limit 10 --json-array --output test.json

# Full production run (500 posters, 30 days back)
python main.py analyze-eligible --days-back 30 --limit 500 --output production.json

# Specific SOT types only
python main.py analyze-eligible \
  --sot-type just_added \
  --sot-type most_popular \
  --limit 100 \
  --output specific_sot.json

# Import to dashboard
cd red-zone-dashboard
python -c "from database import import_json_results; from pathlib import Path; \
run_id = import_json_results(Path('../production.json'), 'Production Run'); \
print(f'Run ID: {run_id}')"

# Start dashboard
python dashboard.py

# Check system health
python main.py health

# View metrics
python main.py metrics

# Export from dashboard
curl http://localhost:5000/export/<run_id> > export.json
```

### File Locations

```
/Users/fchen/Code/content/
├── .env                           # Environment configuration
├── main.py                        # CLI entry point
├── sot_pipeline.py                # SOT analysis pipeline
├── sot_repository.py              # SOT data access
├── analysis.py                    # OpenAI Vision analysis
├── service.py                     # Content services
├── debug_composite_images/        # Debug images with overlays
├── sot_analysis_checkpoint.json   # Resume checkpoint (auto-created)
└── red-zone-dashboard/
    ├── dashboard.py               # Web dashboard
    ├── database.py                # Database schema & operations
    ├── red_zone_analysis.db       # SQLite database
    ├── production_integration.py  # Automated integration script
    ├── uploads/                   # Imported JSON files
    └── exports/                   # Exported results
```

### API Endpoints (When Dashboard is Running)

```
GET  /                          - Dashboard home with statistics
GET  /results/<run_id>          - View results for a specific run
GET  /detail/<result_id>        - View detailed poster analysis
GET  /import                    - Import page
POST /import                    - Upload and import JSON results
GET  /export/<run_id>           - Export results as JSON
GET  /poster-image?url=<url>    - Proxy poster image (CORS bypass)

# API Endpoints
GET  /api/runs                  - List all analysis runs
GET  /api/results?run_id=X      - Get results with filters
GET  /api/stats/trending        - Get trending statistics
```

## Project Structure

```
.
├── Core Analysis
│   ├── sot_pipeline.py         # Main SOT analysis pipeline
│   ├── sot_repository.py       # SOT data access layer
│   ├── service.py              # Content services
│   ├── analysis.py             # OpenAI Vision integration
│   └── main.py                 # CLI interface
│
├── Dashboard
│   ├── dashboard.py            # Flask web application
│   ├── database.py             # SQLite database operations
│   ├── templates/              # HTML templates
│   └── static/                 # CSS, JS, images
│
├── Configuration
│   ├── config.py               # Configuration management
│   ├── connection.py           # Databricks connection
│   └── .env                    # Environment variables
│
└── Supporting
    ├── monitoring.py           # Health checks and metrics
    ├── cache.py                # Result caching
    └── exceptions.py           # Custom exceptions
```

## Additional Resources

- **PRODUCTION_GUIDE.md**: Detailed production deployment guide
- **COMPOSITE_IMAGES_GUIDE.md**: Understanding debug composite images
- **examples/**: Sample JSON files for reference
- **red-zone-dashboard/README.md**: Dashboard-specific documentation

## Support

For issues or questions:
1. Check this README's troubleshooting section
2. Review the production guide: `PRODUCTION_GUIDE.md`
3. Check recent issues in the repository
4. Contact the development team

## License

Copyright 2025 Tubi. All rights reserved.

