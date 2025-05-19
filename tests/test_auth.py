import pytest
from unittest.mock import patch
from auth import get_access_token, AuthConfigError

@pytest.fixture
def mock_config():
    with patch('auth.get_env_config') as mock:
        mock.return_value = {
            "client_id": "test_client_id",
            "client_secret": "test_client_secret",
            "auth0_domain": "test.auth0.com"
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
            "grant_type": "client_credentials"
        },
        timeout=5
    )

def test_get_access_token_missing_client_id(mock_config):
    mock_config.return_value = {
        "client_id": "",
        "client_secret": "test_client_secret",
        "auth0_domain": "test.auth0.com"
    }

    with pytest.raises(AuthConfigError) as exc_info:
        get_access_token("dev")
    assert "Missing Auth0 Client ID" in str(exc_info.value)

def test_get_access_token_missing_client_secret(mock_config):
    mock_config.return_value = {
        "client_id": "test_client_id",
        "client_secret": "",
        "auth0_domain": "test.auth0.com"
    }

    with pytest.raises(AuthConfigError) as exc_info:
        get_access_token("dev")
    assert "Missing Auth0 Client Secret" in str(exc_info.value)

def test_get_access_token_missing_domain(mock_config):
    mock_config.return_value = {
        "client_id": "test_client_id",
        "client_secret": "test_client_secret",
        "auth0_domain": ""
    }

    with pytest.raises(AuthConfigError) as exc_info:
        get_access_token("dev")
    assert "Missing Auth0 Domain" in str(exc_info.value)

def test_get_access_token_no_token_in_response(mock_requests, mock_response, mock_config):
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
