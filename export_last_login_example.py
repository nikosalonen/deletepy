#!/usr/bin/env python3
"""
Example script demonstrating how to use the export-last-login functionality.

This script shows how to:
1. Create a file with email addresses
2. Run the export command
3. View the results

Usage:
    python export_last_login_example.py
"""

import os
import subprocess
import sys


def create_sample_emails_file():
    """Create a sample file with email addresses for testing."""
    sample_emails = [
        "user1@example.com",
        "user2@example.com",
        "user3@example.com",
        "admin@company.com",
        "test@domain.org",
    ]

    filename = "sample_emails.txt"
    with open(filename, "w") as f:
        for email in sample_emails:
            f.write(f"{email}\n")

    print(f"Created sample emails file: {filename}")
    return filename


def run_export_command(emails_file, env="dev"):
    """Run the export-last-login command."""
    print(f"\nRunning export command for environment: {env}")
    print(f"Command: python main.py {emails_file} {env} --export-last-login")

    try:
        result = subprocess.run(
            [sys.executable, "main.py", emails_file, env, "--export-last-login"],
            capture_output=True,
            text=True,
            check=True,
        )

        print("Command output:")
        print(result.stdout)

        if result.stderr:
            print("Errors:")
            print(result.stderr)

    except subprocess.CalledProcessError as e:
        print(f"Command failed with exit code {e.returncode}")
        print("Output:")
        print(e.stdout)
        print("Errors:")
        print(e.stderr)


def main():
    """Main function to demonstrate the export functionality."""
    print("Export Last Login Example")
    print("=" * 40)

    # Check if main.py exists
    if not os.path.exists("main.py"):
        print(
            "Error: main.py not found. Please run this script from the project root directory."
        )
        sys.exit(1)

    # Create sample emails file
    emails_file = create_sample_emails_file()

    # Run the export command
    run_export_command(emails_file, "dev")

    # Clean up
    if os.path.exists(emails_file):
        os.remove(emails_file)
        print(f"\nCleaned up: {emails_file}")

    print("\nExample completed!")
    print("\nTo use with your own emails:")
    print("1. Create a text file with one email per line")
    print("2. Run: python main.py your_emails.txt dev --export-last-login")
    print("3. Check the generated CSV file for results")


if __name__ == "__main__":
    main()
