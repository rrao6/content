# Red Zone Analysis - Optimization & Accuracy Summary

## ✅ Issues Fixed

### 1. SQL Syntax Error for "most_popular"
**Problem**: Empty `sot_raw AS ( )` caused SQL syntax error when invalid/empty SOT types were passed.

**Solution**: 
- Added validation in `sot_query.py` to return empty result set when no valid SOT types
- Properly normalized "most_popular" → "most_liked" in analyzer

### 2. Dashboard Environment Issues
**Problem**: Environment variables not loading properly, module import errors

**Solution**:
- Created `run_dashboard_clean.py` with proper environment loading
- Fixed Python path issues for imports

### 3. SOT Type Mapping
**Problem**: UI sends "most_popular" but database expects "most_liked"

**Solution**:
- Implemented SOT_TYPE_MAP in analyzer:
  - "most_popular" → "most_liked"
  - "rotten_tomatoes" → "rt"
  - Proper validation and error messages

## 🎯 Accuracy Improvements

### 1. Duplicate Prevention
```sql
-- All queries now use DISTINCT to prevent duplicates
SELECT DISTINCT 
    et.program_id,
    et.sot_name,
    ci.content_id,
    ci.content_name,
    ci.content_type,
    ci.poster_img_url
FROM eligible_titles et
JOIN core_prod.tubidw.content_info ci 
    ON et.program_id = ci.content_id
```

### 2. Data Validation
- Empty SOT arrays are rejected
- Invalid SOT types are filtered out
- Clear error messages for invalid inputs

### 3. Checkpoint System
- Prevents re-processing of already analyzed posters
- Tracks processed pairs: (content_id, sot_name)
- Resumes from interruptions

## 🚀 Performance Optimizations

### Current Performance
- **3-4 seconds per poster** (15-20 posters/minute)
- Sequential processing is the main bottleneck

### Recommended Optimizations

#### 1. **Parallel Processing** (Highest Impact - 4-6x speedup)
```python
# In sot_pipeline.py - process posters in parallel
from concurrent.futures import ThreadPoolExecutor

def _process_batch_parallel(self, batch, max_workers=10):
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        for poster in batch:
            future = executor.submit(self._process_single_poster, poster)
            futures.append(future)
        
        # Process results as they complete
        for future in concurrent.futures.as_completed(futures):
            yield future.result()
```

#### 2. **Increase Rate Limits**
```bash
# In .env file
VISION_REQUESTS_PER_MINUTE=120  # From 30
VISION_REQUEST_DELAY_MS=50      # From 100
```

#### 3. **Connection Pooling**
```python
# In analysis.py
def _create_retry_session():
    session = requests.Session()
    adapter = HTTPAdapter(
        pool_connections=20,
        pool_maxsize=50,
        pool_block=False
    )
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session
```

#### 4. **Skip Red Zone Overlay During Analysis**
```python
# Only add overlay for display, not for API calls
image_data = _download_image_to_base64(url, add_red_zone=False)
```

#### 5. **Database Query Optimization**
```sql
-- Add indexes for better performance
CREATE INDEX idx_sot_program ON eligible_titles(sot_name, program_id);
CREATE INDEX idx_content_active_poster 
    ON content_info(content_id, active, poster_img_url) 
    WHERE poster_img_url IS NOT NULL;
```

## 📊 Testing & Monitoring

### Test Scripts Created
1. **test_analysis_accuracy.py** - Tests SOT mapping and validation
2. **run_dashboard_clean.py** - Clean startup with logging

### Key Metrics to Monitor
- Processing time per poster
- Success/error rates by SOT type
- Duplicate detection rate
- API rate limit usage

## 🔒 Data Integrity

### Ensuring No Duplicates
1. DISTINCT in all SQL queries
2. Checkpoint tracking of (content_id, sot_name) pairs
3. Set-based duplicate detection in pipeline

### Validation Layers
1. UI validation (frontend)
2. API validation (analyzer)
3. SQL query validation
4. Result verification

## 📝 Usage Guidelines

### Starting the Dashboard
```bash
cd /Users/rrao/content-1
python3 run_dashboard_clean.py
```

### Running Analysis
1. Start with small batches (10-25 posters)
2. Use one SOT type initially
3. Monitor progress in real-time
4. Check for duplicates in results

### SOT Type Reference
- **UI Label** → **Database Value**
- "Most Popular" → "most_liked"
- "Rotten Tomatoes" → "rt"
- "Just Added" → "just_added"
- "Leaving Soon" → "leaving_soon"
- "IMDB" → "imdb"

## 🎯 Next Steps for Optimization

1. **Implement parallel processing** (biggest impact)
2. **Increase rate limits** based on OpenAI tier
3. **Add result streaming** to dashboard
4. **Implement batch API** when available
5. **Add caching layer** for frequently analyzed posters

## 📈 Expected Performance After Optimization

- Current: 15-20 posters/minute
- With optimizations: 60-120 posters/minute
- 4-6x performance improvement
- Better scalability for large batches
