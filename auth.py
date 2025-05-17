import os
import requests
from dotenv import load_dotenv
from config import get_env_config

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
    
    client_id = os.getenv(config["client_id"])
    client_secret = os.getenv(config["client_secret"])
    domain = config["auth0_domain"]
    
    # Validate required environment variables
    if not client_id:
        raise AuthConfigError(f"Missing required environment variable: {config['client_id']}")
    if not client_secret:
        raise AuthConfigError(f"Missing required environment variable: {config['client_secret']}")
    if not domain:
        raise AuthConfigError("Missing required configuration: auth0_domain")

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