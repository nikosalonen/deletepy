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
    def mock_client(self):
        """Create a mock Auth0Client."""
        return MagicMock()

    @pytest.fixture
    def mock_secure_url_encode(self):
        """Mock secure_url_encode function."""
        with patch("src.deletepy.utils.url_utils.secure_url_encode") as mock:
            mock.side_effect = lambda x, _: x  # Return input as-is
            yield mock

    def _make_api_response(
        self, success, status_code=200, data=None, error_message=None
    ):
        """Helper to create a mock APIResponse."""
        response = MagicMock()
        response.success = success
        response.status_code = status_code
        response.data = data
        response.error_message = error_message
        return response

    def test_success_with_database_connection(
        self, mock_client, mock_secure_url_encode
    ):
        """Test successful retrieval of database connection."""
        mock_client.get_user.return_value = self._make_api_response(
            success=True,
            data={
                "identities": [
                    {
                        "provider": "auth0",
                        "connection": "Username-Password-Authentication",
                    }
                ]
            },
        )

        connection = get_user_database_connection("auth0|123", mock_client)

        assert connection == "Username-Password-Authentication"

    def test_social_only_user(self, mock_client, mock_secure_url_encode):
        """Test user with only social identities (no database connection)."""
        mock_client.get_user.return_value = self._make_api_response(
            success=True,
            data={
                "identities": [
                    {"provider": "google-oauth2", "connection": "google-oauth2"}
                ]
            },
        )

        connection = get_user_database_connection("google-oauth2|123", mock_client)

        assert connection is None

    def test_multiple_identities_with_database(
        self, mock_client, mock_secure_url_encode
    ):
        """Test user with multiple identities including database connection."""
        mock_client.get_user.return_value = self._make_api_response(
            success=True,
            data={
                "identities": [
                    {"provider": "google-oauth2", "connection": "google-oauth2"},
                    {
                        "provider": "auth0",
                        "connection": "Username-Password-Authentication",
                    },
                ]
            },
        )

        connection = get_user_database_connection("auth0|123", mock_client)

        assert connection == "Username-Password-Authentication"

    def test_no_identities(self, mock_client, mock_secure_url_encode):
        """Test user with no identities array."""
        mock_client.get_user.return_value = self._make_api_response(
            success=True,
            data={},
        )

        connection = get_user_database_connection("auth0|123", mock_client)

        assert connection is None

    def test_empty_identities(self, mock_client, mock_secure_url_encode):
        """Test user with empty identities array."""
        mock_client.get_user.return_value = self._make_api_response(
            success=True,
            data={"identities": []},
        )

        connection = get_user_database_connection("auth0|123", mock_client)

        assert connection is None

    def test_api_request_failure(self, mock_client, mock_secure_url_encode):
        """Test handling of API request failure."""
        mock_client.get_user.return_value = self._make_api_response(
            success=False,
            status_code=500,
            error_message="Internal Server Error",
        )

        connection = get_user_database_connection("auth0|123", mock_client)

        assert connection is None

    def test_api_request_failure_not_found(self, mock_client, mock_secure_url_encode):
        """Test handling of 404 API response."""
        mock_client.get_user.return_value = self._make_api_response(
            success=False,
            status_code=404,
            error_message="User not found",
        )

        connection = get_user_database_connection("auth0|123", mock_client)

        assert connection is None

    def test_missing_connection_field(self, mock_client, mock_secure_url_encode):
        """Test identity without connection field."""
        mock_client.get_user.return_value = self._make_api_response(
            success=True,
            data={"identities": [{"provider": "auth0"}]},
        )

        connection = get_user_database_connection("auth0|123", mock_client)

        assert connection is None

    def test_correct_api_call(self, mock_client, mock_secure_url_encode):
        """Test that client.get_user is called with the encoded user ID."""
        mock_client.get_user.return_value = self._make_api_response(
            success=True,
            data={
                "identities": [
                    {
                        "provider": "auth0",
                        "connection": "Username-Password-Authentication",
                    }
                ]
            },
        )

        get_user_database_connection("auth0|123", mock_client)

        # secure_url_encode returns input as-is due to mock side_effect
        mock_client.get_user.assert_called_once_with("auth0|123")

    def test_secure_url_encode_is_called(self, mock_client, mock_secure_url_encode):
        """Test that secure_url_encode is called on the user ID."""
        mock_client.get_user.return_value = self._make_api_response(
            success=True,
            data={"identities": []},
        )

        get_user_database_connection("auth0|123", mock_client)

        mock_secure_url_encode.assert_called_once_with("auth0|123", "user ID")
