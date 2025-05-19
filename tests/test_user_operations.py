import pytest
from unittest.mock import patch, MagicMock
from user_operations import (
    delete_user,
    block_user,
    get_user_id_from_email,
    revoke_user_sessions,
    revoke_user_grants,
    check_unblocked_users,
    get_user_email
)
from utils import YELLOW, CYAN, RESET

@pytest.fixture
def mock_response():
    response = MagicMock()
    response.raise_for_status = MagicMock()
    return response

@pytest.fixture
def mock_requests():
    with patch('user_operations.requests') as mock:
        yield mock

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
                "Content-Type": "application/json"
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
                "Content-Type": "application/json"
            },
            json={"blocked": True},
            timeout=30
        )

def test_get_user_id_from_email(mock_requests, mock_response):
    mock_response.json.return_value = [{"user_id": "test_user_id"}]
    mock_requests.get.return_value = mock_response

    result = get_user_id_from_email("test@example.com", "test_token", "http://test.com")

    assert result == "test_user_id"
    mock_requests.get.assert_called_once()
    mock_requests.get.assert_called_with(
        "http://test.com/api/v2/users-by-email",
        headers={
            "Authorization": "Bearer test_token",
            "Content-Type": "application/json"
        },
        params={"email": "test@example.com"},
        timeout=30
    )

def test_get_user_id_from_email_not_found(mock_requests, mock_response):
    mock_response.json.return_value = []
    mock_requests.get.return_value = mock_response

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
            "Content-Type": "application/json"
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
            "Content-Type": "application/json"
        },
        "timeout": 30
    }

    # Verify second session deletion
    assert delete_calls[1][0][0] == "http://test.com/api/v2/sessions/session2"
    assert delete_calls[1][1] == {
        "headers": {
            "Authorization": "Bearer test_token",
            "Content-Type": "application/json"
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
            "Content-Type": "application/json"
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
         patch('user_operations.show_progress') as mock_show_progress:
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
                "Content-Type": "application/json"
            },
            "timeout": 30
        }

        # Verify second user API call
        assert get_calls[1][0][0] == "http://test.com/api/v2/users/user2"
        assert get_calls[1][1] == {
            "headers": {
                "Authorization": "Bearer test_token",
                "Content-Type": "application/json"
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
            "Content-Type": "application/json"
        },
        timeout=30
    )
