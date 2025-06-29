"""Batch processing operations for Auth0 user management."""

import time
from typing import Any
from urllib.parse import quote

import requests

from ..core.config import API_RATE_LIMIT, API_TIMEOUT
from ..utils.display_utils import (
    show_progress,
    shutdown_requested,
)
from ..utils.legacy_print import (
    print_error,
    print_info,
    print_success,
    print_warning,
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
        if shutdown_requested():
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
            print_error(
                f"Error checking user {user_id}: {e}",
                user_id=user_id,
                operation="check_blocked",
            )
            continue

    print("\n")  # Clear progress line
    if unblocked:
        print_warning(
            f"Found {len(unblocked)} unblocked users:",
            count=len(unblocked),
            operation="check_unblocked",
        )
        for user_id in unblocked:
            print_info(f"  {user_id}", user_id=user_id, status="unblocked")
    else:
        print_success("All users are blocked.", operation="check_unblocked")


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
    print_info(
        f"Searching for users with {len(social_ids)} social media IDs...",
        social_ids_count=len(social_ids),
        operation="social_search",
    )

    found_users = []
    not_found_ids = []
    total_ids = len(social_ids)

    # Search for users with each social ID
    for idx, social_id in enumerate(social_ids, 1):
        if shutdown_requested():
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


def _search_users_by_social_id(
    social_id: str, token: str, base_url: str
) -> list[dict[str, Any]]:
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
        "search_engine": "v3",
        "include_totals": "true",
        "page": "0",
        "per_page": "100",
    }

    found_users = []

    try:
        response = requests.get(
            url, headers=headers, params=params, timeout=API_TIMEOUT
        )
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
        print_error(
            f"Error searching for social ID {social_id}: {e}",
            social_id=social_id,
            operation="social_search",
        )

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
                users_to_delete.append(
                    {
                        "user_id": user_id,
                        "email": user.get("email", ""),
                        "matching_connection": matching_connection,
                        "social_id": social_id,
                        "reason": "Main identity",
                    }
                )
            else:
                auth0_main_protected.append(
                    {
                        "user_id": user_id,
                        "email": user.get("email", ""),
                        "matching_connection": matching_connection,
                        "social_id": social_id,
                        "reason": "Main identity (protected)",
                    }
                )
        else:
            # Multiple identities - check if Auth0 is the main identity
            auth0_identity = None
            for identity in identities:
                if identity.get("connection") == "auth0":
                    auth0_identity = identity
                    break

            if auth0_identity and auth0_identity.get("isSocial", False) is False:
                # Auth0 is the main identity, protect the user
                auth0_main_protected.append(
                    {
                        "user_id": user_id,
                        "email": user.get("email", ""),
                        "matching_connection": matching_connection,
                        "social_id": social_id,
                        "reason": "Auth0 main identity",
                    }
                )
            else:
                # Social identity can be safely unlinked
                identities_to_unlink.append(
                    {
                        "user_id": user_id,
                        "email": user.get("email", ""),
                        "matching_connection": matching_connection,
                        "social_id": social_id,
                        "reason": "Secondary identity",
                    }
                )

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
    print_info("\nSearch Results Summary:", operation="social_search_summary")
    print_info(f"Total social IDs searched: {total_ids}", total_ids=total_ids)
    print_info(f"Users found: {len(found_users)}", users_found=len(found_users))
    print_info(
        f"Social IDs not found: {len(not_found_ids)}",
        not_found_count=len(not_found_ids),
    )

    if not_found_ids:
        print_warning("\nSocial IDs not found:", count=len(not_found_ids))
        for social_id in not_found_ids:
            print_info(f"  {social_id}", social_id=social_id, status="not_found")

    print_info("\nUser Categories:", operation="categorization")
    print_info(
        f"  Users to delete: {len(users_to_delete)}", delete_count=len(users_to_delete)
    )
    print_info(
        f"  Identities to unlink: {len(identities_to_unlink)}",
        unlink_count=len(identities_to_unlink),
    )
    print_info(
        f"  Protected users: {len(auth0_main_protected)}",
        protected_count=len(auth0_main_protected),
    )

    if users_to_delete:
        print_warning("\nUsers that will be deleted:", count=len(users_to_delete))
        for user in users_to_delete:
            print_info(
                f"  {user['user_id']} ({user['email']}) - {user['reason']}",
                user_id=user["user_id"],
                email=user["email"],
                reason=user["reason"],
                action="delete",
            )

    if identities_to_unlink:
        print_warning(
            "\nUsers where identities will be unlinked:",
            count=len(identities_to_unlink),
        )
        for user in identities_to_unlink:
            print_info(
                f"  {user['user_id']} ({user['email']}) - {user['reason']}",
                user_id=user["user_id"],
                email=user["email"],
                reason=user["reason"],
                action="unlink",
            )

    if auth0_main_protected:
        print_warning(
            "\nProtected users (Auth0 main identity):", count=len(auth0_main_protected)
        )
        for user in auth0_main_protected:
            print_info(
                f"  {user['user_id']} ({user['email']}) - {user['reason']}",
                user_id=user["user_id"],
                email=user["email"],
                reason=user["reason"],
                action="protected",
            )


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
        print_success("\nNo operations to perform.", operation="auto_delete")
        return

    if auto_delete:
        # Confirm operations for production environment
        if env == "prod":
            print_error(
                f"\nWARNING: This will perform {total_operations} operations in PRODUCTION!",
                total_operations=total_operations,
                environment="prod",
            )
            confirm = input("Type 'CONFIRM' to proceed: ")
            if confirm != "CONFIRM":
                print_warning("Operations cancelled.", operation="auto_delete")
                return

        # Handle user deletions
        deleted_count = 0
        failed_deletions = 0

        if users_to_delete:
            print_warning(
                f"\nDeleting {len(users_to_delete)} users...",
                count=len(users_to_delete),
                operation="delete_users",
            )
            for idx, user in enumerate(users_to_delete, 1):
                if shutdown_requested():
                    break

                show_progress(idx, len(users_to_delete), "Deleting users")

                try:
                    from .user_ops import delete_user

                    delete_user(user["user_id"], token, base_url)
                    deleted_count += 1
                except Exception as e:
                    print_error(
                        f"\nFailed to delete user {user['user_id']}: {e}",
                        user_id=user["user_id"],
                        operation="delete_user",
                    )
                    failed_deletions += 1
            print("\n")  # Clear progress line

        # Handle identity unlinking and check for orphaned users
        unlinked_count = 0
        failed_unlinks = 0
        orphaned_users_deleted = 0
        orphaned_users_failed = 0

        if identities_to_unlink:
            print_warning(
                f"\nUnlinking {len(identities_to_unlink)} identities...",
                count=len(identities_to_unlink),
                operation="unlink_identities",
            )
            for idx, user in enumerate(identities_to_unlink, 1):
                if shutdown_requested():
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

                        # Check if user has no remaining identities after unlinking
                        remaining_identities = _get_user_identity_count(
                            user["user_id"], token, base_url
                        )
                        if remaining_identities == 0:
                            print_warning(
                                f"User {user['user_id']} has no remaining identities after unlinking, deleting...",
                                user_id=user["user_id"],
                                operation="delete_orphaned_user",
                            )
                            try:
                                from .user_ops import delete_user
                                delete_user(user["user_id"], token, base_url)
                                orphaned_users_deleted += 1
                                print_success(
                                    f"Successfully deleted orphaned user {user['user_id']}",
                                    user_id=user["user_id"],
                                    operation="delete_orphaned_user",
                                )
                            except Exception as e:
                                print_error(
                                    f"Failed to delete orphaned user {user['user_id']}: {e}",
                                    user_id=user["user_id"],
                                    operation="delete_orphaned_user",
                                )
                                orphaned_users_failed += 1
                    else:
                        failed_unlinks += 1
                except Exception as e:
                    print_error(
                        f"\nFailed to unlink identity {user['social_id']} from user {user['user_id']}: {e}",
                        user_id=user["user_id"],
                        social_id=user["social_id"],
                        operation="unlink_identity",
                    )
                    failed_unlinks += 1
            print("\n")  # Clear progress line

        # Print summary
        print_success("\nOperations Summary:", operation="operations_summary")
        if users_to_delete:
            print_info(f"Users deleted: {deleted_count}", deleted_count=deleted_count)
            print_info(
                f"Failed deletions: {failed_deletions}",
                failed_deletions=failed_deletions,
            )
        if identities_to_unlink:
            print_info(
                f"Identities unlinked: {unlinked_count}", unlinked_count=unlinked_count
            )
            print_info(
                f"Failed unlinks: {failed_unlinks}", failed_unlinks=failed_unlinks
            )
            if orphaned_users_deleted > 0:
                print_info(
                    f"Orphaned users deleted: {orphaned_users_deleted}",
                    orphaned_users_deleted=orphaned_users_deleted,
                )
            if orphaned_users_failed > 0:
                print_info(
                    f"Failed orphaned user deletions: {orphaned_users_failed}",
                    orphaned_users_failed=orphaned_users_failed,
                )

    elif total_operations > 0 and not auto_delete:
        print_warning(
            f"\nNote: {total_operations} operations found, but auto_delete is disabled.",
            total_operations=total_operations,
            auto_delete=False,
        )
        print_info(
            f"- {len(users_to_delete)} users would be deleted",
            delete_count=len(users_to_delete),
        )
        print_info(
            f"- {len(identities_to_unlink)} identities would be unlinked",
            unlink_count=len(identities_to_unlink),
        )


def _get_user_identity_count(user_id: str, token: str, base_url: str) -> int:
    """Get the number of identities for a user.

    Args:
        user_id: Auth0 user ID
        token: Auth0 access token
        base_url: Auth0 API base URL

    Returns:
        int: Number of identities for the user
    """
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

        identities = user_data.get("identities", [])
        return len(identities) if isinstance(identities, list) else 0

    except requests.exceptions.RequestException as e:
        print_error(
            f"Error getting user identity count for {user_id}: {e}",
            user_id=user_id,
            error=str(e),
            operation="get_user_identity_count",
        )
        return 0
