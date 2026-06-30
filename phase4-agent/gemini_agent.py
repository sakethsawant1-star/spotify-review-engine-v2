"""
gemini_agent.py — Unified 2-Pass Gemini LLM Agent for Phase 4
==============================================================
Replaces groq_agent.py. Uses Gemini 2.5 Flash to bypass the strict
6000 TPM limits on Groq, allowing for 100-review batches and 4s delays.

Pass 1: Batch Analysis (N calls, 4s apart)
  → per-review theme/sentiment classification + batch-level top quotes
Pass 2: Synthesis (1 call)
  → consolidated top quotes per theme + behavior patterns + executive summary
"""

import os
import sys
import json
import time
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

# Ensure we can import modules from phase1-setup
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "phase1-setup"))

import config

logger = logging.getLogger(__name__)

class SpotifyReviewAgent:
    """
    Unified Spotify Review Analysis Agent using Google Gemini.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = None,
    ):
        self.api_key = (api_key or config.GEMINI_API_KEY)
        if not self.api_key:
            raise ValueError(
                "GEMINI_API_KEY not found. Set it in .env or pass api_key parameter."
            )

        self.model = model or config.LLM_PRIMARY_MODEL

        # Load prompts
        prompts_dir = Path(__file__).parent / "prompts"
        self._batch_prompt = self._load_prompt(prompts_dir / "batch_analysis_prompt.txt")
        self._synthesis_prompt = self._load_prompt(prompts_dir / "synthesis_prompt.txt")

        # Import google.genai
        try:
            from google import genai
            from google.genai import types
            self.client = genai.Client(api_key=self.api_key)
            self.types = types
        except ImportError:
            raise ImportError("google-genai package not installed. Run: pip install google-genai")

        # Track calls for logging
        self._call_count = 0

    @staticmethod
    def _load_prompt(path: Path) -> str:
        """Load a prompt template from a text file."""
        if not path.exists():
            raise FileNotFoundError(f"Prompt file not found: {path}")
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()

    def _call_gemini(self, system_prompt: str, user_content: str, retries: int = 3) -> dict:
        """
        Make a rate-limited Gemini API call with retries.
        """
        # Wait to respect the 15 RPM limit (4s per request)
        if self._call_count > 0:
            print(f"  [Rate Limiter] Waiting {config.LLM_REQUEST_DELAY}s before next Gemini call...")
            time.sleep(config.LLM_REQUEST_DELAY)

        attempt = 1
        while attempt <= retries:
            try:
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=user_content,
                    config=self.types.GenerateContentConfig(
                        system_instruction=system_prompt,
                        response_mime_type="application/json",
                        temperature=config.LLM_TEMPERATURE,
                    )
                )
                
                self._call_count += 1
                
                # Parse JSON
                content = response.text
                return json.loads(content)

            except Exception as e:
                err_str = str(e).upper()
                is_rate_limit = "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "QUOTA" in err_str
                
                if is_rate_limit:
                    wait_time = 60
                    import re
                    match = re.search(r"retry in (\d+)", str(e), re.IGNORECASE)
                    if match:
                        wait_time = int(match.group(1)) + 5  # Add a buffer
                    
                    print(f"  [Rate Limiter] 429 Rate Limit hit. Waiting {wait_time}s for reset...")
                    time.sleep(wait_time)
                    # Do not increment attempt, just try again
                    continue
                else:
                    if attempt == retries:
                        logger.error(f"Gemini API failed after {retries} attempts. Last error: {e}")
                        raise
                    logger.warning(f"Gemini API call failed (attempt {attempt}/{retries}): {e}. Retrying in 10s...")
                    time.sleep(10)
                    attempt += 1

    def _analyze_batch(self, batch: List[Dict], batch_index: int) -> dict:
        """Pass 1: Analyze a single batch of reviews."""
        print(f"\n  [Pass 1] Analyzing Batch {batch_index + 1} ({len(batch)} reviews)...")

        payload = [{
            "id": r["id"],
            "text": r["text"],
            "source": r.get("source", "unknown"),
            "rating": r.get("rating"),
        } for r in batch]

        user_content = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

        raw_result = self._call_gemini(self._batch_prompt, user_content)

        # Validate structure
        if "results" not in raw_result or not isinstance(raw_result["results"], list):
            logger.warning(f"Batch {batch_index + 1}: 'results' missing. Recovering.")
            raw_result.setdefault("results", [])

        if "top_quotes" not in raw_result:
            raw_result["top_quotes"] = []

        n_classified = len(raw_result["results"])
        n_quotes = len(raw_result.get("top_quotes", []))
        print(f"  [Pass 1] Batch {batch_index + 1} [OK] — "
              f"{n_classified} reviews classified, {n_quotes} quotes extracted")

        return raw_result

    def _synthesize(self, partial_results: list, all_reviews: List[Dict]) -> dict:
        """Pass 2: Merge partial batch results."""
        print(f"\n  [Pass 2] Synthesizing {len(partial_results)} batch results...")

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

        critical_reviews = []
        for batch_result in partial_results:
            for r in batch_result.get("results", []):
                if r.get("sentiment") in ("frustrated", "negative"):
                    for orig in all_reviews:
                        if orig["id"] == r.get("review_id"):
                            critical_reviews.append({
                                "id": orig["id"],
                                "text": orig["text"][:300],
                                "source": orig.get("source", "unknown"),
                                "rating": orig.get("rating"),
                                "theme_ids": r.get("theme_ids", []),
                                "sentiment": r.get("sentiment"),
                            })
                            break

        critical_reviews = critical_reviews[:30]

        synthesis_input = {
            "total_reviews_analyzed": sum(len(br.get("results", [])) for br in partial_results),
            "theme_distribution": theme_counts,
            "sentiment_distribution": sentiment_counts,
            "all_candidate_quotes": all_quotes,
            "critical_reviews_for_patterns": critical_reviews,
        }

        user_content = json.dumps(synthesis_input, ensure_ascii=False, separators=(",", ":"))

        raw_result = self._call_gemini(self._synthesis_prompt, user_content)

        if "top_quotes" not in raw_result:
            raw_result["top_quotes"] = {}
        if "patterns" not in raw_result:
            raw_result["patterns"] = []
        if "executive_summary" not in raw_result:
            raw_result["executive_summary"] = "Synthesis completed but no summary generated."

        n_patterns = len(raw_result.get("patterns", []))
        n_themes = len([k for k, v in raw_result.get("top_quotes", {}).items() if v])
        print(f"  [Pass 2] Synthesis [OK] — {n_themes} themes with quotes, {n_patterns} patterns detected")

        return raw_result

    def analyze_reviews(self, reviews: List[Dict], batch_size: int = None) -> dict:
        batch_size = batch_size or config.BATCH_SIZE

        print(f"\n{'='*60}")
        print(f"  🤖 Phase 4 — Unified LLM Agent (Gemini)")
        print(f"{'='*60}")
        print(f"  Model: {self.model}")
        print(f"  Reviews: {len(reviews)}")
        print(f"  Batch size: {batch_size}")
        print(f"  Estimated batches: {-(-len(reviews)//batch_size)}")

        self._call_count = 0

        if not reviews:
            raise ValueError("No reviews to analyze.")

        # Pass 1
        batches = [reviews[i:i+batch_size] for i in range(0, len(reviews), batch_size)]
        
        print(f"\n{'-'*40}")
        print(f"  Pass 1: Batch Analysis ({len(batches)} batches)")
        print(f"{'-'*40}")

        partial_results = []
        all_classification_results = []

        for i, batch in enumerate(batches):
            result = self._analyze_batch(batch, i)
            partial_results.append(result)

            classified_map = {r.get("review_id"): r for r in result.get("results", []) if "review_id" in r}

            for original in batch:
                orig_id = original["id"]
                if orig_id in classified_map:
                    item = classified_map[orig_id]
                    theme_ids = item.get("theme_ids", [])
                    if not isinstance(theme_ids, list):
                        theme_ids = [theme_ids] if theme_ids else []

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
                    logger.warning(f"Review ID {orig_id} missing from LLM response. Creating fallback.")
                    all_classification_results.append({
                        "review_id": orig_id,
                        "theme_ids": json.dumps([]),
                        "theme_confidence": 0.0,
                        "sentiment": "neutral",
                        "sentiment_confidence": 0.0,
                        "signal_phrases": json.dumps([]),
                    })

        # Pass 2
        print(f"\n{'-'*40}")
        print(f"  Pass 2: Synthesis")
        print(f"{'-'*40}")

        synthesis = self._synthesize(partial_results, reviews)

        print(f"\n{'='*60}")
        print(f"  Phase 4 Analysis Complete!")
        print(f"  * Gemini API calls: {self._call_count}")
        print(f"  * Reviews classified: {len(all_classification_results)}")
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
        return self._call_count
