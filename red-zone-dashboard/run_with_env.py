#!/usr/bin/env python3
"""Helper script to run dashboard with proper environment loading."""
import os
import sys
import subprocess
from pathlib import Path

def load_env_file(env_path):
    """Load environment variables from .env file."""
    if not env_path.exists():
        return False
    
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key.strip()] = value.strip()
    return True

def main():
    # Load parent .env
    parent_env = Path('../.env')
    if not load_env_file(parent_env):
        print("❌ Parent .env not found")
        sys.exit(1)
    
    # Load local .env (if exists)
    local_env = Path('.env')
    load_env_file(local_env)
    
    # Check required variables
    required = [
        'DATABRICKS_HOST',
        'DATABRICKS_HTTP_PATH', 
        'DATABRICKS_TOKEN',
        'DATABRICKS_CATALOG',
        'DATABRICKS_SCHEMA',
        'OPENAI_API_KEY'
    ]
    
    missing = []
    for var in required:
        if not os.environ.get(var):
            missing.append(var)
    
    if missing:
        print(f"❌ Missing environment variables: {missing}")
        sys.exit(1)
    
    print("✅ Environment loaded successfully")
    
    # Initialize database
    print("📊 Initializing database...")
    subprocess.run([sys.executable, 'database.py'])
    
    # Start dashboard
    print("\n🚀 Starting Red Zone Dashboard...")
    print("🌐 Visit: http://localhost:5000\n")
    
    # Run dashboard.py in the same process to preserve environment
    import dashboard
    dashboard.app.run(host='0.0.0.0', port=5000, debug=False)

if __name__ == '__main__':
    main()
