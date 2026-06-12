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
