"""Request utilities for HTTP operations with rate limiting and retry logic."""

import time
from contextlib import suppress
from typing import Any

import requests

from ..core.config import (
    API_RATE_LIMIT,
    API_TIMEOUT,
    BASE_RETRY_DELAY,
    MAX_RETRIES,
    MAX_RETRY_DELAY,
)


def handle_rate_limit_response(response: requests.Response, attempt: int) -> bool:
    """Handle rate limit responses with exponential backoff.

    Args:
        response: The HTTP response that triggered rate limiting
        attempt: Current attempt number (1-based)

    Returns:
        bool: True if should retry, False if max retries exceeded
    """
    if response.status_code == 429:  # Too Many Requests
        if attempt >= MAX_RETRIES:
            print(
                f"Rate limit exceeded after {MAX_RETRIES} attempts. Stopping."
            )
            return False

        # Calculate delay with exponential backoff
        delay = min(BASE_RETRY_DELAY * (2 ** (attempt - 1)), MAX_RETRY_DELAY)

        # Try to get retry-after header
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            with suppress(ValueError):
                delay = max(delay, int(retry_after))

        print(
            f"Rate limit hit. Waiting {delay} seconds before retry {attempt}/{MAX_RETRIES}..."
        )
        time.sleep(delay)
        return True

    return False


def make_rate_limited_request(
    method: str, url: str, headers: dict[str, str], **kwargs
) -> requests.Response | None:
    """Make an HTTP request with rate limiting and retry logic.

    Args:
        method: HTTP method (GET, POST, etc.)
        url: Request URL
        headers: Request headers
        **kwargs: Additional request parameters

    Returns:
        Optional[requests.Response]: Response object or None if failed after retries
    """
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.request(
                method, url, headers=headers, timeout=API_TIMEOUT, **kwargs
            )

            # Handle rate limiting
            if response.status_code == 429:
                if handle_rate_limit_response(response, attempt):
                    continue
                return None

            # Handle other errors
            if response.status_code >= 400:
                response.raise_for_status()

            # Success - apply rate limiting
            time.sleep(API_RATE_LIMIT)
            return response

        except requests.exceptions.RequestException as e:
            if attempt >= MAX_RETRIES:
                print(f"Request failed after {MAX_RETRIES} attempts: {e}")
                return None
            delay = min(BASE_RETRY_DELAY * (2 ** (attempt - 1)), MAX_RETRY_DELAY)
            print(
                f"Request failed, retrying in {delay} seconds... ({attempt}/{MAX_RETRIES})"
            )
            time.sleep(delay)

    return None


def make_simple_request(
    method: str, url: str, headers: dict[str, str], **kwargs
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
        print(f"Unexpected status code: {response.status_code} (expected {expected_status})")
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
        return response.json()
    except ValueError as e:
        print(f"Error parsing JSON response: {e}")
        return None
