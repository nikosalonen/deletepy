import pytest
from unittest.mock import patch, mock_open
import sys
from main import validate_args
from utils import read_user_ids_generator

# --- Argument Parsing Tests ---

def test_validate_args_block(monkeypatch):
    test_args = ['script.py', 'users.txt', '--block']
    monkeypatch.setattr('sys.argv', test_args)
    input_file, env, block, delete, revoke_grants_only, check_unblocked, check_domains = validate_args()
    assert input_file == 'users.txt'
    assert env == 'dev'
    assert block is True
    assert delete is False
    assert revoke_grants_only is False
    assert check_unblocked is False
    assert check_domains is False

def test_validate_args_check_unblocked(monkeypatch):
    test_args = ['script.py', 'users.txt', '--check-unblocked']
    monkeypatch.setattr('sys.argv', test_args)
    input_file, env, block, delete, revoke_grants_only, check_unblocked, check_domains = validate_args()
    assert check_unblocked is True
    assert not any([block, delete, revoke_grants_only, check_domains])

def test_validate_args_check_domains(monkeypatch):
    test_args = ['script.py', 'users.txt', '--check-domains']
    monkeypatch.setattr('sys.argv', test_args)
    input_file, env, block, delete, revoke_grants_only, check_unblocked, check_domains = validate_args()
    assert check_domains is True
    assert not any([block, delete, revoke_grants_only, check_unblocked])

def test_validate_args_mutual_exclusive(monkeypatch):
    # block + check-unblocked
    test_args = ['script.py', 'users.txt', '--block', '--check-unblocked']
    monkeypatch.setattr('sys.argv', test_args)
    with pytest.raises(SystemExit):
        validate_args()
    # check-domains + check-unblocked
    test_args = ['script.py', 'users.txt', '--check-domains', '--check-unblocked']
    monkeypatch.setattr('sys.argv', test_args)
    with pytest.raises(SystemExit):
        validate_args()
    # block + check-domains
    test_args = ['script.py', 'users.txt', '--block', '--check-domains']
    monkeypatch.setattr('sys.argv', test_args)
    with pytest.raises(SystemExit):
        validate_args()

def test_validate_args_no_flag(monkeypatch):
    test_args = ['script.py', 'users.txt']
    monkeypatch.setattr('sys.argv', test_args)
    with pytest.raises(SystemExit):
        validate_args()

def test_validate_args_delete(monkeypatch):
    test_args = ['script.py', 'users.txt', '--delete']
    monkeypatch.setattr('sys.argv', test_args)
    input_file, env, block, delete, revoke_grants_only, check_unblocked, check_domains = validate_args()
    assert input_file == 'users.txt'
    assert env == 'dev'
    assert block is False
    assert delete is True
    assert revoke_grants_only is False
    assert check_unblocked is False
    assert check_domains is False

def test_validate_args_revoke_grants_only(monkeypatch):
    test_args = ['script.py', 'users.txt', '--revoke-grants-only']
    monkeypatch.setattr('sys.argv', test_args)
    input_file, env, block, delete, revoke_grants_only, check_unblocked, check_domains = validate_args()
    assert input_file == 'users.txt'
    assert env == 'dev'
    assert block is False
    assert delete is False
    assert revoke_grants_only is True
    assert check_unblocked is False
    assert check_domains is False

def test_validate_args_block_and_delete(monkeypatch):
    test_args = ['script.py', 'users.txt', '--block', '--delete']
    monkeypatch.setattr('sys.argv', test_args)
    with pytest.raises(SystemExit):
        validate_args()

def test_validate_args_block_and_revoke(monkeypatch):
    test_args = ['script.py', 'users.txt', '--block', '--revoke-grants-only']
    monkeypatch.setattr('sys.argv', test_args)
    with pytest.raises(SystemExit):
        validate_args()

def test_validate_args_delete_and_revoke(monkeypatch):
    test_args = ['script.py', 'users.txt', '--delete', '--revoke-grants-only']
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
    input_file, env, block, delete, revoke_grants_only, check_unblocked, check_domains = validate_args()
    assert input_file == 'users.txt'
    assert env == 'prod'
    assert block is True
    assert delete is False
    assert revoke_grants_only is False
    assert check_unblocked is False
    assert check_domains is False

def test_validate_args_no_args(monkeypatch):
    test_args = ['script.py']
    monkeypatch.setattr('sys.argv', test_args)
    with pytest.raises(SystemExit):
        validate_args()

def test_read_user_ids():
    test_content = "user1\nuser2\nuser3"
    with patch('builtins.open', mock_open(read_data=test_content)):
        result = list(read_user_ids_generator('dummy.txt'))
        assert result == ['user1', 'user2', 'user3']

# --- Main Functionality Tests ---

def test_main_block_operation(monkeypatch):
    test_args = ['script.py', 'users.txt', '--block']
    monkeypatch.setattr('sys.argv', test_args)
    with patch('main.block_user') as mock_block:
        mock_block.return_value = True
        from main import main
        main()
        mock_block.assert_called()

def test_main_delete_operation(monkeypatch):
    test_args = ['script.py', 'users.txt', '--delete']
    monkeypatch.setattr('sys.argv', test_args)
    with patch('main.delete_user') as mock_delete:
        mock_delete.return_value = True
        from main import main
        main()
        mock_delete.assert_called()

def test_main_revoke_grants_operation(monkeypatch):
    test_args = ['script.py', 'users.txt', '--revoke-grants-only']
    monkeypatch.setattr('sys.argv', test_args)
    with patch('main.revoke_user_grants') as mock_revoke:
        mock_revoke.return_value = True
        from main import main
        main()
        mock_revoke.assert_called()

def test_main_check_unblocked_operation(monkeypatch):
    test_args = ['script.py', 'users.txt', '--check-unblocked']
    monkeypatch.setattr('sys.argv', test_args)
    with patch('main.check_unblocked_users') as mock_check:
        mock_check.return_value = True
        from main import main
        main()
        mock_check.assert_called()

def test_main_check_domains_operation(monkeypatch):
    test_args = ['script.py', 'users.txt', '--check-domains']
    monkeypatch.setattr('sys.argv', test_args)
    with patch('main.check_domains') as mock_check:
        mock_check.return_value = True
        from main import main
        main()
        mock_check.assert_called()

def test_main_error_handling(monkeypatch):
    test_args = ['script.py', 'users.txt', '--block']
    monkeypatch.setattr('sys.argv', test_args)
    with patch('main.block_user') as mock_block:
        mock_block.side_effect = Exception("Test error")
        from main import main
        with pytest.raises(SystemExit):
            main()
