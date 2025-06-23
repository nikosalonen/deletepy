#!/usr/bin/env python3
"""
Test script to demonstrate multiple user handling functionality.

This script creates a test file with emails that might have multiple users
and shows how the export functionality handles them.
"""

import os

def create_test_emails_file():
    """Create a test file with emails that might have multiple users."""
    test_emails = [
        "admin@company.com",  # Likely to have multiple users (Google + Auth0)
        "user@example.com",   # Single user
        "test@domain.org",    # Single user
        "support@company.com", # Might have multiple users
        "developer@startup.io" # Single user
    ]

    filename = "test_multiple_users.txt"
    with open(filename, 'w') as f:
        for email in test_emails:
            f.write(f"{email}\n")

    print(f"Created test emails file: {filename}")
    print("Test emails:")
    for email in test_emails:
        print(f"  - {email}")
    return filename

def main():
    """Main function to demonstrate multiple user handling."""
    print("Multiple Users Test")
    print("=" * 40)

    # Check if main.py exists
    if not os.path.exists("main.py"):
        print("Error: main.py not found. Please run this script from the project root directory.")
        return

    # Create test emails file
    emails_file = create_test_emails_file()

    print("\nTo test multiple user handling:")
    print(f"1. Run: python main.py {emails_file} dev --export-last-login")
    print("2. Check the generated CSV file")
    print("3. Look for emails with multiple users - they will have multiple rows")
    print("4. Each row will show the connection type (google-oauth2, auth0, etc.)")

    print("\nExpected behavior:")
    print("- Emails with single users: One row per email")
    print("- Emails with multiple users: Multiple rows per email, each with different connection")
    print("- Connection column will show: google-oauth2, auth0, facebook, etc.")
    print("- Status will show: MULTIPLE_USERS (N) for emails with multiple accounts")

if __name__ == "__main__":
    main()
