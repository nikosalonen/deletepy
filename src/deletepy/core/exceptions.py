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

    pass


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
