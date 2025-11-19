# Duplicate Content Fix in SOT Queries

**Date:** November 18, 2025  
**Status:** ✅ Fixed

## Problem

Run #17 contained duplicate entries for the same content_id. For example:
- **Rocky** (content_id: 100000031) appeared **3 times** with sot_name='award'
- **Pan's Labyrinth** (content_id: 100002546) appeared **3 times** with sot_name='award'
- **Ray** (content_id: 100000363) appeared **3 times** with sot_name='award'

These were true duplicates (same content_id, same sot_name), not the same content appearing across different SOTs.

## Root Cause

The SOT queries in `sot_query.py` were missing `DISTINCT` for several source tables:

1. **award** - Movies with multiple awards (Best Picture, Best Actor, etc.) had one row per award
2. **vibe** - Could have duplicate entries
3. **narrative** - Could have duplicate entries  
4. **most_liked** - Container items could have duplicates

### Example: Rocky

Rocky won 3 Academy Awards, so the `dsa_raw_yixinc_award_df` table had 3 rows:
```
program_id  | award_type
100000031   | Best Picture
100000031   | Best Director
100000031   | Best Film Editing
```

Without `DISTINCT`, all 3 rows were carried through the query chain, resulting in 3 analysis runs for the same poster.

## Solution

Added `DISTINCT` to the four affected SOT queries:

### Before:
```sql
SELECT 
    program_id,
    'award' AS sot_name
FROM core_dev.dsa.dsa_raw_yixinc_award_df
```

### After:
```sql
SELECT DISTINCT 
    program_id,
    'award' AS sot_name
FROM core_dev.dsa.dsa_raw_yixinc_award_df
```

## Changes Made

**File:** `sot_query.py`

1. **award query** (line 116) - Added `SELECT DISTINCT`
2. **vibe query** (line 123) - Added `SELECT DISTINCT`
3. **narrative query** (line 130) - Added `SELECT DISTINCT`
4. **most_liked query** (line 137) - Added `SELECT DISTINCT`

## Why Other Queries Didn't Need It

The following queries already had proper deduplication:

- **imdb** - Already had `SELECT DISTINCT` (line 98)
- **rt** - Already had `SELECT DISTINCT` (line 108)
- **leaving_soon** - Base CTE used `SELECT DISTINCT` (line 56)
- **just_added** - Base CTE used `SELECT DISTINCT` (line 78)

## Impact on Existing Data

### Run #17 (Already Completed)
- Contains duplicates (200 entries, but ~150-160 unique posters)
- QA work on duplicates is still valid
- Export will include duplicates
- **Recommendation:** Re-run analysis with fixed query for clean data

### Future Runs
- ✅ No more duplicates
- Each poster appears exactly once per SOT
- If a poster qualifies for multiple SOTs (e.g., both "imdb" and "award"), it will appear multiple times with different sot_names (this is intentional)

## Verification

To check for duplicates in future runs:

```sql
-- Find duplicates in a run
SELECT content_id, title, sot_name, COUNT(*) as count 
FROM poster_results 
WHERE run_id = ?
GROUP BY content_id, sot_name 
HAVING COUNT(*) > 1
ORDER BY count DESC;
```

Should return 0 rows for properly deduplicated data.

## Testing

After fix, running a new analysis should:
1. Not have any content_id appearing multiple times with the same sot_name
2. Content_id CAN appear multiple times if it qualifies for different SOTs
3. Total poster count should match unique (content_id, sot_name) combinations

### Example of Correct Behavior:

**Rocky** qualifies for 3 SOTs:
```
content_id  | sot_name  | count
100000031   | award     | 1    ✅ (not 3!)
100000031   | imdb      | 1    ✅ (if IMDb >= 8.0)
100000031   | rt        | 1    ✅ (if RT >= 80)
```

Total: 3 rows, but each with a different sot_name = CORRECT

## Files Modified

1. **sot_query.py** - Added `DISTINCT` to 4 SOT queries

## Backward Compatibility

✅ **Fully Compatible**
- Only affects future analysis runs
- Existing runs in database unchanged
- No API or schema changes

## Recommendation for Run #17

Since Run #17 has duplicates, you have two options:

### Option 1: Keep Current Data
- Continue QA review on Run #17
- Note that some posters are duplicated
- Export will include duplicates
- Use for testing/development

### Option 2: Re-run Analysis
- Delete Run #17 from database
- Run new analysis with fixed query
- Get clean, deduplicated data
- Use for production ground truth dataset

To delete Run #17:
```sql
DELETE FROM poster_results WHERE run_id = 17;
DELETE FROM analysis_runs WHERE id = 17;
```

Then run a fresh analysis with the fixed query.

## Conclusion

The duplicate issue was caused by missing `DISTINCT` clauses in SOT queries for tables that naturally contain multiple rows per program (especially the award table). This is now fixed and future runs will not have duplicates.

---

**Status:** ✅ Fixed in `sot_query.py`  
**Affects:** Future analysis runs only  
**Action Required:** None (or optionally re-run Run #17 for clean data)

