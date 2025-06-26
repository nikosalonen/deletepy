"""User data models for Auth0 user management."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class UserIdentity:
    """Represents an Auth0 user identity."""

    connection: str
    user_id: str
    provider: str
    is_social: bool = False
    access_token: str | None = None
    access_token_secret: str | None = None
    refresh_token: str | None = None
    profile_data: dict[str, Any] = field(default_factory=dict)


@dataclass
class User:
    """Represents an Auth0 user with all relevant data."""

    user_id: str
    email: str | None = None
    connection: str | None = None
    identities: list[UserIdentity] = field(default_factory=list)
    blocked: bool = False
    last_login: datetime | None = None
    last_ip: str | None = None
    logins_count: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None
    email_verified: bool = False
    phone_number: str | None = None
    phone_verified: bool = False
    picture: str | None = None
    nickname: str | None = None
    name: str | None = None
    given_name: str | None = None
    family_name: str | None = None
    locale: str | None = None
    app_metadata: dict[str, Any] = field(default_factory=dict)
    user_metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_auth0_data(cls, data: dict[str, Any]) -> "User":
        """Create a User instance from Auth0 API response data.

        Args:
            data: Auth0 user data from API response

        Returns:
            User: User instance with parsed data
        """
        # Parse identities
        identities = []
        for identity_data in data.get("identities", []):
            identity = UserIdentity(
                connection=identity_data.get("connection", ""),
                user_id=identity_data.get("user_id", ""),
                provider=identity_data.get("provider", ""),
                is_social=identity_data.get("isSocial", False),
                access_token=identity_data.get("access_token"),
                access_token_secret=identity_data.get("access_token_secret"),
                refresh_token=identity_data.get("refresh_token"),
                profile_data=identity_data.get("profileData", {}),
            )
            identities.append(identity)

        # Parse datetime fields
        last_login = None
        if data.get("last_login"):
            try:
                last_login = datetime.fromisoformat(
                    data["last_login"].replace("Z", "+00:00")
                )
            except (ValueError, AttributeError):
                pass

        created_at = None
        if data.get("created_at"):
            try:
                created_at = datetime.fromisoformat(
                    data["created_at"].replace("Z", "+00:00")
                )
            except (ValueError, AttributeError):
                pass

        updated_at = None
        if data.get("updated_at"):
            try:
                updated_at = datetime.fromisoformat(
                    data["updated_at"].replace("Z", "+00:00")
                )
            except (ValueError, AttributeError):
                pass

        return cls(
            user_id=data.get("user_id", ""),
            email=data.get("email"),
            connection=identities[0].connection if identities else None,
            identities=identities,
            blocked=data.get("blocked", False),
            last_login=last_login,
            last_ip=data.get("last_ip"),
            logins_count=data.get("logins_count", 0),
            created_at=created_at,
            updated_at=updated_at,
            email_verified=data.get("email_verified", False),
            phone_number=data.get("phone_number"),
            phone_verified=data.get("phone_verified", False),
            picture=data.get("picture"),
            nickname=data.get("nickname"),
            name=data.get("name"),
            given_name=data.get("given_name"),
            family_name=data.get("family_name"),
            locale=data.get("locale"),
            app_metadata=data.get("app_metadata", {}),
            user_metadata=data.get("user_metadata", {}),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert User instance to dictionary format.

        Returns:
            Dict[str, Any]: User data as dictionary
        """
        return {
            "user_id": self.user_id,
            "email": self.email,
            "connection": self.connection,
            "identities": [
                {
                    "connection": identity.connection,
                    "user_id": identity.user_id,
                    "provider": identity.provider,
                    "isSocial": identity.is_social,
                    "access_token": identity.access_token,
                    "access_token_secret": identity.access_token_secret,
                    "refresh_token": identity.refresh_token,
                    "profileData": identity.profile_data,
                }
                for identity in self.identities
            ],
            "blocked": self.blocked,
            "last_login": self.last_login.isoformat() if self.last_login else None,
            "last_ip": self.last_ip,
            "logins_count": self.logins_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "email_verified": self.email_verified,
            "phone_number": self.phone_number,
            "phone_verified": self.phone_verified,
            "picture": self.picture,
            "nickname": self.nickname,
            "name": self.name,
            "given_name": self.given_name,
            "family_name": self.family_name,
            "locale": self.locale,
            "app_metadata": self.app_metadata,
            "user_metadata": self.user_metadata,
        }

    def is_social_user(self) -> bool:
        """Check if user has only social identities.

        Returns:
            bool: True if user has only social identities
        """
        return len(self.identities) == 1 and self.identities[0].is_social

    def has_multiple_identities(self) -> bool:
        """Check if user has multiple identities.

        Returns:
            bool: True if user has multiple identities
        """
        return len(self.identities) > 1

    def get_primary_identity(self) -> UserIdentity | None:
        """Get the primary identity for the user.

        Returns:
            Optional[UserIdentity]: Primary identity or None if no identities
        """
        return self.identities[0] if self.identities else None

    def get_social_identities(self) -> list[UserIdentity]:
        """Get all social identities for the user.

        Returns:
            List[UserIdentity]: List of social identities
        """
        return [identity for identity in self.identities if identity.is_social]


@dataclass
class UserOperationResult:
    """Represents the result of a user operation."""

    user_id: str
    operation: str
    success: bool
    error_message: str | None = None
    timestamp: datetime = field(default_factory=datetime.now)

    def __str__(self) -> str:
        """String representation of operation result."""
        status = "SUCCESS" if self.success else "FAILED"
        if self.error_message and not self.success:
            return f"{self.operation} {self.user_id}: {status} - {self.error_message}"
        return f"{self.operation} {self.user_id}: {status}"


@dataclass
class BatchOperationResults:
    """Represents results from a batch operation on multiple users."""

    operation: str
    total_users: int
    processed_count: int = 0
    skipped_count: int = 0
    not_found_users: list[str] = field(default_factory=list)
    invalid_user_ids: list[str] = field(default_factory=list)
    multiple_users: dict[str, list[str]] = field(default_factory=dict)
    operation_results: list[UserOperationResult] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        """Calculate success rate of the batch operation.

        Returns:
            float: Success rate as percentage (0-100)
        """
        if self.total_users == 0:
            return 0.0
        return (self.processed_count / self.total_users) * 100.0

    def add_result(self, result: UserOperationResult) -> None:
        """Add an operation result to the batch.

        Args:
            result: Operation result to add
        """
        self.operation_results.append(result)
        if result.success:
            self.processed_count += 1
        else:
            self.skipped_count += 1

    def get_summary(self) -> dict[str, Any]:
        """Get a summary of the batch operation results.

        Returns:
            Dict[str, Any]: Summary data
        """
        return {
            "operation": self.operation,
            "total_users": self.total_users,
            "processed_count": self.processed_count,
            "skipped_count": self.skipped_count,
            "success_rate": self.success_rate,
            "not_found_users_count": len(self.not_found_users),
            "invalid_user_ids_count": len(self.invalid_user_ids),
            "multiple_users_count": len(self.multiple_users),
        }
