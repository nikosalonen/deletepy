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
