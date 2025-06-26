"""Legacy print function replacements with logging.

This module provides drop-in replacements for the existing print-based
functions to gradually migrate to structured logging while maintaining
backward compatibility.
"""

import logging
from typing import Any, Optional

from .logging_utils import get_logger

# Global logger for legacy functions
_logger = get_logger(__name__)


def print_info(message: str, **context) -> None:
    """Print info message (legacy compatibility)."""
    _logger.info(message, extra=context)


def print_success(message: str, **context) -> None:
    """Print success message (legacy compatibility)."""
    _logger.info(f"✅ {message}", extra={**context, 'status': 'success'})


def print_warning(message: str, **context) -> None:
    """Print warning message (legacy compatibility)."""
    _logger.warning(f"⚠️  {message}", extra=context)


def print_error(message: str, **context) -> None:
    """Print error message (legacy compatibility)."""
    _logger.error(f"❌ {message}", extra=context)


def print_section_header(message: str, **context) -> None:
    """Print section header (legacy compatibility)."""
    _logger.info(f"📋 {message}", extra={**context, 'section': True})


def log_user_operation(
    operation: str,
    user_id: str,
    status: str = "started",
    details: Optional[str] = None,
    **context
) -> None:
    """Log user operation with structured context.
    
    Args:
        operation: Operation being performed (delete, block, etc.)
        user_id: Auth0 user ID
        status: Operation status (started, completed, failed)
        details: Additional details about the operation
        **context: Additional context fields
    """
    operation_context = {
        'operation': operation,
        'user_id': user_id,
        'status': status,
        **context
    }
    
    if status == "started":
        message = f"Starting {operation} for user {user_id}"
        _logger.info(message, extra=operation_context)
    elif status == "completed":
        message = f"Successfully completed {operation} for user {user_id}"
        if details:
            message += f": {details}"
        _logger.info(message, extra=operation_context)
    elif status == "failed":
        message = f"Failed {operation} for user {user_id}"
        if details:
            message += f": {details}"
        _logger.error(message, extra=operation_context)
    else:
        message = f"{operation} for user {user_id}: {status}"
        if details:
            message += f" - {details}"
        _logger.info(message, extra=operation_context)


def log_api_request(
    method: str,
    endpoint: str,
    status_code: Optional[int] = None,
    duration: Optional[float] = None,
    error: Optional[str] = None,
    **context
) -> None:
    """Log API request with structured context.
    
    Args:
        method: HTTP method (GET, POST, DELETE, etc.)
        endpoint: API endpoint
        status_code: HTTP status code
        duration: Request duration in seconds
        error: Error message if request failed
        **context: Additional context fields
    """
    api_context = {
        'method': method,
        'api_endpoint': endpoint,
        **context
    }
    
    if status_code:
        api_context['status_code'] = status_code
    if duration:
        api_context['duration'] = duration
    
    if error:
        message = f"API {method} {endpoint} failed: {error}"
        _logger.error(message, extra=api_context)
    elif status_code and status_code >= 400:
        message = f"API {method} {endpoint} returned {status_code}"
        _logger.warning(message, extra=api_context)
    else:
        message = f"API {method} {endpoint}"
        if status_code:
            message += f" returned {status_code}"
        if duration:
            message += f" in {duration:.3f}s"
        _logger.info(message, extra=api_context)


def log_file_operation(
    operation: str,
    file_path: str,
    status: str = "completed",
    details: Optional[str] = None,
    **context
) -> None:
    """Log file operation with structured context.
    
    Args:
        operation: File operation (read, write, delete, etc.)
        file_path: Path to the file
        status: Operation status
        details: Additional details
        **context: Additional context fields
    """
    file_context = {
        'operation': operation,
        'file_path': file_path,
        'status': status,
        **context
    }
    
    message = f"File {operation}: {file_path}"
    if details:
        message += f" - {details}"
    
    if status == "failed":
        _logger.error(message, extra=file_context)
    elif status == "warning":
        _logger.warning(message, extra=file_context)
    else:
        _logger.info(message, extra=file_context)


def log_progress(
    current: int,
    total: int,
    operation: str = "Processing",
    **context
) -> None:
    """Log progress information.
    
    Args:
        current: Current item number
        total: Total number of items
        operation: Operation being performed
        **context: Additional context fields
    """
    percentage = (current / total * 100) if total > 0 else 0
    progress_context = {
        'operation': operation,
        'current': current,
        'total': total,
        'percentage': percentage,
        **context
    }
    
    # Only log every 10% or at significant milestones
    if current == 1 or current == total or percentage % 10 == 0:
        message = f"{operation}: {current}/{total} ({percentage:.1f}%)"
        _logger.info(message, extra=progress_context)


def log_batch_operation(
    operation: str,
    batch_size: int,
    total_items: int,
    estimated_time: Optional[float] = None,
    **context
) -> None:
    """Log batch operation start with parameters.
    
    Args:
        operation: Batch operation name
        batch_size: Size of each batch
        total_items: Total number of items to process
        estimated_time: Estimated processing time in minutes
        **context: Additional context fields
    """
    batch_context = {
        'operation': operation,
        'batch_size': batch_size,
        'total_items': total_items,
        'batches_total': (total_items + batch_size - 1) // batch_size,
        **context
    }
    
    if estimated_time:
        batch_context['estimated_time_minutes'] = estimated_time
    
    message = f"Starting batch {operation}: {total_items} items in batches of {batch_size}"
    if estimated_time:
        message += f" (estimated time: {estimated_time:.1f} minutes)"
    
    _logger.info(message, extra=batch_context)