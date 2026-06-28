"""
migrate_to_postgres.py — One-time SQLite → PostgreSQL Migration Script
======================================================================
Exports all data from the local SQLite database and imports it into
the Supabase PostgreSQL database.

Usage:
  python migrate_to_postgres.py              # Run full migration
  python migrate_to_postgres.py --verify     # Verify data in PostgreSQL
  python migrate_to_postgres.py --dry-run    # Show what would be migrated
"""

import sys
import json
import sqlite3
import argparse
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT / "phase1-setup"))
import config

# We need psycopg2 for this script
try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    print("[X] psycopg2 not installed. Run: pip install psycopg2-binary")
    sys.exit(1)


TABLES = [
    {
        "name": "raw_reviews",
        "columns": "id, source, rating, title, text, date, metadata, scraped_at",
        "col_count": 8,
    },
    {
        "name": "processed_reviews",
        "columns": "id, source, rating, text, date, word_count, discovery_keywords, engagement_score, processed_at",
        "col_count": 9,
    },
    {
        "name": "analysis_results",
        "columns": "review_id, theme_ids, theme_confidence, sentiment, sentiment_confidence, signal_phrases, analyzed_at",
        "col_count": 7,
    },
    {
        "name": "pipeline_runs",
        "columns": "run_id, started_at, completed_at, total_raw, total_processed, total_analyzed, themes_summary, sentiment_summary, top_quotes, behavior_patterns, status",
        "col_count": 11,
    },
]

# JSON columns that need to be converted from string to native JSONB
JSON_COLUMNS = {
    "raw_reviews": [6],         # metadata
    "processed_reviews": [6],   # discovery_keywords
    "analysis_results": [1, 5], # theme_ids, signal_phrases
    "pipeline_runs": [6, 7, 8, 9],  # themes_summary, sentiment_summary, top_quotes, behavior_patterns
}


def get_sqlite_conn():
    """Connect to local SQLite database."""
    conn = sqlite3.connect(str(config.DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def get_pg_conn():
    """Connect to Supabase PostgreSQL."""
    if not config.DATABASE_URL:
        print("[X] DATABASE_URL not set in .env")
        sys.exit(1)
    return psycopg2.connect(config.DATABASE_URL)


def create_pg_tables(pg_conn):
    """Create tables in PostgreSQL using the schema from db.py."""
    from db import DatabaseManager
    # Force postgres mode temporarily
    original = config.USE_POSTGRES
    config.USE_POSTGRES = True

    db = DatabaseManager()
    # Use the pg_conn we already have
    cursor = pg_conn.cursor()

    from db import PG_RAW_REVIEWS, PG_PROCESSED_REVIEWS, PG_ANALYSIS_RESULTS, PG_PIPELINE_RUNS, CREATE_INDEXES

    for sql in [PG_RAW_REVIEWS, PG_PROCESSED_REVIEWS, PG_ANALYSIS_RESULTS, PG_PIPELINE_RUNS]:
        cursor.execute(sql)
    for idx in CREATE_INDEXES:
        cursor.execute(idx)

    pg_conn.commit()
    print("  [OK] PostgreSQL tables created")
    config.USE_POSTGRES = original


def migrate_table(sqlite_conn, pg_conn, table_info, dry_run=False):
    """Migrate a single table from SQLite to PostgreSQL."""
    name = table_info["name"]
    columns = table_info["columns"]
    col_count = table_info["col_count"]
    json_cols = JSON_COLUMNS.get(name, [])

    # Read from SQLite
    cursor = sqlite_conn.cursor()
    cursor.execute(f"SELECT {columns} FROM {name}")
    rows = cursor.fetchall()

    if not rows:
        print(f"  [{name}] 0 rows — skipping")
        return 0

    if dry_run:
        print(f"  [{name}] {len(rows)} rows — would be migrated")
        return len(rows)

    # Prepare for PostgreSQL insert
    placeholders = ", ".join(["%s"] * col_count)
    insert_sql = f"INSERT INTO {name} ({columns}) VALUES ({placeholders}) ON CONFLICT DO NOTHING"

    pg_cursor = pg_conn.cursor()
    batch = []
    for row in rows:
        values = list(row)
        # Convert JSON string columns to Python dicts for JSONB
        for idx in json_cols:
            if idx < len(values) and isinstance(values[idx], str):
                try:
                    values[idx] = json.loads(values[idx])
                except (json.JSONDecodeError, TypeError):
                    pass
        # Convert to psycopg2 Json for JSONB columns
        for idx in json_cols:
            if idx < len(values) and values[idx] is not None:
                values[idx] = psycopg2.extras.Json(values[idx])
        batch.append(tuple(values))

    # Batch insert
    psycopg2.extras.execute_batch(pg_cursor, insert_sql, batch, page_size=500)
    pg_conn.commit()

    print(f"  [{name}] {len(rows)} rows migrated")
    return len(rows)


def verify_pg(pg_conn):
    """Verify data in PostgreSQL."""
    cursor = pg_conn.cursor()
    print("\n  PostgreSQL table counts:")
    for table_info in TABLES:
        name = table_info["name"]
        cursor.execute(f"SELECT COUNT(*) FROM {name}")
        count = cursor.fetchone()[0]
        print(f"    {name}: {count} rows")


def main():
    parser = argparse.ArgumentParser(description="Migrate SQLite → PostgreSQL")
    parser.add_argument("--verify", action="store_true", help="Verify PostgreSQL data")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be migrated")
    args = parser.parse_args()

    print("=" * 60)
    print("  SQLite → PostgreSQL Migration")
    print("=" * 60)
    print()

    if args.verify:
        pg_conn = get_pg_conn()
        verify_pg(pg_conn)
        pg_conn.close()
        print("\n  [OK] Verification complete.")
        return

    # Connect to both databases
    sqlite_conn = get_sqlite_conn()
    pg_conn = get_pg_conn()

    # Step 1: Create tables in PostgreSQL
    if not args.dry_run:
        print("  Step 1: Creating PostgreSQL tables...")
        create_pg_tables(pg_conn)
        print()

    # Step 2: Migrate each table
    print("  Step 2: Migrating data...")
    total = 0
    for table_info in TABLES:
        count = migrate_table(sqlite_conn, pg_conn, table_info, dry_run=args.dry_run)
        total += count

    print(f"\n  Total: {total} rows {'would be ' if args.dry_run else ''}migrated")

    # Step 3: Verify
    if not args.dry_run:
        print("\n  Step 3: Verifying...")
        verify_pg(pg_conn)

    sqlite_conn.close()
    pg_conn.close()

    print()
    print("=" * 60)
    print("  [OK] Migration complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
