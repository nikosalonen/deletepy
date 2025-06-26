"""Utilities module for Auth0 user management."""

# Display utilities
# CSV utilities
from .csv_utils import (
    AUTH0_USER_ID_PREFIXES,
    clean_identifier,
    extract_identifiers_from_csv,
    find_best_column,
    is_auth0_user_id,
    resolve_encoded_username,
    write_identifiers_to_file,
)
from .display_utils import (
    CYAN,
    GREEN,
    RED,
    RESET,
    YELLOW,
    confirm_action,
    print_error,
    print_info,
    print_section_header,
    print_success,
    print_warning,
    show_progress,
    shutdown_requested,
)

# File utilities
from .file_utils import (
    FileOperationError,
    check_shutdown_requested,
    handle_shutdown,
    read_user_ids,
    read_user_ids_generator,
    safe_file_copy,
    safe_file_delete,
    safe_file_move,
    safe_file_read,
    safe_file_write,
    setup_signal_handlers,
    validate_file_path,
)

# Request utilities
from .request_utils import (
    get_json_response,
    make_rate_limited_request,
    make_simple_request,
    validate_response,
)

__all__ = [
    # Display utilities
    "RED",
    "GREEN",
    "YELLOW",
    "CYAN",
    "RESET",
    "shutdown_requested",
    "show_progress",
    "confirm_action",
    "print_section_header",
    "print_warning",
    "print_error",
    "print_success",
    "print_info",

    # Request utilities
    "make_rate_limited_request",
    "make_simple_request",
    "validate_response",
    "get_json_response",

    # File utilities
    "FileOperationError",
    "safe_file_read",
    "safe_file_write",
    "safe_file_copy",
    "safe_file_move",
    "safe_file_delete",
    "validate_file_path",
    "read_user_ids",
    "read_user_ids_generator",
    "setup_signal_handlers",
    "handle_shutdown",
    "check_shutdown_requested",

    # CSV utilities
    "AUTH0_USER_ID_PREFIXES",
    "is_auth0_user_id",
    "find_best_column",
    "resolve_encoded_username",
    "clean_identifier",
    "extract_identifiers_from_csv",
    "write_identifiers_to_file",
]
