#!/usr/bin/env python3
"""
Test script to demonstrate connection filtering functionality.

This script shows how to use the --connection parameter to filter users
and prevent multiple users from occurring.
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

    filename = "test_connection_filter.txt"
    with open(filename, 'w') as f:
        for email in test_emails:
            f.write(f"{email}\n")

    print(f"Created test emails file: {filename}")
    print("Test emails:")
    for email in test_emails:
        print(f"  - {email}")
    return filename

def main():
    """Main function to demonstrate connection filtering."""
    print("Connection Filtering Test")
    print("=" * 40)

    # Check if main.py exists
    if not os.path.exists("main.py"):
        print("Error: main.py not found. Please run this script from the project root directory.")
        return

    # Create test emails file
    emails_file = create_test_emails_file()

    print("\nTo test connection filtering:")
    print("1. Export all users (may have multiple per email):")
    print(f"   python main.py {emails_file} dev --export-last-login")
    print("\n2. Export only Google OAuth users:")
    print(f"   python main.py {emails_file} dev --export-last-login --connection google-oauth2")
    print("\n3. Export only Auth0 database users:")
    print(f"   python main.py {emails_file} dev --export-last-login --connection auth0")
    print("\n4. Export only Facebook users:")
    print(f"   python main.py {emails_file} dev --export-last-login --connection facebook")

    print("\nExpected behavior:")
    print("- Without --connection: May have multiple rows per email")
    print("- With --connection: Should have only one row per email")
    print("- Connection column will show the filtered connection type")
    print("- Status will show SUCCESS for filtered results")

if __name__ == "__main__":
    main()
