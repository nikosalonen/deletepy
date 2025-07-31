"""Tests for CLI functionality."""

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import CliRunner
from deletepy.cli.commands import OperationHandler
from deletepy.cli.main import cli


class TestCLIMain:
    """Test main CLI functionality."""

    def test_cli_help(self):
        """Test CLI help output."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])

        assert result.exit_code == 0
        assert "DeletePy - Auth0 User Management Tool" in result.output
        assert "doctor" in result.output
        assert "users" in result.output

    def test_cli_no_command(self):
        """Test CLI with no command shows help."""
        runner = CliRunner()
        result = runner.invoke(cli, [])

        assert result.exit_code == 0
        assert "DeletePy - Auth0 User Management Tool" in result.output

    @patch("deletepy.cli.main.OperationHandler")
    def test_doctor_command(self, mock_handler_class):
        """Test doctor command."""
        mock_handler = MagicMock()
        mock_handler.handle_doctor.return_value = True
        mock_handler_class.return_value = mock_handler

        runner = CliRunner()
        result = runner.invoke(cli, ["doctor", "dev"])

        assert result.exit_code == 0
        mock_handler.handle_doctor.assert_called_once_with("dev", False)

    @patch("deletepy.cli.main.OperationHandler")
    def test_doctor_command_with_api_test(self, mock_handler_class):
        """Test doctor command with API test."""
        mock_handler = MagicMock()
        mock_handler.handle_doctor.return_value = True
        mock_handler_class.return_value = mock_handler

        runner = CliRunner()
        result = runner.invoke(cli, ["doctor", "dev", "--test-api"])

        assert result.exit_code == 0
        mock_handler.handle_doctor.assert_called_once_with("dev", True)

    def test_users_subcommand_help(self):
        """Test users subcommand help."""
        runner = CliRunner()
        result = runner.invoke(cli, ["users", "--help"])

        assert result.exit_code == 0
        assert "User management operations" in result.output
        assert "block" in result.output
        assert "delete" in result.output
        assert "revoke-grants-only" in result.output

    @patch("deletepy.cli.main.OperationHandler")
    def test_check_unblocked_command(self, mock_handler_class):
        """Test check-unblocked command."""
        mock_handler = MagicMock()
        mock_handler_class.return_value = mock_handler

        # Create temporary file
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as temp:
            temp.write("user1\nuser2\n")
            temp_path = temp.name

        try:
            runner = CliRunner()
            result = runner.invoke(cli, ["check-unblocked", temp_path, "dev"])

            assert result.exit_code == 0
            mock_handler.handle_check_unblocked.assert_called_once()
            args = mock_handler.handle_check_unblocked.call_args[0]
            assert isinstance(args[0], Path)
            assert args[1] == "dev"
        finally:
            os.unlink(temp_path)

    @patch("deletepy.cli.main.OperationHandler")
    def test_export_last_login_command(self, mock_handler_class):
        """Test export-last-login command."""
        mock_handler = MagicMock()
        mock_handler_class.return_value = mock_handler

        # Create temporary file
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as temp:
            temp.write("user1@example.com\nuser2@example.com\n")
            temp_path = temp.name

        try:
            runner = CliRunner()
            result = runner.invoke(
                cli, ["export-last-login", temp_path, "dev", "--connection", "auth0"]
            )

            assert result.exit_code == 0
            mock_handler.handle_export_last_login.assert_called_once()
            args = mock_handler.handle_export_last_login.call_args[0]
            assert isinstance(args[0], Path)
            assert args[1] == "dev"
            assert args[2] == "auth0"  # connection parameter
        finally:
            os.unlink(temp_path)

    @patch("deletepy.cli.main.OperationHandler")
    def test_users_block_command(self, mock_handler_class):
        """Test users block command."""
        mock_handler = MagicMock()
        mock_handler_class.return_value = mock_handler

        # Create temporary file
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as temp:
            temp.write("auth0|123\nauth0|456\n")
            temp_path = temp.name

        try:
            runner = CliRunner()
            result = runner.invoke(cli, ["users", "block", temp_path, "dev"])

            assert result.exit_code == 0
            mock_handler.handle_user_operations.assert_called_once()
            args = mock_handler.handle_user_operations.call_args[0]
            assert isinstance(args[0], Path)
            assert args[1] == "dev"
            assert args[2] == "block"
        finally:
            os.unlink(temp_path)


class TestOperationHandler:
    """Test OperationHandler class."""

    def test_operation_handler_init(self):
        """Test OperationHandler initialization."""
        handler = OperationHandler()
        assert handler is not None

    @patch("deletepy.cli.commands.get_access_token")
    @patch("deletepy.cli.commands.get_base_url")
    def test_setup_auth_and_files(self, mock_get_base_url, mock_get_token):
        """Test _setup_auth_and_files helper method."""
        mock_get_base_url.return_value = "https://test.auth0.com"
        mock_get_token.return_value = "test_token"

        # Create temporary file
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as temp:
            temp.write("user1\nuser2\nuser3\n")
            temp_path = Path(temp.name)

        try:
            handler = OperationHandler()
            base_url, token, user_ids = handler._setup_auth_and_files(temp_path, "dev")

            assert base_url == "https://test.auth0.com"
            assert token == "test_token"
            assert len(user_ids) == 3
            assert user_ids == ["user1", "user2", "user3"]
        finally:
            os.unlink(temp_path)

    def test_get_operation_display_name(self):
        """Test _get_operation_display_name helper method."""
        handler = OperationHandler()

        assert handler._get_operation_display_name("block") == "Blocking users"
        assert handler._get_operation_display_name("delete") == "Deleting users"
        assert (
            handler._get_operation_display_name("revoke-grants-only")
            == "Revoking grants and sessions"
        )
        assert handler._get_operation_display_name("unknown") == "Processing users"

    @patch("deletepy.utils.display_utils.confirm_production_operation")
    def test_confirm_production_operation(self, mock_confirm):
        """Test _confirm_production_operation helper method."""
        mock_confirm.return_value = True

        handler = OperationHandler()
        result = handler._confirm_production_operation("delete", 10)

        assert result is True
        mock_confirm.assert_called_once_with("delete", 10)

    @patch("deletepy.cli.commands.get_user_email")
    def test_fetch_user_emails(self, mock_get_email):
        """Test _fetch_user_emails helper method."""
        mock_get_email.side_effect = [
            "user1@example.com",
            "user2@example.com",
            None,  # User without email
        ]

        handler = OperationHandler()
        emails = handler._fetch_user_emails(
            ["auth0|123", "auth0|456", "auth0|789"],
            "test_token",
            "https://test.auth0.com",
        )

        assert len(emails) == 2
        assert "user1@example.com" in emails
        assert "user2@example.com" in emails

    def test_calculate_export_parameters(self):
        """Test _calculate_export_parameters helper method."""
        handler = OperationHandler()

        with (
            patch("deletepy.utils.request_utils.get_optimal_batch_size") as mock_batch,
            patch(
                "deletepy.utils.request_utils.get_estimated_processing_time"
            ) as mock_time,
        ):
            mock_batch.return_value = 50
            mock_time.return_value = 10.5

            batch_size, estimated_time = handler._calculate_export_parameters(100)

            assert batch_size == 50
            assert estimated_time == 10.5
            mock_batch.assert_called_once_with(100)
            mock_time.assert_called_once_with(100, 50)

    @patch("deletepy.utils.validators.InputValidator.validate_email_comprehensive")
    @patch("deletepy.cli.commands.get_user_id_from_email")
    def test_resolve_user_identifier_email(self, mock_get_user_id, mock_validate_email):
        """Test _resolve_user_identifier with email input."""
        from deletepy.utils.validators import ValidationResult

        mock_validate_email.return_value = ValidationResult(is_valid=True)
        mock_get_user_id.return_value = ["auth0|123"]

        handler = OperationHandler()
        multiple_users = {}
        not_found_users = []
        invalid_user_ids = []

        result = handler._resolve_user_identifier(
            "user@example.com",
            "test_token",
            "https://test.auth0.com",
            multiple_users,
            not_found_users,
            invalid_user_ids,
        )

        assert result == "auth0|123"
        assert len(multiple_users) == 0
        assert len(not_found_users) == 0
        assert len(invalid_user_ids) == 0

    @patch("deletepy.utils.validators.InputValidator.validate_email_comprehensive")
    def test_resolve_user_identifier_invalid_email(self, mock_validate_email):
        """Test _resolve_user_identifier with invalid email input."""
        from deletepy.utils.validators import ValidationResult

        mock_validate_email.return_value = ValidationResult(
            is_valid=False, error_message="Invalid email format"
        )

        handler = OperationHandler()
        multiple_users = {}
        not_found_users = []
        invalid_user_ids = []

        result = handler._resolve_user_identifier(
            "invalid@email",
            "test_token",
            "https://test.auth0.com",
            multiple_users,
            not_found_users,
            invalid_user_ids,
        )

        assert result is None
        assert len(invalid_user_ids) == 1
        assert "invalid@email" in invalid_user_ids[0]
        assert "Invalid email format" in invalid_user_ids[0]

    @patch("deletepy.utils.validators.InputValidator.validate_email_comprehensive")
    @patch("deletepy.cli.commands.get_user_id_from_email")
    def test_resolve_user_identifier_multiple_users(
        self, mock_get_user_id, mock_validate_email
    ):
        """Test _resolve_user_identifier with email that has multiple users."""
        from deletepy.utils.validators import ValidationResult

        mock_validate_email.return_value = ValidationResult(is_valid=True)
        mock_get_user_id.return_value = ["auth0|123", "google-oauth2|456"]

        handler = OperationHandler()
        multiple_users = {}
        not_found_users = []
        invalid_user_ids = []

        result = handler._resolve_user_identifier(
            "user@example.com",
            "test_token",
            "https://test.auth0.com",
            multiple_users,
            not_found_users,
            invalid_user_ids,
        )

        assert result is None
        assert "user@example.com" in multiple_users
        assert multiple_users["user@example.com"] == ["auth0|123", "google-oauth2|456"]

    @patch("deletepy.utils.validators.InputValidator.validate_auth0_user_id_enhanced")
    def test_resolve_user_identifier_auth0_id(self, mock_validate_user_id):
        """Test _resolve_user_identifier with Auth0 user ID."""
        from deletepy.utils.validators import ValidationResult

        mock_validate_user_id.return_value = ValidationResult(is_valid=True)

        handler = OperationHandler()
        multiple_users = {}
        not_found_users = []
        invalid_user_ids = []

        result = handler._resolve_user_identifier(
            "auth0|123456",
            "test_token",
            "https://test.auth0.com",
            multiple_users,
            not_found_users,
            invalid_user_ids,
        )

        assert result == "auth0|123456"
        mock_validate_user_id.assert_called_once_with("auth0|123456")

    @patch("deletepy.utils.validators.InputValidator.validate_auth0_user_id_enhanced")
    def test_resolve_user_identifier_invalid_id(self, mock_validate_user_id):
        """Test _resolve_user_identifier with invalid user ID."""
        from deletepy.utils.validators import ValidationResult

        mock_validate_user_id.return_value = ValidationResult(
            is_valid=False, error_message="Invalid format"
        )

        handler = OperationHandler()
        multiple_users = {}
        not_found_users = []
        invalid_user_ids = []

        result = handler._resolve_user_identifier(
            "invalid_id",
            "test_token",
            "https://test.auth0.com",
            multiple_users,
            not_found_users,
            invalid_user_ids,
        )

        assert result is None
        assert len(invalid_user_ids) == 1
        assert "invalid_id" in invalid_user_ids[0]
        assert "Invalid format" in invalid_user_ids[0]

    @patch("deletepy.cli.commands.block_user")
    def test_execute_user_operation_block(self, mock_block):
        """Test _execute_user_operation for block operation."""
        handler = OperationHandler()

        handler._execute_user_operation(
            "block", "auth0|123", "test_token", "https://test.auth0.com"
        )

        mock_block.assert_called_once_with(
            "auth0|123", "test_token", "https://test.auth0.com"
        )

    @patch("deletepy.cli.commands.delete_user")
    def test_execute_user_operation_delete(self, mock_delete):
        """Test _execute_user_operation for delete operation."""
        handler = OperationHandler()

        handler._execute_user_operation(
            "delete", "auth0|123", "test_token", "https://test.auth0.com"
        )

        mock_delete.assert_called_once_with(
            "auth0|123", "test_token", "https://test.auth0.com"
        )

    @patch("deletepy.operations.user_ops.revoke_user_sessions")
    @patch("deletepy.operations.user_ops.revoke_user_grants")
    def test_execute_user_operation_revoke_grants(
        self, mock_revoke_grants, mock_revoke_sessions
    ):
        """Test _execute_user_operation for revoke-grants-only operation."""
        handler = OperationHandler()

        handler._execute_user_operation(
            "revoke-grants-only", "auth0|123", "test_token", "https://test.auth0.com"
        )

        mock_revoke_sessions.assert_called_once_with(
            "auth0|123", "test_token", "https://test.auth0.com"
        )
        mock_revoke_grants.assert_called_once_with(
            "auth0|123", "test_token", "https://test.auth0.com"
        )


class TestCLIErrorHandling:
    """Test CLI error handling."""

    def test_doctor_command_failure(self):
        """Test doctor command when operation fails."""
        with patch("deletepy.cli.main.OperationHandler") as mock_handler_class:
            mock_handler = MagicMock()
            mock_handler.handle_doctor.return_value = False
            mock_handler_class.return_value = mock_handler

            runner = CliRunner()
            result = runner.invoke(cli, ["doctor", "dev"])

            assert result.exit_code == 1

    def test_nonexistent_file(self):
        """Test command with nonexistent file."""
        runner = CliRunner()
        result = runner.invoke(cli, ["check-unblocked", "/nonexistent/file.txt", "dev"])

        assert result.exit_code == 2  # Click error for invalid path
        assert "does not exist" in result.output or "Invalid value" in result.output

    def test_invalid_environment(self):
        """Test command with invalid environment."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as temp:
            temp.write("user1\n")
            temp_path = temp.name

        try:
            runner = CliRunner()
            result = runner.invoke(cli, ["check-unblocked", temp_path, "invalid_env"])

            assert result.exit_code == 2  # Click error for invalid choice
            assert "Invalid value" in result.output
        finally:
            os.unlink(temp_path)


class TestCLIIntegration:
    """Integration tests for CLI functionality."""

    @patch("deletepy.core.config.check_env_file")
    @patch("deletepy.core.auth.doctor")
    def test_doctor_integration(self, mock_doctor, mock_check_env):
        """Test doctor command integration."""
        mock_doctor.return_value = {"success": True}

        runner = CliRunner()
        result = runner.invoke(cli, ["doctor", "dev"])

        assert result.exit_code == 0
        mock_check_env.assert_called_once()
        mock_doctor.assert_called_once_with("dev", False)

    @patch("deletepy.cli.commands.get_access_token")
    @patch("deletepy.cli.commands.get_base_url")
    @patch("deletepy.cli.commands.check_unblocked_users_with_checkpoints")
    def test_check_unblocked_integration(
        self, mock_check_unblocked, mock_get_base_url, mock_get_token
    ):
        """Test check-unblocked command integration."""
        mock_get_base_url.return_value = "https://test.auth0.com"
        mock_get_token.return_value = "test_token"
        mock_check_unblocked.return_value = None  # Completed operation

        # Create temporary file
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as temp:
            temp.write("auth0|123\nauth0|456\n")
            temp_path = temp.name

        try:
            runner = CliRunner()
            result = runner.invoke(cli, ["check-unblocked", temp_path, "dev"])

            assert result.exit_code == 0
            mock_check_unblocked.assert_called_once()
            # Verify the checkpoint-enabled function was called with user_ids and config
            call_args = mock_check_unblocked.call_args
            assert call_args[1]["user_ids"] is not None  # Check keyword arguments
            user_ids = call_args[1]["user_ids"]
            assert "auth0|123" in user_ids
            assert "auth0|456" in user_ids
        finally:
            os.unlink(temp_path)
