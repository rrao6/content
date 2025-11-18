# Dynamic Pass/Fail Counts Fix

**Date:** November 18, 2025  
**Status:** ✅ Fixed

## Problem

When QA-editing poster labels (changing PASS to FAIL or vice versa), the pass/fail counts displayed on the dashboard and results pages were not updating. The counts remained static, showing the original AI analysis numbers even after human corrections.

## Root Cause

The `analysis_runs` table stored `pass_count` and `fail_count` as static values when the run was initially created. When users updated poster statuses via QA editing:

1. ✅ The `has_elements` field in `poster_results` was updated correctly
2. ❌ The `pass_count` and `fail_count` in `analysis_runs` remained unchanged
3. ❌ Dashboard and results pages displayed the outdated static counts

## Solution

Changed from **static stored counts** to **dynamically calculated counts** by modifying the database query methods to:

1. Join `analysis_runs` with `poster_results`
2. Calculate current pass/fail counts from actual poster data
3. Override stored counts with real-time counts

## Implementation

### Modified Methods in `database.py`

#### 1. `AnalysisRun.get_all()`
**Before:**
```python
SELECT * FROM analysis_runs 
ORDER BY id DESC LIMIT ?
```

**After:**
```python
SELECT 
    ar.*,
    COUNT(pr.id) as current_total,
    SUM(CASE WHEN pr.has_elements = 0 THEN 1 ELSE 0 END) as current_pass_count,
    SUM(CASE WHEN pr.has_elements = 1 THEN 1 ELSE 0 END) as current_fail_count
FROM analysis_runs ar
LEFT JOIN poster_results pr ON ar.id = pr.run_id
GROUP BY ar.id
ORDER BY ar.id DESC LIMIT ?
```

#### 2. `AnalysisRun.get_by_id()`
**Before:**
```python
SELECT * FROM analysis_runs WHERE id = ?
```

**After:**
```python
SELECT 
    ar.*,
    COUNT(pr.id) as current_total,
    SUM(CASE WHEN pr.has_elements = 0 THEN 1 ELSE 0 END) as current_pass_count,
    SUM(CASE WHEN pr.has_elements = 1 THEN 1 ELSE 0 END) as current_fail_count
FROM analysis_runs ar
LEFT JOIN poster_results pr ON ar.id = pr.run_id
WHERE ar.id = ?
GROUP BY ar.id
```

#### 3. `AnalysisRun.get_latest()`
**Before:**
```python
SELECT * FROM analysis_runs ORDER BY id DESC LIMIT 1
```

**After:**
```python
SELECT 
    ar.*,
    COUNT(pr.id) as current_total,
    SUM(CASE WHEN pr.has_elements = 0 THEN 1 ELSE 0 END) as current_pass_count,
    SUM(CASE WHEN pr.has_elements = 1 THEN 1 ELSE 0 END) as current_fail_count
FROM analysis_runs ar
LEFT JOIN poster_results pr ON ar.id = pr.run_id
WHERE ar.id = (SELECT id FROM analysis_runs ORDER BY id DESC LIMIT 1)
GROUP BY ar.id
```

### Count Override Logic

After fetching the data, we override the stored counts with current counts:

```python
result = dict(row)
result['total_analyzed'] = result['current_total']
result['pass_count'] = result['current_pass_count']
result['fail_count'] = result['current_fail_count']
```

## Where Counts Are Now Updated

### 1. Dashboard Homepage (`/`)
- **Total Analyzed** - Dynamic count
- **Pass Count** - Dynamic from current poster statuses
- **Fail Count** - Dynamic from current poster statuses
- **Recent Runs Table** - All rows show current counts

### 2. Results Page (`/results/<run_id>`)
- **Stats Bar** at top:
  - Total: Current count
  - Pass: Current count (green)
  - Fail: Current count (red)

### 3. Run Details
- Any API or page that calls `AnalysisRun.get_by_id()` now gets current counts

## Benefits

### ✅ Real-Time Accuracy
Counts always reflect the current state of poster labels, including all QA modifications.

### ✅ Ground Truth Tracking
See actual curated dataset statistics as you review posters.

### ✅ Progress Monitoring
Track how many posters you've corrected by watching counts change.

### ✅ No Manual Refresh Needed
Simply refresh the page - counts are calculated on every load.

## Example Workflow

### Before Fix:
```
1. Initial analysis: 150 PASS, 50 FAIL
2. QA review: Change 10 FAIL → PASS
3. Dashboard still shows: 150 PASS, 50 FAIL ❌
```

### After Fix:
```
1. Initial analysis: 150 PASS, 50 FAIL
2. QA review: Change 10 FAIL → PASS
3. Dashboard now shows: 160 PASS, 40 FAIL ✅
```

## Performance Considerations

### Query Complexity
- Added JOIN and GROUP BY operations
- Minimal performance impact for typical dataset sizes (< 1000 posters per run)
- Results are not cached - calculated on each page load

### Optimization Notes
- `LEFT JOIN` ensures runs with 0 results still appear
- Indexed columns used for JOIN (`run_id`)
- SUM with CASE is efficient in SQLite

### If Performance Becomes an Issue (Future)
Could add optional caching:
```python
# Cache counts for 1 minute
@lru_cache(maxsize=100, ttl=60)
def get_run_counts(run_id):
    # ... calculate counts ...
```

But current implementation should be fine for production use.

## Testing

### Manual Testing Steps

1. **View Initial Counts**
   - Go to dashboard: http://localhost:5000
   - Note pass/fail counts for Run #17

2. **Edit a Poster**
   - Click on a FAIL poster
   - Click "Edit QA"
   - Change to PASS
   - Save changes

3. **Verify Update**
   - Return to dashboard
   - Refresh page
   - Pass count should increase by 1
   - Fail count should decrease by 1

4. **Check Results Page**
   - Go to results page for run
   - Stats bar should show updated counts

### Expected Behavior

| Action | Pass Count | Fail Count |
|--------|------------|------------|
| Initial (Run #17) | ~50 | ~150 |
| Change 1 FAIL → PASS | 51 | 149 |
| Change 1 PASS → FAIL | 50 | 150 |
| Change 5 FAIL → PASS | 55 | 145 |

## Edge Cases Handled

### Run with 0 Results
- `LEFT JOIN` ensures run appears with 0/0/0 counts
- No division by zero errors

### Newly Created Runs
- Initially stored counts match calculated counts
- As QA progresses, counts diverge appropriately

### Concurrent QA Edits
- Each page load recalculates from database
- No stale data issues

### Filtered Views
- Filters don't affect count calculations
- Counts always reflect full run, not filtered subset

## Database Schema

### No Schema Changes Required ✅

The fix only changes query logic - no new columns or indexes needed. The static counts in `analysis_runs` are preserved for historical reference but no longer used for display.

### Historical Data
- Original AI counts still stored in database
- Can be compared against current counts
- Useful for tracking QA correction rate

## Files Modified

1. **database.py** - Updated three methods:
   - `AnalysisRun.get_all()`
   - `AnalysisRun.get_by_id()`
   - `AnalysisRun.get_latest()`

## Backward Compatibility

✅ **Fully Compatible**
- No API changes
- No template changes required
- Existing code continues to work
- Just shows accurate counts now

## Deployment

### Zero Downtime Update
1. Update `database.py` (already done)
2. Restart dashboard (already done)
3. No migration needed
4. Works immediately

## Verification

Dashboard is now running with dynamic counts at: **http://localhost:5000**

**Test it:**
1. Note current pass/fail counts
2. Edit any poster's label
3. Refresh dashboard
4. Counts should update immediately! ✅

## Future Enhancements

### Potential Additions:
- Show original vs current counts side-by-side
- Add "QA Progress" percentage (% of posters reviewed)
- Export with both original and current statistics
- API endpoint to get count history over time

## Conclusion

Pass/fail counts now accurately reflect the current state of poster labels, including all QA modifications. The dashboard provides real-time statistics that update as you curate your ground truth dataset.

---

**Status:** ✅ Working  
**Dashboard:** http://localhost:5000  
**Try it:** Edit a poster label and watch the counts update on refresh!

