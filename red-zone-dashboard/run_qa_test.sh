#!/bin/bash

# Red Zone Analysis Dashboard - QA Test Runner
# This script sets up and tests the dashboard with limited batches

echo "=== Red Zone Analysis Dashboard - QA Setup ==="
echo

# Check Python version
echo "Checking Python version..."
python3 --version

# Install dependencies
echo
echo "Installing dependencies..."
pip install -r requirements.txt

# Initialize database
echo
echo "Initializing database..."
python3 database.py

# Run tests
echo
echo "Running test suite..."
python3 test_dashboard.py

echo
echo "=== Setup Complete ==="
echo
echo "The dashboard has been set up with:"
echo "- Database initialized"
echo "- Test data (100 posters) imported"
echo "- Batch size limited to 100 max (50 default)"
echo
echo "To start the dashboard:"
echo "  python3 dashboard.py"
echo
echo "Then visit: http://localhost:5000"
echo
echo "QA Guidelines:"
echo "1. Start with small batches (10-25 posters)"
echo "2. Review results for accuracy"
echo "3. Gradually increase batch size"
echo "4. Maximum 100 posters per batch enforced"
echo
echo "Check the QA Guide in the dashboard for detailed instructions."
