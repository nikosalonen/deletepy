import pytest
from unittest.mock import patch, mock_open
import os
from config import (
    check_env_file,
    validate_env_var,
    get_env_config,
    get_base_url
)

def test_check_env_file_exists():
    with patch('pathlib.Path.is_file', return_value=True):
        check_env_file()  # Should not raise an exception

def test_check_env_file_missing():
    with patch('pathlib.Path.is_file', return_value=False):
        with pytest.raises(FileNotFoundError) as exc_info:
            check_env_file()
        assert ".env file not found" in str(exc_info.value)

def test_validate_env_var_valid():
    value = validate_env_var("TEST_VAR", "test_value")
    assert value == "test_value"

def test_validate_env_var_none():
    with pytest.raises(ValueError) as exc_info:
        validate_env_var("TEST_VAR", None)
    assert "Required environment variable 'TEST_VAR' is missing or empty" in str(exc_info.value)

def test_validate_env_var_empty():
    with pytest.raises(ValueError) as exc_info:
        validate_env_var("TEST_VAR", "")
    assert "Required environment variable 'TEST_VAR' is missing or empty" in str(exc_info.value)

def test_validate_env_var_whitespace():
    with pytest.raises(ValueError) as exc_info:
        validate_env_var("TEST_VAR", "   ")
    assert "Required environment variable 'TEST_VAR' is missing or empty" in str(exc_info.value)

@patch('os.getenv')
def test_get_env_config_dev(mock_getenv):
    mock_getenv.side_effect = lambda x: {
        "DEV_AUTH0_CLIENT_ID": "dev-client-id",
        "DEV_AUTH0_CLIENT_SECRET": "dev-secret",
        "DEV_AUTH0_DOMAIN": "dev-domain.com",
        "DEV_URL": "https://dev-api.com"
    }.get(x)
    
    config = get_env_config("dev")
    assert config["client_id"] == "dev-client-id"
    assert config["client_secret"] == "dev-secret"
    assert config["auth0_domain"] == "dev-domain.com"
    assert config["api_url"] == "https://dev-api.com"

@patch('os.getenv')
def test_get_env_config_prod(mock_getenv):
    mock_getenv.side_effect = lambda x: {
        "AUTH0_CLIENT_ID": "prod-client-id",
        "AUTH0_CLIENT_SECRET": "prod-secret",
        "AUTH0_DOMAIN": "prod-domain.com",
        "URL": "https://prod-api.com"
    }.get(x)
    
    config = get_env_config("prod")
    assert config["client_id"] == "prod-client-id"
    assert config["client_secret"] == "prod-secret"
    assert config["auth0_domain"] == "prod-domain.com"
    assert config["api_url"] == "https://prod-api.com"

def test_get_env_config_invalid_env():
    with pytest.raises(ValueError) as exc_info:
        get_env_config("invalid")
    assert "Environment must be either 'dev' or 'prod'" in str(exc_info.value)

@patch('os.getenv')
def test_get_env_config_missing_var(mock_getenv):
    mock_getenv.return_value = None
    with pytest.raises(ValueError) as exc_info:
        get_env_config("dev")
    assert "Required environment variable" in str(exc_info.value)

@patch('config.get_env_config')
def test_get_base_url_dev(mock_get_env_config):
    mock_get_env_config.return_value = {
        "client_id": "test-client-id",
        "client_secret": "test-secret",
        "auth0_domain": "dev-domain.com",
        "api_url": "https://dev-api.com"
    }
    
    base_url = get_base_url("dev")
    assert base_url == "https://dev-domain.com"

@patch('config.get_env_config')
def test_get_base_url_prod(mock_get_env_config):
    mock_get_env_config.return_value = {
        "client_id": "test-client-id",
        "client_secret": "test-secret",
        "auth0_domain": "prod-domain.com",
        "api_url": "https://prod-api.com"
    }
    
    base_url = get_base_url("prod")
    assert base_url == "https://prod-domain.com" 