"""Command handlers for CLI operations."""

import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import click

from ..core.auth import get_access_token
from ..core.config import get_base_url
from ..models.checkpoint import CheckpointStatus, OperationType
from ..operations.batch_ops import (
    check_unblocked_users,
    find_users_by_social_media_ids,
)
from ..operations.domain_ops import check_email_domains
from ..operations.export_ops import (
    export_users_last_login_to_csv,
)
from ..operations.preview_ops import (
    preview_social_unlink_operations,
    preview_user_operations,
)
from ..operations.user_ops import (
    block_user,
    delete_user,
    get_user_details,
    get_user_email,
    get_user_id_from_email,
)
from ..utils.auth_utils import validate_auth0_user_id
from ..utils.checkpoint_manager import CheckpointManager
from ..utils.display_utils import (
    CYAN,
    GREEN,
    RED,
    RESET,
    YELLOW,
    confirm_action,
    show_progress,
)
from ..utils.file_utils import read_user_ids_generator


class OperationHandler:
    """Handles CLI operations for Auth0 user management.

    This class provides a centralized way to handle all Auth0 user management
    operations with proper error handling, progress tracking, and user feedback.
    """

    def __init__(self):
        """Initialize the operation handler."""
        pass

    def _setup_auth_and_files(
        self, input_file: Path, env: str
    ) -> tuple[str, str, list[str]]:
        """Setup authentication and read user files.

        Args:
            input_file: Path to input file
            env: Environment ('dev' or 'prod')

        Returns:
            tuple: (base_url, token, user_ids)

        Raises:
            Exception: If setup fails
        """
        base_url = get_base_url(env)
        token = get_access_token(env)
        user_ids = list(read_user_ids_generator(str(input_file)))
        return base_url, token, user_ids

    def _handle_operation_error(self, error: Exception, operation_name: str) -> None:
        """Handle operation errors with consistent formatting.

        Args:
            error: The exception that occurred
            operation_name: Name of the operation that failed
        """
        click.echo(f"{RED}{operation_name} failed: {error}{RESET}", err=True)
        sys.exit(1)

    def _fetch_user_emails(
        self, user_ids: list[str], token: str, base_url: str
    ) -> list[str]:
        """Fetch email addresses for a list of user IDs.

        Args:
            user_ids: List of Auth0 user IDs
            token: Auth0 access token
            base_url: Auth0 API base URL

        Returns:
            list: Email addresses found
        """
        click.echo(f"\n{CYAN}Fetching user emails...{RESET}")
        emails = []
        total_users = len(user_ids)

        for idx, user_id in enumerate(user_ids, 1):
            show_progress(idx, total_users, "Fetching emails")
            email = get_user_email(user_id, token, base_url)
            if email:
                emails.append(email)
        click.echo("\n")  # Clear progress line
        return emails

    def _calculate_export_parameters(self, num_emails: int) -> tuple[int, float]:
        """Calculate optimal export parameters.

        Args:
            num_emails: Number of emails to process

        Returns:
            tuple: (batch_size, estimated_time_minutes)
        """
        from ..utils.request_utils import (
            get_estimated_processing_time,
            get_optimal_batch_size,
        )

        batch_size = get_optimal_batch_size(num_emails)
        estimated_time = get_estimated_processing_time(num_emails, batch_size)
        return batch_size, estimated_time

    def _display_export_info(
        self,
        num_emails: int,
        batch_size: int,
        estimated_time: float,
        connection: str | None,
        output_file: str,
    ) -> None:
        """Display export operation information.

        Args:
            num_emails: Number of emails to process
            batch_size: Batch size for processing
            estimated_time: Estimated processing time in minutes
            connection: Connection filter (if any)
            output_file: Output file name
        """
        click.echo(
            f"\n{CYAN}Exporting last_login data for {num_emails} users...{RESET}"
        )
        click.echo(f"Output file: {GREEN}{output_file}{RESET}")
        click.echo(f"Using batch size: {batch_size}")
        click.echo(f"Estimated processing time: {estimated_time:.1f} minutes")

        if connection:
            click.echo(f"Connection filter: {YELLOW}{connection}{RESET}")

    def _get_operation_display_name(self, operation: str) -> str:
        """Get display name for operation.

        Args:
            operation: Operation type

        Returns:
            str: Human-readable operation name
        """
        return {
            "block": "Blocking users",
            "delete": "Deleting users",
            "revoke-grants-only": "Revoking grants and sessions",
        }.get(operation, "Processing users")

    def _confirm_production_operation(self, operation: str, total_users: int) -> bool:
        """Confirm production operation with user.

        Args:
            operation: Operation type
            total_users: Number of users to process

        Returns:
            bool: True if confirmed, False otherwise
        """
        from ..utils.display_utils import confirm_production_operation

        return confirm_production_operation(operation, total_users)

    def _initialize_processing_state(self) -> dict[str, Any]:
        """Initialize the processing state tracking variables.

        Returns:
            dict: Initial processing state with counters and lists
        """
        return {
            "multiple_users": {},
            "not_found_users": [],
            "invalid_user_ids": [],
            "processed_count": 0,
            "skipped_count": 0,
        }

    def _process_single_user(
        self,
        user_id: str,
        token: str,
        base_url: str,
        operation: str,
        state: dict[str, Any],
    ) -> None:
        """Process a single user identifier.

        Args:
            user_id: User identifier to process
            token: Auth0 access token
            base_url: Auth0 API base URL
            operation: Operation to perform
            state: Processing state to update
        """
        user_id = user_id.strip()

        # Resolve email to user ID if needed
        resolved_user_id = self._resolve_user_identifier(
            user_id,
            token,
            base_url,
            state["multiple_users"],
            state["not_found_users"],
            state["invalid_user_ids"],
        )

        if resolved_user_id is None:
            state["skipped_count"] += 1
            return

        # Perform the operation
        self._execute_user_operation(operation, resolved_user_id, token, base_url)
        state["processed_count"] += 1

    def _create_processing_results(self, state: dict[str, Any]) -> dict:
        """Create the final processing results dictionary.

        Args:
            state: Processing state with counters and lists

        Returns:
            dict: Processing results
        """
        return {
            "processed_count": state["processed_count"],
            "skipped_count": state["skipped_count"],
            "not_found_users": state["not_found_users"],
            "invalid_user_ids": state["invalid_user_ids"],
            "multiple_users": state["multiple_users"],
        }

    def _process_users(
        self,
        user_ids: list[str],
        token: str,
        base_url: str,
        operation: str,
        operation_display: str,
    ) -> dict:
        """Process users for the specified operation.

        Args:
            user_ids: List of user IDs/emails to process
            token: Auth0 access token
            base_url: Auth0 API base URL
            operation: Operation to perform
            operation_display: Display name for progress

        Returns:
            dict: Processing results with counts and user lists
        """
        state = self._initialize_processing_state()
        total_users = len(user_ids)

        for idx, user_id in enumerate(user_ids, 1):
            show_progress(idx, total_users, operation_display)
            self._process_single_user(user_id, token, base_url, operation, state)

        click.echo("\n")  # Clear progress line
        return self._create_processing_results(state)

    def _resolve_user_identifier(
        self,
        user_id: str,
        token: str,
        base_url: str,
        multiple_users: dict,
        not_found_users: list,
        invalid_user_ids: list,
    ) -> str | None:
        """Resolve user identifier (email or user ID) to a valid user ID.

        Args:
            user_id: User identifier (email or Auth0 user ID)
            token: Auth0 access token
            base_url: Auth0 API base URL
            multiple_users: Dict to store emails with multiple users
            not_found_users: List to store emails that weren't found
            invalid_user_ids: List to store invalid user IDs

        Returns:
            Optional[str]: Valid user ID if found, None if should skip
        """
        # If input is an email, resolve to user_id
        if (
            "@" in user_id
            and user_id.count("@") == 1
            and len(user_id.split("@")[1]) > 0
        ):
            resolved_ids = get_user_id_from_email(user_id, token, base_url)
            if not resolved_ids:
                not_found_users.append(user_id)
                return None

            if len(resolved_ids) > 1:
                multiple_users[user_id] = resolved_ids
                return None

            return resolved_ids[0]

        # Validate Auth0 user ID format
        elif not validate_auth0_user_id(user_id):
            invalid_user_ids.append(user_id)
            return None

        return user_id

    def _execute_user_operation(
        self, operation: str, user_id: str, token: str, base_url: str
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
            from ..operations.user_ops import revoke_user_grants, revoke_user_sessions

            revoke_user_sessions(user_id, token, base_url)
            revoke_user_grants(user_id, token, base_url)

    def handle_doctor(self, env: str, test_api: bool = False) -> bool:
        """Handle doctor operation for testing Auth0 credentials.

        Args:
            env: Environment to test ('dev' or 'prod')
            test_api: Whether to test API access

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            from ..core.auth import doctor as auth_doctor
            from ..core.config import check_env_file

            check_env_file()
            result = auth_doctor(env, test_api)
            if result["success"]:
                click.echo(
                    f"{GREEN}✓ Auth0 credentials are valid for {env} environment{RESET}"
                )
                if test_api:
                    click.echo(f"{GREEN}✓ API access test successful{RESET}")
            else:
                click.echo(f"{RED}✗ Auth0 credentials test failed{RESET}", err=True)
            return result["success"]
        except Exception as e:
            click.echo(f"{RED}Doctor check failed: {e}{RESET}", err=True)
            return False

    def handle_check_unblocked(self, input_file: Path, env: str) -> None:
        """Handle check unblocked users operation."""
        try:
            base_url, token, user_ids = self._setup_auth_and_files(input_file, env)
            click.echo(
                f"\n{CYAN}Checking {len(user_ids)} users for blocked status...{RESET}"
            )
            check_unblocked_users(user_ids, token, base_url)
        except Exception as e:
            self._handle_operation_error(e, "Check unblocked users")

    def handle_check_domains(self, input_file: Path, env: str) -> None:
        """Handle check domains operation."""
        try:
            base_url, token, user_ids = self._setup_auth_and_files(input_file, env)
            emails = self._fetch_user_emails(user_ids, token, base_url)

            if not emails:
                click.echo("No valid emails found to check.")
                return

            click.echo(f"\n{CYAN}Checking {len(emails)} email domains...{RESET}")
            results = check_email_domains(emails)
            self._print_domain_results(results, emails)

        except Exception as e:
            self._handle_operation_error(e, "Check domains")

    def handle_export_last_login(
        self, input_file: Path, env: str, connection: str | None
    ) -> None:
        """Handle export last login operation."""
        try:
            base_url, token, user_ids = self._setup_auth_and_files(input_file, env)

            # For export operation, treat input as emails directly
            emails = [line.strip() for line in user_ids if line.strip()]

            if not emails:
                click.echo("No valid emails found to export.")
                return

            # Setup export parameters
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"users_last_login_{timestamp}.csv"

            batch_size, estimated_time = self._calculate_export_parameters(len(emails))

            # Display export information
            self._display_export_info(
                len(emails), batch_size, estimated_time, connection, output_file
            )

            export_users_last_login_to_csv(
                emails, token, base_url, output_file, batch_size, connection
            )

        except KeyboardInterrupt:
            click.echo(f"\n{YELLOW}Export operation interrupted by user.{RESET}")
            sys.exit(0)
        except Exception as e:
            self._handle_operation_error(e, "Export last login")

    def handle_user_operations(
        self, input_file: Path, env: str, operation: str, dry_run: bool = False
    ) -> None:
        """Handle user operations (block, delete, revoke-grants-only)."""
        try:
            base_url, token, user_ids = self._setup_auth_and_files(input_file, env)
            total_users = len(user_ids)

            # Get operation display name
            operation_display = self._get_operation_display_name(operation)

            if dry_run:
                # Run dry-run preview
                self._handle_dry_run_preview(user_ids, token, base_url, operation)
                return

            # Request confirmation for production environment
            if env == "prod" and not self._confirm_production_operation(
                operation, total_users
            ):
                click.echo("Operation cancelled by user.")
                return

            click.echo(f"\n{CYAN}{operation_display}...{RESET}")

            # Process users and collect results
            results = self._process_users(
                user_ids, token, base_url, operation, operation_display
            )

            # Print summary
            self._print_operation_summary(
                results["processed_count"],
                results["skipped_count"],
                results["not_found_users"],
                results["invalid_user_ids"],
                results["multiple_users"],
                token,
                base_url,
            )

        except Exception as e:
            self._handle_operation_error(e, f"User {operation}")

    def handle_unlink_social_ids(self, input_file: Path, env: str, dry_run: bool = False) -> None:
        """Handle unlink social IDs operation."""
        try:
            base_url, token, user_ids = self._setup_auth_and_files(input_file, env)

            # For social media ID search, treat input as social media IDs
            social_ids = [line.strip() for line in user_ids if line.strip()]

            if not social_ids:
                click.echo("No valid social media IDs found to search.")
                return

            if dry_run:
                # Run dry-run preview for social unlink
                self._handle_social_dry_run_preview(social_ids, token, base_url, env)
                return

            find_users_by_social_media_ids(
                social_ids, token, base_url, env, auto_delete=True
            )

        except KeyboardInterrupt:
            click.echo(f"\n{YELLOW}Social media ID search interrupted by user.{RESET}")
            sys.exit(0)
        except Exception as e:
            self._handle_operation_error(e, "Find social IDs")

    def _handle_dry_run_preview(
        self, user_ids: list[str], token: str, base_url: str, operation: str
    ) -> None:
        """Handle dry-run preview for user operations."""
        try:
            result = preview_user_operations(
                user_ids, token, base_url, operation, show_details=True
            )

            # Ask for confirmation to proceed with actual operation
            if result.success_count > 0:
                click.echo(f"\n{GREEN}Preview completed successfully!{RESET}")
                if confirm_action(
                    f"Do you want to proceed with {operation} operation on {result.success_count} users?",
                    default=False
                ):
                    click.echo(f"\n{CYAN}Proceeding with actual {operation} operation...{RESET}")
                    # Remove dry_run flag and call the actual operation
                    self._execute_actual_operation(user_ids, token, base_url, operation)
                else:
                    click.echo("Operation cancelled by user.")
            else:
                click.echo(f"\n{YELLOW}No users would be processed. Operation cancelled.{RESET}")

        except Exception as e:
            click.echo(f"{RED}Error during dry-run preview: {e}{RESET}", err=True)

    def _handle_social_dry_run_preview(
        self, social_ids: list[str], token: str, base_url: str, env: str
    ) -> None:
        """Handle dry-run preview for social unlink operations."""
        try:
            results = preview_social_unlink_operations(
                social_ids, token, base_url, show_details=True
            )

            total_operations = results['users_to_delete'] + results['identities_to_unlink']

            # Ask for confirmation to proceed with actual operation
            if total_operations > 0:
                click.echo(f"\n{GREEN}Preview completed successfully!{RESET}")
                if confirm_action(
                    f"Do you want to proceed with the social unlink operation on {total_operations} items?",
                    default=False
                ):
                    click.echo(f"\n{CYAN}Proceeding with actual social unlink operation...{RESET}")
                    # Execute the actual operation
                    find_users_by_social_media_ids(
                        social_ids, token, base_url, env, auto_delete=True
                    )
                else:
                    click.echo("Operation cancelled by user.")
            else:
                click.echo(f"\n{YELLOW}No operations would be performed. Operation cancelled.{RESET}")

        except Exception as e:
            click.echo(f"{RED}Error during dry-run preview: {e}{RESET}", err=True)

    def _execute_actual_operation(
        self, user_ids: list[str], token: str, base_url: str, operation: str
    ) -> None:
        """Execute the actual operation after dry-run preview."""
        operation_display = self._get_operation_display_name(operation)

        # Process users and collect results
        results = self._process_users(
            user_ids, token, base_url, operation, operation_display
        )

        # Print summary
        self._print_operation_summary(
            results["processed_count"],
            results["skipped_count"],
            results["not_found_users"],
            results["invalid_user_ids"],
            results["multiple_users"],
            token,
            base_url,
        )

    def _print_domain_results(self, results: dict, emails: list) -> None:
        """Print domain check results summary."""
        # Print summary
        blocked = [email for email, status in results.items() if "BLOCKED" in status]
        unresolvable = [
            email for email, status in results.items() if "UNRESOLVABLE" in status
        ]
        allowed = [email for email, status in results.items() if "ALLOWED" in status]
        ignored = [email for email, status in results.items() if "IGNORED" in status]
        invalid = [email for email, status in results.items() if "INVALID" in status]
        error = [email for email, status in results.items() if "ERROR" in status]

        click.echo("\nDomain Check Summary:")
        click.echo(f"Total emails checked: {len(emails)}")

        if blocked:
            click.echo(f"\nBlocked domains ({len(blocked)}):")
            for email in blocked:
                click.echo(f"  {email}")
        if unresolvable:
            click.echo(f"\nUnresolvable domains ({len(unresolvable)}):")
            for email in unresolvable:
                click.echo(f"  {email}")
        if allowed:
            click.echo(f"\nAllowed domains ({len(allowed)}):")
            for email in allowed:
                click.echo(f"  {email}")
        if ignored:
            click.echo(f"\nIgnored domains ({len(ignored)}):")
            for email in ignored:
                click.echo(f"  {email}")
        if invalid:
            click.echo(f"\nInvalid emails ({len(invalid)}):")
            for email in invalid:
                click.echo(f"  {email}")
        if error:
            click.echo(f"\nErrors checking domains ({len(error)}):")
            for email in error:
                click.echo(f"  {email}")

    def _print_operation_summary(
        self,
        processed_count: int,
        skipped_count: int,
        not_found_users: list[str],
        invalid_user_ids: list[str],
        multiple_users: dict[str, list[str]],
        token: str,
        base_url: str,
    ) -> None:
        """Print a summary of the operation results."""
        click.echo(f"\n{CYAN}Operation Summary:{RESET}")
        click.echo(f"  Total processed: {processed_count}")
        click.echo(f"  Skipped: {skipped_count}")

        if not_found_users:
            click.echo(f"  {RED}Not found: {len(not_found_users)}{RESET}")
            if click.confirm("Show not found users?"):
                for user_id in not_found_users:
                    click.echo(f"    - {user_id}")

        if invalid_user_ids:
            click.echo(f"  {RED}Invalid user IDs: {len(invalid_user_ids)}{RESET}")
            if click.confirm("Show invalid user IDs?"):
                for user_id in invalid_user_ids:
                    click.echo(f"    - {user_id}")

        if multiple_users:
            click.echo(f"  {YELLOW}Multiple users found: {len(multiple_users)}{RESET}")
            if click.confirm("Show multiple users?"):
                for identifier, users in multiple_users.items():
                    click.echo(f"    - {identifier}:")
                    for user_id in users:
                        # Get user details
                        user_details = get_user_details(user_id, token, base_url)
                        if user_details:
                            username = user_details.get("username", "N/A")
                            email = user_details.get("email", "N/A")
                            click.echo(f"      - {user_id} ({username}, {email})")
                        else:
                            click.echo(f"      - {user_id}")

    def handle_list_checkpoints(
        self,
        operation_type: str | None,
        status: str | None,
        env: str | None,
        details: bool
    ) -> None:
        """Handle listing checkpoints."""
        try:
            manager = CheckpointManager()

            # Convert string parameters to enums
            op_type = None
            if operation_type:
                op_type_map = {
                    "export-last-login": OperationType.EXPORT_LAST_LOGIN,
                    "batch-delete": OperationType.BATCH_DELETE,
                    "batch-block": OperationType.BATCH_BLOCK,
                    "batch-revoke-grants": OperationType.BATCH_REVOKE_GRANTS,
                    "social-unlink": OperationType.SOCIAL_UNLINK,
                    "check-unblocked": OperationType.CHECK_UNBLOCKED,
                    "check-domains": OperationType.CHECK_DOMAINS,
                }
                op_type = op_type_map.get(operation_type)

            status_enum = None
            if status:
                status_map = {
                    "active": CheckpointStatus.ACTIVE,
                    "completed": CheckpointStatus.COMPLETED,
                    "failed": CheckpointStatus.FAILED,
                    "cancelled": CheckpointStatus.CANCELLED,
                }
                status_enum = status_map.get(status)

            # Get checkpoints
            checkpoints = manager.list_checkpoints(
                operation_type=op_type,
                status=status_enum,
                environment=env
            )

            if not checkpoints:
                click.echo(f"{YELLOW}No checkpoints found matching the criteria.{RESET}")
                return

            if details:
                for checkpoint in checkpoints:
                    manager.display_checkpoint_details(checkpoint)
                    click.echo()  # Add spacing between checkpoints
            else:
                manager.display_checkpoints(checkpoints)

        except Exception as e:
            self._handle_operation_error(e, "List checkpoints")

    def handle_resume_checkpoint(self, checkpoint_id: str, input_file: Path | None) -> None:
        """Handle resuming from a checkpoint."""
        try:
            manager = CheckpointManager()

            # Load checkpoint
            checkpoint = manager.load_checkpoint(checkpoint_id)
            if not checkpoint:
                click.echo(f"{RED}Checkpoint not found: {checkpoint_id}{RESET}")
                return

            # Check if checkpoint is resumable
            if not checkpoint.can_resume():
                click.echo(f"{RED}Cannot resume checkpoint {checkpoint_id}: {checkpoint.status.value}{RESET}")
                return

            # Override input file if provided
            if input_file:
                checkpoint.config.input_files = [str(input_file)]

            # Resume based on operation type
            env = checkpoint.config.environment
            operation_type = checkpoint.operation_type

            click.echo(f"{CYAN}Resuming {operation_type.value} operation from checkpoint {checkpoint_id}...{RESET}")

            if operation_type == OperationType.EXPORT_LAST_LOGIN:
                from ..operations.export_ops import (
                    export_users_last_login_to_csv_with_checkpoints,
                )
                export_users_last_login_to_csv_with_checkpoints(
                    checkpoint_id=checkpoint_id,
                    env=env,
                    connection=checkpoint.config.parameters.get("connection")
                )
            elif operation_type == OperationType.CHECK_UNBLOCKED:
                from ..core.auth import get_access_token
                from ..core.config import get_base_url
                from ..operations.batch_ops import (
                    CheckpointOperationConfig,
                    check_unblocked_users_with_checkpoints,
                )

                config = CheckpointOperationConfig(
                    token=get_access_token(env),
                    base_url=get_base_url(env),
                    env=env,
                    resume_checkpoint_id=checkpoint_id
                )
                check_unblocked_users_with_checkpoints(
                    user_ids=[],  # Empty list as we're resuming from checkpoint
                    config=config
                )
            elif operation_type == OperationType.SOCIAL_UNLINK:
                from ..operations.batch_ops import (
                    CheckpointOperationConfig,
                    find_users_by_social_media_ids_with_checkpoints,
                )

                config = CheckpointOperationConfig(
                    token=get_access_token(env),
                    base_url=get_base_url(env),
                    env=env,
                    resume_checkpoint_id=checkpoint_id
                )
                find_users_by_social_media_ids_with_checkpoints(
                    social_ids=[],  # Empty list as we're resuming from checkpoint
                    config=config
                )
            elif operation_type in [OperationType.BATCH_DELETE, OperationType.BATCH_BLOCK, OperationType.BATCH_REVOKE_GRANTS]:
                from ..operations.user_ops import batch_user_operations_with_checkpoints
                operation_map = {
                    OperationType.BATCH_DELETE: "delete",
                    OperationType.BATCH_BLOCK: "block",
                    OperationType.BATCH_REVOKE_GRANTS: "revoke-grants-only",
                }
                batch_user_operations_with_checkpoints(
                    checkpoint_id=checkpoint_id,
                    env=env,
                    operation=operation_map[operation_type]
                )
            else:
                click.echo(f"{RED}Resume not supported for operation type: {operation_type.value}{RESET}")
                return

        except Exception as e:
            self._handle_operation_error(e, "Resume checkpoint")

    def handle_clean_checkpoints(
        self,
        clean_all: bool,
        failed: bool,
        days_old: int,
        dry_run: bool
    ) -> None:
        """Handle cleaning checkpoints."""
        try:
            manager = CheckpointManager()

            if clean_all:
                # Get all checkpoints
                checkpoints = manager.list_checkpoints()

                if not checkpoints:
                    click.echo(f"{YELLOW}No checkpoints found to clean.{RESET}")
                    return

                if dry_run:
                    click.echo(f"{CYAN}Would delete {len(checkpoints)} checkpoints:{RESET}")
                    manager.display_checkpoints(checkpoints)
                    return

                if not confirm_action(f"delete ALL {len(checkpoints)} checkpoints"):
                    click.echo(f"{YELLOW}Cleanup cancelled.{RESET}")
                    return

                # Delete all checkpoints
                deleted_count = 0
                for checkpoint in checkpoints:
                    if manager.delete_checkpoint(checkpoint.checkpoint_id):
                        deleted_count += 1

                click.echo(f"{GREEN}Deleted {deleted_count} checkpoints.{RESET}")

            elif failed:
                # Clean only failed checkpoints
                deleted_count = manager.clean_failed_checkpoints()
                if deleted_count > 0:
                    click.echo(f"{GREEN}Cleaned {deleted_count} failed checkpoints.{RESET}")
                else:
                    click.echo(f"{YELLOW}No failed checkpoints found to clean.{RESET}")

            else:
                # Clean old checkpoints
                if dry_run:
                    checkpoints = manager.list_checkpoints()
                    cutoff_date = datetime.now() - timedelta(days=days_old)
                    old_checkpoints = [cp for cp in checkpoints if cp.created_at < cutoff_date]

                    if old_checkpoints:
                        click.echo(f"{CYAN}Would delete {len(old_checkpoints)} checkpoints older than {days_old} days:{RESET}")
                        manager.display_checkpoints(old_checkpoints)
                    else:
                        click.echo(f"{YELLOW}No checkpoints older than {days_old} days found.{RESET}")
                    return

                deleted_count = manager.clean_old_checkpoints(days_old)
                if deleted_count > 0:
                    click.echo(f"{GREEN}Cleaned {deleted_count} old checkpoints.{RESET}")
                else:
                    click.echo(f"{YELLOW}No old checkpoints found to clean.{RESET}")

        except Exception as e:
            self._handle_operation_error(e, "Clean checkpoints")

    def handle_delete_checkpoint(self, checkpoint_id: str, confirm: bool) -> None:
        """Handle deleting a specific checkpoint."""
        try:
            manager = CheckpointManager()

            # Check if checkpoint exists
            checkpoint = manager.load_checkpoint(checkpoint_id)
            if not checkpoint:
                click.echo(f"{RED}Checkpoint not found: {checkpoint_id}{RESET}")
                return

            # Confirm deletion unless --confirm flag is used
            if not confirm:
                manager.display_checkpoint_details(checkpoint)
                if not confirm_action(f"delete checkpoint {checkpoint_id}"):
                    click.echo(f"{YELLOW}Deletion cancelled.{RESET}")
                    return

            # Delete the checkpoint
            if manager.delete_checkpoint(checkpoint_id):
                click.echo(f"{GREEN}Checkpoint {checkpoint_id} deleted successfully.{RESET}")
            else:
                click.echo(f"{RED}Failed to delete checkpoint {checkpoint_id}.{RESET}")

        except Exception as e:
            self._handle_operation_error(e, "Delete checkpoint")

    def handle_checkpoint_details(self, checkpoint_id: str) -> None:
        """Handle showing detailed checkpoint information."""
        try:
            manager = CheckpointManager()

            checkpoint = manager.load_checkpoint(checkpoint_id)
            if not checkpoint:
                click.echo(f"{RED}Checkpoint not found: {checkpoint_id}{RESET}")
                return

            manager.display_checkpoint_details(checkpoint)

        except Exception as e:
            self._handle_operation_error(e, "Show checkpoint details")
