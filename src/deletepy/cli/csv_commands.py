"""CSV-specific CLI commands for Auth0 user management."""

import argparse
from typing import Any

from ..utils.csv_utils import (
    extract_identifiers_from_csv,
    sanitize_identifiers,
)


class CSVCommandError(Exception):
    """Exception raised for CSV command argument errors."""

    def __init__(self, error_type: str, details: str | None = None):
        """Initialize CSV command error.

        Args:
            error_type: Type of error (e.g., 'missing_filename', 'invalid_output_type')
            details: Optional additional details about the error
        """
        self.error_type = error_type
        self.details = details
        super().__init__(f"CSV command error: {error_type}")

    def is_missing_filename(self) -> bool:
        """Check if this is a missing filename error."""
        return self.error_type == "missing_filename"

    def is_invalid_output_type(self) -> bool:
        """Check if this is an invalid output type error."""
        return self.error_type == "invalid_output_type"


def parse_csv_args(args: argparse.Namespace) -> tuple[str, str | None, str]:
    """Parse CSV command arguments and return configuration.

    Args:
        args: Parsed command line arguments

    Returns:
        Tuple[str, str | None, str]: (filename, env, output_type)
            - filename: Always a string (never None, raises exception if missing)
            - env: Environment string or None if not specified
            - output_type: Always a valid output type string

    Raises:
        CSVCommandError: If filename is missing or output_type is invalid
    """
    filename = getattr(args, "filename", None)
    env = getattr(args, "env", None)
    output_type = getattr(args, "output_type", "user_id")

    # Handle special case where no filename is provided
    if not filename:
        raise CSVCommandError("missing_filename")

    # Validate output type
    valid_types = ["user_id", "email", "username"]
    if output_type not in valid_types:
        raise CSVCommandError(
            "invalid_output_type",
            f"Invalid output type: {output_type}. Valid types: {', '.join(valid_types)}",
        )

    return filename, env, output_type


def handle_csv_command(args: argparse.Namespace) -> None:
    """Handle CSV processing command.

    Args:
        args: Parsed command line arguments
    """
    try:
        filename, env, output_type = parse_csv_args(args)
    except CSVCommandError as e:
        if e.is_missing_filename():
            print_csv_usage()
        elif e.is_invalid_output_type():
            print(e.details)
        return

    print(f"Processing CSV file: {filename}")
    print(f"Environment: {env or 'dev'}")
    print(f"Output type: {output_type}")

    try:
        identifiers = extract_identifiers_from_csv(
            filename=filename, env=env, output_type=output_type
        )
        print(f"Extracted {len(identifiers)} identifiers")
        sanitized_identifiers = sanitize_identifiers(identifiers)
        for identifier in sanitized_identifiers[:5]:  # Show first 5
            print(f"  {identifier}")
        if len(sanitized_identifiers) > 5:
            print(f"  ... and {len(sanitized_identifiers) - 5} more")
    except Exception as e:
        print(f"Error processing CSV: {e}")


def print_csv_usage() -> None:
    """Print CSV command usage information."""
    print("CSV Command Usage:")
    print("  deletepy csv <filename> --env <env> --output-type <type>")
    print("")
    print("Options:")
    print("  filename      CSV file to process")
    print("  --env         Environment (dev/prod)")
    print("  --output-type Output type (user_id/email/username)")
    print("")
    print("Examples:")
    print("  deletepy csv users.csv --env dev --output-type email")
    print("  deletepy csv ids.csv --env prod --output-type user_id")


def create_csv_parser(
    subparsers: Any,
) -> None:
    """Create CSV subparser for the main argument parser.

    Args:
        subparsers: Subparsers object from argparse
    """
    csv_parser = subparsers.add_parser("csv", help="Process CSV files")
    csv_parser.add_argument("filename", nargs="?", help="CSV file to process")
    csv_parser.add_argument(
        "--env", choices=["dev", "prod"], help="Environment (dev/prod)"
    )
    csv_parser.add_argument(
        "--output-type",
        choices=["user_id", "email", "username"],
        default="user_id",
        help="Output type (default: user_id)",
    )
    csv_parser.set_defaults(func=handle_csv_command)


def main() -> None:
    """Main entry point for CSV commands."""
    parser = argparse.ArgumentParser(description="CSV processing utility")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    create_csv_parser(subparsers)

    args = parser.parse_args()
    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
