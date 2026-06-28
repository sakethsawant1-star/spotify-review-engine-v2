import os
import json
import subprocess
import sys
from pathlib import Path
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import psycopg2
import psycopg2.extras

# Load environment variables
project_root = Path(__file__).resolve().parent.parent
load_dotenv(project_root / ".env")

app = FastAPI(title="Review Analytics API")

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db_connection():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise Exception("DATABASE_URL not set in .env")
    return psycopg2.connect(db_url)

@app.get("/api/dashboard/overview")
def get_overview():
    """Fetches the latest pipeline run statistics from Postgres."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        cursor.execute("""
            SELECT 
                total_analyzed, 
                themes_summary, 
                sentiment_summary, 
                behavior_patterns, 
                top_quotes, 
                status 
            FROM pipeline_runs 
            ORDER BY started_at DESC LIMIT 1
        """)
        run = cursor.fetchone()
        
        if run:
            themes_summary = run["themes_summary"]
            if themes_summary:
                cursor.execute("""
                    SELECT sentiment, jsonb_array_elements_text(theme_ids) as theme
                    FROM analysis_results
                """)
                sentiment_rows = cursor.fetchall()
                
                theme_sentiments = {}
                for row in sentiment_rows:
                    s, t = row["sentiment"], row["theme"]
                    if t not in theme_sentiments:
                        theme_sentiments[t] = {'positive': 0, 'mixed': 0, 'neutral': 0, 'negative': 0, 'total': 0}
                    if s in theme_sentiments[t]:
                        theme_sentiments[t][s] += 1
                    theme_sentiments[t]['total'] += 1

                for t_id, t_data in themes_summary.items():
                    if t_id in theme_sentiments and theme_sentiments[t_id]['total'] > 0:
                        total = theme_sentiments[t_id]['total']
                        t_data['sentiment_split'] = {
                            'positive': round((theme_sentiments[t_id]['positive'] / total) * 100),
                            'mixed': round((theme_sentiments[t_id]['mixed'] / total) * 100),
                            'neutral': round((theme_sentiments[t_id]['neutral'] / total) * 100),
                            'negative': round((theme_sentiments[t_id]['negative'] / total) * 100),
                        }
                    else:
                        t_data['sentiment_split'] = {'positive': 25, 'mixed': 25, 'neutral': 25, 'negative': 25}

        conn.close()
        
        if run:
            return {
                "total_analyzed": run["total_analyzed"],
                "themes_summary": themes_summary,
                "sentiment_summary": run["sentiment_summary"],
                "behavior_patterns": run["behavior_patterns"],
                "top_quotes": run["top_quotes"],
                "status": run["status"]
            }
        return {"error": "No pipeline runs found in database"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

LOG_FILE = Path(__file__).parent / "pipeline.log"

def run_full_pipeline_task():
    """Background task to run the full pipeline and stream logs."""
    try:
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            f.write("> Initializing full pipeline execution...\n")
            f.flush()
            
            # Step 1: Run scrapers
            f.write("> Step 1: Running Scrapers...\n")
            f.flush()
            scraper_path = project_root / "phase2-scrapers" / "run_scrapers.py"
            subprocess.run([sys.executable, "-u", str(scraper_path)], stdout=f, stderr=subprocess.STDOUT, cwd=str(project_root / "phase2-scrapers"))
            
            # Step 2: Run processing
            f.write("\n> Step 2: Running Data Processing...\n")
            f.flush()
            pipeline_path = project_root / "phase3-pipeline" / "run_pipeline.py"
            subprocess.run([sys.executable, "-u", str(pipeline_path), "--clear"], stdout=f, stderr=subprocess.STDOUT, cwd=str(project_root / "phase3-pipeline"))
            
            # Step 3: Run LLM Analyzer
            f.write("\n> Step 3: Running LLM Analysis...\n")
            f.flush()
            analyzer_path = project_root / "phase4-agent" / "analyzer.py"
            subprocess.run([sys.executable, "-u", str(analyzer_path), "--clear"], stdout=f, stderr=subprocess.STDOUT, cwd=str(project_root / "phase4-agent"))
            
            f.write("\n> PIPELINE_COMPLETE\n")
    except Exception as e:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"\n> PIPELINE_ERROR: {str(e)}\n")

@app.post("/api/pipeline/run")
def trigger_pipeline(background_tasks: BackgroundTasks):
    """Endpoint to trigger a new AI pipeline run asynchronously."""
    background_tasks.add_task(run_full_pipeline_task)
    return {"message": "Pipeline triggered successfully", "status": "running"}

@app.get("/api/pipeline/logs")
def get_pipeline_logs():
    """Reads the current pipeline execution logs."""
    if not LOG_FILE.exists():
        return {"logs": ["Waiting for pipeline to start..."]}
    
    with open(LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
        # Read last 50 lines to keep payload small
        lines = f.readlines()
        return {"logs": [line.strip() for line in lines[-50:]]}

# Mount the static frontend files
frontend_path = Path(__file__).parent / "frontend"
app.mount("/", StaticFiles(directory=str(frontend_path), html=True), name="frontend")
