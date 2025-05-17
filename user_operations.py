import requests
import time
import sys
from urllib.parse import quote
from utils import RED, GREEN, YELLOW, CYAN, RESET, shutdown_requested

# Rate limiting constant (seconds between API calls)
API_RATE_LIMIT = 0.2
# API timeout in seconds
API_TIMEOUT = 30

def delete_user(user_id: str, token: str, base_url: str) -> None:
    """Delete user from Auth0."""
    print(f"{YELLOW}Deleting user: {CYAN}{user_id}{YELLOW}{RESET}")
    
    # First revoke all sessions
    revoke_user_sessions(user_id, token, base_url)
    
    url = f"{base_url}/api/v2/users/{quote(user_id)}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
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
    
    # First revoke all sessions
    revoke_user_sessions(user_id, token, base_url)
    
    url = f"{base_url}/api/v2/users/{quote(user_id)}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload = {"blocked": True}
    try:
        response = requests.patch(url, headers=headers, json=payload, timeout=API_TIMEOUT)
        response.raise_for_status()
        print(f"{GREEN}Successfully blocked user {CYAN}{user_id}{GREEN}{RESET}")
        time.sleep(API_RATE_LIMIT)
    except requests.exceptions.RequestException as e:
        print(f"{RED}Error blocking user {CYAN}{user_id}{RED}: {e}{RESET}")

def get_user_id_from_email(email: str, token: str, base_url: str) -> str:
    """Fetch user_id from Auth0 using email address. Returns user_id or None if not found."""
    url = f"{base_url}/api/v2/users-by-email"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    params = {"email": email}
    try:
        response = requests.get(url, headers=headers, params=params, timeout=API_TIMEOUT)
        response.raise_for_status()
        users = response.json()
        time.sleep(API_RATE_LIMIT)
        if users and isinstance(users, list) and "user_id" in users[0]:
            return users[0]["user_id"]
        else:
            print(f"{YELLOW}Warning: No user found for email {CYAN}{email}{YELLOW}{RESET}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"{RED}Error fetching user_id for email {CYAN}{email}{RED}: {e}{RESET}")
        return None

def revoke_user_sessions(user_id: str, token: str, base_url: str) -> None:
    """Fetch all Auth0 sessions for a user and revoke them one by one."""
    list_url = f"{base_url}/api/v2/users/{quote(user_id)}/sessions"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
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
                print(f"{GREEN}Revoked session {CYAN}{session_id}{GREEN} for user {CYAN}{user_id}{GREEN}{RESET}")
            except requests.exceptions.RequestException as e:
                print(f"{YELLOW}Failed to revoke session {CYAN}{session_id}{YELLOW} for user {CYAN}{user_id}{YELLOW}: {e}{RESET}")
    except requests.exceptions.RequestException as e:
        print(f"{RED}Error revoking sessions for user {CYAN}{user_id}{RED}: {e}{RESET}")

def revoke_user_grants(user_id: str, token: str, base_url: str) -> None:
    """Revoke all application grants (authorized applications) for a user in one call."""
    grants_url = f"{base_url}/api/v2/grants?user_id={quote(user_id)}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    try:
        response = requests.delete(grants_url, headers=headers, timeout=API_TIMEOUT)
        response.raise_for_status()
        print(f"{GREEN}Revoked all application grants for user {CYAN}{user_id}{GREEN}{RESET}")
        time.sleep(API_RATE_LIMIT)
    except requests.exceptions.RequestException as e:
        print(f"{RED}Error revoking grants for user {CYAN}{user_id}{RED}: {e}{RESET}")

def check_unblocked_users(user_ids: list[str], token: str, base_url: str) -> None:
    """Print user IDs that are not blocked, with a progress indicator.
    
    Args:
        user_ids: List of Auth0 user IDs to check
        token: Auth0 access token
        base_url: Auth0 API base URL
    """
    unblocked = []
    spinner = ['|', '/', '-', '\\']
    spin_idx = 0
    for idx, user_id in enumerate(user_ids):
        if shutdown_requested:
            break
        url = f"{base_url}/api/v2/users/{quote(user_id)}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        try:
            response = requests.get(url, headers=headers, timeout=API_TIMEOUT)
            response.raise_for_status()
            user_data = response.json()
            if not user_data.get("blocked", False):
                unblocked.append(user_id)
            # Update spinner
            sys.stdout.write(f"\rChecking users... {spinner[spin_idx]} ({idx + 1}/{len(user_ids)})")
            sys.stdout.flush()
            spin_idx = (spin_idx + 1) % len(spinner)
            time.sleep(API_RATE_LIMIT)
        except requests.exceptions.RequestException:
            continue
    print("\n")  # Clear spinner line
    if unblocked:
        print(f"{YELLOW}Found {len(unblocked)} unblocked users:{RESET}")
        for user_id in unblocked:
            print(f"{CYAN}{user_id}{RESET}")
    else:
        print(f"{GREEN}All users are blocked.{RESET}")

def get_user_email(user_id: str, token: str, base_url: str) -> str | None:
    """Fetch user's email address from Auth0.
    
    Args:
        user_id: The Auth0 user ID
        token: Auth0 access token
        base_url: Auth0 API base URL
        
    Returns:
        str | None: User's email address if found, None otherwise
    """
    url = f"{base_url}/api/v2/users/{quote(user_id)}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
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