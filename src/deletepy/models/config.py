"""Configuration data models for Auth0 user management."""

from dataclasses import dataclass
from typing import Any


@dataclass
class Auth0Config:
    """Configuration for Auth0 API access."""

    domain: str
    client_id: str
    client_secret: str
    environment: str
    base_url: str | None = None

    def __post_init__(self) -> None:
        """Set base_url after initialization if not provided."""
        if self.base_url is None:
            self.base_url = f"https://{self.domain}"

    @classmethod
    def from_env_vars(cls, env_vars: dict[str, str], environment: str) -> "Auth0Config":
        """Create Auth0Config from environment variables.

        Args:
            env_vars: Dictionary of environment variables
            environment: Environment name ('dev' or 'prod')

        Returns:
            Auth0Config: Configuration instance

        Raises:
            ValueError: If required environment variables are missing
        """
        prefix = "DEV_" if environment == "dev" else ""

        domain = env_vars.get(f"{prefix}AUTH0_DOMAIN")
        client_id = env_vars.get(f"{prefix}AUTH0_CLIENT_ID")
        client_secret = env_vars.get(f"{prefix}AUTH0_CLIENT_SECRET")

        if not domain:
            raise ValueError(f"Missing {prefix}AUTH0_DOMAIN environment variable")
        if not client_id:
            raise ValueError(f"Missing {prefix}AUTH0_CLIENT_ID environment variable")
        if not client_secret:
            raise ValueError(
                f"Missing {prefix}AUTH0_CLIENT_SECRET environment variable"
            )

        return cls(
            domain=domain,
            client_id=client_id,
            client_secret=client_secret,
            environment=environment,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert config to dictionary format.

        Returns:
            Dict[str, Any]: Configuration as dictionary
        """
        return {
            "domain": self.domain,
            "client_id": self.client_id,
            "client_secret": "***REDACTED***",  # Don't expose secrets
            "environment": self.environment,
            "base_url": self.base_url,
        }

    def get_token_url(self) -> str:
        """Get the OAuth token URL for this configuration.

        Returns:
            str: OAuth token URL
        """
        return f"{self.base_url}/oauth/token"

    def get_api_url(self, endpoint: str = "") -> str:
        """Get the Management API URL for this configuration.

        Args:
            endpoint: API endpoint to append (optional)

        Returns:
            str: Management API URL
        """
        base_api_url = f"{self.base_url}/api/v2"
        if endpoint:
            # Remove leading slash if present
            endpoint = endpoint.lstrip("/")
            return f"{base_api_url}/{endpoint}"
        return base_api_url

    def validate(self) -> bool:
        """Validate that all required fields are present and valid.

        Returns:
            bool: True if configuration is valid
        """
        if not self.domain or not self.client_id or not self.client_secret:
            return False

        if self.environment not in ["dev", "prod"]:
            return False

        # Basic domain validation
        if not self.domain.endswith(".auth0.com") and not self.domain.endswith(
            ".eu.auth0.com"
        ):
            return False

        return True


@dataclass
class APIConfig:
    """Configuration for API rate limiting and timeouts."""

    rate_limit: float = 0.5  # Seconds between requests
    timeout: int = 30  # Request timeout in seconds
    max_retries: int = 3
    base_retry_delay: float = 1.0
    max_retry_delay: float = 60.0

    def get_requests_per_second(self) -> float:
        """Calculate requests per second based on rate limit.

        Returns:
            float: Requests per second
        """
        return 1.0 / self.rate_limit if self.rate_limit > 0 else float("inf")

    def is_safe_for_auth0(self) -> bool:
        """Check if rate limit is safe for Auth0 API limits.

        Auth0 limits: 2 requests per second, 1000 per hour

        Returns:
            bool: True if rate limit is within safe bounds
        """
        return self.get_requests_per_second() <= 2.0


@dataclass
class ExportConfig:
    """Configuration for export operations."""

    default_batch_size: int = 50
    max_batch_size: int = 100
    min_batch_size: int = 10
    large_dataset_threshold: int = 1000
    medium_dataset_threshold: int = 500

    def get_optimal_batch_size(self, total_items: int) -> int:
        """Calculate optimal batch size based on dataset size.

        Args:
            total_items: Total number of items to process

        Returns:
            int: Optimal batch size
        """
        if total_items > self.large_dataset_threshold:
            return 25
        if total_items > self.medium_dataset_threshold:
            return 50
        return 100


@dataclass
class AppConfig:
    """Main application configuration."""

    auth0: Auth0Config
    api: APIConfig | None = None
    export: ExportConfig | None = None
    debug: bool = False

    def __post_init__(self) -> None:
        """Initialize default configs if not provided."""
        if self.api is None:
            self.api = APIConfig()
        if self.export is None:
            self.export = ExportConfig()

    @classmethod
    def create_for_environment(
        cls, environment: str, env_vars: dict[str, str]
    ) -> "AppConfig":
        """Create application configuration for specified environment.

        Args:
            environment: Environment name ('dev' or 'prod')
            env_vars: Dictionary of environment variables

        Returns:
            AppConfig: Application configuration
        """
        auth0_config = Auth0Config.from_env_vars(env_vars, environment)

        return cls(auth0=auth0_config, debug=environment == "dev")

    def validate(self) -> bool:
        """Validate the entire application configuration.

        Returns:
            bool: True if all configurations are valid
        """
        if not self.auth0.validate():
            return False

        if self.api and not self.api.is_safe_for_auth0():
            return False

        return True

    def to_dict(self) -> dict[str, Any]:
        """Convert entire config to dictionary format.

        Returns:
            Dict[str, Any]: Configuration as dictionary
        """
        result = {"auth0": self.auth0.to_dict(), "debug": self.debug}

        if self.api:
            result["api"] = {
                "rate_limit": self.api.rate_limit,
                "timeout": self.api.timeout,
                "max_retries": self.api.max_retries,
                "requests_per_second": self.api.get_requests_per_second(),
            }

        if self.export:
            result["export"] = {
                "default_batch_size": self.export.default_batch_size,
                "max_batch_size": self.export.max_batch_size,
                "min_batch_size": self.export.min_batch_size,
            }

        return result
