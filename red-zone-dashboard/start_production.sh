#!/bin/bash

# Production Startup Script for Red Zone Analysis System
# This script ensures everything is properly set up and running

echo "🚀 Red Zone Analysis System - Production Startup"
echo "==============================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to check environment variable
check_env_var() {
    if [ -z "${!1}" ]; then
        echo -e "${RED}❌ Missing environment variable: $1${NC}"
        return 1
    else
        echo -e "${GREEN}✅ Found $1${NC}"
        return 0
    fi
}

# Step 1: Check Python
echo "1️⃣ Checking Python environment..."
if command_exists python3; then
    PYTHON_VERSION=$(python3 --version 2>&1)
    echo -e "${GREEN}✅ $PYTHON_VERSION${NC}"
else
    echo -e "${RED}❌ Python 3 not found. Please install Python 3.8+${NC}"
    exit 1
fi

# Step 2: Check if we're in the right directory
echo ""
echo "2️⃣ Checking directory..."
if [ -f "dashboard.py" ]; then
    echo -e "${GREEN}✅ In red-zone-dashboard directory${NC}"
else
    echo -e "${RED}❌ Not in red-zone-dashboard directory${NC}"
    echo "   Please cd to red-zone-dashboard first"
    exit 1
fi

# Step 3: Setup .env if needed
echo ""
echo "3️⃣ Setting up environment..."
if [ -f "setup_env.sh" ]; then
    bash setup_env.sh
else
    echo -e "${YELLOW}⚠️  setup_env.sh not found, skipping environment setup${NC}"
fi

# Step 4: Check parent .env
echo ""
echo "4️⃣ Checking parent .env file..."
if [ -f "../.env" ]; then
    echo -e "${GREEN}✅ Found parent .env file${NC}"
    
    # Load parent environment variables
    export $(grep -v '^#' ../.env | xargs)
    
    # Check required variables
    MISSING_VARS=0
    for VAR in DATABRICKS_HOST DATABRICKS_HTTP_PATH DATABRICKS_TOKEN OPENAI_API_KEY; do
        if ! check_env_var $VAR; then
            MISSING_VARS=$((MISSING_VARS + 1))
        fi
    done
    
    if [ $MISSING_VARS -gt 0 ]; then
        echo -e "${RED}❌ Missing $MISSING_VARS required environment variables${NC}"
        echo "   Please update ../.env with all required variables"
        exit 1
    fi
else
    echo -e "${RED}❌ Parent .env file not found at ../.env${NC}"
    echo "   The system needs Databricks and OpenAI credentials"
    exit 1
fi

# Step 5: Install dependencies
echo ""
echo "5️⃣ Installing dependencies..."
if [ -f "requirements.txt" ]; then
    pip3 install -q -r requirements.txt
    echo -e "${GREEN}✅ Dependencies installed${NC}"
else
    echo -e "${YELLOW}⚠️  requirements.txt not found${NC}"
fi

# Also install parent requirements if needed
if [ -f "../requirements.txt" ]; then
    echo "   Installing parent dependencies..."
    pip3 install -q -r ../requirements.txt
    echo -e "${GREEN}✅ Parent dependencies installed${NC}"
fi

# Step 6: Initialize database
echo ""
echo "6️⃣ Initializing database..."
python3 database.py
echo -e "${GREEN}✅ Database ready${NC}"

# Step 7: Test backend connections
echo ""
echo "7️⃣ Testing backend connections..."
python3 verify_backend.py
BACKEND_STATUS=$?

if [ $BACKEND_STATUS -eq 0 ]; then
    echo -e "${GREEN}✅ All backend systems operational${NC}"
else
    echo -e "${YELLOW}⚠️  Some backend systems may not be fully operational${NC}"
    echo "   Dashboard will still run but may have limited functionality"
fi

# Step 8: Start the dashboard
echo ""
echo "8️⃣ Starting Red Zone Dashboard..."
echo ""
echo "=========================================="
echo "📊 Red Zone Analysis Dashboard"
echo "=========================================="
echo ""
echo "🌐 URL: http://localhost:5000"
echo ""
echo "📌 Available Features:"
echo "   - View analysis results"
echo "   - Run new analysis (if backend connected)"
echo "   - Export results as JSON"
echo "   - Filter by SOT and status"
echo ""
echo "🛑 To stop: Press Ctrl+C"
echo ""
echo "=========================================="
echo ""

# Start the Flask app
export FLASK_APP=dashboard.py
export FLASK_ENV=production
python3 -m flask run --host=0.0.0.0 --port=5000
