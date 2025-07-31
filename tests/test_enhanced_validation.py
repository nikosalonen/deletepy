"""Tests for enhanced input validation security features."""

import tempfile

import pytest

from src.deletepy.utils.validators import (
    InputValidator,
    SecurityValidator,
    ValidationResult,
)


class TestEmailValidation:
    """Test comprehensive email validation."""

    def test_valid_emails(self):
        """Test valid email addresses."""
        valid_emails = [
            "user@example.com",
            "test.email@domain.org",
            "user123@test-domain.com",
            "a@b.co",
            "user+tag@example.com",
        ]

        for email in valid_emails:
            result = InputValidator.validate_email_comprehensive(email)
            assert result.is_valid, (
                f"Email {email} should be valid: {result.error_message}"
            )

    def test_invalid_emails(self):
        """Test invalid email addresses."""
        invalid_emails = [
            "",
            "not-an-email",
            "@domain.com",
            "user@",
            "user..double@domain.com",
            ".user@domain.com",
            "user.@domain.com",
            "user@domain",
            "user@.domain.com",
            "user@domain..com",
            "user@domain.c",
            "user name@domain.com",  # space
            "user\n@domain.com",  # newline
            "user<script>@domain.com",  # dangerous chars
        ]

        for email in invalid_emails:
            result = InputValidator.validate_email_comprehensive(email)
            assert not result.is_valid, f"Email {email} should be invalid"
            assert result.error_message is not None

    def test_email_length_limits(self):
        """Test email length validation."""
        # Too long email
        long_email = "a" * 250 + "@domain.com"
        result = InputValidator.validate_email_comprehensive(long_email)
        assert not result.is_valid
        assert "too long" in result.error_message.lower()

        # Too short email
        short_email = "a@"
        result = InputValidator.validate_email_comprehensive(short_email)
        assert not result.is_valid
        assert "too short" in result.error_message.lower()

    def test_email_dangerous_characters(self):
        """Test detection of dangerous characters in emails."""
        dangerous_emails = [
            "user<@domain.com",
            "user>@domain.com",
            'user"@domain.com',
            "user'@domain.com",
            "user&@domain.com",
            "user\x00@domain.com",  # null byte
        ]

        for email in dangerous_emails:
            result = InputValidator.validate_email_comprehensive(email)
            assert not result.is_valid
            assert "dangerous character" in result.error_message.lower()

    def test_email_warnings(self):
        """Test email validation warnings."""
        # Email with suspicious patterns
        suspicious_email = "user++test@domain.com"
        result = InputValidator.validate_email_comprehensive(suspicious_email)
        assert result.is_valid  # Still valid but has warnings
        assert len(result.warnings) > 0


class TestAuth0UserIdValidation:
    """Test enhanced Auth0 user ID validation."""

    def test_valid_user_ids(self):
        """Test valid Auth0 user IDs."""
        valid_ids = [
            "auth0|123456789",
            "google-oauth2|123456789",
            "facebook|abc123def",
            "github|user123",
            "email|507f1f77bcf86cd799439011",
        ]

        for user_id in valid_ids:
            result = InputValidator.validate_auth0_user_id_enhanced(user_id)
            assert result.is_valid, (
                f"User ID {user_id} should be valid: {result.error_message}"
            )

    def test_invalid_user_ids(self):
        """Test invalid Auth0 user IDs."""
        invalid_ids = [
            "",
            "no-pipe-separator",
            "|empty-connection",
            "empty-identifier|",
            "auth0|",
            "|123456",
            "auth0||double-pipe",
            "auth0|user|extra-pipe",
            "auth0 |space-before-pipe",
            "auth0| space-after-pipe",
            "auth0|user with spaces",
            "auth0|user\nwith\nnewlines",
            "auth0|user<script>",
        ]

        for user_id in invalid_ids:
            result = InputValidator.validate_auth0_user_id_enhanced(user_id)
            assert not result.is_valid, f"User ID {user_id} should be invalid"
            assert result.error_message is not None

    def test_user_id_length_limits(self):
        """Test user ID length validation."""
        # Too long user ID
        long_id = "auth0|" + "a" * 600
        result = InputValidator.validate_auth0_user_id_enhanced(long_id)
        assert not result.is_valid
        assert "too long" in result.error_message.lower()

        # Too short user ID
        short_id = "a|"
        result = InputValidator.validate_auth0_user_id_enhanced(short_id)
        assert not result.is_valid
        assert "too short" in result.error_message.lower()

    def test_user_id_dangerous_characters(self):
        """Test detection of dangerous characters in user IDs."""
        dangerous_ids = [
            "auth0|user<script>",
            "auth0|user>test",
            'auth0|user"test',
            "auth0|user'test",
            "auth0|user&test",
            "auth0|user\x00test",  # null byte
            "auth0|user test",  # space
        ]

        for user_id in dangerous_ids:
            result = InputValidator.validate_auth0_user_id_enhanced(user_id)
            assert not result.is_valid
            assert "dangerous character" in result.error_message.lower()

    def test_user_id_warnings(self):
        """Test user ID validation warnings."""
        # Unknown connection type
        unknown_connection = "unknown-provider|123456"
        result = InputValidator.validate_auth0_user_id_enhanced(unknown_connection)
        assert result.is_valid  # Still valid but has warnings
        assert len(result.warnings) > 0
        assert "unknown connection type" in result.warnings[0].lower()

    def test_user_id_suggestions(self):
        """Test user ID validation suggestions."""
        # Missing pipe separator
        no_pipe = "auth0123456"
        result = InputValidator.validate_auth0_user_id_enhanced(no_pipe)
        assert not result.is_valid
        assert len(result.suggestions) > 0
        assert "connection|identifier" in result.suggestions[0]


class TestUrlEncodingValidation:
    """Test URL encoding security validation."""

    def test_valid_url_encoding(self):
        """Test valid URL encoded strings."""
        valid_encoded = [
            "user%40example.com",
            "auth0%7C123456",
            "normal-string",
            "string%20with%20spaces",
        ]

        for encoded in valid_encoded:
            result = InputValidator.validate_url_encoding_secure(encoded)
            assert result.is_valid, (
                f"Encoded string {encoded} should be valid: {result.error_message}"
            )

    def test_dangerous_url_encoding(self):
        """Test detection of dangerous URL encoding patterns."""
        dangerous_encoded = [
            "string%00with%00nulls",  # null bytes
            "string%0awith%0anewlines",  # newlines
            "string%3cscript%3e",  # script tags
            "path%2f%2e%2e%2ftraversal",  # path traversal
        ]

        for encoded in dangerous_encoded:
            result = InputValidator.validate_url_encoding_secure(encoded)
            assert not result.is_valid, f"Encoded string {encoded} should be invalid"
            assert "dangerous" in result.error_message.lower()

    def test_double_encoding_detection(self):
        """Test detection of double URL encoding."""
        # Double encoded string
        double_encoded = "string%2520with%2520double%2520encoding"
        result = InputValidator.validate_url_encoding_secure(double_encoded)
        assert result.is_valid  # Still valid but has warnings
        assert len(result.warnings) > 0
        assert "double-encoded" in result.warnings[0].lower()


class TestFilePathValidation:
    """Test secure file path validation."""

    def test_valid_file_paths(self):
        """Test valid file paths."""
        valid_paths = [
            "file.txt",
            "data/file.csv",
            "logs/app.log",
            "./relative/path.json",
        ]

        for path in valid_paths:
            result = InputValidator.validate_file_path_secure(path)
            assert result.is_valid, (
                f"Path {path} should be valid: {result.error_message}"
            )

    def test_path_traversal_attacks(self):
        """Test detection of path traversal attacks."""
        traversal_paths = [
            "../../../etc/passwd",
            "..\\..\\windows\\system32",
            "file%2e%2e%2ftraversal",
            "file%252e%252e%252ftraversal",
            "normal/path/../../../etc/passwd",
        ]

        for path in traversal_paths:
            result = InputValidator.validate_file_path_secure(path)
            assert not result.is_valid, f"Path {path} should be invalid"
            assert "traversal" in result.error_message.lower()

    def test_dangerous_file_characters(self):
        """Test detection of dangerous characters in file paths."""
        dangerous_paths = [
            "file\x00.txt",  # null byte
            "file\n.txt",  # newline
            "file\r.txt",  # carriage return
            "file\t.txt",  # tab
        ]

        for path in dangerous_paths:
            result = InputValidator.validate_file_path_secure(path)
            assert not result.is_valid
            assert "dangerous character" in result.error_message.lower()

    def test_file_path_length_limit(self):
        """Test file path length validation."""
        # Very long path
        long_path = "a/" * 500 + "file.txt"
        result = InputValidator.validate_file_path_secure(long_path)
        assert not result.is_valid
        assert "too long" in result.error_message.lower()

    def test_base_directory_restriction(self):
        """Test base directory restriction."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Valid path within base directory
            valid_path = "subdir/file.txt"
            result = InputValidator.validate_file_path_secure(valid_path, temp_dir)
            assert result.is_valid

            # Invalid path outside base directory (should be caught by traversal detection)
            invalid_path = "../outside/file.txt"
            result = InputValidator.validate_file_path_secure(invalid_path, temp_dir)
            assert not result.is_valid
            # Either traversal detection or base directory check should catch this
            assert (
                "traversal" in result.error_message.lower()
                or "outside base directory" in result.error_message.lower()
            )

    def test_suspicious_file_extensions(self):
        """Test that suspicious file extensions are rejected."""
        suspicious_files = [
            "malware.exe",
            "script.bat",
            "command.cmd",
        ]

        for path in suspicious_files:
            result = InputValidator.validate_file_path_secure(path)
            assert not result.is_valid  # Invalid due to dangerous extension
            assert "dangerous file extension" in result.error_message.lower()


class TestSecurityValidator:
    """Test security-focused validation utilities."""

    def test_checkpoint_path_validation(self):
        """Test checkpoint path validation."""
        # Valid checkpoint paths (without base directory restriction for simple names)
        valid_paths = [
            "checkpoint_123.json",
            "batch_delete_20231201_123456_abcd1234.json",
            "checkpoint.json.backup",
        ]

        for path in valid_paths:
            result = SecurityValidator.validate_checkpoint_path(
                path, None
            )  # No base dir restriction
            assert result.is_valid, (
                f"Checkpoint path {path} should be valid: {result.error_message}"
            )

        # Invalid checkpoint paths
        invalid_paths = [
            "../../../etc/passwd",
            "checkpoint.exe",
            "checkpoint<script>.json",
        ]

        for path in invalid_paths:
            result = SecurityValidator.validate_checkpoint_path(path)
            assert not result.is_valid, f"Checkpoint path {path} should be invalid"

    def test_user_input_sanitization(self):
        """Test user input sanitization."""
        # Test with dangerous input
        dangerous_input = "user\x00input\nwith\rcontrol\tchars"
        sanitized = SecurityValidator.sanitize_user_input(dangerous_input)

        # Should remove null bytes and dangerous control chars except allowed ones
        assert "\x00" not in sanitized
        assert "\r" not in sanitized
        # Tab and newline should be preserved
        assert "\t" in sanitized
        assert "\n" in sanitized

        # Test length truncation
        long_input = "a" * 2000
        sanitized = SecurityValidator.sanitize_user_input(long_input, max_length=100)
        assert len(sanitized) <= 100

    def test_batch_size_validation(self):
        """Test batch size validation."""
        # Valid batch sizes
        valid_sizes = [10, 50, 100]
        for size in valid_sizes:
            result = SecurityValidator.validate_batch_size(size)
            assert result.is_valid

        # Invalid batch sizes
        invalid_sizes = [0, -1, "not_int", None]
        for size in invalid_sizes:
            result = SecurityValidator.validate_batch_size(size)
            assert not result.is_valid

        # Batch sizes with warnings
        warning_sizes = [1, 2000]
        for size in warning_sizes:
            result = SecurityValidator.validate_batch_size(size)
            assert result.is_valid
            assert len(result.warnings) > 0


class TestValidationResult:
    """Test ValidationResult class functionality."""

    def test_validation_result_creation(self):
        """Test ValidationResult creation and methods."""
        result = ValidationResult(is_valid=True)
        assert result.is_valid
        assert result.error_message is None
        assert len(result.warnings) == 0
        assert len(result.suggestions) == 0

        # Test adding warnings and suggestions
        result.add_warning("Test warning")
        result.add_suggestion("Test suggestion")

        assert len(result.warnings) == 1
        assert len(result.suggestions) == 1
        assert result.warnings[0] == "Test warning"
        assert result.suggestions[0] == "Test suggestion"

    def test_validation_result_with_error(self):
        """Test ValidationResult with error."""
        result = ValidationResult(
            is_valid=False,
            error_message="Test error",
            warnings=["Warning 1"],
            suggestions=["Suggestion 1"],
        )

        assert not result.is_valid
        assert result.error_message == "Test error"
        assert len(result.warnings) == 1
        assert len(result.suggestions) == 1


if __name__ == "__main__":
    pytest.main([__file__])
