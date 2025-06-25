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
                        # Check if identities array exists in the response and filter directly
                        if user.get("identities") and isinstance(user["identities"], list):
                            # Filter by connection using data already in the response
                            user_connection = user["identities"][0].get("connection", "unknown")
                            if user_connection == connection:
                                user_ids.append(user["user_id"])
                        else:
                            # Fallback: identities not included, skip this user to avoid API call
                            print(f"{RED}Warning: Connection info not available for user {user['user_id']}, skipping{RESET}")
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

def _validate_and_setup_export(emails: list[str], output_file: str, batch_size: int | None, connection: str | None) -> tuple[int, float]:
    """Validate export parameters and setup configuration.
    
    Args:
        emails: List of email addresses to process
        output_file: Output CSV file path
        batch_size: Number of emails to process before writing to CSV (auto-calculated if None)
        connection: Optional connection filter
        
    Returns:
        tuple[int, float]: (batch_size, estimated_time)
        
    Raises:
        PermissionError: If the output file path is not writable
        FileNotFoundError: If the output directory does not exist
    """
    # Validate output file path is writable
    try:
        with open(output_file, 'w', encoding='utf-8'):
            pass  # Just test if we can open for writing
    except PermissionError as e:
        raise PermissionError(f"Output file path is not writable: {output_file}") from e
    except FileNotFoundError as e:
        raise FileNotFoundError(f"Output directory does not exist: {output_file}") from e
    except Exception as e:
        raise IOError(f"Cannot write to output file: {output_file}") from e
    
    # Validate rate limit configuration
    if not validate_rate_limit_config():
        print(f"{YELLOW}Warning: Rate limit configuration may be too aggressive.{RESET}")

    # Calculate optimal batch size if not provided
    if batch_size is None:
        batch_size = get_optimal_batch_size(len(emails))

    # Calculate estimated processing time
    estimated_time = get_estimated_processing_time(len(emails), batch_size)

    # Print setup information
    print(f"{YELLOW}Processing {len(emails)} email addresses...{RESET}")
    print(f"{YELLOW}Batch size: {batch_size} emails{RESET}")
    print(f"{YELLOW}Rate limit: {1.0/API_RATE_LIMIT:.1f} requests/second{RESET}")
    print(f"{YELLOW}Estimated time: {estimated_time:.1f} minutes{RESET}")

    if connection:
        print(f"{YELLOW}Connection filter: {CYAN}{connection}{YELLOW}{RESET}")
    
    return batch_size, estimated_time

def _fetch_user_data(email: str, token: str, base_url: str, connection: str | None) -> tuple[list[dict], dict]:
    """Fetch user data for a single email address.
    
    Args:
        email: Email address to process
        token: Auth0 access token
        base_url: Auth0 API base URL
        connection: Optional connection filter
        
    Returns:
        tuple[list[dict], dict]: (csv_rows, counters_dict)
        counters_dict contains: processed_count, not_found_count, multiple_users_count, error_count
    """
    csv_rows = []
    counters = {
        'processed_count': 0,
        'not_found_count': 0,
        'multiple_users_count': 0,
        'error_count': 0
    }
    
    # Trim whitespace and skip empty lines
    email = email.strip()
    if not email:
        return csv_rows, counters

    # Get user IDs for this email (with connection filter if specified)
    user_ids = get_user_id_from_email(email, token, base_url, connection)

    if not user_ids:
        counters['not_found_count'] += 1
        csv_rows.append({
            'email': email,
            'user_id': 'NOT_FOUND',
            'connection': 'N/A',
            'last_login': 'N/A',
            'created_at': 'N/A',
            'updated_at': 'N/A',
            'status': 'NOT_FOUND'
        })
        return csv_rows, counters

    if len(user_ids) > 1:
        counters['multiple_users_count'] += 1
        # Process all users for this email
        for user_id in user_ids:
            user_details = get_user_details(user_id, token, base_url)

            if user_details:
                csv_rows.append(_build_csv_data_dict(email, user_id, user_details, f'MULTIPLE_USERS ({len(user_ids)})'))
            else:
                csv_rows.append(_build_csv_data_dict(email, user_id, None, 'ERROR_FETCHING_DETAILS'))
        return csv_rows, counters

    # Get user details for single user
    user_id = user_ids[0]
    user_details = get_user_details(user_id, token, base_url)

    if user_details:
        counters['processed_count'] += 1
        csv_rows.append(_build_csv_data_dict(email, user_id, user_details, 'SUCCESS'))
    else:
        counters['error_count'] += 1
        csv_rows.append(_build_csv_data_dict(email, user_id, None, 'ERROR_FETCHING_DETAILS'))

    return csv_rows, counters

def _process_email_batch(batch_emails: list[str], token: str, base_url: str, connection: str | None, batch_start: int, batch_number: int) -> tuple[list[dict], dict]:
    """Process a batch of email addresses.
    
    Args:
        batch_emails: List of email addresses in this batch
        token: Auth0 access token
        base_url: Auth0 API base URL
        connection: Optional connection filter
        batch_start: Starting index for progress display
        batch_number: Current batch number for progress display
        
    Returns:
        tuple[list[dict], dict]: (csv_data, total_counters)
    """
    csv_data = []
    total_counters = {
        'processed_count': 0,
        'not_found_count': 0,
        'multiple_users_count': 0,
        'error_count': 0
    }

    for idx, email in enumerate(batch_emails, batch_start + 1):
        if shutdown_requested:
            print(f"\n{YELLOW}Operation cancelled by user.{RESET}")
            break

        show_progress(idx - batch_start, len(batch_emails), f"Batch {batch_number}")

        # Fetch user data for this email
        email_csv_data, email_counters = _fetch_user_data(email, token, base_url, connection)
        
        # Add to batch data
        csv_data.extend(email_csv_data)
        
        # Update counters
        for key in total_counters:
            total_counters[key] += email_counters[key]

    return csv_data, total_counters

def _write_csv_batch(csv_data: list[dict], output_file: str, batch_number: int) -> bool:
    """Write CSV batch data to file.
    
    Args:
        csv_data: List of CSV row dictionaries
        output_file: Output CSV file path
        batch_number: Current batch number for logging
        
    Returns:
        bool: True if successful, False if error occurred
    """
    if not csv_data:
        return True
        
    try:
        with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['email', 'user_id', 'connection', 'last_login', 'created_at', 'updated_at', 'status']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for row in csv_data:
                writer.writerow(row)

        print(f"{GREEN}✓ Batch {batch_number} saved to {CYAN}{output_file}{GREEN}{RESET}")
        return True

    except IOError as e:
        print(f"{RED}Error writing CSV file: {e}{RESET}")
        return False

def _generate_export_summary(total_emails: int, processed_count: int, not_found_count: int, multiple_users_count: int, error_count: int, connection: str | None, output_file: str, csv_data: list[dict]) -> None:
    """Generate and print export summary.
    
    Args:
        total_emails: Total number of emails processed
        processed_count: Number of successfully processed users
        not_found_count: Number of emails not found
        multiple_users_count: Number of emails with multiple users
        error_count: Number of errors encountered
        connection: Connection filter applied (if any)
        output_file: Output CSV file path
        csv_data: CSV data list to check if any data was exported
    """
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

def _build_csv_data_dict(email: str, user_id: str, user_details: dict | None, status: str) -> dict:
    """Build CSV data dictionary for user export.
    
    Args:
        email: User's email address
        user_id: Auth0 user ID
        user_details: User details from Auth0 API (None if error fetching)
        status: Status string for the CSV record
        
    Returns:
        dict: CSV data dictionary with standardized fields
    """
    if user_details:
        # Extract connection information
        connection_info = "unknown"
        if user_details.get("identities") and len(user_details["identities"]) > 0:
            connection_info = user_details["identities"][0].get("connection", "unknown")
        
        return {
            'email': email,
            'user_id': user_id,
            'connection': connection_info,
            'last_login': user_details.get('last_login', 'N/A'),
            'created_at': user_details.get('created_at', 'N/A'),
            'updated_at': user_details.get('updated_at', 'N/A'),
            'status': status
        }
    else:
        # No user details available
        return {
            'email': email,
            'user_id': user_id,
            'connection': 'unknown',
            'last_login': 'N/A',
            'created_at': 'N/A',
            'updated_at': 'N/A',
            'status': status
        }

def unlink_user_identity(user_id: str, provider: str, user_identity_id: str, token: str, base_url: str) -> bool:
    """Unlink a specific identity from a user.
    
    Args:
        user_id: The Auth0 user ID
        provider: The identity provider (e.g., 'google-oauth2', 'facebook') 
        user_identity_id: The user ID for that identity provider
        token: Auth0 access token
        base_url: Auth0 API base URL
        
    Returns:
        bool: True if successful, False otherwise
    """
    url = f"{base_url}/api/v2/users/{quote(user_id)}/identities/{provider}/{quote(user_identity_id)}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json", 
        "User-Agent": "DeletePy/1.0 (Auth0 User Management Tool)"
    }
    
    response = make_rate_limited_request("DELETE", url, headers)
    if response is None:
        print(f"{RED}Error unlinking identity {CYAN}{user_identity_id}{RED} from user {CYAN}{user_id}{RED}: Request failed after retries{RESET}")
        return False
        
    try:
        # Success response should be 200/204
        if response.status_code in [200, 204]:
            print(f"{GREEN}Successfully unlinked identity {CYAN}{user_identity_id}{GREEN} ({provider}) from user {CYAN}{user_id}{GREEN}{RESET}")
            return True
        else:
            print(f"{RED}Failed to unlink identity {CYAN}{user_identity_id}{RED} from user {CYAN}{user_id}{RED}: HTTP {response.status_code}{RESET}")
            return False
    except Exception as e:
        print(f"{RED}Error unlinking identity {CYAN}{user_identity_id}{RED} from user {CYAN}{user_id}{RED}: {e}{RESET}")
        return False

def find_users_by_social_media_ids(social_ids: list[str], token: str, base_url: str, env: str = "dev", auto_delete: bool = True) -> None:
    """Find Auth0 users who have the specified social media IDs in their identities array.
    
    If auto_delete is True, users where the social media ID is their main/only identity will be deleted.

    Args:
        social_ids: List of social media IDs to search for
        token: Auth0 access token
        base_url: Auth0 API base URL
        env: Environment (dev/prod) for confirmation prompts
        auto_delete: Whether to automatically delete users with main identity matches
    """
    print(f"{YELLOW}Searching for users with {len(social_ids)} social media IDs...{RESET}")
    
    found_users = []
    not_found_ids = []
    users_to_delete = []  # Users where social ID is only non-auth0 identity  
    identities_to_unlink = []  # Identities to unlink from multi-identity users
    auth0_main_protected = []  # Users with auth0 as main identity (protected)
    total_ids = len(social_ids)
    
    for idx, social_id in enumerate(social_ids, 1):
        if shutdown_requested:
            break
            
        show_progress(idx, total_ids, "Searching social IDs")
        
        # Trim whitespace from social ID
        social_id = social_id.strip()
        if not social_id:
            continue
            
        # Search for users with this social ID in their identities
        # Using the users endpoint with a Lucene query to search identities
        url = f"{base_url}/api/v2/users"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "DeletePy/1.0 (Auth0 User Management Tool)"
        }
        
        # Use q parameter to search for the social ID in identities
        params = {
            "q": f'identities.user_id:"{social_id}"',
            "search_engine": "v3"
        }
        
        response = make_rate_limited_request("GET", url, headers, params=params)
        if response is None:
            print(f"{RED}Error searching for social ID {CYAN}{social_id}{RED}: Request failed after retries{RESET}")
            continue
            
        try:
            users = response.json()
            if users and isinstance(users, list) and len(users) > 0:
                for user in users:
                    user_id = user.get("user_id", "unknown")
                    email = user.get("email", "N/A")
                    identities = user.get("identities", [])
                    
                    # Find the matching identity and get main identity info
                    matching_identity = None
                    main_identity = identities[0] if identities else None
                    main_connection = main_identity.get("connection", "unknown") if main_identity else "unknown"
                    
                    if identities:
                        # Find the specific identity that matches our social ID
                        for identity in identities:
                            if identity.get("user_id") == social_id:
                                matching_identity = identity
                                break
                    
                    if not matching_identity:
                        continue  # Skip if no matching identity found
                    
                    matching_connection = matching_identity.get("connection", "unknown")
                    
                    user_info = {
                        "social_id": social_id,
                        "user_id": user_id,
                        "email": email,
                        "matching_connection": matching_connection,
                        "main_connection": main_connection,
                        "identities_count": len(identities),
                        "matching_identity": matching_identity,
                        "is_main_identity": matching_identity == main_identity
                    }
                    
                    found_users.append(user_info)
                    
                    # Apply new logic based on requirements
                    if auto_delete:
                        if main_connection == "auth0":
                            # Main identity is auth0 - protect entire user
                            auth0_main_protected.append(user_info)
                        elif len(identities) == 1:
                            # Single non-auth0 identity - delete entire user
                            users_to_delete.append(user_info)
                        else:
                            # Multiple identities with non-auth0 main - unlink the matching identity
                            identities_to_unlink.append(user_info)
            else:
                not_found_ids.append(social_id)
                
        except ValueError as e:
            print(f"{RED}Error parsing search results for social ID {CYAN}{social_id}{RED}: {e}{RESET}")
            continue
    
    print("\n")  # Clear progress line
    
    # Print results
    print(f"\n{YELLOW}Social Media ID Search Results:{RESET}")
    print(f"Total social IDs searched: {total_ids}")
    print(f"Users found: {len(found_users)}")
    print(f"Not found: {len(not_found_ids)}")
    
    if users_to_delete and auto_delete:
        print(f"\n{RED}Users to delete (single non-auth0 identity): {len(users_to_delete)}{RESET}")
        for user in users_to_delete:
            print(f"  Social ID: {CYAN}{user['social_id']}{RESET}")
            print(f"  User ID: {CYAN}{user['user_id']}{RESET}")
            print(f"  Email: {CYAN}{user['email']}{RESET}")
            print(f"  Connection: {CYAN}{user['matching_connection']}{RESET}")
            print(f"  Identities: {user['identities_count']} (single identity)")
            print()
    
    if identities_to_unlink and auto_delete:
        print(f"\n{YELLOW}Identities to unlink (multi-identity users): {len(identities_to_unlink)}{RESET}")
        for user in identities_to_unlink:
            main_status = " (main)" if user['is_main_identity'] else ""
            print(f"  Social ID: {CYAN}{user['social_id']}{RESET}")
            print(f"  User ID: {CYAN}{user['user_id']}{RESET}")
            print(f"  Email: {CYAN}{user['email']}{RESET}")
            print(f"  Identity to unlink: {CYAN}{user['matching_connection']}{RESET}{main_status}")
            print(f"  Main identity: {CYAN}{user['main_connection']}{RESET}")
            print(f"  Total identities: {user['identities_count']}")
            print()
    
    if auth0_main_protected:
        print(f"\n{GREEN}Users with auth0 main identity (protected): {len(auth0_main_protected)}{RESET}")
        for user in auth0_main_protected:
            print(f"  Social ID: {CYAN}{user['social_id']}{RESET}")
            print(f"  User ID: {CYAN}{user['user_id']}{RESET}")
            print(f"  Email: {CYAN}{user['email']}{RESET}")
            print(f"  Main connection: {CYAN}{user['main_connection']}{RESET}")
            print(f"  Identities: {user['identities_count']} (auth0 main - protected)")
            print()
    
    # Handle remaining found users that don't fall into above categories
    other_users = [u for u in found_users if u not in users_to_delete and u not in identities_to_unlink and u not in auth0_main_protected]
    if other_users:
        print(f"\n{GREEN}Other found users:{RESET}")
        for user in other_users:
            print(f"  Social ID: {CYAN}{user['social_id']}{RESET}")
            print(f"  User ID: {CYAN}{user['user_id']}{RESET}")
            print(f"  Email: {CYAN}{user['email']}{RESET}")
            print(f"  Matching connection: {CYAN}{user['matching_connection']}{RESET}")
            print(f"  Identities: {user['identities_count']}")
            print()
    
    if not_found_ids:
        print(f"\n{YELLOW}Social IDs not found:{RESET}")
        for social_id in not_found_ids:
            print(f"  {CYAN}{social_id}{RESET}")
    
    # Handle operations if there are users to delete or identities to unlink
    total_operations = len(users_to_delete) + len(identities_to_unlink)
    
    if total_operations > 0 and auto_delete:
        # Get confirmation for production environment
        if env == "prod":
            print(f"\n{RED}WARNING: You are about to perform operations in PRODUCTION environment:{RESET}")
            print(f"- Delete {len(users_to_delete)} users")
            print(f"- Unlink {len(identities_to_unlink)} identities")
            print("These actions cannot be undone.")
            response = input("Are you sure you want to proceed? (yes/no): ").lower().strip()
            if response != "yes":
                print("Operations cancelled by user.")
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
                    delete_user(user['user_id'], token, base_url)
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
                        user['user_id'],
                        user['matching_connection'],
                        user['social_id'],
                        token,
                        base_url
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

def export_users_last_login_to_csv(emails: list[str], token: str, base_url: str, output_file: str = "users_last_login.csv", batch_size: int = None, connection: str = None) -> None:
    """Fetch user data for given emails and export last_login values to CSV.

    Args:
        emails: List of email addresses to process
        token: Auth0 access token
        base_url: Auth0 API base URL
        output_file: Output CSV file path (default: users_last_login.csv)
        batch_size: Number of emails to process before writing to CSV (auto-calculated if None)
        connection: Optional connection filter (e.g., "google-oauth2", "auth0", "facebook")
    
    Raises:
        PermissionError: If the output file path is not writable
        FileNotFoundError: If the output directory does not exist
    """
    # Validate and setup export parameters
    batch_size, estimated_time = _validate_and_setup_export(emails, output_file, batch_size, connection)
    
    # Initialize counters and data
    csv_data = []
    total_emails = len(emails)
    total_counters = {
        'processed_count': 0,
        'not_found_count': 0,
        'multiple_users_count': 0,
        'error_count': 0
    }

    # Process emails in batches
    for batch_start in range(0, total_emails, batch_size):
        batch_end = min(batch_start + batch_size, total_emails)
        batch_emails = emails[batch_start:batch_end]
        batch_number = batch_start // batch_size + 1
        total_batches = (total_emails + batch_size - 1) // batch_size

        print(f"\n{YELLOW}Processing batch {batch_number}/{total_batches} ({batch_start + 1}-{batch_end} of {total_emails}){RESET}")

        # Process this batch
        batch_csv_data, batch_counters = _process_email_batch(batch_emails, token, base_url, connection, batch_start, batch_number)
        
        # Add batch data to total
        csv_data.extend(batch_csv_data)
        for key in total_counters:
            total_counters[key] += batch_counters[key]

        print("\n")  # Clear progress line

        # Write batch to CSV to avoid losing progress
        if not _write_csv_batch(csv_data, output_file, batch_number):
            break

        if shutdown_requested:
            break

    # Generate final summary
    _generate_export_summary(
        total_emails, 
        total_counters['processed_count'],
        total_counters['not_found_count'],
        total_counters['multiple_users_count'],
        total_counters['error_count'],
        connection,
        output_file,
        csv_data
    )
