import pytest
import os
import tempfile
from utils import read_user_ids, read_user_ids_generator, validate_args

def test_read_user_ids():
    # Create a temporary file with test data
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp:
        temp.write("user1\nuser2\nuser3\n")
        temp_path = temp.name

    try:
        # Test reading user IDs
        result = read_user_ids(temp_path)
        assert len(result) == 3
        assert result == ["user1", "user2", "user3"]

        # Test reading empty file
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as empty_temp:
            empty_path = empty_temp.name

        empty_result = read_user_ids(empty_path)
        assert len(empty_result) == 0

    finally:
        # Cleanup
        os.unlink(temp_path)
        os.unlink(empty_path)

def test_read_user_ids_generator():
    # Create a temporary file with test data
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp:
        temp.write("user1\nuser2\nuser3\n")
        temp_path = temp.name

    try:
        # Test reading user IDs using generator
        result = list(read_user_ids_generator(temp_path))
        assert len(result) == 3
        assert result == ["user1", "user2", "user3"]

        # Test reading empty file
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as empty_temp:
            empty_path = empty_temp.name

        empty_result = list(read_user_ids_generator(empty_path))
        assert len(empty_result) == 0

    finally:
        # Cleanup
        os.unlink(temp_path)
        os.unlink(empty_path)

def test_read_user_ids_file_not_found():
    with pytest.raises(FileNotFoundError):
        read_user_ids("nonexistent_file.txt")

def test_read_user_ids_generator_file_not_found():
    with pytest.raises(FileNotFoundError):
        list(read_user_ids_generator("nonexistent_file.txt"))

def test_validate_args():
    # Test block operation
    with pytest.raises(SystemExit):
        validate_args()  # Should exit when no args provided

    # Test with valid arguments
    import sys
    sys.argv = ['script.py', 'test.txt', 'dev', '--block']
    args = validate_args()
    assert args.input_file == 'test.txt'
    assert args.env == 'dev'
    assert args.operation == 'block'

    # Test with invalid environment
    sys.argv = ['script.py', 'test.txt', 'invalid_env', '--block']
    with pytest.raises(SystemExit):
        validate_args()

    # Test with missing operation
    sys.argv = ['script.py', 'test.txt', 'dev']
    with pytest.raises(SystemExit):
        validate_args()
