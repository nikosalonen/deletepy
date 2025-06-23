import pytest
from unittest.mock import MagicMock, patch

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

    This fixture automatically determines which module to patch based on the test module name.
    For example, test_auth.py will patch auth.requests, test_user_operations.py will patch user_operations.requests.
    """
    # Extract the module name from the test file name
    # e.g., test_auth.py -> auth, test_user_operations.py -> user_operations
    test_file = request.module.__file__
    module_name = test_file.split('test_')[-1].replace('.py', '')

    with patch(f'{module_name}.requests') as mock:
        yield mock
