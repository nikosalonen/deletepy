"""Protocol interfaces for Auth0 user management operations."""

from abc import ABC, abstractmethod
from typing import Any, Protocol

from ..models.user import BatchOperationResults, User, UserOperationResult


class Auth0ClientProtocol(Protocol):
    """Protocol for Auth0 API client operations."""

    def get_access_token(self) -> str:
        """Get Auth0 access token.

        Returns:
            str: Access token
        """
        ...

    def get_user(self, user_id: str) -> dict[str, Any] | None:
        """Get user details from Auth0.

        Args:
            user_id: Auth0 user ID

        Returns:
            Optional[Dict[str, Any]]: User data or None if not found
        """
        ...

    def delete_user(self, user_id: str) -> bool:
        """Delete user from Auth0.

        Args:
            user_id: Auth0 user ID

        Returns:
            bool: True if successful
        """
        ...

    def block_user(self, user_id: str) -> bool:
        """Block user in Auth0.

        Args:
            user_id: Auth0 user ID

        Returns:
            bool: True if successful
        """
        ...


class UserRepositoryProtocol(Protocol):
    """Protocol for user data repository operations."""

    def find_by_id(self, user_id: str) -> User | None:
        """Find user by ID.

        Args:
            user_id: Auth0 user ID

        Returns:
            Optional[User]: User instance or None if not found
        """
        ...

    def find_by_email(self, email: str) -> list[User]:
        """Find users by email address.

        Args:
            email: Email address

        Returns:
            List[User]: List of users with matching email
        """
        ...

    def find_by_social_id(self, social_id: str) -> list[User]:
        """Find users by social media ID.

        Args:
            social_id: Social media ID

        Returns:
            List[User]: List of users with matching social ID
        """
        ...


class UserOperationProtocol(Protocol):
    """Protocol for user operation services."""

    def execute_operation(self, user_id: str, operation: str) -> UserOperationResult:
        """Execute an operation on a user.

        Args:
            user_id: Auth0 user ID
            operation: Operation to perform

        Returns:
            UserOperationResult: Result of the operation
        """
        ...

    def execute_batch_operation(
        self, user_ids: list[str], operation: str
    ) -> BatchOperationResults:
        """Execute batch operation on multiple users.

        Args:
            user_ids: List of Auth0 user IDs
            operation: Operation to perform

        Returns:
            BatchOperationResults: Results of the batch operation
        """
        ...


class FileHandlerProtocol(Protocol):
    """Protocol for file handling operations."""

    def read_user_ids(self, file_path: str) -> list[str]:
        """Read user IDs from file.

        Args:
            file_path: Path to file containing user IDs

        Returns:
            List[str]: List of user IDs
        """
        ...

    def write_csv(self, data: list[dict[str, Any]], file_path: str) -> bool:
        """Write data to CSV file.

        Args:
            data: Data to write
            file_path: Output file path

        Returns:
            bool: True if successful
        """
        ...


class ProgressReporterProtocol(Protocol):
    """Protocol for progress reporting."""

    def report_progress(self, current: int, total: int, message: str) -> None:
        """Report progress of an operation.

        Args:
            current: Current item number
            total: Total number of items
            message: Progress message
        """
        ...

    def report_completion(self, results: BatchOperationResults) -> None:
        """Report completion of batch operation.

        Args:
            results: Batch operation results
        """
        ...


class ConfigProviderProtocol(Protocol):
    """Protocol for configuration management."""

    def get_auth0_config(self, environment: str) -> dict[str, Any]:
        """Get Auth0 configuration for environment.

        Args:
            environment: Environment name ('dev' or 'prod')

        Returns:
            Dict[str, Any]: Auth0 configuration
        """
        ...

    def get_api_config(self) -> dict[str, Any]:
        """Get API configuration.

        Returns:
            Dict[str, Any]: API configuration
        """
        ...


# Abstract base classes for concrete implementations


class BaseUserService(ABC):
    """Abstract base class for user services."""

    @abstractmethod
    def get_user_details(self, user_id: str) -> User | None:
        """Get user details.

        Args:
            user_id: Auth0 user ID

        Returns:
            Optional[User]: User details or None if not found
        """

    @abstractmethod
    def delete_user(self, user_id: str) -> UserOperationResult:
        """Delete user.

        Args:
            user_id: Auth0 user ID

        Returns:
            UserOperationResult: Operation result
        """

    @abstractmethod
    def block_user(self, user_id: str) -> UserOperationResult:
        """Block user.

        Args:
            user_id: Auth0 user ID

        Returns:
            UserOperationResult: Operation result
        """


class BaseBatchProcessor(ABC):
    """Abstract base class for batch processing."""

    @abstractmethod
    def process_batch(
        self, user_ids: list[str], operation: str
    ) -> BatchOperationResults:
        """Process batch of users.

        Args:
            user_ids: List of user IDs
            operation: Operation to perform

        Returns:
            BatchOperationResults: Batch operation results
        """

    @abstractmethod
    def estimate_processing_time(self, user_count: int) -> float:
        """Estimate processing time for batch operation.

        Args:
            user_count: Number of users to process

        Returns:
            float: Estimated time in minutes
        """


class BaseExportService(ABC):
    """Abstract base class for export services."""

    @abstractmethod
    def export_users_to_csv(self, users: list[User], file_path: str) -> bool:
        """Export users to CSV file.

        Args:
            users: List of users to export
            file_path: Output file path

        Returns:
            bool: True if successful
        """

    @abstractmethod
    def export_last_login_data(self, emails: list[str], file_path: str) -> bool:
        """Export last login data to CSV.

        Args:
            emails: List of email addresses
            file_path: Output file path

        Returns:
            bool: True if successful
        """


class BaseValidator(ABC):
    """Abstract base class for validators."""

    @abstractmethod
    def validate_user_id(self, user_id: str) -> bool:
        """Validate Auth0 user ID format.

        Args:
            user_id: User ID to validate

        Returns:
            bool: True if valid
        """

    @abstractmethod
    def validate_email(self, email: str) -> bool:
        """Validate email address format.

        Args:
            email: Email to validate

        Returns:
            bool: True if valid
        """

    @abstractmethod
    def validate_domain(self, domain: str) -> bool:
        """Validate domain format.

        Args:
            domain: Domain to validate

        Returns:
            bool: True if valid
        """
