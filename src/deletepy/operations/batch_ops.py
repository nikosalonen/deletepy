"""Batch processing operations for Auth0 user management."""

import time
from typing import Any
from urllib.parse import quote

import requests

from ..core.config import API_RATE_LIMIT, API_TIMEOUT
from ..utils.display_utils import (
    CYAN,
    GREEN,
    RED,
    RESET,
    YELLOW,
    show_progress,
    shutdown_requested,
)
from .user_ops import unlink_user_identity


def check_unblocked_users(user_ids: list[str], token: str, base_url: str) -> None:
    """Print user IDs that are not blocked, with a progress indicator.

    Args:
        user_ids: List of Auth0 user IDs to check
        token: Auth0 access token
        base_url: Auth0 API base URL
    """
    unblocked = []
    total_users = len(user_ids)

    for idx, user_id in enumerate(user_ids, 1):
        if shutdown_requested:
            break
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
            if not user_data.get("blocked", False):
                unblocked.append(user_id)
            show_progress(idx, total_users, "Checking users")
            time.sleep(API_RATE_LIMIT)
        except requests.exceptions.RequestException as e:
            print(f"{RED}Error checking user {CYAN}{user_id}{RED}: {e}{RESET}")
            continue

    print("\n")  # Clear progress line
    if unblocked:
        print(f"{YELLOW}Found {len(unblocked)} unblocked users:{RESET}")
        for user_id in unblocked:
            print(f"{CYAN}{user_id}{RESET}")
    else:
        print(f"{GREEN}All users are blocked.{RESET}")


def find_users_by_social_media_ids(
    social_ids: list[str],
    token: str,
    base_url: str,
    env: str = "dev",
    auto_delete: bool = True,
) -> None:
    """Find Auth0 users who have the specified social media IDs in their identities array.

    If auto_delete is True, users where the social media ID is their main/only identity will be deleted.

    Args:
        social_ids: List of social media IDs to search for
        token: Auth0 access token
        base_url: Auth0 API base URL
        env: Environment (dev/prod) for confirmation prompts
        auto_delete: Whether to automatically delete users with main identity matches
    """
    print(
        f"{YELLOW}Searching for users with {len(social_ids)} social media IDs...{RESET}"
    )

    found_users = []
    not_found_ids = []
    total_ids = len(social_ids)

    # Search for users with each social ID
    for idx, social_id in enumerate(social_ids, 1):
        if shutdown_requested:
            break

        show_progress(idx, total_ids, "Searching social IDs")

        # Search for users with this social ID
        users_found = _search_users_by_social_id(social_id, token, base_url)
        if users_found:
            # Add social_id to each user for later processing
            for user in users_found:
                user["social_id"] = social_id
            found_users.extend(users_found)
        else:
            not_found_ids.append(social_id.strip())

    print("\n")  # Clear progress line

    # Categorize users based on their identity configuration
    users_to_delete, identities_to_unlink, auth0_main_protected = _categorize_users(
        found_users, auto_delete
    )

    # Display search results
    _display_search_results(
        total_ids,
        found_users,
        not_found_ids,
        users_to_delete,
        identities_to_unlink,
        auth0_main_protected,
        auto_delete,
    )

    # Handle auto-delete operations
    _handle_auto_delete_operations(
        users_to_delete, identities_to_unlink, token, base_url, env, auto_delete
    )


def _search_users_by_social_id(social_id: str, token: str, base_url: str) -> list[dict[str, Any]]:
    """Search for users with a specific social media ID.

    Args:
        social_id: The social media ID to search for
        token: Auth0 access token
        base_url: Auth0 API base URL

    Returns:
        List[Dict[str, Any]]: List of users found with this social ID
    """
    url = f"{base_url}/api/v2/users"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": "DeletePy/1.0 (Auth0 User Management Tool)",
    }

    # Search for users with this social ID in their identities
    params = {
        "q": f'identities.user_id:"{social_id}"',
        "include_totals": "true",
        "page": "0",
        "per_page": "100"
    }

    found_users = []

    try:
        response = requests.get(url, headers=headers, params=params, timeout=API_TIMEOUT)
        response.raise_for_status()
        data = response.json()

        if "users" in data:
            for user in data["users"]:
                # Verify this user actually has the social ID
                if "identities" in user and isinstance(user["identities"], list):
                    for identity in user["identities"]:
                        if identity.get("user_id") == social_id:
                            found_users.append(user)
                            break

        time.sleep(API_RATE_LIMIT)

    except requests.exceptions.RequestException as e:
        print(f"{RED}Error searching for social ID {CYAN}{social_id}{RED}: {e}{RESET}")

    return found_users


def _categorize_users(
    found_users: list[dict[str, Any]], auto_delete: bool = True
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Categorize users based on their identity configuration.

    Args:
        found_users: List of users found with the social ID
        auto_delete: Whether to automatically delete users with main identity matches

    Returns:
        Tuple containing:
        - users_to_delete: Users that should be deleted
        - identities_to_unlink: Users where only the identity should be unlinked
        - auth0_main_protected: Users with Auth0 as main identity (protected)
    """
    users_to_delete = []
    identities_to_unlink = []
    auth0_main_protected = []

    for user in found_users:
        user_id = user.get("user_id", "")
        identities = user.get("identities", [])
        social_id = user.get("social_id", "")

        if not identities or not social_id:
            continue

        # Find the matching identity
        matching_identity = None
        for identity in identities:
            if identity.get("user_id") == social_id:
                matching_identity = identity
                break

        if not matching_identity:
            continue

        matching_connection = matching_identity.get("connection", "")

        # Determine user category based on identity configuration
        if len(identities) == 1:
            # Only one identity - this is the main identity
            if auto_delete:
                users_to_delete.append({
                    "user_id": user_id,
                    "email": user.get("email", ""),
                    "matching_connection": matching_connection,
                    "social_id": social_id,
                    "reason": "Main identity"
                })
            else:
                auth0_main_protected.append({
                    "user_id": user_id,
                    "email": user.get("email", ""),
                    "matching_connection": matching_connection,
                    "social_id": social_id,
                    "reason": "Main identity (protected)"
                })
        else:
            # Multiple identities - check if Auth0 is the main identity
            auth0_identity = None
            for identity in identities:
                if identity.get("connection") == "auth0":
                    auth0_identity = identity
                    break

            if auth0_identity and auth0_identity.get("isSocial", False) is False:
                # Auth0 is the main identity, protect the user
                auth0_main_protected.append({
                    "user_id": user_id,
                    "email": user.get("email", ""),
                    "matching_connection": matching_connection,
                    "social_id": social_id,
                    "reason": "Auth0 main identity"
                })
            else:
                # Social identity can be safely unlinked
                identities_to_unlink.append({
                    "user_id": user_id,
                    "email": user.get("email", ""),
                    "matching_connection": matching_connection,
                    "social_id": social_id,
                    "reason": "Secondary identity"
                })

    return users_to_delete, identities_to_unlink, auth0_main_protected


def _display_search_results(
    total_ids: int,
    found_users: list[dict[str, Any]],
    not_found_ids: list[str],
    users_to_delete: list[dict[str, Any]],
    identities_to_unlink: list[dict[str, Any]],
    auth0_main_protected: list[dict[str, Any]],
    auto_delete: bool = True,
) -> None:
    """Display search results summary.

    Args:
        total_ids: Total number of social IDs searched
        found_users: All users found with any of the social IDs
        not_found_ids: Social IDs that were not found
        users_to_delete: Users that will be deleted
        identities_to_unlink: Users where identities will be unlinked
        auth0_main_protected: Users that are protected from deletion
        auto_delete: Whether auto-delete is enabled
    """
    print(f"\n{GREEN}Search Results Summary:{RESET}")
    print(f"Total social IDs searched: {total_ids}")
    print(f"Users found: {len(found_users)}")
    print(f"Social IDs not found: {len(not_found_ids)}")

    if not_found_ids:
        print(f"\n{YELLOW}Social IDs not found:{RESET}")
        for social_id in not_found_ids:
            print(f"  {CYAN}{social_id}{RESET}")

    print(f"\n{YELLOW}User Categories:{RESET}")
    print(f"  Users to delete: {len(users_to_delete)}")
    print(f"  Identities to unlink: {len(identities_to_unlink)}")
    print(f"  Protected users: {len(auth0_main_protected)}")

    if users_to_delete:
        print(f"\n{YELLOW}Users that will be deleted:{RESET}")
        for user in users_to_delete:
            print(f"  {CYAN}{user['user_id']}{RESET} ({user['email']}) - {user['reason']}")

    if identities_to_unlink:
        print(f"\n{YELLOW}Users where identities will be unlinked:{RESET}")
        for user in identities_to_unlink:
            print(f"  {CYAN}{user['user_id']}{RESET} ({user['email']}) - {user['reason']}")

    if auth0_main_protected:
        print(f"\n{YELLOW}Protected users (Auth0 main identity):{RESET}")
        for user in auth0_main_protected:
            print(f"  {CYAN}{user['user_id']}{RESET} ({user['email']}) - {user['reason']}")


def _handle_auto_delete_operations(
    users_to_delete: list[dict[str, Any]],
    identities_to_unlink: list[dict[str, Any]],
    token: str,
    base_url: str,
    env: str = "dev",
    auto_delete: bool = True,
) -> None:
    """Handle automatic deletion and unlinking operations.

    Args:
        users_to_delete: Users that should be deleted
        identities_to_unlink: Users where identities should be unlinked
        token: Auth0 access token
        base_url: Auth0 API base URL
        env: Environment (dev/prod) for confirmation prompts
        auto_delete: Whether to perform automatic operations
    """
    total_operations = len(users_to_delete) + len(identities_to_unlink)

    if total_operations == 0:
        print(f"\n{GREEN}No operations to perform.{RESET}")
        return

    if auto_delete:
        # Confirm operations for production environment
        if env == "prod":
            print(f"\n{RED}WARNING: This will perform {total_operations} operations in PRODUCTION!{RESET}")
            confirm = input("Type 'CONFIRM' to proceed: ")
            if confirm != "CONFIRM":
                print(f"{YELLOW}Operations cancelled.{RESET}")
                return

        # Handle user deletions
        deleted_count = 0
        failed_deletions = 0

        if users_to_delete:
            print(f"\n{YELLOW}Deleting {len(users_to_delete)} users...{RESET}")
            for idx, user in enumerate(users_to_delete, 1):
                if shutdown_requested:
                    break

                show_progress(idx, len(users_to_delete), "Deleting users")

                try:
                    from .user_ops import delete_user
                    delete_user(user["user_id"], token, base_url)
                    deleted_count += 1
                except Exception as e:
                    print(f"\n{RED}Failed to delete user {CYAN}{user['user_id']}{RED}: {e}{RESET}")
                    failed_deletions += 1
            print("\n")  # Clear progress line

        # Handle identity unlinking
        unlinked_count = 0
        failed_unlinks = 0

        if identities_to_unlink:
            print(f"\n{YELLOW}Unlinking {len(identities_to_unlink)} identities...{RESET}")
            for idx, user in enumerate(identities_to_unlink, 1):
                if shutdown_requested:
                    break

                show_progress(idx, len(identities_to_unlink), "Unlinking identities")

                try:
                    success = unlink_user_identity(
                        user["user_id"],
                        user["matching_connection"],
                        user["social_id"],
                        token,
                        base_url,
                    )
                    if success:
                        unlinked_count += 1
                    else:
                        failed_unlinks += 1
                except Exception as e:
                    print(f"\n{RED}Failed to unlink identity {CYAN}{user['social_id']}{RED} from user {CYAN}{user['user_id']}{RED}: {e}{RESET}")
                    failed_unlinks += 1
            print("\n")  # Clear progress line

        # Print summary
        print(f"\n{GREEN}Operations Summary:{RESET}")
        if users_to_delete:
            print(f"Users deleted: {deleted_count}")
            print(f"Failed deletions: {failed_deletions}")
        if identities_to_unlink:
            print(f"Identities unlinked: {unlinked_count}")
            print(f"Failed unlinks: {failed_unlinks}")

    elif total_operations > 0 and not auto_delete:
        print(f"\n{YELLOW}Note: {total_operations} operations found, but auto_delete is disabled.{RESET}")
        print(f"- {len(users_to_delete)} users would be deleted")
        print(f"- {len(identities_to_unlink)} identities would be unlinked")
