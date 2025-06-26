import sys
import signal
import argparse
import re
import os
from pathlib import Path
from typing import List, Generator
from contextlib import contextmanager

# ANSI color codes
RESET = "\033[0m"
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"

# Auth0 user ID prefixes
AUTH0_USER_ID_PREFIXES = (
    "auth0|",
    "google-oauth2|",
    "facebook|",
    "github|",
    "twitter|",
    "linkedin|",
    "apple|",
    "microsoft|",
    "windowslive|",
    "line|",
    "samlp|",
    "oidc|",
)

# Graceful shutdown handler
shutdown_requested = False


def is_auth0_user_id(identifier: str) -> bool:
    """Check if a string is an Auth0 user ID.

    Args:
        identifier: String to check

    Returns:
        True if the string starts with a known Auth0 user ID prefix
    """
    return identifier.startswith(AUTH0_USER_ID_PREFIXES)


class FileOperationError(Exception):
    """Custom exception for file operation errors."""

    pass


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
        raise FileOperationError(f"Invalid file path '{file_path}': {e}")

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
def safe_file_read(file_path: str, encoding: str = "utf-8"):
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
        with open(path, "r", encoding=encoding) as file:
            yield file
    except PermissionError:
        raise FileOperationError(f"Permission denied reading file: {path}")
    except IsADirectoryError:
        raise FileOperationError(f"Path is a directory, not a file: {path}")
    except UnicodeDecodeError as e:
        raise FileOperationError(f"File encoding error in {path}: {e}")
    except OSError as e:
        raise FileOperationError(f"OS error reading file {path}: {e}")
    except Exception as e:
        raise FileOperationError(f"Unexpected error reading file {path}: {e}")


@contextmanager
def safe_file_write(file_path: str, encoding: str = "utf-8", mode: str = "w"):
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
    backup_path = None
    if mode in ["w", "wt"] and path.exists():
        backup_path = path.with_suffix(path.suffix + ".backup")
        try:
            import shutil

            shutil.copy2(path, backup_path)
        except Exception:
            # Continue without backup if backup creation fails
            backup_path = None

    try:
        with open(path, mode, encoding=encoding) as file:
            yield file

        # Remove backup on successful write
        if backup_path and backup_path.exists():
            backup_path.unlink()

    except PermissionError:
        # Restore backup if available
        if backup_path and backup_path.exists():
            try:
                import shutil

                shutil.move(backup_path, path)
            except Exception:
                pass
        raise FileOperationError(f"Permission denied writing to file: {path}")
    except OSError as e:
        # Restore backup if available
        if backup_path and backup_path.exists():
            try:
                import shutil

                shutil.move(backup_path, path)
            except Exception:
                pass
        raise FileOperationError(f"OS error writing to file {path}: {e}")
    except Exception as e:
        # Restore backup if available
        if backup_path and backup_path.exists():
            try:
                import shutil

                shutil.move(backup_path, path)
            except Exception:
                pass
        raise FileOperationError(f"Unexpected error writing to file {path}: {e}")


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

        import shutil

        shutil.copy2(src, dst)
        print(f"{GREEN}Successfully copied {src} to {dst}{RESET}")
        return True

    except FileOperationError as e:
        print(f"{RED}File copy error: {e}{RESET}")
        return False
    except Exception as e:
        print(f"{RED}Unexpected error copying file: {e}{RESET}")
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

        import shutil

        shutil.move(src, dst)
        print(f"{GREEN}Successfully moved {src} to {dst}{RESET}")
        return True

    except FileOperationError as e:
        print(f"{RED}File move error: {e}{RESET}")
        return False
    except Exception as e:
        print(f"{RED}Unexpected error moving file: {e}{RESET}")
        return False


def safe_file_delete(file_path: str) -> bool:
    """Safely delete a file with error handling.

    Args:
        file_path: Path to file to delete

    Returns:
        True if successful, False otherwise
    """
    try:
        path = Path(file_path).resolve()

        if not path.exists():
            print(f"{YELLOW}File does not exist: {path}{RESET}")
            return True

        if not path.is_file():
            print(f"{RED}Path is not a file: {path}{RESET}")
            return False

        if not os.access(path, os.W_OK):
            print(f"{RED}Permission denied deleting file: {path}{RESET}")
            return False

        path.unlink()
        print(f"{GREEN}Successfully deleted {path}{RESET}")
        return True

    except PermissionError:
        print(f"{RED}Permission denied deleting file: {file_path}{RESET}")
        return False
    except OSError as e:
        print(f"{RED}OS error deleting file {file_path}: {e}{RESET}")
        return False
    except Exception as e:
        print(f"{RED}Unexpected error deleting file {file_path}: {e}{RESET}")
        return False


def handle_shutdown(signum, frame):
    """Handle graceful shutdown on SIGINT."""
    global shutdown_requested
    shutdown_requested = True
    # Clear spinner/progress line
    import shutil

    terminal_width = shutil.get_terminal_size().columns
    sys.stdout.write("\r" + " " * terminal_width + "\r")
    sys.stdout.flush()
    print(f"{YELLOW}Operation cancelled by user. Exiting...{RESET}")
    sys.exit(130)


# Register signal handler
signal.signal(signal.SIGINT, handle_shutdown)


def read_user_ids(filepath: str) -> List[str]:
    """Read user IDs from file with enhanced error handling.

    Args:
        filepath: Path to the file containing user IDs

    Returns:
        List[str]: List of user IDs read from the file

    Raises:
        FileOperationError: If the file cannot be read
    """
    try:
        with safe_file_read(filepath) as f:
            # Use a generator expression to read line by line
            return [line.strip() for line in f if line.strip()]
    except FileOperationError:
        raise  # Re-raise FileOperationError as-is
    except Exception as e:
        raise FileOperationError(f"Unexpected error reading file {filepath}: {e}")


def read_user_ids_generator(filepath: str) -> Generator[str, None, None]:
    """Read user IDs from file using a generator pattern with enhanced error handling.

    Args:
        filepath: Path to the file containing user IDs

    Yields:
        str: User ID from the file

    Raises:
        FileOperationError: If the file cannot be read
    """
    try:
        with safe_file_read(filepath) as f:
            for line in f:
                line = line.strip()
                if line:  # Skip empty lines
                    yield line
    except FileOperationError:
        raise  # Re-raise FileOperationError as-is
    except Exception as e:
        raise FileOperationError(f"Unexpected error reading file {filepath}: {e}")


def validate_args() -> argparse.Namespace:
    """Parse and validate command line arguments.

    Returns:
        argparse.Namespace: Parsed arguments containing:
            - input_file: Path to the file containing user IDs (optional for doctor)
            - env: Environment to run in ('dev' or 'prod')
            - operation: The operation to perform (block/delete/revoke-grants-only/check-unblocked/check-domains/doctor)
    """
    parser = argparse.ArgumentParser(
        description="Process user operations based on IDs from a file.",
        usage="python main.py <ids_file> [env] [--block|--delete|--revoke-grants-only|--check-unblocked|--check-domains|--doctor]",
    )

    parser.add_argument(
        "input_file",
        nargs="?",
        help="Path to the file containing user IDs (not required for --doctor)",
    )

    parser.add_argument(
        "env",
        nargs="?",
        choices=["dev", "prod"],
        default="dev",
        help="Environment to run in (default: dev)",
    )

    operation_group = parser.add_mutually_exclusive_group(required=True)
    operation_group.add_argument(
        "--block",
        action="store_const",
        const="block",
        dest="operation",
        help="Block the specified users",
    )
    operation_group.add_argument(
        "--delete",
        action="store_const",
        const="delete",
        dest="operation",
        help="Delete the specified users",
    )
    operation_group.add_argument(
        "--revoke-grants-only",
        action="store_const",
        const="revoke-grants-only",
        dest="operation",
        help="Revoke grants for the specified users",
    )
    operation_group.add_argument(
        "--check-unblocked",
        action="store_const",
        const="check-unblocked",
        dest="operation",
        help="Check if specified users are unblocked",
    )
    operation_group.add_argument(
        "--check-domains",
        action="store_const",
        const="check-domains",
        dest="operation",
        help="Check domains for the specified users",
    )
    operation_group.add_argument(
        "--export-last-login",
        action="store_const",
        const="export-last-login",
        dest="operation",
        help="Export user last_login data to CSV",
    )
    operation_group.add_argument(
        "--doctor",
        action="store_const",
        const="doctor",
        dest="operation",
        help="Test if credentials work",
    )
    operation_group.add_argument(
        "--find-social-ids",
        action="store_const",
        const="find-social-ids",
        dest="operation",
        help="Find users by social media IDs from identities",
    )

    parser.add_argument(
        "--test-api",
        action="store_true",
        help="Test API access when using --doctor (optional)",
    )

    parser.add_argument(
        "--connection",
        type=str,
        help="Filter users by connection type (e.g., 'google-oauth2', 'auth0', 'facebook')",
    )

    args = parser.parse_args()

    # Special handling for doctor command: if first argument is 'dev' or 'prod' and operation is doctor,
    # treat it as the environment instead of input_file
    if args.operation == "doctor" and args.input_file in ["dev", "prod"]:
        args.env = args.input_file
        args.input_file = None

    # Validate that input_file is provided for all operations except doctor
    if args.operation != "doctor" and not args.input_file:
        parser.error(f"input_file is required for operation '{args.operation}'")

    return args


def validate_auth0_user_id(user_id: str) -> bool:
    """Validate Auth0 user ID format.

    Auth0 user IDs typically follow patterns like:
    - auth0|123456789012345678901234
    - google-oauth2|123456789012345678901
    - email|507f1f77bcf86cd799439011

    Args:
        user_id: The user ID to validate

    Returns:
        bool: True if valid Auth0 user ID format, False otherwise
    """
    if not user_id or not isinstance(user_id, str):
        return False

    # Auth0 user IDs have connection|identifier format
    # Connection can contain letters, numbers, hyphens
    # Identifier is typically alphanumeric
    pattern = r"^[a-zA-Z0-9\-]+\|[a-zA-Z0-9]+$"
    return bool(re.match(pattern, user_id))


def show_progress(current: int, total: int, operation: str) -> None:
    """Show progress indicator for bulk operations.

    Args:
        current: Current item number
        total: Total number of items
        operation: Operation being performed
    """
    spinner = ["|", "/", "-", "\\"]
    spin_idx = (current - 1) % len(spinner)
    sys.stdout.write(f"\r{operation}... {spinner[spin_idx]} ({current}/{total})")
    sys.stdout.flush()
