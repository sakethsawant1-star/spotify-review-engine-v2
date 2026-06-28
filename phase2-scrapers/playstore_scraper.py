"""
playstore_scraper.py -- Google Play Store Scraper
===================================================
Scrapes Spotify reviews from Google Play Store using
the `google-play-scraper` library. No API key needed.

Usage:
    python playstore_scraper.py
    python playstore_scraper.py --count 2000
"""

import sys
import time
import argparse
import logging
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "phase1-setup"))
import config
from base_scraper import BaseScraper

from google_play_scraper import reviews, Sort
from google_play_scraper.exceptions import NotFoundError

logger = logging.getLogger("playstore_scraper")


class PlayStoreScraper(BaseScraper):
    """Scrapes Spotify reviews from Google Play Store."""

    def __init__(self):
        super().__init__(source_name="play_store")
        self.app_id = config.SPOTIFY_PLAY_STORE_ID

    def fetch(self, count: int = 3000) -> list[dict]:
        """
        Fetch Play Store reviews in batches of 200.
        google-play-scraper handles pagination internally via continuation_token.
        """
        all_reviews = []
        continuation_token = None
        batch_size = 200
        fetched_total = 0

        self.logger.info(f"Fetching up to {count} reviews for {self.app_id}")

        while fetched_total < count:
            remaining = count - fetched_total
            batch_count = min(batch_size, remaining)

            try:
                result, continuation_token = reviews(
                    self.app_id,
                    lang="en",
                    country="in",       # India region (primary market)
                    sort=Sort.NEWEST,
                    count=batch_count,
                    continuation_token=continuation_token,
                )

                if not result:
                    self.logger.info("No more reviews available from Play Store.")
                    break

                for r in result:
                    normalized = self._normalize(r)
                    if normalized:
                        all_reviews.append(normalized)

                fetched_total += len(result)
                self.logger.info(
                    f"  Fetched batch: {len(result)} reviews | Total so far: {fetched_total}"
                )

                if continuation_token is None:
                    self.logger.info("Reached end of Play Store reviews.")
                    break

                # Polite delay between batches
                time.sleep(1.0)

            except NotFoundError:
                self.logger.error(f"App '{self.app_id}' not found on Play Store.")
                break
            except Exception as e:
                self.logger.warning(f"Error fetching batch: {e}. Retrying in 5s...")
                time.sleep(5)
                continue

        self.logger.info(f"Total Play Store reviews collected: {len(all_reviews)}")
        return all_reviews

    def _normalize(self, raw: dict) -> dict | None:
        """Normalize a Play Store review into the standard schema."""
        text = (raw.get("content") or "").strip()
        if not text:
            return None

        # Parse date
        raw_date = raw.get("at")
        date_str = None
        if raw_date:
            try:
                if isinstance(raw_date, datetime):
                    date_str = raw_date.replace(tzinfo=timezone.utc).isoformat()
                else:
                    date_str = str(raw_date)
            except Exception:
                date_str = None

        review_id = str(raw.get("reviewId") or self.generate_id(text, self.source_name))

        return {
            "id": review_id,
            "source": self.source_name,
            "rating": raw.get("score"),          # 1-5
            "title": None,                        # Play Store has no review title
            "text": text,
            "date": date_str,
            "metadata": {
                "thumbs_up": raw.get("thumbsUpCount", 0),
                "reply_content": raw.get("replyContent"),
                "app_version": raw.get("appVersion"),
                "review_creator_image": None,
            },
        }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape Spotify Play Store reviews")
    parser.add_argument("--count", type=int, default=3000, help="Number of reviews to scrape")
    args = parser.parse_args()

    scraper = PlayStoreScraper()
    summary = scraper.run(count=args.count)

    print("\n--- Play Store Scraper Summary ---")
    for k, v in summary.items():
        print(f"  {k}: {v}")
