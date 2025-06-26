"""Utilities module for Auth0 user management."""

from .auth_utils import (
    AUTH0_USER_ID_PREFIXES,
    get_connection_type,
    is_auth0_user_id,
    is_database_connection,
    is_social_connection,
    parse_auth0_user_id,
    validate_auth0_user_id,
)
from .csv_utils import (
    _check_if_data_available,
    _convert_single_identifier,
    _convert_to_output_type,
    _detect_file_type,
    _extract_output_value,
    _handle_conversion,
    _needs_conversion,
    _process_csv_file,
    _process_plain_text,
    _search_user_by_field,
    _should_skip_resolution,
    clean_identifier,
    extract_identifiers_from_csv,
    find_best_column,
    resolve_encoded_username,
    write_identifiers_to_file,
)
from ..core.exceptions import FileOperationError
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
    setup_signal_handlers,
    validate_file_path,
)
from .file_utils import (
    safe_file_write as safe_write,
)

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
    # CSV utilities
    "_check_if_data_available",
    "_convert_single_identifier",
    "_convert_to_output_type",
    "_detect_file_type",
    "_extract_output_value",
    "_handle_conversion",
    "_needs_conversion",
    "_process_csv_file",
    "_process_plain_text",
    "_search_user_by_field",
    "_should_skip_resolution",
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
]
