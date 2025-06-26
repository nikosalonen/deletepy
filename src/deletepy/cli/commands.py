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
from email_domain_checker import check_domains_status_for_emails
from ..operations.export_ops import export_users_last_login_to_csv
from ..operations.user_ops import block_user, delete_user, get_user_details, get_user_email, get_user_id_from_email
from ..utils.auth_utils import validate_auth0_user_id
from ..utils.display_utils import CYAN, GREEN, RED, RESET, YELLOW, show_progress
from ..utils.file_utils import read_user_ids_generator


class OperationHandler:
    """Handles CLI operations for Auth0 user management."""

    def handle_check_unblocked(self, input_file: Path, env: str) -> None:
        """Handle check unblocked users operation."""
        try:
            base_url = get_base_url(env)
            token = get_access_token(env)
            user_ids = list(read_user_ids_generator(str(input_file)))
            check_unblocked_users(user_ids, token, base_url)
        except Exception as e:
            click.echo(f"{RED}Error: {e}{RESET}", err=True)
            sys.exit(1)

    def handle_check_domains(self, input_file: Path, env: str) -> None:
        """Handle check domains operation."""
        try:
            base_url = get_base_url(env)
            token = get_access_token(env)
            user_ids = list(read_user_ids_generator(str(input_file)))
            total_users = len(user_ids)

            click.echo("\nFetching user emails...")
            emails = []
            for idx, user_id in enumerate(user_ids, 1):
                show_progress(idx, total_users, "Fetching emails")
                email = get_user_email(user_id, token, base_url)
                if email:
                    emails.append(email)
            click.echo("\n")  # Clear progress line

            if not emails:
                click.echo("No valid emails found to check.")
                sys.exit(0)

            click.echo(f"\nChecking {len(emails)} email domains...")
            results = check_domains_status_for_emails(emails)

            self._print_domain_results(results, emails)

        except Exception as e:
            click.echo(f"{RED}Error: {e}{RESET}", err=True)
            sys.exit(1)

    def handle_export_last_login(self, input_file: Path, env: str, connection: Optional[str]) -> None:
        """Handle export last login operation."""
        try:
            base_url = get_base_url(env)
            token = get_access_token(env)
            user_ids = list(read_user_ids_generator(str(input_file)))
            
            # For export operation, treat input as emails directly
            emails = [line.strip() for line in user_ids if line.strip()]

            if not emails:
                click.echo("No valid emails found to export.")
                sys.exit(0)

            # Generate output filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"users_last_login_{timestamp}.csv"

            # Import rate limiting functions
            from ..utils.request_utils import get_optimal_batch_size, get_estimated_processing_time

            # Calculate optimal batch size based on number of emails
            batch_size = get_optimal_batch_size(len(emails))
            estimated_time = get_estimated_processing_time(len(emails), batch_size)

            click.echo(f"\nExporting last_login data for {len(emails)} users...")
            click.echo(f"Using batch size: {batch_size}")
            click.echo(f"Estimated processing time: {estimated_time:.1f} minutes")

            if connection:
                click.echo(f"Connection filter: {connection}")

            export_users_last_login_to_csv(
                emails, token, base_url, output_file, batch_size, connection
            )

        except KeyboardInterrupt:
            click.echo(f"\n{YELLOW}Export operation interrupted by user.{RESET}")
            sys.exit(0)
        except Exception as e:
            click.echo(f"{RED}Export operation failed: {e}{RESET}", err=True)
            sys.exit(1)

    def handle_find_social_ids(self, input_file: Path, env: str) -> None:
        """Handle find social IDs operation."""
        try:
            base_url = get_base_url(env)
            token = get_access_token(env)
            user_ids = list(read_user_ids_generator(str(input_file)))
            
            # For social media ID search, treat input as social media IDs
            social_ids = [line.strip() for line in user_ids if line.strip()]

            if not social_ids:
                click.echo("No valid social media IDs found to search.")
                sys.exit(0)

            find_users_by_social_media_ids(
                social_ids, token, base_url, env, auto_delete=True
            )

        except KeyboardInterrupt:
            click.echo(f"\n{YELLOW}Social media ID search interrupted by user.{RESET}")
            sys.exit(0)
        except Exception as e:
            click.echo(f"{RED}Social media ID search failed: {e}{RESET}", err=True)
            sys.exit(1)

    def handle_user_operations(self, input_file: Path, env: str, operation: str) -> None:
        """Handle user operations (block, delete, revoke-grants-only)."""
        try:
            base_url = get_base_url(env)
            token = get_access_token(env)
            user_ids = list(read_user_ids_generator(str(input_file)))
            total_users = len(user_ids)

            # Process users one by one for operations
            operation_display = {
                "block": "Blocking users",
                "delete": "Deleting users",
                "revoke-grants-only": "Revoking grants and sessions",
            }.get(operation, "Processing users")

            # Request confirmation for production environment
            if env == "prod":
                from ..utils.display_utils import confirm_production_operation
                if not confirm_production_operation(operation, total_users):
                    click.echo("Operation cancelled by user.")
                    sys.exit(0)

            click.echo(f"\n{operation_display}...")
            multiple_users: dict[str, list[str]] = {}  # Store emails with multiple users
            not_found_users: list[str] = []  # Store emails that weren't found
            invalid_user_ids: list[str] = []  # Store invalid user IDs
            processed_count: int = 0
            skipped_count: int = 0

            for idx, user_id in enumerate(user_ids, 1):
                show_progress(idx, total_users, operation_display)
                # Trim whitespace
                user_id = user_id.strip()
                
                # If input is an email, resolve to user_id
                if (
                    "@" in user_id
                    and user_id.count("@") == 1
                    and len(user_id.split("@")[1]) > 0
                ):
                    resolved_ids = get_user_id_from_email(user_id, token, base_url)
                    if not resolved_ids:
                        not_found_users.append(user_id)
                        skipped_count += 1
                        continue

                    if len(resolved_ids) > 1:
                        multiple_users[user_id] = resolved_ids
                        skipped_count += 1
                        continue

                    user_id = resolved_ids[0]

                # Validate Auth0 user ID format (skip emails as they're already processed)
                elif not validate_auth0_user_id(user_id):
                    invalid_user_ids.append(user_id)
                    skipped_count += 1
                    continue

                # Perform the operation
                if operation == "block":
                    from ..operations.batch_ops import revoke_user_grants, revoke_user_sessions
                    block_user(user_id, token, base_url)
                elif operation == "delete":
                    delete_user(user_id, token, base_url)
                elif operation == "revoke-grants-only":
                    from ..operations.batch_ops import revoke_user_grants, revoke_user_sessions
                    # First revoke sessions, then grants
                    revoke_user_sessions(user_id, token, base_url)
                    revoke_user_grants(user_id, token, base_url)
                processed_count += 1

            click.echo("\n")  # Clear progress line

            # Print summary
            self._print_operation_summary(
                processed_count, skipped_count, not_found_users, 
                invalid_user_ids, multiple_users, token, base_url
            )

        except Exception as e:
            click.echo(f"{RED}Error: {e}{RESET}", err=True)
            sys.exit(1)

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