"""
theme_sentiment_classifier.py — Classifies review themes and sentiment using Groq Llama-3.3-70b.
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
logger = logging.getLogger("ThemeSentimentClassifier")

class ThemeSentimentClassifier:
    """Classifies themes and sentiment of Spotify reviews in batches using Groq."""

    def __init__(self, api_key: str = None):
        self.api_key = api_key or config.GROQ_API_KEY
        if not self.api_key:
            raise ValueError("GROQ_API_KEY is not set in environment or config.")
        self.client = Groq(api_key=self.api_key)
        self.prompt_path = PROJECT_ROOT / "phase4-agent" / "prompts" / "theme_sentiment_prompt.txt"
        self.system_prompt = self._load_system_prompt()

    def _load_system_prompt(self) -> str:
        """Loads the system prompt from prompts/theme_sentiment_prompt.txt."""
        if not self.prompt_path.exists():
            raise FileNotFoundError(f"System prompt file not found at {self.prompt_path}")
        with open(self.prompt_path, "r", encoding="utf-8") as f:
            return f.read().strip()

    def classify_batch(self, reviews: List[Dict[str, Any]], max_retries: int = 5) -> List[Dict[str, Any]]:
        """
        Classifies a single batch of reviews.
        Each review should have 'id' and 'text'.
        Returns a list of dicts matching the DB analysis_results schema.
        """
        if not reviews:
            return []

        # Prepare payload for LLM (pass only ID and text to save tokens)
        payload = [{"id": r["id"], "text": r["text"]} for r in reviews]
        user_content = json.dumps(payload, ensure_ascii=False)

        delay = 2.0  # Initial retry delay in seconds
        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f"Dispatching batch of {len(reviews)} reviews to Groq (Attempt {attempt}/{max_retries})...")
                response = self.client.chat.completions.create(
                    model=config.LLM_PRIMARY_MODEL,
                    messages=[
                        {"role": "system", "content": self.system_prompt},
                        {"role": "user", "content": user_content}
                    ],
                    temperature=config.LLM_TEMPERATURE,
                    max_tokens=config.LLM_MAX_TOKENS,
                    response_format={"type": "json_object"}
                )

                content = response.choices[0].message.content
                result_json = json.loads(content)

                if "results" not in result_json or not isinstance(result_json["results"], list):
                    raise ValueError("LLM response JSON is missing 'results' list key.")

                classified_reviews = result_json["results"]
                
                # Create a map of results by review ID for easy alignment
                classified_map = {r["review_id"]: r for r in classified_reviews if "review_id" in r}
                
                final_results = []
                for original in reviews:
                    orig_id = original["id"]
                    if orig_id in classified_map:
                        item = classified_map[orig_id]
                        # Ensure fields exist and fallback if not
                        theme_ids = item.get("theme_ids", [])
                        if not isinstance(theme_ids, list):
                            theme_ids = [theme_ids] if theme_ids else []
                        
                        final_results.append({
                            "review_id": orig_id,
                            "theme_ids": json.dumps(theme_ids),
                            "theme_confidence": float(item.get("theme_confidence", 1.0)),
                            "sentiment": str(item.get("sentiment", "neutral")),
                            "sentiment_confidence": float(item.get("sentiment_confidence", 1.0)),
                            "signal_phrases": json.dumps(item.get("signal_phrases", []))
                        })
                    else:
                        # Fallback if the LLM skipped or hallucinated the ID
                        logger.warning(f"Review ID {orig_id} missing from LLM response. Creating fallback classification.")
                        final_results.append({
                            "review_id": orig_id,
                            "theme_ids": json.dumps([]),
                            "theme_confidence": 0.0,
                            "sentiment": "neutral",
                            "sentiment_confidence": 0.0,
                            "signal_phrases": json.dumps([])
                        })

                # Respect rate limits request delay
                time.sleep(config.GROQ_REQUEST_DELAY)
                return final_results

            except Exception as e:
                logger.error(f"Error classifying batch: {e}")
                if attempt == max_retries:
                    raise e
                
                logger.info(f"Waiting {delay}s before retrying...")
                time.sleep(delay)
                delay *= 2.0  # Exponential backoff

        return []
