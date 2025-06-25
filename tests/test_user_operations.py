from unittest.mock import patch
from user_operations import (
    delete_user,
    block_user,
    get_user_id_from_email,
    revoke_user_sessions,
    revoke_user_grants,
    check_unblocked_users,
    get_user_email,
    get_user_details,
    find_users_by_social_media_ids,
    unlink_user_identity
)
from utils import YELLOW, CYAN, RESET

def test_delete_user(mock_requests, mock_response):
    mock_requests.delete.return_value = mock_response

    with patch('user_operations.revoke_user_sessions') as mock_revoke_sessions:
        delete_user("test_user_id", "test_token", "http://test.com")

        # Verify revoke_user_sessions was called first with correct parameters
        mock_revoke_sessions.assert_called_once_with(
            "test_user_id",
            "test_token",
            "http://test.com"
        )

        # Verify delete request was made with correct parameters
        mock_requests.delete.assert_called_once()
        mock_requests.delete.assert_called_with(
            "http://test.com/api/v2/users/test_user_id",
            headers={
                "Authorization": "Bearer test_token",
                "Content-Type": "application/json",
                "User-Agent": "DeletePy/1.0 (Auth0 User Management Tool)"
            },
            timeout=30
        )

def test_block_user(mock_requests, mock_response):
    mock_requests.patch.return_value = mock_response

    with patch('user_operations.revoke_user_sessions') as mock_revoke_sessions, \
         patch('user_operations.revoke_user_grants') as mock_revoke_grants:
        block_user("test_user_id", "test_token", "http://test.com")

        # Verify revoke_user_sessions was called first with correct parameters
        mock_revoke_sessions.assert_called_once_with(
            "test_user_id",
            "test_token",
            "http://test.com"
        )

        # Verify revoke_user_grants was called second with correct parameters
        mock_revoke_grants.assert_called_once_with(
            "test_user_id",
            "test_token",
            "http://test.com"
        )

        # Verify patch request was made last with correct parameters
        mock_requests.patch.assert_called_once()
        mock_requests.patch.assert_called_with(
            "http://test.com/api/v2/users/test_user_id",
            headers={
                "Authorization": "Bearer test_token",
                "Content-Type": "application/json",
                "User-Agent": "DeletePy/1.0 (Auth0 User Management Tool)"
            },
            json={"blocked": True},
            timeout=30
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
            "User-Agent": "DeletePy/1.0 (Auth0 User Management Tool)"
        },
        params={"email": "test@example.com"},
        timeout=30
    )

def test_get_user_id_from_email_multiple_users(mock_requests, mock_response):
    mock_response.json.return_value = [
        {"user_id": "test_user_id_1"},
        {"user_id": "test_user_id_2"}
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
    mock_response.json.return_value = {"sessions": [{"id": "session1"}, {"id": "session2"}]}
    mock_requests.get.return_value = mock_response
    mock_requests.delete.return_value = mock_response

    revoke_user_sessions("test_user_id", "test_token", "http://test.com")

    # Verify GET request for fetching sessions
    mock_requests.get.assert_called_once()
    mock_requests.get.assert_called_with(
        "http://test.com/api/v2/users/test_user_id/sessions",
        headers={
            "Authorization": "Bearer test_token",
            "Content-Type": "application/json",
            "User-Agent": "DeletePy/1.0 (Auth0 User Management Tool)"
        },
        timeout=30
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
            "User-Agent": "DeletePy/1.0 (Auth0 User Management Tool)"
        },
        "timeout": 30
    }

    # Verify second session deletion
    assert delete_calls[1][0][0] == "http://test.com/api/v2/sessions/session2"
    assert delete_calls[1][1] == {
        "headers": {
            "Authorization": "Bearer test_token",
            "Content-Type": "application/json",
            "User-Agent": "DeletePy/1.0 (Auth0 User Management Tool)"
        },
        "timeout": 30
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
            "User-Agent": "DeletePy/1.0 (Auth0 User Management Tool)"
        },
        timeout=30
    )

def test_check_unblocked_users(mock_requests, mock_response):
    # Mock responses for two users - one blocked, one unblocked
    mock_response.json.side_effect = [
        {"blocked": True},  # First user is blocked
        {"blocked": False}  # Second user is unblocked
    ]
    mock_requests.get.return_value = mock_response

    # Mock print function to capture output
    with patch('builtins.print') as mock_print, \
         patch('user_operations.show_progress'):
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
                "User-Agent": "DeletePy/1.0 (Auth0 User Management Tool)"
            },
            "timeout": 30
        }

        # Verify second user API call
        assert get_calls[1][0][0] == "http://test.com/api/v2/users/user2"
        assert get_calls[1][1] == {
            "headers": {
                "Authorization": "Bearer test_token",
                "Content-Type": "application/json",
                "User-Agent": "DeletePy/1.0 (Auth0 User Management Tool)"
            },
            "timeout": 30
        }

        # Verify print output
        mock_print.assert_any_call("\n")  # Clear progress line
        mock_print.assert_any_call(f"{YELLOW}Found 1 unblocked users:{RESET}")  # Summary line
        mock_print.assert_any_call(f"{CYAN}user2{RESET}")  # Unblocked user ID

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
            "User-Agent": "DeletePy/1.0 (Auth0 User Management Tool)"
        },
        timeout=30
    )

def test_get_user_details(mock_requests, mock_response):
    mock_response.json.return_value = {
        "user_id": "test_user_id",
        "identities": [{"connection": "test-connection"}]
    }
    mock_requests.request.return_value = mock_response

    result = get_user_details("test_user_id", "test_token", "http://test.com")

    assert result == {
        "user_id": "test_user_id",
        "identities": [{"connection": "test-connection"}]
    }
    mock_requests.request.assert_called_once()
    mock_requests.request.assert_called_with(
        "GET",
        "http://test.com/api/v2/users/test_user_id",
        headers={
            "Authorization": "Bearer test_token",
            "Content-Type": "application/json",
            "User-Agent": "DeletePy/1.0 (Auth0 User Management Tool)"
        },
        timeout=30
    )

def test_unlink_user_identity_success(mock_requests, mock_response):
    mock_response.status_code = 200
    mock_requests.request.return_value = mock_response

    result = unlink_user_identity("auth0|123", "google-oauth2", "google123", "test_token", "http://test.com")

    assert result is True
    mock_requests.request.assert_called_once()
    mock_requests.request.assert_called_with(
        "DELETE",
        "http://test.com/api/v2/users/auth0%7C123/identities/google-oauth2/google123",
        headers={
            "Authorization": "Bearer test_token",
            "Content-Type": "application/json",
            "User-Agent": "DeletePy/1.0 (Auth0 User Management Tool)"
        },
        timeout=30
    )

def test_unlink_user_identity_failure(mock_requests, mock_response):
    mock_response.status_code = 400
    mock_requests.request.return_value = mock_response

    result = unlink_user_identity("auth0|123", "google-oauth2", "google123", "test_token", "http://test.com")

    assert result is False

def test_find_users_by_social_media_ids_single_identity_delete(mock_requests, mock_response):
    # Mock response with a user that has single non-auth0 identity (should be deleted)
    mock_response.json.return_value = [{
        "user_id": "google-oauth2|123456789",
        "email": "test@example.com",
        "identities": [{
            "user_id": "12345678901234567890",
            "connection": "google-oauth2"
        }]
    }]
    mock_requests.request.return_value = mock_response

    with patch('builtins.print') as mock_print, \
         patch('user_operations.show_progress'), \
         patch('user_operations.delete_user') as mock_delete:
        find_users_by_social_media_ids(["12345678901234567890"], "test_token", "http://test.com", "dev", auto_delete=True)

        # Verify delete_user was called for single identity user
        mock_delete.assert_called_once_with("google-oauth2|123456789", "test_token", "http://test.com")
        
        # Verify output shows deletion
        mock_print.assert_any_call("Users deleted: 1")
        mock_print.assert_any_call("Failed deletions: 0")

def test_find_users_by_social_media_ids_multiple_identities_unlink(mock_requests, mock_response):
    # Mock response with a user that has multiple identities with non-auth0 main (should unlink the matching one)
    mock_response.json.return_value = [{
        "user_id": "google-oauth2|123456789", 
        "email": "test@example.com",
        "identities": [
            {
                "user_id": "google_main_id",
                "connection": "google-oauth2"
            },
            {
                "user_id": "12345678901234567890",
                "connection": "facebook"
            }
        ]
    }]
    mock_requests.request.return_value = mock_response

    with patch('builtins.print') as mock_print, \
         patch('user_operations.show_progress'), \
         patch('user_operations.delete_user') as mock_delete, \
         patch('user_operations.unlink_user_identity') as mock_unlink:
        mock_unlink.return_value = True
        
        find_users_by_social_media_ids(["12345678901234567890"], "test_token", "http://test.com", "dev", auto_delete=True)

        # Verify delete_user was NOT called
        mock_delete.assert_not_called()
        
        # Verify unlink_user_identity was called for the facebook identity
        mock_unlink.assert_called_once_with("google-oauth2|123456789", "facebook", "12345678901234567890", "test_token", "http://test.com")
        
        # Verify output shows unlinking
        mock_print.assert_any_call("Identities unlinked: 1")
        mock_print.assert_any_call("Failed unlinks: 0")

def test_find_users_by_social_media_ids_auth0_main_identity_protection(mock_requests, mock_response):
    # Mock response with auth0 main identity user (should be protected)
    mock_response.json.return_value = [{
        "user_id": "auth0|123456789",
        "email": "test@example.com",
        "identities": [
            {
                "user_id": "auth0user123",
                "connection": "auth0"
            },
            {
                "user_id": "12345678901234567890", 
                "connection": "google-oauth2"
            }
        ]
    }]
    mock_requests.request.return_value = mock_response

    with patch('builtins.print') as mock_print, \
         patch('user_operations.show_progress'), \
         patch('user_operations.delete_user') as mock_delete, \
         patch('user_operations.unlink_user_identity') as mock_unlink:
        
        find_users_by_social_media_ids(["12345678901234567890"], "test_token", "http://test.com", "dev", auto_delete=True)

        # Verify neither delete nor unlink was called (auth0 main identity protection)
        mock_delete.assert_not_called()
        mock_unlink.assert_not_called()
        
        # Verify output shows auth0 protection
        expected_calls = [call for call in mock_print.call_args_list if "Users with auth0 main identity (protected)" in str(call)]
        assert len(expected_calls) > 0

def test_find_users_by_social_media_ids_not_found(mock_requests, mock_response):
    # Mock empty response - no users found
    mock_response.json.return_value = []
    mock_requests.request.return_value = mock_response

    with patch('builtins.print') as mock_print, \
         patch('user_operations.show_progress'):
        find_users_by_social_media_ids(["nonexistent123"], "test_token", "http://test.com", "dev", auto_delete=False)

        # Verify output shows no users found
        mock_print.assert_any_call("Users found: 0")
        mock_print.assert_any_call("Not found: 1")
