import requests
import time
import csv
from contextlib import suppress
from urllib.parse import quote
from utils import RED, GREEN, YELLOW, CYAN, RESET, shutdown_requested, show_progress
from rate_limit_config import (
    API_RATE_LIMIT, API_TIMEOUT, MAX_RETRIES, BASE_RETRY_DELAY, MAX_RETRY_DELAY,
    get_optimal_batch_size, get_estimated_processing_time, validate_rate_limit_config
)

def handle_rate_limit_response(response: requests.Response, attempt: int) -> bool:
    """Handle rate limit responses with exponential backoff.

    Args:
        response: The HTTP response that triggered rate limiting
        attempt: Current attempt number (1-based)

    Returns:
        bool: True if should retry, False if max retries exceeded
    """
    if response.status_code == 429:  # Too Many Requests
        if attempt >= MAX_RETRIES:
            print(f"{RED}Rate limit exceeded after {MAX_RETRIES} attempts. Stopping.{RESET}")
            return False

        # Calculate delay with exponential backoff
        delay = min(BASE_RETRY_DELAY * (2 ** (attempt - 1)), MAX_RETRY_DELAY)

        # Try to get retry-after header
        retry_after = response.headers.get('Retry-After')
        if retry_after:
            with suppress(ValueError):
                delay = max(delay, int(retry_after))

        print(f"{YELLOW}Rate limit hit. Waiting {delay} seconds before retry {attempt}/{MAX_RETRIES}...{RESET}")
        time.sleep(delay)
        return True

    return False

def make_rate_limited_request(method: str, url: str, headers: dict, **kwargs) -> requests.Response | None:
    """Make an HTTP request with rate limiting and retry logic.

    Args:
        method: HTTP method (GET, POST, etc.)
        url: Request URL
        headers: Request headers
        **kwargs: Additional request parameters

    Returns:
        requests.Response | None: Response object or None if failed after retries
    """
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.request(method, url, headers=headers, timeout=API_TIMEOUT, **kwargs)

            # Handle rate limiting
            if response.status_code == 429:
                if handle_rate_limit_response(response, attempt):
                    continue
                return None

            # Handle other errors
            if response.status_code >= 400:
                response.raise_for_status()

            # Success - apply rate limiting
            time.sleep(API_RATE_LIMIT)
            return response

        except requests.exceptions.RequestException as e:
            if attempt >= MAX_RETRIES:
                print(f"{RED}Request failed after {MAX_RETRIES} attempts: {e}{RESET}")
                return None
            delay = min(BASE_RETRY_DELAY * (2 ** (attempt - 1)), MAX_RETRY_DELAY)
            print(f"{YELLOW}Request failed, retrying in {delay} seconds... ({attempt}/{MAX_RETRIES}){RESET}")
            time.sleep(delay)

    return None

def delete_user(user_id: str, token: str, base_url: str) -> None:
    """Delete user from Auth0."""
    print(f"{YELLOW}Deleting user: {CYAN}{user_id}{YELLOW}{RESET}")

    # First revoke all sessions
    revoke_user_sessions(user_id, token, base_url)

    url = f"{base_url}/api/v2/users/{quote(user_id)}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": "DeletePy/1.0 (Auth0 User Management Tool)"
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
        "User-Agent": "DeletePy/1.0 (Auth0 User Management Tool)"
    }
    payload = {"blocked": True}
    try:
        response = requests.patch(url, headers=headers, json=payload, timeout=API_TIMEOUT)
        response.raise_for_status()
        print(f"{GREEN}Successfully blocked user {CYAN}{user_id}{GREEN}{RESET}")
        time.sleep(API_RATE_LIMIT)
    except requests.exceptions.RequestException as e:
        print(f"{RED}Error blocking user {CYAN}{user_id}{RED}: {e}{RESET}")

def get_user_id_from_email(email: str, token: str, base_url: str, connection: str = None) -> list[str] | None:
    """Fetch user_ids from Auth0 using email address. Returns list of user_ids or None if not found.

    Args:
        email: Email address to search for
        token: Auth0 access token
        base_url: Auth0 API base URL
        connection: Optional connection filter (e.g., "google-oauth2", "auth0", "facebook")

    Returns:
        list[str] | None: List of user IDs matching the email and connection filter
    """
    url = f"{base_url}/api/v2/users-by-email"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": "DeletePy/1.0 (Auth0 User Management Tool)"
    }
    params = {"email": email}

    response = make_rate_limited_request("GET", url, headers, params=params)
    if response is None:
        print(f"{RED}Error fetching user_id for email {CYAN}{email}{RED}: Request failed after retries{RESET}")
        return None

    try:
        users = response.json()
        if users and isinstance(users, list):
            user_ids = []
            for user in users:
                if "user_id" in user:
                    # If connection filter is specified, check if user matches
                    if connection:
                        user_details = get_user_details(user["user_id"], token, base_url)
                        if user_details and user_details.get("identities"):
                            user_connection = user_details["identities"][0].get("connection", "unknown")
                            if user_connection == connection:
                                user_ids.append(user["user_id"])
                    else:
                        # No connection filter, include all users
                        user_ids.append(user["user_id"])

            if user_ids:
                return user_ids
        return None
    except ValueError as e:
        print(f"{RED}Error parsing response for email {CYAN}{email}{RED}: {e}{RESET}")
        return None

def revoke_user_sessions(user_id: str, token: str, base_url: str) -> None:
    """Fetch all Auth0 sessions for a user and revoke them one by one."""
    list_url = f"{base_url}/api/v2/users/{quote(user_id)}/sessions"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": "DeletePy/1.0 (Auth0 User Management Tool)"
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
        "Content-Type": "application/json",
        "User-Agent": "DeletePy/1.0 (Auth0 User Management Tool)"
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
    total_users = len(user_ids)

    for idx, user_id in enumerate(user_ids, 1):
        if shutdown_requested:
            break
        url = f"{base_url}/api/v2/users/{quote(user_id)}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "DeletePy/1.0 (Auth0 User Management Tool)"
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
        "Content-Type": "application/json",
        "User-Agent": "DeletePy/1.0 (Auth0 User Management Tool)"
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

def get_user_details(user_id: str, token: str, base_url: str) -> dict | None:
    """Fetch user details from Auth0 including connection information.

    Args:
        user_id: The Auth0 user ID
        token: Auth0 access token
        base_url: Auth0 API base URL

    Returns:
        dict | None: User details if found, None otherwise
    """
    url = f"{base_url}/api/v2/users/{quote(user_id)}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": "DeletePy/1.0 (Auth0 User Management Tool)"
    }

    response = make_rate_limited_request("GET", url, headers)
    if response is None:
        print(f"{RED}Error fetching details for user {CYAN}{user_id}{RED}: Request failed after retries{RESET}")
        return None

    try:
        user_data = response.json()
        return user_data
    except ValueError as e:
        print(f"{RED}Error parsing response for user {CYAN}{user_id}{RED}: {e}{RESET}")
        return None

def export_users_last_login_to_csv(emails: list[str], token: str, base_url: str, output_file: str = "users_last_login.csv", batch_size: int = None, connection: str = None) -> None:
    """Fetch user data for given emails and export last_login values to CSV.

    Args:
        emails: List of email addresses to process
        token: Auth0 access token
        base_url: Auth0 API base URL
        output_file: Output CSV file path (default: users_last_login.csv)
        batch_size: Number of emails to process before writing to CSV (auto-calculated if None)
        connection: Optional connection filter (e.g., "google-oauth2", "auth0", "facebook")
    """
    # Validate rate limit configuration
    if not validate_rate_limit_config():
        print(f"{YELLOW}Warning: Rate limit configuration may be too aggressive.{RESET}")

    # Calculate optimal batch size if not provided
    if batch_size is None:
        batch_size = get_optimal_batch_size(len(emails))

    # Calculate estimated processing time
    estimated_time = get_estimated_processing_time(len(emails), batch_size)

    print(f"{YELLOW}Processing {len(emails)} email addresses...{RESET}")
    print(f"{YELLOW}Batch size: {batch_size} emails{RESET}")
    print(f"{YELLOW}Rate limit: {1.0/API_RATE_LIMIT:.1f} requests/second{RESET}")
    print(f"{YELLOW}Estimated time: {estimated_time:.1f} minutes{RESET}")

    if connection:
        print(f"{YELLOW}Connection filter: {CYAN}{connection}{YELLOW}{RESET}")

    # Prepare CSV data
    csv_data = []
    total_emails = len(emails)
    processed_count = 0
    not_found_count = 0
    multiple_users_count = 0
    error_count = 0

    # Process emails in batches
    for batch_start in range(0, total_emails, batch_size):
        batch_end = min(batch_start + batch_size, total_emails)
        batch_emails = emails[batch_start:batch_end]

        print(f"\n{YELLOW}Processing batch {batch_start//batch_size + 1}/{(total_emails + batch_size - 1)//batch_size} ({batch_start + 1}-{batch_end} of {total_emails}){RESET}")

        for idx, email in enumerate(batch_emails, batch_start + 1):
            if shutdown_requested:
                print(f"\n{YELLOW}Operation cancelled by user.{RESET}")
                break

            show_progress(idx - batch_start, len(batch_emails), f"Batch {batch_start//batch_size + 1}")

            # Trim whitespace
            email = email.strip()

            # Skip empty lines
            if not email:
                continue

            # Get user IDs for this email (with connection filter if specified)
            user_ids = get_user_id_from_email(email, token, base_url, connection)

            if not user_ids:
                not_found_count += 1
                csv_data.append({
                    'email': email,
                    'user_id': 'NOT_FOUND',
                    'connection': 'N/A',
                    'last_login': 'N/A',
                    'created_at': 'N/A',
                    'updated_at': 'N/A',
                    'status': 'NOT_FOUND'
                })
                continue

            if len(user_ids) > 1:
                multiple_users_count += 1
                # Process all users for this email
                for user_id in user_ids:
                    user_details = get_user_details(user_id, token, base_url)

                    if user_details:
                        # Extract connection information
                        connection_info = "unknown"
                        if user_details.get("identities") and len(user_details["identities"]) > 0:
                            connection_info = user_details["identities"][0].get("connection", "unknown")

                        csv_data.append({
                            'email': email,
                            'user_id': user_id,
                            'connection': connection_info,
                            'last_login': user_details.get('last_login', 'N/A'),
                            'created_at': user_details.get('created_at', 'N/A'),
                            'updated_at': user_details.get('updated_at', 'N/A'),
                            'status': f'MULTIPLE_USERS ({len(user_ids)})'
                        })
                    else:
                        csv_data.append({
                            'email': email,
                            'user_id': user_id,
                            'connection': 'unknown',
                            'last_login': 'N/A',
                            'created_at': 'N/A',
                            'updated_at': 'N/A',
                            'status': 'ERROR_FETCHING_DETAILS'
                        })
                continue

            # Get user details for single user
            user_id = user_ids[0]
            user_details = get_user_details(user_id, token, base_url)

            if user_details:
                processed_count += 1
                # Extract connection information
                connection_info = "unknown"
                if user_details.get("identities") and len(user_details["identities"]) > 0:
                    connection_info = user_details["identities"][0].get("connection", "unknown")

                csv_data.append({
                    'email': email,
                    'user_id': user_id,
                    'connection': connection_info,
                    'last_login': user_details.get('last_login', 'N/A'),
                    'created_at': user_details.get('created_at', 'N/A'),
                    'updated_at': user_details.get('updated_at', 'N/A'),
                    'status': 'SUCCESS'
                })
            else:
                error_count += 1
                csv_data.append({
                    'email': email,
                    'user_id': user_id,
                    'connection': 'unknown',
                    'last_login': 'N/A',
                    'created_at': 'N/A',
                    'updated_at': 'N/A',
                    'status': 'ERROR_FETCHING_DETAILS'
                })

        print("\n")  # Clear progress line

        # Write batch to CSV to avoid losing progress
        if csv_data:
            try:
                with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
                    fieldnames = ['email', 'user_id', 'connection', 'last_login', 'created_at', 'updated_at', 'status']
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    writer.writeheader()
                    for row in csv_data:
                        writer.writerow(row)

                print(f"{GREEN}✓ Batch {batch_start//batch_size + 1} saved to {CYAN}{output_file}{GREEN}{RESET}")

            except IOError as e:
                print(f"{RED}Error writing CSV file: {e}{RESET}")
                break

        if shutdown_requested:
            break

    # Final summary
    print(f"\n{YELLOW}Export Summary:{RESET}")
    print(f"Total emails processed: {total_emails}")
    print(f"Successfully processed: {processed_count}")
    print(f"Not found: {not_found_count}")
    print(f"Multiple users: {multiple_users_count}")
    print(f"Errors: {error_count}")

    if connection:
        print(f"Connection filter applied: {CYAN}{connection}{RESET}")

    if csv_data:
        print(f"{GREEN}Data exported to: {CYAN}{output_file}{GREEN}{RESET}")
    else:
        print(f"{RED}No data was exported.{RESET}")
