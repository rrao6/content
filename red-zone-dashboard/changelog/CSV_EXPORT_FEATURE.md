# CSV Export Feature

**Date:** November 18, 2025  
**Status:** ✅ Completed

## Overview

Added CSV export functionality to the Red Zone Dashboard, allowing users to export analysis results in a tabular format that's easy to work with in Excel, Google Sheets, or other data analysis tools.

## Changes Made

### 1. Backend Implementation (`dashboard.py`)

Added a new export route `/export/csv/<int:run_id>` that:
- Retrieves analysis run data and results from the database
- Generates a CSV file in memory using Python's `csv` module
- Returns the CSV as a downloadable file with proper headers

**Key Features:**
- Binary `sot_label` field: "pass" or "fail" (converted from `has_elements` boolean)
- All requested fields included
- Proper CSV formatting with escaped special characters
- Timestamp-based filename for uniqueness

### 2. CSV Structure

The exported CSV includes the following columns:

| Column Name | Description | Source |
|-------------|-------------|--------|
| `content_id` | Unique content identifier | Database |
| `program_id` | Program identifier | Database |
| `title` | Content title/name | Database |
| `content_type` | Type (MOVIE/SERIES) | Database |
| `sot_name` | Source of Truth name (e.g., "rt", "just_added") | Database |
| `poster_url` | Full URL to the Adrise poster image | Database |
| `sot_label` | Binary pass/fail result | Computed from `has_elements` |
| `confidence` | AI confidence score (0-100) | Database |
| `explanation` | GPT justification for the result | Database (justification field) |
| `analysis_date` | When the analysis was performed | Database |
| `run_id` | Analysis run identifier | Database |

### 3. Frontend Updates

#### `results.html`
- Added green "Export CSV" button alongside PDF and JSON buttons
- Button uses Font Awesome icon `fa-file-csv`
- Styled with Tailwind CSS for consistency
- Positioned between PDF and JSON export buttons

#### `dashboard.html`
- Added CSV export icon to the recent runs table
- Icon appears in the Actions column alongside PDF and JSON icons
- Green color scheme to distinguish from other export types
- Tooltip shows "Export CSV" on hover

## Technical Details

### Code Changes

**`dashboard.py`:**
```python
# Added imports
import csv
from io import StringIO

# New route
@app.route('/export/csv/<int:run_id>')
def export_run_csv(run_id):
    """Export results as CSV."""
    # ... implementation
```

**CSV Generation Logic:**
- Uses `StringIO` for in-memory CSV creation (no temporary files)
- Proper CSV escaping for fields with commas, quotes, and newlines
- Efficient streaming response for large datasets

### File Naming Convention

CSV files are named using the pattern:
```
red_zone_analysis_run_{run_id}_{timestamp}.csv
```

Example: `red_zone_analysis_run_17_20251118_143225.csv`

## Testing

Successfully tested with Run #17 (200 results):
- ✅ All fields properly exported
- ✅ CSV formatting correct
- ✅ Pass/fail labels accurate
- ✅ File download works in browser
- ✅ Special characters properly escaped
- ✅ Opens correctly in Excel and Google Sheets

## Usage

### From Results Page
1. Navigate to any analysis run results page
2. Scroll to the bottom
3. Click the green "Export CSV" button
4. CSV file downloads automatically

### From Dashboard
1. Go to the main dashboard
2. Find the desired run in "Recent Analysis Runs" table
3. Click the green CSV icon in the Actions column
4. CSV file downloads automatically

### API Endpoint
```
GET /export/csv/<run_id>
```

**Example:**
```bash
curl -O http://localhost:5000/export/csv/17
```

## Benefits

1. **Spreadsheet Compatibility:** Easy to open in Excel, Google Sheets, Numbers
2. **Data Analysis:** Simple to import into pandas, R, or other analysis tools
3. **Reporting:** Can be used for automated reports and dashboards
4. **Integration:** Easy to integrate with other systems via CSV import
5. **Human Readable:** Clear column names and simple format
6. **Lightweight:** Much smaller file size compared to JSON or PDF

## Example CSV Output

```csv
content_id,program_id,title,content_type,sot_name,poster_url,sot_label,confidence,explanation,analysis_date,run_id
100002005,100002005,Broken Embraces,MOVIE,rt,http://img.adrise.tv/a1e9d73f-06ea-4c75-8400-d2e33291afd6.jpg,fail,100,"The red safe zone contains text elements...",2025-11-17 15:39:32,17
100000441,100000441,Gremlins,MOVIE,rt,http://img.adrise.tv/fc6021eb-3119-4c2a-b6be-85d8949dc6e9.jpg,pass,100,The red safe zone is empty and does not contain any key visual elements.,2025-11-17 15:39:32,17
```

## Future Enhancements (Optional)

Possible improvements for the future:
- [ ] Add filter options (export only pass/fail results)
- [ ] Include additional metadata (image dimensions, zone coordinates)
- [ ] Support for custom column selection
- [ ] Excel format (.xlsx) export with formatting
- [ ] Scheduled automatic exports

## Files Modified

1. `/red-zone-dashboard/dashboard.py` - Added CSV export route and imports
2. `/red-zone-dashboard/templates/results.html` - Added CSV export button
3. `/red-zone-dashboard/templates/dashboard.html` - Added CSV export icon

## Compatibility

- ✅ Works with all existing analysis runs
- ✅ Compatible with filtered results
- ✅ No database schema changes required
- ✅ Backward compatible with existing exports

## Conclusion

The CSV export feature is now fully functional and available in both the results page and the main dashboard. Users can easily export analysis data in a format that's universally compatible with spreadsheet and data analysis tools.

