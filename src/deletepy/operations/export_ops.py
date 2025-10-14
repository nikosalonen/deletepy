"""Export operations for Auth0 user management."""

import csv
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from ..models.checkpoint import (
    Checkpoint,
    CheckpointStatus,
    OperationConfig,
    OperationType,
)
from ..utils.checkpoint_manager import CheckpointManager
from ..utils.display_utils import (
    CYAN,
    GREEN,
    RED,
    RESET,
    YELLOW,
    show_progress,
    shutdown_requested,
)
from ..utils.legacy_print import print_info, print_success, print_warning
from ..utils.validators import InputValidator
from .user_ops import get_user_details, get_user_id_from_email


@dataclass
class ExportWithCheckpointsConfig:
    """Configuration for export operations with checkpoint support."""

    # Auth0/API configuration
    token: str
    base_url: str
    env: str = "dev"
    connection: str | None = None

    # Export configuration
    output_file: str = "users_last_login.csv"
    batch_size: int | None = None

    # Checkpoint configuration
    resume_checkpoint_id: str | None = None
    checkpoint_manager: CheckpointManager | None = None


def _validate_and_setup_export(
    emails: list[str], output_file: str, batch_size: int | None, connection: str | None
) -> tuple[int, float]:
    """Validate export parameters and setup configuration.

    Args:
        emails: List of email addresses to process
        output_file: Output CSV file path
        batch_size: Number of emails to process before writing to CSV (auto-calculated if None)
        connection: Optional connection filter

    Returns:
        Tuple[int, float]: (batch_size, estimated_time)

    Raises:
        PermissionError: If the output file path is not writable
        FileNotFoundError: If the output directory does not exist
    """
    # Validate output file path is writable
    try:
        output_dir = (
            os.path.dirname(output_file) if os.path.dirname(output_file) else "."
        )
        if not os.path.exists(output_dir):
            raise FileNotFoundError(f"Output directory does not exist: {output_dir}")

        # Test write access
        test_file = os.path.join(output_dir, ".test_write")
        with open(test_file, "w") as f:
            f.write("test")
        os.remove(test_file)
    except (PermissionError, OSError) as e:
        raise PermissionError(f"Cannot write to output file {output_file}: {e}") from e

    # Auto-calculate batch size if not provided
    if batch_size is None:
        total_emails = len(emails)
        if total_emails <= 100:
            batch_size = 10
        elif total_emails <= 1000:
            batch_size = 50
        else:
            batch_size = 100

    # Estimate processing time (rough calculation)
    estimated_time = len(emails) * 0.5  # 0.5 seconds per email on average

    print(f"{YELLOW}Export Configuration:{RESET}")
    print(f"  Total emails: {len(emails)}")
    print(f"  Batch size: {batch_size}")
    print(f"  Output file: {output_file}")
    if connection:
        print(f"  Connection filter: {connection}")
    print(f"  Estimated time: {estimated_time:.1f} seconds")

    return batch_size, estimated_time


def _fetch_user_data(
    email: str, token: str, base_url: str, connection: str | None
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Fetch user data for a single identifier.

    The "email" parameter may be either an actual email address or an Auth0
    user ID (e.g., "auth0|...", "google-oauth2|...").

    Args:
        email: Email address or Auth0 user ID to fetch data for
        token: Auth0 access token
        base_url: Auth0 API base URL
        connection: Optional connection filter (only used for email lookups)

    Returns:
        Tuple[List[Dict[str, Any]], Dict[str, int]]: (user_data_list, counters)
    """
    counters = {
        "processed_count": 0,
        "not_found_count": 0,
        "multiple_users_count": 0,
        "error_count": 0,
    }

    try:
        # If input looks like an Auth0 user ID, skip email lookup and fetch directly
        looks_like_user_id = (
            "|" in email
            or InputValidator.validate_auth0_user_id_enhanced(email).is_valid
        )

        user_ids: list[str] = []
        if looks_like_user_id and "@" not in email:
            user_ids = [email]
        else:
            # Resolve email to user IDs
            resolved = get_user_id_from_email(email, token, base_url, connection)
            if not resolved:
                counters["not_found_count"] += 1
                return [], counters
            user_ids = resolved

        if not user_ids:
            counters["not_found_count"] += 1
            return [], counters

        if len(user_ids) > 1:
            counters["multiple_users_count"] += 1
            # For multiple users, we'll include all of them in the export

        # Fetch details for each user
        user_data_list = []
        for user_id in user_ids:
            user_details = get_user_details(user_id, token, base_url)
            if user_details:
                user_data_list.append(user_details)

        counters["processed_count"] += 1
        return user_data_list, counters

    except Exception as e:
        print(f"{RED}Error processing email {CYAN}{email}{RED}: {e}{RESET}")
        counters["error_count"] += 1
        return [], counters


def _process_email_batch(
    batch_emails: list[str],
    token: str,
    base_url: str,
    connection: str | None,
    batch_start: int,
    batch_number: int,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Process a batch of email addresses.

    Args:
        batch_emails: List of email addresses to process
        token: Auth0 access token
        base_url: Auth0 API base URL
        connection: Optional connection filter
        batch_start: Starting index of this batch
        batch_number: Batch number for display

    Returns:
        Tuple[List[Dict[str, Any]], Dict[str, int]]: (csv_data, batch_counters)
    """
    csv_data = []
    batch_counters = {
        "processed_count": 0,
        "not_found_count": 0,
        "multiple_users_count": 0,
        "error_count": 0,
    }

    for idx, email in enumerate(batch_emails, 1):
        if shutdown_requested():
            break

        show_progress(idx, len(batch_emails), f"Batch {batch_number}")

        user_data_list, email_counters = _fetch_user_data(
            email, token, base_url, connection
        )

        # Update batch counters
        for key in batch_counters:
            batch_counters[key] += email_counters[key]

        # Build CSV data for each user found
        for user_details in user_data_list:
            csv_row = _build_csv_data_dict(
                email, user_details.get("user_id", ""), user_details, "Found"
            )
            csv_data.append(csv_row)

        # If no users found, add a row with "Not Found" status
        if not user_data_list and email_counters["not_found_count"] > 0:
            csv_row = _build_csv_data_dict(email, "", None, "Not Found")
            csv_data.append(csv_row)

    return csv_data, batch_counters


def _write_csv_batch(
    csv_data: list[dict[str, Any]],
    output_file: str,
    batch_number: int,
    mode: str | None = None,
    write_headers: bool | None = None,
) -> bool:
    """Write CSV data to file.

    Args:
        csv_data: List of dictionaries containing CSV data
        output_file: Output CSV file path
        batch_number: Batch number for backup naming
        mode: Write mode ('w' for write, 'a' for append). If None, auto-determined.
        write_headers: Whether to write headers. If None, auto-determined.

    Returns:
        bool: True if successful, False otherwise
    """
    if not csv_data:
        return True

    try:
        # Auto-determine mode and write_headers if not provided (backward compatibility)
        if write_headers is None:
            write_headers = batch_number == 1 or not os.path.exists(output_file)

        if mode is None:
            mode = "w" if write_headers else "a"

        with open(output_file, mode, newline="", encoding="utf-8") as csvfile:
            fieldnames = [
                "email",
                "user_id",
                "connection",
                "last_login",
                "created_at",
                "updated_at",
                "status",
                "blocked",
                "email_verified",
                "identities_count",
            ]

            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

            if write_headers:
                writer.writeheader()

            for row in csv_data:
                writer.writerow(row)

        return True

    except Exception as e:
        print_warning(
            f"Error writing CSV batch {batch_number}: {e}",
            operation="export_csv",
            batch_number=batch_number,
            error=str(e),
        )
        return False


def _generate_export_summary(
    total_emails: int,
    processed_count: int,
    not_found_count: int,
    multiple_users_count: int,
    error_count: int,
    connection: str | None,
    output_file: str,
    csv_data: list[dict[str, Any]],
) -> None:
    """Generate and display export summary.

    Args:
        total_emails: Total number of emails processed
        processed_count: Number of emails successfully processed
        not_found_count: Number of emails not found
        multiple_users_count: Number of emails with multiple users
        error_count: Number of emails with errors
        connection: Connection filter used
        output_file: Output file path
        csv_data: Final CSV data
    """
    print(f"\n{GREEN}Export Summary:{RESET}")
    print(f"Total emails processed: {total_emails}")
    print(f"Successfully processed: {processed_count}")
    print(f"Not found: {not_found_count}")
    print(f"Multiple users: {multiple_users_count}")
    print(f"Errors: {error_count}")

    if connection:
        print(f"Connection filter: {connection}")

    print(f"Output file: {output_file}")
    print(f"Total CSV rows: {len(csv_data)}")

    # Show sample of data if available
    if csv_data:
        print(f"\n{YELLOW}Sample data:{RESET}")
        for i, row in enumerate(csv_data[:3]):  # Show first 3 rows
            print(f"  {i + 1}. {row['email']} -> {row['user_id']} ({row['status']})")


def _build_csv_data_dict(
    email: str, user_id: str, user_details: dict[str, Any] | None, status: str
) -> dict[str, Any]:
    """Build a dictionary for CSV export.

    Args:
        email: Email address
        user_id: User ID
        user_details: User details from Auth0 API
        status: Status string (Found, Not Found, etc.)

    Returns:
        Dict[str, Any]: Dictionary ready for CSV export
    """
    # Determine best email to display: prefer actual email from details if the
    # input identifier was a user_id (i.e., did not contain '@').
    display_email = email
    if user_details and "@" not in email:
        display_email = user_details.get("email", "")

    if user_details is None:
        return {
            "email": display_email if "@" in email else display_email,
            "user_id": user_id,
            "connection": "",
            "last_login": "",
            "created_at": "",
            "updated_at": "",
            "status": status,
            "blocked": "",
            "email_verified": "",
            "identities_count": "0",
        }

    # Extract last_login with proper formatting
    last_login = user_details.get("last_login", "")
    if last_login:
        try:
            # Parse and format the date
            dt = datetime.fromisoformat(last_login.replace("Z", "+00:00"))
            last_login = dt.strftime("%Y-%m-%d %H:%M:%S")
        except (ValueError, TypeError):
            # Keep original if parsing fails
            pass

    # Extract and format created_at
    created_at = user_details.get("created_at", "")
    if created_at:
        try:
            # Parse and format the date
            dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            created_at = dt.strftime("%Y-%m-%d %H:%M:%S")
        except (ValueError, TypeError):
            # Keep original if parsing fails
            pass

    # Extract and format updated_at
    updated_at = user_details.get("updated_at", "")
    if updated_at:
        try:
            # Parse and format the date
            dt = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
            updated_at = dt.strftime("%Y-%m-%d %H:%M:%S")
        except (ValueError, TypeError):
            # Keep original if parsing fails
            pass

    # Extract connection from identities
    connection = ""
    identities = user_details.get("identities", [])
    if identities and isinstance(identities, list):
        connection = identities[0].get("connection", "")

    return {
        "email": display_email if display_email else (email if "@" in email else ""),
        "user_id": user_id,
        "connection": connection,
        "last_login": last_login,
        "created_at": created_at,
        "updated_at": updated_at,
        "status": status,
        "blocked": str(user_details.get("blocked", False)),
        "email_verified": str(user_details.get("email_verified", False)),
        "identities_count": str(len(identities)),
    }


def export_users_last_login_to_csv_with_checkpoints(
    emails: list[str],
    config: ExportWithCheckpointsConfig,
) -> str | None:
    """Fetch user data for given emails and export last_login values to CSV with checkpointing.

    Args:
        emails: List of email addresses to process
        config: Configuration for the export operation

    Returns:
        Optional[str]: Checkpoint ID if operation was checkpointed, None if completed

    Raises:
        PermissionError: If the output file path is not writable
        FileNotFoundError: If the output directory does not exist
    """
    # Initialize checkpoint manager if not provided
    checkpoint_manager = config.checkpoint_manager
    if checkpoint_manager is None:
        checkpoint_manager = CheckpointManager()

    # Load or create checkpoint
    checkpoint = _load_or_create_export_checkpoint(emails, config, checkpoint_manager)

    # Save initial checkpoint
    checkpoint_manager.save_checkpoint(checkpoint)

    try:
        return _process_export_with_checkpoints(
            checkpoint=checkpoint,
            token=config.token,
            base_url=config.base_url,
            checkpoint_manager=checkpoint_manager,
        )
    except KeyboardInterrupt:
        return _handle_export_interruption(checkpoint, checkpoint_manager)
    except Exception as e:
        return _handle_export_error(checkpoint, checkpoint_manager, e)


def _load_or_create_export_checkpoint(
    emails: list[str],
    config: ExportWithCheckpointsConfig,
    checkpoint_manager: CheckpointManager,
) -> Checkpoint:
    """Load existing checkpoint or create a new one for export operation.

    Args:
        emails: List of email addresses to process
        config: Configuration for the export operation
        checkpoint_manager: Checkpoint manager instance

    Returns:
        Checkpoint: Loaded or newly created checkpoint
    """
    # Check if we're resuming from a checkpoint
    checkpoint = None
    if config.resume_checkpoint_id:
        checkpoint = _try_load_export_checkpoint(
            config.resume_checkpoint_id, checkpoint_manager
        )
        if checkpoint:
            _apply_checkpoint_config(checkpoint, config)
            print_success(
                f"Resuming from checkpoint: {checkpoint.checkpoint_id}",
                operation="export_resume",
                checkpoint_id=checkpoint.checkpoint_id,
            )
            return checkpoint

    # Create new checkpoint
    checkpoint = _create_new_export_checkpoint(emails, config, checkpoint_manager)
    print_info(
        f"Created checkpoint: {checkpoint.checkpoint_id}",
        operation="export_create_checkpoint",
        checkpoint_id=checkpoint.checkpoint_id,
    )
    return checkpoint


def _try_load_export_checkpoint(
    resume_checkpoint_id: str, checkpoint_manager: CheckpointManager
) -> Checkpoint | None:
    """Try to load an existing export checkpoint.

    Args:
        resume_checkpoint_id: Checkpoint ID to resume from
        checkpoint_manager: Checkpoint manager instance

    Returns:
        Optional[Checkpoint]: Loaded checkpoint if valid, None otherwise
    """
    checkpoint = checkpoint_manager.load_checkpoint(resume_checkpoint_id)
    if not checkpoint:
        print_warning(
            f"Could not load checkpoint {resume_checkpoint_id}, starting fresh"
        )
        return None

    if checkpoint.status != CheckpointStatus.ACTIVE:
        print_warning(
            f"Checkpoint {resume_checkpoint_id} is not active (status: {checkpoint.status.value})"
        )
        return None

    if not checkpoint.is_resumable():
        print_warning(
            f"Checkpoint {resume_checkpoint_id} is not resumable",
            operation="export_resume",
            checkpoint_id=resume_checkpoint_id,
        )
        return None

    return checkpoint


def _apply_checkpoint_config(
    checkpoint: Checkpoint, config: ExportWithCheckpointsConfig
) -> None:
    """Apply checkpoint configuration to the config object.

    Args:
        checkpoint: Checkpoint with configuration
        config: Configuration object to update
    """
    # Use configuration from checkpoint
    config.connection = checkpoint.config.connection_filter
    config.output_file = checkpoint.config.output_file or config.output_file


def _create_new_export_checkpoint(
    emails: list[str],
    config: ExportWithCheckpointsConfig,
    checkpoint_manager: CheckpointManager,
) -> Checkpoint:
    """Create a new checkpoint for export operation.

    Args:
        emails: List of email addresses to process
        config: Configuration for the export operation
        checkpoint_manager: Checkpoint manager instance

    Returns:
        Checkpoint: Newly created checkpoint

    Raises:
        ValueError: If configuration is invalid for export operation
    """
    # Ensure output_file is set with a default if not provided
    output_file = config.output_file
    if not output_file:
        from datetime import datetime

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"users_last_login_{timestamp}.csv"
        config.output_file = output_file

    # Validate and setup export parameters
    batch_size, estimated_time = _validate_and_setup_export(
        emails, output_file, config.batch_size, config.connection
    )

    # Create operation config with validated output_file
    operation_config = OperationConfig(
        environment=config.env,
        input_file=None,  # emails are passed directly
        output_file=output_file,
        connection_filter=config.connection,
        batch_size=batch_size,
        additional_params={"estimated_time": estimated_time},
    )

    # Create new checkpoint (this will now validate the configuration)
    return checkpoint_manager.create_checkpoint(
        operation_type=OperationType.EXPORT_LAST_LOGIN,
        config=operation_config,
        items=emails,
        batch_size=batch_size,
    )


def _handle_export_interruption(
    checkpoint: Checkpoint, checkpoint_manager: CheckpointManager
) -> str:
    """Handle export operation interruption.

    Args:
        checkpoint: Checkpoint to handle
        checkpoint_manager: Checkpoint manager instance

    Returns:
        str: Checkpoint ID
    """
    print_warning(
        "\nExport operation interrupted by user", operation="export_interrupt"
    )
    checkpoint_manager.mark_checkpoint_cancelled(checkpoint)
    checkpoint_manager.save_checkpoint(checkpoint)
    print_info(
        f"Checkpoint saved: {checkpoint.checkpoint_id}",
        operation="export_interrupt",
        checkpoint_id=checkpoint.checkpoint_id,
    )
    print_info(
        "You can resume this operation later using:", operation="export_interrupt"
    )
    print_info(
        f"  deletepy resume {checkpoint.checkpoint_id}",
        operation="export_interrupt",
        checkpoint_id=checkpoint.checkpoint_id,
    )
    return checkpoint.checkpoint_id


def _handle_export_error(
    checkpoint: Checkpoint, checkpoint_manager: CheckpointManager, error: Exception
) -> str:
    """Handle export operation error.

    Args:
        checkpoint: Checkpoint to handle
        checkpoint_manager: Checkpoint manager instance
        error: Exception that occurred

    Returns:
        str: Checkpoint ID
    """
    print_warning(
        f"\nExport operation failed: {error}",
        operation="export_failed",
        error=str(error),
    )
    checkpoint_manager.mark_checkpoint_failed(checkpoint, str(error))
    checkpoint_manager.save_checkpoint(checkpoint)
    return checkpoint.checkpoint_id


def _process_export_with_checkpoints(
    checkpoint: Checkpoint,
    token: str,
    base_url: str,
    checkpoint_manager: CheckpointManager,
) -> str | None:
    """Process export operation with checkpointing support.

    Args:
        checkpoint: Checkpoint to process
        token: Auth0 access token
        base_url: Auth0 API base URL
        checkpoint_manager: Checkpoint manager instance

    Returns:
        Optional[str]: Checkpoint ID if operation was interrupted, None if completed
    """
    batch_size = checkpoint.progress.batch_size
    connection = checkpoint.config.connection_filter
    output_file = checkpoint.config.output_file

    # Validate output_file is not None (should be guaranteed by validation)
    if output_file is None:
        raise ValueError(
            "output_file should be validated during checkpoint creation/loading"
        )

    print_info(f"Processing {len(checkpoint.remaining_items)} remaining emails...")

    # Determine starting batch number and write mode
    current_batch_num = checkpoint.progress.current_batch + 1
    write_headers = current_batch_num == 1 or not Path(output_file).exists()

    # Process remaining emails in batches
    remaining_emails = checkpoint.remaining_items.copy()

    for batch_start in range(0, len(remaining_emails), batch_size):
        if shutdown_requested():
            print_warning("\nOperation interrupted", operation="export_batch_interrupt")
            checkpoint_manager.save_checkpoint(checkpoint)
            return checkpoint.checkpoint_id

        batch_end = min(batch_start + batch_size, len(remaining_emails))
        batch_emails = remaining_emails[batch_start:batch_end]

        total_batches = checkpoint.progress.total_batches

        print_info(
            f"\nProcessing batch {current_batch_num}/{total_batches} ({batch_start + 1}-{batch_end} of {len(remaining_emails)} remaining)"
        )

        # Process this batch
        batch_csv_data, batch_counters = _process_email_batch(
            batch_emails, token, base_url, connection, batch_start, current_batch_num
        )

        print("\n")  # Clear progress line

        # Write batch to CSV
        mode = "w" if write_headers else "a"
        success = _write_csv_batch(
            batch_csv_data, output_file, current_batch_num, mode, write_headers
        )

        if not success:
            error_msg = f"Failed to write CSV batch {current_batch_num}"
            checkpoint_manager.mark_checkpoint_failed(checkpoint, error_msg)
            checkpoint_manager.save_checkpoint(checkpoint)
            return checkpoint.checkpoint_id

        # Update checkpoint progress
        results_update = {
            "processed_count": batch_counters.get("processed_count", 0),
            "not_found_count": batch_counters.get("not_found_count", 0),
            "multiple_users_count": batch_counters.get("multiple_users_count", 0),
            "error_count": batch_counters.get("error_count", 0),
        }

        checkpoint_manager.update_checkpoint_progress(
            checkpoint=checkpoint,
            processed_items=batch_emails,
            results_update=results_update,
        )

        # Save checkpoint after each batch
        checkpoint_manager.save_checkpoint(checkpoint)

        write_headers = False  # Only write headers for first batch
        current_batch_num += 1

    # Mark checkpoint as completed
    checkpoint.status = CheckpointStatus.COMPLETED
    checkpoint_manager.save_checkpoint(checkpoint)

    # Generate final summary
    _generate_export_summary_from_checkpoint(checkpoint, output_file)

    print_success(
        f"Export completed! Checkpoint: {checkpoint.checkpoint_id}",
        operation="export_complete",
        checkpoint_id=checkpoint.checkpoint_id,
    )
    return None  # Operation completed successfully


def _generate_export_summary_from_checkpoint(
    checkpoint: Checkpoint, output_file: str
) -> None:
    """Generate and display export summary from checkpoint data.

    Args:
        checkpoint: Checkpoint containing export results
        output_file: Output file path
    """
    results = checkpoint.results
    config = checkpoint.config

    print_success("\nExport Summary:", operation="export_summary")
    print_info(
        f"Total emails processed: {checkpoint.progress.current_item}",
        operation="export_summary",
        total_processed=checkpoint.progress.current_item,
    )
    print_info(
        f"Successfully processed: {results.processed_count}",
        operation="export_summary",
        processed_count=results.processed_count,
    )
    print_info(
        f"Not found: {results.not_found_count}",
        operation="export_summary",
        not_found_count=results.not_found_count,
    )
    print_info(
        f"Multiple users: {results.multiple_users_count}",
        operation="export_summary",
        multiple_users_count=results.multiple_users_count,
    )
    print_info(
        f"Errors: {results.error_count}",
        operation="export_summary",
        error_count=results.error_count,
    )

    if config.connection_filter:
        print_info(
            f"Connection filter: {config.connection_filter}",
            operation="export_summary",
            connection_filter=config.connection_filter,
        )

    print_info(
        f"Output file: {output_file}",
        operation="export_summary",
        output_file=output_file,
    )

    # Calculate total CSV rows (might include multiple users per email)
    total_csv_rows = results.processed_count + results.not_found_count
    print_info(
        f"Total CSV rows: {total_csv_rows}",
        operation="export_summary",
        total_csv_rows=total_csv_rows,
    )

    success_rate = checkpoint.get_success_rate()
    if success_rate > 0:
        print_info(
            f"Success rate: {success_rate:.1f}%",
            operation="export_summary",
            success_rate=success_rate,
        )


def find_resumable_export_checkpoint(
    checkpoint_manager: CheckpointManager | None = None,
) -> Checkpoint | None:
    """Find the most recent resumable export checkpoint.

    Args:
        checkpoint_manager: Optional checkpoint manager instance

    Returns:
        Optional[Checkpoint]: Most recent resumable export checkpoint or None
    """
    if checkpoint_manager is None:
        checkpoint_manager = CheckpointManager()

    checkpoints = checkpoint_manager.list_checkpoints(
        operation_type=OperationType.EXPORT_LAST_LOGIN, status=CheckpointStatus.ACTIVE
    )

    # Return the most recent resumable checkpoint
    for checkpoint in checkpoints:
        if checkpoint.is_resumable():
            return checkpoint

    return None


@dataclass
class FetchEmailsConfig:
    """Configuration for fetch emails operations with checkpoint support."""

    # Auth0/API configuration
    token: str
    base_url: str
    env: str = "dev"

    # Export configuration
    output_file: str = "user_emails.csv"
    batch_size: int | None = None

    # Checkpoint configuration
    resume_checkpoint_id: str | None = None
    checkpoint_manager: CheckpointManager | None = None


def fetch_emails_with_checkpoints(
    user_ids: list[str],
    config: FetchEmailsConfig,
) -> str | None:
    """Fetch email addresses for given user IDs and export to CSV with checkpointing.

    Args:
        user_ids: List of Auth0 user IDs to process
        config: Configuration for the fetch operation

    Returns:
        Optional[str]: Checkpoint ID if operation was checkpointed, None if completed

    Raises:
        PermissionError: If the output file path is not writable
        FileNotFoundError: If the output directory does not exist
    """
    # Initialize checkpoint manager if not provided
    checkpoint_manager = config.checkpoint_manager
    if checkpoint_manager is None:
        checkpoint_manager = CheckpointManager()

    # Load or create checkpoint
    checkpoint = _load_or_create_fetch_checkpoint(user_ids, config, checkpoint_manager)

    # Save initial checkpoint
    checkpoint_manager.save_checkpoint(checkpoint)

    try:
        return _process_fetch_emails_with_checkpoints(
            checkpoint=checkpoint,
            token=config.token,
            base_url=config.base_url,
            checkpoint_manager=checkpoint_manager,
        )
    except KeyboardInterrupt:
        return _handle_fetch_interruption(checkpoint, checkpoint_manager)
    except Exception as e:
        return _handle_fetch_error(checkpoint, checkpoint_manager, e)


def _load_or_create_fetch_checkpoint(
    user_ids: list[str],
    config: FetchEmailsConfig,
    checkpoint_manager: CheckpointManager,
) -> Checkpoint:
    """Load existing checkpoint or create a new one for fetch emails operation.

    Args:
        user_ids: List of user IDs to process
        config: Configuration for the fetch operation
        checkpoint_manager: Checkpoint manager instance

    Returns:
        Checkpoint: Loaded or newly created checkpoint
    """
    # Check if we're resuming from a checkpoint
    checkpoint = None
    if config.resume_checkpoint_id:
        checkpoint = _try_load_fetch_checkpoint(
            config.resume_checkpoint_id, checkpoint_manager
        )
        if checkpoint:
            _apply_fetch_checkpoint_config(checkpoint, config)
            print_success(
                f"Resuming from checkpoint: {checkpoint.checkpoint_id}",
                operation="fetch_emails_resume",
                checkpoint_id=checkpoint.checkpoint_id,
            )
            return checkpoint

    # Create new checkpoint
    checkpoint = _create_new_fetch_checkpoint(user_ids, config, checkpoint_manager)
    print_info(
        f"Created checkpoint: {checkpoint.checkpoint_id}",
        operation="fetch_emails_create_checkpoint",
        checkpoint_id=checkpoint.checkpoint_id,
    )
    return checkpoint


def _try_load_fetch_checkpoint(
    resume_checkpoint_id: str, checkpoint_manager: CheckpointManager
) -> Checkpoint | None:
    """Try to load an existing fetch emails checkpoint.

    Args:
        resume_checkpoint_id: Checkpoint ID to resume from
        checkpoint_manager: Checkpoint manager instance

    Returns:
        Optional[Checkpoint]: Loaded checkpoint if valid, None otherwise
    """
    checkpoint = checkpoint_manager.load_checkpoint(resume_checkpoint_id)
    if not checkpoint:
        print_warning(
            f"Could not load checkpoint {resume_checkpoint_id}, starting fresh"
        )
        return None

    if checkpoint.status != CheckpointStatus.ACTIVE:
        print_warning(
            f"Checkpoint {resume_checkpoint_id} is not active (status: {checkpoint.status.value})"
        )
        return None

    if not checkpoint.is_resumable():
        print_warning(
            f"Checkpoint {resume_checkpoint_id} is not resumable",
            operation="fetch_emails_resume",
            checkpoint_id=resume_checkpoint_id,
        )
        return None

    return checkpoint


def _apply_fetch_checkpoint_config(
    checkpoint: Checkpoint, config: FetchEmailsConfig
) -> None:
    """Apply checkpoint configuration to the config object.

    Args:
        checkpoint: Checkpoint with configuration
        config: Configuration object to update
    """
    # Use configuration from checkpoint
    config.output_file = checkpoint.config.output_file or config.output_file


def _create_new_fetch_checkpoint(
    user_ids: list[str],
    config: FetchEmailsConfig,
    checkpoint_manager: CheckpointManager,
) -> Checkpoint:
    """Create a new checkpoint for fetch emails operation.

    Args:
        user_ids: List of user IDs to process
        config: Configuration for the fetch operation
        checkpoint_manager: Checkpoint manager instance

    Returns:
        Checkpoint: Newly created checkpoint

    Raises:
        ValueError: If configuration is invalid for fetch operation
    """
    # Ensure output_file is set with a default if not provided
    output_file = config.output_file
    if not output_file:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"user_emails_{timestamp}.csv"
        config.output_file = output_file

    # Validate and setup fetch parameters
    batch_size = config.batch_size
    if batch_size is None:
        total_users = len(user_ids)
        if total_users <= 100:
            batch_size = 10
        elif total_users <= 1000:
            batch_size = 50
        else:
            batch_size = 100

    # Create operation config with validated output_file
    operation_config = OperationConfig(
        environment=config.env,
        input_file=None,  # user_ids are passed directly
        output_file=output_file,
        batch_size=batch_size,
    )

    # Create new checkpoint
    return checkpoint_manager.create_checkpoint(
        operation_type=OperationType.FETCH_EMAILS,
        config=operation_config,
        items=user_ids,
        batch_size=batch_size,
    )


def _handle_fetch_interruption(
    checkpoint: Checkpoint, checkpoint_manager: CheckpointManager
) -> str:
    """Handle fetch emails operation interruption.

    Args:
        checkpoint: Checkpoint to handle
        checkpoint_manager: Checkpoint manager instance

    Returns:
        str: Checkpoint ID
    """
    print_warning(
        "\nFetch emails operation interrupted by user",
        operation="fetch_emails_interrupt",
    )
    checkpoint_manager.mark_checkpoint_cancelled(checkpoint)
    checkpoint_manager.save_checkpoint(checkpoint)
    print_info(
        f"Checkpoint saved: {checkpoint.checkpoint_id}",
        operation="fetch_emails_interrupt",
        checkpoint_id=checkpoint.checkpoint_id,
    )
    print_info(
        "You can resume this operation later using:", operation="fetch_emails_interrupt"
    )
    print_info(
        f"  deletepy checkpoint resume {checkpoint.checkpoint_id}",
        operation="fetch_emails_interrupt",
        checkpoint_id=checkpoint.checkpoint_id,
    )
    return checkpoint.checkpoint_id


def _handle_fetch_error(
    checkpoint: Checkpoint, checkpoint_manager: CheckpointManager, error: Exception
) -> str:
    """Handle fetch emails operation error.

    Args:
        checkpoint: Checkpoint to handle
        checkpoint_manager: Checkpoint manager instance
        error: Exception that occurred

    Returns:
        str: Checkpoint ID
    """
    print_warning(
        f"\nFetch emails operation failed: {error}",
        operation="fetch_emails_failed",
        error=str(error),
    )
    checkpoint_manager.mark_checkpoint_failed(checkpoint, str(error))
    checkpoint_manager.save_checkpoint(checkpoint)
    return checkpoint.checkpoint_id


def _process_fetch_emails_with_checkpoints(
    checkpoint: Checkpoint,
    token: str,
    base_url: str,
    checkpoint_manager: CheckpointManager,
) -> str | None:
    """Process fetch emails operation with checkpointing support.

    Args:
        checkpoint: Checkpoint to process
        token: Auth0 access token
        base_url: Auth0 API base URL
        checkpoint_manager: Checkpoint manager instance

    Returns:
        Optional[str]: Checkpoint ID if operation was interrupted, None if completed
    """

    batch_size = checkpoint.progress.batch_size
    output_file = checkpoint.config.output_file

    # Validate output_file is not None
    if output_file is None:
        raise ValueError(
            "output_file should be validated during checkpoint creation/loading"
        )

    print_info(f"Processing {len(checkpoint.remaining_items)} remaining user IDs...")

    # Determine starting batch number and write mode
    current_batch_num = checkpoint.progress.current_batch + 1
    write_headers = current_batch_num == 1 or not Path(output_file).exists()

    # Process remaining user IDs in batches
    remaining_user_ids = checkpoint.remaining_items.copy()

    for batch_start in range(0, len(remaining_user_ids), batch_size):
        if shutdown_requested():
            print_warning(
                "\nOperation interrupted", operation="fetch_emails_batch_interrupt"
            )
            checkpoint_manager.save_checkpoint(checkpoint)
            return checkpoint.checkpoint_id

        batch_end = min(batch_start + batch_size, len(remaining_user_ids))
        batch_user_ids = remaining_user_ids[batch_start:batch_end]

        total_batches = checkpoint.progress.total_batches

        print_info(
            f"\nProcessing batch {current_batch_num}/{total_batches} ({batch_start + 1}-{batch_end} of {len(remaining_user_ids)} remaining)"
        )

        # Process this batch
        batch_csv_data, batch_counters = _process_user_id_batch(
            batch_user_ids, token, base_url, batch_start, current_batch_num
        )

        print("\n")  # Clear progress line

        # Write batch to CSV
        mode = "w" if write_headers else "a"
        success = _write_fetch_csv_batch(
            batch_csv_data, output_file, current_batch_num, mode, write_headers
        )

        if not success:
            error_msg = f"Failed to write CSV batch {current_batch_num}"
            checkpoint_manager.mark_checkpoint_failed(checkpoint, error_msg)
            checkpoint_manager.save_checkpoint(checkpoint)
            return checkpoint.checkpoint_id

        # Update checkpoint progress
        results_update = {
            "processed_count": batch_counters.get("processed_count", 0),
            "error_count": batch_counters.get("error_count", 0),
        }

        checkpoint_manager.update_checkpoint_progress(
            checkpoint=checkpoint,
            processed_items=batch_user_ids,
            results_update=results_update,
        )

        # Save checkpoint after each batch
        checkpoint_manager.save_checkpoint(checkpoint)

        write_headers = False  # Only write headers for first batch
        current_batch_num += 1

    # Mark checkpoint as completed
    checkpoint.status = CheckpointStatus.COMPLETED
    checkpoint_manager.save_checkpoint(checkpoint)

    # Generate final summary
    _generate_fetch_summary_from_checkpoint(checkpoint, output_file)

    print_success(
        f"Fetch emails completed! Checkpoint: {checkpoint.checkpoint_id}",
        operation="fetch_emails_complete",
        checkpoint_id=checkpoint.checkpoint_id,
    )
    return None  # Operation completed successfully


def _process_user_id_batch(
    batch_user_ids: list[str],
    token: str,
    base_url: str,
    batch_start: int,
    batch_number: int,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Process a batch of user IDs to fetch emails.

    Args:
        batch_user_ids: List of user IDs to process
        token: Auth0 access token
        base_url: Auth0 API base URL
        batch_start: Starting index of this batch
        batch_number: Batch number for display

    Returns:
        Tuple[List[Dict[str, Any]], Dict[str, int]]: (csv_data, batch_counters)
    """
    from .user_ops import get_user_email

    csv_data = []
    batch_counters = {
        "processed_count": 0,
        "error_count": 0,
    }

    for idx, user_id in enumerate(batch_user_ids, 1):
        if shutdown_requested():
            break

        show_progress(idx, len(batch_user_ids), f"Batch {batch_number}")

        try:
            email = get_user_email(user_id, token, base_url)

            if email:
                csv_row = {
                    "user_id": user_id,
                    "email": email,
                    "status": "Found",
                }
                batch_counters["processed_count"] += 1
            else:
                csv_row = {
                    "user_id": user_id,
                    "email": "",
                    "status": "Not Found",
                }
                batch_counters["error_count"] += 1

            csv_data.append(csv_row)

        except Exception as e:
            print(f"{RED}Error processing user {CYAN}{user_id}{RED}: {e}{RESET}")
            csv_row = {
                "user_id": user_id,
                "email": "",
                "status": f"Error: {str(e)}",
            }
            csv_data.append(csv_row)
            batch_counters["error_count"] += 1

    return csv_data, batch_counters


def _write_fetch_csv_batch(
    csv_data: list[dict[str, Any]],
    output_file: str,
    batch_number: int,
    mode: str | None = None,
    write_headers: bool | None = None,
) -> bool:
    """Write CSV data to file for fetch emails operation.

    Args:
        csv_data: List of dictionaries containing CSV data
        output_file: Output CSV file path
        batch_number: Batch number for backup naming
        mode: Write mode ('w' for write, 'a' for append). If None, auto-determined.
        write_headers: Whether to write headers. If None, auto-determined.

    Returns:
        bool: True if successful, False otherwise
    """
    if not csv_data:
        return True

    try:
        # Auto-determine mode and write_headers if not provided
        if write_headers is None:
            write_headers = batch_number == 1 or not os.path.exists(output_file)

        if mode is None:
            mode = "w" if write_headers else "a"

        with open(output_file, mode, newline="", encoding="utf-8") as csvfile:
            fieldnames = ["user_id", "email", "status"]

            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

            if write_headers:
                writer.writeheader()

            for row in csv_data:
                writer.writerow(row)

        return True

    except Exception as e:
        print_warning(
            f"Error writing CSV batch {batch_number}: {e}",
            operation="fetch_emails_csv",
            batch_number=batch_number,
            error=str(e),
        )
        return False


def _generate_fetch_summary_from_checkpoint(
    checkpoint: Checkpoint, output_file: str
) -> None:
    """Generate and display fetch emails summary from checkpoint data.

    Args:
        checkpoint: Checkpoint containing fetch results
        output_file: Output file path
    """
    results = checkpoint.results

    print_success("\nFetch Emails Summary:", operation="fetch_emails_summary")
    print_info(
        f"Total user IDs processed: {checkpoint.progress.current_item}",
        operation="fetch_emails_summary",
        total_processed=checkpoint.progress.current_item,
    )
    print_info(
        f"Emails found: {results.processed_count}",
        operation="fetch_emails_summary",
        processed_count=results.processed_count,
    )
    print_info(
        f"Errors/Not found: {results.error_count}",
        operation="fetch_emails_summary",
        error_count=results.error_count,
    )

    print_info(
        f"Output file: {output_file}",
        operation="fetch_emails_summary",
        output_file=output_file,
    )

    success_rate = checkpoint.get_success_rate()
    if success_rate > 0:
        print_info(
            f"Success rate: {success_rate:.1f}%",
            operation="fetch_emails_summary",
            success_rate=success_rate,
        )
