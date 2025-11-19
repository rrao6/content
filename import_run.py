import sys
import os
from pathlib import Path

# Add red-zone-dashboard to path
sys.path.append(os.path.join(os.getcwd(), "red-zone-dashboard"))

from database import init_database, import_json_results

def main():
    json_file = Path("analysis_results.json")
    if not json_file.exists():
        print(f"Error: {json_file} not found.")
        sys.exit(1)

    print("Initializing database...")
    from database import DB_PATH
    print(f"Using Database at: {DB_PATH.absolute()}")
    
    if DB_PATH.exists():
        print("Database file exists, appending new run...")
    else:
        print("Database file does not exist, creating new.")
        
    init_database()

    print(f"Importing results from {json_file}...")
    
    # Convert NDJSON to JSON array if needed
    import json
    try:
        with open(json_file) as f:
            json.load(f)
    except json.JSONDecodeError:
        print("Detected NDJSON format, converting to JSON array...")
        data = []
        with open(json_file) as f:
            for line in f:
                if line.strip():
                    data.append(json.loads(line))
        
        with open(json_file, 'w') as f:
            json.dump(data, f, indent=2)
            
    try:
        run_id = import_json_results(json_file, description="Manual CLI Analysis Run")
        print(f"\n✅ Successfully imported results as Run ID: {run_id}")
        print(f"   You can view the results at: http://localhost:5000/results/{run_id}")
    except Exception as e:
        print(f"❌ Error importing results: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

