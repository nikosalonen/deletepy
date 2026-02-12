"""Password utilities for secure password generation and user management."""

import secrets
import string
from typing import Any

from ..core.auth0_client import Auth0Client
from ..utils.output import print_error, print_warning


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


def get_user_database_connection(user_id: str, client: Auth0Client) -> str | None:
    """Auto-detect user's database connection from their Auth0 profile.

    Args:
        user_id: Auth0 user ID
        client: Auth0 API client

    Returns:
        Optional[str]: Database connection name if found, None otherwise
    """
    from .url_utils import secure_url_encode

    encoded_id = secure_url_encode(user_id, "user ID")
    result = client.get_user(encoded_id)

    if not result.success:
        print_error(
            f"Failed to fetch user details for {user_id}: {result.error_message}",
            user_id=user_id,
            operation="get_user_database_connection",
        )
        return None

    user_data: dict[str, Any] = result.data if isinstance(result.data, dict) else {}
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
