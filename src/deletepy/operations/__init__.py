"""Operations module for Auth0 user management."""

# Core user operations
# Batch operations
from deletepy.operations.batch_ops import CheckpointOperationConfig

# Domain operations
from deletepy.operations.domain_ops import (
    check_email_domains,
    extract_domains_from_emails,
    filter_emails_by_domain,
    get_domain_statistics,
    validate_domain_format,
)

# Export operations
# Preview operations
from deletepy.operations.preview_ops import (
    PreviewResult,
    preview_social_unlink_operations,
    preview_user_operations,
)
from deletepy.operations.user_ops import (
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
    "CheckpointOperationConfig",
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
