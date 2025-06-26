import csv
import re
from typing import List, Optional
from auth import get_access_token
from config import get_base_url
from user_operations import get_user_details


def find_best_column(headers: List[str]) -> Optional[str]:
    """Find the most likely column containing user identifiers, defaulting to user_id."""
    # First check for exact match of user_id (case insensitive)
    for header in headers:
        if header.lower() == "user_id":
            return header

    # Then use fuzzy matching patterns
    patterns = [
        r"detail\.data\.",
        r"user.*id",
        r"user.*name",
        r"username",
        r"userid",
        r"email",
        r"identifier",
        r"subject",
        r"principal",
    ]

    for pattern in patterns:
        for header in headers:
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
    if username.startswith(
        (
            "auth0|",
            "google-oauth2|",
            "facebook|",
            "github|",
            "twitter|",
            "linkedin|",
            "apple|",
        )
    ):
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
                # Try to get user details using the encoded username as user_id
                user_details = get_user_details(username, token, base_url)
                if user_details and user_details.get("email"):
                    return user_details["email"]
        except Exception:
            # If Auth0 API fails, fall back to string replacement
            pass

    # Fallback to string replacement (but warn about potential issues)
    if "_at_" in username:
        return username.replace("_at_", "@")
    elif "__" in username:
        # This is problematic as noted - but we'll do it as fallback
        return username.replace("__", "@")

    return username


def clean_identifier(value: str, env: str = None) -> str:
    """Clean and normalize user identifiers.

    Args:
        value: Raw identifier value
        env: Environment to use for Auth0 API resolution (optional)

    Returns:
        Cleaned identifier
    """
    if not value or value.strip() == "":
        return ""

    value = value.strip()

    # Handle encoded usernames with Auth0 API resolution
    if "_at_" in value or "__" in value:
        return resolve_encoded_username(value, env)

    return value


def extract_identifiers_from_csv(
    filename: str = "ids.csv", env: str = None
) -> List[str]:
    """Extract user identifiers from CSV with fuzzy column matching.

    Args:
        filename: Input CSV file path
        env: Environment for Auth0 API resolution (dev/prod) - optional but recommended for encoded usernames

    Returns:
        List of cleaned identifiers
    """
    identifiers = []

    with open(filename, newline="") as infile:
        # Check if file has CSV headers by peeking at first line
        first_line = infile.readline()
        infile.seek(0)

        # If first line looks like an Auth0 ID or email, treat as plain text file
        if (
            first_line.strip().startswith(
                ("auth0|", "google-oauth2|", "facebook|", "github|")
            )
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

        best_column = find_best_column(headers)

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

        for row in reader:
            if best_column in row:
                cleaned = clean_identifier(row[best_column], env)
                if cleaned:
                    identifiers.append(cleaned)

    return identifiers


def write_identifiers_to_file(identifiers: List[str], filename: str = "ids.csv"):
    """Write cleaned identifiers to output file."""
    with open(filename, "w", newline="") as outfile:
        for identifier in identifiers:
            outfile.write(f"{identifier}\n")


if __name__ == "__main__":
    import sys

    # Check if environment is provided as argument
    env = None
    if len(sys.argv) > 1:
        env = sys.argv[1]
        if env not in ["dev", "prod"]:
            print("Usage: python cleanup_csv.py [dev|prod]")
            print(
                "Environment parameter is optional but recommended for encoded username resolution"
            )
            env = None

    identifiers = extract_identifiers_from_csv(env=env)
    if identifiers:
        write_identifiers_to_file(identifiers)
        print(f"Processed {len(identifiers)} identifiers")
        if env:
            print(f"Used {env} environment for Auth0 API resolution")
    else:
        print("No identifiers found")
