import pytest
from unittest.mock import patch, mock_open
from delete import (
    validate_args,
    read_user_ids,
    get_base_url,
    get_access_token,
    delete_user
)
import requests

def test_validate_args_block(monkeypatch):
    test_args = ['script.py', 'users.txt', '--block']
    monkeypatch.setattr('sys.argv', test_args)
    input_file, env, block, delete = validate_args()
    assert input_file == 'users.txt'
    assert env == 'dev'
    assert block is True
    assert delete is False

def test_validate_args_delete(monkeypatch):
    test_args = ['script.py', 'users.txt', '--delete']
    monkeypatch.setattr('sys.argv', test_args)
    input_file, env, block, delete = validate_args()
    assert input_file == 'users.txt'
    assert env == 'dev'
    assert block is False
    assert delete is True

def test_validate_args_block_and_delete(monkeypatch):
    test_args = ['script.py', 'users.txt', '--block', '--delete']
    monkeypatch.setattr('sys.argv', test_args)
    input_file, env, block, delete = validate_args()
    assert input_file == 'users.txt'
    assert env == 'dev'
    assert block is True
    assert delete is True

def test_validate_args_neither(monkeypatch):
    test_args = ['script.py', 'users.txt']
    monkeypatch.setattr('sys.argv', test_args)
    with pytest.raises(SystemExit):
        validate_args()

def test_validate_args_invalid_flag(monkeypatch):
    test_args = ['script.py', 'users.txt', '--foo']
    monkeypatch.setattr('sys.argv', test_args)
    with pytest.raises(SystemExit):
        validate_args()

def test_validate_args_with_env(monkeypatch):
    test_args = ['script.py', 'users.txt', 'prod', '--block']
    monkeypatch.setattr('sys.argv', test_args)
    input_file, env, block, delete = validate_args()
    assert input_file == 'users.txt'
    assert env == 'prod'
    assert block is True
    assert delete is False

def test_validate_args_no_args(monkeypatch):
    test_args = ['script.py']
    monkeypatch.setattr('sys.argv', test_args)
    with pytest.raises(SystemExit):
        validate_args()

def test_read_user_ids():
    test_content = "user1\nuser2\nuser3"
    with patch('builtins.open', mock_open(read_data=test_content)):
        result = read_user_ids('dummy.txt')
        assert result == ['user1', 'user2', 'user3']

@patch('os.getenv')
def test_get_base_url_dev(mock_getenv):
    mock_getenv.return_value = 'test-domain.com'
    result = get_base_url('dev')
    assert result == 'https://test-domain.com'
    mock_getenv.assert_any_call('DEV_AUTH0_DOMAIN')

@patch('os.getenv')
def test_get_base_url_prod(mock_getenv):
    mock_getenv.return_value = 'prod-domain.com'
    result = get_base_url('prod')
    assert result == 'https://prod-domain.com'
    mock_getenv.assert_any_call('AUTH0_DOMAIN')

def test_get_base_url_invalid():
    with pytest.raises(ValueError):
        get_base_url('invalid')

@patch('requests.post')
@patch('os.getenv')
def test_get_access_token_dev(mock_getenv, mock_post):
    # Update mock environment variables to match expected keys
    env_vars = {
        'DEVELOPMENT_CLIENT_ID': 'dev-client-id',
        'DEVELOPMENT_CLIENT_SECRET': 'dev-secret',
        'DEV_AUTH0_DOMAIN': 'dev-domain.com'
    }
    mock_getenv.side_effect = lambda x: env_vars.get(x)

    mock_post.return_value.json.return_value = {'access_token': 'test_token'}
    mock_post.return_value.raise_for_status.return_value = None

    token = get_access_token('dev')
    assert token == 'test_token'

    # Verify the correct URL and payload were used
    mock_post.assert_called_once()
    call_args = mock_post.call_args
    assert call_args[0][0] == 'https://dev-domain.com/oauth/token'
    assert call_args[1]['json']['client_id'] == 'dev-client-id'
    assert call_args[1]['json']['client_secret'] == 'dev-secret'
    assert call_args[1]['json']['audience'] == 'https://dev-domain.com/api/v2/'

@patch('requests.delete')
def test_delete_user_success(mock_delete):
    mock_delete.return_value.raise_for_status.return_value = None
    delete_user('user123', 'token123', 'https://test-url')
    mock_delete.assert_called_once_with(
        'https://test-url/api/v2/users/user123',
        headers={
            'Authorization': 'Bearer token123',
            'Content-Type': 'application/json'
        }
    )

@patch('requests.delete')
def test_delete_user_error(mock_delete):
    mock_delete.side_effect = requests.exceptions.RequestException("Test error")
    delete_user('user123', 'token123', 'https://test-url')
    mock_delete.assert_called_once()
