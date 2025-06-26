"""Display utilities for user interaction and progress display."""

import signal
import sys

# Color constants for terminal output
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"

# Global flag for shutdown requests
_shutdown_requested = False


def setup_shutdown_handler():
    """Setup signal handlers for graceful shutdown."""
    def signal_handler(signum, frame):
        global _shutdown_requested
        _shutdown_requested = True
        print(f"\n{YELLOW}Shutdown requested. Finishing current operation...{RESET}")

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


def shutdown_requested() -> bool:
    """Check if shutdown has been requested."""
    return _shutdown_requested


def show_progress(current: int, total: int, operation: str = "Processing") -> None:
    """Display a progress bar.

    Args:
        current: Current item number (1-based)
        total: Total number of items
        operation: Description of the operation being performed
    """
    if total == 0:
        return

    percentage = (current / total) * 100
    bar_length = 30
    filled_length = int(bar_length * current // total)

    bar = "█" * filled_length + "░" * (bar_length - filled_length)

    # Clear the line and show progress
    sys.stdout.write(f"\r{operation}: [{bar}] {percentage:.1f}% ({current}/{total})")
    sys.stdout.flush()

    if current == total:
        print()  # New line when complete


def safe_file_write(file_path: str, content: str, backup: bool = True) -> bool:
    """Safely write content to a file with optional backup.

    Args:
        file_path: Path to the file to write
        content: Content to write to the file
        backup: Whether to create a backup of existing file

    Returns:
        bool: True if successful, False otherwise
    """
    import os
    import shutil
    from datetime import datetime

    try:
        # Create backup if file exists and backup is requested
        if backup and os.path.exists(file_path):
            backup_path = f"{file_path}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            shutil.copy2(file_path, backup_path)

        # Write new content
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)

        return True

    except Exception as e:
        print(f"{RED}Error writing file {file_path}: {e}{RESET}")
        return False


def confirm_action(message: str, default: bool = False) -> bool:
    """Ask user for confirmation.

    Args:
        message: Message to display
        default: Default answer if user just presses Enter

    Returns:
        bool: True if confirmed, False otherwise
    """
    default_str = "Y/n" if default else "y/N"
    response = input(f"{message} ({default_str}): ").strip().lower()

    if not response:
        return default

    return response in ['y', 'yes', 'true', '1']


def print_section_header(title: str) -> None:
    """Print a formatted section header.

    Args:
        title: Section title
    """
    print(f"\n{CYAN}{'=' * 60}{RESET}")
    print(f"{CYAN}{title.center(60)}{RESET}")
    print(f"{CYAN}{'=' * 60}{RESET}")


def print_warning(message: str) -> None:
    """Print a warning message.

    Args:
        message: Warning message
    """
    print(f"{YELLOW}WARNING: {message}{RESET}")


def print_error(message: str) -> None:
    """Print an error message.

    Args:
        message: Error message
    """
    print(f"{RED}ERROR: {message}{RESET}")


def print_success(message: str) -> None:
    """Print a success message.

    Args:
        message: Success message
    """
    print(f"{GREEN}SUCCESS: {message}{RESET}")


def print_info(message: str) -> None:
    """Print an info message.

    Args:
        message: Info message
    """
    print(f"{CYAN}INFO: {message}{RESET}")


class FileOperationError(Exception):
    """Exception raised for file operation errors."""
    pass
