"""Preview operations for dry-run mode - shows what would happen without executing."""

import time
from dataclasses import dataclass, field
from typing import Any

from ..core.config import API_RATE_LIMIT
from ..utils.auth_utils import validate_auth0_user_id
from ..utils.display_utils import (
    CYAN,
    GREEN,
    RED,
    RESET,
    YELLOW,
    show_progress,
    shutdown_requested,
)
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
    errors: list[dict[str, str]] = field(default_factory=list)

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

    for idx, user_id in enumerate(user_ids, 1):
        if shutdown_requested():
            break

        show_progress(idx, len(user_ids), f"Analyzing users for {operation}")

        # Clean the user ID
        user_id = user_id.strip()

        # Resolve user identifier
        resolved_user_id = _resolve_user_identifier(user_id, token, base_url, result)

        if resolved_user_id:
            # Get user details to check current state
            user_details = get_user_details(resolved_user_id, token, base_url)
            if user_details:
                # Check if user is already in target state
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
            else:
                result.errors.append(
                    {"identifier": user_id, "error": "Could not fetch user details"}
                )

        # Rate limiting
        time.sleep(API_RATE_LIMIT)

    print("\n")  # Clear progress line

    if show_details:
        _display_preview_results(result)

    return result


def _resolve_user_identifier(
    user_id: str,
    token: str,
    base_url: str,
    result: PreviewResult,
) -> str | None:
    """Resolve user identifier (email or user ID) to a valid user ID."""
    # If input is an email, resolve to user_id
    if "@" in user_id and user_id.count("@") == 1:
        try:
            resolved_ids = get_user_id_from_email(user_id, token, base_url)
            if not resolved_ids:
                result.not_found_users.append(user_id)
                return None

            if len(resolved_ids) > 1:
                result.multiple_users[user_id] = resolved_ids
                return None

            return resolved_ids[0]
        except Exception as e:
            result.errors.append(
                {"identifier": user_id, "error": f"Error resolving email: {str(e)}"}
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
        return user_details.get("blocked", False)

    # For delete and revoke-grants-only, we don't skip based on state
    return False


def _get_user_connection(user_details: dict[str, Any]) -> str:
    """Extract connection from user details."""
    identities = user_details.get("identities", [])
    if identities and isinstance(identities, list):
        return identities[0].get("connection", "unknown")
    return "unknown"


def _display_preview_results(result: PreviewResult) -> None:
    """Display detailed preview results."""
    print(f"\n{GREEN}📊 DRY RUN PREVIEW RESULTS{RESET}")
    print(f"Operation: {result.operation.upper()}")
    print(f"Total users analyzed: {result.total_users}")
    print(f"Would process: {CYAN}{result.success_count}{RESET}")
    print(f"Would skip: {YELLOW}{result.skip_count}{RESET}")
    print(
        f"Success rate: {GREEN if result.success_rate > 90 else YELLOW}{result.success_rate:.1f}%{RESET}"
    )

    # Show users that would be processed
    if result.valid_users:
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

    # Show users that would be skipped
    if result.blocked_users:
        print(
            f"\n{YELLOW}⚠️  Users already in target state ({len(result.blocked_users)}):{RESET}"
        )
        for user_id in result.blocked_users[:5]:  # Show first 5
            print(f"  - {user_id}")
        if len(result.blocked_users) > 5:
            print(f"  ... and {len(result.blocked_users) - 5} more")

    if result.not_found_users:
        print(f"\n{RED}❌ Users not found ({len(result.not_found_users)}):{RESET}")
        for email in result.not_found_users[:5]:  # Show first 5
            print(f"  - {email}")
        if len(result.not_found_users) > 5:
            print(f"  ... and {len(result.not_found_users) - 5} more")

    if result.invalid_user_ids:
        print(f"\n{RED}❌ Invalid user IDs ({len(result.invalid_user_ids)}):{RESET}")
        for user_id in result.invalid_user_ids[:5]:  # Show first 5
            print(f"  - {user_id}")
        if len(result.invalid_user_ids) > 5:
            print(f"  ... and {len(result.invalid_user_ids) - 5} more")

    if result.multiple_users:
        print(
            f"\n{YELLOW}⚠️  Emails with multiple users ({len(result.multiple_users)}):{RESET}"
        )
        for email, user_ids in list(result.multiple_users.items())[:3]:  # Show first 3
            print(f"  - {email}:")
            for uid in user_ids:
                print(f"    • {uid}")
        if len(result.multiple_users) > 3:
            print(f"  ... and {len(result.multiple_users) - 3} more")

    if result.errors:
        print(f"\n{RED}❌ Errors ({len(result.errors)}):{RESET}")
        for error in result.errors[:5]:  # Show first 5
            print(f"  - {error['identifier']}: {error['error']}")
        if len(result.errors) > 5:
            print(f"  ... and {len(result.errors) - 5} more")


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
    from .batch_ops import _categorize_users, _search_all_social_ids

    print(f"\n{YELLOW}🔍 DRY RUN PREVIEW - SOCIAL UNLINK OPERATION{RESET}")
    print(f"Analyzing {len(social_ids)} social IDs...")

    # Search for users with each social ID
    found_users, not_found_ids = _search_all_social_ids(social_ids, token, base_url)

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
    print(f"\n{GREEN}📊 DRY RUN PREVIEW RESULTS - SOCIAL UNLINK{RESET}")
    print(f"Total social IDs analyzed: {results['total_social_ids']}")
    print(f"Users found: {results['found_users']}")
    print(f"Social IDs not found: {results['not_found_ids']}")

    print(f"\n{GREEN}Operations that would be performed:{RESET}")
    print(f"  Users to delete: {CYAN}{results['users_to_delete']}{RESET}")
    print(f"  Identities to unlink: {CYAN}{results['identities_to_unlink']}{RESET}")
    print(f"  Protected users: {YELLOW}{results['auth0_main_protected']}{RESET}")

    # Show details for each category
    if results["users_to_delete_list"]:
        print(f"\n{GREEN}Users that would be deleted:{RESET}")
        for user in results["users_to_delete_list"][:10]:
            print(f"  - {user['user_id']} ({user['email']}) - {user['reason']}")
        if len(results["users_to_delete_list"]) > 10:
            print(f"  ... and {len(results['users_to_delete_list']) - 10} more")

    if results["identities_to_unlink_list"]:
        print(f"\n{YELLOW}Identities that would be unlinked:{RESET}")
        for user in results["identities_to_unlink_list"][:10]:
            print(f"  - {user['user_id']} ({user['email']}) - {user['reason']}")
        if len(results["identities_to_unlink_list"]) > 10:
            print(f"  ... and {len(results['identities_to_unlink_list']) - 10} more")

    if results["auth0_main_protected_list"]:
        print(f"\n{CYAN}Protected users (would be skipped):{RESET}")
        for user in results["auth0_main_protected_list"][:10]:
            print(f"  - {user['user_id']} ({user['email']}) - {user['reason']}")
        if len(results["auth0_main_protected_list"]) > 10:
            print(f"  ... and {len(results['auth0_main_protected_list']) - 10} more")
