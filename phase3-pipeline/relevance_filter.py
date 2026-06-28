"""
relevance_filter.py — Discovery Relevance Filter
==================================================
Phase 3, Step 4: Filter reviews to keep only those related to
Spotify's music discovery and recommendation features.

Uses a keyword-based approach with the discovery_keywords.json lexicon:
  - A review passes if it contains ≥1 primary keyword OR ≥2 secondary keywords
  - Keyword matching is case-insensitive

Optionally, borderline reviews (close to threshold but not quite matching)
can be routed to Groq for binary classification, but this is skipped by
default to keep Phase 3 self-contained without LLM dependencies.

Input:  List of deduplicated review dicts
Output: List of discovery-relevant review dicts
"""

import re
import sys
import json
import logging
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "phase1-setup"))
import config

logger = logging.getLogger("relevance_filter")


# ──────────────────────────────────────────────
# Keyword Loading & Compilation
# ──────────────────────────────────────────────

def load_keywords() -> dict:
    """Load discovery keywords from the lexicon JSON file."""
    keywords = config.load_discovery_keywords()
    if not keywords.get("primary") and not keywords.get("secondary"):
        logger.warning("Discovery keywords lexicon is empty!")
    return keywords


def compile_keyword_patterns(keywords: dict) -> dict:
    """
    Compile keyword lists into regex patterns for efficient matching.
    Each keyword is compiled as a word-boundary-aware pattern.
    """
    compiled = {}

    for category in ("primary", "secondary"):
        word_list = keywords.get(category, [])
        if not word_list:
            compiled[category] = []
            continue

        patterns = []
        for word in word_list:
            # Escape special regex chars, then make it word-boundary-aware
            escaped = re.escape(word)
            # Use \b for single words, but for multi-word phrases,
            # just ensure they appear as a substring (case-insensitive)
            pattern = re.compile(escaped, re.IGNORECASE)
            patterns.append((word, pattern))

        compiled[category] = patterns

    return compiled


# Module-level cached patterns
_KEYWORD_PATTERNS = None


def _get_patterns() -> dict:
    """Lazy-load and cache compiled keyword patterns."""
    global _KEYWORD_PATTERNS
    if _KEYWORD_PATTERNS is None:
        keywords = load_keywords()
        _KEYWORD_PATTERNS = compile_keyword_patterns(keywords)
        primary_count = len(_KEYWORD_PATTERNS.get("primary", []))
        secondary_count = len(_KEYWORD_PATTERNS.get("secondary", []))
        logger.info(
            f"Loaded keyword patterns: {primary_count} primary, {secondary_count} secondary"
        )
    return _KEYWORD_PATTERNS


# ──────────────────────────────────────────────
# Relevance Scoring
# ──────────────────────────────────────────────

def score_relevance(text: str) -> dict:
    """
    Score a review text against discovery keywords.
    
    Returns:
        {
            "primary_matches": ["discover", "algorithm"],
            "secondary_matches": ["playlist", "boring"],
            "primary_count": 2,
            "secondary_count": 2,
            "is_relevant": True,
            "matched_keywords": ["discover", "algorithm", "playlist", "boring"]
        }
    """
    patterns = _get_patterns()

    primary_matches = []
    secondary_matches = []

    for keyword, pattern in patterns.get("primary", []):
        if pattern.search(text):
            primary_matches.append(keyword)

    for keyword, pattern in patterns.get("secondary", []):
        if pattern.search(text):
            secondary_matches.append(keyword)

    primary_count = len(primary_matches)
    secondary_count = len(secondary_matches)

    # Relevance rule: ≥1 primary OR ≥2 secondary keywords
    is_relevant = (
        primary_count >= config.MIN_PRIMARY_KEYWORDS
        or secondary_count >= config.MIN_SECONDARY_KEYWORDS
    )

    return {
        "primary_matches": primary_matches,
        "secondary_matches": secondary_matches,
        "primary_count": primary_count,
        "secondary_count": secondary_count,
        "is_relevant": is_relevant,
        "matched_keywords": primary_matches + secondary_matches,
    }


# ──────────────────────────────────────────────
# Engagement Score (for enrichment)
# ──────────────────────────────────────────────

def compute_engagement(review: dict) -> int:
    """Compute engagement score from metadata for processed_reviews table."""
    metadata = review.get("metadata", {})
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except (json.JSONDecodeError, TypeError):
            metadata = {}

    score = 0
    score += int(metadata.get("thumbsUpCount", 0))
    score += int(metadata.get("thumbs_up", 0))
    score += int(metadata.get("score", 0))
    score += int(metadata.get("upvotes", 0))
    score += int(metadata.get("ups", 0))
    score += int(metadata.get("reply_count", 0)) * 2
    score += int(metadata.get("num_comments", 0)) * 2
    return score


# ──────────────────────────────────────────────
# Main Filter Function
# ──────────────────────────────────────────────

def filter_relevant(reviews: list[dict]) -> list[dict]:
    """
    Filter reviews to keep only discovery-relevant ones.
    Also enriches each review with:
      - word_count
      - discovery_keywords (matched keywords list)
      - engagement_score
    
    Returns list of relevant reviews ready for processed_reviews table.
    """
    relevant = []
    not_relevant = 0

    for review in reviews:
        text = review.get("text", "")
        relevance = score_relevance(text)

        if not relevance["is_relevant"]:
            not_relevant += 1
            continue

        # Enrich with pipeline metadata
        enriched = {
            "id": review["id"],
            "source": review["source"],
            "rating": review.get("rating"),
            "text": text,
            "date": review.get("date"),
            "word_count": len(text.split()),
            "discovery_keywords": relevance["matched_keywords"],
            "engagement_score": compute_engagement(review),
        }

        relevant.append(enriched)

    logger.info(
        f"Relevance filter: {len(reviews)} input → {len(relevant)} relevant "
        f"({not_relevant} filtered out as not discovery-related)"
    )

    return relevant


# ──────────────────────────────────────────────
# CLI Self-Test
# ──────────────────────────────────────────────

if __name__ == "__main__":

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    print("=" * 50)
    print("  Phase 3 — Relevance Filter Self-Test")
    print("=" * 50)
    print()

    test_reviews = [
        {
            "id": "t1", "source": "play_store", "rating": 2,
            "text": "The algorithm keeps suggesting the same boring songs. "
                    "Discover Weekly used to be great but now it's just repetitive.",
            "date": "2026-06-23", "metadata": {},
        },
        {
            "id": "t2", "source": "play_store", "rating": 5,
            "text": "Best music app ever! The sound quality is amazing.",
            "date": "2026-06-22", "metadata": {},
        },
        {
            "id": "t3", "source": "reddit", "rating": None,
            "text": "Anyone else feel like their playlist recommendations have gotten stale? "
                    "I keep hearing the same loop of songs on Daily Mix.",
            "date": "2026-06-21", "metadata": {"score": 35},
        },
        {
            "id": "t4", "source": "app_store", "rating": 1,
            "text": "App crashes every time I open it. Completely unusable.",
            "date": "2026-06-20", "metadata": {},
        },
        {
            "id": "t5", "source": "play_store", "rating": 3,
            "text": "I wish there were better ways to explore new artists. "
                    "The recommendation engine needs work.",
            "date": "2026-06-19", "metadata": {"thumbsUpCount": 8},
        },
    ]

    results = filter_relevant(test_reviews)
    print(f"  Input: {len(test_reviews)} reviews")
    print(f"  Output: {len(results)} relevant reviews")
    print()

    for r in results:
        print(f"  [{r['source']}] keywords={r['discovery_keywords']}")
        print(f"    wc={r['word_count']} eng={r['engagement_score']}")
        print(f"    {r['text'][:80]}...")
        print()

    print("=" * 50)
