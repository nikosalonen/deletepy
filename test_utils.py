import pytest
from unittest.mock import patch, mock_open
import signal
import sys
from utils import (
    handle_shutdown,
    read_user_ids,
    read_user_ids_generator,
    validate_args,
    show_progress,
    shutdown_requested
)

def test_handle_shutdown():
    # Test that handle_shutdown sets the global flag and exits
    with patch('sys.stdout.write') as mock_write, \
         patch('sys.stdout.flush') as mock_flush, \
         patch('sys.exit') as mock_exit:
        handle_shutdown(signal.SIGINT, None)
        assert shutdown_requested is True
        mock_write.assert_called()
        mock_flush.assert_called()
        mock_exit.assert_called_once_with(130)

def test_read_user_ids_success():
    test_content = "user1\nuser2\nuser3"
    with patch('builtins.open', mock_open(read_data=test_content)):
        result = read_user_ids('dummy.txt')
        assert result == ['user1', 'user2', 'user3']

def test_read_user_ids_empty_lines():
    test_content = "user1\n\nuser2\n  \nuser3"
    with patch('builtins.open', mock_open(read_data=test_content)):
        result = read_user_ids('dummy.txt')
        assert result == ['user1', 'user2', 'user3']

def test_read_user_ids_file_not_found():
    with pytest.raises(FileNotFoundError) as exc_info:
        read_user_ids('nonexistent.txt')
    assert "Error: File nonexistent.txt not found" in str(exc_info.value)

def test_read_user_ids_io_error():
    with patch('builtins.open', mock_open()) as mock_file:
        mock_file.side_effect = IOError("Test error")
        with pytest.raises(IOError) as exc_info:
            read_user_ids('dummy.txt')
        assert "Error reading file: Test error" in str(exc_info.value)

def test_read_user_ids_generator_success():
    test_content = "user1\nuser2\nuser3"
    with patch('builtins.open', mock_open(read_data=test_content)):
        result = list(read_user_ids_generator('dummy.txt'))
        assert result == ['user1', 'user2', 'user3']

def test_read_user_ids_generator_empty_lines():
    test_content = "user1\n\nuser2\n  \nuser3"
    with patch('builtins.open', mock_open(read_data=test_content)):
        result = list(read_user_ids_generator('dummy.txt'))
        assert result == ['user1', 'user2', 'user3']

def test_read_user_ids_generator_file_not_found():
    with pytest.raises(FileNotFoundError) as exc_info:
        list(read_user_ids_generator('nonexistent.txt'))
    assert "Error: File nonexistent.txt not found" in str(exc_info.value)

def test_read_user_ids_generator_io_error():
    with patch('builtins.open', mock_open()) as mock_file:
        mock_file.side_effect = IOError("Test error")
        with pytest.raises(IOError) as exc_info:
            list(read_user_ids_generator('dummy.txt'))
        assert "Error reading file: Test error" in str(exc_info.value)

def test_validate_args_block():
    test_args = ['script.py', 'users.txt', '--block']
    with patch('sys.argv', test_args):
        args = validate_args()
        assert args.input_file == 'users.txt'
        assert args.env == 'dev'
        assert args.operation == 'block'

def test_validate_args_prod_env():
    test_args = ['script.py', 'users.txt', 'prod', '--block']
    with patch('sys.argv', test_args):
        args = validate_args()
        assert args.input_file == 'users.txt'
        assert args.env == 'prod'
        assert args.operation == 'block'

def test_validate_args_invalid_env():
    test_args = ['script.py', 'users.txt', 'invalid', '--block']
    with patch('sys.argv', test_args):
        with pytest.raises(SystemExit):
            validate_args()

def test_validate_args_no_operation():
    test_args = ['script.py', 'users.txt']
    with patch('sys.argv', test_args):
        with pytest.raises(SystemExit):
            validate_args()

def test_validate_args_multiple_operations():
    test_args = ['script.py', 'users.txt', '--block', '--delete']
    with patch('sys.argv', test_args):
        with pytest.raises(SystemExit):
            validate_args()

def test_validate_args_all_operations():
    operations = [
        ('--block', 'block'),
        ('--delete', 'delete'),
        ('--revoke-grants-only', 'revoke-grants-only'),
        ('--check-unblocked', 'check-unblocked'),
        ('--check-domains', 'check-domains')
    ]
    
    for flag, expected in operations:
        test_args = ['script.py', 'users.txt', flag]
        with patch('sys.argv', test_args):
            args = validate_args()
            assert args.operation == expected

def test_show_progress():
    with patch('sys.stdout.write') as mock_write, \
         patch('sys.stdout.flush') as mock_flush:
        show_progress(1, 10, "Testing")
        mock_write.assert_called()
        mock_flush.assert_called() 