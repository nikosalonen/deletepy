import os
import requests
from dotenv import load_dotenv
from config import get_env_config

def get_access_token(env: str = "dev") -> str:
    """Get access token from Auth0 using client credentials."""
    load_dotenv()
    config = get_env_config(env)
    
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