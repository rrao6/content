#!/bin/bash

# Red Zone Dashboard - Switch to REAL Data

echo "🚀 Red Zone Dashboard - Production Mode"
echo "======================================"
echo

# Check environment
echo "Checking environment..."
if [ ! -f "../.env" ]; then
    echo "❌ ERROR: ../.env file not found"
    echo "   Please ensure your .env file has:"
    echo "   - DATABRICKS_HOST"
    echo "   - DATABRICKS_TOKEN"
    echo "   - DATABRICKS_HTTP_PATH"
    echo "   - OPENAI_API_KEY"
    exit 1
fi

echo "✅ Environment file found"
echo

# Option 1: Verify backend
echo "Option 1: Verify all backend systems"
echo "-----------------------------------"
echo "Run: python verify_backend.py"
echo
echo "This will test:"
echo "- Databricks connection"
echo "- OpenAI API"
echo "- Full analysis pipeline"
echo

# Option 2: Run production integration
echo "Option 2: Run REAL analysis"
echo "---------------------------"
echo "Run: python production_integration.py"
echo
echo "This will:"
echo "- Fetch REAL eligible titles from your database"
echo "- Download REAL poster images"
echo "- Run REAL OpenAI analysis"
echo "- Save results to dashboard"
echo

# Option 3: View in dashboard
echo "Option 3: View results"
echo "----------------------"
echo "Run: python dashboard.py"
echo "Then visit: http://localhost:5000"
echo

echo "📌 Quick Start Commands:"
echo
echo "1. Test everything:"
echo "   python verify_backend.py"
echo
echo "2. Run real analysis (25 posters):"
echo "   python production_integration.py"
echo
echo "3. Start dashboard:"
echo "   python dashboard.py"
echo

echo "✨ All data will be REAL from your production database!"
