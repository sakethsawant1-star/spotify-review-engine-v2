"""
quote_extractor.py — Extracts representative quotes for each classified theme.
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
logger = logging.getLogger("QuoteExtractor")

class QuoteExtractor:
    """Extracts high-quality, representative, and PII-free quotes for each theme using Groq."""

    def __init__(self, api_key: str = None):
        self.api_key = api_key or config.GROQ_API_KEY
        if not self.api_key:
            raise ValueError("GROQ_API_KEY is not set in environment or config.")
        self.client = Groq(api_key=self.api_key)
        self.prompt_path = PROJECT_ROOT / "phase4-agent" / "prompts" / "quote_prompt.txt"
        self.system_prompt = self._load_system_prompt()

    def _load_system_prompt(self) -> str:
        """Loads the system prompt from prompts/quote_prompt.txt."""
        if not self.prompt_path.exists():
            raise FileNotFoundError(f"System prompt file not found at {self.prompt_path}")
        with open(self.prompt_path, "r", encoding="utf-8") as f:
            return f.read().strip()

    def extract_quotes_for_theme(self, theme_id: str, reviews: List[Dict[str, Any]], max_retries: int = 5) -> List[Dict[str, Any]]:
        """
        Extracts representative quotes for a specific theme.
        Input `reviews` should contain: 'id', 'text', 'source', 'rating', 'engagement_score'.
        """
        if not reviews:
            logger.info(f"No reviews available for theme {theme_id}.")
            return []

        theme_name = config.THEME_TAXONOMY.get(theme_id, "Unknown Theme")
        logger.info(f"Extracting quotes for theme {theme_id} ({theme_name}) from {len(reviews)} reviews...")

        # Rank reviews by engagement score first, then by word count/length to ensure substance
        # Limit to top 8 to keep prompt clean, cost-efficient and avoid 6000 TPM limit
        sorted_reviews = sorted(
            reviews,
            key=lambda r: (r.get("engagement_score") or 0, len(r.get("text") or "")),
            reverse=True
        )
        candidates = sorted_reviews[:8]

        # Prepare payload
        payload = [{
            "id": r["id"],
            "text": r["text"],
            "source": r["source"],
            "rating": r.get("rating"),
            "engagement_score": r.get("engagement_score", 0)
        } for r in candidates]

        user_content = json.dumps({
            "theme_id": theme_id,
            "theme_name": theme_name,
            "reviews": payload
        }, ensure_ascii=False)

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
                    max_tokens=1000,
                    response_format={"type": "json_object"}
                )

                content = response.choices[0].message.content
                result_json = json.loads(content)

                if "quotes" not in result_json:
                    raise ValueError("LLM response JSON is missing 'quotes' list key.")

                extracted = result_json["quotes"]
                logger.info(f"Successfully extracted {len(extracted)} quotes for theme {theme_id}.")
                
                # Respect rate limits request delay
                time.sleep(config.GROQ_REQUEST_DELAY)
                return extracted

            except Exception as e:
                logger.error(f"Error extracting quotes for theme {theme_id}: {e}")
                if attempt == max_retries:
                    raise e
                
                logger.info(f"Waiting {delay}s before retrying...")
                time.sleep(delay)
                delay *= 2.0

        return []
