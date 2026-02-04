"""Enhanced input validation utilities with security focus."""

import os
import re
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .auth_utils import AUTH0_CONNECTIONS


@dataclass
class ValidationResult:
    """Result of a validation operation with detailed feedback."""

    is_valid: bool
    error_message: str | None = None
    warnings: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)

    def add_warning(self, warning: str) -> None:
        """Add a warning to the validation result."""
        self.warnings.append(warning)

    def add_suggestion(self, suggestion: str) -> None:
        """Add a suggestion to the validation result."""
        self.suggestions.append(suggestion)


class InputValidator:
    """Enhanced input validation with security focus."""

    # Email validation patterns
    EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")

    # More restrictive email pattern for security
    SECURE_EMAIL_PATTERN = re.compile(
        r"^[a-zA-Z0-9][a-zA-Z0-9._%+-]*[a-zA-Z0-9]@[a-zA-Z0-9][a-zA-Z0-9.-]*[a-zA-Z0-9]\.[a-zA-Z]{2,}$"
    )

    # Auth0 user ID patterns
    AUTH0_USER_ID_PATTERN = re.compile(r"^[a-zA-Z0-9\-_]+\|[a-zA-Z0-9\-_]+$")

    # Known Auth0 connection types - imported from auth_utils (single source of truth)
    KNOWN_AUTH0_CONNECTIONS = AUTH0_CONNECTIONS

    # Dangerous characters for path traversal
    PATH_TRAVERSAL_PATTERNS = [
        "../",
        "..\\",
        "..%2f",
        "..%5c",
        "..%252f",
        "..%255c",
        "%2e%2e%2f",
        "%2e%2e%5c",
        "%252e%252e%252f",
        "%252e%252e%255c",
    ]

    # Dangerous URL encoding patterns
    DANGEROUS_URL_PATTERNS = [
        "%00",
        "%0a",
        "%0d",
        "%1f",
        "%7f",  # Control characters
        "%3c",
        "%3e",
        "%22",
        "%27",  # HTML/script injection
        "%2f%2e%2e",
        "%5c%2e%2e",  # Path traversal
    ]

    @staticmethod
    def validate_email_comprehensive(email: str) -> ValidationResult:
        """Comprehensive email validation with security checks.

        Args:
            email: Email address to validate

        Returns:
            ValidationResult: Detailed validation result
        """
        if not email or not isinstance(email, str):
            return ValidationResult(
                is_valid=False, error_message="Email must be a non-empty string"
            )

        # Strip whitespace
        email = email.strip()

        if not email:
            return ValidationResult(
                is_valid=False, error_message="Email cannot be empty or only whitespace"
            )

        result = ValidationResult(is_valid=True)

        # Check length limits
        if len(email) > 254:  # RFC 5321 limit
            return ValidationResult(
                is_valid=False,
                error_message="Email address too long (maximum 254 characters)",
            )

        if len(email) < 3:  # Minimum reasonable email: a@b
            return ValidationResult(
                is_valid=False,
                error_message="Email address too short (minimum 3 characters)",
            )

        # Check for dangerous characters
        dangerous_chars = ["<", ">", '"', "'", "&", "\n", "\r", "\t", "\0"]
        for char in dangerous_chars:
            if char in email:
                return ValidationResult(
                    is_valid=False,
                    error_message=f"Email contains dangerous character: {repr(char)}",
                )

        # Basic format validation
        if not InputValidator.EMAIL_PATTERN.match(email):
            return ValidationResult(
                is_valid=False, error_message="Invalid email format"
            )

        # Security-focused validation
        if not InputValidator.SECURE_EMAIL_PATTERN.match(email):
            result.add_warning("Email format may be vulnerable to injection attacks")
            result.add_suggestion(
                "Ensure email starts and ends with alphanumeric characters"
            )

        # Check local part length (before @)
        local_part = email.split("@")[0]
        if len(local_part) > 64:  # RFC 5321 limit
            return ValidationResult(
                is_valid=False,
                error_message="Email local part too long (maximum 64 characters)",
            )

        # Check domain part
        domain_part = email.split("@")[1]
        if len(domain_part) > 253:  # RFC 1035 limit
            return ValidationResult(
                is_valid=False,
                error_message="Email domain too long (maximum 253 characters)",
            )

        # Check for consecutive dots
        if ".." in email:
            return ValidationResult(
                is_valid=False, error_message="Email contains consecutive dots"
            )

        # Check for dots at start/end of domain
        if domain_part.startswith(".") or domain_part.endswith("."):
            return ValidationResult(
                is_valid=False,
                error_message="Email domain cannot start or end with a dot",
            )

        # Check for leading/trailing dots in local part
        if local_part.startswith(".") or local_part.endswith("."):
            return ValidationResult(
                is_valid=False,
                error_message="Email local part cannot start or end with a dot",
            )

        # Warn about potentially problematic patterns
        if email.count("@") > 1:
            return ValidationResult(
                is_valid=False, error_message="Email contains multiple @ symbols"
            )

        # Check for suspicious patterns
        suspicious_patterns = ["+", "--", "__"]
        for pattern in suspicious_patterns:
            if pattern in email:
                result.add_warning(
                    f"Email contains potentially suspicious pattern: {pattern}"
                )

        return result

    @staticmethod
    def validate_auth0_user_id_enhanced(user_id: str) -> ValidationResult:
        """Enhanced Auth0 user ID validation with better error messages.

        Args:
            user_id: Auth0 user ID to validate

        Returns:
            ValidationResult: Detailed validation result
        """
        if not user_id or not isinstance(user_id, str):
            return ValidationResult(
                is_valid=False, error_message="User ID must be a non-empty string"
            )

        # Strip whitespace
        user_id = user_id.strip()

        if not user_id:
            return ValidationResult(
                is_valid=False,
                error_message="User ID cannot be empty or only whitespace",
            )

        result = ValidationResult(is_valid=True)

        # Check length limits
        if len(user_id) > 512:  # Reasonable upper limit
            return ValidationResult(
                is_valid=False,
                error_message="User ID too long (maximum 512 characters)",
            )

        if len(user_id) < 3:  # Minimum: a|b
            return ValidationResult(
                is_valid=False, error_message="User ID too short (minimum 3 characters)"
            )

        # Check for dangerous characters
        dangerous_chars = ["<", ">", '"', "'", "&", "\n", "\r", "\t", "\0", " "]
        for char in dangerous_chars:
            if char in user_id:
                return ValidationResult(
                    is_valid=False,
                    error_message=f"User ID contains dangerous character: {repr(char)}",
                )

        # Check basic format (connection|identifier)
        if "|" not in user_id:
            return ValidationResult(
                is_valid=False,
                error_message="Auth0 user ID must contain a pipe (|) separator",
                suggestions=[
                    "Format should be: connection|identifier (e.g., auth0|123456)"
                ],
            )

        # Split and validate parts
        parts = user_id.split("|")
        if len(parts) != 2:
            return ValidationResult(
                is_valid=False,
                error_message="Auth0 user ID must have exactly one pipe (|) separator",
                suggestions=["Format should be: connection|identifier"],
            )

        connection, identifier = parts

        # Validate connection part
        if not connection:
            return ValidationResult(
                is_valid=False,
                error_message="Connection part (before |) cannot be empty",
            )

        if not identifier:
            return ValidationResult(
                is_valid=False,
                error_message="Identifier part (after |) cannot be empty",
            )

        # Check connection format
        if not re.match(r"^[a-zA-Z0-9\-_]+$", connection):
            return ValidationResult(
                is_valid=False,
                error_message="Connection part contains invalid characters (only letters, numbers, hyphens, and underscores allowed)",
            )

        # Check identifier format
        if not re.match(r"^[a-zA-Z0-9\-_]+$", identifier):
            return ValidationResult(
                is_valid=False,
                error_message="Identifier part contains invalid characters (only letters, numbers, hyphens, and underscores allowed)",
            )

        # Validate against known connection types
        if connection not in InputValidator.KNOWN_AUTH0_CONNECTIONS:
            result.add_warning(f"Unknown connection type: {connection}")
            result.add_suggestion(
                f"Known connection types: {', '.join(sorted(InputValidator.KNOWN_AUTH0_CONNECTIONS))}"
            )

        # Check for suspicious patterns
        if connection.startswith("-") or connection.endswith("-"):
            result.add_warning("Connection part starts or ends with hyphen")

        if identifier.startswith("-") or identifier.endswith("-"):
            result.add_warning("Identifier part starts or ends with hyphen")

        # Length checks for parts
        if len(connection) > 50:
            result.add_warning("Connection part is unusually long")

        if len(identifier) > 100:
            result.add_warning("Identifier part is unusually long")

        return result

    @staticmethod
    def validate_url_encoding_secure(encoded_string: str) -> ValidationResult:
        """Validate URL encoding for security vulnerabilities.

        Args:
            encoded_string: URL-encoded string to validate

        Returns:
            ValidationResult: Detailed validation result
        """
        if not encoded_string or not isinstance(encoded_string, str):
            return ValidationResult(
                is_valid=False,
                error_message="Encoded string must be a non-empty string",
            )

        result = ValidationResult(is_valid=True)

        # Check for dangerous URL encoding patterns
        encoded_lower = encoded_string.lower()
        for pattern in InputValidator.DANGEROUS_URL_PATTERNS:
            if pattern in encoded_lower:
                return ValidationResult(
                    is_valid=False,
                    error_message=f"Dangerous URL encoding pattern detected: {pattern}",
                )

        # Check for double encoding
        try:
            decoded_once = urllib.parse.unquote(encoded_string)
            decoded_twice = urllib.parse.unquote(decoded_once)

            if decoded_once != decoded_twice:
                result.add_warning("String appears to be double-encoded")
                result.add_suggestion(
                    "Avoid double URL encoding to prevent security issues"
                )
        except Exception:
            result.add_warning("Unable to decode URL-encoded string")

        # Check for null bytes and control characters after decoding
        try:
            decoded = urllib.parse.unquote(encoded_string)
            for i, char in enumerate(decoded):
                if ord(char) < 32 and char not in ["\t", "\n", "\r"]:
                    return ValidationResult(
                        is_valid=False,
                        error_message=f"Decoded string contains control character at position {i}: {repr(char)}",
                    )
        except Exception:
            pass

        # Check for excessive length after decoding
        try:
            decoded = urllib.parse.unquote(encoded_string)
            if len(decoded) > 2048:  # Reasonable limit
                result.add_warning("Decoded string is very long, potential DoS risk")
        except Exception:
            pass

        return result

    @staticmethod
    def validate_file_path_secure(
        file_path: str, base_dir: str | None = None
    ) -> ValidationResult:
        """Secure file path validation to prevent path traversal attacks.

        Args:
            file_path: File path to validate
            base_dir: Optional base directory to restrict access to

        Returns:
            ValidationResult: Detailed validation result
        """
        if not file_path or not isinstance(file_path, str):
            return ValidationResult(
                is_valid=False, error_message="File path must be a non-empty string"
            )

        # Strip whitespace
        file_path = file_path.strip()

        if not file_path:
            return ValidationResult(
                is_valid=False,
                error_message="File path cannot be empty or only whitespace",
            )

        result = ValidationResult(is_valid=True)

        # Check for dangerous characters
        dangerous_chars = ["\0", "\n", "\r", "\t"]
        for char in dangerous_chars:
            if char in file_path:
                return ValidationResult(
                    is_valid=False,
                    error_message=f"File path contains dangerous character: {repr(char)}",
                )

        # Check for path traversal patterns
        path_lower = file_path.lower()
        for pattern in InputValidator.PATH_TRAVERSAL_PATTERNS:
            if pattern in path_lower:
                return ValidationResult(
                    is_valid=False,
                    error_message=f"Path traversal pattern detected: {pattern}",
                )

        # Check for absolute paths when base_dir is specified
        if base_dir and os.path.isabs(file_path):
            result.add_warning(
                "Absolute path provided when base directory is specified"
            )
            result.add_suggestion("Use relative paths for better security")

        # Resolve path and check for traversal
        try:
            # If base_dir is specified, resolve relative to it
            if base_dir:
                base_resolved = Path(base_dir).resolve()
                if os.path.isabs(file_path):
                    resolved_path = Path(file_path).resolve()
                else:
                    resolved_path = (base_resolved / file_path).resolve()

                try:
                    resolved_path.relative_to(base_resolved)
                except ValueError:
                    return ValidationResult(
                        is_valid=False,
                        error_message=f"Path attempts to access outside base directory: {base_dir}",
                    )
            else:
                resolved_path = Path(file_path).resolve()

            # Check for suspicious patterns in resolved path
            resolved_str = str(resolved_path)
            if ".." in resolved_str:
                result.add_warning("Resolved path contains '..' components")

        except (OSError, ValueError) as e:
            return ValidationResult(
                is_valid=False, error_message=f"Invalid file path: {e}"
            )

        # Check path length
        if len(file_path) > 1000:  # Reasonable limit for our use case
            return ValidationResult(
                is_valid=False,
                error_message="File path too long (maximum 1000 characters)",
            )

        # Check for suspicious extensions
        suspicious_extensions = [".exe", ".bat", ".cmd", ".com", ".scr", ".pif"]
        path_obj = Path(file_path)
        if path_obj.suffix.lower() in suspicious_extensions:
            return ValidationResult(
                is_valid=False,
                error_message=f"Dangerous file extension: {path_obj.suffix}",
            )

        # Check for hidden files (starting with .)
        if path_obj.name.startswith(".") and path_obj.name not in [".", ".."]:
            result.add_warning("Path refers to a hidden file")

        return result


class SecurityValidator:
    """Additional security-focused validation utilities."""

    @staticmethod
    def validate_checkpoint_path(
        checkpoint_path: str, checkpoint_dir: str | None = ".checkpoints"
    ) -> ValidationResult:
        """Validate checkpoint file path for security.

        Args:
            checkpoint_path: Path to checkpoint file
            checkpoint_dir: Base checkpoint directory (None to skip base directory check)

        Returns:
            ValidationResult: Detailed validation result
        """
        # First validate as a general file path
        result = InputValidator.validate_file_path_secure(
            checkpoint_path, checkpoint_dir
        )

        if not result.is_valid:
            return result

        # Additional checkpoint-specific validations
        path_obj = Path(checkpoint_path)

        # Check file extension
        if path_obj.suffix.lower() not in [".json", ".json.backup"]:
            result.add_warning("Checkpoint file should have .json extension")
            result.add_suggestion("Use .json extension for checkpoint files")

        # Check filename pattern
        if not re.match(r"^[a-zA-Z0-9_\-]+\.json(\.backup)?$", path_obj.name):
            return ValidationResult(
                is_valid=False,
                error_message="Checkpoint filename contains unusual characters",
            )

        return result

    @staticmethod
    def sanitize_user_input(user_input: str, max_length: int = 1000) -> str:
        """Sanitize user input by removing dangerous characters.

        Args:
            user_input: Raw user input
            max_length: Maximum allowed length

        Returns:
            str: Sanitized input
        """
        if not user_input or not isinstance(user_input, str):
            return ""

        # Remove null bytes and dangerous control characters (keep tab and newline)
        sanitized = "".join(
            char for char in user_input if ord(char) >= 32 or char in ["\t", "\n"]
        )

        # Truncate to max length
        if len(sanitized) > max_length:
            sanitized = sanitized[:max_length]

        # Strip whitespace
        return sanitized.strip()

    @staticmethod
    def validate_batch_size(batch_size: Any) -> ValidationResult:
        """Validate batch size parameter.

        Args:
            batch_size: Batch size to validate

        Returns:
            ValidationResult: Detailed validation result
        """
        if not isinstance(batch_size, int):
            return ValidationResult(
                is_valid=False, error_message="Batch size must be an integer"
            )

        if batch_size <= 0:
            return ValidationResult(
                is_valid=False, error_message="Batch size must be positive"
            )

        result = ValidationResult(is_valid=True)

        if batch_size > 1000:
            result.add_warning("Very large batch size may cause performance issues")
            result.add_suggestion(
                "Consider using batch sizes between 10-100 for optimal performance"
            )

        if batch_size < 5:
            result.add_warning("Very small batch size may be inefficient")
            result.add_suggestion(
                "Consider using batch sizes between 10-100 for optimal performance"
            )

        return result
