from unittest.mock import MagicMock, patch

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


def test_delete_user(mock_auth0_client):
    """Test user deletion via SDK."""
    with (
        patch(
            "src.deletepy.operations.user_ops.revoke_user_sessions"
        ) as mock_revoke_sessions,
        patch(
            "src.deletepy.operations.user_ops.get_sdk_ops_from_base_url"
        ) as mock_get_ops,
    ):
        # Mock SDK operations
        mock_user_ops = MagicMock()
        mock_user_ops.delete_user = MagicMock()
        mock_grant_ops = MagicMock()
        mock_get_ops.return_value = (mock_user_ops, mock_grant_ops)

        delete_user("auth0|test_user_id", "test_token", "http://test.com")

        # Verify revoke_user_sessions was called first
        mock_revoke_sessions.assert_called_once_with(
            "auth0|test_user_id", "test_token", "http://test.com"
        )

        # Verify SDK delete was called
        mock_user_ops.delete_user.assert_called_once_with("auth0|test_user_id")


def test_block_user():
    """Test user blocking via SDK."""
    with (
        patch(
            "src.deletepy.operations.user_ops.revoke_user_sessions"
        ) as mock_revoke_sessions,
        patch(
            "src.deletepy.operations.user_ops.revoke_user_grants"
        ) as mock_revoke_grants,
        patch(
            "src.deletepy.operations.user_ops.get_sdk_ops_from_base_url"
        ) as mock_get_ops,
    ):
        # Mock SDK operations
        mock_user_ops = MagicMock()
        mock_user_ops.block_user = MagicMock(return_value=True)
        mock_grant_ops = MagicMock()
        mock_get_ops.return_value = (mock_user_ops, mock_grant_ops)

        block_user("auth0|test_user_id", "test_token", "http://test.com")

        # Verify revoke functions were called
        mock_revoke_sessions.assert_called_once_with(
            "auth0|test_user_id", "test_token", "http://test.com"
        )
        mock_revoke_grants.assert_called_once_with(
            "auth0|test_user_id", "test_token", "http://test.com"
        )

        # Verify SDK block was called
        mock_user_ops.block_user.assert_called_once_with("auth0|test_user_id")


def test_get_user_id_from_email():
    """Test getting user ID from email via SDK."""
    with patch(
        "src.deletepy.operations.user_ops.get_sdk_ops_from_base_url"
    ) as mock_get_ops:
        mock_user_ops = MagicMock()
        mock_user_ops.search_users_by_email = MagicMock(
            return_value=[{"user_id": "test_user_id"}]
        )
        mock_grant_ops = MagicMock()
        mock_get_ops.return_value = (mock_user_ops, mock_grant_ops)

        result = get_user_id_from_email(
            "test@example.com", "test_token", "http://test.com"
        )

        assert result == ["test_user_id"]
        mock_user_ops.search_users_by_email.assert_called_once_with("test@example.com")


def test_get_user_id_from_email_multiple_users():
    """Test getting multiple user IDs from email via SDK."""
    with patch(
        "src.deletepy.operations.user_ops.get_sdk_ops_from_base_url"
    ) as mock_get_ops:
        mock_user_ops = MagicMock()
        mock_user_ops.search_users_by_email = MagicMock(
            return_value=[
                {"user_id": "test_user_id_1"},
                {"user_id": "test_user_id_2"},
            ]
        )
        mock_grant_ops = MagicMock()
        mock_get_ops.return_value = (mock_user_ops, mock_grant_ops)

        result = get_user_id_from_email(
            "test@example.com", "test_token", "http://test.com"
        )

        assert result == ["test_user_id_1", "test_user_id_2"]


def test_get_user_id_from_email_not_found():
    """Test getting user ID when not found via SDK."""
    with patch(
        "src.deletepy.operations.user_ops.get_sdk_ops_from_base_url"
    ) as mock_get_ops:
        mock_user_ops = MagicMock()
        mock_user_ops.search_users_by_email = MagicMock(return_value=[])
        mock_grant_ops = MagicMock()
        mock_get_ops.return_value = (mock_user_ops, mock_grant_ops)

        result = get_user_id_from_email(
            "test@example.com", "test_token", "http://test.com"
        )

        assert result is None


def test_fetch_users_by_email_empty_response():
    """Test _fetch_users_by_email handles empty response array consistently."""
    from src.deletepy.operations.user_ops import _fetch_users_by_email

    with patch(
        "src.deletepy.operations.user_ops.get_sdk_ops_from_base_url"
    ) as mock_get_ops:
        mock_user_ops = MagicMock()
        mock_user_ops.search_users_by_email = MagicMock(return_value=[])
        mock_grant_ops = MagicMock()
        mock_get_ops.return_value = (mock_user_ops, mock_grant_ops)

        result = _fetch_users_by_email(
            "test@example.com", "test_token", "http://test.com"
        )

        assert result == []


def test_fetch_users_by_email_none_response():
    """Test _fetch_users_by_email handles None response from API."""
    from src.deletepy.operations.user_ops import _fetch_users_by_email

    with patch(
        "src.deletepy.operations.user_ops.get_sdk_ops_from_base_url"
    ) as mock_get_ops:
        mock_user_ops = MagicMock()
        mock_user_ops.search_users_by_email = MagicMock(return_value=None)
        mock_grant_ops = MagicMock()
        mock_get_ops.return_value = (mock_user_ops, mock_grant_ops)

        result = _fetch_users_by_email(
            "test@example.com", "test_token", "http://test.com"
        )

        assert result == []


def test_fetch_users_by_email_invalid_json_response():
    """Test _fetch_users_by_email handles SDK exceptions."""
    from src.deletepy.operations.user_ops import _fetch_users_by_email

    with patch(
        "src.deletepy.operations.user_ops.get_sdk_ops_from_base_url"
    ) as mock_get_ops:
        mock_user_ops = MagicMock()
        mock_user_ops.search_users_by_email = MagicMock(
            side_effect=Exception("SDK Error")
        )
        mock_grant_ops = MagicMock()
        mock_get_ops.return_value = (mock_user_ops, mock_grant_ops)

        result = _fetch_users_by_email(
            "test@example.com", "test_token", "http://test.com"
        )

        assert result is None


def test_fetch_users_by_email_request_failure():
    """Test _fetch_users_by_email handles request failure."""
    from src.deletepy.operations.user_ops import _fetch_users_by_email

    with patch(
        "src.deletepy.operations.user_ops.get_sdk_ops_from_base_url"
    ) as mock_get_ops:
        mock_user_ops = MagicMock()
        mock_user_ops.search_users_by_email = MagicMock(
            side_effect=Exception("Connection failed")
        )
        mock_grant_ops = MagicMock()
        mock_get_ops.return_value = (mock_user_ops, mock_grant_ops)

        result = _fetch_users_by_email(
            "test@example.com", "test_token", "http://test.com"
        )

        assert result is None


def test_fetch_users_by_email_non_list_response():
    """Test _fetch_users_by_email handles non-list response."""
    from src.deletepy.operations.user_ops import _fetch_users_by_email

    with patch(
        "src.deletepy.operations.user_ops.get_sdk_ops_from_base_url"
    ) as mock_get_ops:
        mock_user_ops = MagicMock()
        # SDK returns empty list for no results
        mock_user_ops.search_users_by_email = MagicMock(return_value=[])
        mock_grant_ops = MagicMock()
        mock_get_ops.return_value = (mock_user_ops, mock_grant_ops)

        result = _fetch_users_by_email(
            "test@example.com", "test_token", "http://test.com"
        )

        assert result == []


def test_fetch_users_by_email_successful_response():
    """Test _fetch_users_by_email handles successful response with users."""
    from src.deletepy.operations.user_ops import _fetch_users_by_email

    expected_users = [{"user_id": "test_user_1"}, {"user_id": "test_user_2"}]

    with patch(
        "src.deletepy.operations.user_ops.get_sdk_ops_from_base_url"
    ) as mock_get_ops:
        mock_user_ops = MagicMock()
        mock_user_ops.search_users_by_email = MagicMock(return_value=expected_users)
        mock_grant_ops = MagicMock()
        mock_get_ops.return_value = (mock_user_ops, mock_grant_ops)

        result = _fetch_users_by_email(
            "test@example.com", "test_token", "http://test.com"
        )

        assert result == expected_users


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

    revoke_user_sessions("auth0|test_user_id", "test_token", "http://test.com")

    # Verify GET request for fetching sessions
    mock_requests.get.assert_called_once()
    mock_requests.get.assert_called_with(
        "http://test.com/api/v2/users/auth0%7Ctest_user_id/sessions",
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


def test_revoke_user_grants():
    """Test revoking user grants via SDK."""
    with patch(
        "src.deletepy.operations.user_ops.get_sdk_ops_from_base_url"
    ) as mock_get_ops:
        mock_user_ops = MagicMock()
        mock_grant_ops = MagicMock()
        mock_grant_ops.delete_grants_by_user = MagicMock(return_value=True)
        mock_get_ops.return_value = (mock_user_ops, mock_grant_ops)

        revoke_user_grants("auth0|test_user_id", "test_token", "http://test.com")

        mock_grant_ops.delete_grants_by_user.assert_called_once_with(
            "auth0|test_user_id"
        )


def test_get_user_email():
    """Test getting user email via SDK."""
    with patch(
        "src.deletepy.operations.user_ops.get_sdk_ops_from_base_url"
    ) as mock_get_ops:
        mock_user_ops = MagicMock()
        mock_user_ops.get_user = MagicMock(return_value={"email": "test@example.com"})
        mock_grant_ops = MagicMock()
        mock_get_ops.return_value = (mock_user_ops, mock_grant_ops)

        result = get_user_email("auth0|test_user_id", "test_token", "http://test.com")

        assert result == "test@example.com"
        mock_user_ops.get_user.assert_called_once_with("auth0|test_user_id")


def test_get_user_details():
    """Test getting user details via SDK."""
    with patch(
        "src.deletepy.operations.user_ops.get_sdk_ops_from_base_url"
    ) as mock_get_ops:
        mock_user_ops = MagicMock()
        mock_user_ops.get_user = MagicMock(
            return_value={
                "user_id": "auth0|test_user_id",
                "identities": [{"connection": "test-connection"}],
            }
        )
        mock_grant_ops = MagicMock()
        mock_get_ops.return_value = (mock_user_ops, mock_grant_ops)

        result = get_user_details("auth0|test_user_id", "test_token", "http://test.com")

        assert result == {
            "user_id": "auth0|test_user_id",
            "identities": [{"connection": "test-connection"}],
        }
        mock_user_ops.get_user.assert_called_once_with("auth0|test_user_id")


def test_unlink_user_identity_success():
    """Test unlinking user identity via SDK."""
    with patch(
        "src.deletepy.operations.user_ops.get_sdk_ops_from_base_url"
    ) as mock_get_ops:
        mock_user_ops = MagicMock()
        mock_user_ops.delete_user_identity = MagicMock(return_value=True)
        mock_grant_ops = MagicMock()
        mock_get_ops.return_value = (mock_user_ops, mock_grant_ops)

        result = unlink_user_identity(
            "auth0|123", "google-oauth2", "google123", "test_token", "http://test.com"
        )

        assert result is True
        mock_user_ops.delete_user_identity.assert_called_once_with(
            "auth0|123", "google-oauth2", "google123"
        )


def test_unlink_user_identity_failure():
    """Test unlinking user identity failure via SDK."""
    with patch(
        "src.deletepy.operations.user_ops.get_sdk_ops_from_base_url"
    ) as mock_get_ops:
        mock_user_ops = MagicMock()
        mock_user_ops.delete_user_identity = MagicMock(return_value=False)
        mock_grant_ops = MagicMock()
        mock_get_ops.return_value = (mock_user_ops, mock_grant_ops)

        result = unlink_user_identity(
            "auth0|123", "google-oauth2", "google123", "test_token", "http://test.com"
        )

        assert result is False
