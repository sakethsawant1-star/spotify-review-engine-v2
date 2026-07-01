"""
db.py — Database Manager for Review Discovery Engine
======================================================
Supports both SQLite (local development) and PostgreSQL (Supabase production).
Toggle via USE_POSTGRES=true in .env.

All modules should use DatabaseManager.get_connection() instead of raw
sqlite3.connect() or psycopg2.connect().

Usage:
  python db.py              # Creates database with all tables
  python db.py --verify     # Verifies existing database structure
"""

import sys
import sqlite3
import uuid
from pathlib import Path
from datetime import datetime
from contextlib import contextmanager

# Import config (handles path resolution)
sys.path.insert(0, str(Path(__file__).resolve().parent))
import config

# Always try to import psycopg2 so it's available when needed
_psycopg2 = None
try:
    import psycopg2
    import psycopg2.extras
    _psycopg2 = psycopg2
except ImportError as e:
    if config.USE_POSTGRES:
        raise RuntimeError(f"FATAL: USE_POSTGRES is true but psycopg2 failed to import: {e}")


# ──────────────────────────────────────────────
# SQL Schema Definitions (PostgreSQL-compatible)
# ──────────────────────────────────────────────

# SQLite schemas (original)
SQLITE_RAW_REVIEWS = """
CREATE TABLE IF NOT EXISTS raw_reviews (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    rating INTEGER,
    title TEXT,
    text TEXT NOT NULL,
    date TEXT,
    metadata JSON,
    scraped_at TEXT DEFAULT (datetime('now'))
);
"""

SQLITE_PROCESSED_REVIEWS = """
CREATE TABLE IF NOT EXISTS processed_reviews (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    rating INTEGER,
    text TEXT NOT NULL,
    date TEXT,
    word_count INTEGER,
    discovery_keywords JSON,
    engagement_score INTEGER,
    processed_at TEXT DEFAULT (datetime('now'))
);
"""

SQLITE_ANALYSIS_RESULTS = """
CREATE TABLE IF NOT EXISTS analysis_results (
    review_id TEXT PRIMARY KEY,
    theme_ids JSON,
    theme_confidence REAL,
    sentiment TEXT,
    sentiment_confidence REAL,
    signal_phrases JSON,
    analyzed_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (review_id) REFERENCES processed_reviews(id)
);
"""

SQLITE_PIPELINE_RUNS = """
CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_id TEXT PRIMARY KEY,
    started_at TEXT,
    completed_at TEXT,
    total_raw INTEGER,
    total_processed INTEGER,
    total_analyzed INTEGER,
    themes_summary JSON,
    sentiment_summary JSON,
    top_quotes JSON,
    behavior_patterns JSON,
    status TEXT DEFAULT 'running'
);
"""

# PostgreSQL schemas
PG_RAW_REVIEWS = """
CREATE TABLE IF NOT EXISTS raw_reviews (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    rating INTEGER,
    title TEXT,
    text TEXT NOT NULL,
    date TEXT,
    metadata JSONB,
    scraped_at TIMESTAMP DEFAULT NOW()
);
"""

PG_PROCESSED_REVIEWS = """
CREATE TABLE IF NOT EXISTS processed_reviews (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    rating INTEGER,
    text TEXT NOT NULL,
    date TEXT,
    word_count INTEGER,
    discovery_keywords JSONB,
    engagement_score INTEGER,
    processed_at TIMESTAMP DEFAULT NOW()
);
"""

PG_ANALYSIS_RESULTS = """
CREATE TABLE IF NOT EXISTS analysis_results (
    review_id TEXT PRIMARY KEY,
    theme_ids JSONB,
    theme_confidence DOUBLE PRECISION,
    sentiment TEXT,
    sentiment_confidence DOUBLE PRECISION,
    signal_phrases JSONB,
    analyzed_at TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY (review_id) REFERENCES processed_reviews(id)
);
"""

PG_PIPELINE_RUNS = """
CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_id TEXT PRIMARY KEY,
    started_at TEXT,
    completed_at TEXT,
    total_raw INTEGER,
    total_processed INTEGER,
    total_analyzed INTEGER,
    themes_summary JSONB,
    sentiment_summary JSONB,
    top_quotes JSONB,
    behavior_patterns JSONB,
    status TEXT DEFAULT 'running'
);
"""

# Indexes (same for both, syntax compatible)
CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_raw_source ON raw_reviews(source);",
    "CREATE INDEX IF NOT EXISTS idx_raw_date ON raw_reviews(date);",
    "CREATE INDEX IF NOT EXISTS idx_processed_source ON processed_reviews(source);",
    "CREATE INDEX IF NOT EXISTS idx_analysis_sentiment ON analysis_results(sentiment);",
    "CREATE INDEX IF NOT EXISTS idx_pipeline_status ON pipeline_runs(status);",
]


# ──────────────────────────────────────────────
# Database Manager Class
# ──────────────────────────────────────────────

class DatabaseManager:
    """
    Unified database manager supporting both SQLite and PostgreSQL.
    Toggle via config.USE_POSTGRES.
    """

    def __init__(self, db_path: Path = None):
        self.use_postgres = config.USE_POSTGRES and _psycopg2 is not None
        self.db_path = db_path or config.DB_PATH
        if not self.use_postgres:
            self._ensure_data_dir()

    def _ensure_data_dir(self):
        """Create the data directory if it doesn't exist (SQLite only)."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def placeholder(self) -> str:
        """Return the correct SQL placeholder for the current backend."""
        return "%s" if self.use_postgres else "?"

    def get_connection(self):
        """
        Get a database connection.
        Returns sqlite3.Connection or psycopg2.connection depending on config.
        """
        if self.use_postgres:
            conn = _psycopg2.connect(config.DATABASE_URL)
            return conn
        else:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA foreign_keys=ON;")
            return conn

    @contextmanager
    def connection(self):
        """Context manager that auto-commits and closes the connection."""
        conn = self.get_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def execute_query(self, query: str, params=None, fetch=False):
        """
        Execute a query, adapting placeholders from ? to %s if using PostgreSQL.
        """
        if self.use_postgres:
            query = query.replace("?", "%s")

        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params or ())
            if fetch:
                return cursor.fetchall()
            return cursor

    def initialize(self) -> bool:
        """Create all tables and indexes. Returns True on success."""
        try:
            if self.use_postgres:
                schemas = [
                    ("raw_reviews", PG_RAW_REVIEWS),
                    ("processed_reviews", PG_PROCESSED_REVIEWS),
                    ("analysis_results", PG_ANALYSIS_RESULTS),
                    ("pipeline_runs", PG_PIPELINE_RUNS),
                ]
            else:
                schemas = [
                    ("raw_reviews", SQLITE_RAW_REVIEWS),
                    ("processed_reviews", SQLITE_PROCESSED_REVIEWS),
                    ("analysis_results", SQLITE_ANALYSIS_RESULTS),
                    ("pipeline_runs", SQLITE_PIPELINE_RUNS),
                ]

            with self.connection() as conn:
                cursor = conn.cursor()
                for table_name, create_sql in schemas:
                    cursor.execute(create_sql)
                    print(f"  [OK] Table '{table_name}' ready")

                for index_sql in CREATE_INDEXES:
                    cursor.execute(index_sql)
                print(f"  [OK] {len(CREATE_INDEXES)} indexes created")

            return True

        except Exception as e:
            print(f"  [X] Database error: {e}")
            return False

    def verify(self) -> dict:
        """
        Verify database structure. Returns a dict with table names
        and their column counts.
        """
        if not self.use_postgres and not self.db_path.exists():
            return {"error": "Database file does not exist"}

        with self.connection() as conn:
            cursor = conn.cursor()

            if self.use_postgres:
                cursor.execute("""
                    SELECT table_name FROM information_schema.tables
                    WHERE table_schema = 'public'
                """)
                tables = [row[0] for row in cursor.fetchall()]
            else:
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                tables = [row[0] for row in cursor.fetchall()]

            result = {}
            for table in tables:
                if self.use_postgres:
                    cursor.execute(f"""
                        SELECT column_name FROM information_schema.columns
                        WHERE table_name = '{table}' AND table_schema = 'public'
                    """)
                    columns = [row[0] for row in cursor.fetchall()]
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    row_count = cursor.fetchone()[0]
                else:
                    cursor.execute(f"PRAGMA table_info({table});")
                    columns_data = cursor.fetchall()
                    columns = [col[1] for col in columns_data]
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    row_count = cursor.fetchone()[0]

                result[table] = {
                    "column_count": len(columns),
                    "columns": columns,
                    "row_count": row_count,
                }

        return result

    def create_pipeline_run(self) -> str:
        """Create a new pipeline run record. Returns the run_id."""
        run_id = str(uuid.uuid4())[:8]
        ph = self.placeholder
        with self.connection() as conn:
            cursor = conn.cursor()
            query = f"INSERT INTO pipeline_runs (run_id, started_at, status) VALUES ({ph}, {ph}, {ph})"
            cursor.execute(query, (run_id, datetime.now().isoformat(), "running"))
        return run_id

    def get_table_counts(self) -> dict:
        """Get row counts for all tables."""
        table_names = ["raw_reviews", "processed_reviews", "analysis_results", "pipeline_runs"]
        counts = {}
        with self.connection() as conn:
            cursor = conn.cursor()
            for table_name in table_names:
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                counts[table_name] = cursor.fetchone()[0]
        return counts


# ──────────────────────────────────────────────
# CLI Entry Point
# ──────────────────────────────────────────────

def main():
    """Initialize or verify the database."""
    print("=" * 50)
    print("  Review Discovery Engine -- Database Setup")
    print("=" * 50)
    print()

    db = DatabaseManager()
    backend = "PostgreSQL (Supabase)" if db.use_postgres else f"SQLite ({db.db_path})"
    print(f"  Backend: {backend}")
    print()

    if "--verify" in sys.argv:
        # Verification mode
        print("  Verifying database structure...")
        print()
        info = db.verify()

        if "error" in info:
            print(f"  [X] {info['error']}")
            sys.exit(1)

        for table_name, details in info.items():
            print(f"  [TABLE] {table_name}")
            print(f"     Columns ({details['column_count']}): {', '.join(details['columns'])}")
            print(f"     Rows: {details['row_count']}")
            print()

        print("  [OK] Verification complete.")

    else:
        # Initialization mode
        print("  Creating tables...")
        print()
        success = db.initialize()
        print()

        if success:
            if not db.use_postgres:
                db_size = db.db_path.stat().st_size
                print(f"  [OK] Database created successfully ({db_size:,} bytes)")
                print(f"  [OK] Location: {db.db_path}")
            else:
                print(f"  [OK] PostgreSQL tables created successfully")
            print()

            # Verify what we just created
            print("  Verifying...")
            info = db.verify()
            for table_name, details in info.items():
                cols = ", ".join(details["columns"])
                print(f"    {table_name}: {details['column_count']} columns — [{cols}]")
            print()
            print("  [OK] All tables verified. Database setup complete.")
        else:
            print("  [X] Database creation failed.")
            sys.exit(1)

    print()
    print("=" * 50)


if __name__ == "__main__":
    main()
