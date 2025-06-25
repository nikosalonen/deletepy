"""
Rate limiting configuration for Auth0 API operations.

This file contains configurable parameters for managing API rate limits
and retry behavior when interacting with Auth0's Management API.

Auth0 Management API Rate Limits:
- 2 requests per second (120 requests per minute)
- 1000 requests per hour
- 10000 requests per day

These limits are per application, so be conservative with your settings.
"""

# Rate limiting constants (seconds between API calls)
# Conservative default: 0.5 seconds between requests (2 requests per second max)
API_RATE_LIMIT = 0.5

# API timeout in seconds
API_TIMEOUT = 30

# Retry configuration for rate limiting
MAX_RETRIES = 3
BASE_RETRY_DELAY = 1.0  # Start with 1 second delay
MAX_RETRY_DELAY = 60.0  # Maximum 60 seconds delay

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


def get_estimated_processing_time(total_emails: int, batch_size: int = None) -> float:
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


def validate_rate_limit_config():
    """Validate that the rate limit configuration is safe for Auth0.

    Returns:
        bool: True if configuration is safe, False otherwise
    """
    requests_per_second = 1.0 / API_RATE_LIMIT

    if requests_per_second > 2.0:
        print(
            f"WARNING: Rate limit configured for {requests_per_second:.1f} requests/second"
        )
        print("Auth0 limit is 2 requests/second. Consider increasing API_RATE_LIMIT.")
        return False

    if requests_per_second > 1.5:
        print(
            f"INFO: Rate limit configured for {requests_per_second:.1f} requests/second"
        )
        print("This is close to Auth0's limit. Monitor for rate limit errors.")

    return True
