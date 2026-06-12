"""Output utilities with structured logging support.

This module provides the canonical print functions for user output that integrate
with the structured logging system. All print_* functions go through the logging
infrastructure for proper formatting and optional structured output.

The logging system uses RichHandler when available for pretty console output.
For additional Rich formatting (tables, panels, summaries), use rich_utils directly.

Functions:
    print_info: Print informational messages
    print_success: Print success messages
    print_warning: Print warning messages
    print_error: Print error messages
    print_section_header: Print section headers
    log_*: Additional structured logging helpers
"""

from typing import Any

from .logging_utils import get_logger

# Global logger for legacy functions
_logger = get_logger(__name__)


def print_info(message: str, **context: Any) -> None:
    """Print info message (legacy compatibility)."""
    _logger.info(message, extra=context)


def print_success(message: str, **context: Any) -> None:
    """Print success message (legacy compatibility)."""
    _logger.info(f"✅ {message}", extra={**context, "status": "success"})


def print_warning(message: str, **context: Any) -> None:
    """Print warning message (legacy compatibility)."""
    _logger.warning(f"⚠️  {message}", extra=context)


def print_error(message: str, **context: Any) -> None:
    """Print error message (legacy compatibility)."""
    _logger.error(f"❌ {message}", extra=context)


def print_section_header(message: str, **context: Any) -> None:
    """Print section header (legacy compatibility)."""
    _logger.info(f"📋 {message}", extra={**context, "section": True})
