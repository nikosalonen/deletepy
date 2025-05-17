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

    delete_user("test_user_id", "test_token", "http://test.com")

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

    block_user("test_user_id", "test_token", "http://test.com")

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

    assert mock_requests.get.call_count == 1
    assert mock_requests.delete.call_count == 2

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
    mock_response.json.return_value = {"blocked": False}
    mock_requests.get.return_value = mock_response

    check_unblocked_users(["user1", "user2"], "test_token", "http://test.com")

    assert mock_requests.get.call_count == 2

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
