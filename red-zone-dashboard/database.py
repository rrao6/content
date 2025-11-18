"""Database models and operations for Red Zone Analysis Dashboard."""
import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from contextlib import contextmanager

import structlog

logger = structlog.get_logger(__name__)

# Database path
DB_PATH = Path("red_zone_analysis.db")


@contextmanager
def get_db_connection():
    """Context manager for database connections."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Enable column access by name
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_database():
    """Initialize database with schema."""
    schema = """
    -- Analysis runs table
    CREATE TABLE IF NOT EXISTS analysis_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        total_analyzed INTEGER NOT NULL,
        pass_count INTEGER NOT NULL,
        fail_count INTEGER NOT NULL,
        parameters TEXT,  -- JSON string
        description TEXT,
        status TEXT DEFAULT 'completed'
    );

    -- Individual poster results
    CREATE TABLE IF NOT EXISTS poster_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id INTEGER NOT NULL,
        content_id INTEGER NOT NULL,
        program_id INTEGER,
        title TEXT,
        content_type TEXT,
        sot_name TEXT,
        poster_url TEXT,
        has_elements BOOLEAN,
        confidence INTEGER,
        justification TEXT,
        analysis_json TEXT,  -- JSON string
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        qa_reviewed BOOLEAN DEFAULT 0,
        qa_modified_at TIMESTAMP,
        original_has_elements BOOLEAN,
        original_justification TEXT,
        FOREIGN KEY (run_id) REFERENCES analysis_runs(id)
    );

    -- Indexes for performance
    CREATE INDEX IF NOT EXISTS idx_run_id ON poster_results(run_id);
    CREATE INDEX IF NOT EXISTS idx_content_id ON poster_results(content_id);
    CREATE INDEX IF NOT EXISTS idx_has_elements ON poster_results(has_elements);
    CREATE INDEX IF NOT EXISTS idx_sot_name ON poster_results(sot_name);
    CREATE INDEX IF NOT EXISTS idx_created_at ON poster_results(created_at);
    CREATE INDEX IF NOT EXISTS idx_qa_reviewed ON poster_results(qa_reviewed);
    """
    
    with get_db_connection() as conn:
        conn.executescript(schema)
        logger.info("database_initialized", path=str(DB_PATH))


class AnalysisRun:
    """Model for analysis runs."""
    
    @staticmethod
    def create(total: int, passed: int, failed: int, parameters: Dict[str, Any], description: str = "") -> int:
        """Create a new analysis run and return its ID."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO analysis_runs (total_analyzed, pass_count, fail_count, parameters, description)
                VALUES (?, ?, ?, ?, ?)
            """, (total, passed, failed, json.dumps(parameters), description))
            return cursor.lastrowid
    
    @staticmethod
    def get_all(limit: int = 50) -> List[Dict[str, Any]]:
        """Get all analysis runs."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM analysis_runs 
                ORDER BY id DESC 
                LIMIT ?
            """, (limit,))
            return [dict(row) for row in cursor.fetchall()]
    
    @staticmethod
    def get_by_id(run_id: int) -> Optional[Dict[str, Any]]:
        """Get a specific analysis run."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM analysis_runs WHERE id = ?", (run_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    @staticmethod
    def get_latest() -> Optional[Dict[str, Any]]:
        """Get the most recent analysis run."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM analysis_runs ORDER BY id DESC LIMIT 1")
            row = cursor.fetchone()
            return dict(row) if row else None


class PosterResult:
    """Model for individual poster results."""
    
    @staticmethod
    def create_batch(run_id: int, results: List[Dict[str, Any]]) -> None:
        """Create multiple poster results at once."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            for result in results:
                # Extract analysis data
                analysis = result.get("analysis", {})
                red_zone = analysis.get("red_safe_zone", {})
                
                cursor.execute("""
                    INSERT INTO poster_results (
                        run_id, content_id, program_id, title, content_type,
                        sot_name, poster_url, has_elements, confidence,
                        justification, analysis_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    run_id,
                    result.get("content_id"),
                    result.get("program_id"),
                    result.get("content_name") or result.get("title"),
                    result.get("content_type"),
                    result.get("sot_name", "unknown"),
                    result.get("poster_img_url") or result.get("poster_url"),
                    red_zone.get("contains_key_elements"),
                    red_zone.get("confidence"),
                    red_zone.get("justification"),
                    json.dumps(analysis) if analysis else None
                ))
    
    @staticmethod
    def get_by_run(run_id: int, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Get all results for a specific run with optional filters."""
        query = "SELECT * FROM poster_results WHERE run_id = ?"
        params = [run_id]
        
        if filters:
            if "has_elements" in filters:
                query += " AND has_elements = ?"
                params.append(filters["has_elements"])
            
            if "sot_name" in filters:
                query += " AND sot_name = ?"
                params.append(filters["sot_name"])
            
            if "search" in filters:
                query += " AND (title LIKE ? OR justification LIKE ?)"
                search_term = f"%{filters['search']}%"
                params.extend([search_term, search_term])
        
        query += " ORDER BY confidence DESC, title ASC"
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
    
    @staticmethod
    def get_stats(run_id: Optional[int] = None) -> Dict[str, Any]:
        """Get statistics for a run or all runs."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            if run_id:
                base_query = "FROM poster_results WHERE run_id = ?"
                params = [run_id]
                where_clause = " AND"
            else:
                base_query = "FROM poster_results"
                params = []
                where_clause = " WHERE"
            
            # Total count
            cursor.execute(f"SELECT COUNT(*) {base_query}", params)
            total = cursor.fetchone()[0]
            
            # Pass/fail counts
            cursor.execute(f"SELECT COUNT(*) {base_query}{where_clause} has_elements = 0", params)
            passed = cursor.fetchone()[0]
            
            # Average confidence
            cursor.execute(f"SELECT AVG(confidence) {base_query}", params)
            avg_confidence = cursor.fetchone()[0] or 0
            
            # By SOT
            cursor.execute(f"""
                SELECT sot_name, 
                       COUNT(*) as total,
                       SUM(CASE WHEN has_elements = 0 THEN 1 ELSE 0 END) as passed
                {base_query}
                GROUP BY sot_name
            """, params)
            
            sot_stats = {}
            for row in cursor.fetchall():
                sot_stats[row[0]] = {
                    "total": row[1],
                    "passed": row[2],
                    "failed": row[1] - row[2],
                    "fail_rate": (row[1] - row[2]) / row[1] * 100 if row[1] > 0 else 0
                }
            
            return {
                "total": total,
                "passed": passed,
                "failed": total - passed,
                "fail_rate": (total - passed) / total * 100 if total > 0 else 0,
                "avg_confidence": round(avg_confidence, 1),
                "by_sot": sot_stats
            }
    
    @staticmethod
    def get_trending_data(days: int = 30) -> List[Dict[str, Any]]:
        """Get daily statistics for the last N days."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    DATE(created_at) as date,
                    COUNT(*) as total,
                    SUM(CASE WHEN has_elements = 0 THEN 1 ELSE 0 END) as passed
                FROM poster_results
                WHERE created_at >= DATE('now', ? || ' days')
                GROUP BY DATE(created_at)
                ORDER BY date ASC
            """, (f"-{days}",))
            
            return [
                {
                    "date": row[0],
                    "total": row[1],
                    "passed": row[2],
                    "failed": row[1] - row[2],
                    "fail_rate": (row[1] - row[2]) / row[1] * 100 if row[1] > 0 else 0
                }
                for row in cursor.fetchall()
            ]
    
    @staticmethod
    def update_qa_status(result_id: int, has_elements: bool, justification: str) -> bool:
        """Update a result's QA status and values."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # First get the original values if not already stored
            cursor.execute("""
                SELECT has_elements, justification, original_has_elements, original_justification
                FROM poster_results
                WHERE id = ?
            """, (result_id,))
            
            row = cursor.fetchone()
            if not row:
                return False
            
            current_has_elements, current_justification, orig_has_elements, orig_justification = row
            
            # Store original values if this is the first QA edit
            if orig_has_elements is None:
                orig_has_elements = current_has_elements
                orig_justification = current_justification
            
            # Update the result
            cursor.execute("""
                UPDATE poster_results
                SET has_elements = ?,
                    justification = ?,
                    qa_reviewed = 1,
                    qa_modified_at = CURRENT_TIMESTAMP,
                    original_has_elements = ?,
                    original_justification = ?
                WHERE id = ?
            """, (has_elements, justification, orig_has_elements, orig_justification, result_id))
            
            logger.info(
                "poster_result_qa_updated",
                result_id=result_id,
                has_elements=has_elements,
                was_modified=True
            )
            
            return True
    
    @staticmethod
    def get_by_id(result_id: int) -> Optional[Dict[str, Any]]:
        """Get a single poster result by ID."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM poster_results WHERE id = ?", (result_id,))
            row = cursor.fetchone()
            return dict(row) if row else None


def import_json_results(json_file: Path, description: str = "") -> int:
    """Import results from a JSON file and create a new run."""
    with open(json_file) as f:
        results = json.load(f)
    
    # Calculate stats
    total = len(results)
    passed = sum(1 for r in results if not r.get("analysis", {}).get("red_safe_zone", {}).get("contains_key_elements", True))
    failed = total - passed
    
    # Extract parameters from first result
    parameters = {
        "source": "json_import",
        "file": json_file.name,
        "timestamp": datetime.now().isoformat()
    }
    
    # Create run
    run_id = AnalysisRun.create(total, passed, failed, parameters, description)
    
    # Create results
    PosterResult.create_batch(run_id, results)
    
    logger.info(
        "json_results_imported",
        run_id=run_id,
        total=total,
        passed=passed,
        failed=failed,
        file=str(json_file)
    )
    
    return run_id


if __name__ == "__main__":
    # Initialize database when run directly
    init_database()
    print(f"Database initialized at {DB_PATH}")
