"""Tests for the adaptive rate limiter."""

import time
from unittest.mock import patch

import pytest

from src.deletepy.utils.rate_limiter import (
    CRITICAL_HEADROOM_THRESHOLD,
    HIGH_HEADROOM_THRESHOLD,
    LOW_HEADROOM_THRESHOLD,
    MAX_CONSECUTIVE_429S,
    AdaptiveRateLimiter,
    RateLimitExceededError,
    RateLimitState,
    get_rate_limiter,
    reset_rate_limiter,
)


class TestRateLimitState:
    """Tests for RateLimitState dataclass."""

    def test_initial_state(self):
        """Test initial state values."""
        state = RateLimitState()
        assert state.remaining is None
        assert state.limit is None
        assert state.reset_time is None
        assert state.consecutive_429s == 0

    def test_headroom_ratio_with_values(self):
        """Test headroom ratio calculation."""
        state = RateLimitState(remaining=70, limit=100)
        assert state.headroom_ratio == 0.7

    def test_headroom_ratio_none_when_missing(self):
        """Test headroom ratio is None when values missing."""
        state = RateLimitState(remaining=None, limit=100)
        assert state.headroom_ratio is None

        state = RateLimitState(remaining=70, limit=None)
        assert state.headroom_ratio is None

    def test_headroom_ratio_zero_limit(self):
        """Test headroom ratio with zero limit."""
        state = RateLimitState(remaining=0, limit=0)
        assert state.headroom_ratio is None

    def test_reset_backoff(self):
        """Test backoff reset."""
        state = RateLimitState()
        state.consecutive_429s = 3
        state._current_backoff = 16.0

        state.reset_backoff()

        assert state.consecutive_429s == 0
        assert state._current_backoff == 2.0  # INITIAL_BACKOFF

    def test_increment_backoff(self):
        """Test backoff increment with jitter."""
        state = RateLimitState()

        # First increment
        sleep_time = state.increment_backoff()
        assert state.consecutive_429s == 1
        assert 2.0 <= sleep_time <= 2.5  # 2s + up to 25% jitter

        # Second increment
        sleep_time = state.increment_backoff()
        assert state.consecutive_429s == 2
        assert 4.0 <= sleep_time <= 5.0  # 4s + up to 25% jitter

    def test_should_abort(self):
        """Test abort condition."""
        state = RateLimitState()
        assert not state.should_abort

        state.consecutive_429s = MAX_CONSECUTIVE_429S - 1
        assert not state.should_abort

        state.consecutive_429s = MAX_CONSECUTIVE_429S
        assert state.should_abort


class TestAdaptiveRateLimiter:
    """Tests for AdaptiveRateLimiter class."""

    def test_init_default_values(self):
        """Test default initialization."""
        limiter = AdaptiveRateLimiter()
        assert limiter.min_sleep == 0.4
        assert limiter.default_sleep == 0.5
        assert limiter.cautious_sleep == 1.0
        assert not limiter.conservative_mode

    def test_init_custom_values(self):
        """Test custom initialization."""
        limiter = AdaptiveRateLimiter(
            min_sleep=0.3,
            default_sleep=0.6,
            cautious_sleep=1.5,
            conservative_mode=True,
        )
        assert limiter.min_sleep == 0.3
        assert limiter.default_sleep == 0.6
        assert limiter.cautious_sleep == 1.5
        assert limiter.conservative_mode

    def test_parse_headers(self):
        """Test header parsing."""
        limiter = AdaptiveRateLimiter()
        headers = {
            "X-RateLimit-Remaining": "50",
            "X-RateLimit-Limit": "100",
            "X-RateLimit-Reset": "1234567890",
        }

        limiter.parse_headers(headers)

        assert limiter.state.remaining == 50
        assert limiter.state.limit == 100
        assert limiter.state.reset_time == 1234567890

    def test_parse_headers_invalid_values(self):
        """Test header parsing with invalid values."""
        limiter = AdaptiveRateLimiter()
        headers = {
            "X-RateLimit-Remaining": "invalid",
            "X-RateLimit-Limit": "100",
        }

        # Should not raise, just ignore invalid values
        limiter.parse_headers(headers)
        assert limiter.state.remaining is None
        assert limiter.state.limit == 100

    def test_calculate_sleep_time_high_headroom(self):
        """Test sleep time with high headroom (>70%)."""
        limiter = AdaptiveRateLimiter()
        limiter.state.remaining = 80
        limiter.state.limit = 100

        sleep_time = limiter.calculate_sleep_time()
        assert sleep_time == limiter.min_sleep  # 0.4s

    def test_calculate_sleep_time_normal_headroom(self):
        """Test sleep time with normal headroom (20-70%)."""
        limiter = AdaptiveRateLimiter()
        limiter.state.remaining = 50
        limiter.state.limit = 100

        sleep_time = limiter.calculate_sleep_time()
        assert sleep_time == limiter.default_sleep  # 0.5s

    def test_calculate_sleep_time_low_headroom(self):
        """Test sleep time with low headroom (10-20%)."""
        limiter = AdaptiveRateLimiter()
        limiter.state.remaining = 15
        limiter.state.limit = 100

        sleep_time = limiter.calculate_sleep_time()
        assert sleep_time == limiter.cautious_sleep  # 1.0s

    def test_calculate_sleep_time_critical_headroom(self):
        """Test sleep time with critical headroom (<10%)."""
        limiter = AdaptiveRateLimiter()
        limiter.state.remaining = 5
        limiter.state.limit = 100
        limiter.state.reset_time = int(time.time()) + 15  # 15 seconds from now

        sleep_time = limiter.calculate_sleep_time()
        # Should wait for reset + buffer (0.5s)
        # Allow some tolerance for timing variations
        assert sleep_time >= 14  # At least 15 - 1s tolerance

    def test_calculate_sleep_time_conservative_mode(self):
        """Test conservative mode never goes below default."""
        limiter = AdaptiveRateLimiter(conservative_mode=True)
        limiter.state.remaining = 90
        limiter.state.limit = 100

        sleep_time = limiter.calculate_sleep_time()
        # In conservative mode, even with high headroom, use default
        assert sleep_time >= limiter.default_sleep

    def test_calculate_sleep_time_unknown_headroom(self):
        """Test sleep time when headroom is unknown."""
        limiter = AdaptiveRateLimiter()
        # No state set - headroom is None

        sleep_time = limiter.calculate_sleep_time()
        assert sleep_time == limiter.default_sleep

    def test_handle_429_increments_backoff(self):
        """Test 429 handling increments backoff."""
        limiter = AdaptiveRateLimiter()

        sleep_time = limiter.handle_429()
        assert limiter.state.consecutive_429s == 1
        assert sleep_time >= 2.0

    def test_handle_429_raises_after_max(self):
        """Test 429 handling raises after max attempts."""
        limiter = AdaptiveRateLimiter()
        limiter.state.consecutive_429s = MAX_CONSECUTIVE_429S - 1

        with pytest.raises(RateLimitExceededError):
            limiter.handle_429()

    def test_record_success_resets_backoff(self):
        """Test success recording resets backoff."""
        limiter = AdaptiveRateLimiter()
        limiter.state.consecutive_429s = 3

        limiter.record_success()

        assert limiter.state.consecutive_429s == 0

    def test_get_status_summary_unknown(self):
        """Test status summary when unknown."""
        limiter = AdaptiveRateLimiter()
        summary = limiter.get_status_summary()
        assert "unknown" in summary

    def test_get_status_summary_critical(self):
        """Test status summary when critical."""
        limiter = AdaptiveRateLimiter()
        limiter.state.remaining = 5
        limiter.state.limit = 100

        summary = limiter.get_status_summary()
        assert "CRITICAL" in summary

    def test_get_status_summary_low(self):
        """Test status summary when low."""
        limiter = AdaptiveRateLimiter()
        limiter.state.remaining = 15
        limiter.state.limit = 100

        summary = limiter.get_status_summary()
        assert "LOW" in summary

    def test_get_status_summary_ok(self):
        """Test status summary when OK."""
        limiter = AdaptiveRateLimiter()
        limiter.state.remaining = 70
        limiter.state.limit = 100

        summary = limiter.get_status_summary()
        assert "OK" in summary


class TestGlobalRateLimiter:
    """Tests for global rate limiter functions."""

    def setup_method(self):
        """Reset global limiter before each test."""
        reset_rate_limiter()

    def teardown_method(self):
        """Reset global limiter after each test."""
        reset_rate_limiter()

    def test_get_rate_limiter_creates_singleton(self):
        """Test that get_rate_limiter returns same instance."""
        limiter1 = get_rate_limiter()
        limiter2 = get_rate_limiter()
        assert limiter1 is limiter2

    def test_reset_rate_limiter(self):
        """Test that reset creates new instance."""
        limiter1 = get_rate_limiter()
        reset_rate_limiter()
        limiter2 = get_rate_limiter()
        assert limiter1 is not limiter2


class TestThresholdConstants:
    """Tests for threshold constant values."""

    def test_thresholds_in_order(self):
        """Test that thresholds are in correct order."""
        assert CRITICAL_HEADROOM_THRESHOLD < LOW_HEADROOM_THRESHOLD
        assert LOW_HEADROOM_THRESHOLD < HIGH_HEADROOM_THRESHOLD
        assert HIGH_HEADROOM_THRESHOLD < 1.0

    def test_thresholds_reasonable_values(self):
        """Test that thresholds have reasonable values."""
        assert 0.05 <= CRITICAL_HEADROOM_THRESHOLD <= 0.15
        assert 0.15 <= LOW_HEADROOM_THRESHOLD <= 0.30
        assert 0.60 <= HIGH_HEADROOM_THRESHOLD <= 0.80
