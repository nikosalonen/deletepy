"""Core user operations for Auth0 user management."""

import time
from typing import Any, cast
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
from ..utils.display_utils import show_progress, shutdown_requested
from ..utils.legacy_print import print_error, print_info, print_success, print_warning
from ..utils.request_utils import make_rate_limited_request
from ..utils.validators import InputValidator


def secure_url_encode(value: str, context: str = "URL parameter") -> str:
    """Securely URL encode a value with validation.

    Args:
        value: Value to encode
        context: Context description for error messages

    Returns:
        str: Safely encoded value

    Raises:
        ValueError: If value fails security validation
    """
    if not value:
        raise ValueError(f"{context} cannot be empty")

    # Validate the original value
    if "user" in context.lower() or "id" in context.lower():
        result = InputValidator.validate_auth0_user_id_enhanced(value)
        if not result.is_valid:
            raise ValueError(f"Invalid {context}: {result.error_message}")

    # URL encode the value
    encoded = quote(value, safe="")

    # Validate the encoded result
    validation_result = InputValidator.validate_url_encoding_secure(encoded)
    if not validation_result.is_valid:
        raise ValueError(
            f"URL encoding failed security validation for {context}: {validation_result.error_message}"
        )

    return encoded


def delete_user(user_id: str, token: str, base_url: str) -> None:
    """Delete user from Auth0."""
    print_info(f"Deleting user: {user_id}", user_id=user_id, operation="delete_user")

    # First revoke all sessions
    revoke_user_sessions(user_id, token, base_url)

    url = f"{base_url}/api/v2/users/{secure_url_encode(user_id, 'user ID')}"
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

    url = f"{base_url}/api/v2/users/{secure_url_encode(user_id, 'user ID')}"
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
    # Fetch users by email
    users = _fetch_users_by_email(email, token, base_url)
    if users is None:
        return None

    # Handle empty list consistently - return None when no users found
    if not users:
        return None

    # Extract user IDs with connection filtering
    user_ids = _extract_user_ids_from_response(users, connection, email)

    return user_ids if user_ids else None


def _fetch_users_by_email(
    email: str, token: str, base_url: str
) -> list[dict[str, Any]] | None:
    """Fetch users from Auth0 API by email address.

    Args:
        email: Email address to search for
        token: Auth0 access token
        base_url: Auth0 API base URL

    Returns:
        Optional[List[Dict[str, Any]]]: List of user objects or None if request failed
    """
    from ..utils.logging_utils import get_logger

    logger = get_logger(__name__)
    url = f"{base_url}/api/v2/users-by-email"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": "DeletePy/1.0 (Auth0 User Management Tool)",
    }
    params = {"email": email}

    response = make_rate_limited_request("GET", url, headers, params=params)
    if response is None:
        logger.error(
            f"Error fetching user_id for email {email}: Request failed after retries",
            extra={
                "email": email,
                "operation": "get_user_id_from_email",
                "api_endpoint": url,
                "error_type": "request_failed",
            },
        )
        return None

    try:
        users = response.json()
        if isinstance(users, list):
            if users:
                logger.info(
                    f"Found {len(users)} user(s) for email {email}",
                    extra={
                        "email": email,
                        "operation": "get_user_id_from_email",
                        "user_count": len(users),
                    },
                )
                return cast(list[dict[str, Any]], users)
            else:
                logger.info(
                    f"No users found for email {email}",
                    extra={
                        "email": email,
                        "operation": "get_user_id_from_email",
                        "user_count": 0,
                    },
                )
                return []  # Return empty list instead of None for consistency
        else:
            logger.warning(
                f"Unexpected response format for email {email}: expected list, got {type(users)}",
                extra={
                    "email": email,
                    "operation": "get_user_id_from_email",
                    "response_type": str(type(users)),
                },
            )
            return []
    except ValueError as e:
        logger.error(
            f"Error parsing response for email {email}: {e}",
            extra={
                "email": email,
                "error": str(e),
                "operation": "get_user_id_from_email",
                "error_type": "json_parse_error",
            },
            exc_info=True,
        )
        return None


def _extract_user_ids_from_response(
    users: list[dict[str, Any]], connection: str | None, email: str
) -> list[str]:
    """Extract user IDs from Auth0 API response with optional connection filtering.

    Args:
        users: List of user objects from Auth0 API
        connection: Optional connection filter
        email: Email address for logging purposes

    Returns:
        List[str]: List of user IDs matching the connection filter
    """
    user_ids = []
    for user in users:
        if "user_id" not in user:
            continue

        if connection:
            # Check if connection filter matches
            if _user_matches_connection(user, connection, email):
                user_ids.append(user["user_id"])
        else:
            # No connection filter, include all users
            user_ids.append(user["user_id"])

    return user_ids


def _user_matches_connection(user: dict[str, Any], connection: str, email: str) -> bool:
    """Check if user matches the specified connection filter.

    Args:
        user: User object from Auth0 API
        connection: Connection filter to match
        email: Email address for logging purposes

    Returns:
        bool: True if user matches connection, False otherwise
    """
    # Check if identities array exists in the response
    if user.get("identities") and isinstance(user["identities"], list):
        # Filter by connection using data already in the response
        user_connection = cast(str, user["identities"][0].get("connection", "unknown"))
        return user_connection == connection
    else:
        # Fallback: identities not included, skip this user to avoid API call
        print_warning(
            f"Connection info not available for user {user['user_id']}, skipping",
            user_id=user["user_id"],
            operation="get_user_id_from_email",
        )
        return False


def get_user_email(user_id: str, token: str, base_url: str) -> str | None:
    """Fetch user's email address from Auth0.

    Args:
        user_id: The Auth0 user ID
        token: Auth0 access token
        base_url: Auth0 API base URL

    Returns:
        Optional[str]: User's email address if found, None otherwise
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
        user_data: dict[str, Any] = response.json()
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
    url = f"{base_url}/api/v2/users/{secure_url_encode(user_id, 'user ID')}"
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
        user_data: dict[str, Any] = response.json()
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
    # Get list of sessions for the user
    sessions = _fetch_user_sessions(user_id, token, base_url)
    if sessions is None:
        return

    if not sessions:
        print_info(
            f"No sessions found for user {user_id}",
            user_id=user_id,
            operation="revoke_user_sessions",
        )
        return

    # Revoke each session
    _revoke_individual_sessions(sessions, user_id, token, base_url)


def _fetch_user_sessions(
    user_id: str, token: str, base_url: str
) -> list[dict[str, Any]] | None:
    """Fetch the list of sessions for a user.

    Args:
        user_id: Auth0 user ID
        token: Auth0 access token
        base_url: Auth0 API base URL

    Returns:
        Optional[List[Dict[str, Any]]]: List of sessions or None if request failed
    """
    list_url = (
        f"{base_url}/api/v2/users/{secure_url_encode(user_id, 'user ID')}/sessions"
    )
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": "DeletePy/1.0 (Auth0 User Management Tool)",
    }

    try:
        response = requests.get(list_url, headers=headers, timeout=API_TIMEOUT)
        response.raise_for_status()
        return cast(list[dict[str, Any]], response.json().get("sessions", []))
    except requests.exceptions.RequestException as e:
        print_error(
            f"Error fetching sessions for user {user_id}: {e}",
            user_id=user_id,
            error=str(e),
            operation="revoke_user_sessions",
        )
        return None


def _revoke_individual_sessions(
    sessions: list[dict[str, Any]], user_id: str, token: str, base_url: str
) -> None:
    """Revoke individual sessions for a user.

    Args:
        sessions: List of session objects
        user_id: Auth0 user ID
        token: Auth0 access token
        base_url: Auth0 API base URL
    """
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": "DeletePy/1.0 (Auth0 User Management Tool)",
    }

    _process_session_revocations(sessions, user_id, token, base_url, headers)


def _process_session_revocations(
    sessions: list[dict[str, Any]],
    user_id: str,
    token: str,
    base_url: str,
    headers: dict[str, str],
) -> None:
    """Process the revocation of individual sessions.

    Args:
        sessions: List of session objects
        user_id: Auth0 user ID
        token: Auth0 access token
        base_url: Auth0 API base URL
        headers: HTTP headers for the request
    """
    for session in sessions:
        session_id = session.get("id")
        if not session_id:
            continue

        _revoke_single_session(session_id, user_id, token, base_url, headers)


def _revoke_single_session(
    session_id: str, user_id: str, token: str, base_url: str, headers: dict[str, str]
) -> None:
    """Revoke a single session.

    Args:
        session_id: Session ID to revoke
        user_id: Auth0 user ID
        token: Auth0 access token
        base_url: Auth0 API base URL
        headers: HTTP headers for the request
    """
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


def revoke_user_grants(user_id: str, token: str, base_url: str) -> None:
    """Revoke all application grants (authorized applications) for a user in one call."""
    grants_url = (
        f"{base_url}/api/v2/grants?user_id={secure_url_encode(user_id, 'user ID')}"
    )
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
    url = f"{base_url}/api/v2/users/{secure_url_encode(user_id, 'user ID')}/identities/{provider}/{user_identity_id}"
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


def _load_or_create_checkpoint(
    resume_checkpoint_id: str | None,
    checkpoint_manager: CheckpointManager,
    operation: str,
    operation_type: OperationType,
    env: str,
    user_ids: list[str],
) -> Checkpoint:
    """Load existing checkpoint or create a new one.

    Args:
        resume_checkpoint_id: Optional checkpoint ID to resume from
        checkpoint_manager: Checkpoint manager instance
        operation: Operation to perform
        operation_type: Operation type enum
        env: Environment (dev/prod)
        user_ids: List of user IDs to process

    Returns:
        Checkpoint: Loaded or newly created checkpoint
    """
    # Try to load existing checkpoint
    checkpoint = _try_load_existing_checkpoint(resume_checkpoint_id, checkpoint_manager)

    # If not resuming, create a new checkpoint
    if checkpoint is None:
        checkpoint = _create_new_checkpoint(
            checkpoint_manager, operation, operation_type, env, user_ids
        )
        print_info(
            f"Created checkpoint: {checkpoint.checkpoint_id}",
            operation=operation,
            checkpoint_id=checkpoint.checkpoint_id,
        )
    else:
        print_success(
            f"Resuming from checkpoint: {checkpoint.checkpoint_id}",
            operation=operation,
            checkpoint_id=checkpoint.checkpoint_id,
        )

    return checkpoint


def _try_load_existing_checkpoint(
    resume_checkpoint_id: str | None, checkpoint_manager: CheckpointManager
) -> Checkpoint | None:
    """Try to load an existing checkpoint with validation.

    Args:
        resume_checkpoint_id: Optional checkpoint ID to resume from
        checkpoint_manager: Checkpoint manager instance

    Returns:
        Optional[Checkpoint]: Valid checkpoint if found and resumable, None otherwise
    """
    if not resume_checkpoint_id:
        return None

    checkpoint = checkpoint_manager.load_checkpoint(resume_checkpoint_id)
    if not checkpoint:
        print_warning(
            f"Could not load checkpoint {resume_checkpoint_id}, starting fresh"
        )
        return None

    # Validate checkpoint status
    if checkpoint.status != CheckpointStatus.ACTIVE:
        print_warning(
            f"Checkpoint {resume_checkpoint_id} is not active (status: {checkpoint.status.value})"
        )
        return None

    # Validate checkpoint is resumable
    if not checkpoint.is_resumable():
        print_warning(
            f"Checkpoint {resume_checkpoint_id} is not resumable",
            operation="checkpoint_resume",
            checkpoint_id=resume_checkpoint_id,
        )
        return None

    return checkpoint


def _create_new_checkpoint(
    checkpoint_manager: CheckpointManager,
    operation: str,
    operation_type: OperationType,
    env: str,
    user_ids: list[str],
) -> Checkpoint:
    """Create a new checkpoint for the operation.

    Args:
        checkpoint_manager: Checkpoint manager instance
        operation: Operation to perform
        operation_type: Operation type enum
        env: Environment (dev/prod)
        user_ids: List of user IDs to process

    Returns:
        Checkpoint: Newly created checkpoint
    """
    # Create operation config
    config = OperationConfig(
        environment=env, additional_params={"operation": operation}
    )

    # Create new checkpoint
    return checkpoint_manager.create_checkpoint(
        operation_type=operation_type, config=config, items=user_ids, batch_size=50
    )


def _handle_checkpoint_error(
    checkpoint: Checkpoint,
    checkpoint_manager: CheckpointManager,
    operation: str,
    error: KeyboardInterrupt | Exception | None = None,
) -> str:
    """Handle checkpoint error by marking status and saving.

    Args:
        checkpoint: Checkpoint to handle
        checkpoint_manager: Checkpoint manager instance
        operation: Operation being performed
        error: Optional exception that occurred

    Returns:
        str: Checkpoint ID
    """
    if isinstance(error, KeyboardInterrupt):
        print_warning(f"\n{operation.title()} operation interrupted by user")
        checkpoint_manager.mark_checkpoint_cancelled(checkpoint)
        checkpoint_manager.save_checkpoint(checkpoint)
        print_info(
            f"Checkpoint saved: {checkpoint.checkpoint_id}",
            operation=operation,
            checkpoint_id=checkpoint.checkpoint_id,
        )
        print_info("You can resume this operation later using:", operation=operation)
        print_info(
            f"  deletepy resume {checkpoint.checkpoint_id}",
            operation=operation,
            checkpoint_id=checkpoint.checkpoint_id,
        )
    elif error is not None:
        print_warning(f"\n{operation.title()} operation failed: {error}")
        checkpoint_manager.mark_checkpoint_failed(checkpoint, str(error))
        checkpoint_manager.save_checkpoint(checkpoint)

    return checkpoint.checkpoint_id


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

    # Load or create checkpoint
    checkpoint = _load_or_create_checkpoint(
        resume_checkpoint_id,
        checkpoint_manager,
        operation,
        operation_type,
        env,
        user_ids,
    )

    # Use configuration from checkpoint if resuming
    if resume_checkpoint_id and checkpoint.config:
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
            checkpoint_manager=checkpoint_manager,
        )
    except (KeyboardInterrupt, Exception) as e:
        return _handle_checkpoint_error(checkpoint, checkpoint_manager, operation, e)


def _process_batch_user_operations_with_checkpoints(
    checkpoint: Checkpoint,
    token: str,
    base_url: str,
    operation: str,
    checkpoint_manager: CheckpointManager,
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

    operation_display = _get_operation_display_name(operation)
    print_info(f"{operation_display} - {len(remaining_user_ids)} remaining users...")

    # Initialize processing state
    tracking_state = _initialize_batch_processing_state()

    # Process remaining user IDs in batches
    interrupted_checkpoint_id = _process_batch_loop(
        remaining_user_ids,
        batch_size,
        checkpoint,
        checkpoint_manager,
        token,
        base_url,
        operation,
        tracking_state,
    )

    if interrupted_checkpoint_id:
        return interrupted_checkpoint_id

    # Finalize processing
    _finalize_batch_processing(
        checkpoint, checkpoint_manager, operation, tracking_state, token, base_url
    )

    return None  # Operation completed successfully


def _get_operation_display_name(operation: str) -> str:
    """Get display name for operation.

    Args:
        operation: Operation type

    Returns:
        str: Display name for the operation
    """
    return {
        "delete": "Deleting users",
        "block": "Blocking users",
        "revoke-grants-only": "Revoking grants and sessions",
    }.get(operation, "Processing users")


def _initialize_batch_processing_state() -> dict[str, Any]:
    """Initialize state tracking for batch processing.

    Returns:
        dict: Initialized tracking state
    """
    return {
        "multiple_users": {},
        "not_found_users": [],
        "invalid_user_ids": [],
    }


def _process_batch_loop(
    remaining_user_ids: list[str],
    batch_size: int,
    checkpoint: Checkpoint,
    checkpoint_manager: CheckpointManager,
    token: str,
    base_url: str,
    operation: str,
    tracking_state: dict[str, Any],
) -> str | None:
    """Process user IDs in batches with checkpoint management.

    Args:
        remaining_user_ids: List of user IDs to process
        batch_size: Size of each batch
        checkpoint: Checkpoint object
        checkpoint_manager: Checkpoint manager instance
        token: Auth0 access token
        base_url: Auth0 API base URL
        operation: Operation to perform
        tracking_state: State tracking dictionary

    Returns:
        Optional[str]: Checkpoint ID if interrupted, None if completed
    """
    for batch_start in range(0, len(remaining_user_ids), batch_size):
        if shutdown_requested():
            print_warning("\nOperation interrupted", operation=operation)
            checkpoint_manager.save_checkpoint(checkpoint)
            return checkpoint.checkpoint_id

        batch_end = min(batch_start + batch_size, len(remaining_user_ids))
        batch_user_ids = remaining_user_ids[batch_start:batch_end]

        current_batch = checkpoint.progress.current_batch + 1
        total_batches = checkpoint.progress.total_batches

        print_info(
            f"\nProcessing batch {current_batch}/{total_batches} "
            f"({batch_start + 1}-{batch_end} of {len(remaining_user_ids)} remaining)"
        )

        # Process and update batch
        _process_and_update_batch(
            batch_user_ids,
            checkpoint,
            checkpoint_manager,
            token,
            base_url,
            operation,
            tracking_state,
        )

    return None


def _process_and_update_batch(
    batch_user_ids: list[str],
    checkpoint: Checkpoint,
    checkpoint_manager: CheckpointManager,
    token: str,
    base_url: str,
    operation: str,
    tracking_state: dict[str, Any],
) -> None:
    """Process a single batch and update checkpoint.

    Args:
        batch_user_ids: User IDs in this batch
        checkpoint: Checkpoint object
        checkpoint_manager: Checkpoint manager instance
        token: Auth0 access token
        base_url: Auth0 API base URL
        operation: Operation to perform
        tracking_state: State tracking dictionary
    """
    # Process users in this batch
    batch_results = _process_user_batch(batch_user_ids, token, base_url, operation)

    # Update tracking lists
    tracking_state["multiple_users"].update(batch_results.get("multiple_users", {}))
    tracking_state["not_found_users"].extend(batch_results.get("not_found_users", []))
    tracking_state["invalid_user_ids"].extend(batch_results.get("invalid_user_ids", []))

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
        results_update=results_update,
    )

    # Save checkpoint after each batch
    checkpoint_manager.save_checkpoint(checkpoint)


def _finalize_batch_processing(
    checkpoint: Checkpoint,
    checkpoint_manager: CheckpointManager,
    operation: str,
    tracking_state: dict[str, Any],
    token: str,
    base_url: str,
) -> None:
    """Finalize batch processing with summary and completion.

    Args:
        checkpoint: Checkpoint object
        checkpoint_manager: Checkpoint manager instance
        operation: Operation that was performed
        tracking_state: State tracking dictionary
        token: Auth0 access token
        base_url: Auth0 API base URL
    """
    # Display operation summary
    _print_user_operation_summary(
        checkpoint.results.processed_count,
        checkpoint.results.skipped_count,
        tracking_state["not_found_users"],
        tracking_state["invalid_user_ids"],
        tracking_state["multiple_users"],
        token,
        base_url,
    )

    # Mark checkpoint as completed
    checkpoint.status = CheckpointStatus.COMPLETED
    checkpoint_manager.save_checkpoint(checkpoint)

    print_success(
        f"{operation.title()} operation completed! Checkpoint: {checkpoint.checkpoint_id}"
    )


def _process_users_in_batch(
    user_ids: list[str],
    token: str,
    base_url: str,
    operation: str,
    results: dict[str, Any],
) -> dict[str, Any]:
    """Process users in a batch, handling user resolution and operation execution.

    Args:
        user_ids: List of user IDs to process
        token: Auth0 access token
        base_url: Auth0 API base URL
        operation: Operation to perform
        results: Results dictionary to update

    Returns:
        dict: Updated results dictionary
    """
    from ..utils.display_utils import shutdown_requested
    from ..utils.legacy_print import print_error

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

    return results


def _process_user_batch(
    user_ids: list[str], token: str, base_url: str, operation: str
) -> dict[str, Any]:
    """Process a batch of users for a specific operation.

    Args:
        user_ids: List of user IDs to process
        token: Auth0 access token
        base_url: Auth0 API base URL
        operation: Operation to perform

    Returns:
        dict: Processing results for this batch
    """
    results: dict[str, Any] = {
        "processed_count": 0,
        "skipped_count": 0,
        "multiple_users": {},
        "not_found_users": [],
        "invalid_user_ids": [],
    }

    # Process users using the extracted helper function
    results = _process_users_in_batch(user_ids, token, base_url, operation, results)

    print("\n")  # Clear progress line
    return results


def _resolve_user_identifier_for_batch(
    user_id: str, token: str, base_url: str, results: dict[str, Any]
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
    if "@" in user_id and user_id.count("@") == 1 and len(user_id.split("@")[1]) > 0:
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


def _execute_user_operation(
    operation: str, user_id: str, token: str, base_url: str
) -> None:
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


def _display_multiple_users_details(
    multiple_users: dict[str, list[str]],
    token: str,
    base_url: str,
    fetch_details: bool = True,
) -> None:
    """Display details for multiple users found for each email.

    Args:
        multiple_users: Dict of emails with multiple users
        token: Auth0 access token
        base_url: Auth0 API base URL
        fetch_details: Whether to fetch user details via API calls
    """
    from ..utils.display_utils import CYAN, RESET

    if not multiple_users:
        return

    print_info(f"\nFound {len(multiple_users)} emails with multiple users:")
    for email, user_ids in multiple_users.items():
        print_info(f"\n  {CYAN}{email}{RESET}:")
        for uid in user_ids:
            if fetch_details:
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
            else:
                print_info(f"    - {uid}")


def _print_user_operation_summary(
    processed_count: int,
    skipped_count: int,
    not_found_users: list[str],
    invalid_user_ids: list[str],
    multiple_users: dict[str, list[str]],
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

    # Display multiple users using the extracted helper function
    _display_multiple_users_details(multiple_users, token, base_url, fetch_details=True)
