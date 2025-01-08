import requests
import sys
import time
from typing import List
import os
from dotenv import load_dotenv

def get_access_token(env: str = "dev") -> str:
    """Get access token from Auth0 using client credentials."""
    load_dotenv()

    if env == "prod":
        client_id = os.getenv("CLIENT_ID")
        client_secret = os.getenv("CLIENT_SECRET")
        domain = "almamedia.eu.auth0.com"
    else:
        client_id = os.getenv("DEVELOPMENT_CLIENT_ID")
        client_secret = os.getenv("DEVELOPMENT_CLIENT_SECRET")
        domain = "almamedia-dev.eu.auth0.com"

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

def validate_args() -> tuple[str, str]:
    """Validate command line arguments and return input file path and environment."""
    if len(sys.argv) < 2:
        sys.exit("Usage: python delete.py <ids_file> [env]")
    input_file = sys.argv[1]
    env = sys.argv[2] if len(sys.argv) > 2 else "dev"
    return input_file, env

def read_user_ids(filepath: str) -> List[str]:
    """Read user IDs from file."""
    with open(filepath, 'r') as f:
        return [line.strip() for line in f]

def get_base_url(env: str = "dev") -> str:
    """Get base URL based on environment."""
    if env == "prod":
        return "https://tunnus.almamedia.fi"
    elif env == "dev":
        return "https://tunnus-dev.almamedia.net"
    else:
        sys.exit("Environment must be either 'dev' or 'prod'")

def delete_user(user_id: str, token: str, base_url: str) -> None:
    """Delete user from Auth0."""
    print(f"Deleting user: {user_id}")
    url = f"{base_url}/api/v2/users/{user_id}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    response = requests.delete(url, headers=headers)
    print(response.text)

def main():
    input_file, env = validate_args()
    token = get_access_token(env)
    user_ids = read_user_ids(input_file)
    base_url = get_base_url(env)

    for user_id in user_ids:
        delete_user(user_id, token, base_url)
        time.sleep(1)

if __name__ == "__main__":
    main()
