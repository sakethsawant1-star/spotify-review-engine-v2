"""
groq_agent.py — Unified 2-Pass Groq LLM Agent for Phase 4
==========================================================
Inspired by the M3 Groww Review Agent's architecture.

Consolidates the responsibilities of:
  - theme_sentiment_classifier.py (theme + sentiment classification)
  - quote_extractor.py (quote extraction per theme)
  - pattern_detector.py (cross-corpus behavior patterns)

Into a single 2-pass pipeline:
  Pass 1: Batch Analysis (N calls, 60s apart)
    → per-review theme/sentiment classification + batch-level top quotes
  Pass 2: Synthesis (1 call)
    → consolidated top quotes per theme + behavior patterns + executive summary
"""

import os
import sys
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

# Ensure we can import modules from phase1-setup
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "phase1-setup"))

import config
from rate_limiter import GroqRateLimiter, TokenBudgetExhausted, RateLimitExceeded

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
ESTIMATED_OUTPUT_TOKENS = 1500  # Conservative estimate for output tokens


class SpotifyReviewAgent:
    """
    Unified Spotify Review Analysis Agent.

    Orchestrates the full Phase 4 pipeline:
      1. Batch analysis via Groq (Pass 1) — classification + quotes
      2. Synthesis via Groq (Pass 2) — consolidated quotes + patterns
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = None,
        rate_limiter: Optional[GroqRateLimiter] = None,
    ):
        self.api_key = (api_key or config.GROQ_API_KEY).strip()
        if not self.api_key:
            raise ValueError(
                "GROQ_API_KEY not found. Set it in .env or pass api_key parameter."
            )

        self.model = model or config.LLM_PRIMARY_MODEL
        self.rate_limiter = rate_limiter or GroqRateLimiter()

        # Load prompts
        prompts_dir = Path(__file__).parent / "prompts"
        self._batch_prompt = self._load_prompt(prompts_dir / "batch_analysis_prompt.txt")
        self._synthesis_prompt = self._load_prompt(prompts_dir / "synthesis_prompt.txt")

        # Import groq
        try:
            from groq import Groq
            self._client = Groq(api_key=self.api_key)
        except ImportError:
            raise ImportError("groq package not installed. Run: pip install groq")

        # Track calls for logging
        self._call_count = 0
        self._total_tokens = 0

    @staticmethod
    def _load_prompt(path: Path) -> str:
        """Load a prompt template from a text file."""
        if not path.exists():
            raise FileNotFoundError(f"Prompt file not found: {path}")
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()

    def _call_groq(self, messages: list, max_tokens: int = None) -> dict:
        """
        Make a single rate-limited Groq API call.

        Args:
            messages: List of message dicts (role, content).
            max_tokens: Override max completion tokens.

        Returns:
            Parsed JSON dict from the LLM response.
        """
        # Pre-flight: estimate tokens and check budget
        estimated_input = self.rate_limiter.estimate_call_tokens(messages)
        self.rate_limiter.check_budget(estimated_input, ESTIMATED_OUTPUT_TOKENS)

        # Wait for rate limit spacing
        self.rate_limiter.wait_for_spacing()

        completion_tokens = max_tokens or config.LLM_MAX_TOKENS

        # Make the API call with retry logic
        def _api_call():
            return self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=config.LLM_TEMPERATURE,
                max_tokens=completion_tokens,
            )

        response = self.rate_limiter.execute_with_retry(_api_call)

        # Record actual usage
        usage = response.usage
        self.rate_limiter.record_call(
            input_tokens=usage.prompt_tokens,
            output_tokens=usage.completion_tokens,
            model=self.model,
        )
        self._call_count += 1
        self._total_tokens += usage.total_tokens

        # Parse response
        content = response.choices[0].message.content
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Groq JSON response: {e}")
            logger.error(f"Raw response: {content[:500]}")
            raise ValueError(f"Groq returned invalid JSON: {e}")

    def _analyze_batch(self, batch: List[Dict], batch_index: int) -> dict:
        """
        Pass 1: Analyze a single batch of reviews.
        Returns per-review classifications AND batch-level top quotes.
        """
        print(f"\n  [Pass 1] Analyzing Batch {batch_index + 1} ({len(batch)} reviews)...")

        # Prepare compact payload (only id, text, source, rating to save tokens)
        payload = [{
            "id": r["id"],
            "text": r["text"],
            "source": r.get("source", "unknown"),
            "rating": r.get("rating"),
        } for r in batch]

        user_content = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

        messages = [
            {"role": "system", "content": self._batch_prompt},
            {"role": "user", "content": user_content},
        ]

        raw_result = self._call_groq(messages)

        # Validate basic structure
        if "results" not in raw_result or not isinstance(raw_result["results"], list):
            logger.warning(f"Batch {batch_index + 1}: 'results' key missing or invalid. Attempting recovery.")
            raw_result.setdefault("results", [])

        if "top_quotes" not in raw_result:
            raw_result["top_quotes"] = []

        n_classified = len(raw_result["results"])
        n_quotes = len(raw_result.get("top_quotes", []))
        print(f"  [Pass 1] Batch {batch_index + 1} [OK] — "
              f"{n_classified} reviews classified, {n_quotes} quotes extracted")

        return raw_result

    def _synthesize(self, partial_results: list, all_reviews: List[Dict]) -> dict:
        """
        Pass 2: Merge partial batch results into final consolidated output.
        Produces top quotes per theme, behavior patterns, and executive summary.
        """
        print(f"\n  [Pass 2] Synthesizing {len(partial_results)} batch results...")

        # Collect all top_quotes and a summary of theme/sentiment distributions
        all_quotes = []
        theme_counts: Dict[str, int] = {}
        sentiment_counts: Dict[str, int] = {}

        for batch_result in partial_results:
            all_quotes.extend(batch_result.get("top_quotes", []))
            for r in batch_result.get("results", []):
                for tid in r.get("theme_ids", []):
                    theme_counts[tid] = theme_counts.get(tid, 0) + 1
                sent = r.get("sentiment", "neutral")
                sentiment_counts[sent] = sentiment_counts.get(sent, 0) + 1

        # Select a representative subset of critical reviews for pattern detection
        # (mirrors logic from the old pattern_detector.py)
        critical_reviews = []
        for batch_result in partial_results:
            for r in batch_result.get("results", []):
                if r.get("sentiment") in ("frustrated", "negative"):
                    # Find original review text
                    for orig in all_reviews:
                        if orig["id"] == r.get("review_id"):
                            critical_reviews.append({
                                "id": orig["id"],
                                "text": orig["text"][:300],  # Truncate for token savings
                                "source": orig.get("source", "unknown"),
                                "rating": orig.get("rating"),
                                "theme_ids": r.get("theme_ids", []),
                                "sentiment": r.get("sentiment"),
                            })
                            break

        # Limit to 30 critical reviews for synthesis
        critical_reviews = critical_reviews[:30]

        synthesis_input = {
            "total_reviews_analyzed": sum(len(br.get("results", [])) for br in partial_results),
            "theme_distribution": theme_counts,
            "sentiment_distribution": sentiment_counts,
            "all_candidate_quotes": all_quotes,
            "critical_reviews_for_patterns": critical_reviews,
        }

        user_content = json.dumps(synthesis_input, ensure_ascii=False, separators=(",", ":"))

        messages = [
            {"role": "system", "content": self._synthesis_prompt},
            {"role": "user", "content": user_content},
        ]

        raw_result = self._call_groq(messages, max_tokens=2000)

        # Validate basic structure
        if "top_quotes" not in raw_result:
            raw_result["top_quotes"] = {}
        if "patterns" not in raw_result:
            raw_result["patterns"] = []
        if "executive_summary" not in raw_result:
            raw_result["executive_summary"] = "Synthesis completed but no summary generated."

        n_patterns = len(raw_result.get("patterns", []))
        n_themes_with_quotes = len([k for k, v in raw_result.get("top_quotes", {}).items() if v])
        print(f"  [Pass 2] Synthesis [OK] — "
              f"{n_themes_with_quotes} themes with quotes, {n_patterns} patterns detected")

        return raw_result

    def analyze_reviews(
        self,
        reviews: List[Dict],
        batch_size: int = None,
    ) -> dict:
        """
        Full 2-pass pipeline: Batch Analysis → Synthesis.

        Args:
            reviews: Processed review list from the database.
            batch_size: Max reviews per batch (default from config.BATCH_SIZE).

        Returns:
            Dict with keys:
              - "classification_results": list of per-review analysis dicts
              - "top_quotes": dict of theme_id -> list of quote dicts
              - "behavior_patterns": dict with "patterns" and "executive_summary"
        """
        batch_size = batch_size or config.BATCH_SIZE

        print(f"\n{'='*60}")
        print(f"  🤖 Phase 4 — Unified LLM Analysis Agent (2-Pass)")
        print(f"{'='*60}")
        print(f"  Model: {self.model}")
        print(f"  Reviews: {len(reviews)}")
        print(f"  Batch size: {batch_size}")
        print(f"  Estimated batches: {-(-len(reviews)//batch_size)}")

        # Reset call tracking
        self._call_count = 0
        self._total_tokens = 0

        if not reviews:
            raise ValueError("No reviews to analyze.")

        # ─── Pass 1: Batch Analysis ───
        batches = [reviews[i:i+batch_size] for i in range(0, len(reviews), batch_size)]

        print(f"\n{'-'*40}")
        print(f"  Pass 1: Batch Analysis ({len(batches)} batches)")
        print(f"{'-'*40}")

        partial_results = []
        all_classification_results = []

        for i, batch in enumerate(batches):
            result = self._analyze_batch(batch, i)
            partial_results.append(result)

            # Collect per-review classification results, aligning with original review data
            classified_map = {r.get("review_id"): r for r in result.get("results", []) if "review_id" in r}

            for original in batch:
                orig_id = original["id"]
                if orig_id in classified_map:
                    item = classified_map[orig_id]
                    theme_ids = item.get("theme_ids", [])
                    if not isinstance(theme_ids, list):
                        theme_ids = [theme_ids] if theme_ids else []

                    # Robustly parse confidences in case LLM returns a list (e.g., [0.9])
                    def parse_confidence(val):
                        if isinstance(val, list) and len(val) > 0:
                            val = val[0]
                        try:
                            return float(val)
                        except (ValueError, TypeError):
                            return 1.0

                    all_classification_results.append({
                        "review_id": orig_id,
                        "theme_ids": json.dumps(theme_ids),
                        "theme_confidence": parse_confidence(item.get("theme_confidence", 1.0)),
                        "sentiment": str(item.get("sentiment", "neutral")),
                        "sentiment_confidence": parse_confidence(item.get("sentiment_confidence", 1.0)),
                        "signal_phrases": json.dumps(item.get("signal_phrases", [])),
                    })
                else:
                    # Fallback if the LLM skipped a review
                    logger.warning(f"Review ID {orig_id} missing from LLM response. Creating fallback.")
                    all_classification_results.append({
                        "review_id": orig_id,
                        "theme_ids": json.dumps([]),
                        "theme_confidence": 0.0,
                        "sentiment": "neutral",
                        "sentiment_confidence": 0.0,
                        "signal_phrases": json.dumps([]),
                    })

        # ─── Pass 2: Synthesis ───
        print(f"\n{'-'*40}")
        print(f"  Pass 2: Synthesis")
        print(f"{'-'*40}")

        synthesis = self._synthesize(partial_results, reviews)

        # ─── Summary ───
        print(f"\n{'='*60}")
        print(f"  Phase 4 Analysis Complete!")
        print(f"  * LLM calls: {self._call_count}")
        print(f"  * Total tokens: {self._total_tokens}")
        print(f"  * Reviews classified: {len(all_classification_results)}")
        usage = self.rate_limiter.daily_usage_summary
        print(f"  * Daily budget: {usage['tokens_used']}/{usage['tokens_budget']} "
              f"({usage['utilization_pct']}%)")
        print(f"{'='*60}\n")

        return {
            "classification_results": all_classification_results,
            "top_quotes": synthesis.get("top_quotes", {}),
            "behavior_patterns": {
                "patterns": synthesis.get("patterns", []),
                "executive_summary": synthesis.get("executive_summary", ""),
            },
        }

    @property
    def call_count(self) -> int:
        """Number of Groq API calls made in the last run."""
        return self._call_count

    @property
    def total_tokens(self) -> int:
        """Total tokens used in the last run."""
        return self._total_tokens
