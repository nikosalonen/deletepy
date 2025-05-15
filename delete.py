import requests
import sys
import time
from typing import List, Tuple
import os
from dotenv import load_dotenv
from pathlib import Path
import signal

# ANSI color codes
RESET = "\033[0m"
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"

# Graceful shutdown handler
shutdown_requested = False

def handle_shutdown(signum, frame):
    global shutdown_requested
    shutdown_requested = True
    # Clear spinner/progress line
    sys.stdout.write("\r" + " " * 80 + "\r")
    sys.stdout.flush()
    print(f"{YELLOW}\nOperation cancelled by user. Exiting...{RESET}")
    sys.exit(130)

# Register signal handler
signal.signal(signal.SIGINT, handle_shutdown)

def check_env_file():
    """Check if .env file exists"""
    if not Path('.env').is_file():
        sys.exit("Error: .env file not found. Please create a .env file with your credentials.")

def get_access_token(env: str = "dev") -> str:
    """Get access token from Auth0 using client credentials."""
    load_dotenv()

    # Map environment to config values
    env_config = {
        "prod": {
            "client_id": "CLIENT_ID",
            "client_secret": "CLIENT_SECRET",
            "auth0_domain": os.getenv("AUTH0_DOMAIN"),
            "api_url": os.getenv("URL")
        },
        "dev": {
            "client_id": "DEVELOPMENT_CLIENT_ID",
            "client_secret": "DEVELOPMENT_CLIENT_SECRET",
            "auth0_domain": os.getenv("DEV_AUTH0_DOMAIN"),
            "api_url": os.getenv("DEV_URL")
        }
    }

    if env not in env_config:
        raise ValueError("Environment must be either 'dev' or 'prod'")

    config = env_config[env]
    client_id = os.getenv(config["client_id"])
    client_secret = os.getenv(config["client_secret"])
    domain = config["auth0_domain"]

    url = f"https://{domain}/oauth/token"
    payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "audience": f"https://{domain}/api/v2/",
        "grant_type": "client_credentials"
    }
    response = requests.post(url, json=payload)
    response.raise_for_status()
    return response.json()["access_token"]

def validate_args() -> Tuple[str, str, bool, bool, bool, bool]:
    """Validate command line arguments and return input file path, environment, block flag, delete flag, revoke_grants_only flag, and check_unblocked flag."""
    if len(sys.argv) < 2:
        sys.exit("Usage: python delete.py <ids_file> [env] [--block|--delete|--revoke-grants-only|--check-unblocked]")
    input_file = sys.argv[1]
    env = "dev"
    block = False
    delete = False
    revoke_grants_only = False
    check_unblocked = False
    for arg in sys.argv[2:]:
        if arg == "--block":
            block = True
        elif arg == "--delete":
            delete = True
        elif arg == "--revoke-grants-only":
            revoke_grants_only = True
        elif arg == "--check-unblocked":
            check_unblocked = True
        elif arg in ("dev", "prod"):
            env = arg
    flags = [block, delete, revoke_grants_only, check_unblocked]
    if not any(flags):
        sys.exit("Error: You must specify one of --block, --delete, --revoke-grants-only, or --check-unblocked.")
    if sum(flags) > 1:
        sys.exit("Error: Only one of --block, --delete, --revoke-grants-only, or --check-unblocked can be specified.")
    return input_file, env, block, delete, revoke_grants_only, check_unblocked

def read_user_ids(filepath: str) -> List[str]:
    """Read user IDs from file."""
    try:
        with open(filepath, 'r') as f:
            return [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        sys.exit(f"Error: File {filepath} not found")
    except IOError as e:
        sys.exit(f"Error reading file: {e}")

def get_base_url(env: str = "dev") -> str:
    """Get base URL based on environment."""
    env_config = {
        "prod": {
            "auth0_domain": os.getenv("AUTH0_DOMAIN")
        },
        "dev": {
            "auth0_domain": os.getenv("DEV_AUTH0_DOMAIN")
        }
    }

    if env not in env_config:
        raise ValueError("Environment must be either 'dev' or 'prod'")

    return f"https://{env_config[env]['auth0_domain']}"

def delete_user(user_id: str, token: str, base_url: str) -> None:
    """Delete user from Auth0."""
    print(f"{YELLOW}Deleting user: {user_id}{RESET}")
    url = f"{base_url}/api/v2/users/{user_id}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    try:
        response = requests.delete(url, headers=headers)
        response.raise_for_status()
        print(f"{GREEN}Successfully deleted user {user_id}{RESET}")
    except requests.exceptions.RequestException as e:
        print(f"{RED}Error deleting user {user_id}: {e}{RESET}")

def block_user(user_id: str, token: str, base_url: str) -> None:
    """Block user in Auth0."""
    print(f"{YELLOW}Blocking user: {user_id}{RESET}")
    url = f"{base_url}/api/v2/users/{user_id}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload = {"blocked": True}
    try:
        response = requests.patch(url, headers=headers, json=payload)
        response.raise_for_status()
        print(f"{GREEN}Successfully blocked user {user_id}{RESET}")
    except requests.exceptions.RequestException as e:
        print(f"{RED}Error blocking user {user_id}: {e}{RESET}")

def get_user_id_from_email(email: str, token: str, base_url: str) -> str:
    """Fetch user_id from Auth0 using email address. Returns user_id or None if not found."""
    url = f"{base_url}/api/v2/users-by-email"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    params = {"email": email}
    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        users = response.json()
        if users and isinstance(users, list) and "user_id" in users[0]:
            return users[0]["user_id"]
        else:
            print(f"{YELLOW}Warning: No user found for email {email}{RESET}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"{RED}Error fetching user_id for email {email}: {e}{RESET}")
        return None

def revoke_user_sessions(user_id: str, token: str, base_url: str) -> None:
    """Fetch all Auth0 sessions for a user and revoke them one by one (requires Enterprise plan and delete:sessions scope)."""
    list_url = f"{base_url}/api/v2/users/{user_id}/sessions"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    try:
        response = requests.get(list_url, headers=headers)
        if response.status_code != 200:
            print(f"{YELLOW}Failed to fetch sessions for user {user_id}: {response.status_code} {response.text}{RESET}")
            return
        sessions = response.json().get("sessions", [])
        if not sessions:
            print(f"{YELLOW}No sessions found for user {user_id}{RESET}")
            return
        for session in sessions:
            if shutdown_requested:
                break
            session_id = session.get("id")
            if not session_id:
                continue
            del_url = f"{base_url}/api/v2/sessions/{session_id}"
            del_resp = requests.delete(del_url, headers=headers)
            if del_resp.status_code in (202, 204):
                print(f"{GREEN}Revoked session {session_id} for user {user_id}{RESET}")
            else:
                print(f"{YELLOW}Failed to revoke session {session_id} for user {user_id}: {del_resp.status_code} {del_resp.text}{RESET}")
            time.sleep(0.5)
    except requests.exceptions.RequestException as e:
        print(f"{RED}Error revoking sessions for user {user_id}: {e}{RESET}")

def revoke_user_grants(user_id: str, token: str, base_url: str) -> None:
    """Revoke all application grants (authorized applications) for a user in one call."""
    grants_url = f"{base_url}/api/v2/grants?user_id={user_id}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    try:
        response = requests.delete(grants_url, headers=headers)
        if response.status_code in (204, 200):
            print(f"{GREEN}Revoked all application grants for user {user_id}{RESET}")
        else:
            print(f"{YELLOW}Failed to revoke grants for user {user_id}: {response.status_code} {response.text}{RESET}")
        time.sleep(0.5)
    except requests.exceptions.RequestException as e:
        print(f"{RED}Error revoking grants for user {user_id}: {e}{RESET}")

def check_unblocked_users(user_ids, token, base_url):
    """Print user IDs that are not blocked, with a progress indicator."""
    unblocked = []
    spinner = ['|', '/', '-', '\\']
    spin_idx = 0
    for idx, user_id in enumerate(user_ids):
        if shutdown_requested:
            break
        url = f"{base_url}/api/v2/users/{user_id}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        try:
            response = requests.get(url, headers=headers)
            if response.status_code != 200:
                print(f"\n{YELLOW}Failed to fetch user {user_id}: {response.status_code} {response.text}{RESET}")
                continue
            user = response.json()
            if not user.get("blocked", False):
                unblocked.append(user_id)
        except requests.exceptions.RequestException as e:
            print(f"\n{RED}Error fetching user {user_id}: {e}{RESET}")
        # Print spinner/progress
        sys.stdout.write(f"\r{CYAN}Checking users... {spinner[spin_idx % len(spinner)]} ({idx+1}/{len(user_ids)}){RESET}")
        sys.stdout.flush()
        spin_idx += 1
        time.sleep(0.5)
    print()  # Newline after spinner
    if unblocked:
        print(f"{GREEN}The following user IDs are NOT blocked:{RESET}")
        for uid in unblocked:
            print(f"{GREEN}{uid}{RESET}")
    else:
        print(f"{YELLOW}All users are blocked or could not be checked.{RESET}")

def main():
    try:
        check_env_file()
        input_file, env, block, delete, revoke_grants_only, check_unblocked = validate_args()

        # Add warning for production environment
        if env == "prod":
            if block:
                action = "block"
            elif delete:
                action = "delete"
            elif revoke_grants_only:
                action = "revoke all grants"
            elif check_unblocked:
                action = "check unblocked status"
            confirmation = input(f"\n⚠️  WARNING: You are about to {action} for users in PRODUCTION environment!\nAre you sure you want to continue? (yes/no): ")
            if confirmation.lower() != "yes":
                sys.exit("Operation cancelled by user.")
            print(f"\nProceeding with production {action}...\n")

        token = get_access_token(env)
        user_ids = read_user_ids(input_file)
        base_url = get_base_url(env)

        if check_unblocked:
            # Only check unblocked status
            # If input is email, convert to user_id
            resolved_ids = []
            for user in user_ids:
                if "@" in user and "." in user:
                    user_id = get_user_id_from_email(user, token, base_url)
                    if user_id:
                        resolved_ids.append(user_id)
                else:
                    resolved_ids.append(user)
            check_unblocked_users(resolved_ids, token, base_url)
            return
        for user in user_ids:
            # If input looks like an email, fetch user_id
            if "@" in user and "." in user:
                user_id = get_user_id_from_email(user, token, base_url)
                if not user_id:
                    continue
            else:
                user_id = user
            if revoke_grants_only:
                # Only revoke sessions and application grants
                revoke_user_sessions(user_id, token, base_url)
                time.sleep(0.5)
                revoke_user_grants(user_id, token, base_url)
                time.sleep(0.5)
            else:
                if block:
                    block_user(user_id, token, base_url)
                elif delete:
                    delete_user(user_id, token, base_url)
                # Revoke sessions (for full logout) and application grants (which also revokes all refresh tokens)
                revoke_user_sessions(user_id, token, base_url)
                time.sleep(0.5)
                revoke_user_grants(user_id, token, base_url)
                time.sleep(0.5)
            time.sleep(0.5)
    except KeyboardInterrupt:
        handle_shutdown(None, None)
    except Exception as e:
        sys.exit(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    main()
