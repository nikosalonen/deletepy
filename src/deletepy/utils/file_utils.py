"""File operation utilities for Auth0 user management."""

import os
import shutil
import signal
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, TextIO, cast

from deletepy.core.exceptions import FileOperationError
from deletepy.utils.display_utils import print_error, print_warning

# Graceful shutdown handler
shutdown_requested = False


def handle_shutdown(signum: int, frame: Any) -> None:
    """Handle graceful shutdown on interrupt signals."""
    global shutdown_requested
    print_warning("\nShutdown requested. Finishing current operation...")
    shutdown_requested = True


def validate_file_path(file_path: str, operation: str = "access") -> Path:
    """Validate a file path for the specified operation.

    Args:
        file_path: Path to validate
        operation: Type of operation (read, write, access)

    Returns:
        Path object if valid

    Raises:
        FileOperationError: If path is invalid for the operation
    """
    try:
        path = Path(file_path).resolve()
    except (OSError, ValueError) as e:
        raise FileOperationError(f"Invalid file path '{file_path}': {e}") from e

    if operation == "read":
        if not path.exists():
            raise FileOperationError(f"File not found: {path}")
        if not path.is_file():
            raise FileOperationError(f"Path is not a file: {path}")
        if not os.access(path, os.R_OK):
            raise FileOperationError(f"Permission denied reading file: {path}")
    elif operation == "write":
        # Check if parent directory exists and is writable
        parent = path.parent
        if not parent.exists():
            raise FileOperationError(f"Directory does not exist: {parent}")
        if not parent.is_dir():
            raise FileOperationError(f"Parent path is not a directory: {parent}")
        if not os.access(parent, os.W_OK):
            raise FileOperationError(
                f"Permission denied writing to directory: {parent}"
            )

        # If file exists, check if it's writable
        if path.exists():
            if not path.is_file():
                raise FileOperationError(f"Path exists but is not a file: {path}")
            if not os.access(path, os.W_OK):
                raise FileOperationError(f"Permission denied writing to file: {path}")

    return path


@contextmanager
def safe_file_read(
    file_path: str, encoding: str = "utf-8"
) -> Generator[TextIO, None, None]:
    """Context manager for safe file reading with comprehensive error handling.

    Args:
        file_path: Path to the file to read
        encoding: File encoding (default: utf-8)

    Yields:
        File object for reading

    Raises:
        FileOperationError: If file cannot be read
    """
    path = validate_file_path(file_path, "read")

    try:
        with open(path, encoding=encoding) as file:
            yield file
    except PermissionError as e:
        raise FileOperationError(f"Permission denied reading file: {path}") from e
    except IsADirectoryError as e:
        raise FileOperationError(f"Path is a directory, not a file: {path}") from e
    except UnicodeDecodeError as e:
        raise FileOperationError(f"File encoding error in {path}: {e}") from e
    except OSError as e:
        raise FileOperationError(f"OS error reading file {path}: {e}") from e
    except Exception as e:
        raise FileOperationError(f"Unexpected error reading file {path}: {e}") from e


def _restore_backup(backup_path: Path | None, original_path: Path) -> None:
    """Helper function to restore backup file to original path.

    Args:
        backup_path: Path to the backup file (may be None)
        original_path: Path to restore the backup to
    """
    if backup_path and backup_path.exists():
        try:
            shutil.move(backup_path, original_path)
        except Exception:
            # Silently ignore backup restoration failures
            pass


@contextmanager
def safe_file_write(
    file_path: str, encoding: str = "utf-8", mode: str = "w"
) -> Generator[TextIO, None, None]:
    """Context manager for safe file writing with comprehensive error handling.

    Args:
        file_path: Path to the file to write
        encoding: File encoding (default: utf-8)
        mode: File mode (default: w)

    Yields:
        File object for writing

    Raises:
        FileOperationError: If file cannot be written
    """
    path = validate_file_path(file_path, "write")

    # Create a backup if file exists and we're overwriting
    backup_path: Path | None = None
    if mode in ["w", "wt"] and path.exists():
        backup_path = path.with_suffix(path.suffix + ".backup")
        try:
            shutil.copy2(path, backup_path)
        except Exception:
            # Continue without backup if backup creation fails
            backup_path = None

    try:
        with open(path, mode, encoding=encoding) as file:
            yield cast(TextIO, file)

        # Remove backup on successful write
        if backup_path and backup_path.exists():
            backup_path.unlink()

    except PermissionError as e:
        _restore_backup(backup_path, path)
        raise FileOperationError(f"Permission denied writing to file: {path}") from e
    except OSError as e:
        _restore_backup(backup_path, path)
        raise FileOperationError(f"OS error writing to file {path}: {e}") from e
    except Exception as e:
        _restore_backup(backup_path, path)
        raise FileOperationError(f"Unexpected error writing to file {path}: {e}") from e


def safe_file_copy(src_path: str, dst_path: str) -> bool:
    """Safely copy a file with error handling.

    Args:
        src_path: Source file path
        dst_path: Destination file path

    Returns:
        True if successful, False otherwise
    """
    try:
        src = validate_file_path(src_path, "read")
        dst = validate_file_path(dst_path, "write")

        shutil.copy2(src, dst)
        return True

    except FileOperationError as e:
        print_error(f"File operation error: {e}")
        return False
    except Exception as e:
        print_error(f"Unexpected error copying file: {e}")
        return False


def safe_file_move(src_path: str, dst_path: str) -> bool:
    """Safely move a file with error handling.

    Args:
        src_path: Source file path
        dst_path: Destination file path

    Returns:
        True if successful, False otherwise
    """
    try:
        src = validate_file_path(src_path, "read")
        dst = validate_file_path(dst_path, "write")

        shutil.move(src, dst)
        return True

    except FileOperationError as e:
        print_error(f"File operation error: {e}")
        return False
    except Exception as e:
        print_error(f"Unexpected error moving file: {e}")
        return False


def safe_file_delete(file_path: str) -> bool:
    """Safely delete a file with error handling.

    Args:
        file_path: Path to file to delete

    Returns:
        True if successful, False otherwise
    """
    try:
        path = validate_file_path(file_path, "read")
        path.unlink()
        return True

    except FileOperationError as e:
        print_error(f"File operation error: {e}")
        return False
    except Exception as e:
        print_error(f"Unexpected error deleting file: {e}")
        return False


def read_user_ids(filepath: str) -> list[str]:
    """Read user IDs from a file with comprehensive validation.

    Args:
        filepath: Path to file containing user IDs

    Returns:
        List of validated user IDs
    """
    from deletepy.utils.validators import InputValidator, SecurityValidator

    try:
        # First validate the file path for security
        path_result = InputValidator.validate_file_path_secure(filepath)
        if not path_result.is_valid:
            print_error(f"Invalid file path {filepath}: {path_result.error_message}")
            return []

        # Show path warnings if any
        if path_result.warnings:
            for warning in path_result.warnings:
                print_warning(f"File path warning: {warning}")

        user_ids = []
        with safe_file_read(filepath) as file:
            for line in file:
                # Sanitize input first
                sanitized_line = SecurityValidator.sanitize_user_input(line)
                if not sanitized_line:
                    continue

                # Basic validation - let the calling code do specific validation
                # since this could be emails, user IDs, or other identifiers
                user_ids.append(sanitized_line)

        return user_ids
    except FileOperationError as e:
        print_error(f"Error reading user IDs from {filepath}: {e}")
        return []


def read_user_ids_generator(filepath: str) -> Generator[str, None, None]:
    """Read user IDs from a file as a generator with comprehensive validation.

    Args:
        filepath: Path to file containing user IDs

    Yields:
        Validated user IDs one at a time
    """
    from deletepy.utils.validators import InputValidator, SecurityValidator

    try:
        # First validate the file path for security
        path_result = InputValidator.validate_file_path_secure(filepath)
        if not path_result.is_valid:
            print_error(f"Invalid file path {filepath}: {path_result.error_message}")
            return

        # Show path warnings if any
        if path_result.warnings:
            for warning in path_result.warnings:
                print_warning(f"File path warning: {warning}")

        with safe_file_read(filepath) as file:
            for line in file:
                # Sanitize input first
                sanitized_line = SecurityValidator.sanitize_user_input(line)
                if sanitized_line:
                    yield sanitized_line
    except FileOperationError as e:
        print_error(f"Error reading user IDs from {filepath}: {e}")
        return


def setup_signal_handlers() -> None:
    """Setup signal handlers for graceful shutdown."""
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)


def check_shutdown_requested() -> bool:
    """Check if a shutdown has been requested.

    Returns:
        True if shutdown was requested
    """
    return shutdown_requested
