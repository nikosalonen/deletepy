"""Password utilities for secure password generation and user management."""

import secrets
import string
from typing import Any

from ..utils.legacy_print import print_error, print_warning
from ..utils.request_utils import make_rate_limited_request


def generate_secure_password(length: int = 16) -> str:
    """Generate a cryptographically secure random password.

    Args:
        length: Length of password to generate (default: 16)

    Returns:
        str: Randomly generated password with mixed character types

    The password will contain:
    - At least one uppercase letter (A-Z)
    - At least one lowercase letter (a-z)
    - At least one digit (0-9)
    - At least one special character (!@#$%^&*()-_=+)
    - Remaining characters randomly selected from all sets
    """
    if length < 8:
        raise ValueError("Password length must be at least 8 characters")

    # Define character sets
    uppercase = string.ascii_uppercase
    lowercase = string.ascii_lowercase
    digits = string.digits
    special = "!@#$%^&*()-_=+"

    # Ensure at least one character from each set
    password_chars = [
        secrets.choice(uppercase),
        secrets.choice(lowercase),
        secrets.choice(digits),
        secrets.choice(special),
    ]

    # Fill remaining length with random characters from all sets
    all_chars = uppercase + lowercase + digits + special
    password_chars.extend(secrets.choice(all_chars) for _ in range(length - 4))

    # Shuffle to avoid predictable patterns
    secrets.SystemRandom().shuffle(password_chars)

    return "".join(password_chars)


def get_user_database_connection(
    user_id: str, token: str, base_url: str
) -> str | None:
    """Auto-detect user's database connection from their Auth0 profile.

    Args:
        user_id: Auth0 user ID
        token: Auth0 access token
        base_url: Auth0 API base URL

    Returns:
        Optional[str]: Database connection name if found, None otherwise
    """
    from ..operations.user_ops import secure_url_encode

    url = f"{base_url}/api/v2/users/{secure_url_encode(user_id, 'user ID')}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": "DeletePy/1.0 (Auth0 User Management Tool)",
    }

    response = make_rate_limited_request("GET", url, headers)
    if response is None:
        print_error(
            f"Failed to fetch user details for {user_id}",
            user_id=user_id,
            operation="get_user_database_connection",
        )
        return None

    try:
        user_data: dict[str, Any] = response.json()
        identities = user_data.get("identities", [])

        # Look for auth0 (database) connection
        for identity in identities:
            if identity.get("provider") == "auth0":
                connection = identity.get("connection")
                if connection:
                    return str(connection)

        # No database connection found
        print_warning(
            f"User {user_id} has no database connection (social-only user)",
            user_id=user_id,
            operation="get_user_database_connection",
        )
        return None

    except (ValueError, KeyError) as e:
        print_error(
            f"Error parsing user details for {user_id}: {e}",
            user_id=user_id,
            error=str(e),
            operation="get_user_database_connection",
        )
        return None
