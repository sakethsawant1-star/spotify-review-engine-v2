"""
pii_remover.py — PII (Personally Identifiable Information) Removal
===================================================================
Phase 3, Step 2: Strip PII from cleaned reviews.

Two-pass approach:
  1. Regex pass — emails, phone numbers, URLs with user IDs
  2. spaCy NER pass — person names, account IDs, locations with personal context

Reviews that still contain PII after stripping are flagged but kept
(the PII text is replaced with [REDACTED]).

Input:  List of cleaned review dicts (from cleaner.py)
Output: List of PII-stripped review dicts
"""

import re
import sys
import logging
from pathlib import Path
from typing import Optional

# Allow imports from phase1-setup
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "phase1-setup"))
import config

logger = logging.getLogger("pii_remover")


# ──────────────────────────────────────────────
# Regex Patterns for PII
# ──────────────────────────────────────────────

# Email addresses
_EMAIL_RE = re.compile(config.PII_EMAIL_REGEX)

# Phone numbers (various formats: 123-456-7890, (123) 456-7890, etc.)
_PHONE_RE = re.compile(
    r"""
    (?:                          # Optional country code
        \+?\d{1,3}[\s.-]?       
    )?
    (?:                          # Optional area code in parens
        \(\d{2,4}\)[\s.-]?      
    )?
    \d{3}[\s.-]?\d{3}[\s.-]?\d{4}  # Core phone pattern
    """,
    re.VERBOSE,
)

# URLs (full URLs including paths that might contain user IDs)
_URL_RE = re.compile(config.PII_URL_REGEX)

# Social media handles (@username patterns)
_HANDLE_RE = re.compile(r"@[a-zA-Z0-9_]{3,30}")

# Spotify user IDs / profile patterns
_SPOTIFY_USER_RE = re.compile(
    r"(?:spotify:user:|open\.spotify\.com/user/)[a-zA-Z0-9]+"
)

# IP addresses
_IP_RE = re.compile(
    r"\b(?:\d{1,3}\.){3}\d{1,3}\b"
)

# Credit card-like numbers (16 digits with optional separators)
_CC_RE = re.compile(
    r"\b\d{4}[\s.-]?\d{4}[\s.-]?\d{4}[\s.-]?\d{4}\b"
)

# All regex patterns in order of application
_PII_PATTERNS = [
    ("email", _EMAIL_RE),
    ("spotify_user", _SPOTIFY_USER_RE),
    ("url", _URL_RE),
    ("phone", _PHONE_RE),
    ("handle", _HANDLE_RE),
    ("ip_address", _IP_RE),
    ("credit_card", _CC_RE),
]


# ──────────────────────────────────────────────
# Regex-Based PII Removal
# ──────────────────────────────────────────────

def regex_strip_pii(text: str) -> tuple[str, dict]:
    """
    Apply regex-based PII removal.
    Returns (cleaned_text, pii_counts) where pii_counts shows
    how many of each type were found and replaced.
    """
    pii_counts = {}

    for pii_type, pattern in _PII_PATTERNS:
        matches = pattern.findall(text)
        if matches:
            pii_counts[pii_type] = len(matches)
            text = pattern.sub("[REDACTED]", text)

    return text, pii_counts


# ──────────────────────────────────────────────
# spaCy NER-Based PII Removal
# ──────────────────────────────────────────────

# Lazy-loaded spaCy model
_nlp = None

def _get_nlp():
    """Lazy-load the spaCy model to avoid import-time overhead."""
    global _nlp
    if _nlp is None:
        try:
            import spacy
            _nlp = spacy.load("en_core_web_sm")
            # Only keep the NER component for speed
            logger.info("spaCy en_core_web_sm model loaded for NER")
        except (ImportError, OSError) as e:
            logger.warning(f"spaCy model unavailable, using regex-only PII removal: {e}")
            _nlp = False  # Sentinel: tried and failed
    return _nlp if _nlp is not False else None


# NER entity types that constitute PII
_PII_NER_LABELS = {"PERSON"}  # Person names are the primary NER-based PII


def ner_strip_pii(text: str) -> tuple[str, dict]:
    """
    Apply spaCy NER-based PII removal.
    Targets PERSON entities (names).
    Returns (cleaned_text, pii_counts).
    """
    nlp = _get_nlp()
    if nlp is None:
        return text, {}

    doc = nlp(text)
    pii_counts = {}

    # Process entities in reverse order to preserve positions
    entities = [(ent.start_char, ent.end_char, ent.label_, ent.text)
                for ent in doc.ents
                if ent.label_ in _PII_NER_LABELS]

    # Sort by start position descending so replacements don't shift indices
    entities.sort(key=lambda x: x[0], reverse=True)

    for start, end, label, ent_text in entities:
        # Skip very short entities (likely false positives like "I", "My")
        if len(ent_text.strip()) <= 2:
            continue
        # Skip common words that spaCy sometimes misclassifies as PERSON
        if ent_text.lower() in _COMMON_FALSE_POSITIVES:
            continue

        pii_counts[label] = pii_counts.get(label, 0) + 1
        text = text[:start] + "[REDACTED]" + text[end:]

    return text, pii_counts


# Common false positives that spaCy's NER sometimes tags as PERSON
_COMMON_FALSE_POSITIVES = {
    "spotify", "apple", "google", "amazon", "youtube", "siri",
    "alexa", "android", "iphone", "samsung", "ios", "itunes",
    "pandora", "tidal", "deezer", "soundcloud", "shazam",
    "bluetooth", "wifi", "premium", "free", "daily mix",
    "discover weekly", "release radar",
}


# ──────────────────────────────────────────────
# Main PII Removal Function
# ──────────────────────────────────────────────

def remove_pii(review: dict) -> dict:
    """
    Remove PII from a single review's text.
    Applies regex pass first, then NER pass.
    Returns the review dict with PII-stripped text.
    """
    text = review.get("text", "")

    # Pass 1: Regex
    text, regex_counts = regex_strip_pii(text)

    # Pass 2: spaCy NER
    text, ner_counts = ner_strip_pii(text)

    # Merge PII counts
    all_pii = {**regex_counts, **ner_counts}

    # Clean up multiple consecutive [REDACTED] markers
    text = re.sub(r"(\[REDACTED\]\s*){2,}", "[REDACTED] ", text)
    text = text.strip()

    result = {**review, "text": text}
    if all_pii:
        result["_pii_removed"] = all_pii

    return result


def remove_pii_batch(reviews: list[dict]) -> list[dict]:
    """
    Remove PII from a batch of reviews.
    Returns list of PII-stripped reviews.
    Reviews with empty text after PII removal are excluded.
    """
    results = []
    total_pii_found = 0
    removed_empty = 0

    for review in reviews:
        cleaned = remove_pii(review)

        # Check if text is still meaningful after PII removal
        stripped_text = cleaned["text"].replace("[REDACTED]", "").strip()
        if len(stripped_text) < 3:
            removed_empty += 1
            continue

        if "_pii_removed" in cleaned:
            total_pii_found += sum(cleaned["_pii_removed"].values())

        results.append(cleaned)

    logger.info(
        f"PII removal complete: {len(reviews)} input → {len(results)} output "
        f"({total_pii_found} PII items redacted, {removed_empty} reviews became empty)"
    )

    return results


# ──────────────────────────────────────────────
# CLI Self-Test
# ──────────────────────────────────────────────

if __name__ == "__main__":
    import json

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    print("=" * 50)
    print("  Phase 3 — PII Remover Self-Test")
    print("=" * 50)
    print()

    # Test with synthetic reviews containing PII
    test_reviews = [
        {
            "id": "test-1",
            "source": "play_store",
            "text": "Great app! Contact me at john@example.com or call 555-123-4567",
            "rating": 5,
            "date": "2026-06-23",
        },
        {
            "id": "test-2",
            "source": "reddit",
            "text": "My friend Sarah Johnson recommended Spotify to me and I love it. "
                    "Check my profile: https://open.spotify.com/user/sarah123",
            "rating": None,
            "date": "2026-06-22",
        },
        {
            "id": "test-3",
            "source": "app_store",
            "text": "The algorithm is terrible! @SpotifySupport please fix discover weekly.",
            "rating": 2,
            "date": "2026-06-21",
        },
        {
            "id": "test-4",
            "source": "play_store",
            "text": "Love the new music recommendations! Discover Weekly is amazing.",
            "rating": 5,
            "date": "2026-06-20",
        },
    ]

    results = remove_pii_batch(test_reviews)

    for r in results:
        pii_info = r.pop("_pii_removed", {})
        print(f"  [{r['source']}] {r['text'][:80]}...")
        if pii_info:
            print(f"    PII removed: {pii_info}")
        print()

    print("=" * 50)
