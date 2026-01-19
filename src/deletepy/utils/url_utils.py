"""URL encoding utilities for Auth0 API operations."""

from urllib.parse import quote

from .validators import InputValidator


def secure_url_encode(value: str, context: str = "URL parameter") -> str:
    """Securely URL encode a value with validation.

    This function validates the input value before encoding and validates
    the encoded result to prevent injection attacks.

    Args:
        value: Value to encode
        context: Context description for error messages (used in exceptions)

    Returns:
        str: Safely encoded value

    Raises:
        ValueError: If value is empty or fails security validation

    Example:
        >>> secure_url_encode("auth0|12345", "user ID")
        'auth0%7C12345'
    """
    if not value:
        raise ValueError(f"{context} cannot be empty")

    # Validate the original value if it looks like a user ID
    if "user" in context.lower() or "id" in context.lower():
        result = InputValidator.validate_auth0_user_id_enhanced(value)
        if not result.is_valid:
            raise ValueError(f"Invalid {context}: {result.error_message}")

    # URL encode the value
    encoded = quote(value, safe="")

    # Validate the encoded result
    validation_result = InputValidator.validate_url_encoding_secure(encoded)
    if not validation_result.is_valid:
        raise ValueError(
            f"URL encoding failed security validation for {context}: {validation_result.error_message}"
        )

    return encoded


def encode_user_id(user_id: str) -> str:
    """URL encode an Auth0 user ID.

    Convenience wrapper around secure_url_encode specifically for user IDs.

    Args:
        user_id: Auth0 user ID to encode

    Returns:
        str: URL-encoded user ID

    Raises:
        ValueError: If user_id is invalid
    """
    return secure_url_encode(user_id, "user ID")


def encode_email(email: str) -> str:
    """URL encode an email address for query parameters.

    Args:
        email: Email address to encode

    Returns:
        str: URL-encoded email

    Raises:
        ValueError: If email is empty
    """
    return secure_url_encode(email, "email")
