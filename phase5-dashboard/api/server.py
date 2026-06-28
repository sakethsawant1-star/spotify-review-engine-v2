"""
server.py — FastAPI backend for the Review Discovery Engine Dashboard.
====================================================================
Serves LLM analysis insights from the database to the frontend,
and allows triggering the full pipeline (scrapers + processing + LLM) asynchronously.
"""

from fastapi import FastAPI, BackgroundTasks, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import json
import subprocess
from pathlib import Path
import sys

# Fix Windows terminal encoding for Unicode output
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Ensure we can import modules from phase1-setup
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "phase1-setup"))
import config
from db import DatabaseManager

app = FastAPI(title="Review Discovery Engine API")

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static frontend files
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


def get_latest_run():
    """Fetches the most recent completed pipeline run from the database."""
    db = DatabaseManager()
    with db.connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM pipeline_runs ORDER BY started_at DESC LIMIT 1")
        row = cursor.fetchone()
    if not row:
        return None
    if isinstance(row, tuple):
        # PostgreSQL returns tuples
        cols = ["run_id", "started_at", "completed_at", "total_raw", "total_processed",
                "total_analyzed", "themes_summary", "sentiment_summary", "top_quotes",
                "behavior_patterns", "status"]
        return dict(zip(cols, row))
    return dict(row)


@app.get("/")
def serve_frontend():
    """Serve the dashboard HTML."""
    index_path = FRONTEND_DIR / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return {"message": "Dashboard not found. Place index.html in phase5-dashboard/frontend/"}


@app.get("/api/status")
def get_status():
    """Returns the status of the current or latest pipeline run."""
    run = get_latest_run()
    if not run:
        return {"status": "none"}

    # Also count progress if running
    progress = None
    if run["status"] == "running":
        db = DatabaseManager()
        with db.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM processed_reviews")
            total_processed = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM analysis_results")
            total_analyzed = cursor.fetchone()[0]

        if total_processed > 0:
            pct = round((total_analyzed / total_processed) * 100)
            progress = f"{pct}%"

    return {
        "status": run["status"],
        "run_id": run["run_id"],
        "started_at": run["started_at"],
        "completed_at": run["completed_at"],
        "progress": progress
    }


@app.get("/api/insights")
def get_all_insights():
    """Returns the full insights payload."""
    run = get_latest_run()
    if not run or run["status"] != "completed":
        raise HTTPException(status_code=404, detail="No completed insights available")

    return {
        "themes": json.loads(run["themes_summary"]) if isinstance(run["themes_summary"], str) else (run["themes_summary"] or {}),
        "sentiment": json.loads(run["sentiment_summary"]) if isinstance(run["sentiment_summary"], str) else (run["sentiment_summary"] or {}),
        "quotes": json.loads(run["top_quotes"]) if isinstance(run["top_quotes"], str) else (run["top_quotes"] or {}),
        "patterns": json.loads(run["behavior_patterns"]) if isinstance(run["behavior_patterns"], str) else (run["behavior_patterns"] or {})
    }


@app.get("/api/insights/themes")
def get_themes():
    """Returns the theme distribution."""
    run = get_latest_run()
    if not run or run["status"] != "completed":
        raise HTTPException(status_code=404, detail="No completed insights available")

    themes = json.loads(run["themes_summary"]) if isinstance(run["themes_summary"], str) else (run["themes_summary"] or {})
    result = []
    for tid, data in themes.items():
        result.append({
            "id": tid,
            "name": data["name"],
            "count": data["count"],
            "pct": data["pct"]
        })
    return sorted(result, key=lambda x: x["count"], reverse=True)


@app.get("/api/insights/sentiment")
def get_sentiment():
    """Returns the sentiment breakdown."""
    run = get_latest_run()
    if not run or run["status"] != "completed":
        raise HTTPException(status_code=404, detail="No completed insights available")
    return json.loads(run["sentiment_summary"]) if isinstance(run["sentiment_summary"], str) else (run["sentiment_summary"] or {})


@app.get("/api/insights/quotes")
def get_quotes(theme: str = Query(None, description="Filter quotes by theme ID (e.g. T1)")):
    """Returns representative quotes, optionally filtered by theme."""
    run = get_latest_run()
    if not run or run["status"] != "completed":
        raise HTTPException(status_code=404, detail="No completed insights available")

    quotes = json.loads(run["top_quotes"]) if isinstance(run["top_quotes"], str) else (run["top_quotes"] or {})
    if theme:
        if theme in quotes:
            return quotes[theme]
        raise HTTPException(status_code=404, detail=f"Theme {theme} not found in quotes")

    return quotes


@app.get("/api/insights/patterns")
def get_patterns():
    """Returns the cross-corpus behavior patterns."""
    run = get_latest_run()
    if not run or run["status"] != "completed":
        raise HTTPException(status_code=404, detail="No completed insights available")
    return json.loads(run["behavior_patterns"]) if isinstance(run["behavior_patterns"], str) else (run["behavior_patterns"] or {})


@app.get("/api/meta")
def get_meta():
    """Returns corpus metadata."""
    run = get_latest_run()

    # Even without a completed run, return current counts
    db = DatabaseManager()
    with db.connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM raw_reviews")
        total_raw = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM processed_reviews")
        total_processed = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM analysis_results")
        total_analyzed = cursor.fetchone()[0]

        # Source distribution
        cursor.execute("SELECT source, COUNT(*) FROM raw_reviews GROUP BY source")
        sources = {row[0]: row[1] for row in cursor.fetchall()}

    return {
        "total_raw": total_raw,
        "total_processed": total_processed,
        "total_analyzed": total_analyzed,
        "sources": sources,
        "last_run_completed": run["completed_at"] if run else None,
        "last_run_status": run["status"] if run else "none"
    }


def run_full_pipeline_task():
    """Background task to run the full pipeline: scrapers → processing → LLM analysis."""
    try:
        # Step 1: Run scrapers
        scraper_path = PROJECT_ROOT / "phase2-scrapers" / "run_scrapers.py"
        subprocess.run([sys.executable, str(scraper_path)], check=True,
                      cwd=str(PROJECT_ROOT / "phase2-scrapers"))

        # Step 2: Run data processing pipeline
        pipeline_path = PROJECT_ROOT / "phase3-pipeline" / "run_pipeline.py"
        subprocess.run([sys.executable, str(pipeline_path), "--clear"], check=True,
                      cwd=str(PROJECT_ROOT / "phase3-pipeline"))

        # Step 3: Run LLM analysis
        analyzer_path = PROJECT_ROOT / "phase4-agent" / "analyzer.py"
        subprocess.run([sys.executable, str(analyzer_path), "--clear"], check=True,
                      cwd=str(PROJECT_ROOT / "phase4-agent"))

    except subprocess.CalledProcessError as e:
        print(f"Pipeline execution failed at step: {e}")


@app.post("/api/run-pipeline")
def trigger_pipeline(background_tasks: BackgroundTasks):
    """Triggers the full pipeline (scrapers → processing → analysis) asynchronously."""
    run = get_latest_run()
    if run and run["status"] == "running":
        return {"status": "already_running", "run_id": run["run_id"]}

    background_tasks.add_task(run_full_pipeline_task)
    return {"status": "started", "message": "Full pipeline triggered: Scraping → Processing → LLM Analysis"}


if __name__ == "__main__":
    import uvicorn
    print("=" * 60)
    print("  🚀 Starting Dashboard API Server")
    print("  URL: http://localhost:8000")
    print("  Dashboard: http://localhost:8000/")
    print("=" * 60)
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
