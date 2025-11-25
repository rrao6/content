#!/bin/bash
cd /Users/rrao/content-1

# Load environment variables
export $(grep -v '^#' .env | xargs -0)

# Move to dashboard directory
cd red-zone-dashboard

# Start the dashboard
echo "🚀 Starting Red Zone Dashboard..."
echo "🌐 Visit: http://localhost:5000"
python3 dashboard.py
