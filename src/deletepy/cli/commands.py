"""Command handlers for CLI operations."""

import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import click
import requests

from ..core.auth import get_access_token
from ..core.config import get_base_url
from ..operations.batch_ops import check_unblocked_users, find_users_by_social_media_ids
from ..operations.domain_ops import check_email_domains
from ..operations.export_ops import export_users_last_login_to_csv
from ..operations.user_ops import block_user, delete_user, get_user_details, get_user_email, get_user_id_from_email
from ..utils.auth_utils import validate_auth0_user_id
from ..utils.display_utils import CYAN, GREEN, RED, RESET, YELLOW, show_progress
from ..utils.file_utils import read_user_ids_generator


class OperationHandler:
    """Handles CLI operations for Auth0 user management.
    
    This class provides a centralized way to handle all Auth0 user management
    operations with proper error handling, progress tracking, and user feedback.
    """

    def __init__(self):
        """Initialize the operation handler."""
        pass

    def _setup_auth_and_files(self, input_file: Path, env: str) -> tuple[str, str, list[str]]:
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

    def _fetch_user_emails(self, user_ids: list[str], token: str, base_url: str) -> list[str]:
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
        from ..utils.request_utils import get_optimal_batch_size, get_estimated_processing_time
        
        batch_size = get_optimal_batch_size(num_emails)
        estimated_time = get_estimated_processing_time(num_emails, batch_size)
        return batch_size, estimated_time

    def _display_export_info(self, num_emails: int, batch_size: int, estimated_time: float, 
                           connection: Optional[str], output_file: str) -> None:
        """Display export operation information.
        
        Args:
            num_emails: Number of emails to process
            batch_size: Batch size for processing
            estimated_time: Estimated processing time in minutes
            connection: Connection filter (if any)
            output_file: Output file name
        """
        click.echo(f"\n{CYAN}Exporting last_login data for {num_emails} users...{RESET}")
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

    def _process_users(self, user_ids: list[str], token: str, base_url: str, 
                      operation: str, operation_display: str) -> dict:
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
        multiple_users: dict[str, list[str]] = {}
        not_found_users: list[str] = []
        invalid_user_ids: list[str] = []
        processed_count: int = 0
        skipped_count: int = 0
        total_users = len(user_ids)

        for idx, user_id in enumerate(user_ids, 1):
            show_progress(idx, total_users, operation_display)
            user_id = user_id.strip()
            
            # Resolve email to user ID if needed
            resolved_user_id = self._resolve_user_identifier(
                user_id, token, base_url, multiple_users, not_found_users, invalid_user_ids
            )
            
            if resolved_user_id is None:
                skipped_count += 1
                continue

            # Perform the operation
            self._execute_user_operation(operation, resolved_user_id, token, base_url)
            processed_count += 1

        click.echo("\n")  # Clear progress line
        
        return {
            "processed_count": processed_count,
            "skipped_count": skipped_count,
            "not_found_users": not_found_users,
            "invalid_user_ids": invalid_user_ids,
            "multiple_users": multiple_users
        }

    def _resolve_user_identifier(self, user_id: str, token: str, base_url: str,
                                multiple_users: dict, not_found_users: list, 
                                invalid_user_ids: list) -> Optional[str]:
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
        if "@" in user_id and user_id.count("@") == 1 and len(user_id.split("@")[1]) > 0:
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

    def _execute_user_operation(self, operation: str, user_id: str, token: str, base_url: str) -> None:
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
            from ..operations.user_ops import revoke_user_sessions, revoke_user_grants
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
                click.echo(f"{GREEN}✓ Auth0 credentials are valid for {env} environment{RESET}")
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
            click.echo(f"\n{CYAN}Checking {len(user_ids)} users for blocked status...{RESET}")
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

    def handle_export_last_login(self, input_file: Path, env: str, connection: Optional[str]) -> None:
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
            self._display_export_info(len(emails), batch_size, estimated_time, connection, output_file)

            export_users_last_login_to_csv(
                emails, token, base_url, output_file, batch_size, connection
            )

        except KeyboardInterrupt:
            click.echo(f"\n{YELLOW}Export operation interrupted by user.{RESET}")
            sys.exit(0)
        except Exception as e:
            self._handle_operation_error(e, "Export last login")

    def handle_find_social_ids(self, input_file: Path, env: str) -> None:
        """Handle find social IDs operation."""
        try:
            base_url, token, user_ids = self._setup_auth_and_files(input_file, env)
            
            # For social media ID search, treat input as social media IDs
            social_ids = [line.strip() for line in user_ids if line.strip()]

            if not social_ids:
                click.echo("No valid social media IDs found to search.")
                return

            find_users_by_social_media_ids(
                social_ids, token, base_url, env, auto_delete=True
            )

        except KeyboardInterrupt:
            click.echo(f"\n{YELLOW}Social media ID search interrupted by user.{RESET}")
            sys.exit(0)
        except Exception as e:
            self._handle_operation_error(e, "Find social IDs")

    def handle_user_operations(self, input_file: Path, env: str, operation: str) -> None:
        """Handle user operations (block, delete, revoke-grants-only)."""
        try:
            base_url, token, user_ids = self._setup_auth_and_files(input_file, env)
            total_users = len(user_ids)

            # Get operation display name
            operation_display = self._get_operation_display_name(operation)

            # Request confirmation for production environment
            if env == "prod" and not self._confirm_production_operation(operation, total_users):
                click.echo("Operation cancelled by user.")
                return

            click.echo(f"\n{CYAN}{operation_display}...{RESET}")
            
            # Process users and collect results
            results = self._process_users(user_ids, token, base_url, operation, operation_display)
            
            # Print summary
            self._print_operation_summary(
                results["processed_count"], results["skipped_count"], 
                results["not_found_users"], results["invalid_user_ids"], 
                results["multiple_users"], token, base_url
            )

        except Exception as e:
            self._handle_operation_error(e, f"User {operation}")

    def _print_domain_results(self, results: dict, emails: list) -> None:
        """Print domain check results summary."""
        # Print summary
        blocked = [email for email, status in results.items() if "BLOCKED" in status]
        unresolvable = [email for email, status in results.items() if "UNRESOLVABLE" in status]
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
        base_url: str
    ) -> None:
        """Print operation summary."""
        click.echo("\nOperation Summary:")
        click.echo(f"Total users processed: {processed_count}")
        click.echo(f"Total users skipped: {skipped_count}")

        if not_found_users:
            click.echo(f"\nNot found users ({len(not_found_users)}):")
            for email in not_found_users:
                click.echo(f"  {CYAN}{email}{RESET}")

        if invalid_user_ids:
            click.echo(f"\nInvalid user IDs ({len(invalid_user_ids)}):")
            for user_id in invalid_user_ids:
                click.echo(f"  {CYAN}{user_id}{RESET}")

        if multiple_users:
            click.echo(f"\nFound {len(multiple_users)} emails with multiple users:")
            for email, user_ids in multiple_users.items():
                click.echo(f"\n  {CYAN}{email}{RESET}:")
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
                        click.echo(f"    - {uid} (Connection: {connection})")
                    else:
                        click.echo(f"    - {uid} (Connection: unknown)")