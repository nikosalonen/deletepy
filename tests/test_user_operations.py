from unittest.mock import MagicMock, patch

from src.deletepy.core.auth0_client import APIResponse, Auth0Client
from src.deletepy.operations.user_ops import (
    _fetch_users_by_email,
    block_user,
    delete_user,
    get_user_details,
    get_user_email,
    get_user_id_from_email,
    revoke_user_grants,
    revoke_user_sessions,
    unlink_user_identity,
)


def _make_client() -> MagicMock:
    """Create a mock Auth0Client for testing."""
    return MagicMock(spec=Auth0Client)


def test_delete_user():
    client = _make_client()

    # Mock get_user_sessions (called by revoke_user_sessions via _fetch_user_sessions)
    # Return no sessions so the session revocation path is simple
    client.get_user_sessions.return_value = APIResponse(
        success=True, status_code=200, data={"sessions": []}
    )

    # Mock delete_user response
    client.delete_user.return_value = APIResponse(success=True, status_code=204)

    delete_user("auth0|test_user_id", client)

    # Verify get_user_sessions was called with encoded user ID
    client.get_user_sessions.assert_called_once_with("auth0%7Ctest_user_id")

    # Verify delete_user was called with encoded user ID
    client.delete_user.assert_called_once_with("auth0%7Ctest_user_id")


def test_delete_user_failure():
    client = _make_client()

    client.get_user_sessions.return_value = APIResponse(
        success=True, status_code=200, data={"sessions": []}
    )
    client.delete_user.return_value = APIResponse(
        success=False, status_code=500, error_message="Internal server error"
    )

    # Should not raise, just prints error
    delete_user("auth0|test_user_id", client)

    client.delete_user.assert_called_once_with("auth0%7Ctest_user_id")


def test_block_user():
    client = _make_client()

    # Mock session and grant revocation
    client.get_user_sessions.return_value = APIResponse(
        success=True, status_code=200, data={"sessions": []}
    )
    client.delete_user_grants.return_value = APIResponse(success=True, status_code=204)

    # Mock block_user response
    client.block_user.return_value = APIResponse(success=True, status_code=200)

    block_user("auth0|test_user_id", client)

    # Verify revoke_user_sessions was triggered (get_user_sessions called)
    client.get_user_sessions.assert_called_once_with("auth0%7Ctest_user_id")

    # Verify revoke_user_grants was triggered (delete_user_grants called)
    client.delete_user_grants.assert_called_once_with("auth0|test_user_id")

    # Verify block_user was called with encoded user ID
    client.block_user.assert_called_once_with("auth0%7Ctest_user_id")


def test_block_user_failure():
    client = _make_client()

    client.get_user_sessions.return_value = APIResponse(
        success=True, status_code=200, data={"sessions": []}
    )
    client.delete_user_grants.return_value = APIResponse(success=True, status_code=204)
    client.block_user.return_value = APIResponse(
        success=False, status_code=400, error_message="Bad request"
    )

    # Should not raise, just prints error
    block_user("auth0|test_user_id", client)

    client.block_user.assert_called_once_with("auth0%7Ctest_user_id")


def test_block_user_with_rotate_password():
    client = _make_client()

    client.get_user_sessions.return_value = APIResponse(
        success=True, status_code=200, data={"sessions": []}
    )
    client.delete_user_grants.return_value = APIResponse(success=True, status_code=204)
    client.block_user.return_value = APIResponse(success=True, status_code=200)

    with patch("src.deletepy.operations.user_ops.rotate_user_password") as mock_rotate:
        block_user("auth0|test_user_id", client, rotate_password=True)

        mock_rotate.assert_called_once_with("auth0|test_user_id", client)

    client.block_user.assert_called_once_with("auth0%7Ctest_user_id")


def test_get_user_id_from_email():
    client = _make_client()

    client.get_users_by_email.return_value = APIResponse(
        success=True,
        status_code=200,
        data=[{"user_id": "test_user_id"}],
    )

    result = get_user_id_from_email("test@example.com", client)

    assert result == ["test_user_id"]
    client.get_users_by_email.assert_called_once_with("test@example.com")


def test_get_user_id_from_email_multiple_users():
    client = _make_client()

    client.get_users_by_email.return_value = APIResponse(
        success=True,
        status_code=200,
        data=[
            {"user_id": "test_user_id_1"},
            {"user_id": "test_user_id_2"},
        ],
    )

    result = get_user_id_from_email("test@example.com", client)

    assert result == ["test_user_id_1", "test_user_id_2"]
    client.get_users_by_email.assert_called_once_with("test@example.com")


def test_get_user_id_from_email_not_found():
    client = _make_client()

    client.get_users_by_email.return_value = APIResponse(
        success=True,
        status_code=200,
        data=[],
    )

    result = get_user_id_from_email("test@example.com", client)

    assert result is None


def test_get_user_id_from_email_with_connection_filter():
    client = _make_client()

    client.get_users_by_email.return_value = APIResponse(
        success=True,
        status_code=200,
        data=[
            {
                "user_id": "auth0|user1",
                "identities": [{"connection": "Username-Password-Authentication"}],
            },
            {
                "user_id": "google-oauth2|user2",
                "identities": [{"connection": "google-oauth2"}],
            },
        ],
    )

    result = get_user_id_from_email(
        "test@example.com", client, connection="google-oauth2"
    )

    assert result == ["google-oauth2|user2"]


def test_get_user_id_from_email_api_failure():
    client = _make_client()

    client.get_users_by_email.return_value = APIResponse(
        success=False,
        status_code=500,
        error_message="Internal server error",
    )

    result = get_user_id_from_email("test@example.com", client)

    assert result is None


def test_fetch_users_by_email_empty_response():
    """Test _fetch_users_by_email handles empty response array consistently."""
    client = _make_client()

    client.get_users_by_email.return_value = APIResponse(
        success=True,
        status_code=200,
        data=[],
    )

    result = _fetch_users_by_email("test@example.com", client)

    assert result == []  # Should return empty list, not None
    client.get_users_by_email.assert_called_once_with("test@example.com")


def test_fetch_users_by_email_none_response():
    """Test _fetch_users_by_email handles None data from API."""
    client = _make_client()

    client.get_users_by_email.return_value = APIResponse(
        success=True,
        status_code=200,
        data=None,
    )

    result = _fetch_users_by_email("test@example.com", client)

    assert result == []  # Should return empty list for consistency


def test_fetch_users_by_email_request_failure():
    """Test _fetch_users_by_email handles request failure."""
    client = _make_client()

    client.get_users_by_email.return_value = APIResponse(
        success=False,
        status_code=0,
        error_message="Connection failed",
    )

    result = _fetch_users_by_email("test@example.com", client)

    assert result is None  # Should return None for request failures


def test_fetch_users_by_email_non_list_response():
    """Test _fetch_users_by_email handles non-list response."""
    client = _make_client()

    client.get_users_by_email.return_value = APIResponse(
        success=True,
        status_code=200,
        data={"error": "Invalid request"},
    )

    result = _fetch_users_by_email("test@example.com", client)

    assert result == []  # Should return empty list for non-list responses


def test_fetch_users_by_email_successful_response():
    """Test _fetch_users_by_email handles successful response with users."""
    client = _make_client()

    expected_users = [{"user_id": "test_user_1"}, {"user_id": "test_user_2"}]
    client.get_users_by_email.return_value = APIResponse(
        success=True,
        status_code=200,
        data=expected_users,
    )

    result = _fetch_users_by_email("test@example.com", client)

    assert result == expected_users
    client.get_users_by_email.assert_called_once_with("test@example.com")


def test_revoke_user_sessions():
    client = _make_client()

    # Mock fetching sessions - returns dict with sessions key
    client.get_user_sessions.return_value = APIResponse(
        success=True,
        status_code=200,
        data={"sessions": [{"id": "session1"}, {"id": "session2"}]},
    )

    # Mock deleting sessions
    client.delete_session.return_value = APIResponse(success=True, status_code=204)

    revoke_user_sessions("auth0|test_user_id", client)

    # Verify GET sessions was called with encoded user ID
    client.get_user_sessions.assert_called_once_with("auth0%7Ctest_user_id")

    # Verify DELETE was called for each session
    assert client.delete_session.call_count == 2
    client.delete_session.assert_any_call("session1")
    client.delete_session.assert_any_call("session2")


def test_revoke_user_sessions_no_sessions():
    client = _make_client()

    client.get_user_sessions.return_value = APIResponse(
        success=True,
        status_code=200,
        data={"sessions": []},
    )

    revoke_user_sessions("auth0|test_user_id", client)

    client.get_user_sessions.assert_called_once_with("auth0%7Ctest_user_id")
    client.delete_session.assert_not_called()


def test_revoke_user_sessions_fetch_failure():
    client = _make_client()

    client.get_user_sessions.return_value = APIResponse(
        success=False,
        status_code=500,
        error_message="Server error",
    )

    revoke_user_sessions("auth0|test_user_id", client)

    client.get_user_sessions.assert_called_once_with("auth0%7Ctest_user_id")
    client.delete_session.assert_not_called()


def test_revoke_user_sessions_delete_failure():
    client = _make_client()

    client.get_user_sessions.return_value = APIResponse(
        success=True,
        status_code=200,
        data={"sessions": [{"id": "session1"}]},
    )
    client.delete_session.return_value = APIResponse(
        success=False, status_code=403, error_message="Forbidden"
    )

    # Should not raise, just prints warning
    revoke_user_sessions("auth0|test_user_id", client)

    client.delete_session.assert_called_once_with("session1")


def test_revoke_user_sessions_session_without_id():
    """Test that sessions without an 'id' key are skipped."""
    client = _make_client()

    client.get_user_sessions.return_value = APIResponse(
        success=True,
        status_code=200,
        data={"sessions": [{"id": "session1"}, {"no_id": "bad_session"}]},
    )
    client.delete_session.return_value = APIResponse(success=True, status_code=204)

    revoke_user_sessions("auth0|test_user_id", client)

    # Only the valid session should be deleted
    client.delete_session.assert_called_once_with("session1")


def test_revoke_user_grants():
    client = _make_client()

    client.delete_user_grants.return_value = APIResponse(success=True, status_code=204)

    revoke_user_grants("auth0|test_user_id", client)

    client.delete_user_grants.assert_called_once_with("auth0|test_user_id")


def test_revoke_user_grants_failure():
    client = _make_client()

    client.delete_user_grants.return_value = APIResponse(
        success=False, status_code=500, error_message="Server error"
    )

    # Should not raise, just prints error
    revoke_user_grants("auth0|test_user_id", client)

    client.delete_user_grants.assert_called_once_with("auth0|test_user_id")


def test_get_user_email():
    client = _make_client()

    client.get_user.return_value = APIResponse(
        success=True,
        status_code=200,
        data={"email": "test@example.com"},
    )

    result = get_user_email("auth0|test_user_id", client)

    assert result == "test@example.com"
    client.get_user.assert_called_once_with("auth0%7Ctest_user_id")


def test_get_user_email_not_found():
    client = _make_client()

    client.get_user.return_value = APIResponse(
        success=False,
        status_code=404,
        error_message="User not found",
    )

    result = get_user_email("auth0|test_user_id", client)

    assert result is None


def test_get_user_email_no_email_field():
    client = _make_client()

    client.get_user.return_value = APIResponse(
        success=True,
        status_code=200,
        data={"user_id": "auth0|test_user_id"},
    )

    result = get_user_email("auth0|test_user_id", client)

    assert result is None


def test_get_user_details():
    client = _make_client()

    expected_data = {
        "user_id": "auth0|test_user_id",
        "identities": [{"connection": "test-connection"}],
    }
    client.get_user.return_value = APIResponse(
        success=True,
        status_code=200,
        data=expected_data,
    )

    result = get_user_details("auth0|test_user_id", client)

    assert result == expected_data
    client.get_user.assert_called_once_with("auth0%7Ctest_user_id")


def test_get_user_details_not_found():
    client = _make_client()

    client.get_user.return_value = APIResponse(
        success=False,
        status_code=404,
        error_message="User not found",
    )

    result = get_user_details("auth0|test_user_id", client)

    assert result is None


def test_get_user_details_none_data():
    client = _make_client()

    client.get_user.return_value = APIResponse(
        success=True,
        status_code=200,
        data=None,
    )

    result = get_user_details("auth0|test_user_id", client)

    assert result is None


def test_unlink_user_identity_success():
    client = _make_client()

    client.unlink_identity.return_value = APIResponse(success=True, status_code=200)

    result = unlink_user_identity("auth0|123", "google-oauth2", "google123", client)

    assert result is True
    client.unlink_identity.assert_called_once_with(
        "auth0%7C123", "google-oauth2", "google123"
    )


def test_unlink_user_identity_failure():
    client = _make_client()

    client.unlink_identity.return_value = APIResponse(
        success=False,
        status_code=400,
        error_message="Bad request",
    )

    result = unlink_user_identity("auth0|123", "google-oauth2", "google123", client)

    assert result is False
    client.unlink_identity.assert_called_once_with(
        "auth0%7C123", "google-oauth2", "google123"
    )
