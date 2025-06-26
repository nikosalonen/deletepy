"""CLI argument parsing and validation utilities."""

import argparse

from ..utils.auth_utils import validate_auth0_user_id


def validate_args() -> argparse.Namespace:
    """Parse and validate command line arguments.

    Returns:
        argparse.Namespace: Parsed arguments containing:
            - input_file: Path to the file containing user IDs (optional for doctor)
            - env: Environment to run in ('dev' or 'prod')
            - operation: The operation to perform (block/delete/revoke-grants-only/check-unblocked/check-domains/doctor)
    """
    parser = argparse.ArgumentParser(
        description="Process user operations based on IDs from a file.",
        usage="python main.py <ids_file> [env] [--block|--delete|--revoke-grants-only|--check-unblocked|--check-domains|--doctor]",
    )

    parser.add_argument(
        "input_file",
        nargs="?",
        help="Path to the file containing user IDs (not required for --doctor)",
    )

    parser.add_argument(
        "env",
        nargs="?",
        choices=["dev", "prod"],
        default="dev",
        help="Environment to run in (default: dev)",
    )

    operation_group = parser.add_mutually_exclusive_group(required=True)
    operation_group.add_argument(
        "--block",
        action="store_const",
        const="block",
        dest="operation",
        help="Block the specified users",
    )
    operation_group.add_argument(
        "--delete",
        action="store_const",
        const="delete",
        dest="operation",
        help="Delete the specified users",
    )
    operation_group.add_argument(
        "--revoke-grants-only",
        action="store_const",
        const="revoke-grants-only",
        dest="operation",
        help="Revoke grants for the specified users",
    )
    operation_group.add_argument(
        "--check-unblocked",
        action="store_const",
        const="check-unblocked",
        dest="operation",
        help="Check if specified users are unblocked",
    )
    operation_group.add_argument(
        "--check-domains",
        action="store_const",
        const="check-domains",
        dest="operation",
        help="Check domains for the specified users",
    )
    operation_group.add_argument(
        "--export-last-login",
        action="store_const",
        const="export-last-login",
        dest="operation",
        help="Export user last_login data to CSV",
    )
    operation_group.add_argument(
        "--doctor",
        action="store_const",
        const="doctor",
        dest="operation",
        help="Test if credentials work",
    )
    operation_group.add_argument(
        "--find-social-ids",
        action="store_const",
        const="find-social-ids",
        dest="operation",
        help="Find users by social media IDs from identities",
    )

    parser.add_argument(
        "--test-api",
        action="store_true",
        help="Test API access when using --doctor (optional)",
    )

    parser.add_argument(
        "--connection",
        type=str,
        help="Filter users by connection type (e.g., 'google-oauth2', 'auth0', 'facebook')",
    )

    args = parser.parse_args()

    # Special handling for doctor command: if first argument is 'dev' or 'prod' and operation is doctor,
    # treat it as the environment instead of input_file
    if args.operation == "doctor" and args.input_file in ["dev", "prod"]:
        args.env = args.input_file
        args.input_file = None

    # Validate that input_file is provided for all operations except doctor
    if args.operation != "doctor" and not args.input_file:
        parser.error(f"input_file is required for operation '{args.operation}'")

    return args


def validate_environment(env: str) -> str:
    """Validate environment argument.

    Args:
        env: Environment string to validate

    Returns:
        Validated environment string

    Raises:
        ValueError: If environment is not valid
    """
    valid_environments = ["dev", "prod"]
    if env not in valid_environments:
        raise ValueError(f"Environment must be one of: {', '.join(valid_environments)}")
    return env


def validate_operation(operation: str) -> str:
    """Validate operation argument.

    Args:
        operation: Operation string to validate

    Returns:
        Validated operation string

    Raises:
        ValueError: If operation is not valid
    """
    valid_operations = [
        "block",
        "delete",
        "revoke-grants-only",
        "check-unblocked",
        "check-domains",
        "export-last-login",
        "doctor",
        "find-social-ids",
    ]
    if operation not in valid_operations:
        raise ValueError(f"Operation must be one of: {', '.join(valid_operations)}")
    return operation


def validate_connection_type(connection: str | None) -> str | None:
    """Validate connection type argument.

    Args:
        connection: Connection type string to validate

    Returns:
        Validated connection type string or None

    Raises:
        ValueError: If connection type is not valid
    """
    if connection is None:
        return None

    valid_connections = [
        "auth0",
        "google-oauth2",
        "facebook",
        "github",
        "twitter",
        "linkedin",
        "apple",
        "microsoft",
        "windowslive",
        "line",
        "samlp",
        "oidc",
    ]
    if connection not in valid_connections:
        raise ValueError(f"Connection must be one of: {', '.join(valid_connections)}")
    return connection


def validate_user_id_list(user_ids: list[str]) -> list[str]:
    """Validate a list of user IDs.

    Args:
        user_ids: List of user IDs to validate

    Returns:
        List of valid user IDs

    Raises:
        ValueError: If any user ID is invalid
    """
    invalid_ids = []
    for user_id in user_ids:
        if not validate_auth0_user_id(user_id):
            invalid_ids.append(user_id)

    if invalid_ids:
        raise ValueError(f"Invalid user IDs found: {', '.join(invalid_ids)}")

    return user_ids


def validate_file_path_argument(file_path: str | None, operation: str) -> str | None:
    """Validate file path argument for specific operation.

    Args:
        file_path: File path to validate
        operation: Operation being performed

    Returns:
        Validated file path or None

    Raises:
        ValueError: If file path is invalid for the operation
    """
    if operation == "doctor":
        return None

    if not file_path:
        raise ValueError(f"File path is required for operation '{operation}'")

    return file_path
