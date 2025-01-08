import pytest
from unittest.mock import patch, mock_open
from delete import validate_args, read_user_ids, get_base_url, delete_user

def test_read_user_ids():
    """Test reading user IDs from file."""
    mock_data = "user1\nuser2\nuser3"
    with patch("builtins.open", mock_open(read_data=mock_data)):
        result = read_user_ids("dummy_path")
        assert result == ["user1", "user2", "user3"]

def test_get_base_url_prod():
    """Test base URL for prod environment."""
    assert get_base_url("prod") == "https://tunnus.almamedia.fi"

def test_get_base_url_dev():
    """Test base URL for dev environment."""
    assert get_base_url("dev") == "https://tunnus-dev.almamedia.net"

def test_get_base_url_invalid():
    """Test base URL with invalid environment."""
    with pytest.raises(SystemExit):
        get_base_url("invalid")

@patch('sys.argv', ['delete.py', 'ids.txt', 'token123', 'prod'])
def test_validate_args_valid():
    """Test argument validation with valid inputs."""
    token, input_file, env = validate_args()
    assert token == 'token123'
    assert input_file == 'ids.txt'
    assert env == 'prod'

@patch('sys.argv', ['delete.py', 'ids.txt'])
def test_validate_args_invalid():
    """Test argument validation with invalid inputs."""
    with pytest.raises(SystemExit):
        validate_args()

@patch('requests.delete')
def test_delete_user(mock_delete):
    """Test user deletion."""
    mock_delete.return_value.text = 'Success'

    delete_user('user123', 'token123', 'https://example.com')

    mock_delete.assert_called_once_with(
        'https://example.com/api/v2/users/user123',
        headers={
            'Authorization': 'Bearer token123',
            'Content-Type': 'application/json'
        }
    )
