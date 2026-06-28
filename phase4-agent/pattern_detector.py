"""
pattern_detector.py — Synthesizes cross-corpus behavior patterns from classified reviews.
"""

import os
import sys
import json
import time
import logging
from pathlib import Path
from typing import List, Dict, Any

# Ensure we can import modules from phase1-setup
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "phase1-setup"))

import config
from groq import Groq

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("PatternDetector")

class PatternDetector:
    """Detects cross-corpus behavior patterns, workarounds, churn risks, and segments using Groq."""

    def __init__(self, api_key: str = None):
        self.api_key = api_key or config.GROQ_API_KEY
        if not self.api_key:
            raise ValueError("GROQ_API_KEY is not set in environment or config.")
        self.client = Groq(api_key=self.api_key)
        self.prompt_path = PROJECT_ROOT / "phase4-agent" / "prompts" / "pattern_prompt.txt"
        self.system_prompt = self._load_system_prompt()

    def _load_system_prompt(self) -> str:
        """Loads the system prompt from prompts/pattern_prompt.txt."""
        if not self.prompt_path.exists():
            raise FileNotFoundError(f"System prompt file not found at {self.prompt_path}")
        with open(self.prompt_path, "r", encoding="utf-8") as f:
            return f.read().strip()

    def detect_patterns(self, reviews: List[Dict[str, Any]], max_retries: int = 5) -> Dict[str, Any]:
        """
        Runs pattern detection on a representative subset of the corpus.
        Input `reviews` should have: 'id', 'text', 'source', 'rating', 'theme_ids', 'sentiment'.
        """
        if not reviews:
            logger.warning("No reviews available for pattern detection.")
            return {"patterns": [], "executive_summary": "No data available."}

        logger.info(f"Running cross-corpus pattern detection on {len(reviews)} reviews...")

        # Select a representative subset of critical reviews to fit within the 12,000 TPM limit.
        # Power users, workarounds, and abandonment triggers are most prevalent in detailed,
        # frustrated/negative and highly engaged reviews.
        frustrated_reviews = [r for r in reviews if r.get("sentiment") == "frustrated"]
        negative_reviews = [r for r in reviews if r.get("sentiment") == "negative"]
        other_reviews = [r for r in reviews if r.get("sentiment") not in ("frustrated", "negative")]

        # Sort each group by engagement and length (longer reviews have more detail)
        key_func = lambda r: (r.get("engagement_score") or 0, len(r.get("text") or ""))
        frustrated_reviews.sort(key=key_func, reverse=True)
        negative_reviews.sort(key=key_func, reverse=True)
        other_reviews.sort(key=key_func, reverse=True)

        selected = []
        # Take all frustrated reviews up to 15
        selected.extend(frustrated_reviews[:15])
        # Take negative reviews up to 15
        selected.extend(negative_reviews[:15])
        # Take other reviews (neutral/positive) up to 10 for balance
        selected.extend(other_reviews[:10])

        # If we need more to reach 40 reviews, fill with more negative ones
        if len(selected) < 40 and len(negative_reviews) > 15:
            extra_negs = negative_reviews[15:15 + (40 - len(selected))]
            selected.extend(extra_negs)

        # Deduplicate to be absolutely sure there are no duplicate IDs
        seen_ids = set()
        final_selected = []
        for r in selected:
            if r["id"] not in seen_ids:
                seen_ids.add(r["id"])
                final_selected.append(r)

        # Limit to absolute max of 15 reviews to strictly stay under 6000 TPM limit
        final_selected = final_selected[:15]

        logger.info(f"Selected {len(final_selected)} critical reviews for pattern detection to comply with TPM limits.")

        # Prepare payload
        payload = [{
            "id": r["id"],
            "text": r["text"],
            "source": r["source"],
            "rating": r.get("rating"),
            "theme_ids": r.get("theme_ids") if isinstance(r.get("theme_ids"), list) else json.loads(r.get("theme_ids") or "[]"),
            "sentiment": r.get("sentiment")
        } for r in final_selected]

        user_content = json.dumps(payload, ensure_ascii=False)

        delay = 2.0
        for attempt in range(1, max_retries + 1):
            try:
                response = self.client.chat.completions.create(
                    model=config.LLM_PRIMARY_MODEL,
                    messages=[
                        {"role": "system", "content": self.system_prompt},
                        {"role": "user", "content": user_content}
                    ],
                    temperature=config.LLM_TEMPERATURE,
                    max_tokens=2000,   # Set max_tokens to 2000 to prevent TPM limit errors
                    response_format={"type": "json_object"}
                )

                content = response.choices[0].message.content
                result_json = json.loads(content)

                if "patterns" not in result_json or "executive_summary" not in result_json:
                    raise ValueError("LLM response JSON is missing 'patterns' or 'executive_summary' keys.")

                logger.info(f"Successfully synthesized {len(result_json.get('patterns', []))} behavior patterns.")
                
                # Respect rate limits request delay
                time.sleep(config.GROQ_REQUEST_DELAY)
                return result_json

            except Exception as e:
                logger.error(f"Error in pattern detection: {e}")
                if attempt == max_retries:
                    raise e
                
                logger.info(f"Waiting {delay}s before retrying...")
                time.sleep(delay)
                delay *= 2.0

        return {"patterns": [], "executive_summary": "Analysis failed."}
