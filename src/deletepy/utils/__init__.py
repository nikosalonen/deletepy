"""Utilities module for Auth0 user management."""

from ..core.exceptions import FileOperationError
from .auth_utils import (
    AUTH0_USER_ID_PREFIXES,
    get_connection_type,
    is_auth0_user_id,
    is_database_connection,
    is_social_connection,
    parse_auth0_user_id,
    validate_auth0_user_id,
)
from .checkpoint_manager import CheckpointManager
from .csv_utils import (
    clean_identifier,
    extract_identifiers_from_csv,
    find_best_column,
    resolve_encoded_username,
    write_identifiers_to_file,
)
from .display_utils import (
    confirm_action,
    print_error,
    print_info,
    print_section_header,
    print_success,
    print_warning,
    safe_file_write,
    setup_shutdown_handler,
    show_progress,
    shutdown_requested,
)
from .file_utils import (
    check_shutdown_requested,
    handle_shutdown,
    read_user_ids,
    read_user_ids_generator,
    safe_file_copy,
    safe_file_delete,
    safe_file_move,
    safe_file_read,
)
from .file_utils import setup_signal_handlers, validate_file_path
from .legacy_print import (
    log_api_request,
    log_batch_operation,
    log_file_operation,
    log_progress,
    log_user_operation,
)
from .logging_utils import get_logger, log_operation, setup_logging

# FileOperationError is imported from core.exceptions above

__all__ = [
    # Auth utilities
    "AUTH0_USER_ID_PREFIXES",
    "get_connection_type",
    "is_auth0_user_id",
    "is_database_connection",
    "is_social_connection",
    "parse_auth0_user_id",
    "validate_auth0_user_id",
    # Checkpoint utilities
    "CheckpointManager",
    # CSV utilities
    "clean_identifier",
    "extract_identifiers_from_csv",
    "find_best_column",
    "resolve_encoded_username",
    "write_identifiers_to_file",
    # Display utilities
    "confirm_action",
    "print_error",
    "print_info",
    "print_section_header",
    "print_success",
    "print_warning",
    "setup_shutdown_handler",
    "shutdown_requested",
    "show_progress",
    # File utilities
    "check_shutdown_requested",
    "handle_shutdown",
    "read_user_ids",
    "read_user_ids_generator",
    "safe_file_copy",
    "safe_file_delete",
    "safe_file_move",
    "safe_file_read",
    "safe_file_write",
    "setup_signal_handlers",
    "validate_file_path",
    # Exceptions
    "FileOperationError",
    # Logging utilities
    "get_logger",
    "setup_logging",
    "log_operation",
    "log_api_request",
    "log_batch_operation",
    "log_file_operation",
    "log_progress",
    "log_user_operation",
]
