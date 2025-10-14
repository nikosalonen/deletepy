from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_response():
    """Create a mock response object for requests."""
    response = MagicMock()
    response.status_code = 200  # Set default status code
    response.raise_for_status = MagicMock()
    response.json = MagicMock()
    return response


@pytest.fixture
def mock_auth0_client():
    """Create a mock Auth0 management client."""
    client = MagicMock()

    # Mock users resource
    client.users = MagicMock()
    client.users.get = MagicMock(
        return_value={"user_id": "test_user_id", "email": "test@example.com"}
    )
    client.users.delete = MagicMock()
    client.users.update = MagicMock(
        return_value={"user_id": "test_user_id", "blocked": True}
    )
    client.users.list = MagicMock(return_value={"users": [], "total": 0})
    client.users.unlink_user_identity = MagicMock()

    # Mock users_by_email resource
    client.users_by_email = MagicMock()
    client.users_by_email.search_users_by_email = MagicMock(return_value=[])

    # Mock grants resource
    client.grants = MagicMock()
    client.grants.list = MagicMock(return_value={"grants": []})
    client.grants.delete = MagicMock()

    return client


@pytest.fixture
def mock_get_token():
    """Create a mock GetToken instance."""
    get_token = MagicMock()
    get_token.client_credentials = MagicMock(
        return_value={"access_token": "test_token", "expires_in": 86400}
    )
    return get_token


@pytest.fixture
def mock_auth0_client_manager(mock_auth0_client, mock_get_token):
    """Create a mock Auth0ClientManager."""
    manager = MagicMock()
    manager.get_client = MagicMock(return_value=mock_auth0_client)
    manager.get_token = MagicMock(return_value="test_token")
    return manager


@pytest.fixture
def mock_requests(request):
    """Create a mock requests module.

    This fixture automatically determines which module(s) to patch based on the test module name.
    For example, test_auth.py will patch src.deletepy.core.auth.requests.
    For test_user_operations.py, patches multiple modules since functions are spread across them.
    """
    # Extract the test file name and map to new module structure
    test_file = request.module.__file__
    test_name = test_file.split("test_")[-1].replace(".py", "")

    # Map test files to their corresponding module paths
    # Some test files need multiple modules patched
    module_mapping = {
        "auth": ["src.deletepy.core.auth"],
        "user_operations": [
            "src.deletepy.operations.user_ops",
            "src.deletepy.operations.batch_ops",
            "src.deletepy.utils.request_utils",
        ],
        "utils": ["src.deletepy.utils.file_utils"],
        "cleanup_csv": ["src.deletepy.utils.csv_utils"],
        "email_domain_checker": ["src.deletepy.operations.domain_ops"],
    }

    module_paths = module_mapping.get(test_name, [f"src.deletepy.{test_name}"])

    # If only one module, patch it directly
    if len(module_paths) == 1:
        with patch(f"{module_paths[0]}.requests") as mock:
            # Ensure exceptions module is properly mocked
            import requests

            mock.exceptions = requests.exceptions
            yield mock
    else:
        # Multiple modules - patch all of them with the same mock
        patches = []
        try:
            mock = MagicMock()
            # Ensure exceptions module is properly mocked
            import requests

            mock.exceptions = requests.exceptions
            for module_path in module_paths:
                patcher = patch(f"{module_path}.requests", mock)
                patches.append(patcher)
                patcher.start()
            yield mock
        finally:
            for patcher in patches:
                patcher.stop()
