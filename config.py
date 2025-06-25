import os
from pathlib import Path
from dotenv import load_dotenv


def check_env_file():
    """Check if .env file exists"""
    if not Path(".env").is_file():
        raise FileNotFoundError(
            "Error: .env file not found. Please create a .env file with your credentials."
        )


def validate_env_var(name: str, value: str | None) -> str:
    """Validate that an environment variable exists and is not empty.

    Args:
        name: The name of the environment variable
        value: The value of the environment variable

    Returns:
        The validated value

    Raises:
        ValueError: If the environment variable is missing or empty
    """
    if value is None or value.strip() == "":
        raise ValueError(f"Required environment variable '{name}' is missing or empty")
    return value


def get_env_config(env: str = "dev"):
    """Get environment configuration based on environment.

    Args:
        env: The environment to get configuration for ('dev' or 'prod')

    Returns:
        dict: Configuration dictionary with validated environment variables

    Raises:
        ValueError: If environment is invalid or required variables are missing
    """
    # Load environment variables from .env file
    load_dotenv()

    env_config = {
        "prod": {
            "client_id": "AUTH0_CLIENT_ID",
            "client_secret": "AUTH0_CLIENT_SECRET",
            "auth0_domain": "AUTH0_DOMAIN",
            "api_url": "URL",
        },
        "dev": {
            "client_id": "DEV_AUTH0_CLIENT_ID",
            "client_secret": "DEV_AUTH0_CLIENT_SECRET",
            "auth0_domain": "DEV_AUTH0_DOMAIN",
            "api_url": "DEV_URL",
        },
    }

    if env not in env_config:
        raise ValueError("Environment must be either 'dev' or 'prod'")

    config = env_config[env]

    # Validate all environment variables
    validated_config = {
        "client_id": validate_env_var(
            config["client_id"], os.getenv(config["client_id"])
        ),
        "client_secret": validate_env_var(
            config["client_secret"], os.getenv(config["client_secret"])
        ),
        "auth0_domain": validate_env_var(
            config["auth0_domain"], os.getenv(config["auth0_domain"])
        ),
        "api_url": validate_env_var(config["api_url"], os.getenv(config["api_url"])),
    }

    return validated_config


def get_base_url(env: str = "dev") -> str:
    """Get base URL based on environment."""
    config = get_env_config(env)
    return f"https://{config['auth0_domain']}"
