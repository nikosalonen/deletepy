from unittest.mock import MagicMock, patch

import pytest

from src.deletepy.core.auth import AuthConfigError, doctor, get_access_token


@pytest.fixture
def mock_config():
    with patch("deletepy.core.config.get_env_config") as mock:
        mock.return_value = {
            "client_id": "test_client_id",
            "client_secret": "test_client_secret",
            "domain": "test.auth0.com",
            "base_url": "https://test.auth0.com",
        }
        yield mock


def test_get_access_token_success(mock_config, mock_get_token):
    """Test successful token acquisition via SDK."""
    with patch(
        "deletepy.core.auth0_client.GetToken", return_value=mock_get_token
    ) as mock_get_token_class:
        token = get_access_token("dev")

        assert token == "test_token"
        mock_get_token.client_credentials.assert_called_once()
        # Verify timeout is passed to GetToken constructor
        mock_get_token_class.assert_called_once()
        call_kwargs = mock_get_token_class.call_args.kwargs
        assert "timeout" in call_kwargs
        assert call_kwargs["timeout"] == 5


def test_get_access_token_missing_client_id(mock_config):
    """Test error when client_id is missing."""
    mock_config.return_value = {
        "client_id": "",
        "client_secret": "test_client_secret",
        "domain": "test.auth0.com",
        "base_url": "https://test.auth0.com",
    }

    mock_get_token = MagicMock()
    mock_get_token.client_credentials.side_effect = Exception("invalid_client")

    with patch("deletepy.core.auth0_client.GetToken", return_value=mock_get_token):
        with pytest.raises(AuthConfigError):
            get_access_token("dev")


def test_get_access_token_missing_client_secret(mock_config):
    """Test error when client_secret is missing."""
    mock_config.return_value = {
        "client_id": "test_client_id",
        "client_secret": "",
        "domain": "test.auth0.com",
        "base_url": "https://test.auth0.com",
    }

    mock_get_token = MagicMock()
    mock_get_token.client_credentials.side_effect = Exception("invalid_client")

    with patch("deletepy.core.auth0_client.GetToken", return_value=mock_get_token):
        with pytest.raises(AuthConfigError):
            get_access_token("dev")


def test_get_access_token_missing_domain(mock_config):
    """Test error when domain is missing."""
    mock_config.return_value = {
        "client_id": "test_client_id",
        "client_secret": "test_client_secret",
        "domain": "",
        "base_url": "https://test.auth0.com",
    }

    mock_get_token = MagicMock()
    mock_get_token.client_credentials.side_effect = Exception("invalid_domain")

    with patch("deletepy.core.auth0_client.GetToken", return_value=mock_get_token):
        with pytest.raises(AuthConfigError):
            get_access_token("dev")


def test_get_access_token_no_token_in_response(mock_config):
    """Test error when token is not in response."""
    mock_get_token = MagicMock()
    mock_get_token.client_credentials.return_value = {"error": "invalid_client"}

    with patch("deletepy.core.auth0_client.GetToken", return_value=mock_get_token):
        with pytest.raises(AuthConfigError) as exc_info:
            get_access_token("dev")
        assert "Access token not found" in str(exc_info.value)


def test_get_access_token_sdk_exception(mock_config):
    """Test handling of SDK exceptions."""
    mock_get_token = MagicMock()
    mock_get_token.client_credentials.side_effect = Exception("SDK Error")

    with patch("deletepy.core.auth0_client.GetToken", return_value=mock_get_token):
        with pytest.raises(AuthConfigError) as exc_info:
            get_access_token("dev")
        assert "Failed to obtain Auth0 management token" in str(exc_info.value)


def test_doctor_success():
    """Test doctor function with successful credentials."""
    with (
        patch("deletepy.core.config.get_env_config") as mock_get_config,
        patch("deletepy.core.auth.get_access_token") as mock_get_token,
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


def test_doctor_with_api_test_success(mock_auth0_client):
    """Test doctor function with API test enabled and successful."""
    with (
        patch("deletepy.core.config.get_env_config") as mock_get_config,
        patch("deletepy.core.auth.get_access_token") as mock_get_token,
        patch("deletepy.core.auth.Auth0ClientManager") as mock_manager_class,
    ):
        # Mock successful configuration
        config_return = {
            "client_id": "test_client_id",
            "client_secret": "test_secret",
            "domain": "test.auth0.com",
            "base_url": "https://test.auth0.com",
        }
        mock_get_config.return_value = config_return

        # Mock successful token retrieval
        mock_get_token.return_value = "test_token"

        # Mock Auth0ClientManager to return our mock client
        mock_manager = MagicMock()
        mock_manager.get_client.return_value = mock_auth0_client
        mock_manager_class.return_value = mock_manager

        # Mock successful API response
        mock_auth0_client.users.list.return_value = {"users": [], "total": 0}

        result = doctor("prod", test_api=True)

        assert result["success"] is True
        assert result["environment"] == "prod"
        assert result["token_obtained"] is True
        assert result["api_tested"] is True
        assert result["api_status"] == "success"
        assert "Credentials and API access are working correctly" in result["details"]


@pytest.mark.skip(
    reason="Test hits real Auth0 API despite mocking - needs test infrastructure fix"
)
def test_doctor_with_api_test_failure(mock_auth0_client):
    """Test doctor function with API test enabled but API call fails."""
    with (
        patch("deletepy.core.config.get_env_config") as mock_get_config,
        patch("deletepy.core.auth.get_access_token") as mock_get_token,
        patch("deletepy.core.auth.Auth0ClientManager") as mock_manager_class,
    ):
        # Mock successful configuration
        config_return = {
            "client_id": "test_client_id",
            "client_secret": "test_secret",
            "domain": "test.auth0.com",
            "base_url": "https://test.auth0.com",
        }
        mock_get_config.return_value = config_return

        # Mock successful token retrieval
        mock_get_token.return_value = "test_token"

        # Mock Auth0ClientManager to return our mock client
        mock_manager = MagicMock()
        mock_manager.get_client.return_value = mock_auth0_client
        mock_manager_class.return_value = mock_manager

        # Mock failed API response
        mock_auth0_client.users.list.side_effect = Exception("API Error")

        result = doctor("dev", test_api=True)

        assert result["success"] is True
        assert result["environment"] == "dev"
        assert result["token_obtained"] is True
        assert result["api_tested"] is True
        assert result["api_status"] == "failed"
        assert "Token obtained but API access failed" in result["details"]


@pytest.mark.skip(
    reason="Test hits real Auth0 API despite mocking - needs test infrastructure fix"
)
def test_doctor_auth_config_error():
    """Test doctor function when authentication configuration fails."""
    with patch("deletepy.core.config.get_env_config") as mock_get_config:
        # Mock configuration error
        mock_get_config.side_effect = AuthConfigError("Missing client ID")

        result = doctor("dev", test_api=False)

        assert result["success"] is False
        assert result["environment"] == "dev"
        assert result["token_obtained"] is False
        assert result["api_tested"] is False
        assert "Authentication configuration is invalid" in result["details"]
        assert "Missing client ID" in result["error"]
