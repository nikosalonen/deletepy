"""Core user operations for Auth0 user management."""

import time
from typing import Any
from urllib.parse import quote

import requests

from ..core.config import API_RATE_LIMIT, API_TIMEOUT
from ..models.checkpoint import (
    Checkpoint,
    CheckpointStatus,
    OperationConfig,
    OperationType,
)
from ..utils.checkpoint_manager import CheckpointManager
from ..utils.display_utils import (
    print_error,
    print_info,
    print_success,
    print_warning,
    show_progress,
    shutdown_requested,
)
from ..utils.request_utils import make_rate_limited_request


def delete_user(user_id: str, token: str, base_url: str) -> None:
    """Delete user from Auth0."""
    print_info(f"Deleting user: {user_id}", user_id=user_id, operation="delete_user")

    # First revoke all sessions
    revoke_user_sessions(user_id, token, base_url)

    url = f"{base_url}/api/v2/users/{quote(user_id)}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": "DeletePy/1.0 (Auth0 User Management Tool)",
    }
    try:
        response = requests.delete(url, headers=headers, timeout=API_TIMEOUT)
        response.raise_for_status()
        print_success(
            f"Successfully deleted user {user_id}",
            user_id=user_id,
            operation="delete_user",
        )
        time.sleep(API_RATE_LIMIT)
    except requests.exceptions.RequestException as e:
        print_error(
            f"Error deleting user {user_id}: {e}",
            user_id=user_id,
            operation="delete_user",
        )


def block_user(user_id: str, token: str, base_url: str) -> None:
    """Block user in Auth0."""
    print_info(f"Blocking user: {user_id}", user_id=user_id, operation="block_user")

    # First revoke all sessions and grants
    revoke_user_sessions(user_id, token, base_url)
    revoke_user_grants(user_id, token, base_url)

    url = f"{base_url}/api/v2/users/{quote(user_id)}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": "DeletePy/1.0 (Auth0 User Management Tool)",
    }
    payload = {"blocked": True}
    try:
        response = requests.patch(
            url, headers=headers, json=payload, timeout=API_TIMEOUT
        )
        response.raise_for_status()
        print_success(
            f"Successfully blocked user {user_id}",
            user_id=user_id,
            operation="block_user",
        )
        time.sleep(API_RATE_LIMIT)
    except requests.exceptions.RequestException as e:
        print_error(
            f"Error blocking user {user_id}: {e}",
            user_id=user_id,
            operation="block_user",
        )


def get_user_id_from_email(
    email: str, token: str, base_url: str, connection: str | None = None
) -> list[str] | None:
    """Fetch user_ids from Auth0 using email address. Returns list of user_ids or None if not found.

    Args:
        email: Email address to search for
        token: Auth0 access token
        base_url: Auth0 API base URL
        connection: Optional connection filter (e.g., "google-oauth2", "auth0", "facebook")

    Returns:
        Optional[List[str]]: List of user IDs matching the email and connection filter
    """
    url = f"{base_url}/api/v2/users-by-email"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": "DeletePy/1.0 (Auth0 User Management Tool)",
    }
    params = {"email": email}

    response = make_rate_limited_request("GET", url, headers, params=params)
    if response is None:
        print_error(
            f"Error fetching user_id for email {email}: Request failed after retries",
            email=email,
            operation="get_user_id_from_email",
        )
        return None

    try:
        users = response.json()
        if users and isinstance(users, list):
            user_ids = []
            for user in users:
                if "user_id" in user:
                    # If connection filter is specified, check if user matches
                    if connection:
                        # Check if identities array exists in the response and filter directly
                        if user.get("identities") and isinstance(
                            user["identities"], list
                        ):
                            # Filter by connection using data already in the response
                            user_connection = user["identities"][0].get(
                                "connection", "unknown"
                            )
                            if user_connection == connection:
                                user_ids.append(user["user_id"])
                        else:
                            # Fallback: identities not included, skip this user to avoid API call
                            print_warning(
                                f"Connection info not available for user {user['user_id']}, skipping",
                                user_id=user["user_id"],
                                operation="get_user_id_from_email",
                            )
                    else:
                        # No connection filter, include all users
                        user_ids.append(user["user_id"])

            if user_ids:
                return user_ids
        return None
    except ValueError as e:
        print_error(
            f"Error parsing response for email {email}: {e}",
            email=email,
            error=str(e),
            operation="get_user_id_from_email",
        )
        return None


def get_user_email(user_id: str, token: str, base_url: str) -> str | None:
    """Fetch user's email address from Auth0.

    Args:
        user_id: The Auth0 user ID
        token: Auth0 access token
        base_url: Auth0 API base URL

    Returns:
        Optional[str]: User's email address if found, None otherwise
    """
    url = f"{base_url}/api/v2/users/{quote(user_id)}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": "DeletePy/1.0 (Auth0 User Management Tool)",
    }
    try:
        response = requests.get(url, headers=headers, timeout=API_TIMEOUT)
        response.raise_for_status()
        user_data = response.json()
        time.sleep(API_RATE_LIMIT)
        return user_data.get("email")
    except requests.exceptions.RequestException as e:
        print_error(
            f"Error fetching email for user {user_id}: {e}",
            user_id=user_id,
            error=str(e),
            operation="get_user_email",
        )
        return None


def get_user_details(user_id: str, token: str, base_url: str) -> dict[str, Any] | None:
    """Fetch user details from Auth0 including connection information.

    Args:
        user_id: The Auth0 user ID
        token: Auth0 access token
        base_url: Auth0 API base URL

    Returns:
        Optional[Dict[str, Any]]: User details if found, None otherwise
    """
    url = f"{base_url}/api/v2/users/{quote(user_id)}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": "DeletePy/1.0 (Auth0 User Management Tool)",
    }

    response = make_rate_limited_request("GET", url, headers)
    if response is None:
        print_error(
            f"Error fetching details for user {user_id}: Request failed after retries",
            user_id=user_id,
            operation="get_user_details",
        )
        return None

    try:
        user_data = response.json()
        return user_data
    except ValueError as e:
        print_error(
            f"Error parsing response for user {user_id}: {e}",
            user_id=user_id,
            error=str(e),
            operation="get_user_details",
        )
        return None


def revoke_user_sessions(user_id: str, token: str, base_url: str) -> None:
    """Fetch all Auth0 sessions for a user and revoke them one by one."""
    list_url = f"{base_url}/api/v2/users/{quote(user_id)}/sessions"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": "DeletePy/1.0 (Auth0 User Management Tool)",
    }
    try:
        response = requests.get(list_url, headers=headers, timeout=API_TIMEOUT)
        response.raise_for_status()
        sessions = response.json().get("sessions", [])
        if not sessions:
            print_info(
                f"No sessions found for user {user_id}",
                user_id=user_id,
                operation="revoke_user_sessions",
            )
            return
        for session in sessions:
            if shutdown_requested():
                break
            session_id = session.get("id")
            if not session_id:
                continue
            del_url = f"{base_url}/api/v2/sessions/{session_id}"
            del_resp = requests.delete(del_url, headers=headers, timeout=API_TIMEOUT)
            time.sleep(API_RATE_LIMIT)
            try:
                del_resp.raise_for_status()
                print_success(
                    f"Revoked session {session_id} for user {user_id}",
                    user_id=user_id,
                    session_id=session_id,
                    operation="revoke_user_sessions",
                )
            except requests.exceptions.RequestException as e:
                print_warning(
                    f"Failed to revoke session {session_id} for user {user_id}: {e}",
                    user_id=user_id,
                    session_id=session_id,
                    error=str(e),
                    operation="revoke_user_sessions",
                )
    except requests.exceptions.RequestException as e:
        print_error(
            f"Error revoking sessions for user {user_id}: {e}",
            user_id=user_id,
            error=str(e),
            operation="revoke_user_sessions",
        )


def revoke_user_grants(user_id: str, token: str, base_url: str) -> None:
    """Revoke all application grants (authorized applications) for a user in one call."""
    grants_url = f"{base_url}/api/v2/grants?user_id={quote(user_id)}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": "DeletePy/1.0 (Auth0 User Management Tool)",
    }
    try:
        response = requests.delete(grants_url, headers=headers, timeout=API_TIMEOUT)
        response.raise_for_status()
        print_success(
            f"Revoked all application grants for user {user_id}",
            user_id=user_id,
            operation="revoke_user_grants",
        )
        time.sleep(API_RATE_LIMIT)
    except requests.exceptions.RequestException as e:
        print_error(
            f"Error revoking grants for user {user_id}: {e}",
            user_id=user_id,
            error=str(e),
            operation="revoke_user_grants",
        )


def unlink_user_identity(
    user_id: str, provider: str, user_identity_id: str, token: str, base_url: str
) -> bool:
    """Unlink a social identity from a user.

    Args:
        user_id: The Auth0 user ID
        provider: The identity provider (e.g., "google-oauth2", "facebook")
        user_identity_id: The identity ID to unlink
        token: Auth0 access token
        base_url: Auth0 API base URL

    Returns:
        bool: True if successful, False otherwise
    """
    url = f"{base_url}/api/v2/users/{quote(user_id)}/identities/{provider}/{user_identity_id}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": "DeletePy/1.0 (Auth0 User Management Tool)",
    }
    try:
        response = requests.delete(url, headers=headers, timeout=API_TIMEOUT)
        response.raise_for_status()
        print_success(
            f"Successfully unlinked {provider} identity {user_identity_id} from user {user_id}",
            user_id=user_id,
            provider=provider,
            user_identity_id=user_identity_id,
            operation="unlink_user_identity",
        )
        time.sleep(API_RATE_LIMIT)
        return True
    except requests.exceptions.RequestException as e:
        print_error(
            f"Error unlinking {provider} identity {user_identity_id} from user {user_id}: {e}",
            user_id=user_id,
            provider=provider,
            user_identity_id=user_identity_id,
            error=str(e),
            operation="unlink_user_identity",
        )
        return False


def batch_user_operations_with_checkpoints(
    user_ids: list[str],
    token: str,
    base_url: str,
    operation: str,
    env: str = "dev",
    resume_checkpoint_id: str | None = None,
    checkpoint_manager: CheckpointManager | None = None,
) -> str | None:
    """Perform batch user operations with checkpointing support.

    Args:
        user_ids: List of user IDs/emails to process
        token: Auth0 access token
        base_url: Auth0 API base URL
        operation: Operation to perform ('delete', 'block', 'revoke-grants-only')
        env: Environment (dev/prod)
        resume_checkpoint_id: Optional checkpoint ID to resume from
        checkpoint_manager: Optional checkpoint manager instance

    Returns:
        Optional[str]: Checkpoint ID if operation was checkpointed, None if completed
    """
    # Initialize checkpoint manager if not provided
    if checkpoint_manager is None:
        checkpoint_manager = CheckpointManager()

    # Map operation to checkpoint operation type
    operation_type_map = {
        "delete": OperationType.BATCH_DELETE,
        "block": OperationType.BATCH_BLOCK,
        "revoke-grants-only": OperationType.BATCH_REVOKE_GRANTS,
    }

    if operation not in operation_type_map:
        raise ValueError(f"Unsupported operation: {operation}")

    operation_type = operation_type_map[operation]

    # Check if we're resuming from a checkpoint
    checkpoint = None
    if resume_checkpoint_id:
        checkpoint = checkpoint_manager.load_checkpoint(resume_checkpoint_id)
        if not checkpoint:
            print_warning(f"Could not load checkpoint {resume_checkpoint_id}, starting fresh")
        elif checkpoint.status != CheckpointStatus.ACTIVE:
            print_warning(f"Checkpoint {resume_checkpoint_id} is not active (status: {checkpoint.status.value})")
            checkpoint = None
        elif not checkpoint.is_resumable():
            print_warning(f"Checkpoint {resume_checkpoint_id} is not resumable")
            checkpoint = None

    # If not resuming, create a new checkpoint
    if checkpoint is None:
        # Create operation config
        config = OperationConfig(
            environment=env,
            additional_params={"operation": operation}
        )

        # Create new checkpoint
        checkpoint = checkpoint_manager.create_checkpoint(
            operation_type=operation_type,
            config=config,
            items=user_ids,
            batch_size=50
        )

        print_info(f"Created checkpoint: {checkpoint.checkpoint_id}")
    else:
        print_success(f"Resuming from checkpoint: {checkpoint.checkpoint_id}")
        # Use configuration from checkpoint
        env = checkpoint.config.environment
        operation = checkpoint.config.additional_params.get("operation", operation)

    # Save initial checkpoint
    checkpoint_manager.save_checkpoint(checkpoint)

    try:
        return _process_batch_user_operations_with_checkpoints(
            checkpoint=checkpoint,
            token=token,
            base_url=base_url,
            operation=operation,
            checkpoint_manager=checkpoint_manager
        )
    except KeyboardInterrupt:
        print_warning(f"\n{operation.title()} operation interrupted by user")
        checkpoint_manager.mark_checkpoint_cancelled(checkpoint)
        checkpoint_manager.save_checkpoint(checkpoint)
        print_info(f"Checkpoint saved: {checkpoint.checkpoint_id}")
        print_info("You can resume this operation later using:")
        print_info(f"  deletepy resume {checkpoint.checkpoint_id}")
        return checkpoint.checkpoint_id
    except Exception as e:
        print_warning(f"\n{operation.title()} operation failed: {e}")
        checkpoint_manager.mark_checkpoint_failed(checkpoint, str(e))
        checkpoint_manager.save_checkpoint(checkpoint)
        return checkpoint.checkpoint_id


def _process_batch_user_operations_with_checkpoints(
    checkpoint: Checkpoint,
    token: str,
    base_url: str,
    operation: str,
    checkpoint_manager: CheckpointManager
) -> str | None:
    """Process batch user operations with checkpointing support.

    Args:
        checkpoint: Checkpoint to process
        token: Auth0 access token
        base_url: Auth0 API base URL
        operation: Operation to perform
        checkpoint_manager: Checkpoint manager instance

    Returns:
        Optional[str]: Checkpoint ID if operation was interrupted, None if completed
    """
    remaining_user_ids = checkpoint.remaining_items.copy()
    batch_size = checkpoint.progress.batch_size

    operation_display = {
        "delete": "Deleting users",
        "block": "Blocking users",
        "revoke-grants-only": "Revoking grants and sessions"
    }.get(operation, "Processing users")

    print_info(f"{operation_display} - {len(remaining_user_ids)} remaining users...")

    # Initialize processing state
    multiple_users = {}
    not_found_users = []
    invalid_user_ids = []

    # Process remaining user IDs in batches
    for batch_start in range(0, len(remaining_user_ids), batch_size):
        if shutdown_requested():
            print_warning("\nOperation interrupted")
            checkpoint_manager.save_checkpoint(checkpoint)
            return checkpoint.checkpoint_id

        batch_end = min(batch_start + batch_size, len(remaining_user_ids))
        batch_user_ids = remaining_user_ids[batch_start:batch_end]

        current_batch = checkpoint.progress.current_batch + 1
        total_batches = checkpoint.progress.total_batches

        print_info(f"\nProcessing batch {current_batch}/{total_batches} ({batch_start + 1}-{batch_end} of {len(remaining_user_ids)} remaining)")

        # Process users in this batch
        batch_results = _process_user_batch(
            batch_user_ids, token, base_url, operation
        )

        # Update tracking lists
        multiple_users.update(batch_results.get("multiple_users", {}))
        not_found_users.extend(batch_results.get("not_found_users", []))
        invalid_user_ids.extend(batch_results.get("invalid_user_ids", []))

        # Update checkpoint progress
        results_update = {
            "processed_count": batch_results.get("processed_count", 0),
            "skipped_count": batch_results.get("skipped_count", 0),
            "multiple_users": batch_results.get("multiple_users", {}),
            "not_found_users": batch_results.get("not_found_users", []),
            "invalid_user_ids": batch_results.get("invalid_user_ids", []),
        }

        checkpoint_manager.update_checkpoint_progress(
            checkpoint=checkpoint,
            processed_items=batch_user_ids,
            results_update=results_update
        )

        # Save checkpoint after each batch
        checkpoint_manager.save_checkpoint(checkpoint)

    # Display operation summary
    _print_user_operation_summary(
        checkpoint.results.processed_count,
        checkpoint.results.skipped_count,
        not_found_users,
        invalid_user_ids,
        multiple_users,
        token,
        base_url,
    )

    # Mark checkpoint as completed
    checkpoint.status = CheckpointStatus.COMPLETED
    checkpoint_manager.save_checkpoint(checkpoint)

    print_success(f"{operation.title()} operation completed! Checkpoint: {checkpoint.checkpoint_id}")
    return None  # Operation completed successfully


def _process_user_batch(
    user_ids: list[str],
    token: str,
    base_url: str,
    operation: str
) -> dict:
    """Process a batch of users for a specific operation.

    Args:
        user_ids: List of user IDs to process
        token: Auth0 access token
        base_url: Auth0 API base URL
        operation: Operation to perform

    Returns:
        dict: Processing results for this batch
    """
    results = {
        "processed_count": 0,
        "skipped_count": 0,
        "multiple_users": {},
        "not_found_users": [],
        "invalid_user_ids": [],
    }

    for idx, user_id in enumerate(user_ids, 1):
        if shutdown_requested():
            break

        show_progress(idx, len(user_ids), f"Processing {operation}")

        user_id = user_id.strip()

        # Resolve user identifier
        resolved_user_id = _resolve_user_identifier_for_batch(
            user_id, token, base_url, results
        )

        if resolved_user_id is None:
            results["skipped_count"] += 1
            continue

        # Perform the operation
        try:
            _execute_user_operation(operation, resolved_user_id, token, base_url)
            results["processed_count"] += 1
        except Exception as e:
            print_error(f"\nFailed to {operation} user {resolved_user_id}: {e}")
            results["skipped_count"] += 1

    print("\n")  # Clear progress line
    return results


def _resolve_user_identifier_for_batch(
    user_id: str,
    token: str,
    base_url: str,
    results: dict
) -> str | None:
    """Resolve user identifier (email or user ID) to a valid user ID for batch processing.

    Args:
        user_id: User identifier (email or Auth0 user ID)
        token: Auth0 access token
        base_url: Auth0 API base URL
        results: Results dictionary to update

    Returns:
        Optional[str]: Valid user ID if found, None if should skip
    """
    from ..utils.auth_utils import validate_auth0_user_id

    # If input is an email, resolve to user_id
    if (
        "@" in user_id
        and user_id.count("@") == 1
        and len(user_id.split("@")[1]) > 0
    ):
        resolved_ids = get_user_id_from_email(user_id, token, base_url)
        if not resolved_ids:
            results["not_found_users"].append(user_id)
            return None

        if len(resolved_ids) > 1:
            results["multiple_users"][user_id] = resolved_ids
            return None

        return resolved_ids[0]

    # Validate Auth0 user ID format
    elif not validate_auth0_user_id(user_id):
        results["invalid_user_ids"].append(user_id)
        return None

    return user_id


def _execute_user_operation(operation: str, user_id: str, token: str, base_url: str) -> None:
    """Execute the specified operation on a user.

    Args:
        operation: Operation to perform
        user_id: Auth0 user ID
        token: Auth0 access token
        base_url: Auth0 API base URL
    """
    if operation == "block":
        block_user(user_id, token, base_url)
    elif operation == "delete":
        delete_user(user_id, token, base_url)
    elif operation == "revoke-grants-only":
        revoke_user_sessions(user_id, token, base_url)
        revoke_user_grants(user_id, token, base_url)


def _print_user_operation_summary(
    processed_count: int,
    skipped_count: int,
    not_found_users: list[str],
    invalid_user_ids: list[str],
    multiple_users: dict,
    token: str,
    base_url: str,
) -> None:
    """Print operation summary for user operations.

    Args:
        processed_count: Number of users processed
        skipped_count: Number of users skipped
        not_found_users: List of emails not found
        invalid_user_ids: List of invalid user IDs
        multiple_users: Dict of emails with multiple users
        token: Auth0 access token
        base_url: Auth0 API base URL
    """
    from ..utils.display_utils import CYAN, RESET

    print_info("\nOperation Summary:")
    print_info(f"Total users processed: {processed_count}")
    print_info(f"Total users skipped: {skipped_count}")

    if not_found_users:
        print_info(f"\nNot found users ({len(not_found_users)}):")
        for email in not_found_users:
            print_info(f"  {CYAN}{email}{RESET}")

    if invalid_user_ids:
        print_info(f"\nInvalid user IDs ({len(invalid_user_ids)}):")
        for user_id in invalid_user_ids:
            print_info(f"  {CYAN}{user_id}{RESET}")

    if multiple_users:
        print_info(f"\nFound {len(multiple_users)} emails with multiple users:")
        for email, user_ids in multiple_users.items():
            print_info(f"\n  {CYAN}{email}{RESET}:")
            for uid in user_ids:
                user_details = get_user_details(uid, token, base_url)
                if (
                    user_details
                    and user_details.get("identities")
                    and len(user_details["identities"]) > 0
                ):
                    connection = user_details["identities"][0].get(
                        "connection", "unknown"
                    )
                    print_info(f"    - {uid} (Connection: {connection})")
                else:
                    print_info(f"    - {uid} (Connection: unknown)")
