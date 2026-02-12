"""Preview operations for dry-run mode - shows what would happen without executing."""

import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from ..core.config import API_RATE_LIMIT
from ..utils.auth_utils import validate_auth0_user_id
from ..utils.display_utils import (
    CYAN,
    GREEN,
    RED,
    RESET,
    YELLOW,
    live_progress,
    shutdown_requested,
)
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
    token: str,
    base_url: str,
    operation: str,
    show_details: bool = True,
) -> PreviewResult:
    """Preview what would happen during user operations without executing them.

    Args:
        user_ids: List of user IDs/emails to preview
        token: Auth0 access token
        base_url: Auth0 API base URL
        operation: Operation type ('delete', 'block', 'revoke-grants-only')
        show_details: Whether to show detailed preview information

    Returns:
        PreviewResult: Summary of what would happen
    """
    result = PreviewResult(operation=operation, total_users=len(user_ids))

    print(f"\n{YELLOW}🔍 DRY RUN PREVIEW - {operation.upper()} OPERATION{RESET}")
    print(f"Analyzing {len(user_ids)} users...")

    with live_progress(len(user_ids), f"Analyzing users for {operation}") as advance:
        for user_id in user_ids:
            if shutdown_requested():
                break

            user_id = SecurityValidator.sanitize_user_input(user_id)
            resolved_user_id = _resolve_user_identifier(
                user_id, token, base_url, result
            )

            if resolved_user_id:
                _process_resolved_user(
                    user_id, resolved_user_id, token, base_url, operation, result
                )

            advance()

    if show_details:
        _display_preview_results(result)

    return result


def _process_resolved_user(
    original_id: str,
    resolved_user_id: str,
    token: str,
    base_url: str,
    operation: str,
    result: PreviewResult,
) -> None:
    """Fetch user details and classify into valid, blocked, or error."""
    try:
        user_details = get_user_details(resolved_user_id, token, base_url)
        time.sleep(API_RATE_LIMIT)

        if not user_details:
            result.errors.append(
                {
                    "identifier": original_id,
                    "error": "Could not fetch user details",
                    "timestamp": datetime.utcnow().isoformat(),
                    "operation": operation,
                    "error_type": "user_details_fetch_failed",
                }
            )
            return

        if _should_skip_user(user_details, operation):
            result.blocked_users.append(resolved_user_id)
        else:
            result.valid_users.append(
                {
                    "user_id": resolved_user_id,
                    "email": user_details.get("email", ""),
                    "connection": _get_user_connection(user_details),
                    "blocked": user_details.get("blocked", False),
                    "last_login": user_details.get("last_login", ""),
                    "created_at": user_details.get("created_at", ""),
                }
            )
    except Exception as e:
        result.errors.append(
            {
                "identifier": original_id,
                "error": f"API error: {str(e)}",
                "timestamp": datetime.utcnow().isoformat(),
                "operation": operation,
                "error_type": "api_exception",
            }
        )


def _resolve_user_identifier(
    user_id: str,
    token: str,
    base_url: str,
    result: PreviewResult,
) -> str | None:
    """Resolve user identifier (email or user ID) to a valid user ID."""
    # If input is an email, resolve to user_id
    if "@" in user_id and user_id.count("@") == 1 and len(user_id.split("@")[1]) > 0:
        try:
            resolved_ids = get_user_id_from_email(user_id, token, base_url)
            # Rate limiting after API call
            time.sleep(API_RATE_LIMIT)

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
                    "timestamp": datetime.utcnow().isoformat(),
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
    """Display detailed preview results."""
    _display_preview_header(result)
    _display_valid_users(result)
    _display_skipped_users(result)
    _display_error_categories(result)


def _display_preview_header(result: PreviewResult) -> None:
    """Display the preview results header with summary statistics."""
    print(f"\n{GREEN}📊 DRY RUN PREVIEW RESULTS{RESET}")
    print(f"Operation: {result.operation.upper()}")
    print(f"Total users analyzed: {result.total_users}")
    print(f"Would process: {CYAN}{result.success_count}{RESET}")
    print(f"Would skip: {YELLOW}{result.skip_count}{RESET}")
    print(
        f"Success rate: {GREEN if result.success_rate > 90 else YELLOW}{result.success_rate:.1f}%{RESET}"
    )


def _display_valid_users(result: PreviewResult) -> None:
    """Display users that would be successfully processed."""
    if not result.valid_users:
        return

    print(
        f"\n{GREEN}✅ Users that would be {result.operation}d ({len(result.valid_users)}):{RESET}"
    )
    for i, user in enumerate(result.valid_users[:10], 1):  # Show first 10
        blocked_indicator = " (BLOCKED)" if user["blocked"] else ""
        print(
            f"  {i}. {user['user_id']} ({user['email']}) - {user['connection']}{blocked_indicator}"
        )

    if len(result.valid_users) > 10:
        print(f"  ... and {len(result.valid_users) - 10} more users")


def _display_skipped_users(result: PreviewResult) -> None:
    """Display users that would be skipped."""
    _display_simple_list(
        result.blocked_users, f"{YELLOW}⚠️  Users already in target state", limit=5
    )


def _display_error_categories(result: PreviewResult) -> None:
    """Display all error categories (not found, invalid, multiple users, errors)."""
    _display_simple_list(result.not_found_users, f"{RED}❌ Users not found", limit=5)

    _display_simple_list(result.invalid_user_ids, f"{RED}❌ Invalid user IDs", limit=5)

    _display_multiple_users(result.multiple_users)

    _display_error_list(result.errors)


def _display_simple_list(
    items: list[str], header_template: str, limit: int = 5
) -> None:
    """Display a simple list of items with header and limit."""
    if not items:
        return

    print(f"\n{header_template} ({len(items)}):{RESET}")
    for item in items[:limit]:
        print(f"  - {item}")

    if len(items) > limit:
        print(f"  ... and {len(items) - limit} more")


def _display_multiple_users(multiple_users: dict[str, list[str]]) -> None:
    """Display emails with multiple users."""
    if not multiple_users:
        return

    print(f"\n{YELLOW}⚠️  Emails with multiple users ({len(multiple_users)}):{RESET}")
    for email, user_ids in list(multiple_users.items())[:3]:  # Show first 3
        print(f"  - {email}:")
        for uid in user_ids:
            print(f"    • {uid}")

    if len(multiple_users) > 3:
        print(f"  ... and {len(multiple_users) - 3} more")


def _display_error_list(errors: list[dict[str, Any]]) -> None:
    """Display error list with identifier, error message, timestamp, and error type."""
    if not errors:
        return

    print(f"\n{RED}❌ Errors ({len(errors)}):{RESET}")
    for error in errors[:5]:  # Show first 5
        timestamp = error.get("timestamp", "N/A")
        error_type = error.get("error_type", "unknown")
        print(f"  - {error['identifier']}: {error['error']}")
        print(f"    ↳ Time: {timestamp[:19]} | Type: {error_type}")

    if len(errors) > 5:
        print(f"  ... and {len(errors) - 5} more")


def preview_social_unlink_operations(
    social_ids: list[str],
    token: str,
    base_url: str,
    show_details: bool = True,
) -> dict[str, Any]:
    """Preview what would happen during social identity unlink operations.

    Args:
        social_ids: List of social media IDs to preview
        token: Auth0 access token
        base_url: Auth0 API base URL
        show_details: Whether to show detailed preview information

    Returns:
        dict: Preview results for social unlink operations
    """
    from .batch_ops import _categorize_users, _search_batch_social_ids

    print(f"\n{YELLOW}🔍 DRY RUN PREVIEW - SOCIAL UNLINK OPERATION{RESET}")
    print(f"Analyzing {len(social_ids)} social IDs...")

    # Search for users with each social ID
    found_users, not_found_ids = _search_batch_social_ids(social_ids, token, base_url)

    # Categorize users
    users_to_delete, identities_to_unlink, auth0_main_protected = _categorize_users(
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
    _display_social_header(results)
    _display_social_operations(results)
    _display_social_categories(results)


def _display_social_header(results: dict[str, Any]) -> None:
    """Display social unlink preview header with summary statistics."""
    print(f"\n{GREEN}📊 DRY RUN PREVIEW RESULTS - SOCIAL UNLINK{RESET}")
    print(f"Total social IDs analyzed: {results['total_social_ids']}")
    print(f"Users found: {results['found_users']}")
    print(f"Social IDs not found: {results['not_found_ids']}")


def _display_social_operations(results: dict[str, Any]) -> None:
    """Display the operations that would be performed."""
    print(f"\n{GREEN}Operations that would be performed:{RESET}")
    print(f"  Users to delete: {CYAN}{results['users_to_delete']}{RESET}")
    print(f"  Identities to unlink: {CYAN}{results['identities_to_unlink']}{RESET}")
    print(f"  Protected users: {YELLOW}{results['auth0_main_protected']}{RESET}")


def _display_social_categories(results: dict[str, Any]) -> None:
    """Display detailed information for each category of social unlink operations."""
    _display_social_user_list(
        results["users_to_delete_list"],
        f"{GREEN}Users that would be deleted:",
        limit=10,
    )

    _display_social_user_list(
        results["identities_to_unlink_list"],
        f"{YELLOW}Identities that would be unlinked:",
        limit=10,
    )

    _display_social_user_list(
        results["auth0_main_protected_list"],
        f"{CYAN}Protected users (would be skipped):",
        limit=10,
    )


def _display_social_user_list(
    user_list: list[dict[str, str]], header: str, limit: int = 10
) -> None:
    """Display a list of social users with their details."""
    if not user_list:
        return

    print(f"\n{header}{RESET}")
    for user in user_list[:limit]:
        print(f"  - {user['user_id']} ({user['email']}) - {user['reason']}")

    if len(user_list) > limit:
        print(f"  ... and {len(user_list) - limit} more")
