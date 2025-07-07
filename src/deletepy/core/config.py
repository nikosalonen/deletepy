"""Configuration utilities for Auth0 API access."""

import os
from typing import Any

import dotenv

from .exceptions import AuthConfigError

# Global constants for API configuration
API_RATE_LIMIT = 0.5  # seconds between requests
API_TIMEOUT = 30  # request timeout in seconds
MAX_RETRIES = 3  # maximum number of retries
BASE_RETRY_DELAY = 1.0  # base delay between retries in seconds
MAX_RETRY_DELAY = 60.0  # maximum delay between retries in seconds


def check_env_file() -> None:
    """Check if .env file exists and load it."""
    env_path = ".env"
    if os.path.exists(env_path):
        dotenv.load_dotenv(env_path)


def validate_env_var(name: str, value: str | None) -> str:
    """Validate that an environment variable is set and not empty.

    Args:
        name: Environment variable name
        value: Environment variable value

    Returns:
        str: The validated value

    Raises:
        AuthConfigError: If the environment variable is missing or empty
    """
    if not value or value.strip() == "":
        raise AuthConfigError(
            f"Environment variable {name} is required but not set or empty"
        )
    return value.strip()


def get_env_config(env: str = "dev") -> dict[str, Any]:
    """Get Auth0 configuration from environment variables.

    Args:
        env: Environment to get config for ('dev' or 'prod')

    Returns:
        Dict[str, Any]: Configuration dictionary

    Raises:
        AuthConfigError: If required environment variables are missing
    """
    check_env_file()

    # Determine prefix based on environment
    prefix = "DEV_" if env == "dev" else ""

    # Get required environment variables
    domain = validate_env_var(
        f"{prefix}AUTH0_DOMAIN", os.getenv(f"{prefix}AUTH0_DOMAIN")
    )
    client_id = validate_env_var(
        f"{prefix}AUTH0_CLIENT_ID", os.getenv(f"{prefix}AUTH0_CLIENT_ID")
    )
    client_secret = validate_env_var(
        f"{prefix}AUTH0_CLIENT_SECRET", os.getenv(f"{prefix}AUTH0_CLIENT_SECRET")
    )

    # Validate domain format
    if not domain.endswith(".auth0.com") and not domain.endswith(".eu.auth0.com"):
        raise AuthConfigError(
            f"Invalid Auth0 domain format: {domain}. "
            "Domain should end with .auth0.com or .eu.auth0.com"
        )

    # Validate client_id format (basic check)
    if len(client_id) < 10:
        raise AuthConfigError(f"Invalid Auth0 client ID format: {client_id}")

    return {
        "domain": domain,
        "client_id": client_id,
        "client_secret": client_secret,
        "environment": env,
        "base_url": f"https://{domain}",
    }


def get_base_url(env: str = "dev") -> str:
    """Get the Auth0 base URL for the given environment."""
    config = get_env_config(env)
    return config["base_url"]


def get_optimal_batch_size(total_emails: int) -> int:
    """Calculate optimal batch size based on total number of emails.

    Args:
        total_emails: Total number of emails to process

    Returns:
        int: Optimal batch size
    """
    if total_emails <= 100:
        return 10
    elif total_emails <= 1000:
        return 50
    else:
        return 100


def get_estimated_processing_time(total_emails: int, batch_size: int | None = None) -> float:
    """Estimate processing time based on email count and batch size.

    Args:
        total_emails: Total number of emails to process
        batch_size: Batch size for processing (calculated if None)

    Returns:
        float: Estimated processing time in seconds
    """
    if batch_size is None:
        batch_size = get_optimal_batch_size(total_emails)

    # Base time per email (including API calls, rate limiting, etc.)
    base_time_per_email = 0.7  # seconds

    # Additional overhead per batch
    batch_overhead = 2.0  # seconds

    # Calculate total batches
    total_batches = (total_emails + batch_size - 1) // batch_size

    # Calculate estimated time
    estimated_time = (total_emails * base_time_per_email) + (
        total_batches * batch_overhead
    )

    return estimated_time


def validate_rate_limit_config() -> None:
    """Validate that rate limiting configuration is safe for Auth0 API.

    Auth0 has rate limits of approximately 2 requests per second for Management API.
    This function ensures our configuration respects these limits.

    Raises:
        AuthConfigError: If rate limiting configuration is unsafe
    """
    if API_RATE_LIMIT < 0.5:
        raise AuthConfigError(
            f"API_RATE_LIMIT ({API_RATE_LIMIT}) is too aggressive. "
            "Auth0 Management API allows max 2 requests/second. "
            "Use at least 0.5 seconds between requests."
        )
