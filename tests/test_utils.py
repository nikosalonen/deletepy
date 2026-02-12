import os
import tempfile
from unittest.mock import patch

import pytest

from src.deletepy.cli.validators import validate_args
from src.deletepy.utils.file_utils import read_user_ids, read_user_ids_generator


def test_read_user_ids():
    # Create a temporary file with test data
    with tempfile.NamedTemporaryFile(mode="w", delete=False) as temp:
        temp.write("user1\nuser2\nuser3\n")
        temp_path = temp.name

    try:
        # Test reading user IDs
        result = read_user_ids(temp_path)
        assert len(result) == 3
        assert result == ["user1", "user2", "user3"]

        # Test reading empty file
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as empty_temp:
            empty_path = empty_temp.name

        empty_result = read_user_ids(empty_path)
        assert len(empty_result) == 0

    finally:
        # Cleanup
        os.unlink(temp_path)
        os.unlink(empty_path)


def test_read_user_ids_generator():
    # Create a temporary file with test data
    with tempfile.NamedTemporaryFile(mode="w", delete=False) as temp:
        temp.write("user1\nuser2\nuser3\n")
        temp_path = temp.name

    try:
        # Test reading user IDs using generator
        result = list(read_user_ids_generator(temp_path))
        assert len(result) == 3
        assert result == ["user1", "user2", "user3"]

        # Test reading empty file
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as empty_temp:
            empty_path = empty_temp.name

        empty_result = list(read_user_ids_generator(empty_path))
        assert len(empty_result) == 0

    finally:
        # Cleanup
        os.unlink(temp_path)
        os.unlink(empty_path)


def test_read_user_ids_file_not_found():
    # The function handles file not found gracefully and returns empty list
    result = read_user_ids("nonexistent_file.txt")
    assert result == []


def test_read_user_ids_generator_file_not_found():
    # The generator function handles file not found gracefully and returns empty generator
    result = list(read_user_ids_generator("nonexistent_file.txt"))
    assert result == []


def test_validate_args():
    # Test block operation
    with pytest.raises(SystemExit):
        validate_args()  # Should exit when no args provided

    # Test with valid arguments
    import sys

    original_argv = sys.argv.copy()
    try:
        sys.argv = ["script.py", "test.txt", "dev", "--block"]
        args = validate_args()
        assert args.input_file == "test.txt"
        assert args.env == "dev"
        assert args.operation == "block"

        # Test with invalid environment
        sys.argv = ["script.py", "test.txt", "invalid_env", "--block"]
        with pytest.raises(SystemExit):
            validate_args()

        # Test with missing operation
        sys.argv = ["script.py", "test.txt", "dev"]
        with pytest.raises(SystemExit):
            validate_args()
    finally:
        sys.argv = original_argv


@pytest.mark.parametrize(
    "flag,expected_operation",
    [
        ("--block", "block"),
        ("--delete", "delete"),
        ("--revoke-grants-only", "revoke-grants-only"),
        ("--check-unblocked", "check-unblocked"),
        ("--check-domains", "check-domains"),
        ("--export-last-login", "export-last-login"),
        ("--doctor", "doctor"),
        ("--unlink-social-ids", "unlink-social-ids"),
    ],
)
def test_validate_args_operations(monkeypatch, flag, expected_operation):
    """Test that validate_args correctly parses all supported operation flags."""
    # Set up test arguments
    test_args = ["script.py", "test.txt", "dev", flag]
    monkeypatch.setattr("sys.argv", test_args)

    # Parse arguments
    args = validate_args()

    # Verify the operation was parsed correctly
    assert args.input_file == "test.txt"
    assert args.env == "dev"
    assert args.operation == expected_operation


@pytest.fixture
def mock_requests(request):
    """Create a mock requests module.

    This fixture automatically determines which module to patch based on the test module name.
    """
    module_name = request.module.__name__.replace("test_", "")
    with patch(f"{module_name}.requests") as mock:
        yield mock


# =============================================================================
# Tests for get_stderr_console singleton
# =============================================================================


class TestGetStderrConsole:
    """Tests for the shared stderr console singleton."""

    def teardown_method(self):
        """Reset the singleton between tests."""
        import src.deletepy.utils.rich_utils as mod

        mod._stderr_console = None

    def test_returns_console(self):
        from src.deletepy.utils.rich_utils import get_stderr_console

        console = get_stderr_console()
        from rich.console import Console

        assert isinstance(console, Console)

    def test_singleton(self):
        from src.deletepy.utils.rich_utils import get_stderr_console

        c1 = get_stderr_console()
        c2 = get_stderr_console()
        assert c1 is c2

    def test_writes_to_stderr(self):
        from src.deletepy.utils.rich_utils import get_stderr_console

        console = get_stderr_console()
        assert console.stderr is True


# =============================================================================
# Tests for live_progress context manager
# =============================================================================


class TestLiveProgress:
    """Tests for the live_progress context manager."""

    def test_zero_total_yields_noop(self):
        from src.deletepy.utils.display_utils import live_progress

        with live_progress(0, "Testing") as advance:
            advance()  # Should not raise
            advance(5)  # Should not raise

    @patch("src.deletepy.utils.display_utils._RICH_PROGRESS_AVAILABLE", False)
    @patch("src.deletepy.utils.display_utils.show_progress")
    @patch("src.deletepy.utils.display_utils.clear_progress_line")
    def test_fallback_to_ascii(self, mock_clear, mock_show):
        from src.deletepy.utils.display_utils import live_progress

        with live_progress(3, "Fallback") as advance:
            advance()
            advance()
            advance()

        assert mock_show.call_count == 3
        mock_clear.assert_called_once()

    def test_rich_progress_path(self):
        """Test that Rich progress path works when Rich is available."""
        from src.deletepy.utils.display_utils import live_progress

        counter = 0
        with live_progress(3, "Rich test") as advance:
            for _ in range(3):
                advance()
                counter += 1

        assert counter == 3

    def test_advance_with_step(self):
        """Test that advance accepts a step parameter."""
        from src.deletepy.utils.display_utils import live_progress

        with live_progress(10, "Step test") as advance:
            advance(5)
            advance(5)
