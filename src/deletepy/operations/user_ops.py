"""Core user operations for Auth0 user management."""

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
    shutdown_requested,
)
from ..utils.request_utils import make_rate_limited_request


def delete_user(user_id: str, token: str, base_url: str) -> None:
    """Delete user from Auth0."""
    print(f"{YELLOW}Deleting user: {CYAN}{user_id}{YELLOW}{RESET}")

    # First revoke all sessions
    revoke_user_sessions(user_id, token, base_url)

    url = f"{base_url}/api/v2/users/{quote(user_id)}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": "DeletePy/1.0 (Auth0 User Management Tool)",
    }
    try:
        response = requests.delete(url, headers=headers, timeout=API_TIMEOUT)
        response.raise_for_status()
        print(f"{GREEN}Successfully deleted user {CYAN}{user_id}{GREEN}{RESET}")
        time.sleep(API_RATE_LIMIT)
    except requests.exceptions.RequestException as e:
        print(f"{RED}Error deleting user {CYAN}{user_id}{RED}: {e}{RESET}")


def block_user(user_id: str, token: str, base_url: str) -> None:
    """Block user in Auth0."""
    print(f"{YELLOW}Blocking user: {CYAN}{user_id}{YELLOW}{RESET}")

    # First revoke all sessions and grants
    revoke_user_sessions(user_id, token, base_url)
    revoke_user_grants(user_id, token, base_url)

    url = f"{base_url}/api/v2/users/{quote(user_id)}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": "DeletePy/1.0 (Auth0 User Management Tool)",
    }
    payload = {"blocked": True}
    try:
        response = requests.patch(
            url, headers=headers, json=payload, timeout=API_TIMEOUT
        )
        response.raise_for_status()
        print(f"{GREEN}Successfully blocked user {CYAN}{user_id}{GREEN}{RESET}")
        time.sleep(API_RATE_LIMIT)
    except requests.exceptions.RequestException as e:
        print(f"{RED}Error blocking user {CYAN}{user_id}{RED}: {e}{RESET}")


def get_user_id_from_email(
    email: str, token: str, base_url: str, connection: str | None = None
) -> list[str] | None:
    """Fetch user_ids from Auth0 using email address. Returns list of user_ids or None if not found.

    Args:
        email: Email address to search for
        token: Auth0 access token
        base_url: Auth0 API base URL
        connection: Optional connection filter (e.g., "google-oauth2", "auth0", "facebook")

    Returns:
        Optional[List[str]]: List of user IDs matching the email and connection filter
    """
    url = f"{base_url}/api/v2/users-by-email"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": "DeletePy/1.0 (Auth0 User Management Tool)",
    }
    params = {"email": email}

    response = make_rate_limited_request("GET", url, headers, params=params)
    if response is None:
        print(
            f"{RED}Error fetching user_id for email {CYAN}{email}{RED}: Request failed after retries{RESET}"
        )
        return None

    try:
        users = response.json()
        if users and isinstance(users, list):
            user_ids = []
            for user in users:
                if "user_id" in user:
                    # If connection filter is specified, check if user matches
                    if connection:
                        # Check if identities array exists in the response and filter directly
                        if user.get("identities") and isinstance(
                            user["identities"], list
                        ):
                            # Filter by connection using data already in the response
                            user_connection = user["identities"][0].get(
                                "connection", "unknown"
                            )
                            if user_connection == connection:
                                user_ids.append(user["user_id"])
                        else:
                            # Fallback: identities not included, skip this user to avoid API call
                            print(
                                f"{RED}Warning: Connection info not available for user {user['user_id']}, skipping{RESET}"
                            )
                    else:
                        # No connection filter, include all users
                        user_ids.append(user["user_id"])

            if user_ids:
                return user_ids
        return None
    except ValueError as e:
        print(f"{RED}Error parsing response for email {CYAN}{email}{RED}: {e}{RESET}")
        return None


def get_user_email(user_id: str, token: str, base_url: str) -> str | None:
    """Fetch user's email address from Auth0.

    Args:
        user_id: The Auth0 user ID
        token: Auth0 access token
        base_url: Auth0 API base URL

    Returns:
        Optional[str]: User's email address if found, None otherwise
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
        time.sleep(API_RATE_LIMIT)
        return user_data.get("email")
    except requests.exceptions.RequestException as e:
        print(f"{RED}Error fetching email for user {CYAN}{user_id}{RED}: {e}{RESET}")
        return None


def get_user_details(user_id: str, token: str, base_url: str) -> dict[str, Any] | None:
    """Fetch user details from Auth0 including connection information.

    Args:
        user_id: The Auth0 user ID
        token: Auth0 access token
        base_url: Auth0 API base URL

    Returns:
        Optional[Dict[str, Any]]: User details if found, None otherwise
    """
    url = f"{base_url}/api/v2/users/{quote(user_id)}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": "DeletePy/1.0 (Auth0 User Management Tool)",
    }

    response = make_rate_limited_request("GET", url, headers)
    if response is None:
        print(
            f"{RED}Error fetching details for user {CYAN}{user_id}{RED}: Request failed after retries{RESET}"
        )
        return None

    try:
        user_data = response.json()
        return user_data
    except ValueError as e:
        print(f"{RED}Error parsing response for user {CYAN}{user_id}{RED}: {e}{RESET}")
        return None


def revoke_user_sessions(user_id: str, token: str, base_url: str) -> None:
    """Fetch all Auth0 sessions for a user and revoke them one by one."""
    list_url = f"{base_url}/api/v2/users/{quote(user_id)}/sessions"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": "DeletePy/1.0 (Auth0 User Management Tool)",
    }
    try:
        response = requests.get(list_url, headers=headers, timeout=API_TIMEOUT)
        response.raise_for_status()
        sessions = response.json().get("sessions", [])
        if not sessions:
            print(f"{YELLOW}No sessions found for user {CYAN}{user_id}{YELLOW}{RESET}")
            return
        for session in sessions:
            if shutdown_requested:
                break
            session_id = session.get("id")
            if not session_id:
                continue
            del_url = f"{base_url}/api/v2/sessions/{session_id}"
            del_resp = requests.delete(del_url, headers=headers, timeout=API_TIMEOUT)
            time.sleep(API_RATE_LIMIT)
            try:
                del_resp.raise_for_status()
                print(
                    f"{GREEN}Revoked session {CYAN}{session_id}{GREEN} for user {CYAN}{user_id}{GREEN}{RESET}"
                )
            except requests.exceptions.RequestException as e:
                print(
                    f"{YELLOW}Failed to revoke session {CYAN}{session_id}{YELLOW} for user {CYAN}{user_id}{YELLOW}: {e}{RESET}"
                )
    except requests.exceptions.RequestException as e:
        print(f"{RED}Error revoking sessions for user {CYAN}{user_id}{RED}: {e}{RESET}")


def revoke_user_grants(user_id: str, token: str, base_url: str) -> None:
    """Revoke all application grants (authorized applications) for a user in one call."""
    grants_url = f"{base_url}/api/v2/grants?user_id={quote(user_id)}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": "DeletePy/1.0 (Auth0 User Management Tool)",
    }
    try:
        response = requests.delete(grants_url, headers=headers, timeout=API_TIMEOUT)
        response.raise_for_status()
        print(
            f"{GREEN}Revoked all application grants for user {CYAN}{user_id}{GREEN}{RESET}"
        )
        time.sleep(API_RATE_LIMIT)
    except requests.exceptions.RequestException as e:
        print(f"{RED}Error revoking grants for user {CYAN}{user_id}{RED}: {e}{RESET}")


def unlink_user_identity(
    user_id: str, provider: str, user_identity_id: str, token: str, base_url: str
) -> bool:
    """Unlink a social identity from a user.

    Args:
        user_id: The Auth0 user ID
        provider: The identity provider (e.g., "google-oauth2", "facebook")
        user_identity_id: The identity ID to unlink
        token: Auth0 access token
        base_url: Auth0 API base URL

    Returns:
        bool: True if successful, False otherwise
    """
    url = f"{base_url}/api/v2/users/{quote(user_id)}/identities/{provider}/{user_identity_id}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": "DeletePy/1.0 (Auth0 User Management Tool)",
    }
    try:
        response = requests.delete(url, headers=headers, timeout=API_TIMEOUT)
        response.raise_for_status()
        print(
            f"{GREEN}Successfully unlinked {CYAN}{provider}{GREEN} identity {CYAN}{user_identity_id}{GREEN} from user {CYAN}{user_id}{GREEN}{RESET}"
        )
        time.sleep(API_RATE_LIMIT)
        return True
    except requests.exceptions.RequestException as e:
        print(
            f"{RED}Error unlinking {CYAN}{provider}{RED} identity {CYAN}{user_identity_id}{RED} from user {CYAN}{user_id}{RED}: {e}{RESET}"
        )
        return False
