from unittest.mock import call, patch

import requests

from src.deletepy.operations.batch_ops import (
    check_unblocked_users,
    find_users_by_social_media_ids,
)
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


def test_check_unblocked_users(mock_requests, mock_response):
    # Mock responses for two users - one blocked, one unblocked
    mock_response.json.side_effect = [
        {"blocked": True},  # First user is blocked
        {"blocked": False},  # Second user is unblocked
    ]
    mock_requests.get.return_value = mock_response

    # Mock logging functions to capture output
    with (
        patch("builtins.print") as mock_print,
        patch("src.deletepy.utils.display_utils.show_progress"),
        patch("src.deletepy.operations.batch_ops.print_warning") as mock_warning,
        patch("src.deletepy.operations.batch_ops.print_info") as mock_info,
    ):
        # Call the function with two test users
        user_ids = ["user1", "user2"]
        check_unblocked_users(user_ids, "test_token", "http://test.com")

        # Verify that GET requests were made for both users
        assert mock_requests.get.call_count == 2

        # Get all calls made to get
        get_calls = mock_requests.get.call_args_list

        # Verify first user API call
        assert get_calls[0][0][0] == "http://test.com/api/v2/users/user1"
        assert get_calls[0][1] == {
            "headers": {
                "Authorization": "Bearer test_token",
                "Content-Type": "application/json",
                "User-Agent": "DeletePy/1.0 (Auth0 User Management Tool)",
            },
            "timeout": 30,
        }

        # Verify second user API call
        assert get_calls[1][0][0] == "http://test.com/api/v2/users/user2"
        assert get_calls[1][1] == {
            "headers": {
                "Authorization": "Bearer test_token",
                "Content-Type": "application/json",
                "User-Agent": "DeletePy/1.0 (Auth0 User Management Tool)",
            },
            "timeout": 30,
        }

        # Verify structured logging output
        mock_print.assert_any_call("\n")  # Clear progress line
        mock_warning.assert_called_once_with(
            "Found 1 unblocked users:",
            count=1,
            operation="check_unblocked",
        )
        mock_info.assert_called_once_with(
            "  user2",
            user_id="user2",
            status="unblocked"
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


def test_find_users_by_social_media_ids_single_identity_delete(
    mock_requests, mock_response
):
    # Mock response with a user that has single non-auth0 identity (should be deleted)
    mock_response.json.return_value = {
        "users": [
            {
                "user_id": "google-oauth2|123456789",
                "email": "test@example.com",
                "identities": [
                    {"user_id": "12345678901234567890", "connection": "google-oauth2"}
                ],
            }
        ],
        "total": 1
    }
    mock_requests.get.return_value = mock_response

    with (
        patch("src.deletepy.utils.display_utils.show_progress"),
        patch("src.deletepy.operations.batch_ops.delete_user") as mock_delete,
    ):
        find_users_by_social_media_ids(
            ["12345678901234567890"],
            "test_token",
            "http://test.com",
            "dev",
            auto_delete=True,
        )

        # Verify delete_user was called for single identity user
        mock_delete.assert_called_once_with(
            "google-oauth2|123456789", "test_token", "http://test.com"
        )


def test_find_users_by_social_media_ids_multiple_identities_unlink(
    mock_requests, mock_response
):
    # Mock response with a user that has multiple identities with non-auth0 main (should unlink the matching one)
    mock_response.json.return_value = {
        "users": [
            {
                "user_id": "google-oauth2|123456789",
                "email": "test@example.com",
                "identities": [
                    {"user_id": "google_main_id", "connection": "google-oauth2"},
                    {"user_id": "12345678901234567890", "connection": "facebook"},
                    {"user_id": "another_identity", "connection": "linkedin"},
                ],
            }
        ],
        "total": 1
    }
    mock_requests.get.return_value = mock_response

    with (
        patch("src.deletepy.utils.display_utils.show_progress"),
        patch("src.deletepy.operations.batch_ops.delete_user") as mock_delete,
        patch("src.deletepy.operations.batch_ops.unlink_user_identity") as mock_unlink,
        patch("src.deletepy.operations.batch_ops._get_user_identity_count") as mock_identity_count,
    ):
        mock_unlink.return_value = True
        # Patch so user is NOT orphaned after unlinking (should have 2 identities remaining)
        mock_identity_count.return_value = 2

        find_users_by_social_media_ids(
            ["12345678901234567890"],
            "test_token",
            "http://test.com",
            "dev",
            auto_delete=True,
        )

        # Verify delete_user was NOT called (user has multiple identities after unlink)
        mock_delete.assert_not_called()

        # Output verification is done via structured logging, behavior verification is more important


def test_find_users_by_social_media_ids_auth0_main_identity_protection(
    mock_requests, mock_response
):
    # Mock response with auth0 main identity user (should be protected)
    mock_response.json.return_value = {
        "users": [
            {
                "user_id": "auth0|123456789",
                "email": "test@example.com",
                "identities": [
                    {"user_id": "auth0user123", "connection": "auth0"},
                    {"user_id": "12345678901234567890", "connection": "google-oauth2"},
                ],
            }
        ],
        "total": 1
    }
    mock_requests.get.return_value = mock_response

    with (
        patch("src.deletepy.utils.display_utils.show_progress"),
        patch("src.deletepy.operations.batch_ops.delete_user") as mock_delete,
        patch("src.deletepy.operations.user_ops.unlink_user_identity") as mock_unlink,
    ):
        find_users_by_social_media_ids(
            ["12345678901234567890"],
            "test_token",
            "http://test.com",
            "dev",
            auto_delete=True,
        )

        # Verify neither delete nor unlink was called (auth0 main identity protection)
        mock_delete.assert_not_called()
        mock_unlink.assert_not_called()

        # Protection behavior is verified by ensuring no operations were called
        # Output verification is done via structured logging


def test_find_users_by_social_media_ids_not_found(mock_requests, mock_response):
    # Mock empty response - no users found
    mock_response.json.return_value = {"users": [], "total": 0}
    mock_requests.get.return_value = mock_response

    with (
        patch("src.deletepy.utils.display_utils.show_progress"),
    ):
        find_users_by_social_media_ids(
            ["nonexistent123"],
            "test_token",
            "http://test.com",
            "dev",
            auto_delete=False,
        )

        # No operations should be performed when no users are found
        # Output verification is done via structured logging


def test_find_users_by_social_media_ids_orphaned_user_deletion(
    mock_requests, mock_response
):
    # Mock response with a user that has multiple identities, one of which will be unlinked
    mock_response.json.return_value = {
        "users": [
            {
                "user_id": "google-oauth2|123456789",
                "email": "test@example.com",
                "identities": [
                    {"user_id": "12345678901234567890", "connection": "facebook"},
                    {"user_id": "another_social_id", "connection": "google-oauth2"},
                ],
            }
        ],
        "total": 1
    }
    mock_requests.get.return_value = mock_response

    with (
        patch("src.deletepy.utils.display_utils.show_progress"),
        patch("src.deletepy.operations.batch_ops.delete_user") as mock_delete,
        patch("src.deletepy.operations.batch_ops.unlink_user_identity") as mock_unlink,
        patch("src.deletepy.operations.batch_ops._get_user_identity_count") as mock_identity_count,
        patch("src.deletepy.operations.batch_ops._find_users_with_primary_social_id") as mock_find_detached,
    ):
        # Mock successful unlink
        mock_unlink.return_value = True
        # Mock that after unlinking, user has no remaining identities (orphaned)
        mock_identity_count.return_value = 0
        # Mock finding a detached social user with the same ID (simulating the new behavior)
        mock_find_detached.return_value = [{"user_id": "google-oauth2|123456789"}]

        find_users_by_social_media_ids(
            ["12345678901234567890"],
            "test_token",
            "http://test.com",
            "dev",
            auto_delete=True,
        )

        # Verify unlink_user_identity was called
        mock_unlink.assert_called_once_with(
            "google-oauth2|123456789", "facebook", "12345678901234567890", "test_token", "http://test.com"
        )

        # Verify delete_user was called twice: once for orphaned user, once for detached social user
        assert mock_delete.call_count == 2
        expected_calls = [
            call("google-oauth2|123456789", "test_token", "http://test.com"),  # Orphaned user deletion
            call("google-oauth2|123456789", "test_token", "http://test.com"),  # Detached social user deletion
        ]
        mock_delete.assert_has_calls(expected_calls)


def test_find_users_by_social_media_ids_user_not_orphaned_after_unlink(
    mock_requests, mock_response
):
    # Mock response with a user that has multiple identities, one of which will be unlinked
    mock_response.json.return_value = {
        "users": [
            {
                "user_id": "google-oauth2|123456789",
                "email": "test@example.com",
                "identities": [
                    {"user_id": "12345678901234567890", "connection": "facebook"},
                    {"user_id": "another_social_id", "connection": "google-oauth2"},
                ],
            }
        ],
        "total": 1
    }
    mock_requests.get.return_value = mock_response

    with (
        patch("src.deletepy.utils.display_utils.show_progress"),
        patch("src.deletepy.operations.batch_ops.delete_user") as mock_delete,
        patch("src.deletepy.operations.batch_ops.unlink_user_identity") as mock_unlink,
        patch("src.deletepy.operations.batch_ops._get_user_identity_count") as mock_identity_count,
        patch("src.deletepy.operations.batch_ops._find_users_with_primary_social_id") as mock_find_detached,
    ):
        # Mock successful unlink
        mock_unlink.return_value = True
        # Mock that after unlinking, user still has remaining identities (not orphaned)
        mock_identity_count.return_value = 1
        # Mock no detached social users found (so no deletion should happen)
        mock_find_detached.return_value = []

        find_users_by_social_media_ids(
            ["12345678901234567890"],
            "test_token",
            "http://test.com",
            "dev",
            auto_delete=True,
        )

        # Verify unlink_user_identity was called
        mock_unlink.assert_called_once_with(
            "google-oauth2|123456789", "facebook", "12345678901234567890", "test_token", "http://test.com"
        )

        # Verify delete_user was NOT called since user still has identities and no detached users found
        mock_delete.assert_not_called()
