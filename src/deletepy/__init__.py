"""Auth0 User Management Tool - DeletePy

A comprehensive tool for managing Auth0 users with bulk operations,
export capabilities, and domain validation.
"""

__version__ = "1.0.0"
__author__ = "DeletePy Team"

# Core modules
from . import core, models, operations, utils

# Configuration
from .core.config import (
    get_base_url,
    get_env_config,
    get_estimated_processing_time,
    get_optimal_batch_size,
    validate_rate_limit_config,
)

# Main operations for easy access
from .operations import (
    block_user,
    # Domain operations
    check_email_domains,
    # Batch operations
    check_unblocked_users,
    # Core user operations
    delete_user,
    # Export operations
    export_users_last_login_to_csv,
    extract_domains_from_emails,
    filter_emails_by_domain,
    find_users_by_social_media_ids,
    get_domain_statistics,
    get_user_details,
    get_user_email,
    get_user_id_from_email,
    validate_domain_format,
)

# Utility functions
from .utils import (
    confirm_action,
    make_rate_limited_request,
    safe_file_write,
    show_progress,
    shutdown_requested,
)

__all__ = [
    # Version info
    "__version__",
    "__author__",

    # Core modules
    "core",
    "operations",
    "utils",
    "models",

    # Main operations
    "delete_user",
    "block_user",
    "get_user_id_from_email",
    "get_user_email",
    "get_user_details",
    "check_unblocked_users",
    "find_users_by_social_media_ids",
    "export_users_last_login_to_csv",
    "check_email_domains",
    "validate_domain_format",
    "extract_domains_from_emails",
    "get_domain_statistics",
    "filter_emails_by_domain",

    # Utilities
    "shutdown_requested",
    "show_progress",
    "safe_file_write",
    "confirm_action",
    "make_rate_limited_request",

    # Configuration
    "get_env_config",
    "get_base_url",
    "get_optimal_batch_size",
    "get_estimated_processing_time",
    "validate_rate_limit_config",
]
