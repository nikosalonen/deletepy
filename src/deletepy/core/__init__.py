"""Core functionality for Auth0 User Management Tool."""

from deletepy.core.auth import doctor, get_access_token
from deletepy.core.config import (
    check_env_file,
    get_base_url,
    get_env_config,
    validate_env_var,
)
from deletepy.core.exceptions import AuthConfigError
from deletepy.core.sdk_operations import (
    SDKGrantOperations,
    SDKUserOperations,
    get_sdk_operations,
    get_sdk_ops_from_base_url,
)

__all__ = [
    "get_access_token",
    "doctor",
    "AuthConfigError",
    "get_env_config",
    "get_base_url",
    "check_env_file",
    "validate_env_var",
    "get_sdk_operations",
    "get_sdk_ops_from_base_url",
    "SDKUserOperations",
    "SDKGrantOperations",
]
