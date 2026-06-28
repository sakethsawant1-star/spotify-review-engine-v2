"""
run_scrapers.py -- Scraper Orchestrator
========================================
Runs all scrapers in sequence and prints a combined summary.
Each scraper saves directly to raw_reviews in the SQLite database.

Usage:
    python run_scrapers.py                    # Run all scrapers
    python run_scrapers.py --source play_store
    python run_scrapers.py --source app_store
    python run_scrapers.py --source reddit
"""

import sys
import time
import argparse
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "phase1-setup"))
import config
from db import DatabaseManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("run_scrapers")


def print_db_summary():
    """Print current row counts per source in raw_reviews."""
    db = DatabaseManager()
    with db.connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT source, COUNT(*) as cnt FROM raw_reviews GROUP BY source ORDER BY cnt DESC"
        )
        rows = cursor.fetchall()
        cursor.execute("SELECT COUNT(*) FROM raw_reviews")
        total = cursor.fetchone()[0]

    print("\n" + "=" * 50)
    print("  raw_reviews table summary")
    print("=" * 50)
    for row in rows:
        source = row[0] if isinstance(row, tuple) else row["source"]
        cnt = row[1] if isinstance(row, tuple) else row["cnt"]
        bar = "#" * (cnt // 20)
        print(f"  {source:<20} {cnt:>5}  {bar}")
    print(f"  {'TOTAL':<20} {total:>5}")
    print("=" * 50 + "\n")


def run_play_store(count: int):
    from playstore_scraper import PlayStoreScraper
    scraper = PlayStoreScraper()
    return scraper.run(count=count)


def run_app_store(count: int):
    from appstore_scraper import AppStoreScraper
    scraper = AppStoreScraper()
    return scraper.run(count=count)


def run_reddit(count: int):
    from reddit_scraper import RedditScraper
    scraper = RedditScraper()
    return scraper.run(count=count)


SCRAPERS = {
    "play_store": (run_play_store, config.SCRAPER_TARGETS["play_store"]),
    "app_store":  (run_app_store,  config.SCRAPER_TARGETS["app_store"]),
    "reddit":     (run_reddit,     config.SCRAPER_TARGETS["reddit"]),
}


def main():
    parser = argparse.ArgumentParser(description="Run review scrapers")
    parser.add_argument(
        "--source",
        choices=list(SCRAPERS.keys()) + ["all"],
        default="all",
        help="Which scraper to run (default: all)",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=None,
        help="Override default target count for the selected source",
    )
    args = parser.parse_args()

    sources_to_run = list(SCRAPERS.keys()) if args.source == "all" else [args.source]
    all_summaries = []
    overall_start = time.time()

    print("\n" + "=" * 50)
    print("  Review Discovery Engine -- Scraper Run")
    print("=" * 50)
    print(f"  Sources: {', '.join(sources_to_run)}")
    print(f"  DB: {config.DB_PATH}")
    print("=" * 50 + "\n")

    for source in sources_to_run:
        fn, default_count = SCRAPERS[source]
        count = args.count if args.count else default_count

        logger.info(f"Running scraper: {source} (count={count})")
        try:
            summary = fn(count)
            all_summaries.append(summary)
        except Exception as e:
            logger.error(f"Scraper '{source}' failed: {e}")
            all_summaries.append({"source": source, "error": str(e)})

        # Brief pause between scrapers
        if source != sources_to_run[-1]:
            logger.info("Pausing 5s before next scraper...")
            time.sleep(5)

    total_duration = time.time() - overall_start

    # Print combined summary
    print("\n" + "=" * 50)
    print("  Scraper Run Complete")
    print("=" * 50)
    for s in all_summaries:
        if "error" in s:
            print(f"  [{s['source']}] ERROR: {s['error']}")
        else:
            print(
                f"  [{s['source']}] "
                f"fetched={s.get('fetched', 0)} | "
                f"saved={s.get('saved', 0)} | "
                f"skipped={s.get('skipped', 0)} | "
                f"db_total={s.get('total_in_db', 0)} | "
                f"time={s.get('duration_seconds', 0)}s"
            )
    print(f"\n  Total wall time: {total_duration:.1f}s")
    print("=" * 50)

    print_db_summary()


if __name__ == "__main__":
    main()
