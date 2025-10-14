"""Auth0 SDK client wrapper for centralized management API access."""


from auth0.authentication import GetToken
from auth0.management import Auth0
from auth0.rest import RestClientOptions

from deletepy.core.config import get_env_config
from deletepy.core.exceptions import AuthConfigError
from deletepy.utils.logging_utils import get_logger

# Auth0 token request timeout in seconds
AUTH0_TOKEN_TIMEOUT = 5

# Module logger
logger = get_logger(__name__)

# Global client cache for singleton pattern
_client_cache: dict[str, Auth0] = {}


class Auth0ClientManager:
    """Manager for Auth0 SDK client instances with connection pooling."""

    def __init__(self, env: str = "dev") -> None:
        """Initialize the Auth0 client manager.

        Args:
            env: Environment to use ('dev' or 'prod')
        """
        self.env = env
        self._config = get_env_config(env)
        self._client: Auth0 | None = None
        self._token: str | None = None

    def get_client(self) -> Auth0:
        """Get or create an Auth0 management client.

        Returns:
            Auth0: Initialized management client

        Raises:
            AuthConfigError: If client initialization fails
        """
        cache_key = f"{self.env}:{self._config['domain']}"

        # Check cache first for connection pooling
        if cache_key in _client_cache:
            logger.debug(
                f"Reusing cached Auth0 client for {self.env}",
                extra={"environment": self.env},
            )
            return _client_cache[cache_key]

        # Get access token if not already obtained
        if self._token is None:
            self._token = self._get_management_token()

        # Initialize Auth0 management client
        try:
            self._client = Auth0(
                domain=self._config["domain"],
                token=self._token,
                rest_options=RestClientOptions(timeout=30.0),
            )

            # Cache the client for reuse
            _client_cache[cache_key] = self._client

            logger.info(
                f"Initialized Auth0 management client for {self.env}",
                extra={
                    "environment": self.env,
                    "domain": self._config["domain"],
                },
            )

            return self._client

        except Exception as e:
            logger.error(
                f"Failed to initialize Auth0 client: {e}",
                extra={"environment": self.env, "error": str(e)},
                exc_info=True,
            )
            raise AuthConfigError(
                f"Failed to initialize Auth0 client for {self.env}: {e}"
            ) from e

    def _get_management_token(self) -> str:
        """Get management API access token using client credentials.

        Returns:
            str: Access token

        Raises:
            AuthConfigError: If token acquisition fails
        """
        try:
            get_token = GetToken(
                domain=self._config["domain"],
                client_id=self._config["client_id"],
                client_secret=self._config["client_secret"],
                timeout=AUTH0_TOKEN_TIMEOUT,
            )

            # Request token with required scopes
            # Note: Auth0 SDK client_credentials doesn't accept scope parameter directly
            # Scopes are managed at the application level in Auth0 dashboard
            token_response = get_token.client_credentials(
                audience=f"https://{self._config['domain']}/api/v2/",
            )

            if "access_token" not in token_response:
                raise AuthConfigError("Access token not found in Auth0 response")

            logger.info(
                "Successfully obtained management API token",
                extra={"environment": self.env},
            )

            return str(token_response["access_token"])

        except Exception as e:
            logger.error(
                f"Failed to get management token: {e}",
                extra={"environment": self.env, "error": str(e)},
                exc_info=True,
            )
            raise AuthConfigError(
                f"Failed to obtain Auth0 management token: {e}"
            ) from e

    def get_token(self) -> str:
        """Get the current management API token.

        Returns:
            str: Access token

        Raises:
            AuthConfigError: If token is not available
        """
        if self._token is None:
            self._token = self._get_management_token()
        return self._token

    @staticmethod
    def clear_cache() -> None:
        """Clear the client cache. Useful for testing or environment switches."""
        global _client_cache
        _client_cache.clear()
        logger.debug("Cleared Auth0 client cache")


def get_auth0_client(env: str = "dev") -> Auth0:
    """Get an Auth0 management client for the specified environment.

    This is a convenience function that creates a client manager and returns
    the client. For better control and reuse, use Auth0ClientManager directly.

    Args:
        env: Environment to use ('dev' or 'prod')

    Returns:
        Auth0: Initialized management client

    Raises:
        AuthConfigError: If client initialization fails
    """
    manager = Auth0ClientManager(env)
    return manager.get_client()


def get_management_token(env: str = "dev") -> str:
    """Get a management API token for the specified environment.

    Args:
        env: Environment to use ('dev' or 'prod')

    Returns:
        str: Access token

    Raises:
        AuthConfigError: If token acquisition fails
    """
    manager = Auth0ClientManager(env)
    return manager.get_token()


def get_base_url(env: str = "dev") -> str:
    """Get the Auth0 base URL for the given environment.

    Args:
        env: Environment to use ('dev' or 'prod')

    Returns:
        str: Base URL for the Auth0 tenant
    """
    config = get_env_config(env)
    base_url: str = config["base_url"]
    return base_url
