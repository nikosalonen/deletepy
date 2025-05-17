import sys
import requests
from config import check_env_file, get_base_url
from auth import get_access_token, AuthConfigError
from utils import validate_args, read_user_ids_generator
from user_operations import (
    delete_user,
    block_user,
    revoke_user_grants,
    check_unblocked_users,
    get_user_email,
    revoke_user_sessions
)
from email_domain_checker import check_domains_for_emails

def show_progress(current: int, total: int, operation: str) -> None:
    """Show progress indicator for bulk operations.

    Args:
        current: Current item number
        total: Total number of items
        operation: Operation being performed
    """
    spinner = ['|', '/', '-', '\\']
    spin_idx = (current - 1) % len(spinner)
    sys.stdout.write(f"\r{operation}... {spinner[spin_idx]} ({current}/{total})")
    sys.stdout.flush()

def confirm_production_operation(operation: str, total_users: int) -> bool:
    """Confirm operation in production environment.

    Args:
        operation: The operation to be performed
        total_users: Total number of users to be processed

    Returns:
        bool: True if confirmed, False otherwise
    """
    operation_details = {
        "block": {
            "action": "blocking",
            "consequence": "This will prevent users from logging in and revoke all their active sessions and application grants."
        },
        "delete": {
            "action": "deleting",
            "consequence": "This will permanently remove users from Auth0, including all their data, sessions, and application grants."
        },
        "revoke-grants-only": {
            "action": "revoking grants for",
            "consequence": "This will invalidate all refresh tokens and prevent applications from obtaining new access tokens for these users."
        }
    }.get(operation, {
        "action": "processing",
        "consequence": "This operation will affect user data in the production environment."
    })

    print(f"\nYou are about to perform {operation_details['action']} {total_users} users in PRODUCTION environment.")
    print(f"Consequence: {operation_details['consequence']}")
    print("This action cannot be undone.")
    response = input("Are you sure you want to proceed? (yes/no): ").lower().strip()
    return response == "yes"

def main():
    """Main entry point for the application."""
    try:
        # Validate arguments
        args = validate_args()
        input_file = args.input_file
        env = args.env
        operation = args.operation

        # Check environment configuration
        check_env_file()
        base_url = get_base_url(env)
        token = get_access_token(env)

        # Read user IDs from file
        user_ids = list(read_user_ids_generator(input_file))
        total_users = len(user_ids)

        if operation == "check-unblocked":
            check_unblocked_users(user_ids, token, base_url)
        elif operation == "check-domains":
            emails = [get_user_email(user_id, token, base_url) for user_id in user_ids]
            check_domains_for_emails(emails)
        else:
            # Process users one by one for other operations
            operation_display = {
                "block": "Blocking users",
                "delete": "Deleting users",
                "revoke-grants-only": "Revoking grants and sessions"
            }.get(operation, "Processing users")

            # Request confirmation for production environment
            if env == "prod" and not confirm_production_operation(operation, total_users):
                print("Operation cancelled by user.")
                sys.exit(0)

            print(f"\n{operation_display}...")
            for idx, user_id in enumerate(user_ids, 1):
                show_progress(idx, total_users, operation_display)
                if operation == "block":
                    block_user(user_id, token, base_url)
                elif operation == "delete":
                    delete_user(user_id, token, base_url)
                elif operation == "revoke-grants-only":
                    # First revoke sessions, then grants
                    revoke_user_sessions(user_id, token, base_url)
                    revoke_user_grants(user_id, token, base_url)
            print("\n")  # Clear progress line

    except FileNotFoundError as e:
        print(f"Error: {str(e)}")
        sys.exit(1)
    except IOError as e:
        print(f"Error reading file: {str(e)}")
        sys.exit(1)
    except AuthConfigError as e:
        print(f"Authentication configuration error: {str(e)}")
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        print(f"API request error: {str(e)}")
        sys.exit(1)
    except ValueError as e:
        print(f"Configuration error: {str(e)}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
