"""Command handlers for CLI operations."""

import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, cast

import click
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)

from ..core.auth import get_access_token
from ..core.config import get_base_url
from ..models.checkpoint import Checkpoint, CheckpointStatus, OperationType
from ..operations.batch_ops import (
    CheckpointOperationConfig,
    check_unblocked_users_with_checkpoints,
    find_users_by_social_media_ids_with_checkpoints,
)
from ..operations.domain_ops import check_email_domains
from ..operations.export_ops import (
    ExportWithCheckpointsConfig,
    export_users_last_login_to_csv_with_checkpoints,
)
from ..operations.preview_ops import (
    preview_social_unlink_operations,
    preview_user_operations,
)
from ..operations.user_ops import (
    batch_user_operations_with_checkpoints,
    block_user,
    delete_user,
    get_user_email,
    get_user_id_from_email,
)
from ..utils.checkpoint_manager import CheckpointManager
from ..utils.display_utils import (
    CYAN,
    GREEN,
    RED,
    RESET,
    YELLOW,
    confirm_action,
)
from ..utils.file_utils import read_user_ids_generator
from ..utils.rich_utils import get_stderr_console


class OperationHandler:
    """Handles CLI operations for Auth0 user management.

    This class provides a centralized way to handle all Auth0 user management
    operations with proper error handling, progress tracking, and user feedback.
    """

    def __init__(self) -> None:
        """Initialize the operation handler."""

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
        task_description = "Fetching emails"
        with Progress(
            TextColumn("{task.description}", style="info"),
            BarColumn(),
            MofNCompleteColumn(),
            TextColumn("|"),
            TimeElapsedColumn(),
            TextColumn("remaining"),
            TimeRemainingColumn(),
            console=get_stderr_console(),
        ) as progress:
            task_id = progress.add_task(task_description, total=len(user_ids))
            for user_id in user_ids:
                email = get_user_email(user_id, token, base_url)
                if email:
                    emails.append(email)
                progress.advance(task_id)
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

    def _confirm_production_operation(
        self, operation: str, total_users: int, rotate_password: bool = False
    ) -> bool:
        """Confirm production operation with user.

        Args:
            operation: Operation type
            total_users: Number of users to process
            rotate_password: Whether password rotation is enabled

        Returns:
            bool: True if confirmed, False otherwise
        """
        from ..utils.display_utils import confirm_production_operation

        return confirm_production_operation(operation, total_users, rotate_password)

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
        from ..utils.validators import SecurityValidator

        # Sanitize user input first
        user_id = SecurityValidator.sanitize_user_input(user_id)

        if not user_id:
            state["skipped_count"] += 1
            return

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

    def _create_processing_results(self, state: dict[str, Any]) -> dict[str, Any]:
        """Create the final processing results dictionary.

        Args:
            state: Processing state with counters and lists

        Returns:
            Dict[str, Any]: Processing results
        """
        return {
            "processed_count": state["processed_count"],
            "skipped_count": state["skipped_count"],
            "not_found_users": state["not_found_users"],
            "invalid_user_ids": state["invalid_user_ids"],
            "multiple_users": state["multiple_users"],
        }

    def _resolve_user_identifier(
        self,
        user_id: str,
        token: str,
        base_url: str,
        multiple_users: dict[str, list[str]],
        not_found_users: list[str],
        invalid_user_ids: list[str],
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
        from ..utils.validators import InputValidator

        # If input looks like an email, validate and resolve to user_id
        if "@" in user_id:
            # Validate email format comprehensively
            email_result = InputValidator.validate_email_comprehensive(user_id)
            if not email_result.is_valid:
                invalid_user_ids.append(
                    f"{user_id} (invalid email: {email_result.error_message})"
                )
                return None

            # Show warnings if any
            if email_result.warnings:
                from ..utils.display_utils import print_warning

                for warning in email_result.warnings:
                    print_warning(f"Email validation warning for {user_id}: {warning}")

            resolved_ids = get_user_id_from_email(user_id, token, base_url)
            if not resolved_ids:
                not_found_users.append(user_id)
                return None

            if len(resolved_ids) > 1:
                multiple_users[user_id] = resolved_ids
                return None

            return resolved_ids[0]

        # Validate Auth0 user ID format using enhanced validation
        else:
            user_id_result = InputValidator.validate_auth0_user_id_enhanced(user_id)
            if not user_id_result.is_valid:
                invalid_user_ids.append(f"{user_id} ({user_id_result.error_message})")
                return None

            # Show warnings if any
            if user_id_result.warnings:
                from ..utils.display_utils import print_warning

                for warning in user_id_result.warnings:
                    print_warning(
                        f"User ID validation warning for {user_id}: {warning}"
                    )

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
            return cast(bool, result["success"])
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

            # Use checkpoint-enabled operation
            config = CheckpointOperationConfig(
                token=token,
                base_url=base_url,
                env=env,
            )

            checkpoint_id = check_unblocked_users_with_checkpoints(
                user_ids=user_ids, config=config
            )

            if checkpoint_id:
                click.echo(f"\n{YELLOW}Operation was interrupted. Resume with:{RESET}")
                click.echo(f"  deletepy checkpoint resume {checkpoint_id}")

        except KeyboardInterrupt:
            click.echo(
                f"\n{YELLOW}Check unblocked operation interrupted by user.{RESET}"
            )
            sys.exit(0)
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

            # For export operation, treat input as emails directly with validation
            from ..utils.validators import InputValidator, SecurityValidator

            emails = []
            for line in user_ids:
                sanitized_line = SecurityValidator.sanitize_user_input(line)
                if sanitized_line:
                    # Validate email format if it looks like an email
                    if "@" in sanitized_line:
                        email_result = InputValidator.validate_email_comprehensive(
                            sanitized_line
                        )
                        if email_result.is_valid:
                            emails.append(sanitized_line)
                            # Show warnings if any
                            if email_result.warnings:
                                for warning in email_result.warnings:
                                    click.echo(
                                        f"{YELLOW}Email validation warning for {sanitized_line}: {warning}{RESET}"
                                    )
                        else:
                            click.echo(
                                f"{RED}Invalid email skipped: {sanitized_line} - {email_result.error_message}{RESET}"
                            )
                    else:
                        # Treat as user ID or other identifier
                        emails.append(sanitized_line)

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

            # Use checkpoint-enabled operation
            config = ExportWithCheckpointsConfig(
                token=token,
                base_url=base_url,
                env=env,
                connection=connection,
                output_file=output_file,
                batch_size=batch_size,
            )

            checkpoint_id = export_users_last_login_to_csv_with_checkpoints(
                emails=emails, config=config
            )

            if checkpoint_id:
                click.echo(f"\n{YELLOW}Operation was interrupted. Resume with:{RESET}")
                click.echo(f"  deletepy checkpoint resume {checkpoint_id}")

        except KeyboardInterrupt:
            click.echo(f"\n{YELLOW}Export operation interrupted by user.{RESET}")
            sys.exit(0)
        except Exception as e:
            self._handle_operation_error(e, "Export last login")

    def handle_fetch_emails(self, input_file: Path, env: str) -> None:
        """Handle fetch emails operation."""
        try:
            base_url, token, user_ids = self._setup_auth_and_files(input_file, env)

            # For fetch emails operation, treat input as user IDs with validation
            from ..utils.validators import InputValidator, SecurityValidator

            validated_user_ids = []
            for line in user_ids:
                sanitized_line = SecurityValidator.sanitize_user_input(line)
                if sanitized_line:
                    # Validate user ID format
                    user_id_result = InputValidator.validate_auth0_user_id_enhanced(
                        sanitized_line
                    )
                    if user_id_result.is_valid:
                        validated_user_ids.append(sanitized_line)
                        # Show warnings if any
                        if user_id_result.warnings:
                            for warning in user_id_result.warnings:
                                click.echo(
                                    f"{YELLOW}User ID validation warning for {sanitized_line}: {warning}{RESET}"
                                )
                    else:
                        click.echo(
                            f"{RED}Invalid user ID skipped: {sanitized_line} - {user_id_result.error_message}{RESET}"
                        )

            if not validated_user_ids:
                click.echo("No valid user IDs found to process.")
                return

            # Setup export parameters
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"user_emails_{timestamp}.csv"

            click.echo(
                f"\n{CYAN}Fetching emails for {len(validated_user_ids)} user IDs...{RESET}"
            )
            click.echo(f"Output file: {GREEN}{output_file}{RESET}")

            # Use checkpoint-enabled operation
            from ..operations.export_ops import (
                FetchEmailsConfig,
                fetch_emails_with_checkpoints,
            )

            config = FetchEmailsConfig(
                token=token,
                base_url=base_url,
                env=env,
                output_file=output_file,
            )

            checkpoint_id = fetch_emails_with_checkpoints(
                user_ids=validated_user_ids, config=config
            )

            if checkpoint_id:
                click.echo(f"\n{YELLOW}Operation was interrupted. Resume with:{RESET}")
                click.echo(f"  deletepy checkpoint resume {checkpoint_id}")

        except KeyboardInterrupt:
            click.echo(f"\n{YELLOW}Fetch emails operation interrupted by user.{RESET}")
            sys.exit(0)
        except Exception as e:
            self._handle_operation_error(e, "Fetch emails")

    def handle_user_operations(
        self,
        input_file: Path,
        env: str,
        operation: str,
        dry_run: bool = False,
        rotate_password: bool = False,
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
                operation, total_users, rotate_password
            ):
                click.echo("Operation cancelled by user.")
                return

            click.echo(f"\n{CYAN}{operation_display}...{RESET}")

            # Use checkpoint-enabled batch operation
            checkpoint_id = batch_user_operations_with_checkpoints(
                user_ids=user_ids,
                token=token,
                base_url=base_url,
                operation=operation,
                env=env,
                rotate_password=rotate_password,
            )

            if checkpoint_id:
                click.echo(f"\n{YELLOW}Operation was interrupted. Resume with:{RESET}")
                click.echo(f"  deletepy checkpoint resume {checkpoint_id}")

        except Exception as e:
            self._handle_operation_error(e, f"User {operation}")

    def handle_unlink_social_ids(
        self, input_file: Path, env: str, dry_run: bool = False
    ) -> None:
        """Handle unlink social IDs operation."""
        try:
            base_url, token, user_ids = self._setup_auth_and_files(input_file, env)

            # For social media ID search, treat input as social media IDs with validation
            from ..utils.validators import SecurityValidator

            social_ids = []
            for line in user_ids:
                sanitized_line = SecurityValidator.sanitize_user_input(line)
                if sanitized_line:
                    social_ids.append(sanitized_line)

            if not social_ids:
                click.echo("No valid social media IDs found to search.")
                return

            if dry_run:
                # Run dry-run preview for social unlink
                self._handle_social_dry_run_preview(social_ids, token, base_url, env)
                return

            # Use checkpoint-enabled operation
            config = CheckpointOperationConfig(
                token=token,
                base_url=base_url,
                env=env,
            )

            checkpoint_id = find_users_by_social_media_ids_with_checkpoints(
                social_ids=social_ids, config=config, auto_delete=True
            )

            if checkpoint_id:
                click.echo(f"\n{YELLOW}Operation was interrupted. Resume with:{RESET}")
                click.echo(f"  deletepy checkpoint resume {checkpoint_id}")

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
                    default=False,
                ):
                    click.echo(
                        f"\n{CYAN}Proceeding with actual {operation} operation...{RESET}"
                    )
                    # Remove dry_run flag and call the actual operation
                    self._execute_actual_operation(user_ids, token, base_url, operation)
                else:
                    click.echo("Operation cancelled by user.")
            else:
                click.echo(
                    f"\n{YELLOW}No users would be processed. Operation cancelled.{RESET}"
                )

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

            total_operations = (
                results["users_to_delete"] + results["identities_to_unlink"]
            )

            # Ask for confirmation to proceed with actual operation
            if total_operations > 0:
                click.echo(f"\n{GREEN}Preview completed successfully!{RESET}")
                if confirm_action(
                    f"Do you want to proceed with the social unlink operation on {total_operations} items?",
                    default=False,
                ):
                    click.echo(
                        f"\n{CYAN}Proceeding with actual social unlink operation...{RESET}"
                    )
                    # Execute the actual operation with checkpoints
                    config = CheckpointOperationConfig(
                        token=token,
                        base_url=base_url,
                        env=env,
                    )

                    checkpoint_id = find_users_by_social_media_ids_with_checkpoints(
                        social_ids=social_ids, config=config, auto_delete=True
                    )

                    if checkpoint_id:
                        click.echo(
                            f"\n{YELLOW}Operation was interrupted. Resume with:{RESET}"
                        )
                        click.echo(f"  deletepy checkpoint resume {checkpoint_id}")
                else:
                    click.echo("Operation cancelled by user.")
            else:
                click.echo(
                    f"\n{YELLOW}No operations would be performed. Operation cancelled.{RESET}"
                )

        except Exception as e:
            click.echo(f"{RED}Error during dry-run preview: {e}{RESET}", err=True)

    def _execute_actual_operation(
        self, user_ids: list[str], token: str, base_url: str, operation: str
    ) -> None:
        """Execute the actual operation after dry-run preview."""
        # Determine environment from base_url (simple heuristic)
        env = "prod" if "prod" in base_url or "p." in base_url else "dev"

        # Use checkpoint-enabled batch operation
        checkpoint_id = batch_user_operations_with_checkpoints(
            user_ids=user_ids,
            token=token,
            base_url=base_url,
            operation=operation,
            env=env,
        )

        if checkpoint_id:
            click.echo(f"\n{YELLOW}Operation was interrupted. Resume with:{RESET}")
            click.echo(f"  deletepy checkpoint resume {checkpoint_id}")

    def _print_domain_results(self, results: dict[str, Any], emails: list[str]) -> None:
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
        """Print summary of operation results.

        Args:
            processed_count: Number of users processed
            skipped_count: Number of users skipped
            not_found_users: List of users not found
            invalid_user_ids: List of invalid user IDs
            multiple_users: Dictionary of emails with multiple users
            token: Auth0 access token
            base_url: Auth0 API base URL
        """
        click.echo(f"\n{CYAN}Operation Summary:{RESET}")
        click.echo(f"Processed: {processed_count}")
        click.echo(f"Skipped: {skipped_count}")

        if not_found_users:
            click.echo(f"Not found: {len(not_found_users)}")
            for user in not_found_users:
                click.echo(f"  - {user}")

        if invalid_user_ids:
            click.echo(f"Invalid user IDs: {len(invalid_user_ids)}")
            for user_id in invalid_user_ids:
                click.echo(f"  - {user_id}")

        if multiple_users:
            click.echo(f"Multiple users found: {len(multiple_users)}")
            for email, user_ids in multiple_users.items():
                click.echo(f"  - {email}: {len(user_ids)} users")

    def _parse_operation_type(self, operation_type: str | None) -> OperationType | None:
        """Parse operation type string to enum.

        Args:
            operation_type: Operation type string to parse

        Returns:
            OperationType: Corresponding enum value or None if not found
        """
        if not operation_type:
            return None

        op_type_map = {
            "export-last-login": OperationType.EXPORT_LAST_LOGIN,
            "fetch-emails": OperationType.FETCH_EMAILS,
            "batch-delete": OperationType.BATCH_DELETE,
            "batch-block": OperationType.BATCH_BLOCK,
            "batch-revoke-grants": OperationType.BATCH_REVOKE_GRANTS,
            "social-unlink": OperationType.SOCIAL_UNLINK,
            "check-unblocked": OperationType.CHECK_UNBLOCKED,
            "check-domains": OperationType.CHECK_DOMAINS,
        }
        return op_type_map.get(operation_type)

    def _parse_checkpoint_status(self, status: str | None) -> CheckpointStatus | None:
        """Parse checkpoint status string to enum.

        Args:
            status: Status string to parse

        Returns:
            CheckpointStatus: Corresponding enum value or None if not found
        """
        if not status:
            return None

        status_map = {
            "active": CheckpointStatus.ACTIVE,
            "completed": CheckpointStatus.COMPLETED,
            "failed": CheckpointStatus.FAILED,
            "cancelled": CheckpointStatus.CANCELLED,
        }
        return status_map.get(status)

    def handle_list_checkpoints(
        self,
        operation_type: str | None,
        status: str | None,
        env: str | None,
        details: bool,
    ) -> None:
        """Handle listing checkpoints."""
        try:
            manager = CheckpointManager()

            # Convert string parameters to enums
            op_type = self._parse_operation_type(operation_type)
            status_enum = self._parse_checkpoint_status(status)

            # Get checkpoints
            checkpoints = manager.list_checkpoints(
                operation_type=op_type, status=status_enum, environment=env
            )

            if not checkpoints:
                click.echo(
                    f"{YELLOW}No checkpoints found matching the criteria.{RESET}"
                )
                return

            if details:
                for checkpoint in checkpoints:
                    manager.display_checkpoint_details(checkpoint)
                    click.echo()  # Add spacing between checkpoints
            else:
                manager.display_checkpoints(checkpoints)

        except Exception as e:
            self._handle_operation_error(e, "List checkpoints")

    def handle_resume_checkpoint(
        self, checkpoint_id: str, input_file: Path | None
    ) -> None:
        """Handle resuming from a checkpoint."""
        try:
            manager = CheckpointManager()

            # Load checkpoint
            checkpoint = manager.load_checkpoint(checkpoint_id)
            if not checkpoint:
                click.echo(f"{RED}Checkpoint not found: {checkpoint_id}{RESET}")
                return

            # Check if checkpoint is resumable
            if not checkpoint.is_resumable():
                click.echo(
                    f"{RED}Cannot resume checkpoint {checkpoint_id}: {checkpoint.status.value}{RESET}"
                )
                return

            # Reactivate checkpoint if it was cancelled or failed
            if checkpoint.status in (
                CheckpointStatus.CANCELLED,
                CheckpointStatus.FAILED,
            ):
                manager.reactivate_checkpoint(checkpoint)

            # Override input file if provided
            if input_file:
                checkpoint.config.input_file = str(input_file)

            # Dispatch to appropriate operation
            self._dispatch_checkpoint_resume(checkpoint, manager)

        except Exception as e:
            self._handle_operation_error(e, "Resume checkpoint")

    def _dispatch_checkpoint_resume(
        self, checkpoint: Checkpoint, checkpoint_manager: CheckpointManager
    ) -> None:
        """Dispatch checkpoint resume to the appropriate operation function.

        Args:
            checkpoint: The checkpoint to resume
            checkpoint_manager: Checkpoint manager instance
        """
        operation_type = checkpoint.operation_type
        checkpoint_id = checkpoint.checkpoint_id

        click.echo(
            f"{CYAN}Resuming {operation_type.value} operation from checkpoint {checkpoint_id}...{RESET}"
        )

        if operation_type == OperationType.EXPORT_LAST_LOGIN:
            self._resume_export_last_login(checkpoint, checkpoint_manager)
        elif operation_type == OperationType.FETCH_EMAILS:
            self._resume_fetch_emails(checkpoint, checkpoint_manager)
        elif operation_type == OperationType.CHECK_UNBLOCKED:
            self._resume_check_unblocked(checkpoint, checkpoint_manager)
        elif operation_type == OperationType.SOCIAL_UNLINK:
            self._resume_social_unlink(checkpoint, checkpoint_manager)
        elif operation_type in [
            OperationType.BATCH_DELETE,
            OperationType.BATCH_BLOCK,
            OperationType.BATCH_REVOKE_GRANTS,
        ]:
            self._resume_batch_user_operations(checkpoint, checkpoint_manager)
        else:
            click.echo(
                f"{RED}Resume not supported for operation type: {operation_type.value}{RESET}"
            )
            return

    def _resume_export_last_login(
        self, checkpoint: Checkpoint, checkpoint_manager: CheckpointManager
    ) -> None:
        """Resume export last login operation from checkpoint.

        Args:
            checkpoint: The checkpoint to resume
            checkpoint_manager: Checkpoint manager instance
        """

        env = checkpoint.config.environment
        checkpoint_id = checkpoint.checkpoint_id

        # Handle case where output_file might be None for older checkpoints
        output_file = checkpoint.config.output_file
        if not output_file:
            # Generate a default output file for older checkpoints that lack this field
            from datetime import datetime

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"users_last_login_resumed_{timestamp}.csv"
            click.echo(
                f"{YELLOW}Warning: Checkpoint missing output_file, using: {output_file}{RESET}"
            )

        config = ExportWithCheckpointsConfig(
            token=get_access_token(env),
            base_url=get_base_url(env),
            output_file=output_file,
            connection=checkpoint.config.connection_filter,
            env=env,
            resume_checkpoint_id=checkpoint_id,
            checkpoint_manager=checkpoint_manager,
        )

        export_users_last_login_to_csv_with_checkpoints(
            emails=checkpoint.remaining_items,
            config=config,
        )

    def _resume_fetch_emails(
        self, checkpoint: Checkpoint, checkpoint_manager: CheckpointManager
    ) -> None:
        """Resume fetch emails operation from checkpoint.

        Args:
            checkpoint: The checkpoint to resume
            checkpoint_manager: Checkpoint manager instance
        """
        from ..operations.export_ops import (
            FetchEmailsConfig,
            fetch_emails_with_checkpoints,
        )

        env = checkpoint.config.environment
        checkpoint_id = checkpoint.checkpoint_id

        # Handle case where output_file might be None for older checkpoints
        output_file = checkpoint.config.output_file
        if not output_file:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"user_emails_resumed_{timestamp}.csv"
            click.echo(
                f"{YELLOW}Warning: Checkpoint missing output_file, using: {output_file}{RESET}"
            )

        config = FetchEmailsConfig(
            token=get_access_token(env),
            base_url=get_base_url(env),
            output_file=output_file,
            env=env,
            resume_checkpoint_id=checkpoint_id,
            checkpoint_manager=checkpoint_manager,
        )

        fetch_emails_with_checkpoints(
            user_ids=checkpoint.remaining_items,
            config=config,
        )

    def _resume_check_unblocked(
        self, checkpoint: Checkpoint, checkpoint_manager: CheckpointManager
    ) -> None:
        """Resume check unblocked users operation from checkpoint.

        Args:
            checkpoint: The checkpoint to resume
            checkpoint_manager: Checkpoint manager instance
        """

        env = checkpoint.config.environment
        checkpoint_id = checkpoint.checkpoint_id

        config = CheckpointOperationConfig(
            token=get_access_token(env),
            base_url=get_base_url(env),
            env=env,
            resume_checkpoint_id=checkpoint_id,
            checkpoint_manager=checkpoint_manager,
        )
        check_unblocked_users_with_checkpoints(
            user_ids=checkpoint.remaining_items, config=config
        )

    def _resume_social_unlink(
        self, checkpoint: Checkpoint, checkpoint_manager: CheckpointManager
    ) -> None:
        """Resume social unlink operation from checkpoint.

        Args:
            checkpoint: The checkpoint to resume
            checkpoint_manager: Checkpoint manager instance
        """

        env = checkpoint.config.environment
        checkpoint_id = checkpoint.checkpoint_id

        config = CheckpointOperationConfig(
            token=get_access_token(env),
            base_url=get_base_url(env),
            env=env,
            resume_checkpoint_id=checkpoint_id,
            checkpoint_manager=checkpoint_manager,
        )
        find_users_by_social_media_ids_with_checkpoints(
            social_ids=checkpoint.remaining_items,
            config=config,
            auto_delete=checkpoint.config.auto_delete,
        )

    def _resume_batch_user_operations(
        self, checkpoint: Checkpoint, checkpoint_manager: CheckpointManager
    ) -> None:
        """Resume batch user operations from checkpoint.

        Args:
            checkpoint: The checkpoint to resume
            checkpoint_manager: Checkpoint manager instance
        """

        env = checkpoint.config.environment
        checkpoint_id = checkpoint.checkpoint_id
        operation_type = checkpoint.operation_type

        operation_map = {
            OperationType.BATCH_DELETE: "delete",
            OperationType.BATCH_BLOCK: "block",
            OperationType.BATCH_REVOKE_GRANTS: "revoke-grants-only",
        }
        batch_user_operations_with_checkpoints(
            user_ids=checkpoint.remaining_items,
            token=get_access_token(env),
            base_url=get_base_url(env),
            operation=operation_map[operation_type],
            env=env,
            resume_checkpoint_id=checkpoint_id,
            checkpoint_manager=checkpoint_manager,
        )

    def _clean_all_checkpoints(self, manager: CheckpointManager, dry_run: bool) -> None:
        """Clean all checkpoints.

        Args:
            manager: Checkpoint manager instance
            dry_run: Whether to perform a dry run
        """
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

    def _clean_failed_checkpoints(self, manager: CheckpointManager) -> None:
        """Clean failed checkpoints.

        Args:
            manager: Checkpoint manager instance
        """
        # Clean only failed checkpoints
        deleted_count = manager.clean_failed_checkpoints()
        if deleted_count > 0:
            click.echo(f"{GREEN}Cleaned {deleted_count} failed checkpoints.{RESET}")
        else:
            click.echo(f"{YELLOW}No failed checkpoints found to clean.{RESET}")

    def _clean_completed_checkpoints(
        self, manager: CheckpointManager, dry_run: bool = False
    ) -> None:
        """Clean completed checkpoints.

        Args:
            manager: Checkpoint manager instance
            dry_run: Whether to perform a dry run
        """
        # Clean all completed checkpoints regardless of age
        deleted_count = manager.clean_completed_checkpoints(dry_run)
        if dry_run:
            if deleted_count > 0:
                click.echo(
                    f"{CYAN}Would delete {deleted_count} completed checkpoints.{RESET}"
                )
            else:
                click.echo(f"{YELLOW}No completed checkpoints found to clean.{RESET}")
        else:
            if deleted_count > 0:
                click.echo(
                    f"{GREEN}Cleaned {deleted_count} completed checkpoints.{RESET}"
                )
            else:
                click.echo(f"{YELLOW}No completed checkpoints found to clean.{RESET}")

    def _clean_old_checkpoints(
        self, manager: CheckpointManager, days_old: int, dry_run: bool
    ) -> None:
        """Clean old checkpoints.

        Args:
            manager: Checkpoint manager instance
            days_old: Number of days old to consider checkpoints for deletion
            dry_run: Whether to perform a dry run
        """
        # Clean old checkpoints
        if dry_run:
            checkpoints = manager.list_checkpoints()
            cutoff_date = datetime.now() - timedelta(days=days_old)
            old_checkpoints = [cp for cp in checkpoints if cp.created_at < cutoff_date]

            if old_checkpoints:
                click.echo(
                    f"{CYAN}Would delete {len(old_checkpoints)} checkpoints older than {days_old} days:{RESET}"
                )
                manager.display_checkpoints(old_checkpoints)
            else:
                click.echo(
                    f"{YELLOW}No checkpoints older than {days_old} days found.{RESET}"
                )
            return

        deleted_count = manager.clean_old_checkpoints(days_old)
        if deleted_count > 0:
            click.echo(f"{GREEN}Cleaned {deleted_count} old checkpoints.{RESET}")
        else:
            click.echo(f"{YELLOW}No old checkpoints found to clean.{RESET}")

    def handle_clean_checkpoints(
        self,
        clean_all: bool,
        failed: bool,
        completed: bool,
        days_old: int,
        dry_run: bool,
    ) -> None:
        """Handle cleaning checkpoints."""
        try:
            manager = CheckpointManager()

            if clean_all:
                self._clean_all_checkpoints(manager, dry_run)
            elif failed:
                self._clean_failed_checkpoints(manager)
            elif completed:
                self._clean_completed_checkpoints(manager, dry_run)
            else:
                self._clean_old_checkpoints(manager, days_old, dry_run)

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
                click.echo(
                    f"{GREEN}Checkpoint {checkpoint_id} deleted successfully.{RESET}"
                )
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
