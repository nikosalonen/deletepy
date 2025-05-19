import sys
import requests
from config import check_env_file, get_base_url
from auth import get_access_token, AuthConfigError
from utils import validate_args, read_user_ids_generator, CYAN, RESET, show_progress
from user_operations import (
    delete_user,
    block_user,
    revoke_user_grants,
    check_unblocked_users,
    get_user_email,
    revoke_user_sessions,
    get_user_id_from_email,
    get_user_details
)
from email_domain_checker import check_domains_status_for_emails

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
            print("\nFetching user emails...")
            emails = []
            for idx, user_id in enumerate(user_ids, 1):
                show_progress(idx, total_users, "Fetching emails")
                email = get_user_email(user_id, token, base_url)
                if email:
                    emails.append(email)
            print("\n")  # Clear progress line

            if not emails:
                print("No valid emails found to check.")
                sys.exit(0)

            print(f"\nChecking {len(emails)} email domains...")
            results = check_domains_status_for_emails(emails)

            # Print summary
            blocked = [email for email, status in results.items() if "BLOCKED" in status]
            unresolvable = [email for email, status in results.items() if "UNRESOLVABLE" in status]
            allowed = [email for email, status in results.items() if "ALLOWED" in status]
            ignored = [email for email, status in results.items() if "IGNORED" in status]
            invalid = [email for email, status in results.items() if "INVALID" in status]
            error = [email for email, status in results.items() if "ERROR" in status]

            print("\nDomain Check Summary:")
            print(f"Total emails checked: {len(emails)}")
            if blocked:
                print(f"\nBlocked domains ({len(blocked)}):")
                for email in blocked:
                    print(f"  {email}")
            if unresolvable:
                print(f"\nUnresolvable domains ({len(unresolvable)}):")
                for email in unresolvable:
                    print(f"  {email}")
            if allowed:
                print(f"\nAllowed domains ({len(allowed)}):")
                for email in allowed:
                    print(f"  {email}")
            if ignored:
                print(f"\nIgnored domains ({len(ignored)}):")
                for email in ignored:
                    print(f"  {email}")
            if invalid:
                print(f"\nInvalid emails ({len(invalid)}):")
                for email in invalid:
                    print(f"  {email}")
            if error:
                print(f"\nErrors checking domains ({len(error)}):")
                for email in error:
                    print(f"  {email}")
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
            multiple_users = {}  # Store emails with multiple users
            not_found_users = []  # Store emails that weren't found
            processed_count = 0
            skipped_count = 0

            for idx, user_id in enumerate(user_ids, 1):
                show_progress(idx, total_users, operation_display)
                # Trim whitespace
                user_id = user_id.strip()
                # If input is an email, resolve to user_id
                if "@" in user_id:
                    resolved_ids = get_user_id_from_email(user_id, token, base_url)
                    if not resolved_ids:
                        not_found_users.append(user_id)
                        skipped_count += 1
                        continue

                    if len(resolved_ids) > 1:
                        multiple_users[user_id] = resolved_ids
                        skipped_count += 1
                        continue

                    user_id = resolved_ids[0]

                if operation == "block":
                    block_user(user_id, token, base_url)
                elif operation == "delete":
                    delete_user(user_id, token, base_url)
                elif operation == "revoke-grants-only":
                    # First revoke sessions, then grants
                    revoke_user_sessions(user_id, token, base_url)
                    revoke_user_grants(user_id, token, base_url)
                processed_count += 1

            print("\n")  # Clear progress line

            # Print summary
            print("\nOperation Summary:")
            print(f"Total users processed: {processed_count}")
            print(f"Total users skipped: {skipped_count}")

            if not_found_users:
                print(f"\nNot found users ({len(not_found_users)}):")
                for email in not_found_users:
                    print(f"  {CYAN}{email}{RESET}")

            if multiple_users:
                print(f"\nFound {len(multiple_users)} emails with multiple users:")
                for email, user_ids in multiple_users.items():
                    print(f"\n  {CYAN}{email}{RESET}:")
                    for uid in user_ids:
                        user_details = get_user_details(uid, token, base_url)
                        if user_details and "identities" in user_details and len(user_details["identities"]) > 0:
                            connection = user_details["identities"][0].get("connection", "unknown")
                            print(f"    - {uid} (Connection: {connection})")
                        else:
                            print(f"    - {uid} (Connection: unknown)")

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
