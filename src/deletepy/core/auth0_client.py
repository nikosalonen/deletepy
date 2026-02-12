"""Unified Auth0 API client for centralized HTTP operations."""

import time
from dataclasses import dataclass
from enum import Enum
from typing import Any

import requests

from .config import API_RATE_LIMIT, API_TIMEOUT


class HttpMethod(Enum):
    """HTTP methods supported by the Auth0 client."""

    GET = "GET"
    POST = "POST"
    PATCH = "PATCH"
    DELETE = "DELETE"
    PUT = "PUT"


@dataclass
class APIResponse:
    """Standardized API response wrapper.

    Attributes:
        success: Whether the request was successful
        status_code: HTTP status code
        data: Response data (parsed JSON or None)
        error_message: Error message if request failed
        rate_limit_remaining: Remaining rate limit from response headers
        rate_limit_reset: Rate limit reset time from response headers
    """

    success: bool
    status_code: int
    data: dict[str, Any] | list[Any] | None = None
    error_message: str | None = None
    rate_limit_remaining: int | None = None
    rate_limit_reset: int | None = None


@dataclass
class Auth0Context:
    """Context object for Auth0 API operations.

    Encapsulates authentication and environment information needed
    for API requests.

    Attributes:
        token: Auth0 access token
        base_url: Auth0 API base URL (e.g., https://your-tenant.auth0.com)
        env: Environment name (dev/prod)
    """

    token: str
    base_url: str
    env: str = "dev"


class Auth0Client:
    """Unified client for Auth0 Management API operations.

    This client provides:
    - Automatic header construction
    - Consistent rate limiting
    - Centralized error handling
    - Response parsing and wrapping
    - Dynamic rate limit adaptation based on response headers
    """

    USER_AGENT = "DeletePy/1.0 (Auth0 User Management Tool)"

    def __init__(
        self,
        context: Auth0Context,
        rate_limit: float = API_RATE_LIMIT,
        timeout: int = API_TIMEOUT,
    ):
        """Initialize the Auth0 client.

        Args:
            context: Auth0 context with authentication information
            rate_limit: Minimum time between requests in seconds
            timeout: Request timeout in seconds
        """
        self.context = context
        self.rate_limit = rate_limit
        self.timeout = timeout
        self._last_request_time: float = 0

    @property
    def token(self) -> str:
        """Get the current access token."""
        return self.context.token

    @property
    def base_url(self) -> str:
        """Get the base URL."""
        return self.context.base_url

    def _build_headers(
        self, extra_headers: dict[str, str] | None = None
    ) -> dict[str, str]:
        """Build HTTP headers for Auth0 API requests.

        Args:
            extra_headers: Additional headers to include

        Returns:
            dict: Complete headers dictionary
        """
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "User-Agent": self.USER_AGENT,
        }
        if extra_headers:
            headers.update(extra_headers)
        return headers

    def _apply_rate_limit(self, response: requests.Response | None = None) -> None:
        """Apply rate limiting between requests.

        If response headers indicate low remaining rate limit,
        adaptively wait longer.

        Args:
            response: Optional response to check for rate limit headers
        """
        sleep_time = self.rate_limit

        if response is not None:
            # Parse rate limit headers for adaptive throttling
            remaining = response.headers.get("X-RateLimit-Remaining")
            reset_time = response.headers.get("X-RateLimit-Reset")

            if remaining is not None:
                try:
                    remaining_int = int(remaining)
                    # If we're running low on rate limit, wait longer
                    if remaining_int < 5 and reset_time is not None:
                        reset_int = int(reset_time)
                        current_time = int(time.time())
                        if reset_int > current_time:
                            # Wait until reset, with a small buffer
                            sleep_time = max(sleep_time, reset_int - current_time + 0.5)
                except (ValueError, TypeError):
                    pass

        time.sleep(sleep_time)

    def _parse_rate_limit_headers(
        self, response: requests.Response
    ) -> tuple[int | None, int | None]:
        """Parse rate limit information from response headers.

        Args:
            response: HTTP response

        Returns:
            tuple: (remaining, reset_time)
        """
        remaining = None
        reset_time = None

        try:
            if "X-RateLimit-Remaining" in response.headers:
                remaining = int(response.headers["X-RateLimit-Remaining"])
            if "X-RateLimit-Reset" in response.headers:
                reset_time = int(response.headers["X-RateLimit-Reset"])
        except (ValueError, TypeError):
            pass

        return remaining, reset_time

    def _handle_response(
        self,
        response: requests.Response,
        operation_name: str = "API request",
    ) -> APIResponse:
        """Handle HTTP response and create standardized APIResponse.

        Args:
            response: HTTP response from requests
            operation_name: Name of the operation for error messages

        Returns:
            APIResponse: Standardized response wrapper
        """
        remaining, reset_time = self._parse_rate_limit_headers(response)

        # Handle rate limiting
        if response.status_code == 429:
            return APIResponse(
                success=False,
                status_code=429,
                error_message=f"Rate limit exceeded during {operation_name}",
                rate_limit_remaining=remaining,
                rate_limit_reset=reset_time,
            )

        # Handle not found
        if response.status_code == 404:
            return APIResponse(
                success=False,
                status_code=404,
                error_message=f"Resource not found during {operation_name}",
                rate_limit_remaining=remaining,
                rate_limit_reset=reset_time,
            )

        # Handle other client errors
        if 400 <= response.status_code < 500:
            try:
                error_data = response.json()
                if isinstance(error_data, dict):
                    error_msg = error_data.get(
                        "message", error_data.get("error", str(error_data))
                    )
                else:
                    # Handle non-dict JSON responses (list, string, etc.)
                    error_msg = str(error_data)
            except ValueError:
                error_msg = response.text or f"Client error {response.status_code}"

            return APIResponse(
                success=False,
                status_code=response.status_code,
                error_message=f"{operation_name} failed: {error_msg}",
                rate_limit_remaining=remaining,
                rate_limit_reset=reset_time,
            )

        # Handle server errors
        if response.status_code >= 500:
            return APIResponse(
                success=False,
                status_code=response.status_code,
                error_message=f"Server error during {operation_name}: {response.status_code}",
                rate_limit_remaining=remaining,
                rate_limit_reset=reset_time,
            )

        # Success - parse response body
        data = None
        if response.text:
            try:
                data = response.json()
            except ValueError:
                # Response might not be JSON (e.g., 204 No Content)
                pass

        return APIResponse(
            success=True,
            status_code=response.status_code,
            data=data,
            rate_limit_remaining=remaining,
            rate_limit_reset=reset_time,
        )

    def request(
        self,
        method: HttpMethod,
        endpoint: str,
        params: dict[str, Any] | None = None,
        json_data: dict[str, Any] | None = None,
        extra_headers: dict[str, str] | None = None,
        operation_name: str = "API request",
    ) -> APIResponse:
        """Make an HTTP request to the Auth0 API.

        Args:
            method: HTTP method to use
            endpoint: API endpoint (relative to base_url, e.g., "/api/v2/users")
            params: Query parameters
            json_data: JSON body data
            extra_headers: Additional headers
            operation_name: Name of the operation for error messages

        Returns:
            APIResponse: Standardized response wrapper
        """
        url = f"{self.base_url}{endpoint}"
        headers = self._build_headers(extra_headers)

        try:
            response = requests.request(
                method=method.value,
                url=url,
                headers=headers,
                params=params,
                json=json_data,
                timeout=self.timeout,
            )

            # Apply rate limiting with adaptive behavior
            self._apply_rate_limit(response)

            return self._handle_response(response, operation_name)

        except requests.exceptions.Timeout:
            return APIResponse(
                success=False,
                status_code=0,
                error_message=f"Request timeout during {operation_name}",
            )
        except requests.exceptions.ConnectionError:
            return APIResponse(
                success=False,
                status_code=0,
                error_message=f"Connection error during {operation_name}",
            )
        except requests.exceptions.RequestException as e:
            return APIResponse(
                success=False,
                status_code=0,
                error_message=f"Request failed during {operation_name}: {str(e)}",
            )

    def get(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
        operation_name: str = "GET request",
    ) -> APIResponse:
        """Make a GET request to the Auth0 API.

        Args:
            endpoint: API endpoint
            params: Query parameters
            operation_name: Name of the operation

        Returns:
            APIResponse: Standardized response wrapper
        """
        return self.request(
            method=HttpMethod.GET,
            endpoint=endpoint,
            params=params,
            operation_name=operation_name,
        )

    def post(
        self,
        endpoint: str,
        json_data: dict[str, Any] | None = None,
        operation_name: str = "POST request",
    ) -> APIResponse:
        """Make a POST request to the Auth0 API.

        Args:
            endpoint: API endpoint
            json_data: JSON body data
            operation_name: Name of the operation

        Returns:
            APIResponse: Standardized response wrapper
        """
        return self.request(
            method=HttpMethod.POST,
            endpoint=endpoint,
            json_data=json_data,
            operation_name=operation_name,
        )

    def patch(
        self,
        endpoint: str,
        json_data: dict[str, Any] | None = None,
        operation_name: str = "PATCH request",
    ) -> APIResponse:
        """Make a PATCH request to the Auth0 API.

        Args:
            endpoint: API endpoint
            json_data: JSON body data
            operation_name: Name of the operation

        Returns:
            APIResponse: Standardized response wrapper
        """
        return self.request(
            method=HttpMethod.PATCH,
            endpoint=endpoint,
            json_data=json_data,
            operation_name=operation_name,
        )

    def delete(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
        operation_name: str = "DELETE request",
    ) -> APIResponse:
        """Make a DELETE request to the Auth0 API.

        Args:
            endpoint: API endpoint
            params: Query parameters
            operation_name: Name of the operation

        Returns:
            APIResponse: Standardized response wrapper
        """
        return self.request(
            method=HttpMethod.DELETE,
            endpoint=endpoint,
            params=params,
            operation_name=operation_name,
        )

    # Convenience methods for common Auth0 operations

    def get_user(self, user_id: str) -> APIResponse:
        """Get user details by ID.

        Args:
            user_id: URL-encoded Auth0 user ID

        Returns:
            APIResponse: Response containing user data
        """
        return self.get(
            endpoint=f"/api/v2/users/{user_id}",
            operation_name="get user",
        )

    def get_users_by_email(self, email: str) -> APIResponse:
        """Get users by email address.

        Args:
            email: Email address to search for

        Returns:
            APIResponse: Response containing list of users
        """
        return self.get(
            endpoint="/api/v2/users-by-email",
            params={"email": email},
            operation_name="get users by email",
        )

    def delete_user(self, user_id: str) -> APIResponse:
        """Delete a user.

        Args:
            user_id: URL-encoded Auth0 user ID

        Returns:
            APIResponse: Response indicating success/failure
        """
        return self.delete(
            endpoint=f"/api/v2/users/{user_id}",
            operation_name="delete user",
        )

    def update_user(self, user_id: str, data: dict[str, Any]) -> APIResponse:
        """Update user properties.

        Args:
            user_id: URL-encoded Auth0 user ID
            data: Properties to update

        Returns:
            APIResponse: Response containing updated user data
        """
        return self.patch(
            endpoint=f"/api/v2/users/{user_id}",
            json_data=data,
            operation_name="update user",
        )

    def block_user(self, user_id: str) -> APIResponse:
        """Block a user.

        Args:
            user_id: URL-encoded Auth0 user ID

        Returns:
            APIResponse: Response indicating success/failure
        """
        return self.update_user(user_id, {"blocked": True})

    def get_user_sessions(self, user_id: str) -> APIResponse:
        """Get active sessions for a user.

        Args:
            user_id: URL-encoded Auth0 user ID

        Returns:
            APIResponse: Response containing sessions list
        """
        return self.get(
            endpoint=f"/api/v2/users/{user_id}/sessions",
            operation_name="get user sessions",
        )

    def delete_session(self, session_id: str) -> APIResponse:
        """Delete a specific session.

        Args:
            session_id: Session ID to delete

        Returns:
            APIResponse: Response indicating success/failure
        """
        return self.delete(
            endpoint=f"/api/v2/sessions/{session_id}",
            operation_name="delete session",
        )

    def delete_user_grants(self, user_id: str) -> APIResponse:
        """Delete all grants for a user.

        Args:
            user_id: Raw Auth0 user ID (not URL-encoded, passed as query param)

        Returns:
            APIResponse: Response indicating success/failure
        """
        return self.delete(
            endpoint="/api/v2/grants",
            params={"user_id": user_id},
            operation_name="delete user grants",
        )

    def unlink_identity(
        self,
        user_id: str,
        provider: str,
        identity_id: str,
    ) -> APIResponse:
        """Unlink a secondary identity from a user.

        Args:
            user_id: URL-encoded Auth0 user ID
            provider: Identity provider (e.g., "google-oauth2")
            identity_id: Identity ID to unlink

        Returns:
            APIResponse: Response indicating success/failure
        """
        return self.delete(
            endpoint=f"/api/v2/users/{user_id}/identities/{provider}/{identity_id}",
            operation_name="unlink identity",
        )

    def search_users(
        self,
        query: str,
        page: int = 0,
        per_page: int = 100,
        include_totals: bool = True,
    ) -> APIResponse:
        """Search for users using a query string.

        Args:
            query: Lucene query string
            page: Page number (0-based)
            per_page: Results per page
            include_totals: Whether to include total count

        Returns:
            APIResponse: Response containing search results
        """
        return self.get(
            endpoint="/api/v2/users",
            params={
                "q": query,
                "search_engine": "v3",
                "page": str(page),
                "per_page": str(per_page),
                "include_totals": str(include_totals).lower(),
            },
            operation_name="search users",
        )


def create_client_from_token(
    token: str, base_url: str, env: str = "dev"
) -> Auth0Client:
    """Factory function to create an Auth0Client from basic parameters.

    Args:
        token: Auth0 access token
        base_url: Auth0 API base URL
        env: Environment name

    Returns:
        Auth0Client: Configured client instance
    """
    context = Auth0Context(token=token, base_url=base_url, env=env)
    return Auth0Client(context)
