from typing import Any

from dotenv import load_dotenv

from ..utils.logging_utils import get_logger
from .auth0_client import Auth0ClientManager, get_management_token
from .config import get_env_config
from .exceptions import AuthConfigError

# API timeout in seconds for authentication requests
API_TIMEOUT = 30

# Auth0 token request timeout in seconds
AUTH0_TOKEN_TIMEOUT = 5

# Module logger
logger = get_logger(__name__)


def get_access_token(env: str = "dev") -> str:
    """Get access token from Auth0 using client credentials via SDK.

    Args:
        env: Environment to use ('dev' or 'prod')

    Returns:
        str: Access token for authentication

    Raises:
        AuthConfigError: If required environment variables are missing
    """
    load_dotenv(override=True)

    # Use the SDK-based token acquisition
    try:
        return get_management_token(env)
    except AuthConfigError:
        # Re-raise as-is
        raise
    except Exception as e:
        # Wrap any unexpected errors
        raise AuthConfigError(f"Failed to get access token for {env}: {str(e)}") from e


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

        logger.info("  🔑 Getting access token via SDK...")
        get_access_token(env)
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
            logger.info("  🌐 Testing API access via SDK...")
            try:
                # Use SDK client to test API access
                client_manager = Auth0ClientManager(env)
                client = client_manager.get_client()

                # Make a simple API call to test access
                # List users with minimal result set
                _ = client.users.list(per_page=1)

                logger.info(
                    "    ✅ API access successful",
                    extra={
                        "operation": "api_test",
                        "status": "success",
                    },
                )
                result["api_tested"] = True
                result["api_status"] = "success"
                result["details"] = "Credentials and API access are working correctly"
            except Exception as api_error:
                logger.warning(
                    f"    ⚠️  API access test failed: {api_error}",
                    extra={
                        "operation": "api_test",
                        "status": "failed",
                        "error": str(api_error),
                    },
                )
                result["api_tested"] = True
                result["api_status"] = "failed"
                result[
                    "details"
                ] = f"Token obtained but API access failed: {str(api_error)}"

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
