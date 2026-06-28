"""
cleaner.py — Data Cleaning Module
===================================
Phase 3, Step 1: Clean raw reviews before further processing.

Operations:
  1. Strip HTML tags and entities
  2. Normalize Unicode (NFKC)
  3. Standardize dates to ISO 8601
  4. Normalize ratings to 1–5 range (or None)
  5. Discard reviews with empty/whitespace-only text
  6. Language detection — keep English only
  7. Collapse excessive whitespace

Input:  List of raw review dicts (from raw_reviews table)
Output: List of cleaned review dicts (ready for PII removal)
"""

import re
import html
import logging
import unicodedata
from datetime import datetime
from typing import Optional

from langdetect import detect, LangDetectException

logger = logging.getLogger("cleaner")


# ──────────────────────────────────────────────
# HTML & Text Normalization
# ──────────────────────────────────────────────

# Regex to strip HTML tags
_HTML_TAG_RE = re.compile(r"<[^>]+>")

# Regex to collapse multiple whitespace into single space
_MULTI_SPACE_RE = re.compile(r"\s{2,}")

# Regex to strip zero-width characters and other invisible Unicode
_INVISIBLE_RE = re.compile(
    r"[\u200b\u200c\u200d\u200e\u200f\ufeff\u00ad\u2060\u2061\u2062\u2063\u2064]"
)


def strip_html(text: str) -> str:
    """Remove HTML tags and decode HTML entities."""
    # Decode HTML entities first (e.g., &amp; → &)
    text = html.unescape(text)
    # Strip HTML tags
    text = _HTML_TAG_RE.sub(" ", text)
    return text


def normalize_unicode(text: str) -> str:
    """
    Normalize Unicode to NFKC form.
    This converts compatibility characters to their canonical equivalents,
    e.g., fullwidth letters → ASCII, ligatures → separate chars.
    Also strips invisible characters.
    """
    text = unicodedata.normalize("NFKC", text)
    text = _INVISIBLE_RE.sub("", text)
    return text


def collapse_whitespace(text: str) -> str:
    """Collapse multiple whitespace (including newlines) into single spaces."""
    text = _MULTI_SPACE_RE.sub(" ", text)
    return text.strip()


# ──────────────────────────────────────────────
# Date Standardization
# ──────────────────────────────────────────────

# Common date formats found in scraped reviews
_DATE_FORMATS = [
    "%Y-%m-%dT%H:%M:%S%z",        # ISO 8601 with timezone
    "%Y-%m-%dT%H:%M:%S.%f%z",     # ISO 8601 with microseconds
    "%Y-%m-%dT%H:%M:%S",          # ISO 8601 without timezone
    "%Y-%m-%d %H:%M:%S",          # Common datetime
    "%Y-%m-%d",                    # Date only
    "%B %d, %Y",                   # "June 23, 2026"
    "%b %d, %Y",                   # "Jun 23, 2026"
    "%d/%m/%Y",                    # DD/MM/YYYY
    "%m/%d/%Y",                    # MM/DD/YYYY
]


def standardize_date(date_str: Optional[str]) -> Optional[str]:
    """
    Parse various date formats and return ISO 8601 string (YYYY-MM-DD).
    Returns None if parsing fails.
    """
    if not date_str or not date_str.strip():
        return None

    date_str = date_str.strip()

    # Already in ISO 8601 format — try to parse and re-format
    for fmt in _DATE_FORMATS:
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue

    # Fallback: try to extract just the date portion if it starts with YYYY-MM-DD
    iso_match = re.match(r"(\d{4}-\d{2}-\d{2})", date_str)
    if iso_match:
        return iso_match.group(1)

    logger.debug(f"Could not parse date: {date_str}")
    return None


# ──────────────────────────────────────────────
# Rating Normalization
# ──────────────────────────────────────────────

def normalize_rating(rating) -> Optional[int]:
    """
    Normalize rating to integer 1–5 range.
    Returns None for non-numeric or out-of-range values.
    Reddit posts/comments typically have no rating → returns None.
    """
    if rating is None:
        return None

    try:
        r = int(rating)
        if 1 <= r <= 5:
            return r
        elif r > 5:
            # Some sources use 1-10 scale
            return max(1, min(5, round(r / 2)))
        else:
            return None
    except (ValueError, TypeError):
        return None


# ──────────────────────────────────────────────
# Language Detection
# ──────────────────────────────────────────────

def is_english(text: str, min_length: int = 10) -> bool:
    """
    Detect if text is English using langdetect.
    Very short texts (< min_length chars) are assumed English to avoid
    false negatives on brief reviews like "great app" or "love it".
    """
    if len(text.strip()) < min_length:
        # Too short for reliable detection — assume English
        return True

    try:
        lang = detect(text)
        return lang == "en"
    except LangDetectException:
        # If detection fails, keep the review (benefit of the doubt)
        return True


# ──────────────────────────────────────────────
# Main Cleaning Function
# ──────────────────────────────────────────────

def clean_review(review: dict) -> Optional[dict]:
    """
    Apply all cleaning steps to a single review.
    Returns cleaned review dict, or None if the review should be discarded.
    """
    text = review.get("text", "")

    # Step 1: Strip HTML
    text = strip_html(text)

    # Step 2: Normalize Unicode
    text = normalize_unicode(text)

    # Step 3: Collapse whitespace
    text = collapse_whitespace(text)

    # Step 4: Discard empty text
    if not text or len(text.strip()) < 3:
        return None

    # Step 5: Language detection — English only
    if not is_english(text):
        return None

    # Step 6: Standardize date
    date = standardize_date(review.get("date"))

    # Step 7: Normalize rating
    rating = normalize_rating(review.get("rating"))

    # Build cleaned review
    cleaned = {
        "id": review["id"],
        "source": review["source"],
        "rating": rating,
        "text": text,
        "date": date,
        "metadata": review.get("metadata", {}),
    }

    return cleaned


def clean_reviews(reviews: list[dict]) -> list[dict]:
    """
    Clean a batch of raw reviews.
    Returns list of cleaned reviews (discarded reviews are excluded).
    Logs statistics about the cleaning process.
    """
    cleaned = []
    discarded_empty = 0
    discarded_language = 0

    for review in reviews:
        text = review.get("text", "")

        # Pre-clean for empty check
        text_cleaned = collapse_whitespace(normalize_unicode(strip_html(text)))

        if not text_cleaned or len(text_cleaned.strip()) < 3:
            discarded_empty += 1
            continue

        if not is_english(text_cleaned):
            discarded_language += 1
            continue

        result = clean_review(review)
        if result:
            cleaned.append(result)

    total = len(reviews)
    kept = len(cleaned)
    logger.info(
        f"Cleaning complete: {total} input → {kept} kept "
        f"({discarded_empty} empty, {discarded_language} non-English, "
        f"{total - kept - discarded_empty - discarded_language} other)"
    )

    return cleaned


# ──────────────────────────────────────────────
# CLI Self-Test
# ──────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "phase1-setup"))
    import config
    import sqlite3, json

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    print("=" * 50)
    print("  Phase 3 — Cleaner Self-Test")
    print("=" * 50)
    print()

    # Load a sample of raw reviews
    conn = sqlite3.connect(str(config.DB_PATH))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM raw_reviews LIMIT 100")
    rows = cursor.fetchall()
    conn.close()

    reviews = []
    for row in rows:
        reviews.append({
            "id": row["id"],
            "source": row["source"],
            "rating": row["rating"],
            "title": row["title"],
            "text": row["text"],
            "date": row["date"],
            "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
        })

    print(f"  Loaded {len(reviews)} raw reviews for testing")
    cleaned = clean_reviews(reviews)
    print(f"  Result: {len(cleaned)} cleaned reviews")
    print()

    # Show a few samples
    for r in cleaned[:3]:
        print(f"  [{r['source']}] rating={r['rating']} date={r['date']}")
        print(f"    {r['text'][:100]}...")
        print()

    print("=" * 50)
