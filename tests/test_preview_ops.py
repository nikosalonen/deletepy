"""Tests for dry-run preview operations."""

from unittest.mock import patch

from src.deletepy.operations.preview_ops import (
    PreviewResult,
    _get_user_connection,
    _resolve_user_identifier,
    _should_skip_user,
    preview_social_unlink_operations,
    preview_user_operations,
)


class TestPreviewResult:
    """Test PreviewResult dataclass."""

    def test_empty_result(self):
        """Test empty preview result."""
        result = PreviewResult(operation="delete", total_users=0)
        assert result.success_count == 0
        assert result.skip_count == 0
        assert result.success_rate == 0.0

    def test_success_rate_calculation(self):
        """Test success rate calculation."""
        result = PreviewResult(operation="delete", total_users=10)
        result.valid_users = [{"user_id": f"user_{i}"} for i in range(7)]
        result.invalid_user_ids = ["invalid1", "invalid2"]
        result.not_found_users = ["notfound1"]

        assert result.success_count == 7
        assert result.skip_count == 3
        assert result.success_rate == 70.0

    def test_all_categories_count(self):
        """Test that all skip categories are counted."""
        result = PreviewResult(operation="block", total_users=10)
        result.valid_users = [{"user_id": "valid1"}]
        result.invalid_user_ids = ["invalid1"]
        result.not_found_users = ["notfound1"]
        result.multiple_users = {"email1": ["user1", "user2"]}
        result.blocked_users = ["blocked1"]
        result.errors = [{"identifier": "error1", "error": "test"}]

        assert result.success_count == 1
        assert result.skip_count == 5


class TestPreviewUserOperations:
    """Test preview_user_operations function."""

    @patch("src.deletepy.operations.preview_ops.get_user_details")
    @patch("src.deletepy.operations.preview_ops.get_user_id_from_email")
    @patch("src.deletepy.operations.preview_ops.time.sleep")
    @patch("src.deletepy.operations.preview_ops.show_progress")
    @patch("src.deletepy.operations.preview_ops.print")
    def test_preview_with_valid_user_ids(
        self, mock_print, mock_progress, mock_sleep, mock_get_email, mock_get_details
    ):
        """Test preview with valid Auth0 user IDs."""
        # Setup mocks
        mock_get_details.return_value = {
            "user_id": "auth0|123456789",
            "email": "test@example.com",
            "blocked": False,
            "identities": [{"connection": "auth0"}],
        }

        user_ids = ["auth0|123456789", "auth0|987654321"]

        result = preview_user_operations(
            user_ids, "token", "https://test.auth0.com", "delete", show_details=False
        )

        assert result.operation == "delete"
        assert result.total_users == 2
        assert result.success_count == 2
        assert result.skip_count == 0
        assert len(result.valid_users) == 2

    @patch("src.deletepy.operations.preview_ops.get_user_details")
    @patch("src.deletepy.operations.preview_ops.get_user_id_from_email")
    @patch("src.deletepy.operations.preview_ops.time.sleep")
    @patch("src.deletepy.operations.preview_ops.show_progress")
    @patch("src.deletepy.operations.preview_ops.print")
    def test_preview_with_emails(
        self, mock_print, mock_progress, mock_sleep, mock_get_email, mock_get_details
    ):
        """Test preview with email addresses."""
        # Setup mocks
        mock_get_email.return_value = ["auth0|123456789"]
        mock_get_details.return_value = {
            "user_id": "auth0|123456789",
            "email": "test@example.com",
            "blocked": False,
            "identities": [{"connection": "auth0"}],
        }

        user_ids = ["test@example.com"]

        result = preview_user_operations(
            user_ids, "token", "https://test.auth0.com", "delete", show_details=False
        )

        assert result.success_count == 1
        assert len(result.valid_users) == 1
        assert result.valid_users[0]["email"] == "test@example.com"

    @patch("src.deletepy.operations.preview_ops.get_user_details")
    @patch("src.deletepy.operations.preview_ops.get_user_id_from_email")
    @patch("src.deletepy.operations.preview_ops.time.sleep")
    @patch("src.deletepy.operations.preview_ops.show_progress")
    @patch("src.deletepy.operations.preview_ops.print")
    def test_preview_with_invalid_user_ids(
        self, mock_print, mock_progress, mock_sleep, mock_get_email, mock_get_details
    ):
        """Test preview with invalid user IDs."""
        user_ids = ["invalid-id", "another-invalid"]

        result = preview_user_operations(
            user_ids, "token", "https://test.auth0.com", "delete", show_details=False
        )

        assert result.success_count == 0
        assert result.skip_count == 2
        assert len(result.invalid_user_ids) == 2

    @patch("src.deletepy.operations.preview_ops.get_user_details")
    @patch("src.deletepy.operations.preview_ops.get_user_id_from_email")
    @patch("src.deletepy.operations.preview_ops.time.sleep")
    @patch("src.deletepy.operations.preview_ops.show_progress")
    @patch("src.deletepy.operations.preview_ops.print")
    def test_preview_with_not_found_emails(
        self, mock_print, mock_progress, mock_sleep, mock_get_email, mock_get_details
    ):
        """Test preview with emails that don't exist."""
        mock_get_email.return_value = []

        user_ids = ["notfound@example.com"]

        result = preview_user_operations(
            user_ids, "token", "https://test.auth0.com", "delete", show_details=False
        )

        assert result.success_count == 0
        assert len(result.not_found_users) == 1
        assert "notfound@example.com" in result.not_found_users

    @patch("src.deletepy.operations.preview_ops.get_user_details")
    @patch("src.deletepy.operations.preview_ops.get_user_id_from_email")
    @patch("src.deletepy.operations.preview_ops.time.sleep")
    @patch("src.deletepy.operations.preview_ops.show_progress")
    @patch("src.deletepy.operations.preview_ops.print")
    def test_preview_with_multiple_users(
        self, mock_print, mock_progress, mock_sleep, mock_get_email, mock_get_details
    ):
        """Test preview with email that has multiple users."""
        mock_get_email.return_value = ["auth0|123456789", "google-oauth2|987654321"]

        user_ids = ["shared@example.com"]

        result = preview_user_operations(
            user_ids, "token", "https://test.auth0.com", "delete", show_details=False
        )

        assert result.success_count == 0
        assert len(result.multiple_users) == 1
        assert "shared@example.com" in result.multiple_users

    @patch("src.deletepy.operations.preview_ops.get_user_details")
    @patch("src.deletepy.operations.preview_ops.get_user_id_from_email")
    @patch("src.deletepy.operations.preview_ops.time.sleep")
    @patch("src.deletepy.operations.preview_ops.show_progress")
    @patch("src.deletepy.operations.preview_ops.print")
    def test_preview_block_operation_with_blocked_user(
        self, mock_print, mock_progress, mock_sleep, mock_get_email, mock_get_details
    ):
        """Test preview block operation with already blocked user."""
        mock_get_details.return_value = {
            "user_id": "auth0|123456789",
            "email": "test@example.com",
            "blocked": True,
            "identities": [{"connection": "auth0"}],
        }

        user_ids = ["auth0|123456789"]

        result = preview_user_operations(
            user_ids, "token", "https://test.auth0.com", "block", show_details=False
        )

        assert result.success_count == 0
        assert len(result.blocked_users) == 1


class TestSocialUnlinkPreview:
    """Test preview_social_unlink_operations function."""

    @patch("src.deletepy.operations.batch_ops._search_batch_social_ids")
    @patch("src.deletepy.operations.batch_ops._categorize_users")
    @patch("src.deletepy.operations.preview_ops.print")
    def test_social_unlink_preview(self, mock_print, mock_categorize, mock_search):
        """Test social unlink preview."""
        # Setup mocks
        mock_search.return_value = (
            [{"user_id": "auth0|123", "email": "test@example.com"}],
            ["not_found_id"],
        )
        mock_categorize.return_value = (
            [
                {
                    "user_id": "auth0|123",
                    "email": "test@example.com",
                    "reason": "Main identity",
                }
            ],
            [],
            [],
        )

        result = preview_social_unlink_operations(
            ["social_id1", "social_id2"],
            "token",
            "https://test.auth0.com",
            show_details=False,
        )

        assert result["total_social_ids"] == 2
        assert result["found_users"] == 1
        assert result["not_found_ids"] == 1
        assert result["users_to_delete"] == 1
        assert result["identities_to_unlink"] == 0
        assert result["auth0_main_protected"] == 0


class TestHelperFunctions:
    """Test helper functions."""

    def test_resolve_user_identifier_valid_user_id(self):
        """Test resolving valid user ID."""
        result = PreviewResult(operation="delete", total_users=1)

        resolved = _resolve_user_identifier(
            "auth0|123456789", "token", "https://test.auth0.com", result
        )

        assert resolved == "auth0|123456789"
        assert len(result.invalid_user_ids) == 0

    def test_resolve_user_identifier_invalid_user_id(self):
        """Test resolving invalid user ID."""
        result = PreviewResult(operation="delete", total_users=1)

        resolved = _resolve_user_identifier(
            "invalid-id", "token", "https://test.auth0.com", result
        )

        assert resolved is None
        assert len(result.invalid_user_ids) == 1

    @patch("src.deletepy.operations.preview_ops.get_user_id_from_email")
    def test_resolve_user_identifier_email_found(self, mock_get_email):
        """Test resolving email to user ID."""
        mock_get_email.return_value = ["auth0|123456789"]
        result = PreviewResult(operation="delete", total_users=1)

        resolved = _resolve_user_identifier(
            "test@example.com", "token", "https://test.auth0.com", result
        )

        assert resolved == "auth0|123456789"
        assert len(result.not_found_users) == 0

    @patch("src.deletepy.operations.preview_ops.get_user_id_from_email")
    def test_resolve_user_identifier_email_not_found(self, mock_get_email):
        """Test resolving email that doesn't exist."""
        mock_get_email.return_value = []
        result = PreviewResult(operation="delete", total_users=1)

        resolved = _resolve_user_identifier(
            "notfound@example.com", "token", "https://test.auth0.com", result
        )

        assert resolved is None
        assert len(result.not_found_users) == 1

    def test_should_skip_user_block_operation(self):
        """Test should skip user for block operation."""
        user_details = {"blocked": True}
        assert _should_skip_user(user_details, "block") is True

        user_details = {"blocked": False}
        assert _should_skip_user(user_details, "block") is False

    def test_should_skip_user_delete_operation(self):
        """Test should skip user for delete operation."""
        user_details = {"blocked": True}
        assert _should_skip_user(user_details, "delete") is False

    def test_get_user_connection(self):
        """Test getting user connection."""
        user_details = {
            "identities": [{"connection": "auth0"}, {"connection": "google-oauth2"}]
        }
        assert _get_user_connection(user_details) == "auth0"

        user_details = {"identities": []}
        assert _get_user_connection(user_details) == "unknown"

        user_details = {}
        assert _get_user_connection(user_details) == "unknown"


class TestIntegration:
    """Integration tests for preview operations."""

    @patch("src.deletepy.operations.preview_ops.get_user_details")
    @patch("src.deletepy.operations.preview_ops.get_user_id_from_email")
    @patch("src.deletepy.operations.preview_ops.time.sleep")
    @patch("src.deletepy.operations.preview_ops.show_progress")
    @patch("src.deletepy.operations.preview_ops.print")
    def test_mixed_input_types(
        self, mock_print, mock_progress, mock_sleep, mock_get_email, mock_get_details
    ):
        """Test preview with mixed input types."""
        # Setup mocks
        mock_get_email.return_value = ["auth0|email_resolved"]
        mock_get_details.side_effect = [
            {
                "user_id": "auth0|123456789",
                "email": "direct@example.com",
                "blocked": False,
                "identities": [{"connection": "auth0"}],
            },
            {
                "user_id": "auth0|email_resolved",
                "email": "resolved@example.com",
                "blocked": False,
                "identities": [{"connection": "auth0"}],
            },
        ]

        user_ids = ["auth0|123456789", "resolved@example.com", "invalid-id"]

        result = preview_user_operations(
            user_ids, "token", "https://test.auth0.com", "delete", show_details=False
        )

        assert result.total_users == 3
        assert result.success_count == 2
        assert result.skip_count == 1
        assert len(result.valid_users) == 2
        assert len(result.invalid_user_ids) == 1
