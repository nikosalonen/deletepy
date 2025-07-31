from unittest.mock import patch

import requests

from src.deletepy.operations.user_ops import (
    block_user,
    delete_user,
    get_user_details,
    get_user_email,
    get_user_id_from_email,
    revoke_user_grants,
    revoke_user_sessions,
    unlink_user_identity,
)


def test_delete_user(mock_requests, mock_response):
    mock_requests.delete.return_value = mock_response

    with patch(
        "src.deletepy.operations.user_ops.revoke_user_sessions"
    ) as mock_revoke_sessions:
        delete_user("test_user_id", "test_token", "http://test.com")

        # Verify revoke_user_sessions was called first with correct parameters
        mock_revoke_sessions.assert_called_once_with(
            "test_user_id", "test_token", "http://test.com"
        )

        # Verify delete request was made with correct parameters
        mock_requests.delete.assert_called_once()
        mock_requests.delete.assert_called_with(
            "http://test.com/api/v2/users/test_user_id",
            headers={
                "Authorization": "Bearer test_token",
                "Content-Type": "application/json",
                "User-Agent": "DeletePy/1.0 (Auth0 User Management Tool)",
            },
            timeout=30,
        )


def test_block_user(mock_requests, mock_response):
    mock_requests.patch.return_value = mock_response

    with (
        patch(
            "src.deletepy.operations.user_ops.revoke_user_sessions"
        ) as mock_revoke_sessions,
        patch(
            "src.deletepy.operations.user_ops.revoke_user_grants"
        ) as mock_revoke_grants,
    ):
        block_user("test_user_id", "test_token", "http://test.com")

        # Verify revoke_user_sessions was called first with correct parameters
        mock_revoke_sessions.assert_called_once_with(
            "test_user_id", "test_token", "http://test.com"
        )

        # Verify revoke_user_grants was called second with correct parameters
        mock_revoke_grants.assert_called_once_with(
            "test_user_id", "test_token", "http://test.com"
        )

        # Verify patch request was made last with correct parameters
        mock_requests.patch.assert_called_once()
        mock_requests.patch.assert_called_with(
            "http://test.com/api/v2/users/test_user_id",
            headers={
                "Authorization": "Bearer test_token",
                "Content-Type": "application/json",
                "User-Agent": "DeletePy/1.0 (Auth0 User Management Tool)",
            },
            json={"blocked": True},
            timeout=30,
        )


def test_get_user_id_from_email(mock_requests, mock_response):
    mock_response.json.return_value = [{"user_id": "test_user_id"}]
    mock_requests.request.return_value = mock_response

    result = get_user_id_from_email("test@example.com", "test_token", "http://test.com")

    assert result == ["test_user_id"]
    mock_requests.request.assert_called_once()
    mock_requests.request.assert_called_with(
        "GET",
        "http://test.com/api/v2/users-by-email",
        headers={
            "Authorization": "Bearer test_token",
            "Content-Type": "application/json",
            "User-Agent": "DeletePy/1.0 (Auth0 User Management Tool)",
        },
        params={"email": "test@example.com"},
        timeout=30,
    )


def test_get_user_id_from_email_multiple_users(mock_requests, mock_response):
    mock_response.json.return_value = [
        {"user_id": "test_user_id_1"},
        {"user_id": "test_user_id_2"},
    ]
    mock_requests.request.return_value = mock_response

    result = get_user_id_from_email("test@example.com", "test_token", "http://test.com")

    assert result == ["test_user_id_1", "test_user_id_2"]
    mock_requests.request.assert_called_once()


def test_get_user_id_from_email_not_found(mock_requests, mock_response):
    mock_response.json.return_value = []
    mock_requests.request.return_value = mock_response

    result = get_user_id_from_email("test@example.com", "test_token", "http://test.com")

    assert result is None


def test_fetch_users_by_email_empty_response(mock_requests, mock_response):
    """Test _fetch_users_by_email handles empty response array consistently."""
    from src.deletepy.operations.user_ops import _fetch_users_by_email
    
    mock_response.json.return_value = []
    mock_requests.request.return_value = mock_response

    result = _fetch_users_by_email("test@example.com", "test_token", "http://test.com")

    assert result == []  # Should return empty list, not None
    mock_requests.request.assert_called_once()


def test_fetch_users_by_email_none_response(mock_requests, mock_response):
    """Test _fetch_users_by_email handles None response from API."""
    from src.deletepy.operations.user_ops import _fetch_users_by_email
    
    mock_response.json.return_value = None
    mock_requests.request.return_value = mock_response

    result = _fetch_users_by_email("test@example.com", "test_token", "http://test.com")

    assert result == []  # Should return empty list for consistency


def test_fetch_users_by_email_invalid_json_response(mock_requests, mock_response):
    """Test _fetch_users_by_email handles invalid JSON response."""
    from src.deletepy.operations.user_ops import _fetch_users_by_email
    
    mock_response.json.side_effect = ValueError("Invalid JSON")
    mock_requests.request.return_value = mock_response

    result = _fetch_users_by_email("test@example.com", "test_token", "http://test.com")

    assert result is None  # Should return None for JSON parse errors


def test_fetch_users_by_email_request_failure(mock_requests):
    """Test _fetch_users_by_email handles request failure."""
    from src.deletepy.operations.user_ops import _fetch_users_by_email
    
    # Simulate request failure by raising an exception
    mock_requests.request.side_effect = requests.exceptions.RequestException("Connection failed")

    result = _fetch_users_by_email("test@example.com", "test_token", "http://test.com")

    assert result is None  # Should return None for request failures


def test_fetch_users_by_email_non_list_response(mock_requests, mock_response):
    """Test _fetch_users_by_email handles non-list response."""
    from src.deletepy.operations.user_ops import _fetch_users_by_email
    
    mock_response.json.return_value = {"error": "Invalid request"}
    mock_requests.request.return_value = mock_response

    result = _fetch_users_by_email("test@example.com", "test_token", "http://test.com")

    assert result == []  # Should return empty list for non-list responses


def test_fetch_users_by_email_successful_response(mock_requests, mock_response):
    """Test _fetch_users_by_email handles successful response with users."""
    from src.deletepy.operations.user_ops import _fetch_users_by_email
    
    expected_users = [{"user_id": "test_user_1"}, {"user_id": "test_user_2"}]
    mock_response.json.return_value = expected_users
    mock_requests.request.return_value = mock_response

    result = _fetch_users_by_email("test@example.com", "test_token", "http://test.com")

    assert result == expected_users
    mock_requests.request.assert_called_once()


def test_revoke_user_sessions(mock_requests, mock_response):
    # Mock the get response for fetching sessions
    get_response = mock_response
    get_response.json.return_value = {
        "sessions": [{"id": "session1"}, {"id": "session2"}]
    }
    get_response.raise_for_status.return_value = None

    # Mock the delete responses
    delete_response = mock_response
    delete_response.raise_for_status.return_value = None

    mock_requests.get.return_value = get_response
    mock_requests.delete.return_value = delete_response

    revoke_user_sessions("test_user_id", "test_token", "http://test.com")

    # Verify GET request for fetching sessions
    mock_requests.get.assert_called_once()
    mock_requests.get.assert_called_with(
        "http://test.com/api/v2/users/test_user_id/sessions",
        headers={
            "Authorization": "Bearer test_token",
            "Content-Type": "application/json",
            "User-Agent": "DeletePy/1.0 (Auth0 User Management Tool)",
        },
        timeout=30,
    )

    # Verify DELETE requests for revoking sessions
    assert mock_requests.delete.call_count == 2

    # Get all calls made to delete
    delete_calls = mock_requests.delete.call_args_list

    # Verify first session deletion
    assert delete_calls[0][0][0] == "http://test.com/api/v2/sessions/session1"
    assert delete_calls[0][1] == {
        "headers": {
            "Authorization": "Bearer test_token",
            "Content-Type": "application/json",
            "User-Agent": "DeletePy/1.0 (Auth0 User Management Tool)",
        },
        "timeout": 30,
    }

    # Verify second session deletion
    assert delete_calls[1][0][0] == "http://test.com/api/v2/sessions/session2"
    assert delete_calls[1][1] == {
        "headers": {
            "Authorization": "Bearer test_token",
            "Content-Type": "application/json",
            "User-Agent": "DeletePy/1.0 (Auth0 User Management Tool)",
        },
        "timeout": 30,
    }


def test_revoke_user_grants(mock_requests, mock_response):
    mock_requests.delete.return_value = mock_response

    revoke_user_grants("test_user_id", "test_token", "http://test.com")

    mock_requests.delete.assert_called_once()
    mock_requests.delete.assert_called_with(
        "http://test.com/api/v2/grants?user_id=test_user_id",
        headers={
            "Authorization": "Bearer test_token",
            "Content-Type": "application/json",
            "User-Agent": "DeletePy/1.0 (Auth0 User Management Tool)",
        },
        timeout=30,
    )


def test_get_user_email(mock_requests, mock_response):
    mock_response.json.return_value = {"email": "test@example.com"}
    mock_requests.get.return_value = mock_response

    result = get_user_email("test_user_id", "test_token", "http://test.com")

    assert result == "test@example.com"
    mock_requests.get.assert_called_once()
    mock_requests.get.assert_called_with(
        "http://test.com/api/v2/users/test_user_id",
        headers={
            "Authorization": "Bearer test_token",
            "Content-Type": "application/json",
            "User-Agent": "DeletePy/1.0 (Auth0 User Management Tool)",
        },
        timeout=30,
    )


def test_get_user_details(mock_requests, mock_response):
    mock_response.json.return_value = {
        "user_id": "test_user_id",
        "identities": [{"connection": "test-connection"}],
    }
    mock_requests.request.return_value = mock_response

    result = get_user_details("test_user_id", "test_token", "http://test.com")

    assert result == {
        "user_id": "test_user_id",
        "identities": [{"connection": "test-connection"}],
    }
    mock_requests.request.assert_called_once()
    mock_requests.request.assert_called_with(
        "GET",
        "http://test.com/api/v2/users/test_user_id",
        headers={
            "Authorization": "Bearer test_token",
            "Content-Type": "application/json",
            "User-Agent": "DeletePy/1.0 (Auth0 User Management Tool)",
        },
        timeout=30,
    )


def test_unlink_user_identity_success(mock_requests, mock_response):
    mock_response.status_code = 200
    mock_requests.delete.return_value = mock_response

    result = unlink_user_identity(
        "auth0|123", "google-oauth2", "google123", "test_token", "http://test.com"
    )

    assert result is True
    mock_requests.delete.assert_called_once()
    mock_requests.delete.assert_called_with(
        "http://test.com/api/v2/users/auth0%7C123/identities/google-oauth2/google123",
        headers={
            "Authorization": "Bearer test_token",
            "Content-Type": "application/json",
            "User-Agent": "DeletePy/1.0 (Auth0 User Management Tool)",
        },
        timeout=30,
    )


def test_unlink_user_identity_failure(mock_requests, mock_response):
    mock_response.status_code = 400
    mock_requests.delete.side_effect = requests.exceptions.RequestException(
        "400 Client Error"
    )

    result = unlink_user_identity(
        "auth0|123", "google-oauth2", "google123", "test_token", "http://test.com"
    )

    assert result is False
