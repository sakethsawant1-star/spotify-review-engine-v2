"""
run_pipeline.py — Phase 3 Pipeline Orchestrator
=================================================
Chains the 4 data processing steps in sequence:

  raw_reviews table
    → cleaner.py        (HTML strip, Unicode normalize, English filter)
    → pii_remover.py    (regex + NER PII stripping)
    → deduplicator.py   (exact + fuzzy dedup)
    → relevance_filter.py (discovery keyword matching)
    → INSERT INTO processed_reviews

Usage:
  python run_pipeline.py                    # Process all raw reviews
  python run_pipeline.py --limit 500        # Process first 500 raw reviews
  python run_pipeline.py --source play_store  # Process only Play Store reviews
  python run_pipeline.py --dry-run          # Run pipeline but don't save to DB
  python run_pipeline.py --clear            # Clear processed_reviews before run

Exit codes:
  0 = Success
  1 = Error
"""

import sys
import json
import time
import logging
import argparse
from pathlib import Path
from datetime import datetime

# Fix Windows terminal encoding for Unicode output
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Add phase1-setup to path for config & db imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "phase1-setup"))
import config
from db import DatabaseManager

# Import pipeline modules
from cleaner import clean_reviews
from pii_remover import remove_pii_batch
from deduplicator import deduplicate
from relevance_filter import filter_relevant

# ──────────────────────────────────────────────
# Logging Setup
# ──────────────────────────────────────────────

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("pipeline")


# ──────────────────────────────────────────────
# Data Loading
# ──────────────────────────────────────────────

def load_raw_reviews(
    source: str = None,
    limit: int = None,
) -> list[dict]:
    """
    Load raw reviews from the database.
    """
    db = DatabaseManager()
    ph = db.placeholder

    query = "SELECT * FROM raw_reviews"
    params = []

    if source:
        query += f" WHERE source = {ph}"
        params.append(source)

    query += " ORDER BY scraped_at DESC"

    if limit:
        query += f" LIMIT {ph}"
        params.append(limit)

    with db.connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()

    reviews = []
    for row in rows:
        if isinstance(row, tuple):
            # psycopg2 returns tuples — use index
            reviews.append({
                "id": row[0],
                "source": row[1],
                "rating": row[2],
                "title": row[3],
                "text": row[4],
                "date": row[5],
                "metadata": json.loads(row[6]) if isinstance(row[6], str) else (row[6] or {}),
            })
        else:
            reviews.append({
                "id": row["id"],
                "source": row["source"],
                "rating": row["rating"],
                "title": row["title"],
                "text": row["text"],
                "date": row["date"],
                "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
            })

    return reviews


# ──────────────────────────────────────────────
# Saving to processed_reviews
# ──────────────────────────────────────────────

def save_processed_reviews(reviews: list[dict]) -> int:
    """
    Save processed reviews to the processed_reviews table.
    Uses INSERT OR REPLACE (SQLite) or ON CONFLICT (PostgreSQL).
    Returns number of reviews saved.
    """
    if not reviews:
        return 0

    db = DatabaseManager()
    ph = db.placeholder
    saved = 0

    with db.connection() as conn:
        cursor = conn.cursor()

        for review in reviews:
            try:
                if db.use_postgres:
                    cursor.execute(
                        f"""
                        INSERT INTO processed_reviews
                        (id, source, rating, text, date, word_count, discovery_keywords, engagement_score)
                        VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})
                        ON CONFLICT (id) DO UPDATE SET
                            source = EXCLUDED.source,
                            rating = EXCLUDED.rating,
                            text = EXCLUDED.text,
                            date = EXCLUDED.date,
                            word_count = EXCLUDED.word_count,
                            discovery_keywords = EXCLUDED.discovery_keywords,
                            engagement_score = EXCLUDED.engagement_score
                        """,
                        (
                            review["id"],
                            review["source"],
                            review.get("rating"),
                            review["text"],
                            review.get("date"),
                            review.get("word_count", len(review["text"].split())),
                            json.dumps(review.get("discovery_keywords", [])),
                            review.get("engagement_score", 0),
                        ),
                    )
                else:
                    cursor.execute(
                        """
                        INSERT OR REPLACE INTO processed_reviews
                        (id, source, rating, text, date, word_count, discovery_keywords, engagement_score)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            review["id"],
                            review["source"],
                            review.get("rating"),
                            review["text"],
                            review.get("date"),
                            review.get("word_count", len(review["text"].split())),
                            json.dumps(review.get("discovery_keywords", [])),
                            review.get("engagement_score", 0),
                        ),
                    )
                saved += 1
            except Exception as e:
                logger.error(f"Failed to save review {review['id']}: {e}")

    return saved


def clear_processed_reviews():
    """Clear the processed_reviews table (and dependent analysis_results)."""
    db = DatabaseManager()
    with db.connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM analysis_results")
        except Exception:
            pass
        cursor.execute("DELETE FROM processed_reviews")
    logger.info("Cleared processed_reviews table")


# ──────────────────────────────────────────────
# Pipeline Orchestrator
# ──────────────────────────────────────────────

def run_pipeline(
    source: str = None,
    limit: int = None,
    dry_run: bool = False,
    clear: bool = False,
) -> dict:
    """
    Run the full Phase 3 data pipeline.
    
    Args:
        source: Filter raw reviews by source
        limit: Maximum number of raw reviews to process
        dry_run: If True, run pipeline but don't save to DB
        clear: If True, clear processed_reviews before run
    
    Returns:
        Summary dict with counts at each pipeline step
    """
    start_time = time.time()
    summary = {
        "started_at": datetime.now().isoformat(),
        "source_filter": source,
        "limit": limit,
        "dry_run": dry_run,
    }

    print()
    print("=" * 60)
    print("  🔧 Phase 3 — Data Processing Pipeline")
    print("=" * 60)
    print()

    # ── Step 0: Clear (if requested) ──
    if clear and not dry_run:
        clear_processed_reviews()
        print("  [✓] Cleared existing processed reviews")
        print()

    # ── Step 1: Load raw reviews ──
    print("  ⏳ Step 1/4: Loading raw reviews...")
    raw_reviews = load_raw_reviews(source=source, limit=limit)
    summary["raw_count"] = len(raw_reviews)
    print(f"  [✓] Loaded {len(raw_reviews)} raw reviews")

    if not raw_reviews:
        print("  [!] No raw reviews found. Run Phase 2 scrapers first.")
        summary["status"] = "no_data"
        return summary

    # Show source distribution
    source_counts = {}
    for r in raw_reviews:
        source_counts[r["source"]] = source_counts.get(r["source"], 0) + 1
    for src, count in sorted(source_counts.items()):
        print(f"      {src}: {count}")
    print()

    # ── Step 2: Cleaning ──
    print("  ⏳ Step 2/4: Cleaning & normalizing...")
    t0 = time.time()
    cleaned = clean_reviews(raw_reviews)
    summary["cleaned_count"] = len(cleaned)
    summary["cleaning_time"] = round(time.time() - t0, 2)
    print(f"  [✓] {len(raw_reviews)} → {len(cleaned)} reviews "
          f"({len(raw_reviews) - len(cleaned)} removed) [{summary['cleaning_time']}s]")
    print()

    # ── Step 3: PII Removal ──
    print("  ⏳ Step 3/4: Removing PII...")
    t0 = time.time()
    pii_stripped = remove_pii_batch(cleaned)
    summary["pii_stripped_count"] = len(pii_stripped)
    summary["pii_time"] = round(time.time() - t0, 2)

    # Count total PII items removed
    total_pii = sum(
        sum(r.get("_pii_removed", {}).values())
        for r in pii_stripped
    )
    summary["pii_items_redacted"] = total_pii

    print(f"  [✓] {len(cleaned)} → {len(pii_stripped)} reviews "
          f"({total_pii} PII items redacted) [{summary['pii_time']}s]")
    print()

    # Clean up internal _pii_removed metadata before next steps
    for r in pii_stripped:
        r.pop("_pii_removed", None)

    # ── Step 4a: Deduplication ──
    print("  ⏳ Step 4/4: Deduplicating...")
    t0 = time.time()
    deduped = deduplicate(pii_stripped)
    summary["deduped_count"] = len(deduped)
    summary["dedup_time"] = round(time.time() - t0, 2)
    print(f"  [✓] {len(pii_stripped)} → {len(deduped)} reviews "
          f"({len(pii_stripped) - len(deduped)} duplicates removed) [{summary['dedup_time']}s]")
    print()

    # ── Step 4b: Relevance Filter ──
    print("  ⏳ Applying relevance filter...")
    t0 = time.time()
    relevant = filter_relevant(deduped)
    summary["relevant_count"] = len(relevant)
    summary["filter_time"] = round(time.time() - t0, 2)
    print(f"  [✓] {len(deduped)} → {len(relevant)} discovery-relevant reviews "
          f"({len(deduped) - len(relevant)} filtered) [{summary['filter_time']}s]")
    print()

    # ── Save Results ──
    if dry_run:
        print("  [DRY RUN] Skipping database save")
        summary["saved_count"] = 0
    else:
        print("  💾 Saving to processed_reviews table...")
        saved = save_processed_reviews(relevant)
        summary["saved_count"] = saved
        print(f"  [✓] Saved {saved} processed reviews to database")
    print()

    # ── Summary ──
    total_time = round(time.time() - start_time, 2)
    summary["total_time"] = total_time
    summary["status"] = "completed"
    summary["completed_at"] = datetime.now().isoformat()

    drop_rate = round((1 - len(relevant) / len(raw_reviews)) * 100, 1) if raw_reviews else 0

    print("─" * 60)
    print("  📊 Pipeline Summary")
    print("─" * 60)
    print(f"  Raw reviews loaded:       {summary['raw_count']:>6}")
    print(f"  After cleaning:           {summary['cleaned_count']:>6}")
    print(f"  After PII removal:        {summary['pii_stripped_count']:>6}")
    print(f"  After deduplication:       {summary['deduped_count']:>6}")
    print(f"  After relevance filter:   {summary['relevant_count']:>6}")
    print(f"  Saved to DB:              {summary['saved_count']:>6}")
    print(f"  ──────────────────────────────────")
    print(f"  Total drop rate:          {drop_rate:>5}%")
    print(f"  Total time:               {total_time:>5.1f}s")
    print(f"  PII items redacted:       {summary['pii_items_redacted']:>6}")
    print()

    # Source distribution in output
    if relevant:
        print("  Output by source:")
        out_sources = {}
        for r in relevant:
            out_sources[r["source"]] = out_sources.get(r["source"], 0) + 1
        for src, count in sorted(out_sources.items()):
            pct = round(count / len(relevant) * 100, 1)
            print(f"    {src}: {count} ({pct}%)")
        print()

    print("=" * 60)
    print("  ✅ Phase 3 pipeline complete!")
    print("=" * 60)
    print()

    return summary


# ──────────────────────────────────────────────
# CLI Entry Point
# ──────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Phase 3 — Data Processing Pipeline for Review Discovery Engine"
    )
    parser.add_argument(
        "--source",
        choices=["play_store", "app_store", "reddit", "community"],
        help="Process reviews from a specific source only",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Maximum number of raw reviews to process",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run pipeline without saving to database",
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear processed_reviews table before run",
    )

    args = parser.parse_args()

    summary = run_pipeline(
        source=args.source,
        limit=args.limit,
        dry_run=args.dry_run,
        clear=args.clear,
    )

    # Exit with appropriate code
    sys.exit(0 if summary.get("status") == "completed" else 1)


if __name__ == "__main__":
    main()
