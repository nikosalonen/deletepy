"""Core SDK operations wrapper for Auth0 API calls.

This module provides a clean interface between the SDK and our business logic,
handling error translation and providing backwards-compatible dict responses.
"""

import time
from typing import Any, cast

from auth0.management import Auth0

from ..utils.logging_utils import get_logger
from .auth0_client import Auth0ClientManager
from .config import API_RATE_LIMIT
from .exceptions import UserOperationError, wrap_sdk_exception

# Module logger
logger = get_logger(__name__)


class SDKUserOperations:
    """Wrapper for SDK user operations with error handling."""

    def __init__(self, client: Auth0) -> None:
        """Initialize with an Auth0 management client.

        Args:
            client: Initialized Auth0 management client
        """
        self.client = client

    def get_user(self, user_id: str) -> dict[str, Any] | None:
        """Get user details by ID.

        Args:
            user_id: Auth0 user ID

        Returns:
            User details dictionary or None if not found
        """
        try:
            # SDK returns dict directly
            user = self.client.users.get(user_id)
            time.sleep(API_RATE_LIMIT)
            return cast(dict[str, Any], user)
        except Exception as e:
            wrapped = wrap_sdk_exception(e, f"get_user:{user_id}")
            logger.error(
                f"Failed to get user {user_id}: {wrapped}",
                extra={"user_id": user_id, "error": str(wrapped)},
            )
            return None

    def delete_user(self, user_id: str) -> bool:
        """Delete a user.

        Args:
            user_id: Auth0 user ID

        Returns:
            True if successful, False otherwise

        Raises:
            UserOperationError: If deletion fails
        """
        try:
            self.client.users.delete(user_id)
            time.sleep(API_RATE_LIMIT)
            logger.info(f"Successfully deleted user {user_id}")
            return True
        except Exception as e:
            wrapped = wrap_sdk_exception(e, f"delete_user:{user_id}")
            logger.error(
                f"Failed to delete user {user_id}: {wrapped}",
                extra={"user_id": user_id, "error": str(wrapped)},
            )
            raise UserOperationError(
                message=f"Failed to delete user: {wrapped}",
                user_id=user_id,
                operation="delete",
            ) from e

    def update_user(self, user_id: str, body: dict[str, Any]) -> dict[str, Any] | None:
        """Update a user.

        Args:
            user_id: Auth0 user ID
            body: Update payload

        Returns:
            Updated user details or None if failed
        """
        try:
            user = self.client.users.update(user_id, body)
            time.sleep(API_RATE_LIMIT)
            return cast(dict[str, Any], user)
        except Exception as e:
            wrapped = wrap_sdk_exception(e, f"update_user:{user_id}")
            logger.error(
                f"Failed to update user {user_id}: {wrapped}",
                extra={"user_id": user_id, "error": str(wrapped)},
            )
            return None

    def block_user(self, user_id: str) -> bool:
        """Block a user.

        Args:
            user_id: Auth0 user ID

        Returns:
            True if successful, False otherwise
        """
        try:
            self.client.users.update(user_id, {"blocked": True})
            time.sleep(API_RATE_LIMIT)
            logger.info(f"Successfully blocked user {user_id}")
            return True
        except Exception as e:
            wrapped = wrap_sdk_exception(e, f"block_user:{user_id}")
            logger.error(
                f"Failed to block user {user_id}: {wrapped}",
                extra={"user_id": user_id, "error": str(wrapped)},
            )
            return False

    def search_users_by_email(self, email: str) -> list[dict[str, Any]]:
        """Search for users by email address.

        Args:
            email: Email address to search for

        Returns:
            List of user dictionaries
        """
        try:
            # Use users_by_email endpoint via SDK
            users = self.client.users_by_email.search_users_by_email(email)
            time.sleep(API_RATE_LIMIT)
            return cast(list[dict[str, Any]], users if users else [])
        except Exception as e:
            wrapped = wrap_sdk_exception(e, f"search_by_email:{email}")
            logger.error(
                f"Failed to search users by email {email}: {wrapped}",
                extra={"email": email, "error": str(wrapped)},
            )
            return []

    def search_users(
        self, query: str, per_page: int = 50, page: int = 0
    ) -> list[dict[str, Any]]:
        """Search users using Lucene query syntax.

        Args:
            query: Lucene query string
            per_page: Results per page
            page: Page number

        Returns:
            List of user dictionaries
        """
        try:
            response = self.client.users.list(
                q=query,
                search_engine="v3",
                per_page=per_page,
                page=page,
            )
            time.sleep(API_RATE_LIMIT)

            # SDK may return dict with 'users' key or list directly
            if isinstance(response, dict) and "users" in response:
                return cast(list[dict[str, Any]], response["users"])
            elif isinstance(response, list):
                return cast(list[dict[str, Any]], response)
            return []
        except Exception as e:
            wrapped = wrap_sdk_exception(e, f"search_users:{query}")
            logger.error(
                f"Failed to search users with query '{query}': {wrapped}",
                extra={"query": query, "error": str(wrapped)},
            )
            return []

    def delete_user_identity(
        self, user_id: str, provider: str, identity_id: str
    ) -> bool:
        """Unlink/delete a user identity.

        Args:
            user_id: Auth0 user ID
            provider: Identity provider (e.g., "google-oauth2")
            identity_id: Identity ID to unlink

        Returns:
            True if successful, False otherwise
        """
        try:
            # SDK method: users.delete_multifactor() or direct REST call
            # The SDK doesn't have a direct delete_user_identity method on the users resource
            # We need to use the unlink method
            self.client.users.unlink_user_identity(user_id, provider, identity_id)
            time.sleep(API_RATE_LIMIT)
            logger.info(
                f"Successfully unlinked identity {provider}:{identity_id} from user {user_id}"
            )
            return True
        except Exception as e:
            wrapped = wrap_sdk_exception(e, f"unlink_identity:{user_id}")
            logger.error(
                f"Failed to unlink identity for user {user_id}: {wrapped}",
                extra={"user_id": user_id, "provider": provider, "error": str(wrapped)},
            )
            return False


class SDKGrantOperations:
    """Wrapper for SDK grant operations."""

    def __init__(self, client: Auth0) -> None:
        """Initialize with an Auth0 management client.

        Args:
            client: Initialized Auth0 management client
        """
        self.client = client

    def delete_grants_by_user(self, user_id: str) -> bool:
        """Delete all grants for a user.

        Args:
            user_id: Auth0 user ID

        Returns:
            True if successful, False otherwise

        Raises:
            Exception: Re-raises wrapped exceptions for proper error propagation
        """
        try:
            # Use SDK's all() method with user_id in extra_params
            grants_response = self.client.grants.all(extra_params={"user_id": user_id})

            # The SDK returns a dict with 'grants' key or potentially a list
            grants = []
            if isinstance(grants_response, dict):
                grants = grants_response.get("grants", [])
            elif isinstance(grants_response, list):
                grants = grants_response

            # Delete each grant individually
            for grant in grants:
                grant_id = grant.get("id")
                if grant_id:
                    self.client.grants.delete(id=grant_id)
                    time.sleep(API_RATE_LIMIT)

            logger.info(
                f"Successfully revoked {len(grants)} grant(s) for user {user_id}"
            )
            return True
        except Exception as e:
            wrapped = wrap_sdk_exception(e, f"delete_grants:{user_id}")
            logger.error(
                f"Failed to revoke grants for user {user_id}: {wrapped}",
                extra={"user_id": user_id, "error": str(wrapped)},
            )
            # Re-raise to propagate the error instead of silently returning False
            raise wrapped from e


def get_sdk_operations(
    env: str = "dev",
) -> tuple[SDKUserOperations, SDKGrantOperations]:
    """Get SDK operation wrappers for the specified environment.

    Args:
        env: Environment ('dev' or 'prod')

    Returns:
        Tuple of (user_ops, grant_ops)
    """
    manager = Auth0ClientManager(env)
    client = manager.get_client()

    user_ops = SDKUserOperations(client)
    grant_ops = SDKGrantOperations(client)

    return user_ops, grant_ops
