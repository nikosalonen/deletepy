import os
import requests
from dotenv import load_dotenv
from config import get_env_config

# API timeout in seconds
API_TIMEOUT = 5

class AuthConfigError(Exception):
    """Exception raised for authentication configuration errors."""
    pass

def get_access_token(env: str = "dev") -> str:
    """Get access token from Auth0 using client credentials.
    
    Args:
        env: Environment to use ('dev' or 'prod')
        
    Returns:
        str: Access token for authentication
        
    Raises:
        AuthConfigError: If required environment variables are missing
        requests.exceptions.RequestException: If the token request fails
    """
    load_dotenv()
    config = get_env_config(env)
    
    client_id = config["client_id"]
    client_secret = config["client_secret"]
    domain = config["auth0_domain"]
    
    # Validate required environment variables
    if not client_id:
        raise AuthConfigError("Missing Auth0 Client ID. Please set the AUTH0_CLIENT_ID environment variable.")
    if not client_secret:
        raise AuthConfigError("Missing Auth0 Client Secret. Please set the AUTH0_CLIENT_SECRET environment variable.")
    if not domain:
        raise AuthConfigError("Missing Auth0 Domain. Please set the AUTH0_DOMAIN environment variable.")

    url = f"https://{domain}/oauth/token"
    payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "audience": f"https://{domain}/api/v2/",
        "grant_type": "client_credentials"
    }
    response = requests.post(url, json=payload, timeout=API_TIMEOUT)
    response.raise_for_status()
    return response.json()["access_token"] 