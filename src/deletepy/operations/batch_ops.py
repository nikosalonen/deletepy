"""Batch processing operations for Auth0 user management."""

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import requests

from ..core.config import API_RATE_LIMIT, API_TIMEOUT
from ..models.checkpoint import (
    Checkpoint,
    CheckpointStatus,
    OperationType,
)
from ..utils.checkpoint_manager import CheckpointManager
from ..utils.checkpoint_utils import CheckpointConfig, load_or_create_checkpoint
from ..utils.checkpoint_utils import handle_checkpoint_error as _handle_checkpoint_error
from ..utils.checkpoint_utils import (
    handle_checkpoint_interruption as _handle_checkpoint_interruption,
)
from ..utils.display_utils import live_progress, shutdown_requested
from ..utils.output import print_error, print_info, print_success, print_warning
from ..utils.url_utils import secure_url_encode
from ..utils.validators import SecurityValidator
from .user_ops import delete_user, unlink_user_identity


@dataclass
class CheckpointOperationConfig:
    """Configuration for checkpoint-enabled operations."""

    token: str
    base_url: str
    env: str = "dev"
    resume_checkpoint_id: str | None = None
    checkpoint_manager: CheckpointManager | None = None


@dataclass
class ProcessingConfig:
    """Configuration for process function parameters and additional settings."""

    # Core processing parameters
    dry_run: bool = False
    batch_timeout: int | None = None

    # Operation-specific parameters
    connection_filter: str | None = None
    include_inactive: bool = False
    verify_results: bool = True

    # Additional custom parameters
    custom_params: dict[str, Any] = field(default_factory=dict)

    def get_all_params(self) -> dict[str, Any]:
        """Get all parameters as a dictionary for function calls.

        Returns:
            dict: All configuration parameters combined
        """
        params = {
            "dry_run": self.dry_run,
            "batch_timeout": self.batch_timeout,
            "connection_filter": self.connection_filter,
            "include_inactive": self.include_inactive,
            "verify_results": self.verify_results,
        }

        # Add custom parameters
        params.update(self.custom_params)

        # Remove None values to avoid passing unnecessary parameters
        return {k: v for k, v in params.items() if v is not None}


@dataclass
class ExecuteCheckpointConfig:
    """Configuration for checkpoint execution operations."""

    operation_type: OperationType
    items: list[str]
    config: CheckpointOperationConfig
    process_func: Callable[..., str | None]
    operation_name: str
    auto_delete: bool = True
    processing_config: ProcessingConfig | None = None


def categorize_users(
    found_users: list[dict[str, Any]], auto_delete: bool = True
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Categorize users based on their identity configuration.

    Args:
        found_users: List of users found with the social ID
        auto_delete: Whether to automatically delete users with main identity matches

    Returns:
        Tuple containing:
        - users_to_delete: Users that should be deleted
        - identities_to_unlink: Users where only the identity should be unlinked
        - auth0_main_protected: Users with Auth0 as main identity (protected)
    """
    users_to_delete = []
    identities_to_unlink = []
    auth0_main_protected = []

    for user in found_users:
        category = _determine_user_category(user, auto_delete)
        if category == "delete":
            users_to_delete.append(_create_user_record(user, "Main identity"))
        elif category == "unlink":
            identities_to_unlink.append(_create_user_record(user, "Secondary identity"))
        elif category == "protected":
            reason = (
                "Main identity (protected)"
                if not auto_delete
                else "Auth0 main identity"
            )
            auth0_main_protected.append(_create_user_record(user, reason))

    return users_to_delete, identities_to_unlink, auth0_main_protected


def _determine_user_category(user: dict[str, Any], auto_delete: bool) -> str:
    """Determine the category for a single user based on identity configuration.

    Args:
        user: User data with identities and social_id
        auto_delete: Whether auto-delete is enabled

    Returns:
        str: Category - "delete", "unlink", "protected", or "skip"
    """
    identities = user.get("identities", [])
    social_id = user.get("social_id", "")

    if not identities or not social_id:
        return "skip"

    matching_identity = _find_matching_identity(identities, social_id)
    if not matching_identity:
        return "skip"

    if _is_main_identity(identities):
        # Only one identity - this is the main identity
        return "delete" if auto_delete else "protected"

    # Multiple identities - check if Auth0 is the main identity
    if _has_auth0_main_identity(identities):
        return "protected"
    return "unlink"


def _find_matching_identity(
    identities: list[dict[str, Any]], social_id: str
) -> dict[str, Any] | None:
    """Find the identity matching the given social ID.

    Args:
        identities: List of user identities
        social_id: Social media ID to match

    Returns:
        dict | None: Matching identity or None if not found
    """
    for identity in identities:
        if identity.get("user_id") == social_id:
            return identity
    return None


def _is_main_identity(identities: list[dict[str, Any]]) -> bool:
    """Check if this is the user's only/main identity.

    Args:
        identities: List of user identities

    Returns:
        bool: True if this is the main/only identity
    """
    return len(identities) == 1


def _has_auth0_main_identity(identities: list[dict[str, Any]]) -> bool:
    """Check if the user has Auth0 as their main identity.

    Args:
        identities: List of user identities

    Returns:
        bool: True if Auth0 is the main identity (non-social)
    """
    for identity in identities:
        if (
            identity.get("connection") == "auth0"
            and identity.get("isSocial", False) is False
        ):
            return True
    return False


def _create_user_record(user: dict[str, Any], reason: str) -> dict[str, str]:
    """Create a standardized user record for categorization results.

    Args:
        user: User data
        reason: Reason for categorization

    Returns:
        dict: Standardized user record
    """
    identities = user.get("identities", [])
    social_id = user.get("social_id", "")
    matching_identity = _find_matching_identity(identities, social_id)
    matching_connection = (
        matching_identity.get("connection", "") if matching_identity else ""
    )

    return {
        "user_id": user.get("user_id", ""),
        "email": user.get("email", ""),
        "matching_connection": matching_connection,
        "social_id": social_id,
        "reason": reason,
    }


def _display_search_results(
    total_ids: int,
    found_users: list[dict[str, Any]],
    not_found_ids: list[str],
    users_to_delete: list[dict[str, Any]],
    identities_to_unlink: list[dict[str, Any]],
    auth0_main_protected: list[dict[str, Any]],
    auto_delete: bool = True,
) -> None:
    """Display search results summary.

    Args:
        total_ids: Total number of social IDs searched
        found_users: All users found with any of the social IDs
        not_found_ids: Social IDs that were not found
        users_to_delete: Users that will be deleted
        identities_to_unlink: Users where identities will be unlinked
        auth0_main_protected: Users that are protected from deletion
        auto_delete: Whether auto-delete is enabled
    """
    _print_search_summary(total_ids, found_users, not_found_ids)
    _print_not_found_ids(not_found_ids)
    _print_category_counts(users_to_delete, identities_to_unlink, auth0_main_protected)
    _print_category_details(users_to_delete, identities_to_unlink, auth0_main_protected)


def _print_search_summary(
    total_ids: int, found_users: list[dict[str, Any]], not_found_ids: list[str]
) -> None:
    """Print basic search results summary.

    Args:
        total_ids: Total number of social IDs searched
        found_users: All users found with any of the social IDs
        not_found_ids: Social IDs that were not found
    """
    print_info("\nSearch Results Summary:", operation="social_search_summary")
    print_info(f"Total social IDs searched: {total_ids}", total_ids=total_ids)
    print_info(f"Users found: {len(found_users)}", users_found=len(found_users))
    print_info(
        f"Social IDs not found: {len(not_found_ids)}",
        not_found_count=len(not_found_ids),
    )


def _print_not_found_ids(not_found_ids: list[str]) -> None:
    """Print list of social IDs that were not found.

    Args:
        not_found_ids: Social IDs that were not found
    """
    if not_found_ids:
        print_warning("\nSocial IDs not found:", count=len(not_found_ids))
        for social_id in not_found_ids:
            print_info(f"  {social_id}", social_id=social_id, status="not_found")


def _print_category_counts(
    users_to_delete: list[dict[str, Any]],
    identities_to_unlink: list[dict[str, Any]],
    auth0_main_protected: list[dict[str, Any]],
) -> None:
    """Print user category counts.

    Args:
        users_to_delete: Users that will be deleted
        identities_to_unlink: Users where identities will be unlinked
        auth0_main_protected: Users that are protected from deletion
    """
    print_info("\nUser Categories:", operation="categorization")
    print_info(
        f"  Users to delete: {len(users_to_delete)}", delete_count=len(users_to_delete)
    )
    print_info(
        f"  Identities to unlink: {len(identities_to_unlink)}",
        unlink_count=len(identities_to_unlink),
    )
    print_info(
        f"  Protected users: {len(auth0_main_protected)}",
        protected_count=len(auth0_main_protected),
    )


def _print_category_details(
    users_to_delete: list[dict[str, Any]],
    identities_to_unlink: list[dict[str, Any]],
    auth0_main_protected: list[dict[str, Any]],
) -> None:
    """Print detailed user lists for each category.

    Args:
        users_to_delete: Users that will be deleted
        identities_to_unlink: Users where identities will be unlinked
        auth0_main_protected: Users that are protected from deletion
    """
    if users_to_delete:
        _print_user_list("\nUsers that will be deleted:", users_to_delete, "delete")

    if identities_to_unlink:
        _print_user_list(
            "\nUsers where identities will be unlinked:", identities_to_unlink, "unlink"
        )

    if auth0_main_protected:
        _print_user_list(
            "\nProtected users (Auth0 main identity):",
            auth0_main_protected,
            "protected",
        )


def _print_user_list(header: str, user_list: list[dict[str, Any]], action: str) -> None:
    """Print a formatted list of users.

    Args:
        header: Header text for the list
        user_list: List of user records to print
        action: Action type for logging context
    """
    print_info(header, count=len(user_list))
    for user in user_list:
        print_info(
            f"  {user['user_id']} ({user['email']}) - {user['reason']}",
            user_id=user["user_id"],
            email=user["email"],
            reason=user["reason"],
            action=action,
        )


def _handle_auto_delete_operations(
    users_to_delete: list[dict[str, Any]],
    identities_to_unlink: list[dict[str, Any]],
    token: str,
    base_url: str,
    env: str = "dev",
    auto_delete: bool = True,
) -> None:
    """Handle automatic deletion and unlinking operations.

    Args:
        users_to_delete: Users that should be deleted
        identities_to_unlink: Users where identities should be unlinked
        token: Auth0 access token
        base_url: Auth0 API base URL
        env: Environment (dev/prod) for confirmation prompts
        auto_delete: Whether to perform automatic operations
    """
    total_operations = len(users_to_delete) + len(identities_to_unlink)

    if total_operations == 0:
        print_success("\nNo operations to perform.", operation="auto_delete")
        return

    if auto_delete:
        if not _confirm_production_operations(env, total_operations):
            return

        deletion_results = _handle_user_deletions(users_to_delete, token, base_url)
        unlinking_results = _handle_identity_unlinking(
            identities_to_unlink, token, base_url
        )

        _print_operations_summary(
            deletion_results, unlinking_results, users_to_delete, identities_to_unlink
        )

    elif total_operations > 0 and not auto_delete:
        _print_disabled_operations_notice(
            total_operations, users_to_delete, identities_to_unlink
        )


def _confirm_production_operations(env: str, total_operations: int) -> bool:
    """Confirm operations for production environment.

    Args:
        env: Environment (dev/prod)
        total_operations: Total number of operations to perform

    Returns:
        bool: True if confirmed, False if cancelled
    """
    import sys

    if env == "prod":
        print_warning(
            f"This will perform {total_operations} operations in PRODUCTION!",
            total_operations=total_operations,
            environment="prod",
        )
        # Flush both streams to ensure clean terminal state before input
        sys.stdout.flush()
        sys.stderr.flush()
        confirm = input("Type 'CONFIRM' to proceed: ")
        if confirm != "CONFIRM":
            print_warning("Operations cancelled.", operation="auto_delete")
            return False
    return True


def _handle_user_deletions(
    users_to_delete: list[dict[str, Any]], token: str, base_url: str
) -> dict[str, int]:
    """Handle deletion of users marked for deletion.

    Args:
        users_to_delete: List of users to delete
        token: Auth0 access token
        base_url: Auth0 API base URL

    Returns:
        dict: Results with deleted_count and failed_deletions
    """
    deleted_count = 0
    failed_deletions = 0

    if not users_to_delete:
        return {"deleted_count": 0, "failed_deletions": 0}

    print_info(
        f"\nDeleting {len(users_to_delete)} users...",
        count=len(users_to_delete),
        operation="delete_users",
    )

    with live_progress(len(users_to_delete), "Deleting users") as advance:
        for user in users_to_delete:
            if shutdown_requested():
                break

            try:
                delete_user(user["user_id"], token, base_url)
                deleted_count += 1
            except Exception as e:
                print_error(
                    f"\nFailed to delete user {user['user_id']}: {e}",
                    user_id=user["user_id"],
                    operation="delete_user",
                )
                failed_deletions += 1

            advance()
    return {"deleted_count": deleted_count, "failed_deletions": failed_deletions}


def _handle_identity_unlinking(
    identities_to_unlink: list[dict[str, Any]], token: str, base_url: str
) -> dict[str, int]:
    """Handle unlinking of identities and cleanup of orphaned users.

    Args:
        identities_to_unlink: List of identities to unlink
        token: Auth0 access token
        base_url: Auth0 API base URL

    Returns:
        dict: Results with counts for various operations
    """
    results = {
        "unlinked_count": 0,
        "failed_unlinks": 0,
        "orphaned_users_deleted": 0,
        "orphaned_users_failed": 0,
    }

    if not identities_to_unlink:
        return results

    print_warning(
        f"\nUnlinking {len(identities_to_unlink)} identities...",
        count=len(identities_to_unlink),
        operation="unlink_identities",
    )

    with live_progress(len(identities_to_unlink), "Unlinking identities") as advance:
        for user in identities_to_unlink:
            if shutdown_requested():
                break

            _process_single_identity_unlink(user, token, base_url, results)
            advance()
    return results


def _process_single_identity_unlink(
    user: dict[str, Any], token: str, base_url: str, results: dict[str, int]
) -> None:
    """Process unlinking of a single identity and handle orphaned users.

    Args:
        user: User data with identity information
        token: Auth0 access token
        base_url: Auth0 API base URL
        results: Results dictionary to update
    """
    try:
        success = unlink_user_identity(
            user["user_id"],
            user["matching_connection"],
            user["social_id"],
            token,
            base_url,
        )
        if success:
            results["unlinked_count"] += 1
            _handle_orphaned_users_cleanup(user, token, base_url, results)
        else:
            results["failed_unlinks"] += 1
    except Exception as e:
        print_error(
            f"\nFailed to unlink identity {user['social_id']} from user {user['user_id']}: {e}",
            user_id=user["user_id"],
            social_id=user["social_id"],
            operation="unlink_identity",
        )
        results["failed_unlinks"] += 1


def _handle_orphaned_users_cleanup(
    user: dict[str, Any], token: str, base_url: str, results: dict[str, int]
) -> None:
    """Handle cleanup of orphaned users after identity unlinking.

    Args:
        user: User data with identity information
        token: Auth0 access token
        base_url: Auth0 API base URL
        results: Results dictionary to update
    """
    # Check if user has no remaining identities after unlinking
    remaining_identities = _get_user_identity_count(user["user_id"], token, base_url)
    if remaining_identities == 0:
        _delete_orphaned_user(user["user_id"], token, base_url, results)

    # Search for and delete separate user accounts with this social ID as primary identity
    detached_users = _find_users_with_primary_social_id(
        user["social_id"], user["matching_connection"], token, base_url
    )
    for detached_user in detached_users:
        _delete_detached_social_user(
            detached_user, user["social_id"], token, base_url, results
        )


def _delete_orphaned_user(
    user_id: str, token: str, base_url: str, results: dict[str, int]
) -> None:
    """Delete a user that has no remaining identities.

    Args:
        user_id: User ID to delete
        token: Auth0 access token
        base_url: Auth0 API base URL
        results: Results dictionary to update
    """
    print_warning(
        f"User {user_id} has no remaining identities after unlinking, deleting...",
        user_id=user_id,
        operation="delete_orphaned_user",
    )
    try:
        delete_user(user_id, token, base_url)
        results["orphaned_users_deleted"] += 1
        print_success(
            f"Successfully deleted orphaned user {user_id}",
            user_id=user_id,
            operation="delete_orphaned_user",
        )
    except Exception as e:
        print_error(
            f"Failed to delete orphaned user {user_id}: {e}",
            user_id=user_id,
            operation="delete_orphaned_user",
        )
        results["orphaned_users_failed"] += 1


def _delete_detached_social_user(
    detached_user: dict[str, Any],
    social_id: str,
    token: str,
    base_url: str,
    results: dict[str, int],
) -> None:
    """Delete a detached social user account.

    Args:
        detached_user: Detached user data
        social_id: Social media ID
        token: Auth0 access token
        base_url: Auth0 API base URL
        results: Results dictionary to update
    """
    try:
        delete_user(detached_user["user_id"], token, base_url)
        results["orphaned_users_deleted"] += 1
        print_success(
            f"Successfully deleted detached social user {detached_user['user_id']} with identity {social_id}",
            user_id=detached_user["user_id"],
            social_id=social_id,
            operation="delete_detached_social_user",
        )
    except Exception as e:
        print_error(
            f"Failed to delete detached social user {detached_user['user_id']}: {e}",
            user_id=detached_user["user_id"],
            operation="delete_detached_social_user",
        )
        results["orphaned_users_failed"] += 1


def _print_operations_summary(
    deletion_results: dict[str, int],
    unlinking_results: dict[str, int],
    users_to_delete: list[dict[str, Any]],
    identities_to_unlink: list[dict[str, Any]],
) -> None:
    """Print summary of completed operations.

    Args:
        deletion_results: Results from user deletions
        unlinking_results: Results from identity unlinking
        users_to_delete: Original list of users to delete
        identities_to_unlink: Original list of identities to unlink
    """
    print_success("\nOperations Summary:", operation="operations_summary")

    if users_to_delete:
        print_info(
            f"Users deleted: {deletion_results['deleted_count']}",
            deleted_count=deletion_results["deleted_count"],
        )
        print_info(
            f"Failed deletions: {deletion_results['failed_deletions']}",
            failed_deletions=deletion_results["failed_deletions"],
        )

    if identities_to_unlink:
        print_info(
            f"Identities unlinked: {unlinking_results['unlinked_count']}",
            unlinked_count=unlinking_results["unlinked_count"],
        )
        print_info(
            f"Failed unlinks: {unlinking_results['failed_unlinks']}",
            failed_unlinks=unlinking_results["failed_unlinks"],
        )

        if unlinking_results["orphaned_users_deleted"] > 0:
            print_info(
                f"Orphaned users deleted: {unlinking_results['orphaned_users_deleted']}",
                orphaned_users_deleted=unlinking_results["orphaned_users_deleted"],
            )

        if unlinking_results["orphaned_users_failed"] > 0:
            print_info(
                f"Failed orphaned user deletions: {unlinking_results['orphaned_users_failed']}",
                orphaned_users_failed=unlinking_results["orphaned_users_failed"],
            )


def _print_disabled_operations_notice(
    total_operations: int,
    users_to_delete: list[dict[str, Any]],
    identities_to_unlink: list[dict[str, Any]],
) -> None:
    """Print notice when auto_delete is disabled but operations were found.

    Args:
        total_operations: Total number of operations found
        users_to_delete: Users that would be deleted
        identities_to_unlink: Identities that would be unlinked
    """
    print_warning(
        f"\nNote: {total_operations} operations found, but auto_delete is disabled.",
        total_operations=total_operations,
        auto_delete=False,
    )
    print_info(
        f"- {len(users_to_delete)} users would be deleted",
        delete_count=len(users_to_delete),
    )
    print_info(
        f"- {len(identities_to_unlink)} identities would be unlinked",
        unlink_count=len(identities_to_unlink),
    )


def _get_user_identity_count(user_id: str, token: str, base_url: str) -> int:
    """Get the number of identities for a user.

    Args:
        user_id: Auth0 user ID
        token: Auth0 access token
        base_url: Auth0 API base URL

    Returns:
        int: Number of identities for the user
    """
    url = f"{base_url}/api/v2/users/{secure_url_encode(user_id, 'user ID')}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": "DeletePy/1.0 (Auth0 User Management Tool)",
    }

    try:
        response = requests.get(url, headers=headers, timeout=API_TIMEOUT)
        response.raise_for_status()
        user_data = response.json()

        identities = user_data.get("identities", [])
        identity_count = len(identities) if isinstance(identities, list) else 0

        return identity_count

    except requests.exceptions.RequestException as e:
        print_error(
            f"Error getting user identity count for {user_id}: {e}",
            user_id=user_id,
            error=str(e),
            operation="get_user_identity_count",
        )
        return 0


def _has_social_id_as_primary_identity(
    user: dict[str, Any], social_id: str, connection: str
) -> bool:
    """Check if a user has the given social ID as their primary identity.

    Args:
        user: User data from Auth0
        social_id: The social media ID to check
        connection: The connection name for the social ID

    Returns:
        bool: True if the user has this social ID as their primary identity
    """
    if "identities" not in user or not isinstance(user["identities"], list):
        return False

    identities = user["identities"]
    if len(identities) == 0:
        return False

    # Check if this is the primary identity (usually the first one)
    primary_identity = identities[0]
    user_id = primary_identity.get("user_id")
    connection_name = primary_identity.get("connection")
    return bool(user_id == social_id and connection_name == connection)


def _find_users_with_primary_social_id(
    social_id: str,
    connection: str,
    token: str,
    base_url: str,
) -> list[dict[str, Any]]:
    """Find users with a specific social media ID as their primary identity.

    Args:
        social_id: The social media ID to search for
        connection: The connection name for the social ID
        token: Auth0 access token
        base_url: Auth0 API base URL

    Returns:
        List[Dict[str, Any]]: List of users found with this social ID as primary identity
    """
    url = f"{base_url}/api/v2/users"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": "DeletePy/1.0 (Auth0 User Management Tool)",
    }

    # Search for users with this social ID as their primary identity
    params = {
        "q": f'identities.user_id:"{social_id}" AND identities.connection:"{connection}"',
        "search_engine": "v3",
        "include_totals": "true",
        "page": "0",
        "per_page": "100",
    }

    found_users = []

    try:
        response = requests.get(
            url, headers=headers, params=params, timeout=API_TIMEOUT
        )
        response.raise_for_status()
        data = response.json()

        if "users" in data:
            for user in data["users"]:
                # Only include users where this social ID is their primary/main identity
                if _has_social_id_as_primary_identity(user, social_id, connection):
                    # This user has the social ID as their primary identity
                    found_users.append(user)
                    print_info(
                        f"Found detached social user {user.get('user_id', 'unknown')} with primary identity {social_id}",
                        user_id=user.get("user_id", "unknown"),
                        social_id=social_id,
                        operation="find_detached_social_user",
                    )

        time.sleep(API_RATE_LIMIT)

    except requests.exceptions.RequestException as e:
        print_error(
            f"Error searching for social ID {social_id}: {e}",
            social_id=social_id,
            operation="social_search",
        )

    return found_users


def _execute_batch_processing_loop(
    remaining_items: list[str],
    batch_size: int,
    checkpoint: Checkpoint,
    checkpoint_manager: CheckpointManager,
    batch_processor_func: Callable[..., dict[str, int]],
    operation_name: str,
    *processor_args: Any,
) -> str | None:
    """Execute batch processing loop with checkpoint support.

    Args:
        remaining_items: Items to process in batches
        batch_size: Size of each batch
        checkpoint: Checkpoint to update
        checkpoint_manager: Checkpoint manager instance
        batch_processor_func: Function to process each batch
        operation_name: Name of the operation for logging
        *processor_args: Additional arguments for the batch processor

    Returns:
        Optional[str]: Checkpoint ID if operation was interrupted, None if completed
    """
    # Process items in batches
    for batch_start in range(0, len(remaining_items), batch_size):
        if shutdown_requested():
            print_warning(f"\n{operation_name} interrupted")
            checkpoint_manager.save_checkpoint(checkpoint)
            return checkpoint.checkpoint_id

        batch_end = min(batch_start + batch_size, len(remaining_items))
        batch_items = remaining_items[batch_start:batch_end]

        current_batch = checkpoint.progress.current_batch + 1
        total_batches = checkpoint.progress.total_batches

        print_info(
            f"\nProcessing batch {current_batch}/{total_batches} "
            f"({batch_start + 1}-{batch_end} of {len(remaining_items)} remaining)"
        )

        # Process batch using the provided function
        batch_results = batch_processor_func(batch_items, *processor_args)

        # Update checkpoint progress
        results_update = {"processed_count": len(batch_items), **batch_results}

        checkpoint_manager.update_checkpoint_progress(
            checkpoint=checkpoint,
            processed_items=batch_items,
            results_update=results_update,
        )

        # Save checkpoint after each batch
        checkpoint_manager.save_checkpoint(checkpoint)

    return None  # Completed successfully


def _process_batch_items_with_checkpoints(
    checkpoint: Checkpoint,
    checkpoint_manager: CheckpointManager,
    batch_processor_func: Callable[..., dict[str, int]],
    operation_name: str,
    *processor_args: Any,
) -> str | None:
    """Process items in batches with checkpoint support.

    Args:
        checkpoint: Checkpoint to process
        checkpoint_manager: Checkpoint manager instance
        batch_processor_func: Function to process each batch
        operation_name: Name of the operation for logging
        *processor_args: Additional arguments for the batch processor

    Returns:
        Optional[str]: Checkpoint ID if operation was interrupted, None if completed
    """
    remaining_items = checkpoint.remaining_items.copy()
    batch_size = checkpoint.progress.batch_size

    if not remaining_items:
        print_info(f"No remaining items to process for {operation_name}")
        _finalize_checkpoint_completion(checkpoint, checkpoint_manager, operation_name)
        return None

    print_info(
        f"Processing {len(remaining_items)} remaining items for {operation_name}..."
    )

    # Execute the batch processing loop
    result = _execute_batch_processing_loop(
        remaining_items,
        batch_size,
        checkpoint,
        checkpoint_manager,
        batch_processor_func,
        operation_name,
        *processor_args,
    )

    # If operation was interrupted, return checkpoint ID
    if result is not None:
        return result

    # Mark checkpoint as completed
    _finalize_checkpoint_completion(checkpoint, checkpoint_manager, operation_name)
    return None


def _finalize_checkpoint_completion(
    checkpoint: Checkpoint, checkpoint_manager: CheckpointManager, operation_name: str
) -> None:
    """Finalize checkpoint completion.

    Args:
        checkpoint: Checkpoint to finalize
        checkpoint_manager: Checkpoint manager instance
        operation_name: Name of the operation for logging
    """
    checkpoint.status = CheckpointStatus.COMPLETED
    checkpoint_manager.save_checkpoint(checkpoint)
    print_success(f"{operation_name} completed! Checkpoint: {checkpoint.checkpoint_id}")


def _setup_checkpoint_operation_from_config(
    exec_config: ExecuteCheckpointConfig,
) -> tuple[Checkpoint, CheckpointManager, str, bool]:
    """Set up checkpoint operation from execution config.

    Args:
        exec_config: Configuration for checkpoint execution

    Returns:
        Tuple of (checkpoint, checkpoint_manager, env, auto_delete)
    """
    if exec_config.processing_config is None:
        exec_config.processing_config = ProcessingConfig()

    config = CheckpointConfig(
        operation_type=exec_config.operation_type,
        items=exec_config.items,
        env=exec_config.config.env,
        auto_delete=exec_config.auto_delete,
        operation_name=exec_config.operation_name,
    )

    result = load_or_create_checkpoint(
        resume_checkpoint_id=exec_config.config.resume_checkpoint_id,
        checkpoint_manager=exec_config.config.checkpoint_manager,
        config=config,
    )

    return result.checkpoint, result.checkpoint_manager, result.env, result.auto_delete


def _prepare_process_parameters(
    exec_config: ExecuteCheckpointConfig,
    checkpoint: Checkpoint,
    checkpoint_manager: CheckpointManager,
    env: str,
    auto_delete: bool,
) -> dict[str, Any]:
    """Prepare process function parameters dictionary.

    Args:
        exec_config: Configuration for checkpoint execution
        checkpoint: Checkpoint instance
        checkpoint_manager: Checkpoint manager instance
        env: Environment name
        auto_delete: Whether auto-delete is enabled

    Returns:
        Dictionary of process function parameters
    """
    process_params = {
        "checkpoint": checkpoint,
        "token": exec_config.config.token,
        "base_url": exec_config.config.base_url,
        "env": env,
        "auto_delete": auto_delete,
        "checkpoint_manager": checkpoint_manager,
    }

    # Add processing configuration parameters
    if exec_config.processing_config is not None:
        process_params.update(exec_config.processing_config.get_all_params())

    return process_params


def _execute_process_function_with_error_handling(
    exec_config: ExecuteCheckpointConfig,
    process_params: dict[str, Any],
    checkpoint: Checkpoint,
    checkpoint_manager: CheckpointManager,
) -> str | None:
    """Execute process function with error handling.

    Args:
        exec_config: Configuration for checkpoint execution
        process_params: Parameters for the process function
        checkpoint: Checkpoint instance
        checkpoint_manager: Checkpoint manager instance

    Returns:
        Optional[str]: Checkpoint ID if operation was interrupted, None if completed
    """
    try:
        return exec_config.process_func(**process_params)
    except KeyboardInterrupt:
        return _handle_checkpoint_interruption(
            checkpoint,
            checkpoint_manager,
            f"{exec_config.operation_name.replace('_', ' ').title()} operation",
        )
    except Exception as e:
        return _handle_checkpoint_error(
            checkpoint,
            checkpoint_manager,
            f"{exec_config.operation_name.replace('_', ' ').title()} operation",
            e,
        )


def _execute_with_checkpoints(
    operation_type: OperationType,
    items: list[str],
    config: CheckpointOperationConfig,
    process_func: Callable[..., str | None],
    operation_name: str,
    auto_delete: bool = True,
    processing_config: ProcessingConfig | None = None,
) -> str | None:
    """Execute operation with checkpoint lifecycle management.

    Args:
        operation_type: Type of operation to checkpoint
        items: List of items to process
        config: Configuration for checkpoint operations
        process_func: Function to process the operation
        operation_name: Name of the operation for logging
        auto_delete: Whether auto-delete is enabled
        processing_config: Additional processing configuration parameters

    Returns:
        Optional[str]: Checkpoint ID if operation was checkpointed, None if completed
    """
    exec_config = ExecuteCheckpointConfig(
        operation_type=operation_type,
        items=items,
        config=config,
        process_func=process_func,
        operation_name=operation_name,
        auto_delete=auto_delete,
        processing_config=processing_config,
    )

    (
        checkpoint,
        checkpoint_manager,
        env,
        auto_delete,
    ) = _setup_checkpoint_operation_from_config(exec_config)

    process_params = _prepare_process_parameters(
        exec_config, checkpoint, checkpoint_manager, env, auto_delete
    )

    return _execute_process_function_with_error_handling(
        exec_config, process_params, checkpoint, checkpoint_manager
    )


def find_users_by_social_media_ids_with_checkpoints(
    social_ids: list[str],
    config: CheckpointOperationConfig,
    auto_delete: bool = True,
) -> str | None:
    """Find Auth0 users with social media IDs and optionally delete them with checkpointing.

    Args:
        social_ids: List of social media IDs to search for
        config: Configuration for checkpoint operations (token, base_url, env, etc.)
        auto_delete: Whether to automatically delete users with main identity matches

    Returns:
        Optional[str]: Checkpoint ID if operation was checkpointed, None if completed
    """
    return _execute_with_checkpoints(
        operation_type=OperationType.SOCIAL_UNLINK,
        items=social_ids,
        config=config,
        process_func=_process_social_search_with_checkpoints,
        operation_name="social_unlink",
        auto_delete=auto_delete,
        processing_config=ProcessingConfig(),
    )


def _process_social_search_batch(
    batch_social_ids: list[str],
    token: str,
    base_url: str,
    accumulator: dict[str, list[Any]],
) -> dict[str, int]:
    """Process a batch of social IDs and update accumulator.

    Args:
        batch_social_ids: Batch of social IDs to process
        token: Auth0 access token
        base_url: Auth0 API base URL
        accumulator: Results accumulator to update

    Returns:
        Dict[str, int]: Batch processing results
    """
    found_users, not_found_ids = search_batch_social_ids(
        batch_social_ids, token, base_url
    )
    accumulator["found_users"].extend(found_users)
    accumulator["not_found_ids"].extend(not_found_ids)
    return {"processed_count": len(batch_social_ids)}


def _handle_social_search_completion(
    results_accumulator: dict[str, list[Any]],
    checkpoint: Checkpoint,
    token: str,
    base_url: str,
    env: str,
    auto_delete: bool,
) -> None:
    """Handle completion of social search with results processing.

    Args:
        results_accumulator: Accumulated search results
        checkpoint: Checkpoint being processed
        token: Auth0 access token
        base_url: Auth0 API base URL
        env: Environment name
        auto_delete: Whether auto-delete is enabled
    """
    found_users = results_accumulator["found_users"]
    not_found_ids = results_accumulator["not_found_ids"]

    _process_final_social_search_results(
        found_users, not_found_ids, checkpoint, token, base_url, env, auto_delete
    )


def _process_social_search_with_checkpoints(
    checkpoint: Checkpoint,
    token: str,
    base_url: str,
    env: str,
    auto_delete: bool,
    checkpoint_manager: CheckpointManager,
    dry_run: bool = False,  # Processing config parameter
    batch_timeout: int | None = None,  # Processing config parameter
    connection_filter: str | None = None,  # Processing config parameter
    include_inactive: bool = False,  # Processing config parameter
    verify_results: bool = True,  # Processing config parameter
    **custom_params: Any,  # Custom parameters from ProcessingConfig
) -> str | None:
    """Process social search operation with checkpointing support.

    This function is part of a generic interface system where all process functions
    receive the same set of parameters from ProcessingConfig via _execute_with_checkpoints.
    Only the first six parameters are used by this specific operation; the remaining
    parameters are kept for interface consistency but are not used in the function body.

    Args:
        checkpoint: Checkpoint to process
        token: Auth0 access token
        base_url: Auth0 API base URL
        env: Environment
        auto_delete: Whether to auto-delete users
        checkpoint_manager: Checkpoint manager instance
        dry_run: Processing config parameter (unused - kept for interface consistency)
        batch_timeout: Processing config parameter (unused - kept for interface consistency)
        connection_filter: Processing config parameter (unused - kept for interface consistency)
        include_inactive: Processing config parameter (unused - kept for interface consistency)
        verify_results: Processing config parameter (unused - kept for interface consistency)
        **custom_params: Custom parameters from ProcessingConfig (unused - kept for interface consistency)

    Returns:
        Optional[str]: Checkpoint ID if operation was interrupted, None if completed
    """
    # Initialize accumulator for results
    results_accumulator: dict[str, list[Any]] = {"found_users": [], "not_found_ids": []}

    # Process batches using common batch processing logic
    result = _process_batch_items_with_checkpoints(
        checkpoint,
        checkpoint_manager,
        _process_social_search_batch,
        "Social search",
        token,
        base_url,
        results_accumulator,
    )

    # If operation was interrupted, return checkpoint ID
    if result is not None:
        return result

    # Handle completion by processing final results
    _handle_social_search_completion(
        results_accumulator, checkpoint, token, base_url, env, auto_delete
    )

    return None  # Operation completed successfully


def _process_final_social_search_results(
    found_users: list[dict[str, Any]],
    not_found_ids: list[str],
    checkpoint: Checkpoint,
    token: str,
    base_url: str,
    env: str,
    auto_delete: bool,
) -> None:
    """Process final social search results and perform operations.

    Args:
        found_users: All users found during search
        not_found_ids: Social IDs that were not found
        checkpoint: Current checkpoint
        token: Auth0 access token
        base_url: Auth0 API base URL
        env: Environment
        auto_delete: Whether to auto-delete users
    """
    total_processed = len(checkpoint.processed_items) + len(checkpoint.remaining_items)

    # Categorize users based on their identity configuration
    users_to_delete, identities_to_unlink, auth0_main_protected = categorize_users(
        found_users, auto_delete
    )

    # Display search results
    _display_search_results(
        total_processed,
        found_users,
        not_found_ids,
        users_to_delete,
        identities_to_unlink,
        auth0_main_protected,
        auto_delete,
    )

    # Handle auto-delete operations
    _handle_auto_delete_operations(
        users_to_delete,
        identities_to_unlink,
        token,
        base_url,
        env,
        auto_delete,
    )


def search_batch_social_ids(
    social_ids: list[str], token: str, base_url: str
) -> tuple[list[dict[str, Any]], list[str]]:
    """Search for users with a batch of social media IDs.

    Args:
        social_ids: List of social media IDs to search for
        token: Auth0 access token
        base_url: Auth0 API base URL

    Returns:
        Tuple of (found_users, not_found_ids)
    """
    found_users = []
    not_found_ids = []

    with live_progress(len(social_ids), "Searching social IDs") as advance:
        for social_id in social_ids:
            if shutdown_requested():
                break

            social_id = SecurityValidator.sanitize_user_input(social_id)
            if not social_id:
                advance()
                continue

            # Search for users with this social ID
            users_found = _search_single_social_id(social_id, token, base_url)
            if users_found:
                # Add social_id to each user for later processing
                for user in users_found:
                    user["social_id"] = social_id
                found_users.extend(users_found)
            else:
                not_found_ids.append(social_id)

            advance()
    return found_users, not_found_ids


def _search_single_social_id(
    social_id: str, token: str, base_url: str
) -> list[dict[str, Any]]:
    """Search for users with a specific social media ID.

    Args:
        social_id: The social media ID to search for
        token: Auth0 access token
        base_url: Auth0 API base URL

    Returns:
        List[Dict[str, Any]]: List of users found with this social ID
    """
    url = f"{base_url}/api/v2/users"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": "DeletePy/1.0 (Auth0 User Management Tool)",
    }

    # Search for users with this social ID in their identities
    params = {
        "q": f'identities.user_id:"{social_id}"',
        "search_engine": "v3",
        "include_totals": "true",
        "page": "0",
        "per_page": "100",
    }

    found_users = []

    try:
        response = requests.get(
            url, headers=headers, params=params, timeout=API_TIMEOUT
        )
        response.raise_for_status()
        data = response.json()

        if "users" in data:
            for user in data["users"]:
                # Verify this user actually has the social ID
                if "identities" in user and isinstance(user["identities"], list):
                    for identity in user["identities"]:
                        if identity.get("user_id") == social_id:
                            found_users.append(user)
                            break

        time.sleep(API_RATE_LIMIT)

    except requests.exceptions.RequestException as e:
        print_error(
            f"Error searching for social ID {social_id}: {e}",
            social_id=social_id,
            operation="social_search",
        )

    return found_users


def check_unblocked_users_with_checkpoints(
    user_ids: list[str],
    config: CheckpointOperationConfig,
) -> str | None:
    """Check unblocked users with checkpointing support.

    Args:
        user_ids: List of Auth0 user IDs to check
        config: Configuration for checkpoint operations (token, base_url, env, etc.)

    Returns:
        Optional[str]: Checkpoint ID if operation was checkpointed, None if completed
    """
    return _execute_with_checkpoints(
        operation_type=OperationType.CHECK_UNBLOCKED,
        items=user_ids,
        config=config,
        process_func=_process_check_unblocked_with_checkpoints,
        operation_name="check_unblocked",
        auto_delete=False,  # Not relevant for check operations
        processing_config=ProcessingConfig(),
    )


def _process_check_unblocked_batch(
    batch_user_ids: list[str],
    token: str,
    base_url: str,
    accumulator: dict[str, list[str]],
) -> dict[str, int]:
    """Process a batch of user IDs to check for unblocked status.

    Args:
        batch_user_ids: List of user IDs to check
        token: Auth0 access token
        base_url: Auth0 API base URL
        accumulator: Dictionary to accumulate unblocked users

    Returns:
        dict: Batch processing results for checkpoint update
    """
    batch_unblocked = _check_batch_unblocked_users(batch_user_ids, token, base_url)

    accumulator["unblocked_users"].extend(batch_unblocked)

    return {}  # No specific results to track for checkpoint


def _process_check_unblocked_with_checkpoints(
    checkpoint: Checkpoint,
    token: str,
    base_url: str,
    checkpoint_manager: CheckpointManager,
    env: str | None = None,  # Ignored for check operations
    auto_delete: bool | None = None,  # Ignored for check operations
    dry_run: bool = False,  # Processing config parameter
    batch_timeout: int | None = None,  # Processing config parameter
    connection_filter: str | None = None,  # Processing config parameter
    include_inactive: bool = False,  # Processing config parameter
    verify_results: bool = True,  # Processing config parameter
    **custom_params: Any,  # Custom parameters from ProcessingConfig
) -> str | None:
    """Process check unblocked users with checkpoints.

    This function is part of a generic interface system where all process functions
    receive the same set of parameters from ProcessingConfig via _execute_with_checkpoints.
    Only the first four parameters are used by this specific operation; the remaining
    parameters are kept for interface consistency but are not used in the function body.

    Args:
        checkpoint: Checkpoint to process
        token: Auth0 access token
        base_url: Auth0 API base URL
        checkpoint_manager: Checkpoint manager instance
        env: Environment (unused - kept for interface consistency)
        auto_delete: Auto-delete flag (unused - kept for interface consistency)
        dry_run: Processing config parameter (unused - kept for interface consistency)
        batch_timeout: Processing config parameter (unused - kept for interface consistency)
        connection_filter: Processing config parameter (unused - kept for interface consistency)
        include_inactive: Processing config parameter (unused - kept for interface consistency)
        verify_results: Processing config parameter (unused - kept for interface consistency)
        **custom_params: Custom parameters from ProcessingConfig (unused - kept for interface consistency)

    Returns:
        Optional[str]: Checkpoint ID if operation was interrupted, None if completed
    """
    # Initialize results accumulator
    results_accumulator: dict[str, list[str]] = {"unblocked_users": []}

    # Process with checkpoint support
    checkpoint_result = _process_batch_items_with_checkpoints(
        checkpoint,
        checkpoint_manager,
        _process_check_unblocked_batch,
        "check_unblocked_users",
        token,
        base_url,
        results_accumulator,
    )

    if checkpoint_result is not None:
        return checkpoint_result

    # Display results
    _display_check_unblocked_results(results_accumulator["unblocked_users"])
    return None


def _display_check_unblocked_results(unblocked_users: list[str]) -> None:
    """Display results of check unblocked operation.

    Args:
        unblocked_users: List of unblocked user IDs
    """
    if unblocked_users:
        print_warning(
            f"Found {len(unblocked_users)} unblocked users:",
            count=len(unblocked_users),
            operation="check_unblocked",
        )
        for user_id in unblocked_users:
            print_info(f"  {user_id}", user_id=user_id, status="unblocked")
    else:
        print_info("All users are blocked.", operation="check_unblocked")


def _check_batch_unblocked_users(
    user_ids: list[str], token: str, base_url: str
) -> list[str]:
    """Check a batch of users for unblocked status.

    Args:
        user_ids: List of Auth0 user IDs to check
        token: Auth0 access token
        base_url: Auth0 API base URL

    Returns:
        List[str]: List of unblocked user IDs
    """
    unblocked = []
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": "DeletePy/1.0 (Auth0 User Management Tool)",
    }

    with live_progress(len(user_ids), "Checking users") as advance:
        for user_id in user_ids:
            if shutdown_requested():
                break

            url = f"{base_url}/api/v2/users/{secure_url_encode(user_id, 'user ID')}"

            try:
                response = requests.get(url, headers=headers, timeout=API_TIMEOUT)
                response.raise_for_status()
                user_data = response.json()
                if not user_data.get("blocked", False):
                    unblocked.append(user_id)
                time.sleep(API_RATE_LIMIT)
            except requests.exceptions.RequestException as e:
                print_error(
                    f"Error checking user {user_id}: {e}",
                    user_id=user_id,
                    operation="check_blocked",
                )

            advance()

    return unblocked
