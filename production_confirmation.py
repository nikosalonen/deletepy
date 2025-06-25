"""Production operation confirmation utilities.

This module provides functionality for confirming potentially destructive operations
in production environments with appropriate warnings and user confirmations.
"""


def confirm_production_operation(operation: str, total_users: int) -> bool:
    """Confirm operation in production environment.

    Args:
        operation: The operation to be performed
        total_users: Total number of users to be processed

    Returns:
        bool: True if confirmed, False otherwise

    Raises:
        ValueError: If operation is empty or total_users is not positive
        TypeError: If parameters are not of expected types
    """
    if not isinstance(operation, str):
        raise TypeError(f"Operation must be a string, got {type(operation).__name__}")

    if not isinstance(total_users, int):
        raise TypeError(
            f"Total users must be an integer, got {type(total_users).__name__}"
        )

    if not operation or not operation.strip():
        raise ValueError("Operation cannot be empty or whitespace")

    if total_users <= 0:
        raise ValueError(f"Total users must be a positive integer, got {total_users}")
    operation_details = {
        "block": {
            "action": "blocking",
            "consequence": "This will prevent users from logging in and revoke all their active sessions and application grants.",
        },
        "delete": {
            "action": "deleting",
            "consequence": "This will permanently remove users from Auth0, including all their data, sessions, and application grants.",
        },
        "revoke-grants-only": {
            "action": "revoking grants for",
            "consequence": "This will invalidate all refresh tokens and prevent applications from obtaining new access tokens for these users.",
        },
    }.get(
        operation,
        {
            "action": "processing",
            "consequence": "This operation will affect user data in the production environment.",
        },
    )

    print(
        f"\nYou are about to perform {operation_details['action']} {total_users} users in PRODUCTION environment."
    )
    print(f"Consequence: {operation_details['consequence']}")
    print("This action cannot be undone.")
    response = input("Are you sure you want to proceed? (yes/no): ").lower().strip()
    return response == "yes"
