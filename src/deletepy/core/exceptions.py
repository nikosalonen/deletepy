"""Custom exception hierarchy for DeletePy Auth0 User Management Tool."""


class Auth0ManagerError(Exception):
    """Base exception for Auth0 Manager.

    This is the root exception class for all DeletePy-specific errors.
    All other custom exceptions should inherit from this class.
    """

    def __init__(self, message: str, details: str | None = None):
        """Initialize the exception.

        Args:
            message: The main error message
            details: Optional additional details about the error
        """
        self.message = message
        self.details = details
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        """Format the complete error message."""
        if self.details:
            return f"{self.message}: {self.details}"
        return self.message


class AuthConfigError(Auth0ManagerError):
    """Authentication configuration errors.

    Raised when there are issues with Auth0 authentication configuration,
    such as missing credentials, invalid tokens, or connection failures.
    """


class UserOperationError(Auth0ManagerError):
    """User operation errors.

    Raised when Auth0 user operations fail, such as user deletion,
    blocking, session revocation, or identity management operations.
    """

    def __init__(
        self,
        message: str,
        user_id: str | None = None,
        operation: str | None = None,
        details: str | None = None,
    ):
        """Initialize the user operation error.

        Args:
            message: The main error message
            user_id: The Auth0 user ID that caused the error
            operation: The operation that failed (delete, block, etc.)
            details: Optional additional details about the error
        """
        self.user_id = user_id
        self.operation = operation
        super().__init__(message, details)

    def _format_message(self) -> str:
        """Format the complete error message with user context."""
        parts = [self.message]

        if self.operation:
            parts.append(f"Operation: {self.operation}")

        if self.user_id:
            parts.append(f"User ID: {self.user_id}")

        if self.details:
            parts.append(f"Details: {self.details}")

        return " | ".join(parts)


class FileOperationError(Auth0ManagerError):
    """File operation errors.

    Raised when file operations fail, such as reading input files,
    writing output files, or CSV processing operations.
    """

    def __init__(
        self,
        message: str,
        file_path: str | None = None,
        operation: str | None = None,
        details: str | None = None,
    ):
        """Initialize the file operation error.

        Args:
            message: The main error message
            file_path: The file path that caused the error
            operation: The file operation that failed (read, write, etc.)
            details: Optional additional details about the error
        """
        self.file_path = file_path
        self.operation = operation
        super().__init__(message, details)

    def _format_message(self) -> str:
        """Format the complete error message with file context."""
        parts = [self.message]

        if self.operation:
            parts.append(f"Operation: {self.operation}")

        if self.file_path:
            parts.append(f"File: {self.file_path}")

        if self.details:
            parts.append(f"Details: {self.details}")

        return " | ".join(parts)


class APIError(Auth0ManagerError):
    """Auth0 API-specific errors.

    Raised when Auth0 API calls fail due to rate limiting,
    invalid requests, or server errors.
    """

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        endpoint: str | None = None,
        details: str | None = None,
    ):
        """Initialize the API error.

        Args:
            message: The main error message
            status_code: The HTTP status code from the API response
            endpoint: The API endpoint that failed
            details: Optional additional details about the error
        """
        self.status_code = status_code
        self.endpoint = endpoint
        super().__init__(message, details)

    def _format_message(self) -> str:
        """Format the complete error message with API context."""
        parts = [self.message]

        if self.status_code:
            parts.append(f"Status: {self.status_code}")

        if self.endpoint:
            parts.append(f"Endpoint: {self.endpoint}")

        if self.details:
            parts.append(f"Details: {self.details}")

        return " | ".join(parts)


class ValidationError(Auth0ManagerError):
    """Input validation errors.

    Raised when user input fails validation, such as invalid
    Auth0 user IDs, malformed email addresses, or invalid file formats.
    """

    def __init__(
        self,
        message: str,
        field: str | None = None,
        value: str | None = None,
        details: str | None = None,
    ):
        """Initialize the validation error.

        Args:
            message: The main error message
            field: The field that failed validation
            value: The invalid value
            details: Optional additional details about the error
        """
        self.field = field
        self.value = value
        super().__init__(message, details)

    def _format_message(self) -> str:
        """Format the complete error message with validation context."""
        parts = [self.message]

        if self.field:
            parts.append(f"Field: {self.field}")

        if self.value:
            parts.append(f"Value: {self.value}")

        if self.details:
            parts.append(f"Details: {self.details}")

        return " | ".join(parts)


class RateLimitError(APIError):
    """Rate limiting errors from Auth0 API.

    Raised when the Auth0 API rate limit is exceeded.
    Contains retry-after information when available.
    """

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: int | None = None,
        endpoint: str | None = None,
        details: str | None = None,
    ):
        """Initialize the rate limit error.

        Args:
            message: The main error message
            retry_after: Seconds to wait before retrying
            endpoint: The API endpoint that was rate limited
            details: Optional additional details
        """
        self.retry_after = retry_after
        super().__init__(
            message=message,
            status_code=429,
            endpoint=endpoint,
            details=details,
        )

    def _format_message(self) -> str:
        """Format the complete error message with retry information."""
        msg = super()._format_message()
        if self.retry_after:
            msg += f" | Retry after: {self.retry_after}s"
        return msg


def wrap_sdk_exception(
    exc: Exception, operation: str | None = None
) -> Auth0ManagerError:
    """Wrap Auth0 SDK exceptions into DeletePy exception hierarchy.

    This function translates Auth0 SDK exceptions into our custom exception
    types for consistent error handling across the application.

    Args:
        exc: The original exception from Auth0 SDK
        operation: Optional operation context

    Returns:
        Auth0ManagerError: Wrapped exception
    """
    # Try to import Auth0 exception types
    try:
        from auth0.exceptions import Auth0Error
    except ImportError:
        # If SDK exceptions aren't available, wrap as generic error
        return Auth0ManagerError(
            message=f"SDK error: {str(exc)}",
            details=f"Operation: {operation}" if operation else None,
        )

    # Handle Auth0 SDK exceptions
    if isinstance(exc, Auth0Error):
        # Extract error details from SDK exception
        error_code = getattr(exc, "status_code", None)
        error_msg = str(exc)

        # Rate limit errors
        if error_code == 429:
            return RateLimitError(
                message=error_msg,
                details=f"Operation: {operation}" if operation else None,
            )

        # Authentication/authorization errors
        if error_code in (401, 403):
            return AuthConfigError(
                message=f"Authentication failed: {error_msg}",
                details=f"Status: {error_code}",
            )

        # Not found errors
        if error_code == 404:
            return UserOperationError(
                message=f"Resource not found: {error_msg}",
                operation=operation,
                details=f"Status: {error_code}",
            )

        # Other API errors
        return APIError(
            message=error_msg,
            status_code=error_code,
            details=f"Operation: {operation}" if operation else None,
        )

    # Wrap any other exceptions
    return Auth0ManagerError(
        message=f"Unexpected error: {str(exc)}",
        details=f"Operation: {operation}, Type: {type(exc).__name__}"
        if operation
        else f"Type: {type(exc).__name__}",
    )
