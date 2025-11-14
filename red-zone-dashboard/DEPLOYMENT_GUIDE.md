# Red Zone Analysis - Complete Deployment Guide

## 🚀 Quick Start

```bash
# 1. Navigate to dashboard directory
cd /Users/rrao/content/red-zone-dashboard

# 2. Run the production startup script
./start_production.sh
```

That's it! The dashboard will be available at http://localhost:5000

## 📋 Prerequisites

1. **Python 3.8+** installed
2. **Parent .env file** at `/Users/rrao/content/.env` with:
   - `DATABRICKS_HOST`
   - `DATABRICKS_HTTP_PATH`
   - `DATABRICKS_TOKEN`
   - `DATABRICKS_CATALOG`
   - `DATABRICKS_SCHEMA`
   - `OPENAI_API_KEY`
   - `OPENAI_MODEL`

## 🔧 Manual Setup (if needed)

### 1. Environment Setup

```bash
cd /Users/rrao/content/red-zone-dashboard

# Create local .env
./setup_env.sh

# Install dependencies
pip install -r requirements.txt
pip install -r ../requirements.txt
```

### 2. Initialize Database

```bash
python database.py
```

### 3. Verify Backend Connections

```bash
python verify_backend.py
```

### 4. Start Dashboard

```bash
python dashboard.py
```

## 🧪 Testing

### Run Comprehensive Tests
```bash
python test_full_system.py
```

### Test Individual Components
```bash
# Test just the dashboard
python test_dashboard.py

# Test backend connections only
python verify_backend.py
```

## 📊 Running Real Analysis

### Option 1: Through Dashboard UI
1. Navigate to http://localhost:5000
2. Click "New Analysis"
3. Select SOT types and configure parameters
4. Click "Start Analysis"

### Option 2: Command Line
```bash
# Run production integration script
python production_integration.py
```

### Option 3: Using Main Pipeline
```bash
cd /Users/rrao/content
python main.py analyze-eligible --sot-type just_added --limit 50
```

## 🎯 Key Features

### Dashboard Features
- **Real-time Analysis**: Run analysis on live data from Databricks
- **Image Proxy**: Handles HTTP/HTTPS CDN images seamlessly
- **Export/Import**: Share results as JSON files
- **Filtering**: Filter by SOT, status, and search
- **Detailed Views**: Click any poster for full analysis details

### Analysis Features
- **Red Zone Detection**: Analyzes top-left 60% × 10% region
- **Key Element Detection**: Identifies text and facial features
- **Confidence Scoring**: 0-100% confidence ratings
- **Batch Processing**: Analyze up to 100 posters at once
- **Caching**: Reduces redundant API calls

## 🛠️ Troubleshooting

### Dashboard Won't Start
```bash
# Check if port 5000 is in use
lsof -i :5000

# Kill existing process if needed
kill -9 <PID>

# Try different port
python dashboard.py --port 5001
```

### Database Issues
```bash
# Reset database
rm red_zone_analysis.db
python database.py
```

### Import Parent Modules Failing
```bash
# Ensure you're in the right directory
cd /Users/rrao/content/red-zone-dashboard

# Check Python path
python -c "import sys; print(sys.path)"
```

### Analysis Not Working
1. Check `.env` variables are loaded
2. Verify OpenAI API key has quota
3. Check Databricks connection
4. Run `verify_backend.py` for diagnostics

## 📈 Production Tips

1. **Batch Sizes**: Start with 25-50 posters for testing
2. **Rate Limiting**: Default is 30 requests/minute to OpenAI
3. **Caching**: Enable for cost savings (24-hour default TTL)
4. **Monitoring**: Check `/api/stats/trending` for metrics

## 🔒 Security

1. **Never commit .env files** to version control
2. **Use strong SECRET_KEY** in production
3. **Restrict image proxy** to allowed domains only
4. **Enable HTTPS** for production deployment

## 📞 Support

For issues:
1. Check test results: `test_report.json`
2. Review logs in terminal output
3. Run `verify_backend.py` for diagnostics

## ✅ Checklist

Before running in production:

- [ ] Parent .env has all required variables
- [ ] Python 3.8+ installed
- [ ] All dependencies installed
- [ ] Database initialized
- [ ] Backend connections verified
- [ ] Test suite passes
- [ ] Dashboard accessible at http://localhost:5000

## 🎉 Success Indicators

You know everything is working when:
1. Dashboard loads without errors
2. `/api/runs` returns JSON data
3. Image proxy shows poster images
4. "New Analysis" runs successfully
5. Results appear in dashboard grid
