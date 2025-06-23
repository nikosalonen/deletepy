import sys
import signal
import argparse
import re
from typing import List, Generator

# ANSI color codes
RESET = "\033[0m"
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"

# Graceful shutdown handler
shutdown_requested = False

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
    """Read user IDs from file.

    Args:
        filepath: Path to the file containing user IDs

    Returns:
        List[str]: List of user IDs read from the file

    Raises:
        FileNotFoundError: If the specified file does not exist
        IOError: If there is an error reading the file
    """
    try:
        with open(filepath, 'r') as f:
            # Use a generator expression to read line by line
            return [line.strip() for line in f if line.strip()]
    except FileNotFoundError as e:
        raise FileNotFoundError(f"Error: File {filepath} not found") from e
    except IOError as e:
        raise IOError(f"Error reading file: {e}") from e

def read_user_ids_generator(filepath: str) -> Generator[str, None, None]:
    """Read user IDs from file using a generator pattern.

    Args:
        filepath: Path to the file containing user IDs

    Yields:
        str: User ID from the file

    Raises:
        FileNotFoundError: If the specified file does not exist
        IOError: If there is an error reading the file
    """
    try:
        with open(filepath, 'r') as f:
            for line in f:
                line = line.strip()
                if line:  # Skip empty lines
                    yield line
    except FileNotFoundError:
        raise FileNotFoundError(f"Error: File {filepath} not found") from None
    except IOError as e:
        raise IOError(f"Error reading file: {e}") from e

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
        usage="python main.py <ids_file> [env] [--block|--delete|--revoke-grants-only|--check-unblocked|--check-domains|--doctor]"
    )

    parser.add_argument(
        "input_file",
        nargs="?",
        help="Path to the file containing user IDs (not required for --doctor)"
    )

    parser.add_argument(
        "env",
        nargs="?",
        choices=["dev", "prod"],
        default="dev",
        help="Environment to run in (default: dev)"
    )

    operation_group = parser.add_mutually_exclusive_group(required=True)
    operation_group.add_argument(
        "--block",
        action="store_const",
        const="block",
        dest="operation",
        help="Block the specified users"
    )
    operation_group.add_argument(
        "--delete",
        action="store_const",
        const="delete",
        dest="operation",
        help="Delete the specified users"
    )
    operation_group.add_argument(
        "--revoke-grants-only",
        action="store_const",
        const="revoke-grants-only",
        dest="operation",
        help="Revoke grants for the specified users"
    )
    operation_group.add_argument(
        "--check-unblocked",
        action="store_const",
        const="check-unblocked",
        dest="operation",
        help="Check if specified users are unblocked"
    )
    operation_group.add_argument(
        "--check-domains",
        action="store_const",
        const="check-domains",
        dest="operation",
        help="Check domains for the specified users"
    )
    operation_group.add_argument(
        "--export-last-login",
        action="store_const",
        const="export-last-login",
        dest="operation",
        help="Export user last_login data to CSV"
    )
    operation_group.add_argument(
        "--doctor",
        action="store_const",
        const="doctor",
        dest="operation",
        help="Test if credentials work"
    )

    parser.add_argument(
        "--test-api",
        action="store_true",
        help="Test API access when using --doctor (optional)"
    )

    parser.add_argument(
        "--connection",
        type=str,
        help="Filter users by connection type (e.g., 'google-oauth2', 'auth0', 'facebook')"
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
    pattern = r'^[a-zA-Z0-9\-]+\|[a-zA-Z0-9]+$'
    return bool(re.match(pattern, user_id))

def show_progress(current: int, total: int, operation: str) -> None:
    """Show progress indicator for bulk operations.

    Args:
        current: Current item number
        total: Total number of items
        operation: Operation being performed
    """
    spinner = ['|', '/', '-', '\\']
    spin_idx = (current - 1) % len(spinner)
    sys.stdout.write(f"\r{operation}... {spinner[spin_idx]} ({current}/{total})")
    sys.stdout.flush()
