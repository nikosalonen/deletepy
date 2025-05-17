import sys
import signal
import argparse
from typing import List, Tuple, Generator

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
    sys.stdout.write("\r" + " " * 80 + "\r")
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
    except FileNotFoundError:
        raise FileNotFoundError(f"Error: File {filepath} not found")
    except IOError as e:
        raise IOError(f"Error reading file: {e}")

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
        raise FileNotFoundError(f"Error: File {filepath} not found")
    except IOError as e:
        raise IOError(f"Error reading file: {e}")

def validate_args() -> argparse.Namespace:
    """Parse and validate command line arguments.
    
    Returns:
        argparse.Namespace: Parsed arguments containing:
            - input_file: Path to the file containing user IDs
            - env: Environment to run in ('dev' or 'prod')
            - operation: The operation to perform (block/delete/revoke-grants-only/check-unblocked/check-domains)
    """
    parser = argparse.ArgumentParser(
        description="Process user operations based on IDs from a file.",
        usage="python main.py <ids_file> [env] [--block|--delete|--revoke-grants-only|--check-unblocked|--check-domains]"
    )
    
    parser.add_argument(
        "input_file",
        help="Path to the file containing user IDs"
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
    
    args = parser.parse_args()
    return args 