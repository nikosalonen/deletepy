"""Tests for Auth0 API client."""

import time
from unittest.mock import MagicMock, patch

import pytest
import requests

from src.deletepy.core.auth0_client import (
    APIResponse,
    Auth0Client,
    Auth0Context,
    HttpMethod,
    create_client_from_token,
)


class TestHttpMethod:
    """Tests for HttpMethod enum."""

    def test_http_methods_exist(self):
        """Test all HTTP methods are defined."""
        assert HttpMethod.GET.value == "GET"
        assert HttpMethod.POST.value == "POST"
        assert HttpMethod.PATCH.value == "PATCH"
        assert HttpMethod.DELETE.value == "DELETE"
        assert HttpMethod.PUT.value == "PUT"


class TestAPIResponse:
    """Tests for APIResponse dataclass."""

    def test_success_response(self):
        """Test creating a success response."""
        response = APIResponse(
            success=True,
            status_code=200,
            data={"user_id": "auth0|123"},
        )
        assert response.success is True
        assert response.status_code == 200
        assert response.data == {"user_id": "auth0|123"}
        assert response.error_message is None

    def test_error_response(self):
        """Test creating an error response."""
        response = APIResponse(
            success=False,
            status_code=404,
            error_message="Resource not found",
        )
        assert response.success is False
        assert response.status_code == 404
        assert response.error_message == "Resource not found"
        assert response.data is None

    def test_rate_limit_fields(self):
        """Test rate limit fields in response."""
        response = APIResponse(
            success=True,
            status_code=200,
            rate_limit_remaining=50,
            rate_limit_reset=1234567890,
        )
        assert response.rate_limit_remaining == 50
        assert response.rate_limit_reset == 1234567890


class TestAuth0Context:
    """Tests for Auth0Context dataclass."""

    def test_context_creation(self):
        """Test creating Auth0 context."""
        context = Auth0Context(
            token="test_token",
            base_url="https://test.auth0.com",
            env="dev",
        )
        assert context.token == "test_token"
        assert context.base_url == "https://test.auth0.com"
        assert context.env == "dev"

    def test_context_default_env(self):
        """Test default environment is dev."""
        context = Auth0Context(
            token="test_token",
            base_url="https://test.auth0.com",
        )
        assert context.env == "dev"


class TestAuth0ClientInit:
    """Tests for Auth0Client initialization."""

    def test_client_initialization(self):
        """Test client initialization with default values."""
        context = Auth0Context(
            token="test_token",
            base_url="https://test.auth0.com",
        )
        client = Auth0Client(context)

        assert client.context is context
        assert client.token == "test_token"
        assert client.base_url == "https://test.auth0.com"
        assert client.rate_limit == 0.5  # API_RATE_LIMIT default
        assert client.timeout == 30  # API_TIMEOUT default

    def test_client_custom_rate_limit(self):
        """Test client with custom rate limit."""
        context = Auth0Context(token="test", base_url="https://test.auth0.com")
        client = Auth0Client(context, rate_limit=1.0, timeout=60)

        assert client.rate_limit == 1.0
        assert client.timeout == 60


class TestAuth0ClientHeaders:
    """Tests for header construction."""

    def test_build_headers_basic(self):
        """Test basic header construction."""
        context = Auth0Context(token="test_token", base_url="https://test.auth0.com")
        client = Auth0Client(context)

        headers = client._build_headers()

        assert headers["Authorization"] == "Bearer test_token"
        assert headers["Content-Type"] == "application/json"
        assert headers["User-Agent"] == Auth0Client.USER_AGENT

    def test_build_headers_with_extra(self):
        """Test header construction with extra headers."""
        context = Auth0Context(token="test_token", base_url="https://test.auth0.com")
        client = Auth0Client(context)

        headers = client._build_headers({"X-Custom-Header": "custom_value"})

        assert headers["Authorization"] == "Bearer test_token"
        assert headers["X-Custom-Header"] == "custom_value"


class TestAuth0ClientRateLimitParsing:
    """Tests for rate limit header parsing."""

    def test_parse_rate_limit_headers(self):
        """Test parsing rate limit headers."""
        context = Auth0Context(token="test", base_url="https://test.auth0.com")
        client = Auth0Client(context)

        mock_response = MagicMock()
        mock_response.headers = {
            "X-RateLimit-Remaining": "50",
            "X-RateLimit-Reset": "1234567890",
        }

        remaining, reset_time = client._parse_rate_limit_headers(mock_response)

        assert remaining == 50
        assert reset_time == 1234567890

    def test_parse_rate_limit_headers_missing(self):
        """Test parsing when headers are missing."""
        context = Auth0Context(token="test", base_url="https://test.auth0.com")
        client = Auth0Client(context)

        mock_response = MagicMock()
        mock_response.headers = {}

        remaining, reset_time = client._parse_rate_limit_headers(mock_response)

        assert remaining is None
        assert reset_time is None

    def test_parse_rate_limit_headers_invalid(self):
        """Test parsing with invalid header values."""
        context = Auth0Context(token="test", base_url="https://test.auth0.com")
        client = Auth0Client(context)

        mock_response = MagicMock()
        mock_response.headers = {
            "X-RateLimit-Remaining": "invalid",
            "X-RateLimit-Reset": "also_invalid",
        }

        remaining, reset_time = client._parse_rate_limit_headers(mock_response)

        assert remaining is None
        assert reset_time is None


class TestAuth0ClientResponseHandling:
    """Tests for response handling."""

    def setup_method(self):
        """Set up test fixtures."""
        self.context = Auth0Context(token="test", base_url="https://test.auth0.com")
        self.client = Auth0Client(self.context)

    def test_handle_response_success_with_json(self):
        """Test handling successful response with JSON body."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.text = '{"user_id": "auth0|123"}'
        mock_response.json.return_value = {"user_id": "auth0|123"}

        result = self.client._handle_response(mock_response, "get user")

        assert result.success is True
        assert result.status_code == 200
        assert result.data == {"user_id": "auth0|123"}

    def test_handle_response_success_no_content(self):
        """Test handling 204 No Content response."""
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_response.headers = {}
        mock_response.text = ""

        result = self.client._handle_response(mock_response, "delete user")

        assert result.success is True
        assert result.status_code == 204
        assert result.data is None

    def test_handle_response_rate_limit(self):
        """Test handling 429 rate limit response."""
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.headers = {
            "X-RateLimit-Remaining": "0",
            "X-RateLimit-Reset": "1234567890",
        }

        result = self.client._handle_response(mock_response, "get user")

        assert result.success is False
        assert result.status_code == 429
        assert "Rate limit exceeded" in result.error_message
        assert result.rate_limit_remaining == 0

    def test_handle_response_not_found(self):
        """Test handling 404 not found response."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.headers = {}

        result = self.client._handle_response(mock_response, "get user")

        assert result.success is False
        assert result.status_code == 404
        assert "not found" in result.error_message.lower()

    def test_handle_response_client_error_dict_json(self):
        """Test handling 4xx client error with dict JSON."""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.headers = {}
        mock_response.json.return_value = {"message": "Invalid user ID"}

        result = self.client._handle_response(mock_response, "delete user")

        assert result.success is False
        assert result.status_code == 400
        assert "Invalid user ID" in result.error_message

    def test_handle_response_client_error_non_dict_json(self):
        """Test handling 4xx client error with non-dict JSON (list/string)."""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.headers = {}
        mock_response.json.return_value = ["error1", "error2"]

        result = self.client._handle_response(mock_response, "delete user")

        assert result.success is False
        assert result.status_code == 400
        assert "error1" in result.error_message

    def test_handle_response_client_error_no_json(self):
        """Test handling 4xx client error without JSON body."""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.headers = {}
        mock_response.json.side_effect = ValueError("No JSON")
        mock_response.text = "Bad Request"

        result = self.client._handle_response(mock_response, "delete user")

        assert result.success is False
        assert result.status_code == 400
        assert "Bad Request" in result.error_message

    def test_handle_response_server_error(self):
        """Test handling 5xx server error."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.headers = {}

        result = self.client._handle_response(mock_response, "get user")

        assert result.success is False
        assert result.status_code == 500
        assert "Server error" in result.error_message


class TestAuth0ClientRequest:
    """Tests for the main request method."""

    def setup_method(self):
        """Set up test fixtures."""
        self.context = Auth0Context(token="test", base_url="https://test.auth0.com")
        self.client = Auth0Client(self.context, rate_limit=0.01)  # Fast for tests

    @patch("src.deletepy.core.auth0_client.requests.request")
    @patch("src.deletepy.core.auth0_client.time.sleep")
    def test_request_success(self, mock_sleep, mock_request):
        """Test successful API request."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.text = '{"result": "success"}'
        mock_response.json.return_value = {"result": "success"}
        mock_request.return_value = mock_response

        result = self.client.request(
            HttpMethod.GET,
            "/api/v2/users/123",
            operation_name="get user",
        )

        assert result.success is True
        assert result.data == {"result": "success"}
        mock_request.assert_called_once()

    @patch("src.deletepy.core.auth0_client.requests.request")
    @patch("src.deletepy.core.auth0_client.time.sleep")
    def test_request_with_params(self, mock_sleep, mock_request):
        """Test request with query parameters."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.text = "[]"
        mock_response.json.return_value = []
        mock_request.return_value = mock_response

        self.client.request(
            HttpMethod.GET,
            "/api/v2/users",
            params={"email": "test@example.com"},
        )

        call_args = mock_request.call_args
        assert call_args.kwargs["params"] == {"email": "test@example.com"}

    @patch("src.deletepy.core.auth0_client.requests.request")
    @patch("src.deletepy.core.auth0_client.time.sleep")
    def test_request_with_json_body(self, mock_sleep, mock_request):
        """Test request with JSON body."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.text = "{}"
        mock_response.json.return_value = {}
        mock_request.return_value = mock_response

        self.client.request(
            HttpMethod.PATCH,
            "/api/v2/users/123",
            json_data={"blocked": True},
        )

        call_args = mock_request.call_args
        assert call_args.kwargs["json"] == {"blocked": True}

    @patch("src.deletepy.core.auth0_client.requests.request")
    @patch("src.deletepy.core.auth0_client.time.sleep")
    def test_request_timeout(self, mock_sleep, mock_request):
        """Test request timeout handling."""
        mock_request.side_effect = requests.exceptions.Timeout("Timeout")

        result = self.client.request(
            HttpMethod.GET,
            "/api/v2/users/123",
            operation_name="get user",
        )

        assert result.success is False
        assert result.status_code == 0
        assert "timeout" in result.error_message.lower()

    @patch("src.deletepy.core.auth0_client.requests.request")
    @patch("src.deletepy.core.auth0_client.time.sleep")
    def test_request_connection_error(self, mock_sleep, mock_request):
        """Test request connection error handling."""
        mock_request.side_effect = requests.exceptions.ConnectionError(
            "Connection failed"
        )

        result = self.client.request(
            HttpMethod.GET,
            "/api/v2/users/123",
            operation_name="get user",
        )

        assert result.success is False
        assert result.status_code == 0
        assert "Connection error" in result.error_message

    @patch("src.deletepy.core.auth0_client.requests.request")
    @patch("src.deletepy.core.auth0_client.time.sleep")
    def test_request_generic_error(self, mock_sleep, mock_request):
        """Test generic request exception handling."""
        mock_request.side_effect = requests.exceptions.RequestException("Generic error")

        result = self.client.request(
            HttpMethod.GET,
            "/api/v2/users/123",
            operation_name="get user",
        )

        assert result.success is False
        assert result.status_code == 0
        assert "Generic error" in result.error_message


class TestAuth0ClientConvenienceMethods:
    """Tests for convenience methods."""

    def setup_method(self):
        """Set up test fixtures."""
        self.context = Auth0Context(token="test", base_url="https://test.auth0.com")
        self.client = Auth0Client(self.context, rate_limit=0.01)

    @patch("src.deletepy.core.auth0_client.requests.request")
    @patch("src.deletepy.core.auth0_client.time.sleep")
    def test_get_method(self, mock_sleep, mock_request):
        """Test GET convenience method."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.text = '{"data": []}'
        mock_response.json.return_value = {"data": []}
        mock_request.return_value = mock_response

        self.client.get("/api/v2/users", params={"page": "0"})

        call_args = mock_request.call_args
        assert call_args.kwargs["method"] == "GET"
        assert call_args.kwargs["params"] == {"page": "0"}

    @patch("src.deletepy.core.auth0_client.requests.request")
    @patch("src.deletepy.core.auth0_client.time.sleep")
    def test_post_method(self, mock_sleep, mock_request):
        """Test POST convenience method."""
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.headers = {}
        mock_response.text = '{"id": "123"}'
        mock_response.json.return_value = {"id": "123"}
        mock_request.return_value = mock_response

        self.client.post("/api/v2/users", json_data={"email": "test@example.com"})

        call_args = mock_request.call_args
        assert call_args.kwargs["method"] == "POST"
        assert call_args.kwargs["json"] == {"email": "test@example.com"}

    @patch("src.deletepy.core.auth0_client.requests.request")
    @patch("src.deletepy.core.auth0_client.time.sleep")
    def test_patch_method(self, mock_sleep, mock_request):
        """Test PATCH convenience method."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.text = "{}"
        mock_response.json.return_value = {}
        mock_request.return_value = mock_response

        self.client.patch("/api/v2/users/123", json_data={"blocked": True})

        call_args = mock_request.call_args
        assert call_args.kwargs["method"] == "PATCH"

    @patch("src.deletepy.core.auth0_client.requests.request")
    @patch("src.deletepy.core.auth0_client.time.sleep")
    def test_delete_method(self, mock_sleep, mock_request):
        """Test DELETE convenience method."""
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_response.headers = {}
        mock_response.text = ""
        mock_request.return_value = mock_response

        self.client.delete("/api/v2/users/123")

        call_args = mock_request.call_args
        assert call_args.kwargs["method"] == "DELETE"


class TestAuth0ClientUserOperations:
    """Tests for user-related convenience methods."""

    def setup_method(self):
        """Set up test fixtures."""
        self.context = Auth0Context(token="test", base_url="https://test.auth0.com")
        self.client = Auth0Client(self.context, rate_limit=0.01)

    @patch("src.deletepy.core.auth0_client.requests.request")
    @patch("src.deletepy.core.auth0_client.time.sleep")
    def test_get_user(self, mock_sleep, mock_request):
        """Test get_user method."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.text = '{"user_id": "auth0|123"}'
        mock_response.json.return_value = {"user_id": "auth0|123"}
        mock_request.return_value = mock_response

        result = self.client.get_user("auth0%7C123")

        assert result.success is True
        call_args = mock_request.call_args
        assert "/api/v2/users/auth0%7C123" in call_args.kwargs["url"]

    @patch("src.deletepy.core.auth0_client.requests.request")
    @patch("src.deletepy.core.auth0_client.time.sleep")
    def test_get_users_by_email(self, mock_sleep, mock_request):
        """Test get_users_by_email method."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.text = '[{"user_id": "auth0|123"}]'
        mock_response.json.return_value = [{"user_id": "auth0|123"}]
        mock_request.return_value = mock_response

        result = self.client.get_users_by_email("test@example.com")

        assert result.success is True
        call_args = mock_request.call_args
        assert call_args.kwargs["params"] == {"email": "test@example.com"}

    @patch("src.deletepy.core.auth0_client.requests.request")
    @patch("src.deletepy.core.auth0_client.time.sleep")
    def test_delete_user(self, mock_sleep, mock_request):
        """Test delete_user method."""
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_response.headers = {}
        mock_response.text = ""
        mock_request.return_value = mock_response

        result = self.client.delete_user("auth0%7C123")

        assert result.success is True
        call_args = mock_request.call_args
        assert call_args.kwargs["method"] == "DELETE"

    @patch("src.deletepy.core.auth0_client.requests.request")
    @patch("src.deletepy.core.auth0_client.time.sleep")
    def test_update_user(self, mock_sleep, mock_request):
        """Test update_user method."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.text = '{"blocked": true}'
        mock_response.json.return_value = {"blocked": True}
        mock_request.return_value = mock_response

        result = self.client.update_user("auth0%7C123", {"blocked": True})

        assert result.success is True
        call_args = mock_request.call_args
        assert call_args.kwargs["method"] == "PATCH"
        assert call_args.kwargs["json"] == {"blocked": True}

    @patch("src.deletepy.core.auth0_client.requests.request")
    @patch("src.deletepy.core.auth0_client.time.sleep")
    def test_block_user(self, mock_sleep, mock_request):
        """Test block_user method."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.text = '{"blocked": true}'
        mock_response.json.return_value = {"blocked": True}
        mock_request.return_value = mock_response

        result = self.client.block_user("auth0%7C123")

        assert result.success is True
        call_args = mock_request.call_args
        assert call_args.kwargs["json"] == {"blocked": True}

    @patch("src.deletepy.core.auth0_client.requests.request")
    @patch("src.deletepy.core.auth0_client.time.sleep")
    def test_get_user_sessions(self, mock_sleep, mock_request):
        """Test get_user_sessions method."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.text = "[]"
        mock_response.json.return_value = []
        mock_request.return_value = mock_response

        result = self.client.get_user_sessions("auth0%7C123")

        assert result.success is True
        call_args = mock_request.call_args
        assert "/sessions" in call_args.kwargs["url"]

    @patch("src.deletepy.core.auth0_client.requests.request")
    @patch("src.deletepy.core.auth0_client.time.sleep")
    def test_delete_session(self, mock_sleep, mock_request):
        """Test delete_session method."""
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_response.headers = {}
        mock_response.text = ""
        mock_request.return_value = mock_response

        result = self.client.delete_session("session_123")

        assert result.success is True
        call_args = mock_request.call_args
        assert "/api/v2/sessions/session_123" in call_args.kwargs["url"]

    @patch("src.deletepy.core.auth0_client.requests.request")
    @patch("src.deletepy.core.auth0_client.time.sleep")
    def test_delete_user_grants(self, mock_sleep, mock_request):
        """Test delete_user_grants method."""
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_response.headers = {}
        mock_response.text = ""
        mock_request.return_value = mock_response

        result = self.client.delete_user_grants("auth0%7C123")

        assert result.success is True
        call_args = mock_request.call_args
        assert call_args.kwargs["params"] == {"user_id": "auth0%7C123"}

    @patch("src.deletepy.core.auth0_client.requests.request")
    @patch("src.deletepy.core.auth0_client.time.sleep")
    def test_unlink_identity(self, mock_sleep, mock_request):
        """Test unlink_identity method."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.text = "[]"
        mock_response.json.return_value = []
        mock_request.return_value = mock_response

        result = self.client.unlink_identity(
            "auth0%7C123",
            "google-oauth2",
            "google_user_123",
        )

        assert result.success is True
        call_args = mock_request.call_args
        assert "/identities/google-oauth2/google_user_123" in call_args.kwargs["url"]

    @patch("src.deletepy.core.auth0_client.requests.request")
    @patch("src.deletepy.core.auth0_client.time.sleep")
    def test_search_users(self, mock_sleep, mock_request):
        """Test search_users method."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.text = '{"users": [], "total": 0}'
        mock_response.json.return_value = {"users": [], "total": 0}
        mock_request.return_value = mock_response

        result = self.client.search_users(
            query="email:*@example.com",
            page=1,
            per_page=50,
        )

        assert result.success is True
        call_args = mock_request.call_args
        params = call_args.kwargs["params"]
        assert params["q"] == "email:*@example.com"
        assert params["page"] == "1"
        assert params["per_page"] == "50"
        assert params["search_engine"] == "v3"


class TestCreateClientFromToken:
    """Tests for the factory function."""

    def test_create_client_from_token(self):
        """Test creating client from basic parameters."""
        client = create_client_from_token(
            token="test_token",
            base_url="https://test.auth0.com",
            env="prod",
        )

        assert isinstance(client, Auth0Client)
        assert client.token == "test_token"
        assert client.base_url == "https://test.auth0.com"
        assert client.context.env == "prod"

    def test_create_client_from_token_default_env(self):
        """Test creating client with default environment."""
        client = create_client_from_token(
            token="test_token",
            base_url="https://test.auth0.com",
        )

        assert client.context.env == "dev"


class TestAuth0ClientAdaptiveRateLimit:
    """Tests for adaptive rate limiting behavior."""

    def setup_method(self):
        """Set up test fixtures."""
        self.context = Auth0Context(token="test", base_url="https://test.auth0.com")

    @patch("src.deletepy.core.auth0_client.time.sleep")
    def test_apply_rate_limit_basic(self, mock_sleep):
        """Test basic rate limiting."""
        client = Auth0Client(self.context, rate_limit=0.5)
        client._apply_rate_limit(None)

        mock_sleep.assert_called_once_with(0.5)

    @patch("src.deletepy.core.auth0_client.time.sleep")
    def test_apply_rate_limit_with_low_remaining(self, mock_sleep):
        """Test rate limiting with low remaining quota."""
        client = Auth0Client(self.context, rate_limit=0.5)

        mock_response = MagicMock()
        current_time = int(time.time())
        mock_response.headers = {
            "X-RateLimit-Remaining": "3",
            "X-RateLimit-Reset": str(current_time + 10),
        }

        with patch(
            "src.deletepy.core.auth0_client.time.time", return_value=current_time
        ):
            client._apply_rate_limit(mock_response)

        # Should sleep for at least reset_time - current_time + buffer
        call_args = mock_sleep.call_args[0][0]
        assert call_args >= 10.5  # At least until reset + 0.5 buffer

    @patch("src.deletepy.core.auth0_client.time.sleep")
    def test_apply_rate_limit_with_high_remaining(self, mock_sleep):
        """Test rate limiting with high remaining quota."""
        client = Auth0Client(self.context, rate_limit=0.5)

        mock_response = MagicMock()
        mock_response.headers = {
            "X-RateLimit-Remaining": "100",
            "X-RateLimit-Reset": "1234567890",
        }

        client._apply_rate_limit(mock_response)

        # Should use default rate limit when remaining is high
        mock_sleep.assert_called_once_with(0.5)


if __name__ == "__main__":
    pytest.main([__file__])
