"""Migration script to add QA tracking fields to existing database."""
import sqlite3
from pathlib import Path

def migrate_database(db_path="red_zone_analysis.db"):
    """Add QA tracking fields to poster_results table."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='poster_results'")
    if not cursor.fetchone():
        print(f"  ✗ Table 'poster_results' not found. Skipping.")
        conn.close()
        return
    
    # Check if columns already exist
    cursor.execute("PRAGMA table_info(poster_results)")
    columns = [col[1] for col in cursor.fetchall()]
    
    migrations_needed = []
    
    if 'qa_reviewed' not in columns:
        migrations_needed.append(
            "ALTER TABLE poster_results ADD COLUMN qa_reviewed BOOLEAN DEFAULT 0"
        )
    
    if 'qa_modified_at' not in columns:
        migrations_needed.append(
            "ALTER TABLE poster_results ADD COLUMN qa_modified_at TIMESTAMP"
        )
    
    if 'original_has_elements' not in columns:
        migrations_needed.append(
            "ALTER TABLE poster_results ADD COLUMN original_has_elements BOOLEAN"
        )
    
    if 'original_justification' not in columns:
        migrations_needed.append(
            "ALTER TABLE poster_results ADD COLUMN original_justification TEXT"
        )
    
    if migrations_needed:
        print(f"Applying {len(migrations_needed)} migrations...")
        for migration in migrations_needed:
            print(f"  - {migration}")
            cursor.execute(migration)
        
        # Create index if needed
        try:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_qa_reviewed ON poster_results(qa_reviewed)")
            print("  - Created index on qa_reviewed")
        except sqlite3.OperationalError:
            pass  # Index already exists
        
        conn.commit()
        print("\n✓ Migration completed successfully!")
    else:
        print("✓ Database already up to date. No migrations needed.")
    
    conn.close()

if __name__ == "__main__":
    print("Red Zone Analysis - QA Fields Migration")
    print("=" * 50)
    
    # Migrate main database
    db_path = Path("red_zone_analysis.db")
    if db_path.exists():
        print(f"\nMigrating: {db_path}")
        migrate_database(str(db_path))
    else:
        print(f"\n✗ Database not found: {db_path}")
        print("  Run the dashboard first to create the database.")
    
    # Also migrate poster_analysis.db if it exists
    poster_db_path = Path("poster_analysis.db")
    if poster_db_path.exists():
        print(f"\nMigrating: {poster_db_path}")
        migrate_database(str(poster_db_path))
    
    print("\nDone!")

