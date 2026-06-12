"""Auth0 User Management Tool - Main Package."""

# Core functionality
# CLI
from .cli import (
    csv_main,
    handle_csv_command,
    parse_csv_args,
    print_csv_usage,
)
from .core.auth import doctor, get_access_token
from .core.config import (
    API_RATE_LIMIT,
    API_TIMEOUT,
    get_base_url,
    get_env_config,
    validate_rate_limit_config,
)
from .core.exceptions import (
    Auth0ManagerError,
    AuthConfigError,
    FileOperationError,
)

# Models
from .models.checkpoint import (
    BatchProgress,
    Checkpoint,
    CheckpointStatus,
    OperationConfig,
    OperationType,
    ProcessingResults,
)

# Operations
from .operations.batch_ops import (
    CheckpointOperationConfig,
    ExecuteCheckpointConfig,
    check_unblocked_users_with_checkpoints,
    find_users_by_social_media_ids_with_checkpoints,
)
from .operations.domain_ops import (
    check_email_domains,
    validate_domain_format,
)
from .operations.export_ops import (
    ExportWithCheckpointsConfig,
    export_users_last_login_to_csv_with_checkpoints,
)
from .operations.preview_ops import (
    PreviewResult,
    preview_social_unlink_operations,
    preview_user_operations,
)
from .operations.user_ops import (
    batch_user_operations_with_checkpoints,
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
    AUTH0_USER_ID_PREFIXES,
    check_shutdown_requested,
    clean_identifier,
    confirm_action,
    extract_identifiers_from_csv,
    find_best_column,
    get_connection_type,
    handle_shutdown,
    is_auth0_user_id,
    is_database_connection,
    is_social_connection,
    live_progress,
    parse_auth0_user_id,
    print_error,
    print_info,
    print_section_header,
    print_success,
    print_warning,
    read_user_ids,
    read_user_ids_generator,
    resolve_encoded_username,
    safe_file_read,
    safe_file_write,
    setup_signal_handlers,
    shutdown_requested,
    validate_auth0_user_id,
    validate_file_path,
    write_identifiers_to_file,
)
from .utils.checkpoint_manager import CheckpointManager
from .utils.request_utils import get_estimated_processing_time, get_optimal_batch_size

__version__ = "1.0.0"

__all__ = [
    # Core
    "get_access_token",
    "doctor",
    "get_env_config",
    "get_base_url",
    "API_RATE_LIMIT",
    "API_TIMEOUT",
    "get_optimal_batch_size",
    "get_estimated_processing_time",
    "validate_rate_limit_config",
    # Exceptions
    "Auth0ManagerError",
    "AuthConfigError",
    "FileOperationError",
    # Models
    "Checkpoint",
    "CheckpointStatus",
    "OperationType",
    "OperationConfig",
    "BatchProgress",
    "ProcessingResults",
    # Operations
    "CheckpointOperationConfig",
    "ExecuteCheckpointConfig",
    "ExportWithCheckpointsConfig",
    "block_user",
    "delete_user",
    "get_user_details",
    "get_user_email",
    "get_user_id_from_email",
    "revoke_user_grants",
    "revoke_user_sessions",
    "unlink_user_identity",
    "check_email_domains",
    "validate_domain_format",
    # Checkpoint-enabled operations
    "export_users_last_login_to_csv_with_checkpoints",
    "check_unblocked_users_with_checkpoints",
    "find_users_by_social_media_ids_with_checkpoints",
    "batch_user_operations_with_checkpoints",
    # Preview operations
    "PreviewResult",
    "preview_user_operations",
    "preview_social_unlink_operations",
    # Utilities
    "AUTH0_USER_ID_PREFIXES",
    "is_auth0_user_id",
    "validate_auth0_user_id",
    "get_connection_type",
    "is_social_connection",
    "is_database_connection",
    "parse_auth0_user_id",
    "extract_identifiers_from_csv",
    "write_identifiers_to_file",
    "find_best_column",
    "resolve_encoded_username",
    "clean_identifier",
    "safe_file_read",
    "safe_file_write",
    "validate_file_path",
    "read_user_ids",
    "read_user_ids_generator",
    "live_progress",
    "shutdown_requested",
    "handle_shutdown",
    "check_shutdown_requested",
    "setup_signal_handlers",
    "confirm_action",
    "print_error",
    "print_warning",
    "print_success",
    "print_info",
    "print_section_header",
    # Checkpoint manager
    "CheckpointManager",
    # CLI
    "csv_main",
    "parse_csv_args",
    "print_csv_usage",
    "handle_csv_command",
]
