"""CSV processing utilities for Auth0 user management."""

import csv
import re
from typing import Any, NamedTuple, TextIO, cast

from ..core.auth import get_access_token
from ..core.config import get_base_url
from ..core.exceptions import FileOperationError
from ..operations.user_ops import get_user_details
from ..utils.display_utils import (
    print_error,
    print_info,
    print_warning,
)
from ..utils.request_utils import make_rate_limited_request
from .auth_utils import AUTH0_USER_ID_PREFIXES, is_auth0_user_id
from .file_utils import safe_file_read, safe_file_write


def sanitize_identifiers(identifiers: list[str]) -> list[str]:
    """Sanitize identifiers by redacting sensitive data.

    Args:
        identifiers: List of identifiers to sanitize.

    Returns:
        List of sanitized identifiers.
    """
    redacted_keywords = ["client_secret", "auth0"]
    return [
        identifier
        if not any(keyword in identifier.lower() for keyword in redacted_keywords)
        else "[REDACTED]"
        for identifier in identifiers
    ]


class CsvRowData(NamedTuple):
    """Data structure to hold CSV row information for enhanced processing."""

    identifier: str
    user_id: str | None
    row_data: dict[str, str]


def find_best_column(headers: list[str], output_type: str = "user_id") -> str | None:
    """Find the most likely column containing user identifiers or requested output type.

    Args:
        headers: List of CSV column headers
        output_type: Type of output desired (username|email|user_id)

    Returns:
        Best matching column name or None if no match found
    """
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
        # For email output, prefer user_name column since it often contains email-like data
        patterns = [r"user.*name", r"username", r"email", r"mail"]
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
            if re.search(
                r"ip|address|location|geo|timestamp|time|date", header.lower()
            ):
                continue
            if re.search(pattern, header.lower()):
                return header

    return None


def resolve_encoded_username(username: str, env: str | None = None) -> str:
    """Resolve encoded username to actual email using Auth0 API.

    Note: Auth0 usernames cannot contain '@' - if there's an '@' it's already an email.
    Only encoded usernames with '_at_' or '__' patterns need resolution.

    Args:
        username: Encoded username (with _at_ or __) or regular identifier
        env: Environment to use for Auth0 API (dev/prod)

    Returns:
        Resolved email address or original identifier if resolution fails
    """
    validated_username = _validate_username_input(username)
    if not validated_username:
        return ""

    if not _needs_username_resolution(validated_username):
        return validated_username

    # Try Auth0 API resolution if env is provided
    if env:
        resolved = _try_auth0_username_resolution(validated_username, env)
        if resolved:
            return resolved

    # Fallback to string replacement
    return _apply_username_fallback(validated_username, env)


def _validate_username_input(username: str) -> str:
    """Validate and clean username input.

    Args:
        username: Raw username input

    Returns:
        Cleaned username or empty string if invalid
    """
    if not username or not username.strip():
        return ""
    return username.strip()


def _needs_username_resolution(username: str) -> bool:
    """Check if username needs resolution to email.

    Args:
        username: Cleaned username

    Returns:
        True if resolution is needed, False if already resolved
    """
    # If it contains '@', it's already an email address (Auth0 usernames cannot have '@')
    if "@" in username:
        return False

    # If it's an Auth0 ID format, return as-is
    if is_auth0_user_id(username):
        return False

    # Only try to resolve if it contains encoded patterns
    if "_at_" not in username and "__" not in username:
        return False

    return True


def _try_auth0_username_resolution(username: str, env: str) -> str | None:
    """Try to resolve encoded username using Auth0 API.

    Args:
        username: Encoded username to resolve
        env: Environment for Auth0 API

    Returns:
        Resolved email or None if resolution fails
    """
    try:
        token = get_access_token(env)
        base_url = get_base_url(env)

        if token:
            # Search for user by encoded username
            user_details = _search_user_by_field(username, token, base_url)
            if user_details:
                email = user_details.get("email")
                if email is not None and isinstance(email, str):
                    return cast(str, email)
    except Exception:
        # If Auth0 API fails, fall back to string replacement
        pass

    return None


def _apply_username_fallback(username: str, env: str | None) -> str:
    """Apply string replacement fallback for encoded usernames.

    Args:
        username: Encoded username
        env: Environment (for warning context)

    Returns:
        Username with string replacement applied
    """
    if "_at_" in username:
        fallback = username.replace("_at_", "@")
        if env:  # Only show warning if we tried API and failed
            print_warning(
                f"API resolution failed for {username}, using fallback: {fallback}"
            )
        return fallback
    elif "__" in username:
        # This is problematic as noted - but we'll do it as fallback
        fallback = username.replace("__", "@")
        if env:  # Only show warning if we tried API and failed
            print_warning(
                f"API resolution failed for {username}, using fallback: {fallback} (may be incomplete)"
            )
        return fallback

    return username


def clean_identifier(
    value: str, env: str | None = None, preserve_encoded: bool = False
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


def _detect_file_type(first_line: str) -> str:
    """Detect whether file is plain text or CSV based on first line.

    Args:
        first_line: First line of the file

    Returns:
        'plain_text' or 'csv'
    """
    first_line = first_line.strip()

    # Check if it's a CSV header line (contains commas and looks like column names)
    if "," in first_line:
        # If it contains commas, likely CSV - check if it looks like headers
        parts = first_line.split(",")
        if len(parts) > 1:
            # Check if parts look like column headers (contain descriptive text)
            header_indicators = [
                "timestamp",
                "ip",
                "user",
                "data",
                "type",
                "id",
                "name",
                "email",
            ]
            if any(
                indicator in part.lower()
                for part in parts
                for indicator in header_indicators
            ):
                return "csv"
            # If comma-separated but doesn't look like headers, check if first part is an identifier
            first_part = parts[0].strip()
            if (
                first_part.startswith(AUTH0_USER_ID_PREFIXES)
                or ("@" in first_part and "." in first_part)  # email-like
                or "__" in first_part
                or "_at_" in first_part
            ):
                return "plain_text"
        return "csv"

    # If no commas, check if it looks like a single identifier
    if (
        first_line.startswith(AUTH0_USER_ID_PREFIXES)
        or ("@" in first_line and "." in first_line)  # email-like pattern
        or "__" in first_line
        or "_at_" in first_line
    ):
        return "plain_text"

    return "csv"


def _process_plain_text(infile: TextIO, env: str | None = None) -> list[str]:
    """Process plain text file with identifiers.

    Args:
        infile: File object to read from
        env: Environment for Auth0 API resolution

    Returns:
        List of cleaned identifiers
    """
    print_info("Detected plain text file with identifiers")
    identifiers = []

    for line in infile:
        cleaned = clean_identifier(line.strip(), env)
        if cleaned:
            identifiers.append(cleaned)

    return identifiers


def _process_csv_file(
    infile: TextIO, output_type: str = "user_id", env: str | None = None
) -> tuple[list[str | CsvRowData], bool]:
    """Process CSV file and extract identifiers with row context.

    Args:
        infile: File object to read from
        output_type: Type of output desired (username|email|user_id)
        env: Environment for Auth0 API resolution

    Returns:
        Tuple of (identifiers/row_data list, skip_resolution flag)
    """
    reader, headers = _setup_csv_reader(infile)
    if not headers or not reader:
        return [], False

    best_column, user_id_column = _determine_csv_columns(headers, output_type)
    skip_resolution = _setup_processing_config(best_column, output_type)

    identifiers = _process_csv_rows(
        reader, best_column, user_id_column, output_type, env, skip_resolution
    )

    return identifiers, skip_resolution


def _setup_csv_reader(
    infile: TextIO,
) -> tuple[csv.DictReader[str] | None, list[str] | None]:
    """Setup CSV reader and validate headers.

    Args:
        infile: File object to read from

    Returns:
        Tuple of (reader, headers) or (None, None) if invalid
    """
    reader = csv.DictReader(infile)
    headers = reader.fieldnames

    if not headers:
        print_error("No headers found in CSV file")
        return None, None

    print_info(f"Available columns: {', '.join(headers)}")
    return reader, list(headers)


def _determine_csv_columns(
    headers: list[str], output_type: str
) -> tuple[str, str | None]:
    """Determine the best column to use and find user_id column for fallback.

    Args:
        headers: List of CSV headers
        output_type: Type of output desired

    Returns:
        Tuple of (best_column, user_id_column)
    """
    best_column = find_best_column(headers, output_type)

    if not best_column:
        print_error(
            "Could not automatically detect identifier column. Available columns:"
        )
        for i, header in enumerate(headers):
            print(f"  {i}: {header}")

        # For automated processing, use first column as fallback
        best_column = headers[0]
        print_info(f"Using first column as fallback: {best_column}")

    print_info(f"Using column: {best_column}")

    # Find user_id column for fallback lookup
    user_id_column = None
    for header in headers:
        if header.lower() == "user_id":
            user_id_column = header
            break

    return best_column, user_id_column


def _setup_processing_config(best_column: str, output_type: str) -> bool:
    """Setup processing configuration and determine if resolution should be skipped.

    Args:
        best_column: The selected column name
        output_type: Type of output desired

    Returns:
        bool: True if resolution should be skipped
    """
    skip_resolution = _should_skip_resolution(best_column, output_type)
    if skip_resolution:
        data_type = "username" if output_type == "username" else "email"
        print_info(
            f"CSV column '{best_column}' contains {data_type} data. Skipping encoded username resolution."
        )
    return skip_resolution


def _process_csv_rows(
    reader: csv.DictReader[Any],
    best_column: str,
    user_id_column: str | None,
    output_type: str,
    env: str | None,
    skip_resolution: bool,
) -> list[str | CsvRowData]:
    """Process CSV rows and extract identifiers.

    Args:
        reader: CSV DictReader instance
        best_column: Column to extract data from
        user_id_column: User ID column for fallback (if available)
        output_type: Type of output desired
        env: Environment for Auth0 API resolution
        skip_resolution: Whether to skip encoded username resolution

    Returns:
        List of identifiers or CsvRowData objects
    """
    identifiers = []

    for row in reader:
        if best_column in row:
            identifier = _create_identifier_record(
                row, best_column, user_id_column, output_type, env, skip_resolution
            )
            if identifier:
                identifiers.append(identifier)

    return identifiers


def _create_identifier_record(
    row: dict[str, str],
    best_column: str,
    user_id_column: str | None,
    output_type: str,
    env: str | None,
    skip_resolution: bool,
) -> str | CsvRowData | None:
    """Create an identifier record from a CSV row.

    Args:
        row: CSV row data
        best_column: Column to extract data from
        user_id_column: User ID column for fallback (if available)
        output_type: Type of output desired
        env: Environment for Auth0 API resolution
        skip_resolution: Whether to skip encoded username resolution

    Returns:
        Identifier string, CsvRowData object, or None if empty
    """
    # Preserve encoded usernames if we're looking for username output and found username column
    preserve_encoded = skip_resolution and output_type == "username"
    env_for_cleaning = None if skip_resolution else env
    cleaned = clean_identifier(row[best_column], env_for_cleaning, preserve_encoded)

    if not cleaned:
        return None

    # If we have Auth0 API env and user_id column, store row data for enhanced processing
    if env and user_id_column and user_id_column in row:
        user_id = row[user_id_column].strip() if row[user_id_column] else None
        return CsvRowData(identifier=cleaned, user_id=user_id, row_data=dict(row))
    else:
        return cleaned


def _should_skip_resolution(best_column: str, output_type: str) -> bool:
    """Determine if we should skip encoded username resolution.

    Args:
        best_column: The selected column name
        output_type: Type of output desired

    Returns:
        True if resolution should be skipped
    """
    if output_type == "username" and best_column and "user_name" in best_column.lower():
        return True
    elif output_type == "email" and best_column and "email" in best_column.lower():
        return True

    return False


def _check_if_data_available(
    identifiers: list[str | CsvRowData], output_type: str
) -> bool:
    """Check if the identifiers already contain the requested data type.

    Args:
        identifiers: List of identifiers from CSV or CsvRowData
        output_type: Requested output type (username|email|user_id)

    Returns:
        True if data is already in the correct format
    """
    if not identifiers:
        return False

    # Sample the first few identifiers to determine type
    sample_size = min(5, len(identifiers))
    sample = identifiers[:sample_size]

    # Extract actual identifiers from CsvRowData if needed
    sample_identifiers = [
        item.identifier if isinstance(item, CsvRowData) else item for item in sample
    ]

    if output_type == "email":
        # Check if most samples are email addresses
        email_count = sum(
            1
            for item in sample_identifiers
            if "@" in item and not item.startswith(AUTH0_USER_ID_PREFIXES)
        )
        return email_count >= len(sample_identifiers) * 0.8  # 80% threshold
    elif output_type == "user_id":
        # Check if most samples are Auth0 user IDs
        user_id_count = sum(
            1 for item in sample_identifiers if item.startswith(AUTH0_USER_ID_PREFIXES)
        )
        return user_id_count >= len(sample_identifiers) * 0.8
    elif output_type == "username":
        # Check if samples look like usernames (not emails, not user_ids)
        username_count = sum(
            1
            for item in sample_identifiers
            if "@" not in item and not item.startswith(AUTH0_USER_ID_PREFIXES)
        )
        return username_count >= len(sample_identifiers) * 0.8

    return False


def extract_identifiers_from_csv(
    filename: str = "ids.csv",
    env: str | None = None,
    output_type: str = "user_id",
    interactive: bool = True,
) -> list[str]:
    """Extract user identifiers from CSV with fuzzy column matching.

    Args:
        filename: Input CSV file path
        env: Environment for Auth0 API resolution (dev/prod) - optional but recommended for encoded usernames
        output_type: Type of output desired (username|email|user_id)
        interactive: Whether to prompt user for input (default True, set False for testing)

    Returns:
        List of cleaned identifiers
    """
    try:
        with safe_file_read(filename) as infile:
            # Detect file type and process accordingly
            identifiers, skip_resolution = _detect_and_process_file(
                infile, output_type, env
            )

            # Handle post-processing (conversion, extraction)
            return _handle_post_processing(
                identifiers, skip_resolution, output_type, env, interactive
            )

    except FileOperationError as e:
        print_error(f"Error reading file {filename}: {e}")
        return []
    except csv.Error as e:
        print_error(f"CSV parsing error in {filename}: {e}")
        return []
    except Exception as e:
        print_error(f"Unexpected error processing file {filename}: {e}")
        return []


def _detect_and_process_file(
    infile: TextIO, output_type: str, env: str | None
) -> tuple[list[str | CsvRowData], bool]:
    """Detect file type and process accordingly.

    Args:
        infile: File object to read from
        output_type: Type of output desired (username|email|user_id)
        env: Environment for Auth0 API resolution

    Returns:
        Tuple of (identifiers/row_data list, skip_resolution flag)
    """
    # Store position and read first line
    start_pos = infile.tell()
    first_line = infile.readline()
    if not first_line:
        return [], False

    # Detect file type
    file_type = _detect_file_type(first_line)

    # Reset file position
    infile.seek(start_pos)

    if file_type == "plain_text":
        plain_identifiers = _process_plain_text(infile, env)
        # Convert to tuple format for consistency
        return cast(list[str | CsvRowData], plain_identifiers), False
    else:
        return _process_csv_file(infile, output_type, env)


def _handle_post_processing(
    identifiers: list[str | CsvRowData],
    skip_resolution: bool,
    output_type: str,
    env: str | None,
    interactive: bool,
) -> list[str]:
    """Handle post-processing of identifiers including conversion and extraction.

    Args:
        identifiers: List of identifiers or CsvRowData
        skip_resolution: Whether resolution was skipped
        output_type: Type of output desired
        env: Environment for Auth0 API
        interactive: Whether to prompt user for input

    Returns:
        Final list of processed identifiers
    """
    # Handle conversion if needed
    if _needs_conversion(skip_resolution, identifiers, output_type):
        return _handle_conversion(identifiers, output_type, env, interactive)
    elif not skip_resolution and _check_if_data_available(identifiers, output_type):
        print_info(
            f"CSV already contains {output_type} data. No Auth0 API calls needed."
        )

    # Extract just the identifiers from CsvRowData objects for final output
    return _extract_final_identifiers(identifiers)


def _extract_final_identifiers(identifiers: list[str | CsvRowData]) -> list[str]:
    """Extract final identifiers from mixed list of strings and CsvRowData.

    Args:
        identifiers: List of identifiers or CsvRowData objects

    Returns:
        List of string identifiers
    """
    return [
        item.identifier if isinstance(item, CsvRowData) else item
        for item in identifiers
    ]


def _needs_conversion(
    skip_resolution: bool, identifiers: list[str | CsvRowData], output_type: str
) -> bool:
    """Check if identifiers need conversion to the requested output type.

    Args:
        skip_resolution: Whether resolution was skipped during CSV processing
        identifiers: List of identifiers
        output_type: Requested output type

    Returns:
        True if conversion is needed
    """
    if skip_resolution:
        return False

    data_already_available = _check_if_data_available(identifiers, output_type)
    return not data_already_available


def _handle_conversion(
    identifiers: list[str | CsvRowData],
    output_type: str,
    env: str | None = None,
    interactive: bool = True,
) -> list[str]:
    """Handle conversion of identifiers to requested output type.

    Args:
        identifiers: List of identifiers or CsvRowData to convert
        output_type: Requested output type
        env: Environment for Auth0 API
        interactive: Whether to prompt user for input

    Returns:
        Converted identifiers list
    """
    if env:
        return _convert_to_output_type(identifiers, output_type, env)
    elif interactive:
        print_warning(
            f"Requested output type '{output_type}' but no environment specified."
        )
        response = (
            input(
                "Do you want to fetch this data from Auth0? Specify environment (dev/prod) or press Enter to skip: "
            )
            .strip()
            .lower()
        )
        if response in ["dev", "prod"]:
            return _convert_to_output_type(identifiers, output_type, response)
        else:
            print_info("Skipping Auth0 data fetch. Using original identifiers.")
    # Non-interactive mode or user declined - return original identifiers
    return [
        item.identifier if isinstance(item, CsvRowData) else item
        for item in identifiers
    ]


def write_identifiers_to_file(
    identifiers: list[str], filename: str = "ids.csv"
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
        print_error(f"Error writing to file {filename}: {e}")
        return False
    except Exception as e:
        print_error(f"Unexpected error writing to file {filename}: {e}")
        return False


def _search_user_by_field(
    identifier: str, token: str, base_url: str
) -> dict[str, Any] | None:
    """Search for a user in Auth0 by identifier.

    Args:
        identifier: User identifier (email, username, user_id)
        token: Auth0 access token
        base_url: Auth0 API base URL

    Returns:
        User details dictionary or None if not found
    """
    if is_auth0_user_id(identifier):
        # Direct user ID lookup
        return get_user_details(identifier, token, base_url)
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
                return cast(dict[str, Any], users[0])
        except ValueError:
            return None

        return None


def _extract_output_value(
    user_details: dict[str, Any], output_type: str, fallback: str
) -> str:
    """Extract the requested value from user details.

    Args:
        user_details: User details from Auth0 API
        output_type: Requested output type (email|username|user_id)
        fallback: Fallback value if extraction fails

    Returns:
        Extracted value or fallback
    """
    if output_type == "email":
        email = user_details.get("email")
        return (
            cast(str, email)
            if email is not None and isinstance(email, str)
            else fallback
        )
    elif output_type == "username":
        username = user_details.get("username")
        if username is not None and isinstance(username, str):
            return cast(str, username)
        # Fallback to email if username is not available or not a string
        email = user_details.get("email")
        return (
            cast(str, email)
            if email is not None and isinstance(email, str)
            else fallback
        )
    elif output_type == "user_id":
        user_id = user_details.get("user_id")
        return (
            cast(str, user_id)
            if user_id is not None and isinstance(user_id, str)
            else fallback
        )
    else:
        return fallback


def _extract_identifier_data(item: str | CsvRowData) -> tuple[str, str | None]:
    """Extract identifier and fallback user_id from item.

    Args:
        item: Identifier string or CsvRowData with fallback user_id

    Returns:
        Tuple of (identifier, fallback_user_id)
    """
    if isinstance(item, CsvRowData):
        return item.identifier, item.user_id
    else:
        return item, None


def _get_user_details_with_fallback(
    identifier: str, fallback_user_id: str | None, token: str, base_url: str, env: str
) -> dict[str, Any] | None:
    """Get user details with fallback strategy.

    Args:
        identifier: Original identifier
        fallback_user_id: Fallback user ID to try if primary lookup fails
        token: Auth0 access token
        base_url: Auth0 API base URL
        env: Environment for Auth0 API

    Returns:
        User details dict or None if not found
    """
    # Check if identifier is an encoded username (before cleaning)
    is_encoded_username = "_at_" in identifier or "__" in identifier

    # Clean the identifier
    cleaned_identifier = clean_identifier(identifier, env)

    # Try primary lookup
    user_details = None
    if is_auth0_user_id(cleaned_identifier):
        user_details = get_user_details(cleaned_identifier, token, base_url)
    else:
        # For encoded usernames, search by the original encoded value as username
        search_value = identifier if is_encoded_username else cleaned_identifier
        user_details = _search_user_by_field(search_value, token, base_url)

    # Try fallback if primary lookup failed
    if not user_details and fallback_user_id and is_auth0_user_id(fallback_user_id):
        print_info(
            f"Primary lookup failed for '{identifier}', trying fallback user_id: {fallback_user_id}"
        )
        user_details = get_user_details(fallback_user_id, token, base_url)

    return user_details


def _handle_conversion_result(
    user_details: dict[str, Any] | None,
    output_type: str,
    identifier: str,
    item: str | CsvRowData,
) -> str:
    """Handle conversion result extraction.

    Args:
        user_details: User details from Auth0 API or None
        output_type: Requested output type
        identifier: Original identifier
        item: Original item for fallback

    Returns:
        Converted identifier or original if conversion fails
    """
    if user_details:
        return _extract_output_value(user_details, output_type, identifier)
    else:
        return identifier


def _convert_single_identifier(
    item: str | CsvRowData,
    idx: int,
    output_type: str,
    env: str,
    token: str,
    base_url: str,
) -> str:
    """Convert a single identifier to the requested output type with fallback support.

    Args:
        item: Identifier string or CsvRowData with fallback user_id
        idx: Current index (1-based)
        output_type: Requested output type
        env: Environment for Auth0 API
        token: Auth0 access token
        base_url: Auth0 API base URL

    Returns:
        Converted identifier or original if conversion fails
    """
    try:
        identifier, fallback_user_id = _extract_identifier_data(item)

        user_details = _get_user_details_with_fallback(
            identifier, fallback_user_id, token, base_url, env
        )

        return _handle_conversion_result(user_details, output_type, identifier, item)

    except Exception as e:
        print_warning(f"Error converting identifier {identifier}: {e}")
        return identifier if isinstance(item, str) else item.identifier


def _convert_to_output_type(
    identifiers: list[str | CsvRowData], output_type: str, env: str
) -> list[str]:
    """Convert identifiers to the requested output type using Auth0 API.

    Args:
        identifiers: List of user identifiers (emails, user_ids, etc.) or CsvRowData with fallback
        output_type: Desired output type (username|email|user_id)
        env: Environment for Auth0 API calls

    Returns:
        List of converted identifiers
    """
    print_info(f"Fetching {output_type} data from Auth0 API...")

    # Get Auth0 credentials
    try:
        token = get_access_token(env)
        base_url = get_base_url(env)
    except Exception as e:
        print_error(f"Error getting Auth0 credentials: {e}")
        return [
            item.identifier if isinstance(item, CsvRowData) else item
            for item in identifiers
        ]

    # Process each identifier
    converted = []

    for idx, item in enumerate(identifiers, 1):
        converted_identifier = _convert_single_identifier(
            item, idx, output_type, env, token, base_url
        )
        converted.append(converted_identifier)

    return converted
