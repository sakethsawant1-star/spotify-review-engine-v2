"""
analyzer.py — Main orchestrator for Phase 4 LLM Analysis Agent.
=============================================================
Refactored to use the unified 2-pass SpotifyReviewAgent (adopted from M3
Groww agent architecture). Replaces the previous 3-module approach
(theme_sentiment_classifier + quote_extractor + pattern_detector) with
a single agent that does classification + quote extraction in Pass 1 and
synthesis + pattern detection in Pass 2.

Usage:
  python analyzer.py                     # Run analysis on all processed reviews
  python analyzer.py --clear             # Clear previous analysis results and run fresh
  python analyzer.py --run-id <run_id>   # Update an existing pipeline run record
  python analyzer.py --dry-run           # Run LLM analysis and print output without saving to DB
"""

import os
import sys
import json
import time
import logging
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

# Ensure we can import modules from phase1-setup
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "phase1-setup"))

import config
from db import DatabaseManager

# Import Phase 4 unified agent
sys.path.insert(0, str(PROJECT_ROOT / "phase4-agent"))
from gemini_agent import SpotifyReviewAgent

# Fix Windows terminal encoding for Unicode output
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Configure logging
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("analyzer")


def load_processed_reviews() -> List[Dict[str, Any]]:
    """Loads all reviews from the processed_reviews table."""
    db = DatabaseManager()
    with db.connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM processed_reviews")
        rows = cursor.fetchall()

    reviews = []
    for r in rows:
        if isinstance(r, tuple):
            reviews.append({
                "id": r[0], "source": r[1], "rating": r[2], "text": r[3],
                "date": r[4], "word_count": r[5],
                "discovery_keywords": json.loads(r[6]) if isinstance(r[6], str) else (r[6] or []),
                "engagement_score": r[7]
            })
        else:
            reviews.append({
                "id": r["id"], "source": r["source"], "rating": r["rating"],
                "text": r["text"], "date": r["date"], "word_count": r["word_count"],
                "discovery_keywords": json.loads(r["discovery_keywords"]) if r["discovery_keywords"] else [],
                "engagement_score": r["engagement_score"]
            })
    return reviews


def save_analysis_results(results: List[Dict[str, Any]]) -> int:
    """Saves classification results to the analysis_results table."""
    if not results:
        return 0

    db = DatabaseManager()
    ph = db.placeholder
    saved = 0

    with db.connection() as conn:
        cursor = conn.cursor()
        for res in results:
            try:
                if db.use_postgres:
                    cursor.execute(
                        f"""
                        INSERT INTO analysis_results
                        (review_id, theme_ids, theme_confidence, sentiment, sentiment_confidence, signal_phrases)
                        VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph})
                        ON CONFLICT (review_id) DO UPDATE SET
                            theme_ids = EXCLUDED.theme_ids,
                            theme_confidence = EXCLUDED.theme_confidence,
                            sentiment = EXCLUDED.sentiment,
                            sentiment_confidence = EXCLUDED.sentiment_confidence,
                            signal_phrases = EXCLUDED.signal_phrases
                        """,
                        (
                            res["review_id"], res["theme_ids"], res["theme_confidence"],
                            res["sentiment"], res["sentiment_confidence"], res["signal_phrases"]
                        )
                    )
                else:
                    cursor.execute(
                        """
                        INSERT OR REPLACE INTO analysis_results
                        (review_id, theme_ids, theme_confidence, sentiment, sentiment_confidence, signal_phrases)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            res["review_id"], res["theme_ids"], res["theme_confidence"],
                            res["sentiment"], res["sentiment_confidence"], res["signal_phrases"]
                        )
                    )
                saved += 1
            except Exception as e:
                logger.error(f"Failed to save analysis result for review {res['review_id']}: {e}")

    return saved


def clear_analysis_data():
    """Clears the analysis_results table."""
    db = DatabaseManager()
    with db.connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM analysis_results")
        cursor.execute("UPDATE pipeline_runs SET status = 'failed' WHERE status = 'running'")
    logger.info("Cleared analysis_results table.")


def calculate_aggregates(classification_results: List[Dict[str, Any]]) -> tuple[Dict[str, Any], Dict[str, Any]]:
    """Calculates theme and sentiment distributions from classification results."""
    total = len(classification_results)
    if total == 0:
        return {}, {}

    theme_counts = {tid: 0 for tid in config.THEME_TAXONOMY.keys()}
    sentiment_counts = {sent: 0 for sent in config.SENTIMENT_CLASSES}

    for r in classification_results:
        # Theme IDs is a JSON array string
        tids = json.loads(r["theme_ids"] or "[]")
        for tid in tids:
            if tid in theme_counts:
                theme_counts[tid] += 1
            else:
                theme_counts[tid] = 1

        sent = r["sentiment"]
        if sent in sentiment_counts:
            sentiment_counts[sent] += 1
        else:
            sentiment_counts[sent] = 1

    themes_summary = {}
    for tid, count in theme_counts.items():
        themes_summary[tid] = {
            "name": config.THEME_TAXONOMY.get(tid, "Unknown"),
            "count": count,
            "pct": round((count / total) * 100, 2)
        }

    sentiment_summary = {}
    for sent, count in sentiment_counts.items():
        sentiment_summary[sent] = {
            "count": count,
            "pct": round((count / total) * 100, 2)
        }

    return themes_summary, sentiment_summary


def update_pipeline_run(
    run_id: str,
    started_at: str,
    total_raw: int,
    total_processed: int,
    total_analyzed: int,
    themes_summary: Dict[str, Any],
    sentiment_summary: Dict[str, Any],
    top_quotes: Dict[str, Any],
    behavior_patterns: Dict[str, Any],
    status: str = "completed"
):
    """Updates a pipeline run entry in the pipeline_runs table."""
    db = DatabaseManager()
    ph = db.placeholder
    completed_at = datetime.now().isoformat()

    with db.connection() as conn:
        cursor = conn.cursor()

        cursor.execute(f"SELECT 1 FROM pipeline_runs WHERE run_id = {ph}", (run_id,))
        exists = cursor.fetchone()

        if exists:
            cursor.execute(
                f"""
                UPDATE pipeline_runs
                SET completed_at = {ph},
                    total_raw = {ph},
                    total_processed = {ph},
                    total_analyzed = {ph},
                    themes_summary = {ph},
                    sentiment_summary = {ph},
                    top_quotes = {ph},
                    behavior_patterns = {ph},
                    status = {ph}
                WHERE run_id = {ph}
                """,
                (
                    completed_at, total_raw, total_processed, total_analyzed,
                    json.dumps(themes_summary), json.dumps(sentiment_summary),
                    json.dumps(top_quotes), json.dumps(behavior_patterns),
                    status, run_id
                )
            )
        else:
            cursor.execute(
                f"""
                INSERT INTO pipeline_runs
                (run_id, started_at, completed_at, total_raw, total_processed, total_analyzed,
                 themes_summary, sentiment_summary, top_quotes, behavior_patterns, status)
                VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})
                """,
                (
                    run_id, started_at, completed_at, total_raw, total_processed, total_analyzed,
                    json.dumps(themes_summary), json.dumps(sentiment_summary),
                    json.dumps(top_quotes), json.dumps(behavior_patterns), status
                )
            )

    logger.info(f"Pipeline run {run_id} updated with status: {status}")


def run_analysis(run_id: str = None, dry_run: bool = False, clear: bool = False, limit: int = None) -> Dict[str, Any]:
    """Runs the full Phase 4 analysis pipeline using the unified 2-pass agent."""
    start_time = time.time()
    started_at = datetime.now().isoformat()

    # 1. Initialize run_id
    db_mgr = DatabaseManager()
    if not run_id and not dry_run:
        run_id = db_mgr.create_pipeline_run()
        logger.info(f"Created new pipeline run: {run_id}")
    elif dry_run:
        run_id = "dry_run"
        logger.info("Dry run enabled — no data will be saved to the database.")
    else:
        logger.info(f"Using provided pipeline run: {run_id}")

    print()
    print("=" * 60)
    print("  🤖 Phase 4 — LLM Analysis Agent (Refactored 2-Pass)")
    print("=" * 60)
    print()

    # Clear previous results if requested
    if clear and not dry_run:
        clear_analysis_data()
        print("  [✓] Cleared previous analysis results")
        print()

    try:
        # Load processed reviews
        print("  ⏳ Loading processed reviews...")
        processed_reviews = load_processed_reviews()
        total_processed = len(processed_reviews)
        print(f"  [✓] Loaded {total_processed} processed reviews")

        # Load raw reviews count for metrics
        db = DatabaseManager()
        with db.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM raw_reviews")
            total_raw = cursor.fetchone()[0]
        print(f"  [✓] Current total raw reviews in DB: {total_raw}")
        print()

        if total_processed == 0:
            print("  [!] No processed reviews found. Run Phase 3 pipeline first.")
            return {"status": "no_data"}

        # Filter out already analyzed reviews (resume support)
        with db.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT review_id FROM analysis_results")
            analyzed_ids = {row[0] for row in cursor.fetchall()}

        unprocessed_reviews = [r for r in processed_reviews if r["id"] not in analyzed_ids]
        print(f"  [!] Found {len(analyzed_ids)} already analyzed reviews. "
              f"{len(unprocessed_reviews)} remaining to analyze.")

        if limit:
            reviews_to_analyze = unprocessed_reviews[:limit]
            print(f"  [!] Limiting analysis to {limit} reviews as requested.")
        else:
            reviews_to_analyze = unprocessed_reviews

        total_to_analyze = len(reviews_to_analyze)

        if total_to_analyze == 0:
            print("  [!] All reviews already analyzed. Skipping to aggregation.")
        else:
            # 2. Run the unified 2-pass agent
            print(f"\n  ⏳ Initializing unified agent (batch_size={config.BATCH_SIZE})...")
            agent = SpotifyReviewAgent()
            agent_result = agent.analyze_reviews(reviews_to_analyze, batch_size=config.BATCH_SIZE)

            # 3. Save classification results
            classification_results = agent_result["classification_results"]

            if not dry_run:
                print("  💾 Saving classification results to database...")
                saved = save_analysis_results(classification_results)
                print(f"  [✓] Saved {saved} analysis records")
                print()
            else:
                print("  [DRY RUN] Skipping database save of classification results")
                print()

        # 4. Calculate aggregates from ALL classification results (including previously analyzed)
        print("  ⏳ Calculating aggregates...")

        if dry_run and total_to_analyze > 0:
            # Use in-memory results for dry run
            all_classification = classification_results
        else:
            # Query all results from DB
            with db.connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT review_id, theme_ids, sentiment FROM analysis_results")
                rows = cursor.fetchall()
            all_classification = []
            for row in rows:
                if isinstance(row, tuple):
                    all_classification.append({
                        "review_id": row[0],
                        "theme_ids": row[1] if isinstance(row[1], str) else json.dumps(row[1] or []),
                        "sentiment": row[2],
                    })
                else:
                    all_classification.append({
                        "review_id": row["review_id"],
                        "theme_ids": row["theme_ids"] if isinstance(row["theme_ids"], str) else json.dumps(row["theme_ids"] or []),
                        "sentiment": row["sentiment"],
                    })

        themes_summary, sentiment_summary = calculate_aggregates(all_classification)
        print("  [✓] Frequencies and distributions calculated")
        print()

        # 5. Get top_quotes and behavior_patterns from agent synthesis
        if total_to_analyze > 0:
            top_quotes = agent_result["top_quotes"]
            behavior_patterns = agent_result["behavior_patterns"]
        else:
            # If no new reviews, use empty defaults
            top_quotes = {}
            behavior_patterns = {"patterns": [], "executive_summary": "No new reviews to analyze."}

        # 6. Save pipeline run
        if not dry_run:
            print("  💾 Updating pipeline run in database...")
            update_pipeline_run(
                run_id=run_id,
                started_at=started_at,
                total_raw=total_raw,
                total_processed=total_processed,
                total_analyzed=total_to_analyze,
                themes_summary=themes_summary,
                sentiment_summary=sentiment_summary,
                top_quotes=top_quotes,
                behavior_patterns=behavior_patterns,
                status="completed"
            )
            print("  [✓] Pipeline run updated successfully")
            print()
        else:
            print("  [DRY RUN] Skipping database update of pipeline run")
            print()

        # 7. Print Dashboard Summary
        total_time = round(time.time() - start_time, 2)

        print("─" * 60)
        print("  📊 LLM Analysis Dashboard")
        print("─" * 60)
        print(f"  Run ID:                   {run_id}")
        print(f"  Total processed reviews:  {total_processed:>6}")
        print(f"  Total analyzed reviews:   {total_to_analyze:>6}")
        print(f"  Total analysis time:      {total_time:>5.1f}s")
        print("  ──────────────────────────────────")
        print("  Theme Distribution:")
        for tid, data in sorted(themes_summary.items(), key=lambda x: x[1]["count"], reverse=True):
            print(f"    {tid} - {data['name']:<25}: {data['count']:>4} ({data['pct']:.1f}%)")
        print("  ──────────────────────────────────")
        print("  Sentiment Breakdown:")
        for sent, data in sorted(sentiment_summary.items(), key=lambda x: x[1]["count"], reverse=True):
            print(f"    {sent:<12}: {data['count']:>4} ({data['pct']:.1f}%)")
        print("  ──────────────────────────────────")
        print("  Behavior Patterns Detected:")
        for pat in behavior_patterns.get("patterns", []):
            print(f"    - [{pat.get('category', 'unknown').upper()}] {pat.get('title', 'Unnamed')} "
                  f"(Severity: {pat.get('severity', 'unknown').upper()})")
        print("─" * 60)
        print("  ✅ Phase 4 analysis complete!")
        print("=" * 60)
        print()

        return {
            "status": "completed",
            "run_id": run_id,
            "total_analyzed": total_to_analyze,
            "themes_summary": themes_summary,
            "sentiment_summary": sentiment_summary,
            "top_quotes": top_quotes,
            "behavior_patterns": behavior_patterns
        }

    except Exception as e:
        logger.error(f"Analysis pipeline failed: {e}", exc_info=True)
        if not dry_run and run_id:
            try:
                db = DatabaseManager()
                ph = db.placeholder
                with db.connection() as conn:
                    conn.cursor().execute(
                        f"UPDATE pipeline_runs SET status = 'failed' WHERE run_id = {ph}",
                        (run_id,)
                    )
            except Exception as db_err:
                logger.error(f"Failed to set pipeline status to failed: {db_err}")
        return {"status": "failed", "error": str(e)}


def main():
    parser = argparse.ArgumentParser(
        description="Phase 4 — LLM Analysis Agent for Review Discovery Engine"
    )
    parser.add_argument(
        "--run-id",
        help="Specify an existing run_id to update in pipeline_runs",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run analysis without saving to the database",
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear analysis_results table before run",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit the number of reviews to analyze",
    )

    args = parser.parse_args()

    result = run_analysis(
        run_id=args.run_id,
        dry_run=args.dry_run,
        clear=args.clear,
        limit=args.limit,
    )

    sys.exit(0 if result.get("status") == "completed" else 1)


if __name__ == "__main__":
    main()
