"""
appstore_scraper.py -- Apple App Store Scraper
================================================
Scrapes Spotify reviews from the Apple App Store using
Apple's public iTunes RSS JSON feeds. No API key needed.
Scrapes across multiple country storefronts (IN, US, GB).

Usage:
    python appstore_scraper.py
    python appstore_scraper.py --count 2000
"""

import sys
import time
import argparse
import logging
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "phase1-setup"))
import config
from base_scraper import BaseScraper

logger = logging.getLogger("appstore_scraper")

ITUNES_RSS_BASE = "https://itunes.apple.com"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}

# Country storefronts to scrape
COUNTRIES = ["in", "us", "gb"]

# iTunes RSS caps pagination at page 10 (~50 reviews per page)
MAX_PAGES = 10
REVIEWS_PER_PAGE = 50

# Sort modes — mostrecent for recency, mosthelpful for high-signal reviews
SORT_MODES = ["mostrecent", "mosthelpful"]


class AppStoreScraper(BaseScraper):
    """Scrapes Spotify reviews from Apple iTunes RSS JSON feeds."""

    def __init__(self):
        super().__init__(source_name="app_store")
        self.app_id = config.SPOTIFY_APP_STORE_ID
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def fetch(self, count: int = 2000) -> list[dict]:
        """
        Fetch App Store reviews from multiple country storefronts.
        Paginates through iTunes RSS JSON feeds until the target is met
        or all available pages are exhausted.
        """
        all_reviews: list[dict] = []
        seen_ids: set[str] = set()

        for country in COUNTRIES:
            if len(all_reviews) >= count:
                break

            remaining = count - len(all_reviews)
            countries_left = len(COUNTRIES) - COUNTRIES.index(country)
            country_target = min(
                remaining,
                max(50, (remaining + countries_left - 1) // countries_left),
            )

            self.logger.info(
                f"Fetching up to {country_target} reviews from App Store [{country.upper()}]"
            )

            country_reviews = self._scrape_country(country, country_target, seen_ids)
            all_reviews.extend(country_reviews)

            self.logger.info(
                f"  [{country.upper()}] Collected: {len(country_reviews)} reviews "
                f"(running total: {len(all_reviews)})"
            )

            time.sleep(1.5)

        self.logger.info(f"Total App Store reviews collected: {len(all_reviews)}")
        return all_reviews[:count]

    def _scrape_country(
        self, country: str, target: int, seen_ids: set[str]
    ) -> list[dict]:
        """Scrape reviews for one country across sort modes and pages."""
        results: list[dict] = []

        for sort_mode in SORT_MODES:
            if len(results) >= target:
                break

            for page in range(1, MAX_PAGES + 1):
                if len(results) >= target:
                    break

                entries = self._fetch_page(country, page, sort_mode)
                if not entries:
                    break

                page_added = 0
                for entry in entries:
                    normalized = self._normalize(entry, country)
                    if not normalized:
                        continue

                    review_id = normalized["id"]
                    if review_id in seen_ids:
                        continue

                    seen_ids.add(review_id)
                    results.append(normalized)
                    page_added += 1

                    if len(results) >= target:
                        break

                self.logger.debug(
                    f"  [{country.upper()}] {sort_mode} page {page}: "
                    f"{page_added} new reviews"
                )

                if page_added == 0 and page > 1:
                    break

                time.sleep(1.0)

        return results

    def _fetch_page(
        self, country: str, page: int, sort_mode: str, retries: int = 3
    ) -> list[dict]:
        """Fetch one page of reviews from the iTunes RSS JSON feed."""
        url = (
            f"{ITUNES_RSS_BASE}/{country}/rss/customerreviews/"
            f"page={page}/id={self.app_id}/sortby={sort_mode}/json"
        )

        for attempt in range(retries):
            try:
                resp = self.session.get(url, timeout=15)

                if resp.status_code == 400:
                    return []

                if resp.status_code == 429:
                    wait = 30 * (attempt + 1)
                    self.logger.warning(f"Rate limited. Waiting {wait}s...")
                    time.sleep(wait)
                    continue

                if resp.status_code != 200:
                    self.logger.warning(f"HTTP {resp.status_code} for {country} page {page}")
                    return []

                data = resp.json()
                feed = data.get("feed", {})
                entries = feed.get("entry", [])

                if not entries:
                    return []

                if isinstance(entries, dict):
                    entries = [entries]

                return entries

            except requests.RequestException as e:
                self.logger.warning(
                    f"Request error [{country} page {page}]: {e} "
                    f"(attempt {attempt + 1}/{retries})"
                )
                time.sleep(2 * (attempt + 1))
            except ValueError as e:
                self.logger.warning(f"JSON parse error [{country} page {page}]: {e}")
                return []

        return []

    @staticmethod
    def _label(entry: dict, key: str) -> str | None:
        """Extract a string label from an iTunes RSS entry field."""
        value = entry.get(key)
        if isinstance(value, dict):
            label = value.get("label")
            return str(label).strip() if label is not None else None
        return None

    def _normalize(self, entry: dict, country: str) -> dict | None:
        """Normalize an iTunes RSS review entry into the standard schema."""
        rating_label = self._label(entry, "im:rating")
        if not rating_label:
            return None

        text = self._label(entry, "content")
        if not text:
            return None

        apple_id = self._label(entry, "id")
        review_id = (
            f"app_store_{apple_id}"
            if apple_id
            else self.generate_id(text, f"{self.source_name}_{country}")
        )

        try:
            rating = int(rating_label)
        except ValueError:
            rating = None

        vote_sum = self._label(entry, "im:voteSum")
        vote_count = self._label(entry, "im:voteCount")

        return {
            "id": review_id,
            "source": self.source_name,
            "rating": rating,
            "title": self._label(entry, "title"),
            "text": text,
            "date": self._label(entry, "updated"),
            "metadata": {
                "country": country,
                "apple_review_id": apple_id,
                "app_version": self._label(entry, "im:version"),
                "vote_sum": int(vote_sum) if vote_sum and vote_sum.isdigit() else None,
                "vote_count": int(vote_count) if vote_count and vote_count.isdigit() else None,
            },
        }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape Spotify App Store reviews")
    parser.add_argument("--count", type=int, default=2000, help="Number of reviews to scrape")
    args = parser.parse_args()

    scraper = AppStoreScraper()
    summary = scraper.run(count=args.count)

    print("\n--- App Store Scraper Summary ---")
    for k, v in summary.items():
        print(f"  {k}: {v}")
