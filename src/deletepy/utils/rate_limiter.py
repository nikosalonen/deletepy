"""Adaptive rate limiter for Auth0 API requests.

This module provides conservative rate limiting that:
- Respects Auth0's rate limit headers
- Never goes faster than the minimum safe rate
- Backs off aggressively when limits are low
- Uses exponential backoff with jitter on 429 responses
"""

import random
import time
from dataclasses import dataclass, field
from typing import Any

from ..core.config import API_RATE_LIMIT

# Rate limiting thresholds (percentage of remaining requests)
HIGH_HEADROOM_THRESHOLD = 0.70  # >70% remaining: slight speedup allowed
LOW_HEADROOM_THRESHOLD = 0.20  # <20% remaining: slow down
CRITICAL_HEADROOM_THRESHOLD = 0.10  # <10% remaining: wait for reset

# Sleep times in seconds
MIN_SLEEP_TIME = 0.4  # Never faster than this (slight speedup from 0.5)
DEFAULT_SLEEP_TIME = API_RATE_LIMIT  # 0.5s - current default
CAUTIOUS_SLEEP_TIME = 1.0  # When headroom is low
MAX_BACKOFF_TIME = 60.0  # Maximum backoff time

# Backoff configuration
INITIAL_BACKOFF = 2.0  # Initial backoff on 429
BACKOFF_MULTIPLIER = 2.0  # Exponential multiplier
JITTER_FACTOR = 0.25  # Random jitter factor (0-25% added)

# Safety limits
MAX_CONSECUTIVE_429S = 5  # Abort after this many consecutive 429s


@dataclass
class RateLimitState:
    """Tracks rate limit state from Auth0 response headers.

    Attributes:
        remaining: Number of requests remaining in current window
        limit: Total requests allowed in window
        reset_time: Unix timestamp when limit resets
        consecutive_429s: Count of consecutive 429 responses
        last_request_time: Timestamp of last request
    """

    remaining: int | None = None
    limit: int | None = None
    reset_time: int | None = None
    consecutive_429s: int = 0
    last_request_time: float = 0.0
    _current_backoff: float = field(default=INITIAL_BACKOFF, repr=False)

    def reset_backoff(self) -> None:
        """Reset backoff state after successful request."""
        self.consecutive_429s = 0
        self._current_backoff = INITIAL_BACKOFF

    def increment_backoff(self) -> float:
        """Increment backoff and return sleep time with jitter.

        Returns:
            float: Sleep time in seconds with jitter applied
        """
        self.consecutive_429s += 1
        sleep_time = min(self._current_backoff, MAX_BACKOFF_TIME)

        # Add jitter to prevent thundering herd
        jitter = random.uniform(0, sleep_time * JITTER_FACTOR)
        sleep_time += jitter

        # Increase for next time
        self._current_backoff = min(
            self._current_backoff * BACKOFF_MULTIPLIER, MAX_BACKOFF_TIME
        )

        return sleep_time

    @property
    def headroom_ratio(self) -> float | None:
        """Calculate the ratio of remaining requests to limit.

        Returns:
            float or None: Ratio (0.0 to 1.0) or None if unknown
        """
        if self.remaining is None or self.limit is None or self.limit == 0:
            return None
        return self.remaining / self.limit

    @property
    def should_abort(self) -> bool:
        """Check if we should abort due to too many 429s.

        Returns:
            bool: True if we should abort
        """
        return self.consecutive_429s >= MAX_CONSECUTIVE_429S


class AdaptiveRateLimiter:
    """Adaptive rate limiter that respects Auth0's rate limits.

    This limiter:
    - Parses rate limit headers from responses
    - Adjusts sleep time based on remaining headroom
    - Uses exponential backoff on 429 responses
    - Logs warnings when limits are getting low
    """

    def __init__(
        self,
        min_sleep: float = MIN_SLEEP_TIME,
        default_sleep: float = DEFAULT_SLEEP_TIME,
        cautious_sleep: float = CAUTIOUS_SLEEP_TIME,
        conservative_mode: bool = False,
    ):
        """Initialize the rate limiter.

        Args:
            min_sleep: Minimum sleep time (never go faster)
            default_sleep: Default sleep time when headroom is normal
            cautious_sleep: Sleep time when headroom is low
            conservative_mode: If True, always use default_sleep or higher
        """
        self.min_sleep = min_sleep
        self.default_sleep = default_sleep
        self.cautious_sleep = cautious_sleep
        self.conservative_mode = conservative_mode
        self.state = RateLimitState()

    def parse_headers(self, headers: dict[str, Any]) -> None:
        """Parse rate limit headers from response.

        Auth0 returns headers like:
        - X-RateLimit-Limit: Total requests allowed
        - X-RateLimit-Remaining: Requests remaining
        - X-RateLimit-Reset: Unix timestamp when limit resets

        Args:
            headers: Response headers dictionary
        """
        # Parse each header separately to handle partial failures
        if "X-RateLimit-Remaining" in headers:
            try:
                self.state.remaining = int(headers["X-RateLimit-Remaining"])
            except (ValueError, TypeError):
                pass

        if "X-RateLimit-Limit" in headers:
            try:
                self.state.limit = int(headers["X-RateLimit-Limit"])
            except (ValueError, TypeError):
                pass

        if "X-RateLimit-Reset" in headers:
            try:
                self.state.reset_time = int(headers["X-RateLimit-Reset"])
            except (ValueError, TypeError):
                pass

    def calculate_sleep_time(self) -> float:
        """Calculate appropriate sleep time based on current state.

        Returns:
            float: Sleep time in seconds
        """
        # In conservative mode, never go below default
        if self.conservative_mode:
            return max(self.default_sleep, self._calculate_adaptive_sleep())

        return self._calculate_adaptive_sleep()

    def _calculate_adaptive_sleep(self) -> float:
        """Calculate adaptive sleep time based on headroom.

        Returns:
            float: Sleep time in seconds
        """
        headroom = self.state.headroom_ratio

        # If we don't have rate limit info, use default
        if headroom is None:
            return self.default_sleep

        # Critical: wait for reset
        if headroom < CRITICAL_HEADROOM_THRESHOLD:
            return self._calculate_wait_for_reset()

        # Low headroom: be cautious
        if headroom < LOW_HEADROOM_THRESHOLD:
            return self.cautious_sleep

        # Normal headroom: use default
        if headroom <= HIGH_HEADROOM_THRESHOLD:
            return self.default_sleep

        # High headroom: slight speedup allowed
        return self.min_sleep

    def _calculate_wait_for_reset(self) -> float:
        """Calculate wait time until rate limit resets.

        Returns:
            float: Sleep time in seconds (at least cautious_sleep)
        """
        if self.state.reset_time is None:
            return self.cautious_sleep

        current_time = time.time()
        wait_time = self.state.reset_time - current_time

        if wait_time <= 0:
            # Reset time has passed, use cautious sleep
            return self.cautious_sleep

        # Add a small buffer after reset
        return wait_time + 0.5

    def handle_429(self) -> float:
        """Handle a 429 Too Many Requests response.

        Returns:
            float: Backoff sleep time in seconds

        Raises:
            RateLimitExceededError: If too many consecutive 429s
        """
        sleep_time = self.state.increment_backoff()

        if self.state.should_abort:
            raise RateLimitExceededError(
                f"Aborting after {MAX_CONSECUTIVE_429S} consecutive rate limit errors. "
                "The Auth0 API rate limit has been exceeded. Please wait and try again later."
            )

        return sleep_time

    def record_success(self) -> None:
        """Record a successful request (non-429 response)."""
        self.state.reset_backoff()
        self.state.last_request_time = time.time()

    def wait(self, response_headers: dict[str, Any] | None = None) -> None:
        """Wait the appropriate amount of time before next request.

        Args:
            response_headers: Optional response headers to parse
        """
        if response_headers:
            self.parse_headers(response_headers)

        sleep_time = self.calculate_sleep_time()
        time.sleep(sleep_time)

    def get_status_summary(self) -> str:
        """Get a human-readable status summary.

        Returns:
            str: Status summary
        """
        headroom = self.state.headroom_ratio
        if headroom is None:
            return "Rate limit status: unknown"

        remaining = self.state.remaining or 0
        limit = self.state.limit or 0
        percentage = headroom * 100

        if headroom < CRITICAL_HEADROOM_THRESHOLD:
            return f"Rate limit CRITICAL: {remaining}/{limit} ({percentage:.0f}%) - waiting for reset"
        if headroom < LOW_HEADROOM_THRESHOLD:
            return f"Rate limit LOW: {remaining}/{limit} ({percentage:.0f}%) - slowing down"
        return f"Rate limit OK: {remaining}/{limit} ({percentage:.0f}%)"


class RateLimitExceededError(Exception):
    """Raised when rate limit is exceeded and we should abort."""

    pass


# Global rate limiter instance for shared state across requests
_global_limiter: AdaptiveRateLimiter | None = None


def get_rate_limiter(conservative: bool = False) -> AdaptiveRateLimiter:
    """Get or create the global rate limiter instance.

    Args:
        conservative: If True, use conservative mode

    Returns:
        AdaptiveRateLimiter: The global rate limiter
    """
    global _global_limiter
    if _global_limiter is None:
        _global_limiter = AdaptiveRateLimiter(conservative_mode=conservative)
    return _global_limiter


def reset_rate_limiter() -> None:
    """Reset the global rate limiter (useful for testing)."""
    global _global_limiter
    _global_limiter = None
