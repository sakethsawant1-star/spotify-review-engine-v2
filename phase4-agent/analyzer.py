"""
analyzer.py — Main orchestrator for Phase 4 LLM Analysis Agent.
=============================================================
Loads processed reviews from SQLite database, runs theme & sentiment classification,
extracts representative quotes per theme, detects behavior patterns across the corpus,
and updates SQLite database with final analysis results and pipeline run stats.

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

# Import Phase 4 modules
sys.path.insert(0, str(PROJECT_ROOT / "phase4-agent"))
from theme_sentiment_classifier import ThemeSentimentClassifier
from quote_extractor import QuoteExtractor
from pattern_detector import PatternDetector

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


def get_combined_reviews_data() -> List[Dict[str, Any]]:
    """Fetches combined data from processed_reviews and analysis_results."""
    db = DatabaseManager()
    with db.connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT p.*, a.theme_ids, a.sentiment
            FROM processed_reviews p
            JOIN analysis_results a ON p.id = a.review_id
            """
        )
        rows = cursor.fetchall()

    reviews = []
    for r in rows:
        if isinstance(r, tuple):
            reviews.append({
                "id": r[0], "source": r[1], "rating": r[2], "text": r[3],
                "date": r[4], "engagement_score": r[7],
                "theme_ids": r[9] if isinstance(r[9], str) else json.dumps(r[9] or []),
                "sentiment": r[10] if len(r) > 10 else r[9]
            })
        else:
            reviews.append({
                "id": r["id"], "source": r["source"], "rating": r["rating"],
                "text": r["text"], "date": r["date"],
                "engagement_score": r["engagement_score"],
                "theme_ids": r["theme_ids"],
                "sentiment": r["sentiment"]
            })
    return reviews


def calculate_aggregates(reviews: List[Dict[str, Any]]) -> tuple[Dict[str, Any], Dict[str, Any]]:
    """Calculates theme and sentiment distributions."""
    total = len(reviews)
    if total == 0:
        return {}, {}

    theme_counts = {tid: 0 for tid in config.THEME_TAXONOMY.keys()}
    sentiment_counts = {sent: 0 for sent in config.SENTIMENT_CLASSES}

    for r in reviews:
        # Theme IDs is a JSON array string in DB
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
    """Runs the full Phase 4 analysis pipeline."""
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
    print("  🤖 Phase 4 — LLM Analysis Agent")
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
            total_raw = conn.cursor().execute("SELECT COUNT(*) FROM raw_reviews").fetchone()[0]
        print(f"  [✓] Current total raw reviews in DB: {total_raw}")
        print()

        if total_processed == 0:
            print("  [!] No processed reviews found. Run Phase 3 pipeline first.")
            return {"status": "no_data"}

        # 2. Theme and Sentiment Classification in Batches
        print("  ⏳ Initializing classifier...")
        classifier = ThemeSentimentClassifier()
        
        # Fetch IDs of already analyzed reviews to resume where we left off
        with db.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT review_id FROM analysis_results")
            analyzed_ids = {row[0] for row in cursor.fetchall()}

        # Filter out already analyzed reviews
        unprocessed_reviews = [r for r in processed_reviews if r["id"] not in analyzed_ids]
        print(f"  [!] Found {len(analyzed_ids)} already analyzed reviews. {len(unprocessed_reviews)} remaining to analyze.")

        if limit:
            reviews_to_analyze = unprocessed_reviews[:limit]
            print(f"  [!] Limiting analysis to {limit} reviews as requested.")
        else:
            reviews_to_analyze = unprocessed_reviews
        
        total_to_analyze = len(reviews_to_analyze)
        print(f"  ⏳ Analyzing {total_to_analyze} reviews using Groq (batch size = {config.BATCH_SIZE})...")

        analysis_results = []
        batch_size = config.BATCH_SIZE
        
        for i in range(0, total_to_analyze, batch_size):
            batch = reviews_to_analyze[i:i + batch_size]
            print(f"     Processing batch {i//batch_size + 1} / {-(-total_to_analyze//batch_size)}...")
            batch_results = classifier.classify_batch(batch)
            analysis_results.extend(batch_results)

        print(f"  [✓] Completed classification for {len(analysis_results)} reviews")
        print()

        # Save classification results
        if not dry_run:
            print("  💾 Saving classification results to database...")
            saved = save_analysis_results(analysis_results)
            print(f"  [✓] Saved {saved} analysis records")
            print()
        else:
            print("  [DRY RUN] Skipping database save of classification results")
            print()

        # 3. Aggregate results and get combined data
        print("  ⏳ Calculating aggregates...")
        if dry_run:
            # Reconstruct combined data in-memory for dry run
            combined_reviews = []
            results_map = {res["review_id"]: res for res in analysis_results}
            for pr in processed_reviews:
                rid = pr["id"]
                if rid in results_map:
                    combined_reviews.append({
                        **pr,
                        "theme_ids": results_map[rid]["theme_ids"],
                        "sentiment": results_map[rid]["sentiment"]
                    })
        else:
            combined_reviews = get_combined_reviews_data()

        themes_summary, sentiment_summary = calculate_aggregates(combined_reviews)
        print("  [✓] Frequencies and distributions calculated")
        print()

        # 4. Extract quotes for each theme (7 calls total)
        print("  ⏳ Initializing quote extractor...")
        quote_extractor = QuoteExtractor()
        top_quotes = {}

        for theme_id in config.THEME_TAXONOMY.keys():
            # Filter reviews matching this theme
            theme_reviews = []
            for r in combined_reviews:
                tids = json.loads(r["theme_ids"] or "[]")
                if theme_id in tids:
                    theme_reviews.append(r)
            
            if theme_reviews:
                quotes = quote_extractor.extract_quotes_for_theme(theme_id, theme_reviews)
                top_quotes[theme_id] = quotes
            else:
                top_quotes[theme_id] = []

        print("  [✓] Quote extraction complete")
        print()

        # 5. Detect cross-corpus behavior patterns (1 call)
        print("  ⏳ Initializing pattern detector...")
        pattern_detector = PatternDetector()
        behavior_patterns = pattern_detector.detect_patterns(combined_reviews)
        print("  [✓] Behavior pattern synthesis complete")
        print()

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
            print(f"    - [{pat.get('category').upper()}] {pat.get('title')} (Severity: {pat.get('severity').upper()})")
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
