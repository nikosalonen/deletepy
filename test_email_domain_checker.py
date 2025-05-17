import pytest
from unittest.mock import patch, mock_open
import json
from email_domain_checker import (
    extract_domain,
    load_cache,
    save_cache,
    check_domain,
    check_domains_for_emails,
    check_domains_status_for_emails
)

def test_extract_domain():
    assert extract_domain("test@example.com") == "example.com"
    assert extract_domain("test@sub.example.com") == "sub.example.com"
    assert extract_domain("example.com") == "example.com"
    assert extract_domain("") == ""

@patch('os.path.exists')
@patch('builtins.open', new_callable=mock_open, read_data='{"example.com": {"blocked": true}}')
def test_load_cache_success(mock_file, mock_exists):
    mock_exists.return_value = True
    cache = load_cache()
    assert cache == {"example.com": {"blocked": True}}
    mock_file.assert_called_once_with("domain_cache.json", "r")

@patch('os.path.exists')
def test_load_cache_file_not_exists(mock_exists):
    mock_exists.return_value = False
    cache = load_cache()
    assert cache == {}

@patch('os.path.exists')
@patch('builtins.open', new_callable=mock_open, read_data='invalid json')
def test_load_cache_invalid_json(mock_file, mock_exists):
    mock_exists.return_value = True
    cache = load_cache()
    assert cache == {}

@patch('builtins.open', new_callable=mock_open)
def test_save_cache_success(mock_file):
    cache = {"example.com": {"blocked": True}}
    save_cache(cache)
    mock_file.assert_called_once_with("domain_cache.json", "w")
    mock_file().write.assert_called_once_with(json.dumps(cache, indent=2))

@patch('requests.get')
def test_check_domain_success(mock_get):
    mock_get.return_value.json.return_value = {"blocked": True}
    mock_get.return_value.raise_for_status.return_value = None
    
    with patch('email_domain_checker.API_KEY', 'test-key'):
        result = check_domain("example.com", {})
        assert result == {"blocked": True}
        mock_get.assert_called_once_with(
            "https://www.istempmail.com/api/check/test-key/example.com",
            timeout=10
        )

@patch('requests.get')
def test_check_domain_error(mock_get):
    mock_get.side_effect = Exception("Test error")
    
    with patch('email_domain_checker.API_KEY', 'test-key'):
        result = check_domain("example.com", {})
        assert result is None

@patch('email_domain_checker.check_domain')
def test_check_domains_for_emails(mock_check_domain):
    mock_check_domain.return_value = {"blocked": True}
    
    with patch('email_domain_checker.API_KEY', 'test-key'):
        check_domains_for_emails(["test@example.com"])
        mock_check_domain.assert_called_once_with("example.com", {})

@patch('email_domain_checker.check_domain')
def test_check_domains_status_for_emails(mock_check_domain):
    mock_check_domain.return_value = {"blocked": True}
    
    with patch('email_domain_checker.API_KEY', 'test-key'):
        results = check_domains_status_for_emails(["test@example.com"])
        assert results == {"test@example.com": ["BLOCKED"]}
        mock_check_domain.assert_called_once_with("example.com", {})

def test_check_domains_status_for_emails_invalid():
    with patch('email_domain_checker.API_KEY', 'test-key'):
        results = check_domains_status_for_emails(["invalid-email"])
        assert results == {"invalid-email": ["INVALID"]}

def test_check_domains_status_for_emails_apple_relay():
    with patch('email_domain_checker.API_KEY', 'test-key'):
        results = check_domains_status_for_emails(["test@privaterelay.appleid.com"])
        assert results == {"test@privaterelay.appleid.com": ["IGNORED"]} 