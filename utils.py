import sys
import signal
from typing import List, Tuple

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
    """Read user IDs from file."""
    try:
        with open(filepath, 'r') as f:
            return [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        sys.exit(f"Error: File {filepath} not found")
    except IOError as e:
        sys.exit(f"Error reading file: {e}")

def validate_args() -> Tuple[str, str, bool, bool, bool, bool, bool]:
    """Validate command line arguments and return input file path, environment, and operation flags."""
    if len(sys.argv) < 2:
        sys.exit("Usage: python main.py <ids_file> [env] [--block|--delete|--revoke-grants-only|--check-unblocked|--check-domains]")
    
    input_file = sys.argv[1]
    env = "dev"
    block = False
    delete = False
    revoke_grants_only = False
    check_unblocked = False
    check_domains = False
    
    for arg in sys.argv[2:]:
        if arg == "--block":
            block = True
        elif arg == "--delete":
            delete = True
        elif arg == "--revoke-grants-only":
            revoke_grants_only = True
        elif arg == "--check-unblocked":
            check_unblocked = True
        elif arg == "--check-domains":
            check_domains = True
        elif arg in ("dev", "prod"):
            env = arg
    
    flags = [block, delete, revoke_grants_only, check_unblocked, check_domains]
    if not any(flags):
        sys.exit("Error: You must specify one of --block, --delete, --revoke-grants-only, --check-unblocked, or --check-domains.")
    if sum(flags) > 1:
        sys.exit("Error: Only one of --block, --delete, --revoke-grants-only, --check-unblocked, or --check-domains can be specified.")
    
    return input_file, env, block, delete, revoke_grants_only, check_unblocked, check_domains 