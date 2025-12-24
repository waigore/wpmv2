"""Rate limiting utility for API calls."""

import logging
import time
from datetime import datetime, timedelta

import pytz

logger = logging.getLogger(__name__)


class RateLimiter:
    """Rate limiting utility for API calls."""

    def __init__(self, max_calls_per_minute: int = 60):
        """Initialize rate limiter.

        Args:
            max_calls_per_minute: Maximum number of API calls per minute
        """
        self.max_calls_per_minute = max_calls_per_minute
        self.call_times: list[datetime] = []

    def wait_if_needed(self) -> None:
        """Wait if rate limit would be exceeded."""
        now = datetime.now(pytz.UTC)

        minute_ago = now - timedelta(minutes=1)
        self.call_times = [t for t in self.call_times if t > minute_ago]

        if len(self.call_times) >= self.max_calls_per_minute:
            oldest_call = min(self.call_times)
            wait_until = oldest_call + timedelta(minutes=1)

            if wait_until > now:
                wait_seconds = (wait_until - now).total_seconds()
                logger.info(f"Rate limit reached. Waiting {wait_seconds:.1f} seconds")
                time.sleep(wait_seconds)

        self.call_times.append(now)

