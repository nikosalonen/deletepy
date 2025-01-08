import pytest
from unittest.mock import patch, mock_open
from delete import (
    validate_args,
    read_user_ids,
    get_base_url,
    get_access_token,
    delete_user
)

def test_validate_args_with_file_only(monkeypatch):
    test_args = ['script.py', 'users.txt']
    monkeypatch.setattr('sys.argv', test_args)
    input_file, env = validate_args()
    assert input_file == 'users.txt'
    assert env == 'dev'

def test_validate_args_with_env(monkeypatch):
    test_args = ['script.py', 'users.txt', 'prod']
    monkeypatch.setattr('sys.argv', test_args)
    input_file, env = validate_args()
    assert input_file == 'users.txt'
    assert env == 'prod'

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

def test_get_base_url_dev():
    assert get_base_url('dev') == 'https://tunnus-dev.almamedia.net'

def test_get_base_url_prod():
    assert get_base_url('prod') == 'https://tunnus.almamedia.fi'

def test_get_base_url_invalid():
    with pytest.raises(SystemExit):
        get_base_url('invalid')

@patch('requests.post')
@patch('os.getenv')
def test_get_access_token_dev(mock_getenv, mock_post):
    mock_getenv.side_effect = ['dev_client_id', 'dev_client_secret']
    mock_post.return_value.json.return_value = {'access_token': 'test_token'}
    mock_post.return_value.raise_for_status.return_value = None

    token = get_access_token('dev')
    assert token == 'test_token'
    mock_post.assert_called_once()

@patch('requests.delete')
def test_delete_user(mock_delete):
    mock_delete.return_value.text = 'Success'
    delete_user('user123', 'token123', 'https://test-url')
    mock_delete.assert_called_once_with(
        'https://test-url/api/v2/users/user123',
        headers={
            'Authorization': 'Bearer token123',
            'Content-Type': 'application/json'
        }
    )
