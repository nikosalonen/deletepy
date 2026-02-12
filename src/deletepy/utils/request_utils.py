"""Request utilities for HTTP operations."""

from ..core.config import API_RATE_LIMIT

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
