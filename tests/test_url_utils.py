"""Tests for URL encoding utilities."""

import pytest

from src.deletepy.utils.url_utils import (
    encode_email,
    encode_user_id,
    secure_url_encode,
)


class TestSecureUrlEncode:
    """Tests for secure_url_encode function."""

    def test_encode_valid_string(self):
        """Test encoding a valid string."""
        result = secure_url_encode("hello world", context="test parameter")
        assert result == "hello%20world"

    def test_encode_empty_string_raises(self):
        """Test that empty string raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            secure_url_encode("", context="test parameter")
        assert "cannot be empty" in str(exc_info.value)

    def test_encode_special_characters(self):
        """Test encoding special characters."""
        result = secure_url_encode("test@example.com", context="test parameter")
        assert result == "test%40example.com"

    def test_encode_auth0_user_id(self):
        """Test encoding Auth0 user ID with pipe character."""
        result = secure_url_encode("auth0|12345", context="user ID")
        assert result == "auth0%7C12345"

    def test_encode_google_oauth2_user_id(self):
        """Test encoding Google OAuth2 user ID."""
        result = secure_url_encode("google-oauth2|123456789", context="user ID")
        assert result == "google-oauth2%7C123456789"

    def test_encode_facebook_user_id(self):
        """Test encoding Facebook user ID."""
        result = secure_url_encode("facebook|abc123", context="user ID")
        assert result == "facebook%7Cabc123"

    def test_encode_user_id_validates_format(self):
        """Test that encoding validates user ID format."""
        # Invalid user ID (no pipe separator) should raise
        with pytest.raises(ValueError) as exc_info:
            secure_url_encode("invalid_user_id", context="user ID")
        assert "Invalid" in str(exc_info.value)

    def test_encode_user_id_validates_empty_parts(self):
        """Test that encoding validates user ID parts are not empty."""
        with pytest.raises(ValueError) as exc_info:
            secure_url_encode("auth0|", context="user ID")
        assert "Invalid" in str(exc_info.value)

    def test_encode_preserves_alphanumeric(self):
        """Test that alphanumeric characters are not encoded."""
        result = secure_url_encode("abc123", context="test parameter")
        assert result == "abc123"

    def test_encode_with_hyphens(self):
        """Test encoding strings with hyphens."""
        result = secure_url_encode("test-value", context="test parameter")
        assert result == "test-value"

    def test_encode_with_underscores(self):
        """Test encoding strings with underscores."""
        result = secure_url_encode("test_value", context="test parameter")
        assert result == "test_value"


class TestEncodeUserId:
    """Tests for encode_user_id convenience function."""

    def test_encode_auth0_user_id(self):
        """Test encoding standard Auth0 user ID."""
        result = encode_user_id("auth0|123456")
        assert result == "auth0%7C123456"

    def test_encode_social_provider_user_id(self):
        """Test encoding social provider user ID."""
        result = encode_user_id("google-oauth2|abc123")
        assert result == "google-oauth2%7Cabc123"

    def test_encode_empty_user_id_raises(self):
        """Test that empty user ID raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            encode_user_id("")
        assert "cannot be empty" in str(exc_info.value)

    def test_encode_invalid_format_raises(self):
        """Test that invalid format raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            encode_user_id("invalid_format")
        assert "Invalid" in str(exc_info.value)

    def test_encode_user_id_with_numbers(self):
        """Test encoding user ID with various number formats."""
        result = encode_user_id("email|507f1f77bcf86cd799439011")
        assert result == "email%7C507f1f77bcf86cd799439011"

    def test_encode_github_user_id(self):
        """Test encoding GitHub user ID."""
        result = encode_user_id("github|user123")
        assert result == "github%7Cuser123"


class TestEncodeEmail:
    """Tests for encode_email convenience function."""

    def test_encode_simple_email(self):
        """Test encoding simple email address."""
        result = encode_email("user@example.com")
        assert result == "user%40example.com"

    def test_encode_email_with_plus(self):
        """Test encoding email with plus sign."""
        result = encode_email("user+tag@example.com")
        assert result == "user%2Btag%40example.com"

    def test_encode_email_with_dots(self):
        """Test encoding email with dots in local part."""
        result = encode_email("first.last@example.com")
        assert result == "first.last%40example.com"

    def test_encode_empty_email_raises(self):
        """Test that empty email raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            encode_email("")
        assert "cannot be empty" in str(exc_info.value)

    def test_encode_email_subdomain(self):
        """Test encoding email with subdomain."""
        result = encode_email("user@mail.example.com")
        assert result == "user%40mail.example.com"


class TestSecurityValidation:
    """Tests for security validation in URL encoding."""

    def test_dangerous_characters_in_user_id(self):
        """Test that dangerous characters are rejected in user IDs."""
        dangerous_inputs = [
            "auth0|user<script>",
            "auth0|user>test",
            'auth0|user"test',
            "auth0|user'test",
            "auth0|user&test",
        ]
        for input_val in dangerous_inputs:
            with pytest.raises(ValueError):
                encode_user_id(input_val)

    def test_null_bytes_rejected(self):
        """Test that null bytes are rejected."""
        with pytest.raises(ValueError):
            encode_user_id("auth0|user\x00test")

    def test_newlines_rejected_in_user_id(self):
        """Test that newlines are rejected in user IDs."""
        with pytest.raises(ValueError):
            encode_user_id("auth0|user\ntest")

    def test_spaces_rejected_in_user_id(self):
        """Test that spaces are rejected in user IDs."""
        with pytest.raises(ValueError):
            encode_user_id("auth0|user test")


class TestEdgeCases:
    """Tests for edge cases."""

    def test_very_long_user_id(self):
        """Test encoding very long user ID."""
        # Auth0 allows up to 512 characters
        long_id = "auth0|" + "a" * 100
        result = encode_user_id(long_id)
        assert "%7C" in result
        assert result.startswith("auth0%7C")

    def test_unicode_in_email(self):
        """Test that URL encoding handles special chars in context of email."""
        # This tests the general encoding, not validation
        result = secure_url_encode("test@example.com", context="test email")
        assert "%40" in result

    def test_context_used_in_error_message(self):
        """Test that context appears in error messages."""
        with pytest.raises(ValueError) as exc_info:
            secure_url_encode("", context="custom context name")
        assert "custom context name" in str(exc_info.value)


if __name__ == "__main__":
    pytest.main([__file__])
