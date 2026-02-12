from unittest.mock import MagicMock, patch

import pytest

from src.deletepy.core.auth0_client import Auth0Client


@pytest.fixture
def mock_response():
    """Create a mock response object for requests."""
    response = MagicMock()
    response.status_code = 200  # Set default status code
    response.raise_for_status = MagicMock()
    response.json = MagicMock()
    return response


@pytest.fixture
def mock_client():
    """Create a mock Auth0Client for testing.

    Returns a MagicMock with spec=Auth0Client and pre-configured context attributes.
    Individual tests should configure return values on specific methods.
    """
    client = MagicMock(spec=Auth0Client)
    client.context.token = "test_token"
    client.context.base_url = "https://test.auth0.com"
    client.context.env = "dev"
    return client


@pytest.fixture
def mock_requests(request):
    """Create a mock requests module.

    This fixture patches the `requests` module for test files that still
    use direct HTTP calls (e.g., auth.py for token acquisition).
    """
    # Extract the test file name and map to new module structure
    test_file = request.module.__file__
    test_name = test_file.split("test_")[-1].replace(".py", "")

    # Map test files to their corresponding module paths
    module_mapping = {
        "auth": ["src.deletepy.core.auth"],
        "utils": ["src.deletepy.utils.file_utils"],
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
