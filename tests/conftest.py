import pytest
from unittest.mock import MagicMock

@pytest.fixture
def mock_response():
    """Create a mock response object for requests."""
    response = MagicMock()
    response.raise_for_status = MagicMock()
    return response

@pytest.fixture
def mock_requests():
    """Create a mock requests module."""
    with pytest.MonkeyPatch.context() as m:
        m.setattr('requests', MagicMock())
        yield m.getattr('requests')
