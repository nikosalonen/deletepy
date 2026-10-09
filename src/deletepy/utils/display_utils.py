"""Display utilities for user interaction and progress display.

This module provides:
- Terminal color constants
- Progress bar display (including live_progress context manager)
- Graceful shutdown handling
- User confirmation prompts
- Backward-compatible re-exports from output module
"""

import logging
import os
import signal
import sys
import threading
from collections.abc import Callable, Generator
from contextlib import contextmanager
from types import FrameType
from typing import Protocol

# Re-export print functions from output module for backward compatibility
from .output import (
    print_error,
    print_info,
    print_section_header,
    print_success,
    print_warning,
)

# Get logger for this module - using standard logging to avoid circular import
logger = logging.getLogger("deletepy.utils.display_utils")

# =============================================================================
# Terminal Color Constants
# =============================================================================

RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"


def _supports_ansi() -> bool:
    """Check if the terminal supports ANSI escape sequences.

    Returns:
        True if ANSI sequences are supported, False otherwise.
    """
    import os

    # Check for dumb terminal
    if os.environ.get("TERM", "") == "dumb":
        return False

    # Check if stdout is a TTY
    if not sys.stdout.isatty():
        return False

    return True


# =============================================================================
# Shutdown Handling
# =============================================================================

# Global flag for shutdown requests
_shutdown_requested = False


def setup_shutdown_handler() -> None:
    """Setup signal handlers for graceful shutdown."""
    from .logging_utils import get_logger

    logger = get_logger(__name__)

    def signal_handler(signum: int, frame: FrameType | None) -> None:
        global _shutdown_requested
        _shutdown_requested = True
        # Use logging instead of raw print for better tracking
        logger.warning(
            "⚠️  Shutdown requested. Finishing current operation...",
            extra={"signal": signal.Signals(signum).name, "operation": "shutdown"},
        )

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


def shutdown_requested() -> bool:
    """Check if shutdown has been requested."""
    return _shutdown_requested


def _write_notice(message: bytes) -> None:
    """Write a notice to stderr from inside a signal handler.

    os.write, not print or logging: the signal can land while the main thread
    is writing to the same buffered stream, and a buffered write from here
    would then raise "reentrant call" and turn the stop into a failure.
    """
    try:
        os.write(2, message)
    except OSError:
        pass


def _request_shutdown(signum: int, frame: FrameType | None) -> None:
    """Signal handler: the first signal asks to stop, the second stops now."""
    global _shutdown_requested
    if _shutdown_requested:
        raise KeyboardInterrupt
    _shutdown_requested = True
    _write_notice(
        b"\nShutdown requested. Finishing the current user, then saving the "
        b"checkpoint. Press Ctrl-C again to stop immediately.\n"
    )


def _defer_shutdown(signum: int, frame: FrameType | None) -> None:
    """Signal handler: note the signal and let the current step finish."""
    _write_notice(
        b"\nAll users are processed and saved. Finishing the summary, then exiting.\n"
    )


@contextmanager
def _signal_handlers(
    handler: Callable[[int, FrameType | None], None],
) -> Generator[None, None, None]:
    """Install handler for SIGINT and SIGTERM, and restore the previous ones."""
    # signal.signal() only works in the main thread.
    if threading.current_thread() is not threading.main_thread():
        yield
        return

    previous_sigint = signal.signal(signal.SIGINT, handler)
    previous_sigterm = signal.signal(signal.SIGTERM, handler)
    try:
        yield
    finally:
        signal.signal(signal.SIGINT, previous_sigint)
        signal.signal(signal.SIGTERM, previous_sigterm)


@contextmanager
def graceful_shutdown() -> Generator[None, None, None]:
    """Turn the first Ctrl-C or SIGTERM into a shutdown request.

    Inside the block, loops that check shutdown_requested() stop at a safe
    point and save their checkpoint. A second signal raises KeyboardInterrupt,
    so a stuck run can still be stopped. The previous handlers and the flag
    are restored on exit, so prompts outside the block keep normal Ctrl-C.
    """
    global _shutdown_requested

    _shutdown_requested = False
    try:
        with _signal_handlers(_request_shutdown):
            yield
    finally:
        _shutdown_requested = False


@contextmanager
def deferred_shutdown() -> Generator[None, None, None]:
    """Hold off Ctrl-C and SIGTERM until a short, must-finish step is done.

    Use it for work that runs after everything is saved, such as the final
    summary. Stopping there would only cut the report short, so a signal
    inside the block prints a notice and the block runs to the end. The
    caller then returns as normal, so the process still exits soon after.
    """
    with _signal_handlers(_defer_shutdown):
        yield


# =============================================================================
# Progress Display
# =============================================================================

# Try to import Rich for prettier progress bars
try:
    from rich.progress import (
        BarColumn,
        MofNCompleteColumn,
        Progress,
        SpinnerColumn,
        TaskProgressColumn,
        TextColumn,
        TimeRemainingColumn,
    )

    _RICH_PROGRESS_AVAILABLE = True
except ImportError:
    _RICH_PROGRESS_AVAILABLE = False


def clear_progress_line() -> None:
    """Clear the current progress line and ensure clean output state.

    Call this before any log output that follows a progress bar to avoid
    text corruption from mixed stdout/stderr output.

    Uses ANSI erase-to-end-of-line sequence when supported, falls back to
    fixed-space overwrite for dumb terminals.
    """
    if _supports_ansi():
        # Use ANSI escape: carriage return + erase to end of line
        sys.stdout.write("\r\x1b[K")
    else:
        # Fallback: clear with spaces (assuming max 100 char progress bar)
        sys.stdout.write("\r" + " " * 100 + "\r")
    sys.stdout.flush()
    # Also flush stderr to ensure proper ordering
    sys.stderr.flush()


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
        # Clear the progress line and move to next line
        clear_progress_line()
        print()  # New line when complete


class _AdvanceCallable(Protocol):
    def __call__(self, step: int = 1) -> None: ...


@contextmanager
def live_progress(
    total: int, operation: str = "Processing"
) -> Generator[_AdvanceCallable, None, None]:
    """Context manager for a live Rich progress bar pinned to the bottom.

    Log messages (via RichHandler on the shared stderr console) automatically
    scroll above the progress bar while it is active.

    Falls back to the ASCII ``show_progress`` when Rich is not available.

    Args:
        total: Total number of items to process.
        operation: Label shown next to the progress bar.

    Yields:
        A callable ``advance(step=1)`` to increment the progress bar.

    Example::

        with live_progress(len(items), "Deleting users") as advance:
            for item in items:
                process(item)
                advance()
    """
    if total == 0:
        yield lambda step=1: None
        return

    if not _RICH_PROGRESS_AVAILABLE:
        counter = {"current": 0}

        def _ascii_advance(step: int = 1) -> None:
            counter["current"] += step
            show_progress(counter["current"], total, operation)

        try:
            yield _ascii_advance
        finally:
            clear_progress_line()
        return

    from .rich_utils import get_stderr_console

    progress = Progress(
        SpinnerColumn(),
        TextColumn(f"[bold blue]{operation}"),
        BarColumn(bar_width=30),
        TaskProgressColumn(),
        MofNCompleteColumn(),
        TimeRemainingColumn(),
        console=get_stderr_console(),
    )
    with progress:
        task_id = progress.add_task("", total=total)
        yield lambda step=1: progress.advance(task_id, advance=step)


# =============================================================================
# User Confirmation
# =============================================================================


def confirm_action(message: str, default: bool = False) -> bool:
    """Ask user for confirmation.

    Args:
        message: Message to display
        default: Default answer if user just presses Enter

    Returns:
        bool: True if confirmed, False otherwise
    """
    default_str = "Y/n" if default else "y/N"
    from .validators import SecurityValidator

    raw_response = input(f"{message} ({default_str}): ")
    response = SecurityValidator.sanitize_user_input(raw_response).lower()

    if not response:
        return default

    return response in ["y", "yes", "true", "1"]


def confirm_production_operation(
    operation: str,
    total_users: int,
    rotate_password: bool = False,
    force_otp: bool = False,
) -> bool:
    """Confirm operation in production environment.

    Args:
        operation: The operation to be performed
        total_users: Total number of users to be processed
        rotate_password: Whether password rotation is enabled
        force_otp: Whether the requiresAdditionalVerification flag will be set

    Returns:
        bool: True if confirmed, False otherwise

    Raises:
        ValueError: If operation is empty or total_users is not positive
        TypeError: If parameters are not of expected types
    """
    if not isinstance(operation, str):
        raise TypeError(f"Operation must be a string, got {type(operation).__name__}")

    if not isinstance(total_users, int):
        raise TypeError(
            f"Total users must be an integer, got {type(total_users).__name__}"
        )

    from .validators import SecurityValidator

    if not operation:
        raise ValueError("Operation cannot be empty")

    # Sanitize the operation input
    sanitized_operation = SecurityValidator.sanitize_user_input(operation)
    if not sanitized_operation:
        raise ValueError("Operation contains invalid characters")

    if total_users <= 0:
        raise ValueError(f"Total users must be a positive integer, got {total_users}")

    operation_details = {
        "block": {
            "action": "blocking",
            "consequence": "This will prevent users from logging in and revoke all their active sessions and application grants.",
        },
        "delete": {
            "action": "deleting",
            "consequence": "This will permanently remove users from Auth0, including all their data, sessions, and application grants.",
        },
        "revoke-grants-only": {
            "action": "revoking grants for",
            "consequence": "This will invalidate all refresh tokens and prevent applications from obtaining new access tokens for these users.",
        },
        "unlink-social-ids": {
            "action": "processing social media identities for",
            "consequence": "This will delete users with single social identities and unlink social identities from users with multiple identities.",
        },
    }.get(
        operation,
        {
            "action": "processing",
            "consequence": "This operation will affect user data in the production environment.",
        },
    )

    print(
        f"\nYou are about to perform {operation_details['action']} {total_users} users in PRODUCTION environment."
    )
    print(f"Consequence: {operation_details['consequence']}")

    if rotate_password:
        print(
            f"{YELLOW}WARNING: Password rotation is enabled. This will invalidate current user credentials.{RESET}"
        )

    if force_otp:
        print(
            f"{YELLOW}WARNING: --force-otp is enabled. This will set "
            f"app_metadata.requiresAdditionalVerification=true on each user.{RESET}"
        )

    print("This action cannot be undone.")
    from .validators import SecurityValidator

    raw_response = input("Are you sure you want to proceed? (yes/no): ")
    response = SecurityValidator.sanitize_user_input(raw_response).lower()
    return response == "yes"


# =============================================================================
# Module Exports
# =============================================================================

__all__ = [
    # Terminal colors
    "RED",
    "GREEN",
    "YELLOW",
    "CYAN",
    "RESET",
    # Shutdown handling
    "setup_shutdown_handler",
    "shutdown_requested",
    "graceful_shutdown",
    "deferred_shutdown",
    # Progress display
    "live_progress",
    # User confirmation
    "confirm_action",
    "confirm_production_operation",
    # Re-exported from output module
    "print_error",
    "print_info",
    "print_section_header",
    "print_success",
    "print_warning",
]
