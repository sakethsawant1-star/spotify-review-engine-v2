"""
rate_limiter.py — Groq API Rate Limiter for Phase 4
====================================================
Ported from the M3 Groww Review Agent project, adapted for the
Spotify Review Discovery Engine's config values.

Wraps all Groq API calls with:
  - Pre-flight token estimation (char/4 heuristic)
  - Minimum 60-second spacing between consecutive calls
  - Exponential backoff on 429 Too Many Requests (max 3 retries)
  - Daily token budget tracker (aborts at 90K threshold)
"""

import sys
import time
import logging
from pathlib import Path
from datetime import datetime, date
from typing import Dict, Optional, Any

# Ensure we can import config from phase1-setup
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "phase1-setup"))

import config

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Rate limit constants (derived from config or M3 defaults)
# ---------------------------------------------------------------------------
MIN_CALL_SPACING_SECONDS = getattr(config, "GROQ_REQUEST_DELAY", 60.0)
MAX_TOKENS_PER_CALL = getattr(config, "GROQ_RATE_LIMIT_TPM", 6_000)
DAILY_TOKEN_BUDGET = getattr(config, "GROQ_DAILY_TOKEN_BUDGET", 90_000)
MAX_RETRIES = 3
INITIAL_BACKOFF_SECONDS = 30


class TokenBudgetExhausted(Exception):
    """Raised when daily Groq token budget is exhausted."""
    pass


class RateLimitExceeded(Exception):
    """Raised when rate limit retries are exhausted."""
    pass


class GroqRateLimiter:
    """
    Stateful rate limiter for Groq API calls.

    Tracks:
      - Last call timestamp (for 60s spacing)
      - Daily token usage (for 90K budget)
      - Call count (for logging)
    """

    def __init__(
        self,
        min_spacing: float = MIN_CALL_SPACING_SECONDS,
        daily_budget: int = DAILY_TOKEN_BUDGET,
        max_tokens_per_call: int = MAX_TOKENS_PER_CALL,
    ):
        self.min_spacing = min_spacing
        self.daily_budget = daily_budget
        self.max_tokens_per_call = max_tokens_per_call
        self._last_call_time: Optional[float] = None
        self._daily_tokens_used: int = 0
        self._daily_requests: int = 0
        self._budget_date: date = date.today()
        self._call_log: list = []

    def _reset_daily_if_needed(self):
        """Reset daily counters if the date has changed."""
        today = date.today()
        if today != self._budget_date:
            logger.info(
                f"New day detected. Resetting daily budget. "
                f"Yesterday's usage: {self._daily_tokens_used} tokens, "
                f"{self._daily_requests} requests."
            )
            self._daily_tokens_used = 0
            self._daily_requests = 0
            self._budget_date = today

    def estimate_tokens(self, text: str) -> int:
        """Estimate token count using char/4 heuristic."""
        return max(1, len(text) // 4)

    def estimate_call_tokens(self, messages: list) -> int:
        """
        Estimate total input tokens for a Groq chat completion call.
        Sums token estimates across all message contents.
        """
        total = 0
        for msg in messages:
            content = msg.get("content", "")
            total += self.estimate_tokens(content)
            # ~4 tokens overhead per message for role/formatting
            total += 4
        return total

    def check_budget(self, estimated_input_tokens: int, estimated_output_tokens: int = 1500):
        """
        Pre-flight check: will this call exceed our budgets?

        Raises:
            TokenBudgetExhausted: if daily budget would be exceeded
        """
        self._reset_daily_if_needed()

        total_estimated = estimated_input_tokens + estimated_output_tokens

        projected_daily = self._daily_tokens_used + total_estimated
        if projected_daily > self.daily_budget:
            raise TokenBudgetExhausted(
                f"Daily Groq token budget exhausted. "
                f"Used: {self._daily_tokens_used}, "
                f"Estimated: {total_estimated}, "
                f"Budget: {self.daily_budget}. "
                f"Try again tomorrow."
            )

    def wait_for_spacing(self):
        """
        Block until at least `min_spacing` seconds have elapsed
        since the last API call.
        """
        if self._last_call_time is None:
            return

        elapsed = time.time() - self._last_call_time
        if elapsed < self.min_spacing:
            wait_time = self.min_spacing - elapsed
            logger.info(f"Rate limiter: waiting {wait_time:.1f}s before next call...")
            print(f"  [Rate Limiter] Waiting {wait_time:.1f}s before next Groq call...")
            time.sleep(wait_time)

    def record_call(self, input_tokens: int, output_tokens: int, model: str = ""):
        """
        Record a completed API call for tracking.

        Args:
            input_tokens: Actual input tokens from API response.
            output_tokens: Actual output tokens from API response.
            model: Model name for logging.
        """
        self._last_call_time = time.time()
        total = input_tokens + output_tokens
        self._daily_tokens_used += total
        self._daily_requests += 1

        entry = {
            "timestamp": datetime.now().isoformat(),
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total,
            "daily_cumulative": self._daily_tokens_used,
            "daily_requests": self._daily_requests,
            "model": model,
        }
        self._call_log.append(entry)

        logger.info(
            f"Groq call #{self._daily_requests}: "
            f"{input_tokens} in + {output_tokens} out = {total} tokens. "
            f"Daily total: {self._daily_tokens_used}/{self.daily_budget}"
        )
        print(
            f"  [Rate Limiter] Call #{self._daily_requests}: "
            f"{total} tokens (daily: {self._daily_tokens_used}/{self.daily_budget})"
        )

    def execute_with_retry(self, api_call_fn, *args, **kwargs) -> Any:
        """
        Execute a Groq API call with exponential backoff on 429 errors.

        Args:
            api_call_fn: Callable that makes the Groq API call.
            *args, **kwargs: Passed to api_call_fn.

        Returns:
            The API response.

        Raises:
            RateLimitExceeded: if all retries are exhausted.
        """
        backoff = INITIAL_BACKOFF_SECONDS

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                return api_call_fn(*args, **kwargs)
            except Exception as e:
                error_str = str(e)
                # Check for rate limit errors (429)
                if "429" in error_str or "rate_limit" in error_str.lower():
                    if attempt == MAX_RETRIES:
                        raise RateLimitExceeded(
                            f"Groq rate limit: all {MAX_RETRIES} retries exhausted. "
                            f"Last error: {error_str}"
                        )
                    logger.warning(
                        f"Groq 429 rate limit hit (attempt {attempt}/{MAX_RETRIES}). "
                        f"Waiting {backoff}s..."
                    )
                    print(
                        f"  [Rate Limiter] 429 rate limit (attempt {attempt}/{MAX_RETRIES}). "
                        f"Retrying in {backoff}s..."
                    )
                    time.sleep(backoff)
                    backoff *= 2  # Exponential backoff
                else:
                    # Non-rate-limit error — re-raise immediately
                    raise

    @property
    def daily_usage_summary(self) -> Dict:
        """Return a summary of today's API usage."""
        self._reset_daily_if_needed()
        return {
            "date": self._budget_date.isoformat(),
            "tokens_used": self._daily_tokens_used,
            "tokens_budget": self.daily_budget,
            "tokens_remaining": self.daily_budget - self._daily_tokens_used,
            "requests_count": self._daily_requests,
            "utilization_pct": round(
                self._daily_tokens_used / self.daily_budget * 100, 1
            ),
        }

    @property
    def call_log(self) -> list:
        """Return the full call log for this session."""
        return list(self._call_log)
