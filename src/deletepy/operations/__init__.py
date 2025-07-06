"""Operations module for Auth0 user management."""

# Core user operations
# Batch operations
from .batch_ops import (
    check_unblocked_users,
    find_users_by_social_media_ids,
)

# Domain operations
from .domain_ops import (
    check_email_domains,
    extract_domains_from_emails,
    filter_emails_by_domain,
    get_domain_statistics,
    validate_domain_format,
)

# Export operations
from .export_ops import (
    export_users_last_login_to_csv,
)
from .user_ops import (
    block_user,
    delete_user,
    get_user_details,
    get_user_email,
    get_user_id_from_email,
    revoke_user_grants,
    revoke_user_sessions,
    unlink_user_identity,
)

# Validation operations
from .validation_ops import (
    SmartValidator,
    ValidationResult,
    ValidationWarning,
    display_validation_results,
    get_validation_level_description,
)

__all__ = [
    # Core user operations
    "delete_user",
    "block_user",
    "get_user_id_from_email",
    "get_user_email",
    "get_user_details",
    "revoke_user_sessions",
    "revoke_user_grants",
    "unlink_user_identity",
    # Batch operations
    "check_unblocked_users",
    "find_users_by_social_media_ids",
    # Export operations
    "export_users_last_login_to_csv",
    # Domain operations
    "check_email_domains",
    "validate_domain_format",
    "extract_domains_from_emails",
    "get_domain_statistics",
    "filter_emails_by_domain",
    # Validation operations
    "SmartValidator",
    "ValidationResult",
    "ValidationWarning",
    "display_validation_results",
    "get_validation_level_description",
]
