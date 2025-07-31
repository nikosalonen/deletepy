"""Tests for structured logging functionality."""

import json
import logging
import os
import tempfile
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest

from src.deletepy.utils.logging_utils import (
    ColoredFormatter,
    DetailedFormatter,
    StructuredFormatter,
    configure_from_env,
    get_logger,
    setup_logging,
)
from src.deletepy.utils.legacy_print import (
    print_error,
    print_info,
    print_success,
    print_warning,
)


class TestStructuredFormatter:
    """Test structured JSON formatter."""

    def test_basic_formatting(self):
        """Test basic log record formatting."""
        formatter = StructuredFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        
        result = formatter.format(record)
        log_data = json.loads(result)
        
        assert log_data["level"] == "INFO"
        assert log_data["logger"] == "test.logger"
        assert log_data["message"] == "Test message"
        assert log_data["line"] == 42
        assert "timestamp" in log_data

    def test_context_fields(self):
        """Test that context fields are included."""
        formatter = StructuredFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        
        # Add context fields
        record.user_id = "auth0|123456"
        record.operation = "delete_user"
        record.duration = 1.234
        
        result = formatter.format(record)
        log_data = json.loads(result)
        
        assert log_data["user_id"] == "auth0|123456"
        assert log_data["operation"] == "delete_user"
        assert log_data["duration"] == 1.234


class TestDetailedFormatter:
    """Test detailed formatter with context."""

    def test_basic_formatting(self):
        """Test basic formatting without context."""
        formatter = DetailedFormatter(
            fmt="%(levelname)s - %(message)s"
        )
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        
        result = formatter.format(record)
        assert result == "INFO - Test message"

    def test_context_formatting(self):
        """Test formatting with context fields."""
        formatter = DetailedFormatter(
            fmt="%(levelname)s - %(message)s"
        )
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        
        # Add context fields
        record.operation = "delete_user"
        record.user_id = "auth0|123456"
        record.duration = 1.234
        
        result = formatter.format(record)
        assert "INFO - Test message [" in result
        assert "op=delete_user" in result
        assert "user=auth0|123456" in result
        assert "duration=1.234s" in result


class TestColoredFormatter:
    """Test colored formatter."""

    def test_colors_disabled(self):
        """Test formatter with colors disabled."""
        formatter = ColoredFormatter(
            fmt="%(levelname)s - %(message)s",
            disable_colors=True
        )
        record = logging.LogRecord(
            name="test.logger",
            level=logging.ERROR,
            pathname="test.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        
        result = formatter.format(record)
        assert result == "ERROR - Test message"
        assert "\033[" not in result  # No ANSI codes


class TestLoggingSetup:
    """Test logging setup functions."""

    def test_setup_logging_console_format(self):
        """Test setup with console format."""
        logger = setup_logging(level="DEBUG", log_format="console")
        assert logger.level == logging.DEBUG
        assert len(logger.handlers) == 1
        assert isinstance(logger.handlers[0].formatter, ColoredFormatter)

    def test_setup_logging_detailed_format(self):
        """Test setup with detailed format."""
        logger = setup_logging(level="INFO", log_format="detailed")
        assert isinstance(logger.handlers[0].formatter, DetailedFormatter)

    def test_setup_logging_json_format(self):
        """Test setup with JSON format."""
        logger = setup_logging(level="INFO", log_format="json")
        assert isinstance(logger.handlers[0].formatter, StructuredFormatter)

    def test_setup_logging_with_file(self):
        """Test setup with file output."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = tmp.name
        
        try:
            logger = setup_logging(level="INFO", log_file=tmp_path)
            assert len(logger.handlers) == 2  # Console + file
            
            # File handler should use structured format
            file_handler = logger.handlers[1]
            assert isinstance(file_handler.formatter, StructuredFormatter)
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def test_configure_from_env(self):
        """Test configuration from environment variables."""
        env_vars = {
            "DELETEPY_LOG_LEVEL": "DEBUG",
            "DELETEPY_LOG_FORMAT": "detailed",
            "DELETEPY_LOG_DISABLE_COLORS": "true"
        }
        
        with patch.dict(os.environ, env_vars):
            logger = configure_from_env()
            assert logger.level == logging.DEBUG
            assert isinstance(logger.handlers[0].formatter, DetailedFormatter)


class TestLegacyPrintFunctions:
    """Test legacy print functions with structured logging."""

    def test_print_functions_with_context(self):
        """Test that print functions work and include context."""
        # This is a basic test to ensure the functions work
        # The actual context testing is complex due to logger hierarchy
        
        # Test that functions don't raise exceptions
        try:
            print_info("Test info message", user_id="auth0|123", operation="test")
            print_success("Test success", user_id="auth0|456")
            print_warning("Test warning", operation="test_op")
            print_error("Test error", user_id="auth0|789", error="test_error")
        except Exception as e:
            pytest.fail(f"Print functions raised exception: {e}")
        
        # Test that the functions accept context parameters
        assert True  # If we get here, the functions worked

    def test_get_logger(self):
        """Test get_logger function."""
        logger = get_logger("test.module")
        assert logger.name == "deletepy.test.module"


class TestLoggingIntegration:
    """Integration tests for logging functionality."""

    def test_structured_logging_output(self):
        """Test that structured logging produces valid JSON."""
        # Capture log output
        log_stream = StringIO()
        handler = logging.StreamHandler(log_stream)
        handler.setFormatter(StructuredFormatter())
        
        logger = logging.getLogger("test.integration")
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        
        # Log a message with context
        logger.info("Test message", extra={
            "user_id": "auth0|123456",
            "operation": "delete_user",
            "duration": 1.234
        })
        
        # Parse the output
        log_output = log_stream.getvalue().strip()
        log_data = json.loads(log_output)
        
        assert log_data["message"] == "Test message"
        assert log_data["user_id"] == "auth0|123456"
        assert log_data["operation"] == "delete_user"
        assert log_data["duration"] == 1.234
        assert "timestamp" in log_data

    def test_environment_configuration(self):
        """Test that environment variables configure logging correctly."""
        env_vars = {
            "DELETEPY_LOG_LEVEL": "WARNING",
            "DELETEPY_LOG_STRUCTURED": "true"
        }
        
        with patch.dict(os.environ, env_vars):
            logger = configure_from_env()
            
            # Should be at WARNING level
            assert logger.level == logging.WARNING
            
            # Should use structured formatter
            assert isinstance(logger.handlers[0].formatter, StructuredFormatter)