import pytest
from unittest.mock import patch, MagicMock
from auth import get_access_token, AuthConfigError, doctor

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
        headers={
            "User-Agent": "DeletePy/1.0 (Auth0 User Management Tool)",
            "Content-Type": "application/json"
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

def test_doctor_success():
    """Test doctor function with successful credentials."""
    with patch('auth.get_env_config') as mock_get_config, \
         patch('auth.get_access_token') as mock_get_token:

        # Mock successful configuration
        mock_get_config.return_value = {
            'client_id': 'test_client_id',
            'client_secret': 'test_secret',
            'auth0_domain': 'test.auth0.com',
            'api_url': 'https://test.api.com'
        }

        # Mock successful token retrieval
        mock_get_token.return_value = 'test_token'

        result = doctor('dev', test_api=False)

        assert result['success'] is True
        assert result['environment'] == 'dev'
        assert result['token_obtained'] is True
        assert result['api_tested'] is False
        assert 'Credentials are working correctly' in result['details']

def test_doctor_with_api_test_success():
    """Test doctor function with API test enabled and successful."""
    with patch('auth.get_env_config') as mock_get_config, \
         patch('auth.get_access_token') as mock_get_token, \
         patch('auth.requests.get') as mock_get:

        # Mock successful configuration
        mock_get_config.return_value = {
            'client_id': 'test_client_id',
            'client_secret': 'test_secret',
            'auth0_domain': 'test.auth0.com',
            'api_url': 'https://test.api.com'
        }

        # Mock successful token retrieval
        mock_get_token.return_value = 'test_token'

        # Mock successful API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        result = doctor('prod', test_api=True)

        assert result['success'] is True
        assert result['environment'] == 'prod'
        assert result['token_obtained'] is True
        assert result['api_tested'] is True
        assert result['api_status'] == 'success'
        assert 'Credentials and API access are working correctly' in result['details']

def test_doctor_with_api_test_failure():
    """Test doctor function with API test enabled but API call fails."""
    with patch('auth.get_env_config') as mock_get_config, \
         patch('auth.get_access_token') as mock_get_token, \
         patch('auth.requests.get') as mock_get:

        # Mock successful configuration
        mock_get_config.return_value = {
            'client_id': 'test_client_id',
            'client_secret': 'test_secret',
            'auth0_domain': 'test.auth0.com',
            'api_url': 'https://test.api.com'
        }

        # Mock successful token retrieval
        mock_get_token.return_value = 'test_token'

        # Mock failed API response
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_get.return_value = mock_response

        result = doctor('dev', test_api=True)

        assert result['success'] is True
        assert result['environment'] == 'dev'
        assert result['token_obtained'] is True
        assert result['api_tested'] is True
        assert result['api_status'] == 'failed_403'
        assert 'Token obtained but API access failed' in result['details']

def test_doctor_auth_config_error():
    """Test doctor function when authentication configuration fails."""
    with patch('auth.get_env_config') as mock_get_config:
        # Mock configuration error
        mock_get_config.side_effect = AuthConfigError("Missing client ID")

        result = doctor('dev', test_api=False)

        assert result['success'] is False
        assert result['environment'] == 'dev'
        assert result['token_obtained'] is False
        assert result['api_tested'] is False
        assert 'Authentication configuration is invalid' in result['details']
        assert 'Missing client ID' in result['error']
