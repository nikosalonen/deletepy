from typing import Any, cast

import requests
from dotenv import load_dotenv

from ..utils.logging_utils import get_logger
from .auth0_client import create_client_from_token
from .config import get_env_config
from .exceptions import AuthConfigError

# API timeout in seconds for authentication requests
API_TIMEOUT = 30

# Module logger
logger = get_logger(__name__)


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
    load_dotenv(override=True)
    config = get_env_config(env)

    client_id = config["client_id"]
    client_secret = config["client_secret"]
    domain = config["domain"]

    # Validate required environment variables
    if not client_id:
        raise AuthConfigError(
            f"Missing Auth0 Client ID. Please set the {'DEV_AUTH0_CLIENT_ID' if env == 'dev' else 'AUTH0_CLIENT_ID'} environment variable."
        )
    if not client_secret:
        raise AuthConfigError(
            f"Missing Auth0 Client Secret. Please set the {'DEV_AUTH0_CLIENT_SECRET' if env == 'dev' else 'AUTH0_CLIENT_SECRET'} environment variable."
        )
    if not domain:
        raise AuthConfigError(
            f"Missing Auth0 Domain. Please set the {'DEV_AUTH0_DOMAIN' if env == 'dev' else 'AUTH0_DOMAIN'} environment variable."
        )

    url = f"https://{domain}/oauth/token"
    headers = {
        "User-Agent": "DeletePy/1.0 (Auth0 User Management Tool)",
        "Content-Type": "application/json",
    }
    payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "audience": f"https://{domain}/api/v2/",
        "grant_type": "client_credentials",
        "scope": "delete:users update:users delete:sessions delete:grants read:users",
    }
    response = requests.post(url, json=payload, headers=headers, timeout=API_TIMEOUT)
    response.raise_for_status()
    try:
        json_response: dict[str, Any] = response.json()
        if "access_token" not in json_response:
            raise AuthConfigError("Access token not found in Auth0 response")
        return cast(str, json_response["access_token"])
    except ValueError as e:
        raise AuthConfigError(f"Invalid JSON response from Auth0: {str(e)}") from e


def doctor(env: str = "dev", test_api: bool = False) -> dict[str, Any]:
    """Test if the credentials work by getting an access token and optionally testing API access.

    Args:
        env: Environment to use ('dev' or 'prod')
        test_api: Whether to test API access with the token

    Returns:
        Dict[str, Any]: Status information including success status and details

    Raises:
        AuthConfigError: If authentication fails
    """
    try:
        logger.info(
            f"🔍 Testing credentials for {env.upper()} environment...",
            extra={"operation": "doctor_check", "environment": env},
        )

        # Test getting access token
        logger.info("  📋 Checking environment variables...")
        config = get_env_config(env)
        logger.info(f"    ✅ Client ID: {config['client_id'][:8]}...")
        logger.info(f"    ✅ Client Secret: {'*' * 8}...")
        logger.info(f"    ✅ Auth0 Domain: {config['domain']}")
        logger.info(f"    ✅ API URL: {config['base_url']}")

        logger.info("  🔑 Getting access token...")
        token = get_access_token(env)
        logger.info(
            "    ✅ Access token obtained successfully",
            extra={"operation": "token_request", "status": "success"},
        )

        result = {
            "success": True,
            "environment": env,
            "token_obtained": True,
            "api_tested": False,
            "details": "Credentials are working correctly",
        }

        if test_api:
            logger.info("  🌐 Testing API access...")
            client = create_client_from_token(token, config["base_url"], env)

            # Make a simple API call to test the token
            api_result = client.get(
                endpoint="/api/v2/users",
                params={"per_page": 1},
                operation_name="doctor API test",
            )

            if api_result.success:
                logger.info(
                    "    ✅ API access successful",
                    extra={
                        "operation": "api_test",
                        "status": "success",
                        "status_code": api_result.status_code,
                    },
                )
                result["api_tested"] = True
                result["api_status"] = "success"
                result["details"] = "Credentials and API access are working correctly"
            else:
                logger.warning(
                    f"    ⚠️  API access failed with status {api_result.status_code}",
                    extra={
                        "operation": "api_test",
                        "status": "failed",
                        "status_code": api_result.status_code,
                    },
                )
                result["api_tested"] = True
                result["api_status"] = f"failed_{api_result.status_code}"
                result["details"] = (
                    f"Token obtained but API access failed with status {api_result.status_code}"
                )

        logger.info(
            "✅ Doctor check completed successfully!",
            extra={
                "operation": "doctor_check",
                "status": "completed",
                "environment": env,
            },
        )
        return result

    except AuthConfigError as e:
        logger.error(
            f"❌ Authentication configuration error: {str(e)}",
            extra={
                "operation": "doctor_check",
                "error_type": "AuthConfigError",
                "environment": env,
            },
            exc_info=True,
        )
        return {
            "success": False,
            "environment": env,
            "token_obtained": False,
            "api_tested": False,
            "error": str(e),
            "details": "Authentication configuration is invalid",
        }
    except requests.exceptions.RequestException as e:
        logger.error(
            f"❌ Network/API error: {str(e)}",
            extra={
                "operation": "doctor_check",
                "error_type": "RequestException",
                "environment": env,
            },
            exc_info=True,
        )
        return {
            "success": False,
            "environment": env,
            "token_obtained": False,
            "api_tested": False,
            "error": str(e),
            "details": "Network or API request failed",
        }
    except Exception as e:
        logger.error(
            f"❌ Unexpected error: {str(e)}",
            extra={
                "operation": "doctor_check",
                "error_type": "UnexpectedError",
                "environment": env,
            },
            exc_info=True,
        )
        return {
            "success": False,
            "environment": env,
            "token_obtained": False,
            "api_tested": False,
            "error": str(e),
            "details": "Unexpected error occurred",
        }
