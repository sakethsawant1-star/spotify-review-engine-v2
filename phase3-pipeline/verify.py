"""Quick verification script for Phase 3 pipeline results."""
import json
import sys
import re
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "phase1-setup"))
import config
from db import DatabaseManager

db = DatabaseManager()

with db.connection() as conn:
    c = conn.cursor()

    print("=" * 60)
    print("  Phase 3 — Verification Report")
    print("=" * 60)
    print()

    # 1. Counts
    c.execute("SELECT COUNT(*) FROM raw_reviews")
    raw = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM processed_reviews")
    proc = c.fetchone()[0]
    print(f"  Raw reviews:       {raw}")
    print(f"  Processed reviews: {proc}")
    print(f"  Reduction:         {raw - proc} ({round((1 - proc/raw)*100, 1)}%)")
    print()

    # 2. Source distribution
    print("  Source distribution:")
    c.execute("SELECT source, COUNT(*) as cnt FROM processed_reviews GROUP BY source ORDER BY cnt DESC")
    for row in c.fetchall():
        src = row[0] if isinstance(row, tuple) else row["source"]
        cnt = row[1] if isinstance(row, tuple) else row["cnt"]
        pct = round(cnt / proc * 100, 1)
        print(f"    {src}: {cnt} ({pct}%)")
    print()

    # 3. Spot-check 20 random reviews
    print("  Spot-check 20 random reviews:")
    c.execute("SELECT * FROM processed_reviews ORDER BY RANDOM() LIMIT 20")
    rows = c.fetchall()

    pii_found = 0
    email_re = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
    phone_re = re.compile(r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b")

    for i, row in enumerate(rows, 1):
        if isinstance(row, tuple):
            text, source, rating, word_count = row[3], row[1], row[2], row[5]
            keywords = json.loads(row[6]) if isinstance(row[6], str) else (row[6] or [])
        else:
            text = row["text"]
            source, rating, word_count = row["source"], row["rating"], row["word_count"]
            keywords = json.loads(row["discovery_keywords"]) if row["discovery_keywords"] else []

        has_email = bool(email_re.search(text))
        has_phone = bool(phone_re.search(text))
        pii_flag = " [PII!]" if has_email or has_phone else ""
        if has_email or has_phone:
            pii_found += 1

        print(f"  {i:>2}. [{source}] r={rating} wc={word_count}{pii_flag}")
        print(f"      keys: {keywords[:4]}")
        print(f"      text: {text[:90]}...")
        print()

    print(f"  PII found in spot-check: {pii_found}/20")
    print()

    # 4. Word count stats
    c.execute("SELECT MIN(word_count), AVG(word_count), MAX(word_count) FROM processed_reviews")
    stats = c.fetchone()
    print(f"  Word count: min={stats[0]}, avg={round(float(stats[1]), 1)}, max={stats[2]}")

    # 5. Engagement stats
    c.execute("SELECT MIN(engagement_score), AVG(engagement_score), MAX(engagement_score) FROM processed_reviews")
    stats = c.fetchone()
    print(f"  Engagement: min={stats[0]}, avg={round(float(stats[1]), 1)}, max={stats[2]}")

print()
print("=" * 60)
print("  Verification complete!")
print("=" * 60)
