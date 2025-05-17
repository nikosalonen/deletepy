import pytest
from unittest.mock import patch, mock_open
import requests
from user_operations import (
    delete_user,
    block_user,
    get_user_id_from_email,
    revoke_user_sessions,
    revoke_user_grants,
    check_unblocked_users,
    get_user_email
)

@patch('requests.delete')
def test_delete_user_success(mock_delete):
    mock_delete.return_value.raise_for_status.return_value = None
    delete_user('user123', 'token123', 'https://test-url')
    mock_delete.assert_called_once_with(
        'https://test-url/api/v2/users/user123',
        headers={
            'Authorization': 'Bearer token123',
            'Content-Type': 'application/json'
        },
        timeout=30
    )

@patch('requests.delete')
def test_delete_user_error(mock_delete):
    mock_delete.side_effect = requests.exceptions.RequestException("Test error")
    delete_user('user123', 'token123', 'https://test-url')
    mock_delete.assert_called_once()

@patch('requests.patch')
def test_block_user_success(mock_patch):
    mock_patch.return_value.raise_for_status.return_value = None
    block_user('user123', 'token123', 'https://test-url')
    mock_patch.assert_called_once_with(
        'https://test-url/api/v2/users/user123',
        headers={
            'Authorization': 'Bearer token123',
            'Content-Type': 'application/json'
        },
        json={'blocked': True},
        timeout=30
    )

@patch('requests.patch')
def test_block_user_error(mock_patch):
    mock_patch.side_effect = requests.exceptions.RequestException("Test error")
    block_user('user123', 'token123', 'https://test-url')
    mock_patch.assert_called_once()

@patch('requests.get')
def test_get_user_id_from_email_success(mock_get):
    mock_get.return_value.json.return_value = [{"user_id": "user123"}]
    mock_get.return_value.raise_for_status.return_value = None
    
    user_id = get_user_id_from_email('test@example.com', 'token123', 'https://test-url')
    assert user_id == 'user123'
    
    mock_get.assert_called_once_with(
        'https://test-url/api/v2/users-by-email',
        headers={
            'Authorization': 'Bearer token123',
            'Content-Type': 'application/json'
        },
        params={'email': 'test@example.com'},
        timeout=30
    )

@patch('requests.get')
def test_get_user_id_from_email_not_found(mock_get):
    mock_get.return_value.json.return_value = []
    mock_get.return_value.raise_for_status.return_value = None
    
    user_id = get_user_id_from_email('test@example.com', 'token123', 'https://test-url')
    assert user_id is None

@patch('requests.get')
def test_get_user_id_from_email_error(mock_get):
    mock_get.side_effect = requests.exceptions.RequestException("Test error")
    user_id = get_user_id_from_email('test@example.com', 'token123', 'https://test-url')
    assert user_id is None

@patch('requests.get')
@patch('requests.delete')
def test_revoke_user_sessions_success(mock_delete, mock_get):
    mock_get.return_value.json.return_value = {
        "sessions": [
            {"id": "session1"},
            {"id": "session2"}
        ]
    }
    mock_get.return_value.raise_for_status.return_value = None
    mock_delete.return_value.raise_for_status.return_value = None
    
    revoke_user_sessions('user123', 'token123', 'https://test-url')
    
    assert mock_get.call_count == 1
    assert mock_delete.call_count == 2

@patch('requests.get')
def test_revoke_user_sessions_no_sessions(mock_get):
    mock_get.return_value.json.return_value = {"sessions": []}
    mock_get.return_value.raise_for_status.return_value = None
    
    revoke_user_sessions('user123', 'token123', 'https://test-url')
    mock_get.assert_called_once()

@patch('requests.get')
def test_revoke_user_sessions_error(mock_get):
    mock_get.side_effect = requests.exceptions.RequestException("Test error")
    revoke_user_sessions('user123', 'token123', 'https://test-url')
    mock_get.assert_called_once()

@patch('requests.delete')
def test_revoke_user_grants_success(mock_delete):
    mock_delete.return_value.raise_for_status.return_value = None
    revoke_user_grants('user123', 'token123', 'https://test-url')
    mock_delete.assert_called_once_with(
        'https://test-url/api/v2/grants?user_id=user123',
        headers={
            'Authorization': 'Bearer token123',
            'Content-Type': 'application/json'
        },
        timeout=30
    )

@patch('requests.delete')
def test_revoke_user_grants_error(mock_delete):
    mock_delete.side_effect = requests.exceptions.RequestException("Test error")
    revoke_user_grants('user123', 'token123', 'https://test-url')
    mock_delete.assert_called_once()

@patch('requests.get')
def test_check_unblocked_users(mock_get):
    mock_get.side_effect = [
        type('Response', (), {'json': lambda: {"blocked": False}, 'raise_for_status': lambda: None})(),
        type('Response', (), {'json': lambda: {"blocked": True}, 'raise_for_status': lambda: None})(),
        type('Response', (), {'json': lambda: {"blocked": False}, 'raise_for_status': lambda: None})()
    ]
    
    check_unblocked_users(['user1', 'user2', 'user3'], 'token123', 'https://test-url')
    assert mock_get.call_count == 3

@patch('requests.get')
def test_check_unblocked_users_error(mock_get):
    mock_get.side_effect = requests.exceptions.RequestException("Test error")
    check_unblocked_users(['user1'], 'token123', 'https://test-url')
    mock_get.assert_called_once()

@patch('requests.get')
def test_get_user_email_success(mock_get):
    mock_get.return_value.json.return_value = {"email": "test@example.com"}
    mock_get.return_value.raise_for_status.return_value = None
    
    email = get_user_email('user123', 'token123', 'https://test-url')
    assert email == 'test@example.com'
    
    mock_get.assert_called_once_with(
        'https://test-url/api/v2/users/user123',
        headers={
            'Authorization': 'Bearer token123',
            'Content-Type': 'application/json'
        },
        timeout=30
    )

@patch('requests.get')
def test_get_user_email_error(mock_get):
    mock_get.side_effect = requests.exceptions.RequestException("Test error")
    email = get_user_email('user123', 'token123', 'https://test-url')
    assert email is None 