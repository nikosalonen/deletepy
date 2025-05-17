import pytest
import os
import json
from unittest.mock import patch, MagicMock
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
    assert extract_domain("invalid-email") == "invalid-email"
    assert extract_domain("") == ""

def test_load_cache(tmp_path):
    # Test loading non-existent cache
    with patch('email_domain_checker.CACHE_FILE', str(tmp_path / "nonexistent.json")):
        cache = load_cache()
        assert cache == {}

    # Test loading valid cache
    test_cache = {"example.com": {"blocked": True}}
    cache_file = tmp_path / "domain_cache.json"
    with open(cache_file, "w") as f:
        json.dump(test_cache, f)

    with patch('email_domain_checker.CACHE_FILE', str(cache_file)):
        cache = load_cache()
        assert cache == test_cache

def test_save_cache(tmp_path):
    test_cache = {"example.com": {"blocked": True}}
    cache_file = tmp_path / "domain_cache.json"

    with patch('email_domain_checker.CACHE_FILE', str(cache_file)):
        save_cache(test_cache)
        assert os.path.exists(cache_file)
        with open(cache_file) as f:
            saved_cache = json.load(f)
        assert saved_cache == test_cache

@patch('email_domain_checker.requests.get')
def test_check_domain(mock_get, tmp_path):
    # Mock successful API response
    mock_response = MagicMock()
    mock_response.json.return_value = {"blocked": True}
    mock_get.return_value = mock_response

    # Test with API key
    with patch('email_domain_checker.API_KEY', 'test_key'):
        result = check_domain("example.com", {})
        assert result == {"blocked": True}
        mock_get.assert_called_once()

    # Test with cached result
    cache = {"example.com": {"blocked": False}}
    result = check_domain("example.com", cache)
    assert result == {"blocked": False}
    assert mock_get.call_count == 1  # Should not make another API call

@patch('email_domain_checker.check_domain')
def test_check_domains_for_emails(mock_check_domain):
    # Reset the mock for each test
    mock_check_domain.reset_mock()
    mock_check_domain.return_value = {"blocked": True}

    with patch('email_domain_checker.API_KEY', 'test_key'):
        with patch('email_domain_checker.load_cache') as mock_load_cache:
            mock_load_cache.return_value = {}  # Start with empty cache
            emails = ["test@example.com", "test@privaterelay.appleid.com"]
            check_domains_for_emails(emails)
            mock_check_domain.assert_called_once_with("example.com", {})

@patch('email_domain_checker.check_domain')
def test_check_domains_status_for_emails(mock_check_domain):
    mock_check_domain.return_value = {"blocked": True}

    with patch('email_domain_checker.API_KEY', 'test_key'):
        emails = ["test@example.com", "test@privaterelay.appleid.com"]
        results = check_domains_status_for_emails(emails)
        assert "test@example.com" in results
        assert "test@privaterelay.appleid.com" in results
        assert results["test@privaterelay.appleid.com"] == ["IGNORED"]
