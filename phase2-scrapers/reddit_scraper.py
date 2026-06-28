"""
reddit_scraper.py -- Reddit RSS/Atom Feed Scraper (quality-first)
=================================================================
Scrapes Spotify-related posts from Reddit using public RSS/Atom feeds.
No API key or PRAW required.

Quality strategy:
  - High-signal subreddits only (Spotify-focused + discovery culture)
  - One feed per subreddit (fewer requests, less rate limiting)
  - Keyword relevance filter on broader subs
  - Lower volume target (~400) with stricter post selection

Usage:
    python reddit_scraper.py
    python reddit_scraper.py --count 400
"""

import re
import sys
import time
import argparse
import logging
import xml.etree.ElementTree as ET
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "phase1-setup"))
import config
from base_scraper import BaseScraper

logger = logging.getLogger("reddit_scraper")

REDDIT_BASE = "https://www.reddit.com"
ATOM_NS = "http://www.w3.org/2005/Atom"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/atom+xml, application/xml, text/xml, */*",
}

# Per-subreddit caps: one RSS request each, quality tier controls filtering
SUBREDDIT_CONFIG = [
    {"name": "spotify", "max_posts": 80, "feed": "new", "tier": "spotify"},
    {"name": "truespotify", "max_posts": 60, "feed": "new", "tier": "spotify"},
    {"name": "spotifyplaylists", "max_posts": 50, "feed": "new", "tier": "spotify"},
    {"name": "SpotifyPremium", "max_posts": 40, "feed": "new", "tier": "spotify"},
    {"name": "ifyoulikeblank", "max_posts": 50, "feed": "hot", "tier": "discovery"},
    {"name": "MusicRecommendations", "max_posts": 40, "feed": "hot", "tier": "discovery"},
    {"name": "listentothis", "max_posts": 40, "feed": "hot", "tier": "discovery"},
    {"name": "streaming", "max_posts": 30, "feed": "hot", "tier": "discovery"},
]

DELAY_AFTER_FEED = 4.0
DELAY_BETWEEN_SUBS = 8.0


class RedditScraper(BaseScraper):
    """Scrapes high-signal Reddit posts via public RSS/Atom feeds."""

    def __init__(self):
        super().__init__(source_name="reddit")
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        lexicon = config.load_discovery_keywords()
        self._primary_kw = [k.lower() for k in lexicon.get("primary", [])]
        self._secondary_kw = [k.lower() for k in lexicon.get("secondary", [])]

    def _fetch_rss(self, url: str, retries: int = 2) -> ET.Element | None:
        """Fetch and parse an RSS/Atom feed."""
        for attempt in range(retries):
            try:
                resp = self.session.get(url, timeout=15)

                if resp.status_code == 429:
                    wait = 45 * (attempt + 1)
                    self.logger.warning(f"Rate limited. Waiting {wait}s...")
                    time.sleep(wait)
                    continue

                if resp.status_code == 200:
                    return ET.fromstring(resp.content)

                self.logger.warning(f"HTTP {resp.status_code} for: {url}")
                return None

            except requests.RequestException as e:
                self.logger.warning(f"Request error (attempt {attempt + 1}): {e}")
                time.sleep(5)
            except ET.ParseError as e:
                self.logger.warning(f"XML parse error: {e}")
                return None

        return None

    def _parse_atom_entries(self, root: ET.Element) -> list[dict]:
        entries = []
        for entry in root.findall(f"{{{ATOM_NS}}}entry"):
            title_el = entry.find(f"{{{ATOM_NS}}}title")
            title = (title_el.text or "").strip() if title_el is not None else ""

            content_el = entry.find(f"{{{ATOM_NS}}}content")
            summary_el = entry.find(f"{{{ATOM_NS}}}summary")
            raw_content = ""
            if content_el is not None and content_el.text:
                raw_content = content_el.text.strip()
            elif summary_el is not None and summary_el.text:
                raw_content = summary_el.text.strip()

            content = self._strip_html(raw_content)

            link_el = entry.find(f"{{{ATOM_NS}}}link")
            link = link_el.get("href", "") if link_el is not None else ""

            published_el = entry.find(f"{{{ATOM_NS}}}published")
            updated_el = entry.find(f"{{{ATOM_NS}}}updated")
            date_str = None
            for el in [published_el, updated_el]:
                if el is not None and el.text:
                    date_str = el.text.strip()
                    break

            author_el = entry.find(f"{{{ATOM_NS}}}author")
            author_name = ""
            if author_el is not None:
                name_el = author_el.find(f"{{{ATOM_NS}}}name")
                if name_el is not None:
                    author_name = (name_el.text or "").strip()

            entries.append({
                "title": title,
                "content": content,
                "link": link,
                "date": date_str,
                "author": author_name,
            })

        return entries

    def _strip_html(self, html: str) -> str:
        clean = re.sub(r"<[^>]+>", " ", html)
        clean = clean.replace("&amp;", "&").replace("&lt;", "<").replace(
            "&gt;", ">"
        ).replace("&quot;", '"').replace("&#39;", "'").replace("&nbsp;", " ")
        return re.sub(r"\s+", " ", clean).strip()

    def _keyword_counts(self, text: str) -> tuple[int, int]:
        lower = text.lower()
        primary = sum(1 for kw in self._primary_kw if kw in lower)
        secondary = sum(1 for kw in self._secondary_kw if kw in lower)
        return primary, secondary

    def _passes_quality_filter(self, text: str, tier: str) -> bool:
        """Spotif-y subs: context is enough. Discovery subs: need relevance signals."""
        lower = text.lower()
        if "spotify" in lower:
            return True

        primary, secondary = self._keyword_counts(text)
        if tier == "spotify":
            return primary >= 1 or secondary >= 2
        return primary >= 1 or secondary >= 2

    def _normalize_entry(
        self, entry: dict, subreddit: str, feed_type: str, tier: str
    ) -> dict | None:
        title = entry.get("title", "").strip()
        content = entry.get("content", "").strip()

        if content and content != title:
            text = f"{title}\n\n{content}" if title else content
        else:
            text = title

        text = text.strip()
        if not text or len(text) < 30:
            return None

        if text.lower() in ("[deleted]", "[removed]"):
            return None

        if not self._passes_quality_filter(text, tier):
            return None

        link = entry.get("link", "")
        review_id = self.generate_id(link or text, f"reddit_{subreddit}")
        primary, secondary = self._keyword_counts(text)

        return {
            "id": f"reddit_{review_id}",
            "source": self.source_name,
            "rating": None,
            "title": title or None,
            "text": text,
            "date": entry.get("date"),
            "metadata": {
                "subreddit": subreddit,
                "feed_type": feed_type,
                "link": link,
                "author": entry.get("author", ""),
                "type": "post",
                "quality_tier": tier,
                "discovery_keyword_hits": {
                    "primary": primary,
                    "secondary": secondary,
                },
            },
        }

    def _scrape_subreddit(
        self, subreddit: str, target: int, feed_type: str, tier: str
    ) -> list[dict]:
        results = []
        seen_ids = set()
        skipped_quality = 0

        url = f"{REDDIT_BASE}/r/{subreddit}/{feed_type}.rss?limit=100"
        self.logger.info(f"  [r/{subreddit}] Fetching '{feed_type}' feed (tier={tier})")

        root = self._fetch_rss(url)
        if root is None:
            self.logger.warning(f"  [r/{subreddit}] Failed to fetch feed")
            return results

        entries = self._parse_atom_entries(root)
        self.logger.info(f"  [r/{subreddit}] Parsed {len(entries)} entries")

        for entry in entries:
            if len(results) >= target:
                break

            normalized = self._normalize_entry(entry, subreddit, feed_type, tier)
            if not normalized:
                skipped_quality += 1
                continue

            if normalized["id"] in seen_ids:
                continue
            seen_ids.add(normalized["id"])
            results.append(normalized)

        self.logger.info(
            f"  [r/{subreddit}] Collected {len(results)} posts "
            f"(filtered out {skipped_quality})"
        )
        time.sleep(DELAY_AFTER_FEED)
        return results

    def fetch(self, count: int = 400) -> list[dict]:
        """Fetch quality-filtered Reddit posts across high-signal subreddits."""
        all_items = []
        seen_global: set[str] = set()

        self.logger.info(
            f"Starting quality-first Reddit scrape. Target: {count} items, "
            f"{len(SUBREDDIT_CONFIG)} subreddits"
        )

        for i, sub_cfg in enumerate(SUBREDDIT_CONFIG):
            if len(all_items) >= count:
                break

            subreddit = sub_cfg["name"]
            remaining = count - len(all_items)
            sub_target = min(sub_cfg["max_posts"], remaining)

            self.logger.info(
                f"Scraping r/{subreddit} (target: {sub_target}, feed: {sub_cfg['feed']})"
            )

            items = self._scrape_subreddit(
                subreddit,
                sub_target,
                sub_cfg["feed"],
                sub_cfg["tier"],
            )

            for item in items:
                if item["id"] in seen_global:
                    continue
                seen_global.add(item["id"])
                all_items.append(item)
                if len(all_items) >= count:
                    break

            if i < len(SUBREDDIT_CONFIG) - 1 and len(all_items) < count:
                self.logger.info(f"Pausing {DELAY_BETWEEN_SUBS}s before next subreddit...")
                time.sleep(DELAY_BETWEEN_SUBS)

        self.logger.info(f"Total Reddit items collected: {len(all_items)}")
        return all_items[:count]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape Reddit via RSS feeds")
    parser.add_argument(
        "--count",
        type=int,
        default=config.SCRAPER_TARGETS.get("reddit", 400),
        help="Target number of quality posts",
    )
    args = parser.parse_args()

    scraper = RedditScraper()
    summary = scraper.run(count=args.count)

    print("\n--- Reddit Scraper Summary ---")
    for k, v in summary.items():
        print(f"  {k}: {v}")
