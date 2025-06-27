"""Core user operations for Auth0 user management."""

import time
from typing import Any
from urllib.parse import quote

import requests

from ..core.config import API_RATE_LIMIT, API_TIMEOUT
from ..utils.display_utils import shutdown_requested
from ..utils.legacy_print import (
    print_error,
    print_info,
    print_success,
    print_warning,
)
from ..utils.request_utils import make_rate_limited_request


def delete_user(user_id: str, token: str, base_url: str) -> None:
    """Delete user from Auth0."""
    print_info(f"Deleting user: {user_id}", user_id=user_id, operation="delete_user")

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
        print_success(
            f"Successfully deleted user {user_id}",
            user_id=user_id,
            operation="delete_user",
        )
        time.sleep(API_RATE_LIMIT)
    except requests.exceptions.RequestException as e:
        print_error(
            f"Error deleting user {user_id}: {e}",
            user_id=user_id,
            operation="delete_user",
        )


def block_user(user_id: str, token: str, base_url: str) -> None:
    """Block user in Auth0."""
    print_info(f"Blocking user: {user_id}", user_id=user_id, operation="block_user")

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
        print_success(
            f"Successfully blocked user {user_id}",
            user_id=user_id,
            operation="block_user",
        )
        time.sleep(API_RATE_LIMIT)
    except requests.exceptions.RequestException as e:
        print_error(
            f"Error blocking user {user_id}: {e}",
            user_id=user_id,
            operation="block_user",
        )


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
        print_error(
            f"Error fetching user_id for email {email}: Request failed after retries",
            email=email,
            operation="get_user_id_from_email"
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
                            print_warning(
                                f"Connection info not available for user {user['user_id']}, skipping",
                                user_id=user['user_id'],
                                operation="get_user_id_from_email"
                            )
                    else:
                        # No connection filter, include all users
                        user_ids.append(user["user_id"])

            if user_ids:
                return user_ids
        return None
    except ValueError as e:
        print_error(
            f"Error parsing response for email {email}: {e}",
            email=email,
            error=str(e),
            operation="get_user_id_from_email"
        )
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
        print_error(
            f"Error fetching email for user {user_id}: {e}",
            user_id=user_id,
            error=str(e),
            operation="get_user_email"
        )
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
        print_error(
            f"Error fetching details for user {user_id}: Request failed after retries",
            user_id=user_id,
            operation="get_user_details"
        )
        return None

    try:
        user_data = response.json()
        return user_data
    except ValueError as e:
        print_error(
            f"Error parsing response for user {user_id}: {e}",
            user_id=user_id,
            error=str(e),
            operation="get_user_details"
        )
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
            print_info(
                f"No sessions found for user {user_id}",
                user_id=user_id,
                operation="revoke_user_sessions"
            )
            return
        for session in sessions:
            if shutdown_requested():
                break
            session_id = session.get("id")
            if not session_id:
                continue
            del_url = f"{base_url}/api/v2/sessions/{session_id}"
            del_resp = requests.delete(del_url, headers=headers, timeout=API_TIMEOUT)
            time.sleep(API_RATE_LIMIT)
            try:
                del_resp.raise_for_status()
                print_success(
                    f"Revoked session {session_id} for user {user_id}",
                    user_id=user_id,
                    session_id=session_id,
                    operation="revoke_user_sessions"
                )
            except requests.exceptions.RequestException as e:
                print_warning(
                    f"Failed to revoke session {session_id} for user {user_id}: {e}",
                    user_id=user_id,
                    session_id=session_id,
                    error=str(e),
                    operation="revoke_user_sessions"
                )
    except requests.exceptions.RequestException as e:
        print_error(
            f"Error revoking sessions for user {user_id}: {e}",
            user_id=user_id,
            error=str(e),
            operation="revoke_user_sessions"
        )


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
        print_success(
            f"Revoked all application grants for user {user_id}",
            user_id=user_id,
            operation="revoke_user_grants"
        )
        time.sleep(API_RATE_LIMIT)
    except requests.exceptions.RequestException as e:
        print_error(
            f"Error revoking grants for user {user_id}: {e}",
            user_id=user_id,
            error=str(e),
            operation="revoke_user_grants"
        )


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
        print_success(
            f"Successfully unlinked {provider} identity {user_identity_id} from user {user_id}",
            user_id=user_id,
            provider=provider,
            user_identity_id=user_identity_id,
            operation="unlink_user_identity"
        )
        time.sleep(API_RATE_LIMIT)
        return True
    except requests.exceptions.RequestException as e:
        print_error(
            f"Error unlinking {provider} identity {user_identity_id} from user {user_id}: {e}",
            user_id=user_id,
            provider=provider,
            user_identity_id=user_identity_id,
            error=str(e),
            operation="unlink_user_identity"
        )
        return False
