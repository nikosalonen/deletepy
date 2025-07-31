"""Structured logging utilities for DeletePy Auth0 User Management Tool."""

import json
import logging
import logging.config
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

try:
    import yaml

    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False


class ColoredFormatter(logging.Formatter):
    """Custom formatter with color support for terminal output."""

    # ANSI color codes
    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
        "RESET": "\033[0m",  # Reset
    }

    def __init__(self, *args: Any, disable_colors: bool = False, **kwargs: Any) -> None:
        """Initialize formatter with color configuration.

        Args:
            disable_colors: Whether to disable colored output
        """
        super().__init__(*args, **kwargs)
        self.disable_colors = disable_colors

    def format(self, record: logging.LogRecord) -> str:
        """Format log record with colors for terminal output."""
        # Add color to levelname if outputting to terminal and colors are enabled
        if (
            not self.disable_colors
            and hasattr(sys.stderr, "isatty")
            and sys.stderr.isatty()
        ):
            color = self.COLORS.get(record.levelname, "")
            reset = self.COLORS["RESET"]
            record.levelname = f"{color}{record.levelname}{reset}"

        return super().format(record)


class StructuredFormatter(logging.Formatter):
    """JSON formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as structured JSON."""
        log_entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        # Add extra fields if present
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        if hasattr(record, "operation"):
            log_entry["operation"] = record.operation
        if hasattr(record, "file_path"):
            log_entry["file_path"] = record.file_path
        if hasattr(record, "api_endpoint"):
            log_entry["api_endpoint"] = record.api_endpoint
        if hasattr(record, "status_code"):
            log_entry["status_code"] = record.status_code
        if hasattr(record, "duration"):
            log_entry["duration"] = record.duration

        return json.dumps(log_entry, default=str)


class DetailedFormatter(logging.Formatter):
    """Detailed formatter with context information."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record with detailed context."""
        # Base message
        base_msg = super().format(record)

        # Add context information
        context_parts = []
        if hasattr(record, "operation"):
            context_parts.append(f"op={record.operation}")
        if hasattr(record, "user_id"):
            context_parts.append(f"user={record.user_id}")
        if hasattr(record, "api_endpoint"):
            context_parts.append(f"endpoint={record.api_endpoint}")
        if hasattr(record, "status_code"):
            context_parts.append(f"status={record.status_code}")
        if hasattr(record, "duration"):
            context_parts.append(f"duration={record.duration:.3f}s")

        if context_parts:
            context_str = " [" + ", ".join(context_parts) + "]"
            return base_msg + context_str

        return base_msg


class OperationFilter(logging.Filter):
    """Filter to add operation context to log records."""

    def __init__(self, operation: str | None = None):
        """Initialize the filter with an operation context.

        Args:
            operation: The current operation being performed
        """
        super().__init__()
        self.operation = operation

    def filter(self, record: logging.LogRecord) -> bool:
        """Add operation context to the record."""
        if self.operation and not hasattr(record, "operation"):
            record.operation = self.operation
        return True


def setup_logging(
    level: str = "INFO",
    log_file: str | None = None,
    structured: bool = False,
    operation: str | None = None,
    log_format: str = "console",
    disable_colors: bool = False,
) -> logging.Logger:
    """Configure structured logging for the application.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional log file path for file output
        structured: Whether to use structured JSON logging
        operation: Current operation context for filtering
        log_format: Log format (console, json, detailed)
        disable_colors: Whether to disable colored output

    Returns:
        logging.Logger: Configured logger instance
    """
    # Clear any existing handlers
    root_logger = logging.getLogger("deletepy")
    root_logger.handlers.clear()

    # Set log level
    log_level = getattr(logging, level.upper(), logging.INFO)
    root_logger.setLevel(log_level)

    # Console handler
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(log_level)

    # Choose formatter based on configuration
    if structured or log_format == "json":
        console_formatter: logging.Formatter = StructuredFormatter()
    elif log_format == "detailed":
        console_formatter = DetailedFormatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    else:  # console format (default)
        console_formatter = ColoredFormatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
            disable_colors=disable_colors,
        )

    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    # File handler (if specified)
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(log_level)

        # Always use structured logging for files
        file_formatter = StructuredFormatter()
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)

    # Add operation filter if specified
    if operation:
        operation_filter = OperationFilter(operation)
        for handler in root_logger.handlers:
            handler.addFilter(operation_filter)

    return root_logger


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance for the specified module.

    Args:
        name: Logger name (typically __name__)

    Returns:
        logging.Logger: Logger instance
    """
    return logging.getLogger(f"deletepy.{name}")


def configure_from_env() -> logging.Logger:
    """Configure logging from environment variables.

    Environment variables:
        DELETEPY_LOG_LEVEL: Log level (default: INFO)
        DELETEPY_LOG_FILE: Log file path (optional)
        DELETEPY_LOG_STRUCTURED: Use structured logging (default: false)
        DELETEPY_LOG_OPERATION: Current operation context (optional)
        DELETEPY_LOG_FORMAT: Log format (console, json, detailed) (default: console)
        DELETEPY_LOG_DISABLE_COLORS: Disable colored output (default: false)

    Returns:
        logging.Logger: Configured logger instance
    """
    level = os.getenv("DELETEPY_LOG_LEVEL", "INFO")
    log_file = os.getenv("DELETEPY_LOG_FILE")
    structured = os.getenv("DELETEPY_LOG_STRUCTURED", "false").lower() == "true"
    operation = os.getenv("DELETEPY_LOG_OPERATION")
    log_format = os.getenv("DELETEPY_LOG_FORMAT", "console")
    disable_colors = os.getenv("DELETEPY_LOG_DISABLE_COLORS", "false").lower() == "true"

    return setup_logging(
        level=level,
        log_file=log_file,
        structured=structured,
        operation=operation,
        log_format=log_format,
        disable_colors=disable_colors,
    )


class LogContext:
    """Context manager for adding structured context to log records."""

    def __init__(self, logger: logging.Logger, **context: Any) -> None:
        """Initialize log context.

        Args:
            logger: Logger instance to add context to
            **context: Key-value pairs to add as context
        """
        self.logger = logger
        self.context = context
        self.old_context: dict[str, Any] = {}

    def __enter__(self) -> "LogContext":
        """Enter the context and apply context variables."""
        # Store old context and apply new context
        for key, value in self.context.items():
            if hasattr(self.logger, key):
                self.old_context[key] = getattr(self.logger, key)
            setattr(self.logger, key, value)
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit the context and restore previous context."""
        # Restore old context
        for key in self.context:
            if key in self.old_context:
                setattr(self.logger, key, self.old_context[key])
            elif hasattr(self.logger, key):
                delattr(self.logger, key)


def log_operation(operation: str, user_id: str | None = None, **kwargs: Any) -> Any:
    """Decorator for logging operation start/end with context.

    Args:
        operation: Operation name
        user_id: Optional user ID context
        **kwargs: Additional context variables
    """

    def decorator(func: Any) -> Any:
        def wrapper(*args: Any, **func_kwargs: Any) -> Any:
            logger = get_logger(func.__module__)

            # Create context
            context = {"operation": operation}
            if user_id:
                context["user_id"] = user_id
            context.update(kwargs)

            with LogContext(logger, **context):
                logger.info(f"Starting {operation}", extra=context)
                start_time = datetime.utcnow()

                try:
                    result = func(*args, **func_kwargs)
                    duration = (datetime.utcnow() - start_time).total_seconds()
                    logger.info(
                        f"Completed {operation}",
                        extra={**context, "duration": duration, "status": "success"},
                    )
                    return result
                except Exception as e:
                    duration = (datetime.utcnow() - start_time).total_seconds()
                    logger.error(
                        f"Failed {operation}: {e}",
                        extra={**context, "duration": duration, "status": "error"},
                        exc_info=True,
                    )
                    raise

        return wrapper

    return decorator


# Default logger configuration
def init_default_logging() -> None:
    """Initialize default logging configuration if not already configured."""
    if not logging.getLogger("deletepy").handlers:
        # Try YAML configuration first, fall back to environment
        configure_from_default_yaml()


def configure_from_yaml(config_path: str | Path) -> logging.Logger:
    """Configure logging from YAML configuration file.

    Args:
        config_path: Path to YAML configuration file

    Returns:
        logging.Logger: Configured logger instance

    Raises:
        ImportError: If PyYAML is not installed
        FileNotFoundError: If config file doesn't exist
        ValueError: If config file is invalid
    """
    if not YAML_AVAILABLE:
        raise ImportError(
            "PyYAML is required for YAML configuration. Install with: pip install pyyaml"
        )

    config_path = Path(config_path)
    if not config_path.exists():
        raise FileNotFoundError(f"Logging config file not found: {config_path}")

    try:
        with open(config_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)

        logging.config.dictConfig(config)
        return logging.getLogger("deletepy")
    except Exception as e:
        raise ValueError(f"Invalid logging configuration: {e}") from e


def configure_from_default_yaml() -> logging.Logger:
    """Configure logging from default YAML configuration.

    Returns:
        logging.Logger: Configured logger instance, or falls back to environment config
    """
    try:
        # Try to find default config file
        config_dir = Path(__file__).parent.parent / "config"
        default_config = config_dir / "logging.yaml"

        if default_config.exists() and YAML_AVAILABLE:
            return configure_from_yaml(default_config)
    except Exception:
        # Fall back to environment configuration if YAML config fails
        pass

    return configure_from_env()


# Initialize logging when module is imported
init_default_logging()
