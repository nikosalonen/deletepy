"""Request utilities for HTTP operations."""

from typing import Any, cast

import requests

from ..core.config import API_RATE_LIMIT
from .logging_utils import get_logger

logger = get_logger(__name__)


def validate_response(response: requests.Response, expected_status: int = 200) -> bool:
    """Validate HTTP response.

    Args:
        response: HTTP response to validate
        expected_status: Expected status code (default: 200)

    Returns:
        bool: True if response is valid, False otherwise
    """
    if response.status_code != expected_status:
        logger.warning(
            "Unexpected status code: %d (expected %d)",
            response.status_code,
            expected_status,
            extra={
                "status_code": response.status_code,
                "expected_status": expected_status,
                "operation": "validate_response",
            },
        )
        return False

    try:
        response.json()  # Test if response is valid JSON
        return True
    except ValueError:
        logger.warning(
            "Response is not valid JSON",
            extra={"operation": "validate_response", "error": "invalid_json"},
        )
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
        logger.error(
            "Error parsing JSON response: %s",
            str(e),
            extra={"operation": "parse_json", "error": str(e)},
        )
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
