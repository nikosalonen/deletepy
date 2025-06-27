"""Auth0-specific validation utilities."""

import re

# Auth0 user ID prefixes
AUTH0_USER_ID_PREFIXES = (
    "auth0|",
    "google-oauth2|",
    "facebook|",
    "github|",
    "twitter|",
    "linkedin|",
    "apple|",
    "microsoft|",
    "windowslive|",
    "line|",
    "samlp|",
    "oidc|",
)


def is_auth0_user_id(identifier: str) -> bool:
    """Check if a string is an Auth0 user ID.

    Args:
        identifier: String to check

    Returns:
        True if the string starts with a known Auth0 user ID prefix
    """
    return identifier.startswith(AUTH0_USER_ID_PREFIXES)


def validate_auth0_user_id(user_id: str) -> bool:
    """Validate Auth0 user ID format.

    Auth0 user IDs typically follow patterns like:
    - auth0|123456789012345678901234
    - google-oauth2|123456789012345678901
    - email|507f1f77bcf86cd799439011

    Args:
        user_id: The user ID to validate

    Returns:
        bool: True if valid Auth0 user ID format, False otherwise
    """
    if not user_id or not isinstance(user_id, str):
        return False

    # Auth0 user IDs have connection|identifier format
    # Connection can contain letters, numbers, hyphens
    # Identifier is typically alphanumeric
    pattern = r"^[a-zA-Z0-9\-]+\|[a-zA-Z0-9]+$"
    return bool(re.match(pattern, user_id))


def parse_auth0_user_id(user_id: str) -> tuple[str, str]:
    """Parse Auth0 user ID into connection and identifier parts.

    Args:
        user_id: Auth0 user ID to parse

    Returns:
        Tuple of (connection, identifier)

    Raises:
        ValueError: If user_id is not a valid Auth0 user ID format
    """
    if not validate_auth0_user_id(user_id):
        raise ValueError(f"Invalid Auth0 user ID format: {user_id}")

    connection, identifier = user_id.split("|", 1)
    return connection, identifier


def get_connection_type(user_id: str) -> str:
    """Extract connection type from Auth0 user ID.

    Args:
        user_id: Auth0 user ID

    Returns:
        Connection type (e.g., 'auth0', 'google-oauth2', 'facebook')

    Raises:
        ValueError: If user_id is not a valid Auth0 user ID format
    """
    connection, _ = parse_auth0_user_id(user_id)
    return connection


def is_social_connection(user_id: str) -> bool:
    """Check if user ID belongs to a social connection.

    Args:
        user_id: Auth0 user ID

    Returns:
        True if it's a social connection, False otherwise
    """
    try:
        connection = get_connection_type(user_id)
        social_connections = {
            "google-oauth2",
            "facebook",
            "github",
            "twitter",
            "linkedin",
            "apple",
            "microsoft",
            "windowslive",
            "line",
        }
        return connection in social_connections
    except ValueError:
        return False


def is_database_connection(user_id: str) -> bool:
    """Check if user ID belongs to a database connection.

    Args:
        user_id: Auth0 user ID

    Returns:
        True if it's a database connection, False otherwise
    """
    try:
        connection = get_connection_type(user_id)
        return connection == "auth0"
    except ValueError:
        return False
