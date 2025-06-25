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
    find_users_by_social_media_ids
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

def test_find_users_by_social_media_ids_found(mock_requests, mock_response):
    # Mock response with a user found
    mock_response.json.return_value = [{
        "user_id": "auth0|123456789",
        "email": "test@example.com",
        "identities": [{
            "user_id": "12345678901234567890",
            "connection": "google-oauth2"
        }]
    }]
    mock_requests.request.return_value = mock_response

    with patch('builtins.print') as mock_print, \
         patch('user_operations.show_progress'):
        find_users_by_social_media_ids(["12345678901234567890"], "test_token", "http://test.com")

        # Verify API call was made correctly
        mock_requests.request.assert_called_once()
        mock_requests.request.assert_called_with(
            "GET",
            "http://test.com/api/v2/users",
            headers={
                "Authorization": "Bearer test_token",
                "Content-Type": "application/json",
                "User-Agent": "DeletePy/1.0 (Auth0 User Management Tool)"
            },
            params={
                "q": 'identities.user_id:"12345678901234567890"',
                "search_engine": "v3"
            },
            timeout=30
        )

        # Verify output includes found user
        mock_print.assert_any_call("Users found: 1")
        mock_print.assert_any_call("Not found: 0")

def test_find_users_by_social_media_ids_not_found(mock_requests, mock_response):
    # Mock empty response - no users found
    mock_response.json.return_value = []
    mock_requests.request.return_value = mock_response

    with patch('builtins.print') as mock_print, \
         patch('user_operations.show_progress'):
        find_users_by_social_media_ids(["nonexistent123"], "test_token", "http://test.com")

        # Verify API call was made correctly
        mock_requests.request.assert_called_once()
        mock_requests.request.assert_called_with(
            "GET",
            "http://test.com/api/v2/users",
            headers={
                "Authorization": "Bearer test_token",
                "Content-Type": "application/json",
                "User-Agent": "DeletePy/1.0 (Auth0 User Management Tool)"
            },
            params={
                "q": 'identities.user_id:"nonexistent123"',
                "search_engine": "v3"
            },
            timeout=30
        )

        # Verify output shows no users found
        mock_print.assert_any_call("Users found: 0")
        mock_print.assert_any_call("Not found: 1")

def test_find_users_by_social_media_ids_multiple_ids(mock_requests, mock_response):
    # Mock responses for multiple social IDs - first found, second not found
    mock_response.json.side_effect = [
        [{
            "user_id": "auth0|123456789",
            "email": "test@example.com",
            "identities": [{
                "user_id": "12345678901234567890",
                "connection": "google-oauth2"
            }]
        }],
        []  # Second ID not found
    ]
    mock_requests.request.return_value = mock_response

    with patch('builtins.print') as mock_print, \
         patch('user_operations.show_progress'):
        find_users_by_social_media_ids(["12345678901234567890", "nonexistent123"], "test_token", "http://test.com")

        # Verify two API calls were made
        assert mock_requests.request.call_count == 2

        # Verify output shows summary
        mock_print.assert_any_call("Total social IDs searched: 2")
        mock_print.assert_any_call("Users found: 1")
        mock_print.assert_any_call("Not found: 1")

def test_find_users_by_social_media_ids_empty_input(mock_requests, mock_response):
    with patch('builtins.print') as mock_print, \
         patch('user_operations.show_progress'):
        find_users_by_social_media_ids([], "test_token", "http://test.com")

        # Verify no API calls were made for empty input
        mock_requests.request.assert_not_called()

        # Verify summary shows zero results
        mock_print.assert_any_call("Total social IDs searched: 0")
        mock_print.assert_any_call("Users found: 0")
        mock_print.assert_any_call("Not found: 0")

def test_find_users_by_social_media_ids_whitespace_handling(mock_requests, mock_response):
    # Mock response for trimmed social ID
    mock_response.json.return_value = [{
        "user_id": "auth0|123456789",
        "email": "test@example.com",
        "identities": [{
            "user_id": "12345678901234567890",
            "connection": "google-oauth2"
        }]
    }]
    mock_requests.request.return_value = mock_response

    with patch('builtins.print'), \
         patch('user_operations.show_progress'):
        # Test with social ID that has whitespace
        find_users_by_social_media_ids(["  12345678901234567890  ", ""], "test_token", "http://test.com")

        # Verify only one API call was made (empty string skipped)
        mock_requests.request.assert_called_once()
        
        # Verify the API call used the trimmed social ID
        call_args = mock_requests.request.call_args
        assert call_args[1]['params']['q'] == 'identities.user_id:"12345678901234567890"'
