"""Auth0 User Management Tool - Main Package."""

# Core functionality
# CLI commands
from .cli import (
    csv_main,
    parse_csv_arguments,
    print_csv_usage,
    process_csv_file,
    validate_auth0_user_id,
)
from .core.auth import get_access_token
from .core.config import get_base_url
from .operations.batch_ops import (
    check_unblocked_users,
    find_users_by_social_media_ids,
)
from .operations.domain_ops import (
    check_email_domains,
    extract_domains_from_emails,
    filter_emails_by_domain,
    get_domain_statistics,
    validate_domain_format,
)
from .operations.export_ops import (
    export_users_last_login_to_csv,
)

# Operations
from .operations.user_ops import (
    block_user,
    delete_user,
    get_user_details,
    get_user_email,
    get_user_id_from_email,
    revoke_user_grants,
    revoke_user_sessions,
    unlink_user_identity,
)

# Utilities
from .utils import (
    # CSV utilities
    AUTH0_USER_ID_PREFIXES,
    CYAN,
    GREEN,
    # Display utilities
    RED,
    RESET,
    YELLOW,
    # File utilities
    FileOperationError,
    check_shutdown_requested,
    clean_identifier,
    confirm_action,
    extract_identifiers_from_csv,
    find_best_column,
    get_json_response,
    handle_shutdown,
    is_auth0_user_id,
    # Request utilities
    make_rate_limited_request,
    make_simple_request,
    print_error,
    print_info,
    print_section_header,
    print_success,
    print_warning,
    read_user_ids,
    read_user_ids_generator,
    resolve_encoded_username,
    safe_file_copy,
    safe_file_delete,
    safe_file_move,
    safe_file_read,
    safe_file_write,
    setup_signal_handlers,
    show_progress,
    shutdown_requested,
    validate_file_path,
    validate_response,
    write_identifiers_to_file,
)

__version__ = "1.0.0"

__all__ = [
    # Core
    "get_access_token",
    "get_base_url",

    # User operations
    "delete_user",
    "block_user",
    "get_user_details",
    "get_user_email",
    "get_user_id_from_email",
    "revoke_user_grants",
    "revoke_user_sessions",
    "unlink_user_identity",

    # Batch operations
    "check_unblocked_users",
    "find_users_by_social_media_ids",

    # Export operations
    "export_users_last_login_to_csv",

    # Domain operations
    "check_email_domains",
    "extract_domains_from_emails",
    "filter_emails_by_domain",
    "get_domain_statistics",
    "validate_domain_format",

    # Display utilities
    "RED",
    "GREEN",
    "YELLOW",
    "CYAN",
    "RESET",
    "print_error",
    "print_info",
    "print_success",
    "print_warning",
    "print_section_header",
    "show_progress",
    "confirm_action",
    "shutdown_requested",

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

    # CLI commands
    "csv_main",
    "parse_csv_arguments",
    "print_csv_usage",
    "process_csv_file",
    "validate_auth0_user_id",
]
