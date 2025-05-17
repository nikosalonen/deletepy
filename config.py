import os
from pathlib import Path
from dotenv import load_dotenv

def check_env_file():
    """Check if .env file exists"""
    if not Path('.env').is_file():
        raise FileNotFoundError("Error: .env file not found. Please create a .env file with your credentials.")

def get_env_config(env: str = "dev"):
    """Get environment configuration based on environment."""
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

    return env_config[env]

def get_base_url(env: str = "dev") -> str:
    """Get base URL based on environment."""
    config = get_env_config(env)
    return f"https://{config['auth0_domain']}" 