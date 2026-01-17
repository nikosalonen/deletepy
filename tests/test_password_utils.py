"""Tests for password utilities."""

import string
from unittest.mock import MagicMock, patch

import pytest

from src.deletepy.utils.password_utils import (
    generate_secure_password,
    get_user_database_connection,
)


class TestGenerateSecurePassword:
    """Tests for generate_secure_password function."""

    def test_default_length(self):
        """Test password generation with default length."""
        password = generate_secure_password()
        assert len(password) == 16

    def test_custom_length(self):
        """Test password generation with custom length."""
        password = generate_secure_password(length=20)
        assert len(password) == 20

    def test_contains_uppercase(self):
        """Test that password contains at least one uppercase letter."""
        password = generate_secure_password()
        assert any(c in string.ascii_uppercase for c in password)

    def test_contains_lowercase(self):
        """Test that password contains at least one lowercase letter."""
        password = generate_secure_password()
        assert any(c in string.ascii_lowercase for c in password)

    def test_contains_digit(self):
        """Test that password contains at least one digit."""
        password = generate_secure_password()
        assert any(c in string.digits for c in password)

    def test_contains_special_char(self):
        """Test that password contains at least one special character."""
        password = generate_secure_password()
        special_chars = "!@#$%^&*()-_=+"
        assert any(c in special_chars for c in password)

    def test_all_characters_valid(self):
        """Test that all characters in password are from allowed sets."""
        password = generate_secure_password()
        allowed_chars = (
            string.ascii_uppercase
            + string.ascii_lowercase
            + string.digits
            + "!@#$%^&*()-_=+"
        )
        assert all(c in allowed_chars for c in password)

    def test_minimum_length_enforcement(self):
        """Test that password generation enforces minimum length."""
        with pytest.raises(ValueError, match="Password length must be at least 8"):
            generate_secure_password(length=7)

    def test_randomness(self):
        """Test that generated passwords are different (not deterministic)."""
        passwords = [generate_secure_password() for _ in range(10)]
        # All passwords should be different
        assert len(set(passwords)) == 10


class TestGetUserDatabaseConnection:
    """Tests for get_user_database_connection function."""

    @pytest.fixture
    def mock_make_rate_limited_request(self):
        """Mock make_rate_limited_request function."""
        with patch(
            "src.deletepy.utils.password_utils.make_rate_limited_request"
        ) as mock:
            yield mock

    @pytest.fixture
    def mock_secure_url_encode(self):
        """Mock secure_url_encode function."""
        with patch("src.deletepy.operations.user_ops.secure_url_encode") as mock:
            mock.side_effect = lambda x, _: x  # Return input as-is
            yield mock

    def test_success_with_database_connection(
        self, mock_make_rate_limited_request, mock_secure_url_encode
    ):
        """Test successful retrieval of database connection."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "identities": [
                {"provider": "auth0", "connection": "Username-Password-Authentication"}
            ]
        }
        mock_make_rate_limited_request.return_value = mock_response

        connection = get_user_database_connection(
            "auth0|123", "test_token", "https://test.auth0.com"
        )

        assert connection == "Username-Password-Authentication"

    def test_social_only_user(
        self, mock_make_rate_limited_request, mock_secure_url_encode
    ):
        """Test user with only social identities (no database connection)."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "identities": [{"provider": "google-oauth2", "connection": "google-oauth2"}]
        }
        mock_make_rate_limited_request.return_value = mock_response

        connection = get_user_database_connection(
            "google-oauth2|123", "test_token", "https://test.auth0.com"
        )

        assert connection is None

    def test_multiple_identities_with_database(
        self, mock_make_rate_limited_request, mock_secure_url_encode
    ):
        """Test user with multiple identities including database connection."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "identities": [
                {"provider": "google-oauth2", "connection": "google-oauth2"},
                {"provider": "auth0", "connection": "Username-Password-Authentication"},
            ]
        }
        mock_make_rate_limited_request.return_value = mock_response

        connection = get_user_database_connection(
            "auth0|123", "test_token", "https://test.auth0.com"
        )

        assert connection == "Username-Password-Authentication"

    def test_no_identities(
        self, mock_make_rate_limited_request, mock_secure_url_encode
    ):
        """Test user with no identities array."""
        mock_response = MagicMock()
        mock_response.json.return_value = {}
        mock_make_rate_limited_request.return_value = mock_response

        connection = get_user_database_connection(
            "auth0|123", "test_token", "https://test.auth0.com"
        )

        assert connection is None

    def test_empty_identities(
        self, mock_make_rate_limited_request, mock_secure_url_encode
    ):
        """Test user with empty identities array."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"identities": []}
        mock_make_rate_limited_request.return_value = mock_response

        connection = get_user_database_connection(
            "auth0|123", "test_token", "https://test.auth0.com"
        )

        assert connection is None

    def test_api_request_failure(
        self, mock_make_rate_limited_request, mock_secure_url_encode
    ):
        """Test handling of API request failure."""
        mock_make_rate_limited_request.return_value = None

        connection = get_user_database_connection(
            "auth0|123", "test_token", "https://test.auth0.com"
        )

        assert connection is None

    def test_invalid_json_response(
        self, mock_make_rate_limited_request, mock_secure_url_encode
    ):
        """Test handling of invalid JSON response."""
        mock_response = MagicMock()
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_make_rate_limited_request.return_value = mock_response

        connection = get_user_database_connection(
            "auth0|123", "test_token", "https://test.auth0.com"
        )

        assert connection is None

    def test_missing_connection_field(
        self, mock_make_rate_limited_request, mock_secure_url_encode
    ):
        """Test identity without connection field."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"identities": [{"provider": "auth0"}]}
        mock_make_rate_limited_request.return_value = mock_response

        connection = get_user_database_connection(
            "auth0|123", "test_token", "https://test.auth0.com"
        )

        assert connection is None

    def test_correct_api_call(
        self, mock_make_rate_limited_request, mock_secure_url_encode
    ):
        """Test that API is called with correct parameters."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "identities": [
                {"provider": "auth0", "connection": "Username-Password-Authentication"}
            ]
        }
        mock_make_rate_limited_request.return_value = mock_response

        get_user_database_connection(
            "auth0|123", "test_token", "https://test.auth0.com"
        )

        # Verify API call was made correctly
        mock_make_rate_limited_request.assert_called_once()
        args, kwargs = mock_make_rate_limited_request.call_args
        assert args[0] == "GET"
        assert args[1] == "https://test.auth0.com/api/v2/users/auth0|123"
        assert args[2]["Authorization"] == "Bearer test_token"
        assert args[2]["Content-Type"] == "application/json"
