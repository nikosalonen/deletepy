"""Request utilities for HTTP operations with rate limiting."""

import time
from typing import Any, cast

import requests

from ..core.config import API_RATE_LIMIT, API_TIMEOUT
from .rate_limiter import RateLimitExceededError, get_rate_limiter


def make_rate_limited_request(
    method: str, url: str, headers: dict[str, str], **kwargs: Any
) -> requests.Response | None:
    """Make an HTTP request with adaptive rate limiting.

    Uses the adaptive rate limiter which:
    - Respects Auth0's rate limit headers
    - Backs off when limits are low
    - Uses exponential backoff on 429 responses

    Args:
        method: HTTP method (GET, POST, etc.)
        url: Request URL
        headers: Request headers
        **kwargs: Additional request parameters

    Returns:
        Optional[requests.Response]: Response object or None if failed
    """
    limiter = get_rate_limiter()

    try:
        response = requests.request(
            method, url, headers=headers, timeout=API_TIMEOUT, **kwargs
        )

        # Handle rate limiting (429)
        if response.status_code == 429:
            try:
                backoff_time = limiter.handle_429()
                print(
                    f"Rate limit hit. Backing off for {backoff_time:.1f}s "
                    f"(attempt {limiter.state.consecutive_429s})"
                )
                time.sleep(backoff_time)
                # Retry once after backoff
                response = requests.request(
                    method, url, headers=headers, timeout=API_TIMEOUT, **kwargs
                )
                if response.status_code == 429:
                    # Still rate limited after backoff
                    backoff_time = limiter.handle_429()
                    print(
                        f"Still rate limited. Backing off for {backoff_time:.1f}s "
                        f"(attempt {limiter.state.consecutive_429s})"
                    )
                    return None
            except RateLimitExceededError as e:
                print(f"CRITICAL: {e}")
                raise

        # Success - record it and apply adaptive rate limiting
        limiter.record_success()
        limiter.wait(dict(response.headers))

        # Log if rate limits are getting low
        headroom = limiter.state.headroom_ratio
        if headroom is not None and headroom < 0.20:
            print(f"WARNING: {limiter.get_status_summary()}")

        # Handle other errors
        if response.status_code >= 400:
            response.raise_for_status()

        return response

    except RateLimitExceededError:
        # Re-raise rate limit errors to abort operation
        raise
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
        return None


def make_simple_request(
    method: str, url: str, headers: dict[str, str], **kwargs: Any
) -> requests.Response | None:
    """Make a simple HTTP request without rate limiting.

    Args:
        method: HTTP method (GET, POST, etc.)
        url: Request URL
        headers: Request headers
        **kwargs: Additional request parameters

    Returns:
        Optional[requests.Response]: Response object or None if failed
    """
    try:
        response = requests.request(
            method, url, headers=headers, timeout=API_TIMEOUT, **kwargs
        )
        response.raise_for_status()
        return response
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
        return None


def validate_response(response: requests.Response, expected_status: int = 200) -> bool:
    """Validate HTTP response.

    Args:
        response: HTTP response to validate
        expected_status: Expected status code (default: 200)

    Returns:
        bool: True if response is valid, False otherwise
    """
    if response.status_code != expected_status:
        print(
            f"Unexpected status code: {response.status_code} (expected {expected_status})"
        )
        return False

    try:
        response.json()  # Test if response is valid JSON
        return True
    except ValueError:
        print("Response is not valid JSON")
        return False


def get_json_response(response: requests.Response) -> dict[str, Any] | None:
    """Safely extract JSON from response.

    Args:
        response: HTTP response

    Returns:
        Optional[Dict[str, Any]]: JSON data or None if invalid
    """
    try:
        json_data = response.json()
        return cast(dict[str, Any], json_data)
    except ValueError as e:
        print(f"Error parsing JSON response: {e}")
        return None


# Batch processing configuration
DEFAULT_BATCH_SIZE = 50
MAX_BATCH_SIZE = 100
MIN_BATCH_SIZE = 10

# Batch size thresholds for automatic adjustment
LARGE_DATASET_THRESHOLD = 1000  # Use smaller batches for datasets > 1000
MEDIUM_DATASET_THRESHOLD = 500  # Use medium batches for datasets > 500


def get_optimal_batch_size(total_emails: int) -> int:
    """Calculate optimal batch size based on dataset size.

    Args:
        total_emails: Total number of emails to process

    Returns:
        int: Optimal batch size
    """
    if total_emails > LARGE_DATASET_THRESHOLD:
        return 25
    if total_emails > MEDIUM_DATASET_THRESHOLD:
        return 50
    return 100


def get_estimated_processing_time(
    total_emails: int, batch_size: int | None = None
) -> float:
    """Calculate estimated processing time in minutes.

    Args:
        total_emails: Total number of emails to process
        batch_size: Batch size (optional, will be calculated if not provided)

    Returns:
        float: Estimated processing time in minutes
    """
    if batch_size is None:
        batch_size = get_optimal_batch_size(total_emails)

    # Each email requires:
    # 1. One API call to get_user_id_from_email
    # 2. One API call to get_user_details per user found
    # For multiple users, we need additional API calls
    # Conservative estimate: assume 1.5 users per email on average
    api_calls_per_email = 1 + 1.5  # email lookup + user details
    total_api_calls = total_emails * api_calls_per_email
    total_time_seconds = total_api_calls * API_RATE_LIMIT

    return total_time_seconds / 60.0
