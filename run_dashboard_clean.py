#!/usr/bin/env python3
"""Clean dashboard startup with proper environment and error handling."""
import os
import sys
import subprocess
import time
import signal
from pathlib import Path

def kill_existing_processes():
    """Kill any existing dashboard processes."""
    print("🧹 Cleaning up existing processes...")
    
    # Kill any Python processes on port 5000
    try:
        result = subprocess.run(['lsof', '-ti:5000'], capture_output=True, text=True)
        if result.stdout:
            pids = result.stdout.strip().split('\n')
            for pid in pids:
                if pid:
                    subprocess.run(['kill', '-9', pid])
            print(f"   ✅ Killed {len(pids)} processes on port 5000")
    except:
        pass
    
    # Kill any dashboard.py processes
    subprocess.run(['pkill', '-f', 'dashboard.py'], stderr=subprocess.DEVNULL)
    time.sleep(2)
    print("   ✅ Cleanup complete")

def load_environment():
    """Load environment variables from .env file."""
    print("\n🔧 Loading environment...")
    
    env_path = Path('.env')
    if not env_path.exists():
        print("   ❌ .env file not found!")
        return False
    
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key.strip()] = value.strip()
    
    # Verify critical variables
    required = [
        'DATABRICKS_HOST',
        'DATABRICKS_HTTP_PATH',
        'DATABRICKS_TOKEN',
        'DATABRICKS_CATALOG',
        'DATABRICKS_SCHEMA',
        'OPENAI_API_KEY'
    ]
    
    missing = [var for var in required if not os.environ.get(var)]
    if missing:
        print(f"   ❌ Missing environment variables: {missing}")
        return False
    
    print("   ✅ Environment loaded successfully")
    return True

def start_dashboard():
    """Start the dashboard with proper error handling."""
    print("\n🚀 Starting Red Zone Analysis Dashboard...")
    
    # Change to dashboard directory
    os.chdir('red-zone-dashboard')
    
    # Initialize database
    print("   📊 Initializing database...")
    subprocess.run([sys.executable, 'database.py'])
    
    print("\n" + "="*60)
    print("📱 Red Zone Analysis Dashboard")
    print("="*60)
    print("\n🌐 Dashboard URL: http://localhost:5000")
    print("\n📌 Available Features:")
    print("   • View previous analysis runs")
    print("   • Run new analysis (small batches recommended)")
    print("   • Filter results by SOT type and status")
    print("   • Export results as JSON/CSV")
    print("\n⚠️  Important Notes:")
    print("   • Start with batch sizes of 10-25 for testing")
    print("   • Current performance: ~3-4 seconds per poster")
    print("   • Most Popular = Most Liked in the database")
    print("\n🛑 To stop: Press Ctrl+C")
    print("="*60 + "\n")
    
    # Import and run dashboard
    try:
        # Add current directory to Python path
        sys.path.insert(0, os.getcwd())
        import dashboard
        dashboard.app.run(host='0.0.0.0', port=5000, debug=False)
    except KeyboardInterrupt:
        print("\n\n✅ Dashboard stopped gracefully")
    except Exception as e:
        print(f"\n❌ Dashboard error: {e}")
        import traceback
        traceback.print_exc()

def main():
    """Main entry point."""
    print("🎯 Red Zone Dashboard Startup Script\n")
    
    # Handle Ctrl+C gracefully
    signal.signal(signal.SIGINT, lambda s, f: sys.exit(0))
    
    # Step 1: Kill existing processes
    kill_existing_processes()
    
    # Step 2: Load environment
    if not load_environment():
        sys.exit(1)
    
    # Step 3: Start dashboard
    start_dashboard()

if __name__ == '__main__':
    main()
