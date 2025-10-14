"""Tests for request utilities including rate limiting functions."""

from deletepy.utils.request_utils import (
    get_estimated_processing_time,
    get_optimal_batch_size,
)


class TestRateLimitingFunctions:
    """Test rate limiting utility functions."""

    def test_get_optimal_batch_size_small_dataset(self):
        """Test optimal batch size for small datasets (≤500 items)."""
        # Small datasets should use larger batch sizes for efficiency
        assert get_optimal_batch_size(100) == 100
        assert get_optimal_batch_size(250) == 100
        assert get_optimal_batch_size(500) == 100

    def test_get_optimal_batch_size_medium_dataset(self):
        """Test optimal batch size for medium datasets (501-1000 items)."""
        # Medium datasets should use moderate batch sizes
        assert get_optimal_batch_size(501) == 50
        assert get_optimal_batch_size(750) == 50
        assert get_optimal_batch_size(1000) == 50

    def test_get_optimal_batch_size_large_dataset(self):
        """Test optimal batch size for large datasets (>1000 items)."""
        # Large datasets should use smaller batch sizes to avoid memory issues
        assert get_optimal_batch_size(1001) == 25
        assert get_optimal_batch_size(5000) == 25
        assert get_optimal_batch_size(10000) == 25

    def test_get_optimal_batch_size_edge_cases(self):
        """Test optimal batch size for edge cases."""
        # Test boundary conditions
        assert get_optimal_batch_size(0) == 100  # Empty dataset
        assert get_optimal_batch_size(1) == 100  # Single item

    def test_get_estimated_processing_time_with_batch_size(self):
        """Test estimated processing time when batch size is provided."""
        # Test with explicit batch size
        total_emails = 100
        batch_size = 50

        # Expected calculation:
        # api_calls_per_email = 1 + 1.5 = 2.5
        # total_api_calls = 100 * 2.5 = 250
        # total_time_seconds = 250 * 0.5 (API_RATE_LIMIT) = 125
        # total_time_minutes = 125 / 60.0 ≈ 2.083

        estimated_time = get_estimated_processing_time(total_emails, batch_size)
        expected_time = (100 * 2.5 * 0.5) / 60.0  # ≈ 2.083 minutes

        assert abs(estimated_time - expected_time) < 0.001

    def test_get_estimated_processing_time_without_batch_size(self):
        """Test estimated processing time when batch size is calculated automatically."""
        total_emails = 100

        # Should use get_optimal_batch_size(100) = 100
        estimated_time = get_estimated_processing_time(total_emails)

        # Same calculation as above since batch size doesn't affect the time calculation
        expected_time = (100 * 2.5 * 0.5) / 60.0  # ≈ 2.083 minutes

        assert abs(estimated_time - expected_time) < 0.001

    def test_get_estimated_processing_time_large_dataset(self):
        """Test estimated processing time for large datasets."""
        total_emails = 2000

        estimated_time = get_estimated_processing_time(total_emails)

        # Expected calculation:
        # api_calls_per_email = 2.5
        # total_api_calls = 2000 * 2.5 = 5000
        # total_time_seconds = 5000 * 0.5 = 2500
        # total_time_minutes = 2500 / 60.0 ≈ 41.67

        expected_time = (2000 * 2.5 * 0.5) / 60.0

        assert abs(estimated_time - expected_time) < 0.001

    def test_get_estimated_processing_time_zero_emails(self):
        """Test estimated processing time for zero emails."""
        estimated_time = get_estimated_processing_time(0)
        assert estimated_time == 0.0

    def test_get_estimated_processing_time_with_zero_batch_size(self):
        """Test estimated processing time with zero batch size."""
        # When batch_size is 0, it should fall back to calculated batch size
        total_emails = 100
        estimated_time = get_estimated_processing_time(total_emails, 0)

        # Should be same as without batch size since 0 is falsy
        expected_time = get_estimated_processing_time(total_emails)
        assert estimated_time == expected_time

    def test_rate_limiting_consistency(self):
        """Test that rate limiting calculations are consistent."""
        # Test that the same inputs always produce the same outputs
        total_emails = 500

        batch_size_1 = get_optimal_batch_size(total_emails)
        batch_size_2 = get_optimal_batch_size(total_emails)
        assert batch_size_1 == batch_size_2

        time_1 = get_estimated_processing_time(total_emails)
        time_2 = get_estimated_processing_time(total_emails)
        assert time_1 == time_2

    def test_batch_size_thresholds(self):
        """Test that batch size thresholds work correctly."""
        # Test the exact threshold boundaries
        assert get_optimal_batch_size(500) == 100  # At medium threshold
        assert get_optimal_batch_size(501) == 50  # Just above medium threshold
        assert get_optimal_batch_size(1000) == 50  # At large threshold
        assert get_optimal_batch_size(1001) == 25  # Just above large threshold

    def test_processing_time_scales_linearly(self):
        """Test that processing time scales linearly with email count."""
        # Double the emails should roughly double the time
        emails_1 = 100
        emails_2 = 200

        time_1 = get_estimated_processing_time(emails_1)
        time_2 = get_estimated_processing_time(emails_2)

        # Should be approximately double (within small tolerance for rounding)
        ratio = time_2 / time_1
        assert abs(ratio - 2.0) < 0.01

    def test_api_rate_limit_integration(self):
        """Test that functions properly use the API_RATE_LIMIT constant."""
        from deletepy.utils.request_utils import API_RATE_LIMIT

        # Verify that the rate limit is being used in calculations
        total_emails = 100
        estimated_time = get_estimated_processing_time(total_emails)

        # Manual calculation to verify API_RATE_LIMIT is used
        api_calls = total_emails * 2.5  # 1 + 1.5 users per email
        expected_seconds = api_calls * API_RATE_LIMIT
        expected_minutes = expected_seconds / 60.0

        assert abs(estimated_time - expected_minutes) < 0.001
