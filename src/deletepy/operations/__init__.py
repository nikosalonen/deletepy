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

# Preview operations
from .preview_ops import (
    PreviewResult,
    preview_social_unlink_operations,
    preview_user_operations,
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
    # Preview operations
    "PreviewResult",
    "preview_user_operations",
    "preview_social_unlink_operations",
    # Domain operations
    "check_email_domains",
    "validate_domain_format",
    "extract_domains_from_emails",
    "get_domain_statistics",
    "filter_emails_by_domain",
]
