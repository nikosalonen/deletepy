"""CSV-specific CLI commands for Auth0 user management."""

import sys

from ..utils.csv_utils import (
    extract_identifiers_from_csv,
    write_identifiers_to_file,
)
from ..utils.display_utils import (
    print_error,
    print_info,
    print_success,
    print_warning,
)


def parse_csv_arguments() -> tuple[str | None, str | None, str]:
    """Parse command line arguments for CSV operations.

    Returns:
        Tuple of (filename, env, output_type) or (None, None, None) for help
    """
    # Check for help flag
    if len(sys.argv) > 1 and sys.argv[1] in ["--help", "-h", "help"]:
        print_csv_usage()
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
                print_error(
                    f"Invalid output type '{output_type}'. Must be username, email, or user_id"
                )
                return None, None, None
        elif arg in ["dev", "prod"]:
            env = arg
        elif not arg.startswith("--"):
            filename = arg

    return filename, env, output_type


def print_csv_usage():
    """Print detailed usage information for CSV operations."""
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


def process_csv_file(
    filename: str,
    env: str | None = None,
    output_type: str = "user_id",
    interactive: bool = True,
) -> bool:
    """Process a CSV file and extract/convert user identifiers.

    Args:
        filename: Input CSV file path
        env: Environment for Auth0 API resolution (dev/prod)
        output_type: Type of output desired (username|email|user_id)
        interactive: Whether to prompt user for input

    Returns:
        True if successful, False otherwise
    """
    print_info(f"Processing file: {filename}")

    if env:
        print_info(f"Using environment: {env}")

    if output_type != "user_id":
        print_info(f"Output type: {output_type}")

    # Extract identifiers from CSV
    identifiers = extract_identifiers_from_csv(
        filename=filename,
        env=env,
        output_type=output_type,
        interactive=interactive,
    )

    if not identifiers:
        print_warning("No identifiers found in file")
        return False

    # Write processed identifiers back to file
    success = write_identifiers_to_file(identifiers, filename)

    if success:
        print_success(f"Processed {len(identifiers)} identifiers")
        if env:
            print_info(f"Used {env} environment for Auth0 API resolution")
        if output_type != "user_id":
            print_info(f"Output type: {output_type}")
        return True
    else:
        print_error("Failed to write output file")
        return False


def main():
    """Main entry point for CSV processing CLI."""
    filename, env, output_type = parse_csv_arguments()

    if filename is None:
        sys.exit(1)

    success = process_csv_file(filename, env, output_type)

    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
