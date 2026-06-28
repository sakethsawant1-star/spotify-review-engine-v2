"""
deduplicator.py — Review Deduplication Module
===============================================
Phase 3, Step 3: Remove duplicate reviews.

Two-level dedup:
  1. Exact dedup — via (source, text_hash). If the same text appears
     from the same source, keep only one copy (highest engagement).
  2. Fuzzy dedup — via Jaccard similarity on word shingles (≥ 0.85 threshold).
     Catches near-duplicate reviews with minor differences (typos, punctuation).

When duplicates are found, the version with the highest engagement score
(thumbs_up, upvotes, reply_count) is kept.

Input:  List of PII-stripped review dicts
Output: Deduplicated list of review dicts
"""

import hashlib
import logging
from collections import defaultdict

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "phase1-setup"))
import config

logger = logging.getLogger("deduplicator")


# ──────────────────────────────────────────────
# Engagement Score Calculation
# ──────────────────────────────────────────────

def compute_engagement_score(review: dict) -> int:
    """
    Compute a composite engagement score from metadata.
    Used to decide which duplicate to keep (highest engagement wins).
    """
    metadata = review.get("metadata", {})
    if isinstance(metadata, str):
        import json
        try:
            metadata = json.loads(metadata)
        except (json.JSONDecodeError, TypeError):
            metadata = {}

    score = 0

    # Play Store / App Store: thumbsUpCount
    score += int(metadata.get("thumbsUpCount", 0))
    score += int(metadata.get("thumbs_up", 0))

    # Reddit: upvotes / score
    score += int(metadata.get("score", 0))
    score += int(metadata.get("upvotes", 0))
    score += int(metadata.get("ups", 0))

    # Comment/reply count (weighted)
    score += int(metadata.get("reply_count", 0)) * 2
    score += int(metadata.get("num_comments", 0)) * 2

    return score


# ──────────────────────────────────────────────
# Text Hashing (for Exact Dedup)
# ──────────────────────────────────────────────

def text_hash(text: str) -> str:
    """
    Create a normalized hash of review text for exact dedup.
    Normalizes: lowercase, strip whitespace, remove punctuation.
    """
    normalized = text.lower().strip()
    # Remove common punctuation to catch trivial variations
    for char in ".,!?;:'\"()-":
        normalized = normalized.replace(char, "")
    # Collapse whitespace
    normalized = " ".join(normalized.split())
    return hashlib.md5(normalized.encode("utf-8")).hexdigest()


# ──────────────────────────────────────────────
# Jaccard Similarity (for Fuzzy Dedup)
# ──────────────────────────────────────────────

def word_shingles(text: str, n: int = 2) -> set:
    """
    Create a set of word n-grams (shingles) from text.
    Using bigrams (n=2) by default for a good balance of
    precision and recall in similarity matching.
    """
    words = text.lower().split()
    if len(words) < n:
        return set(words)
    return {" ".join(words[i:i + n]) for i in range(len(words) - n + 1)}


def jaccard_similarity(set_a: set, set_b: set) -> float:
    """Compute Jaccard similarity between two sets."""
    if not set_a and not set_b:
        return 1.0
    if not set_a or not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union > 0 else 0.0


# ──────────────────────────────────────────────
# Exact Deduplication
# ──────────────────────────────────────────────

def exact_dedup(reviews: list[dict]) -> list[dict]:
    """
    Remove exact duplicates based on (source, text_hash).
    When duplicates are found, keep the one with the highest engagement.
    """
    # Group reviews by (source, text_hash)
    groups = defaultdict(list)
    for review in reviews:
        key = (review["source"], text_hash(review["text"]))
        groups[key].append(review)

    results = []
    duplicates_removed = 0

    for key, group in groups.items():
        if len(group) == 1:
            results.append(group[0])
        else:
            # Keep the highest-engagement version
            best = max(group, key=lambda r: compute_engagement_score(r))
            results.append(best)
            duplicates_removed += len(group) - 1

    if duplicates_removed > 0:
        logger.info(f"Exact dedup: removed {duplicates_removed} duplicates")

    return results


# ──────────────────────────────────────────────
# Fuzzy Deduplication
# ──────────────────────────────────────────────

def fuzzy_dedup(
    reviews: list[dict],
    threshold: float = None,
) -> list[dict]:
    """
    Remove near-duplicate reviews using Jaccard similarity on word shingles.
    
    For efficiency, only compare reviews from the same source and with
    similar text lengths (within 2x ratio) to reduce O(n²) comparisons.
    
    Args:
        reviews: List of review dicts
        threshold: Jaccard similarity threshold (default from config)
    
    Returns:
        Deduplicated list of reviews
    """
    if threshold is None:
        threshold = config.FUZZY_DEDUP_THRESHOLD

    if len(reviews) <= 1:
        return reviews

    # Pre-compute shingles for all reviews
    review_shingles = []
    for review in reviews:
        shingles = word_shingles(review["text"])
        engagement = compute_engagement_score(review)
        review_shingles.append((review, shingles, engagement))

    # Group by source for efficiency (only compare within same source)
    source_groups = defaultdict(list)
    for item in review_shingles:
        source_groups[item[0]["source"]].append(item)

    kept_indices = set(range(len(reviews)))  # Start with all kept
    duplicates_removed = 0

    # Build index mapping from review to global index
    review_to_idx = {id(r): i for i, r in enumerate(reviews)}

    for source, group in source_groups.items():
        n = len(group)
        # Mark duplicates within each source group
        local_removed = set()

        for i in range(n):
            if i in local_removed:
                continue

            for j in range(i + 1, n):
                if j in local_removed:
                    continue

                review_i, shingles_i, eng_i = group[i]
                review_j, shingles_j, eng_j = group[j]

                # Skip if text lengths are too different (heuristic speedup)
                len_i = len(review_i["text"])
                len_j = len(review_j["text"])
                if len_i > 0 and len_j > 0:
                    ratio = max(len_i, len_j) / min(len_i, len_j)
                    if ratio > 2.0:
                        continue

                sim = jaccard_similarity(shingles_i, shingles_j)
                if sim >= threshold:
                    # Remove the lower-engagement version
                    if eng_i >= eng_j:
                        local_removed.add(j)
                        global_idx = review_to_idx[id(review_j)]
                        kept_indices.discard(global_idx)
                    else:
                        local_removed.add(i)
                        global_idx = review_to_idx[id(review_i)]
                        kept_indices.discard(global_idx)
                        break  # i is removed, stop comparing it

                    duplicates_removed += 1

    results = [reviews[i] for i in sorted(kept_indices)]

    if duplicates_removed > 0:
        logger.info(f"Fuzzy dedup: removed {duplicates_removed} near-duplicates (threshold={threshold})")

    return results


# ──────────────────────────────────────────────
# Main Deduplication Pipeline
# ──────────────────────────────────────────────

def deduplicate(reviews: list[dict]) -> list[dict]:
    """
    Run full deduplication: exact first, then fuzzy.
    Returns deduplicated list of reviews.
    """
    initial_count = len(reviews)

    # Step 1: Exact dedup
    reviews = exact_dedup(reviews)
    after_exact = len(reviews)

    # Step 2: Fuzzy dedup
    reviews = fuzzy_dedup(reviews)
    after_fuzzy = len(reviews)

    logger.info(
        f"Deduplication complete: {initial_count} input → {after_exact} after exact → "
        f"{after_fuzzy} after fuzzy ({initial_count - after_fuzzy} total removed)"
    )

    return reviews


# ──────────────────────────────────────────────
# CLI Self-Test
# ──────────────────────────────────────────────

if __name__ == "__main__":

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    print("=" * 50)
    print("  Phase 3 — Deduplicator Self-Test")
    print("=" * 50)
    print()

    # Test with synthetic duplicates
    test_reviews = [
        {
            "id": "r1", "source": "play_store",
            "text": "The algorithm keeps recommending the same songs over and over",
            "rating": 2, "metadata": {"thumbsUpCount": 5},
        },
        {
            "id": "r2", "source": "play_store",
            "text": "The algorithm keeps recommending the same songs over and over!",  # Exact dup (punctuation variant)
            "rating": 2, "metadata": {"thumbsUpCount": 10},
        },
        {
            "id": "r3", "source": "play_store",
            "text": "Algorithm keeps recommending same songs over and over again and again",  # Fuzzy dup
            "rating": 2, "metadata": {"thumbsUpCount": 3},
        },
        {
            "id": "r4", "source": "reddit",
            "text": "Discover Weekly has been amazing lately! Getting great new recommendations.",
            "rating": None, "metadata": {"score": 42},
        },
        {
            "id": "r5", "source": "reddit",
            "text": "Totally different review about something else entirely.",
            "rating": None, "metadata": {"score": 10},
        },
    ]

    result = deduplicate(test_reviews)
    print(f"  Input: {len(test_reviews)} reviews")
    print(f"  Output: {len(result)} reviews")
    print()

    for r in result:
        eng = compute_engagement_score(r)
        print(f"  [{r['source']}] eng={eng} | {r['text'][:70]}...")
    print()

    print("=" * 50)
