# Production Deployment Guide

## Overview

This guide covers the production deployment and operation of the Tubi Poster Safe-Zone Analysis system.

## Architecture

```
┌─────────────────┐     ┌──────────────┐     ┌─────────────────┐
│   Databricks    │────▶│   Pipeline   │────▶│  OpenAI Vision  │
│  content_info   │     │  (Analysis)  │     │      API        │
└─────────────────┘     └──────────────┘     └─────────────────┘
                               │
                               ▼
                        ┌──────────────┐
                        │    Cache &   │
                        │  Monitoring  │
                        └──────────────┘
```

## Key Features

### 1. Automatic Image Download
- HTTP poster URLs are automatically downloaded and converted to base64
- Handles timeouts and retries with exponential backoff
- Size limits prevent memory issues (default: 10MB per image)

### 2. Robust JSON Parsing
- Handles multiple response formats from OpenAI
- Automatically cleans markdown-wrapped responses
- Fallback handling for error messages

### 3. Production Monitoring
- Real-time health metrics
- Alert thresholds for error rates and latency
- Detailed error tracking with recent error history

### 4. Caching & Rate Limiting
- TTL-based result caching (default: 24 hours)
- Configurable rate limiting to prevent quota exhaustion
- Automatic request throttling

## Configuration

### Required Environment Variables

```bash
# Databricks
DATABRICKS_HOST=tubi-dev.cloud.databricks.com
DATABRICKS_HTTP_PATH=/sql/1.0/warehouses/34148fb208740945
DATABRICKS_TOKEN=<your-pat-token>
DATABRICKS_CATALOG=core_prod
DATABRICKS_SCHEMA=tubidw
DATABRICKS_CONTENT_TABLE=content_info

# OpenAI
OPENAI_API_KEY=<your-api-key>
OPENAI_MODEL=gpt-4o  # or gpt-4o-mini

# Performance Tuning
VISION_REQUESTS_PER_MINUTE=30
VISION_REQUEST_DELAY_MS=100
ENABLE_ANALYSIS_CACHE=true
CACHE_EXPIRY_HOURS=24
```

### Alert Thresholds

Configure in `monitoring.py`:
- Error rate: 20% (alerts if >20% requests fail)
- Latency: 5000ms (alerts if average >5s)
- Rate: 100 RPM (alerts if exceeding rate limit)

## Running in Production

### Basic Analysis

```bash
# Analyze 100 posters
python main.py analyze-posters --limit 100 --json-array

# Process all active content (no limit)
python main.py analyze-posters --include-inactive
```

### Monitoring

```bash
# Check system health
python main.py health

# View real-time metrics
python main.py metrics

# Monitor logs (structured JSON)
python main.py analyze-posters --limit 10 2>&1 | jq
```

### Performance Optimization

```bash
# Increase batch size for better throughput
python main.py analyze-posters --batch-size 200

# Adjust download timeout for slow networks
python main.py analyze-posters --download-timeout 60

# Skip download for HTTPS URLs (not recommended for HTTP)
python main.py analyze-posters --no-download
```

## Scaling Considerations

### 1. Parallel Processing
For maximum throughput, run multiple workers:

```python
# Example: Process specific content ID ranges
from concurrent.futures import ProcessPoolExecutor

def process_range(start_id, end_id):
    # Run pipeline for specific ID range
    pass

with ProcessPoolExecutor(max_workers=4) as executor:
    futures = []
    for i in range(0, 10000, 2500):
        future = executor.submit(process_range, i, i+2500)
        futures.append(future)
```

### 2. Database Optimization
- Use appropriate batch sizes (100-500 recommended)
- Consider partitioning large queries by date/type
- Monitor Databricks warehouse utilization

### 3. API Rate Management
- Current limit: 30 requests/minute (configurable)
- Automatic throttling prevents 429 errors
- Cache reduces redundant API calls

## Troubleshooting

### Common Issues

1. **"Vision model returned non-JSON output"**
   - Usually caused by markdown-wrapped responses
   - Already handled by JSON cleaning logic
   - Check logs for actual response content

2. **"Image download failed"**
   - Network timeout or connectivity issue
   - Increase `--download-timeout` if needed
   - Check if poster URLs are accessible

3. **"High error rate" alerts**
   - Check OpenAI API status
   - Verify API key has sufficient quota
   - Review recent errors in metrics

### Debug Commands

```bash
# Test single poster with detailed output
python test_production.py --single

# Test JSON cleaning
python test_production.py --json-clean

# Test batch with monitoring
python test_production.py --batch
```

### Log Analysis

```bash
# Find all errors in last run
grep "error" logs/analysis.log | jq

# Count errors by type
grep "error_type" logs/analysis.log | jq -r .error_type | sort | uniq -c

# Monitor real-time
tail -f logs/analysis.log | jq 'select(.level=="error")'
```

## Best Practices

1. **Start Small**: Test with 10-100 posters before full runs
2. **Monitor Metrics**: Check `/metrics` endpoint regularly
3. **Review Errors**: Investigate any sustained error patterns
4. **Cache Warming**: Re-run recently failed items after fixes
5. **Backup Results**: Store analysis results in Delta tables

## Integration Example

```python
# Integration with existing Tubi systems
from main import get_config
from service import ContentService
from analysis import SafeZoneAnalyzer, PosterAnalysisPipeline

# Initialize once
config = get_config()
service = ContentService()
analyzer = SafeZoneAnalyzer(
    provider="openai",
    model=config.openai_model,
    api_key=config.openai_api_key,
)
pipeline = PosterAnalysisPipeline(service, analyzer)

# Process specific content
def analyze_new_content(content_ids: List[int]):
    results = []
    for content_id in content_ids:
        # This will use cache if available
        batch_results = pipeline.run(
            limit=1,
            # Add WHERE clause in repository
            additional_filter=f"content_id = {content_id}"
        )
        results.extend(batch_results)
    return results
```

## Maintenance

### Daily Tasks
- Check health status: `python main.py health`
- Review metrics: `python main.py metrics`
- Monitor error rates in logs

### Weekly Tasks
- Clear old cache entries if needed
- Review and adjust rate limits based on usage
- Update OpenAI model version if new releases

### Monthly Tasks
- Analyze cost vs cache hit rate
- Review alert thresholds
- Performance optimization review
