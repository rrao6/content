#!/bin/bash

# Red Zone Dashboard - Quick Restart Script

echo "🔄 Restarting Red Zone Analysis Dashboard..."
echo

# Kill any existing Flask processes
echo "Stopping existing Flask server..."
pkill -f "python.*dashboard.py" 2>/dev/null || true
sleep 1

# Ensure database is fixed
echo "Ensuring database is optimized..."
python3 fix_dashboard.py > /dev/null 2>&1

echo
echo "🚀 Starting dashboard server..."
echo "================================"
echo
python3 dashboard.py &

# Wait a moment for server to start
sleep 2

echo
echo "✅ Dashboard is running!"
echo
echo "Access the dashboard at:"
echo "  http://localhost:5000"
echo
echo "Quick links:"
echo "  - Dashboard: http://localhost:5000/"
echo "  - Latest Results: http://localhost:5000/results"
echo "  - New Analysis: http://localhost:5000/analyze"
echo "  - QA Guide: http://localhost:5000/qa-guide"
echo
echo "Press Ctrl+C to stop the server"
echo

# Keep script running
wait
