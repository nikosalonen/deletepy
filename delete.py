import requests
import sys
import time
from typing import List

def validate_args() -> tuple[str, str, str]:
    """Validate command line arguments and return token, input file path and environment."""
    if len(sys.argv) < 4:
        sys.exit("Usage: python delete.py <ids_file> <token> <env>")
    return sys.argv[2], sys.argv[1], sys.argv[3]

def read_user_ids(filepath: str) -> List[str]:
    """Read user IDs from file."""
    with open(filepath, 'r') as f:
        return [line.strip() for line in f]

def get_base_url(env: str) -> str:
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
    token, input_file, env = validate_args()
    user_ids = read_user_ids(input_file)
    base_url = get_base_url(env)

    for user_id in user_ids:
        delete_user(user_id, token, base_url)
        time.sleep(1)

if __name__ == "__main__":
    main()
