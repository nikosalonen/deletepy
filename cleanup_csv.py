import csv
import re
import sys
from typing import List, Optional
from auth import get_access_token
from config import get_base_url
from user_operations import get_user_details
from utils import (
    AUTH0_USER_ID_PREFIXES,
    is_auth0_user_id,
    safe_file_read,
    safe_file_write,
    FileOperationError,
    RED,
    RESET,
)


def find_best_column(headers: List[str], output_type: str = "user_id") -> Optional[str]:
    """Find the most likely column containing user identifiers or requested output type."""
    # First check for exact match based on output type
    if output_type == "email":
        for header in headers:
            if header.lower() in ["email", "email_address", "mail"]:
                return header
    elif output_type == "username":
        for header in headers:
            if header.lower() in ["username", "user_name", "name", "nickname"]:
                return header
    elif output_type == "user_id":
        for header in headers:
            if header.lower() == "user_id":
                return header

    # Then use fuzzy matching patterns based on output type
    if output_type == "email":
        patterns = [r"email", r"mail"]
    elif output_type == "username":
        patterns = [r"user.*name", r"username", r"name", r"nickname"]
    else:  # user_id or fallback
        patterns = [
            r"user.*id",
            r"user.*name",
            r"username",
            r"userid",
            r"email",
            r"identifier",
            r"subject",
            r"principal",
            r"detail\.data\.user",  # More specific: detail.data.user_name, detail.data.user_id
        ]

    for pattern in patterns:
        for header in headers:
            # Skip columns that are clearly not user identifiers
            if re.search(r"ip|address|location|geo", header.lower()):
                continue
            if re.search(pattern, header.lower()):
                return header

    return None


def resolve_encoded_username(username: str, env: str = None) -> str:
    """Resolve encoded username to actual email using Auth0 API.

    Note: Auth0 usernames cannot contain '@' - if there's an '@' it's already an email.
    Only encoded usernames with '_at_' or '__' patterns need resolution.

    Args:
        username: Encoded username (with _at_ or __) or regular identifier
        env: Environment to use for Auth0 API (dev/prod)

    Returns:
        Resolved email address or original identifier if resolution fails
    """
    if not username or not username.strip():
        return ""

    username = username.strip()

    # If it contains '@', it's already an email address (Auth0 usernames cannot have '@')
    if "@" in username:
        return username

    # If it's an Auth0 ID format, return as-is
    if is_auth0_user_id(username):
        return username

    # Only try to resolve if it contains encoded patterns
    if "_at_" not in username and "__" not in username:
        return username

    # Try to get Auth0 API access if env is provided
    if env:
        try:
            token = get_access_token(env)
            base_url = get_base_url(env)

            if token:
                # Search for user by encoded username
                user_details = _search_user_by_field(username, token, base_url)
                if user_details and user_details.get("email"):
                    return user_details["email"]
        except Exception:
            # If Auth0 API fails, fall back to string replacement
            pass

    # Fallback to string replacement (but warn about potential issues)
    if "_at_" in username:
        fallback = username.replace("_at_", "@")
        if env:  # Only show warning if we tried API and failed
            print(
                f"    ⚠️  API resolution failed for {username}, using fallback: {fallback}"
            )
        return fallback
    elif "__" in username:
        # This is problematic as noted - but we'll do it as fallback
        fallback = username.replace("__", "@")
        if env:  # Only show warning if we tried API and failed
            print(
                f"    ⚠️  API resolution failed for {username}, using fallback: {fallback} (may be incomplete)"
            )
        return fallback

    return username


def clean_identifier(
    value: str, env: str = None, preserve_encoded: bool = False
) -> str:
    """Clean and normalize user identifiers.

    Args:
        value: Raw identifier value
        env: Environment to use for Auth0 API resolution (optional)
        preserve_encoded: If True, keep encoded usernames as-is instead of resolving

    Returns:
        Cleaned identifier
    """
    if not value or value.strip() == "":
        return ""

    value = value.strip()

    # Handle encoded usernames with Auth0 API resolution
    if "_at_" in value or "__" in value:
        if preserve_encoded:
            # Keep encoded usernames as-is
            return value
        return resolve_encoded_username(value, env)

    return value


def extract_identifiers_from_csv(
    filename: str = "ids.csv",
    env: str = None,
    output_type: str = "user_id",
    interactive: bool = True,
) -> List[str]:
    """Extract user identifiers from CSV with fuzzy column matching.

    Args:
        filename: Input CSV file path
        env: Environment for Auth0 API resolution (dev/prod) - optional but recommended for encoded usernames
        output_type: Type of output desired (username|email|user_id)
        interactive: Whether to prompt user for input (default True, set False for testing)

    Returns:
        List of cleaned identifiers
    """
    identifiers = []
    skip_resolution = False

    try:
        with safe_file_read(filename) as infile:
            # Check if file has CSV headers by peeking at first line
            first_line = infile.readline()
            infile.seek(0)

            # If first line looks like an Auth0 ID or email, treat as plain text file
            if (
                first_line.strip().startswith(AUTH0_USER_ID_PREFIXES)
                or "@" in first_line
                or "__" in first_line
                or "_at_" in first_line
            ):
                print("Detected plain text file with identifiers")
                for line in infile:
                    cleaned = clean_identifier(line.strip(), env)
                    if cleaned:
                        identifiers.append(cleaned)
                return identifiers

            # Otherwise, treat as CSV
            reader = csv.DictReader(infile)
            headers = reader.fieldnames

            if not headers:
                print("No headers found in CSV file")
                return identifiers

            print(f"Available columns: {', '.join(headers)}")

            best_column = find_best_column(headers, output_type)

            if not best_column:
                print(
                    "Could not automatically detect identifier column. Available columns:"
                )
                for i, header in enumerate(headers):
                    print(f"  {i}: {header}")

                # For automated processing, use first column as fallback
                best_column = headers[0]
                print(f"Using first column as fallback: {best_column}")

            print(f"Using column: {best_column}")

            # Check if we should skip encoded username resolution for this column
            if (
                output_type == "username"
                and best_column
                and "user_name" in best_column.lower()
            ):
                skip_resolution = True
                print(
                    f"CSV column '{best_column}' contains username data. Skipping encoded username resolution."
                )
            elif (
                output_type == "email"
                and best_column
                and "email" in best_column.lower()
            ):
                skip_resolution = True
                print(
                    f"CSV column '{best_column}' contains email data. Skipping encoded username resolution."
                )

            for row in reader:
                if best_column in row:
                    # Preserve encoded usernames if we're looking for username output and found username column
                    preserve_encoded = skip_resolution and output_type == "username"
                    env_for_cleaning = None if skip_resolution else env
                    cleaned = clean_identifier(
                        row[best_column], env_for_cleaning, preserve_encoded
                    )
                    if cleaned:
                        identifiers.append(cleaned)

    except FileOperationError as e:
        print(f"{RED}Error reading file {filename}: {e}{RESET}")
        return []
    except csv.Error as e:
        print(f"{RED}CSV parsing error in {filename}: {e}{RESET}")
        return []
    except Exception as e:
        print(f"{RED}Unexpected error processing file {filename}: {e}{RESET}")
        return []

    # Check if we need to fetch additional data from Auth0
    # Skip if CSV already contains the requested data type or we already handled it above
    data_already_available = _check_if_data_available(identifiers, output_type)

    # If we haven't already handled column matching above, check here
    if not skip_resolution and not data_already_available and env:
        identifiers = _convert_to_output_type(identifiers, output_type, env)
    elif not skip_resolution and not data_already_available and not env:
        if interactive:
            print(
                f"\nWarning: Requested output type '{output_type}' but no environment specified."
            )
            response = (
                input(
                    "Do you want to fetch this data from Auth0? Specify environment (dev/prod) or press Enter to skip: "
                )
                .strip()
                .lower()
            )
            if response in ["dev", "prod"]:
                identifiers = _convert_to_output_type(
                    identifiers, output_type, response
                )
            else:
                print("Skipping Auth0 data fetch. Using original identifiers.")
        else:
            # Non-interactive mode - skip Auth0 data fetch
            pass
    elif data_already_available and not skip_resolution:
        print(f"CSV already contains {output_type} data. No Auth0 API calls needed.")

    return identifiers


def _check_if_data_available(identifiers: List[str], output_type: str) -> bool:
    """Check if the identifiers already contain the requested data type.

    Args:
        identifiers: List of identifiers from CSV
        output_type: Requested output type (username|email|user_id)

    Returns:
        True if data is already in the correct format
    """
    if not identifiers:
        return False

    # Sample the first few identifiers to determine type
    sample_size = min(5, len(identifiers))
    sample = identifiers[:sample_size]

    if output_type == "email":
        # Check if most samples are email addresses
        email_count = sum(
            1
            for item in sample
            if "@" in item and not item.startswith(AUTH0_USER_ID_PREFIXES)
        )
        return email_count >= len(sample) * 0.8  # 80% threshold
    elif output_type == "user_id":
        # Check if most samples are Auth0 user IDs
        user_id_count = sum(
            1 for item in sample if item.startswith(AUTH0_USER_ID_PREFIXES)
        )
        return user_id_count >= len(sample) * 0.8
    elif output_type == "username":
        # Check if samples look like usernames (not emails, not user_ids)
        username_count = sum(
            1
            for item in sample
            if "@" not in item and not item.startswith(AUTH0_USER_ID_PREFIXES)
        )
        return username_count >= len(sample) * 0.8

    return False


def write_identifiers_to_file(
    identifiers: List[str], filename: str = "ids.csv"
) -> bool:
    """Write cleaned identifiers to output file.

    Args:
        identifiers: List of identifiers to write
        filename: Output filename

    Returns:
        True if successful, False otherwise
    """
    try:
        with safe_file_write(filename) as outfile:
            for identifier in identifiers:
                outfile.write(f"{identifier}\n")
        return True

    except FileOperationError as e:
        print(f"{RED}Error writing to file {filename}: {e}{RESET}")
        return False
    except Exception as e:
        print(f"{RED}Unexpected error writing to file {filename}: {e}{RESET}")
        return False


def _convert_to_output_type(
    identifiers: List[str], output_type: str, env: str
) -> List[str]:
    """Convert identifiers to the requested output type using Auth0 API.

    Args:
        identifiers: List of user identifiers (emails, user_ids, etc.)
        output_type: Desired output type (username|email|user_id)
        env: Environment for Auth0 API calls

    Returns:
        List of converted identifiers
    """
    print(f"\nFetching {output_type} data from Auth0 API...")

    try:
        token = get_access_token(env)
        base_url = get_base_url(env)
    except Exception as e:
        print(f"Error getting Auth0 credentials: {e}")
        return identifiers

    converted = []
    total = len(identifiers)

    for idx, identifier in enumerate(identifiers, 1):
        if idx % 5 == 0 or idx == total:
            print(f"Processing {idx}/{total}...", end="\r")

        try:
            # Check if identifier is an encoded username (before cleaning)
            is_encoded_username = "_at_" in identifier or "__" in identifier

            if idx <= 3:  # Show details for first few items
                print(
                    f"\n[{idx}] Processing: {identifier[:50]}{'...' if len(identifier) > 50 else ''}"
                )
                if is_encoded_username:
                    print("    → Detected encoded username pattern")

            # Clean the identifier
            cleaned_identifier = clean_identifier(identifier, env)

            if idx <= 3 and cleaned_identifier != identifier:
                print(f"    → Resolved to: {cleaned_identifier}")

            # Check if identifier is already a user_id
            if is_auth0_user_id(cleaned_identifier):
                if idx <= 3:
                    print("    → Looking up user details by user_id")
                # Use get_user_details for user_id lookups
                user_details = get_user_details(cleaned_identifier, token, base_url)
            else:
                # For encoded usernames, search by the original encoded value as username
                search_value = identifier if is_encoded_username else cleaned_identifier
                if idx <= 3:
                    print(f"    → Searching Auth0 for: {search_value}")
                user_details = _search_user_by_field(search_value, token, base_url)

            if user_details:
                if idx <= 3:
                    print(f"    → Found user: {user_details.get('email', 'N/A')}")
                if output_type == "email":
                    value = user_details.get("email", identifier)
                elif output_type == "username":
                    value = user_details.get(
                        "username", user_details.get("email", identifier)
                    )
                elif output_type == "user_id":
                    value = user_details.get("user_id", identifier)
                else:
                    value = identifier
                converted.append(value)
                if idx <= 3:
                    print(f"    → Output ({output_type}): {value}")
            else:
                # If we can't fetch details, keep original identifier
                if idx <= 3:
                    print(f"    → User not found, keeping original: {identifier}")
                converted.append(identifier)
        except Exception as e:
            # On error, keep original identifier
            if idx <= 3:
                print(
                    f"    → Error occurred: {str(e)[:50]}{'...' if len(str(e)) > 50 else ''}, keeping original"
                )
            converted.append(identifier)

    print(f"\nCompleted processing {total} identifiers")
    success_count = sum(
        1
        for orig, conv in zip(identifiers, converted)
        if orig != conv or is_auth0_user_id(conv)
    )
    print(f"Successfully resolved: {success_count}/{total} identifiers")
    return converted


def _search_user_by_field(identifier: str, token: str, base_url: str) -> dict:
    """Search for a user using the appropriate Auth0 Management API endpoint.

    Args:
        identifier: Email or username to search for
        token: Auth0 access token
        base_url: Auth0 API base URL

    Returns:
        User details dict or None if not found
    """
    from user_operations import make_rate_limited_request, get_user_id_from_email

    if "@" in identifier:
        # Use the dedicated users-by-email endpoint for email lookups
        user_ids = get_user_id_from_email(identifier, token, base_url)
        if user_ids and len(user_ids) > 0:
            # Get full user details for the first user
            from user_operations import get_user_details

            return get_user_details(user_ids[0], token, base_url)
        return None
    else:
        # Use search API for username lookups
        url = f"{base_url}/api/v2/users"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "DeletePy/1.0 (Auth0 User Management Tool)",
        }

        # Username search
        params = {"q": f'username:"{identifier}"', "search_engine": "v3"}

        response = make_rate_limited_request("GET", url, headers, params=params)
        if response is None:
            return None

        try:
            users = response.json()
            if users and isinstance(users, list) and len(users) > 0:
                # Return the first match
                return users[0]
        except ValueError:
            return None

        return None


def _parse_arguments():
    """Parse command line arguments."""
    # Check for help flag
    if len(sys.argv) > 1 and sys.argv[1] in ["--help", "-h", "help"]:
        print(
            "Usage: python cleanup_csv.py [filename] [env] [--output-type=username|email|user_id]"
        )
        print("")
        print("Arguments:")
        print("  filename: CSV file to process (default: ids.csv)")
        print("  env: Environment for Auth0 API (dev|prod) - optional")
        print("  --output-type: Type of output desired (default: user_id)")
        print("")
        print("Output types:")
        print("  user_id: Auth0 user IDs (default)")
        print("  email: User email addresses")
        print("  username: User usernames (falls back to email if no username)")
        print("")
        print("Examples:")
        print("  python cleanup_csv.py")
        print("  python cleanup_csv.py ids.csv dev")
        print("  python cleanup_csv.py ids.csv dev --output-type=email")
        print("  python cleanup_csv.py ids.csv --output-type=username")
        return None, None, None

    if len(sys.argv) < 2:
        # Show minimal usage for no arguments
        print("Usage: python cleanup_csv.py [filename] [env] [--output-type=type]")
        print("Use --help for detailed usage information")
        return "ids.csv", None, "user_id"  # Use defaults

    filename = "ids.csv"
    env = None
    output_type = "user_id"

    args = sys.argv[1:]

    # Parse arguments
    for arg in args:
        if arg.startswith("--output-type="):
            output_type = arg.split("=")[1]
            if output_type not in ["username", "email", "user_id"]:
                print(
                    f"Error: Invalid output type '{output_type}'. Must be username, email, or user_id"
                )
                return None, None, None
        elif arg in ["dev", "prod"]:
            env = arg
        elif not arg.startswith("--"):
            filename = arg

    return filename, env, output_type


if __name__ == "__main__":
    filename, env, output_type = _parse_arguments()

    if filename is None:
        sys.exit(1)

    identifiers = extract_identifiers_from_csv(filename, env, output_type)
    if identifiers:
        success = write_identifiers_to_file(identifiers, filename)
        if success:
            print(f"Processed {len(identifiers)} identifiers")
            if env:
                print(f"Used {env} environment for Auth0 API resolution")
            if output_type != "user_id":
                print(f"Output type: {output_type}")
        else:
            print(f"{RED}Failed to write output file{RESET}")
            sys.exit(1)
    else:
        print("No identifiers found")
