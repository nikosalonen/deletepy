import pytest
from unittest.mock import patch, mock_open
import requests
from auth import get_access_token, AuthConfigError

@patch('requests.post')
@patch('auth.get_env_config')
def test_get_access_token_success(mock_get_env_config, mock_post):
    # Mock environment config
    mock_get_env_config.return_value = {
        "client_id": "test-client-id",
        "client_secret": "test-secret",
        "auth0_domain": "test-domain.com",
        "api_url": "https://test-api.com"
    }
    
    # Mock successful API response
    mock_post.return_value.json.return_value = {"access_token": "test_token"}
    mock_post.return_value.raise_for_status.return_value = None
    
    token = get_access_token('dev')
    assert token == 'test_token'
    
    # Verify the correct URL and payload were used
    mock_post.assert_called_once()
    call_args = mock_post.call_args
    assert call_args[0][0] == 'https://test-domain.com/oauth/token'
    assert call_args[1]['json']['client_id'] == 'test-client-id'
    assert call_args[1]['json']['client_secret'] == 'test-secret'
    assert call_args[1]['json']['audience'] == 'https://test-domain.com/api/v2/'

@patch('auth.get_env_config')
def test_get_access_token_missing_client_id(mock_get_env_config):
    mock_get_env_config.return_value = {
        "client_id": None,
        "client_secret": "test-secret",
        "auth0_domain": "test-domain.com",
        "api_url": "https://test-api.com"
    }
    
    with pytest.raises(AuthConfigError) as exc_info:
        get_access_token('dev')
    assert "Missing Auth0 Client ID" in str(exc_info.value)

@patch('auth.get_env_config')
def test_get_access_token_missing_client_secret(mock_get_env_config):
    mock_get_env_config.return_value = {
        "client_id": "test-client-id",
        "client_secret": None,
        "auth0_domain": "test-domain.com",
        "api_url": "https://test-api.com"
    }
    
    with pytest.raises(AuthConfigError) as exc_info:
        get_access_token('dev')
    assert "Missing Auth0 Client Secret" in str(exc_info.value)

@patch('auth.get_env_config')
def test_get_access_token_missing_domain(mock_get_env_config):
    mock_get_env_config.return_value = {
        "client_id": "test-client-id",
        "client_secret": "test-secret",
        "auth0_domain": None,
        "api_url": "https://test-api.com"
    }
    
    with pytest.raises(AuthConfigError) as exc_info:
        get_access_token('dev')
    assert "Missing Auth0 Domain" in str(exc_info.value)

@patch('requests.post')
@patch('auth.get_env_config')
def test_get_access_token_invalid_response(mock_get_env_config, mock_post):
    mock_get_env_config.return_value = {
        "client_id": "test-client-id",
        "client_secret": "test-secret",
        "auth0_domain": "test-domain.com",
        "api_url": "https://test-api.com"
    }
    
    # Mock response without access token
    mock_post.return_value.json.return_value = {"error": "invalid_request"}
    mock_post.return_value.raise_for_status.return_value = None
    
    with pytest.raises(AuthConfigError) as exc_info:
        get_access_token('dev')
    assert "Access token not found in Auth0 response" in str(exc_info.value)

@patch('requests.post')
@patch('auth.get_env_config')
def test_get_access_token_request_error(mock_get_env_config, mock_post):
    mock_get_env_config.return_value = {
        "client_id": "test-client-id",
        "client_secret": "test-secret",
        "auth0_domain": "test-domain.com",
        "api_url": "https://test-api.com"
    }
    
    # Mock request exception
    mock_post.side_effect = requests.exceptions.RequestException("Test error")
    
    with pytest.raises(requests.exceptions.RequestException) as exc_info:
        get_access_token('dev')
    assert "Test error" in str(exc_info.value) 