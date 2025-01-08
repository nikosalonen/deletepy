import requests
import sys
import time
from typing import List, Tuple
import os
from dotenv import load_dotenv
from pathlib import Path

def check_env_file():
    """Check if .env file exists"""
    if not Path('.env').is_file():
        sys.exit("Error: .env file not found. Please create a .env file with your credentials.")

def get_access_token(env: str = "dev") -> str:
    """Get access token from Auth0 using client credentials."""
    load_dotenv()

    # Map environment to config values
    env_config = {
        "prod": {
            "client_id": "CLIENT_ID",
            "client_secret": "CLIENT_SECRET",
            "auth0_domain": os.getenv("AUTH0_DOMAIN"),
            "api_url": os.getenv("URL")
        },
        "dev": {
            "client_id": "DEVELOPMENT_CLIENT_ID",
            "client_secret": "DEVELOPMENT_CLIENT_SECRET",
            "auth0_domain": os.getenv("DEV_AUTH0_DOMAIN"),
            "api_url": os.getenv("DEV_URL")
        }
    }

    if env not in env_config:
        raise ValueError("Environment must be either 'dev' or 'prod'")

    config = env_config[env]
    client_id = os.getenv(config["client_id"])
    client_secret = os.getenv(config["client_secret"])
    domain = config["auth0_domain"]

    url = f"https://{domain}/oauth/token"
    payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "audience": f"https://{domain}/api/v2/",
        "grant_type": "client_credentials"
    }
    response = requests.post(url, json=payload)
    response.raise_for_status()
    return response.json()["access_token"]

def validate_args() -> Tuple[str, str]:
    """Validate command line arguments and return input file path and environment."""
    if len(sys.argv) < 2:
        sys.exit("Usage: python delete.py <ids_file> [env]")
    input_file = sys.argv[1]
    env = sys.argv[2] if len(sys.argv) > 2 else "dev"
    return input_file, env

def read_user_ids(filepath: str) -> List[str]:
    """Read user IDs from file."""
    try:
        with open(filepath, 'r') as f:
            return [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        sys.exit(f"Error: File {filepath} not found")
    except IOError as e:
        sys.exit(f"Error reading file: {e}")

def get_base_url(env: str = "dev") -> str:
    """Get base URL based on environment."""
    env_config = {
        "prod": {
            "auth0_domain": os.getenv("AUTH0_DOMAIN")
        },
        "dev": {
            "auth0_domain": os.getenv("DEV_AUTH0_DOMAIN")
        }
    }

    if env not in env_config:
        raise ValueError("Environment must be either 'dev' or 'prod'")

    return f"https://{env_config[env]['auth0_domain']}"

def delete_user(user_id: str, token: str, base_url: str) -> None:
    """Delete user from Auth0."""
    print(f"Deleting user: {user_id}")
    url = f"{base_url}/api/v2/users/{user_id}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    try:
        response = requests.delete(url, headers=headers)
        response.raise_for_status()
        print(f"Successfully deleted user {user_id}")
    except requests.exceptions.RequestException as e:
        print(f"Error deleting user {user_id}: {e}")

def main():
    try:
        check_env_file()
        input_file, env = validate_args()

        # Add warning for production environment
        if env == "prod":
            confirmation = input("\n⚠️  WARNING: You are about to delete users in PRODUCTION environment!\nAre you sure you want to continue? (yes/no): ")
            if confirmation.lower() != "yes":
                sys.exit("Operation cancelled by user.")
            print("\nProceeding with production deletion...\n")

        token = get_access_token(env)
        user_ids = read_user_ids(input_file)
        base_url = get_base_url(env)

        for user_id in user_ids:
            delete_user(user_id, token, base_url)
            time.sleep(0.5)
    except Exception as e:
        sys.exit(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    main()
