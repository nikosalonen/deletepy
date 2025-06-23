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
        raise AuthConfigError(f"Missing Auth0 Client ID. Please set the {'DEV_AUTH0_CLIENT_ID' if env == 'dev' else 'AUTH0_CLIENT_ID'} environment variable.")
    if not client_secret:
        raise AuthConfigError(f"Missing Auth0 Client Secret. Please set the {'DEV_AUTH0_CLIENT_SECRET' if env == 'dev' else 'AUTH0_CLIENT_SECRET'} environment variable.")
    if not domain:
        raise AuthConfigError(f"Missing Auth0 Domain. Please set the {'DEV_AUTH0_DOMAIN' if env == 'dev' else 'AUTH0_DOMAIN'} environment variable.")

    url = f"https://{domain}/oauth/token"
    headers = {
        "User-Agent": "DeletePy/1.0 (Auth0 User Management Tool)",
        "Content-Type": "application/json"
    }
    payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "audience": f"https://{domain}/api/v2/",
        "grant_type": "client_credentials",
        "scope": "delete:users update:users delete:sessions delete:grants read:users"
    }
    response = requests.post(url, json=payload, headers=headers, timeout=API_TIMEOUT)
    response.raise_for_status()
    try:
        json_response = response.json()
        if "access_token" not in json_response:
            raise AuthConfigError("Access token not found in Auth0 response")
        return json_response["access_token"]
    except ValueError as e:
        raise AuthConfigError(f"Invalid JSON response from Auth0: {str(e)}") from e

def doctor(env: str = "dev", test_api: bool = False) -> dict:
    """Test if the credentials work by getting an access token and optionally testing API access.

    Args:
        env: Environment to use ('dev' or 'prod')
        test_api: Whether to test API access with the token

    Returns:
        dict: Status information including success status and details

    Raises:
        AuthConfigError: If authentication fails
    """
    try:
        print(f"🔍 Testing credentials for {env.upper()} environment...")

        # Test getting access token
        print("  📋 Checking environment variables...")
        config = get_env_config(env)
        print(f"    ✅ Client ID: {config['client_id'][:8]}...")
        print(f"    ✅ Client Secret: {'*' * 8}...")
        print(f"    ✅ Auth0 Domain: {config['auth0_domain']}")
        print(f"    ✅ API URL: {config['api_url']}")

        print("  🔑 Getting access token...")
        token = get_access_token(env)
        print("    ✅ Access token obtained successfully")

        result = {
            "success": True,
            "environment": env,
            "token_obtained": True,
            "api_tested": False,
            "details": "Credentials are working correctly"
        }

        if test_api:
            print("  🌐 Testing API access...")
            base_url = f"https://{config['auth0_domain']}"
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }

            # Make a simple API call to test the token
            test_url = f"{base_url}/api/v2/users"
            response = requests.get(test_url, headers=headers, timeout=API_TIMEOUT, params={"per_page": 1})

            if response.status_code == 200:
                print("    ✅ API access successful")
                result["api_tested"] = True
                result["api_status"] = "success"
                result["details"] = "Credentials and API access are working correctly"
            else:
                print(f"    ⚠️  API access failed with status {response.status_code}")
                result["api_tested"] = True
                result["api_status"] = f"failed_{response.status_code}"
                result["details"] = f"Token obtained but API access failed with status {response.status_code}"

        print("✅ Doctor check completed successfully!")
        return result

    except AuthConfigError as e:
        print(f"❌ Authentication configuration error: {str(e)}")
        return {
            "success": False,
            "environment": env,
            "token_obtained": False,
            "api_tested": False,
            "error": str(e),
            "details": "Authentication configuration is invalid"
        }
    except requests.exceptions.RequestException as e:
        print(f"❌ Network/API error: {str(e)}")
        return {
            "success": False,
            "environment": env,
            "token_obtained": False,
            "api_tested": False,
            "error": str(e),
            "details": "Network or API request failed"
        }
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
        return {
            "success": False,
            "environment": env,
            "token_obtained": False,
            "api_tested": False,
            "error": str(e),
            "details": "Unexpected error occurred"
        }
