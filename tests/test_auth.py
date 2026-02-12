from unittest.mock import MagicMock, patch

import pytest

from src.deletepy.core.auth import AuthConfigError, doctor, get_access_token


@pytest.fixture
def mock_config():
    with patch("src.deletepy.core.auth.get_env_config") as mock:
        mock.return_value = {
            "client_id": "test_client_id",
            "client_secret": "test_client_secret",
            "domain": "test.auth0.com",
        }
        yield mock


def test_get_access_token_success(mock_requests, mock_response, mock_config):
    mock_response.json.return_value = {"access_token": "test_token"}
    mock_requests.post.return_value = mock_response

    token = get_access_token("dev")

    assert token == "test_token"
    mock_requests.post.assert_called_once()
    mock_requests.post.assert_called_with(
        "https://test.auth0.com/oauth/token",
        json={
            "client_id": "test_client_id",
            "client_secret": "test_client_secret",
            "audience": "https://test.auth0.com/api/v2/",
            "grant_type": "client_credentials",
            "scope": "delete:users update:users delete:sessions delete:grants read:users",
        },
        headers={
            "User-Agent": "DeletePy/1.0 (Auth0 User Management Tool)",
            "Content-Type": "application/json",
        },
        timeout=30,
    )


def test_get_access_token_missing_client_id(mock_config):
    mock_config.return_value = {
        "client_id": "",
        "client_secret": "test_client_secret",
        "domain": "test.auth0.com",
    }

    with pytest.raises(AuthConfigError) as exc_info:
        get_access_token("dev")
    assert "Missing Auth0 Client ID" in str(exc_info.value)


def test_get_access_token_missing_client_secret(mock_config):
    mock_config.return_value = {
        "client_id": "test_client_id",
        "client_secret": "",
        "domain": "test.auth0.com",
    }

    with pytest.raises(AuthConfigError) as exc_info:
        get_access_token("dev")
    assert "Missing Auth0 Client Secret" in str(exc_info.value)


def test_get_access_token_missing_domain(mock_config):
    mock_config.return_value = {
        "client_id": "test_client_id",
        "client_secret": "test_client_secret",
        "domain": "",
    }

    with pytest.raises(AuthConfigError) as exc_info:
        get_access_token("dev")
    assert "Missing Auth0 Domain" in str(exc_info.value)


def test_get_access_token_no_token_in_response(
    mock_requests, mock_response, mock_config
):
    mock_response.json.return_value = {"error": "invalid_client"}
    mock_requests.post.return_value = mock_response

    with pytest.raises(AuthConfigError) as exc_info:
        get_access_token("dev")
    assert "Access token not found in Auth0 response" in str(exc_info.value)


def test_get_access_token_invalid_json(mock_requests, mock_response, mock_config):
    mock_response.json.side_effect = ValueError("Invalid JSON")
    mock_requests.post.return_value = mock_response

    with pytest.raises(AuthConfigError) as exc_info:
        get_access_token("dev")
    assert "Invalid JSON response from Auth0" in str(exc_info.value)


def test_doctor_success():
    """Test doctor function with successful credentials."""
    with (
        patch("src.deletepy.core.config.get_env_config") as mock_get_config,
        patch("src.deletepy.core.auth.get_access_token") as mock_get_token,
    ):
        # Mock successful configuration
        mock_get_config.return_value = {
            "client_id": "test_client_id",
            "client_secret": "test_secret",
            "domain": "test.auth0.com",
            "base_url": "https://test.auth0.com",
        }

        # Mock successful token retrieval
        mock_get_token.return_value = "test_token"

        result = doctor("dev", test_api=False)

        assert result["success"] is True
        assert result["environment"] == "dev"
        assert result["token_obtained"] is True
        assert result["api_tested"] is False
        assert "Credentials are working correctly" in result["details"]


def test_doctor_with_api_test_success():
    """Test doctor function with API test enabled and successful."""
    with (
        patch("src.deletepy.core.config.get_env_config") as mock_get_config,
        patch("src.deletepy.core.auth.get_access_token") as mock_get_token,
        patch("src.deletepy.core.auth.create_client_from_token") as mock_create_client,
    ):
        # Mock successful configuration
        mock_get_config.return_value = {
            "client_id": "test_client_id",
            "client_secret": "test_secret",
            "domain": "test.auth0.com",
            "base_url": "https://test.auth0.com",
        }

        # Mock successful token retrieval
        mock_get_token.return_value = "test_token"

        # Mock successful API response via Auth0Client
        mock_api_response = MagicMock()
        mock_api_response.success = True
        mock_api_response.status_code = 200

        mock_client = MagicMock()
        mock_client.get.return_value = mock_api_response
        mock_create_client.return_value = mock_client

        result = doctor("prod", test_api=True)

        assert result["success"] is True
        assert result["environment"] == "prod"
        assert result["token_obtained"] is True
        assert result["api_tested"] is True
        assert result["api_status"] == "success"
        assert "Credentials and API access are working correctly" in result["details"]


def test_doctor_with_api_test_failure():
    """Test doctor function with API test enabled but API call fails."""
    with (
        patch("src.deletepy.core.config.get_env_config") as mock_get_config,
        patch("src.deletepy.core.auth.get_access_token") as mock_get_token,
        patch("src.deletepy.core.auth.create_client_from_token") as mock_create_client,
    ):
        # Mock successful configuration
        mock_get_config.return_value = {
            "client_id": "test_client_id",
            "client_secret": "test_secret",
            "domain": "test.auth0.com",
            "base_url": "https://test.auth0.com",
        }

        # Mock successful token retrieval
        mock_get_token.return_value = "test_token"

        # Mock failed API response via Auth0Client
        mock_api_response = MagicMock()
        mock_api_response.success = False
        mock_api_response.status_code = 403

        mock_client = MagicMock()
        mock_client.get.return_value = mock_api_response
        mock_create_client.return_value = mock_client

        result = doctor("dev", test_api=True)

        assert result["success"] is True
        assert result["environment"] == "dev"
        assert result["token_obtained"] is True
        assert result["api_tested"] is True
        assert result["api_status"] == "failed_403"
        assert "Token obtained but API access failed" in result["details"]


def test_doctor_auth_config_error():
    """Test doctor function when authentication configuration fails."""
    with patch("src.deletepy.core.auth.get_env_config") as mock_get_config:
        # Mock configuration error
        mock_get_config.side_effect = AuthConfigError("Missing client ID")

        result = doctor("dev", test_api=False)

        assert result["success"] is False
        assert result["environment"] == "dev"
        assert result["token_obtained"] is False
        assert result["api_tested"] is False
        assert "Authentication configuration is invalid" in result["details"]
        assert "Missing client ID" in result["error"]
