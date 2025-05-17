import sys
import requests
from config import check_env_file, get_base_url
from auth import get_access_token, AuthConfigError
from utils import validate_args, read_user_ids
from user_operations import (
    delete_user,
    block_user,
    revoke_user_grants,
    check_unblocked_users,
    get_user_email
)
from email_domain_checker import check_domains_for_emails

def main():
    """Main entry point for the application."""
    try:
        # Check for .env file
        check_env_file()
        
        # Validate command line arguments
        input_file, env, block, delete, revoke_grants_only, check_unblocked, check_domains = validate_args()
        
        # Get access token and base URL
        token = get_access_token(env)
        base_url = get_base_url(env)
        
        # Read user IDs from file
        user_ids = read_user_ids(input_file)
        
        # Process users based on operation flags
        if check_unblocked:
            # Process all users at once for unblocked check
            check_unblocked_users(user_ids, token, base_url)
        elif check_domains:
            # Collect emails for all users
            emails = []
            for user_id in user_ids:
                email = get_user_email(user_id, token, base_url)
                if email:
                    emails.append(email)
            
            if emails:
                print(f"\nChecking domains for {len(emails)} users...\n")
                check_domains_for_emails(emails)
            else:
                print("No valid email addresses found for the provided user IDs.")
        else:
            # Process users one by one for other operations
            for user_id in user_ids:
                if block:
                    block_user(user_id, token, base_url)
                elif delete:
                    delete_user(user_id, token, base_url)
                elif revoke_grants_only:
                    revoke_user_grants(user_id, token, base_url)

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