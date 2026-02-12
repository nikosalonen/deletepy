"""Preview operations for dry-run mode - shows what would happen without executing."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from rich.panel import Panel

from ..core.auth0_client import Auth0Client
from ..utils.auth_utils import validate_auth0_user_id
from ..utils.display_utils import (
    live_progress,
    shutdown_requested,
)
from ..utils.output import print_error, print_info, print_warning
from ..utils.rich_utils import create_table, get_console, print_table
from ..utils.validators import SecurityValidator
from .user_ops import get_user_details, get_user_id_from_email


@dataclass
class PreviewResult:
    """Result of a dry-run preview operation."""

    operation: str
    total_users: int
    valid_users: list[dict[str, Any]] = field(default_factory=list)
    invalid_user_ids: list[str] = field(default_factory=list)
    not_found_users: list[str] = field(default_factory=list)
    multiple_users: dict[str, list[str]] = field(default_factory=dict)
    blocked_users: list[str] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)

    @property
    def success_count(self) -> int:
        """Number of users that would be successfully processed."""
        return len(self.valid_users)

    @property
    def skip_count(self) -> int:
        """Number of users that would be skipped."""
        return (
            len(self.invalid_user_ids)
            + len(self.not_found_users)
            + len(self.multiple_users)
            + len(self.blocked_users)
            + len(self.errors)
        )

    @property
    def success_rate(self) -> float:
        """Success rate as percentage."""
        if self.total_users == 0:
            return 0.0
        return (self.success_count / self.total_users) * 100.0


def preview_user_operations(
    user_ids: list[str],
    client: Auth0Client,
    operation: str,
    show_details: bool = True,
) -> PreviewResult:
    """Preview what would happen during user operations without executing them.

    Args:
        user_ids: List of user IDs/emails to preview
        client: Auth0 API client
        operation: Operation type ('delete', 'block', 'revoke-grants-only')
        show_details: Whether to show detailed preview information

    Returns:
        PreviewResult: Summary of what would happen
    """
    result = PreviewResult(operation=operation, total_users=len(user_ids))

    console = get_console()
    console.print(
        f"\n[warning]🔍 DRY RUN PREVIEW — {operation.upper()}[/warning]"
        f"  [muted]({len(user_ids)} users)[/muted]"
    )

    with live_progress(len(user_ids), f"Analyzing users for {operation}") as advance:
        for user_id in user_ids:
            if shutdown_requested():
                break

            user_id = SecurityValidator.sanitize_user_input(user_id)
            if not user_id:
                advance()
                continue

            resolved_user_id = _resolve_user_identifier(user_id, client, result)

            if resolved_user_id:
                _process_resolved_user(user_id, resolved_user_id, client, result)

            advance()

    if show_details:
        _display_preview_results(result)

    return result


def _process_resolved_user(
    original_id: str,
    resolved_user_id: str,
    client: Auth0Client,
    result: PreviewResult,
) -> None:
    """Fetch user details and classify into valid, blocked, or error."""
    operation = result.operation
    try:
        user_details = get_user_details(resolved_user_id, client)

        if not user_details:
            print_warning(
                f"Could not fetch details for {resolved_user_id}",
                user_id=resolved_user_id,
                operation=operation,
            )
            result.errors.append(
                {
                    "identifier": original_id,
                    "error": "Could not fetch user details",
                    "timestamp": datetime.now(UTC).isoformat(),
                    "operation": operation,
                    "error_type": "user_details_fetch_failed",
                }
            )
            return

        _classify_user_result(resolved_user_id, user_details, result)
    except Exception as e:
        print_error(
            f"API error for {original_id}: {e}",
            user_id=original_id,
            operation=operation,
        )
        result.errors.append(
            {
                "identifier": original_id,
                "error": f"API error: {str(e)}",
                "timestamp": datetime.now(UTC).isoformat(),
                "operation": operation,
                "error_type": "api_exception",
            }
        )


def _classify_user_result(
    resolved_user_id: str,
    user_details: dict[str, Any],
    result: PreviewResult,
) -> None:
    """Classify a fetched user as valid or blocked and append to result."""
    operation = result.operation
    email = user_details.get("email", "")

    if _should_skip_user(user_details, operation):
        print_info(
            f"Would skip {resolved_user_id} ({email}) - already in target state",
            user_id=resolved_user_id,
            operation=operation,
        )
        result.blocked_users.append(resolved_user_id)
    else:
        print_info(
            f"Would {operation} {resolved_user_id} ({email})",
            user_id=resolved_user_id,
            operation=operation,
        )
        result.valid_users.append(
            {
                "user_id": resolved_user_id,
                "email": email,
                "connection": _get_user_connection(user_details),
                "blocked": user_details.get("blocked", False),
                "last_login": user_details.get("last_login", ""),
                "created_at": user_details.get("created_at", ""),
            }
        )


def _resolve_user_identifier(
    user_id: str,
    client: Auth0Client,
    result: PreviewResult,
) -> str | None:
    """Resolve user identifier (email or user ID) to a valid user ID."""
    # If input is an email, resolve to user_id
    if "@" in user_id and user_id.count("@") == 1 and len(user_id.split("@")[1]) > 0:
        try:
            resolved_ids = get_user_id_from_email(user_id, client)

            if not resolved_ids:
                result.not_found_users.append(user_id)
                return None

            if len(resolved_ids) > 1:
                result.multiple_users[user_id] = resolved_ids
                return None

            return resolved_ids[0]
        except Exception as e:
            result.errors.append(
                {
                    "identifier": user_id,
                    "error": f"Error resolving email: {str(e)}",
                    "timestamp": datetime.now(UTC).isoformat(),
                    "operation": result.operation,
                    "error_type": "email_resolution_failed",
                }
            )
            return None

    # Validate Auth0 user ID format
    elif not validate_auth0_user_id(user_id):
        result.invalid_user_ids.append(user_id)
        return None

    return user_id


def _should_skip_user(user_details: dict[str, Any], operation: str) -> bool:
    """Check if user should be skipped based on current state and operation."""
    if operation == "block":
        # Skip if user is already blocked
        blocked_status = user_details.get("blocked", False)
        return bool(blocked_status)

    # For delete and revoke-grants-only, we don't skip based on state
    return False


def _get_user_connection(user_details: dict[str, Any]) -> str:
    """Extract connection from user details."""
    identities = user_details.get("identities", [])
    if identities and isinstance(identities, list):
        connection = identities[0].get("connection", "unknown")
        return str(connection)
    return "unknown"


def _display_preview_results(result: PreviewResult) -> None:
    """Display detailed preview results using Rich formatting."""
    console = get_console()

    # --- Summary panel ---
    rate_style = "success" if result.success_rate > 90 else "warning"
    summary_lines = (
        f"[bold]{result.operation.upper()}[/bold]\n"
        f"\n"
        f"  [muted]Total analyzed:[/muted]  [count]{result.total_users}[/count]\n"
        f"  [muted]Would process:[/muted]   [success]{result.success_count}[/success]\n"
        f"  [muted]Would skip:[/muted]      [warning]{result.skip_count}[/warning]\n"
        f"  [muted]Success rate:[/muted]    [{rate_style}]{result.success_rate:.1f}%[/{rate_style}]"
    )
    console.print(
        Panel(
            summary_lines,
            title="📊 Dry Run Results",
            border_style="green",
            expand=False,
        )
    )

    # --- Valid users table ---
    if result.valid_users:
        table = create_table(
            title=f"✅ Would {result.operation} ({len(result.valid_users)})",
            columns=["#", "User ID", "Email", "Connection"],
        )
        for i, user in enumerate(result.valid_users[:10], 1):
            blocked = " [warning](BLOCKED)[/warning]" if user["blocked"] else ""
            table.add_row(
                str(i),
                f"[user_id]{user['user_id']}[/user_id]",
                user["email"] + blocked,
                f"[muted]{user['connection']}[/muted]",
            )
        if len(result.valid_users) > 10:
            table.add_row(
                "", f"[muted]… and {len(result.valid_users) - 10} more[/muted]", "", ""
            )
        print_table(table)

    # --- Skipped / errors ---
    _display_item_table(result.blocked_users, "⚠ Already in target state")
    _display_item_table(result.not_found_users, "✗ Not found")
    _display_item_table(result.invalid_user_ids, "✗ Invalid user IDs")
    _display_multiple_users(result.multiple_users)
    _display_error_table(result.errors)


def _display_item_table(items: list[str], title: str, limit: int = 5) -> None:
    """Display a short list of items as a compact table."""
    if not items:
        return

    table = create_table(title=f"{title} ({len(items)})")
    table.add_column("Identifier", style="user_id")
    for item in items[:limit]:
        table.add_row(item)
    if len(items) > limit:
        table.add_row(f"[muted]… and {len(items) - limit} more[/muted]")
    print_table(table)


def _display_multiple_users(multiple_users: dict[str, list[str]]) -> None:
    """Display emails with multiple users as a table."""
    if not multiple_users:
        return

    table = create_table(title=f"⚠ Emails with multiple users ({len(multiple_users)})")
    table.add_column("Email")
    table.add_column("User IDs")
    for email, user_ids in list(multiple_users.items())[:5]:
        table.add_row(email, ", ".join(user_ids))
    if len(multiple_users) > 5:
        table.add_row(f"[muted]… and {len(multiple_users) - 5} more[/muted]", "")
    print_table(table)


def _display_error_table(errors: list[dict[str, Any]]) -> None:
    """Display errors as a formatted table."""
    if not errors:
        return

    table = create_table(title=f"✗ Errors ({len(errors)})")
    table.add_column("Identifier", style="user_id")
    table.add_column("Error")
    table.add_column("Type", style="muted")
    for error in errors[:5]:
        table.add_row(
            error["identifier"],
            error["error"],
            error.get("error_type", "unknown"),
        )
    if len(errors) > 5:
        table.add_row(f"[muted]… and {len(errors) - 5} more[/muted]", "", "")
    print_table(table)


def preview_social_unlink_operations(
    social_ids: list[str],
    client: Auth0Client,
    show_details: bool = True,
) -> dict[str, Any]:
    """Preview what would happen during social identity unlink operations.

    Args:
        social_ids: List of social media IDs to preview
        client: Auth0 API client
        show_details: Whether to show detailed preview information

    Returns:
        dict: Preview results for social unlink operations
    """
    from .batch_ops import categorize_users, search_batch_social_ids

    console = get_console()
    console.print(
        f"\n[warning]🔍 DRY RUN PREVIEW — SOCIAL UNLINK[/warning]"
        f"  [muted]({len(social_ids)} social IDs)[/muted]"
    )

    # Search for users with each social ID
    found_users, not_found_ids = search_batch_social_ids(social_ids, client)

    # Categorize users
    users_to_delete, identities_to_unlink, auth0_main_protected = categorize_users(
        found_users, auto_delete=True
    )

    results = {
        "total_social_ids": len(social_ids),
        "found_users": len(found_users),
        "not_found_ids": len(not_found_ids),
        "users_to_delete": len(users_to_delete),
        "identities_to_unlink": len(identities_to_unlink),
        "auth0_main_protected": len(auth0_main_protected),
        "users_to_delete_list": users_to_delete,
        "identities_to_unlink_list": identities_to_unlink,
        "auth0_main_protected_list": auth0_main_protected,
        "not_found_ids_list": not_found_ids,
    }

    if show_details:
        _display_social_preview_results(results)

    return results


def _display_social_preview_results(results: dict[str, Any]) -> None:
    """Display detailed preview results for social unlink operations."""
    console = get_console()

    # --- Summary panel ---
    summary_lines = (
        f"[bold]SOCIAL UNLINK[/bold]\n"
        f"\n"
        f"  [muted]Total social IDs:[/muted]      [count]{results['total_social_ids']}[/count]\n"
        f"  [muted]Users found:[/muted]            [success]{results['found_users']}[/success]\n"
        f"  [muted]Not found:[/muted]              [warning]{results['not_found_ids']}[/warning]\n"
        f"\n"
        f"  [muted]Would delete:[/muted]           [info]{results['users_to_delete']}[/info]\n"
        f"  [muted]Would unlink:[/muted]           [info]{results['identities_to_unlink']}[/info]\n"
        f"  [muted]Protected (skipped):[/muted]    [warning]{results['auth0_main_protected']}[/warning]"
    )
    console.print(
        Panel(
            summary_lines,
            title="📊 Dry Run Results",
            border_style="green",
            expand=False,
        )
    )

    # --- Category tables ---
    _display_social_user_table(results["users_to_delete_list"], "✅ Would delete")
    _display_social_user_table(results["identities_to_unlink_list"], "🔗 Would unlink")
    _display_social_user_table(
        results["auth0_main_protected_list"], "🛡 Protected (skipped)"
    )


def _display_social_user_table(
    user_list: list[dict[str, str]], title: str, limit: int = 10
) -> None:
    """Display a list of social users as a formatted table."""
    if not user_list:
        return

    table = create_table(title=f"{title} ({len(user_list)})")
    table.add_column("User ID", style="user_id")
    table.add_column("Email")
    table.add_column("Reason", style="muted")
    for user in user_list[:limit]:
        table.add_row(user["user_id"], user["email"], user["reason"])
    if len(user_list) > limit:
        table.add_row(f"[muted]… and {len(user_list) - limit} more[/muted]", "", "")
    print_table(table)
