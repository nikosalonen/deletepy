# Structured Logging in DeletePy

DeletePy now uses structured logging throughout the application to provide consistent, contextual log messages that are easy to parse and analyze.

## Features

- **Structured JSON logging** for machine-readable logs
- **Colored console output** for human-readable logs
- **Detailed formatting** with context information
- **Configurable log levels** and output formats
- **Context-aware logging** with operation, user_id, and other metadata
- **Environment variable configuration**
- **YAML configuration file support**

## Configuration

### Environment Variables

You can configure logging using these environment variables:

```bash
# Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
export DELETEPY_LOG_LEVEL=INFO

# Log file path (optional)
export DELETEPY_LOG_FILE=/path/to/logfile.log

# Use structured JSON logging (true/false)
export DELETEPY_LOG_STRUCTURED=true

# Log format (rich [default], console, detailed, json)
# Default is 'rich' if Rich is available; falls back to 'console' otherwise
export DELETEPY_LOG_FORMAT=rich

# Disable colored output (true/false)
export DELETEPY_LOG_DISABLE_COLORS=false

# Current operation context (optional)
export DELETEPY_LOG_OPERATION=user_deletion
```

### YAML Configuration

You can also use a YAML configuration file. The default configuration is located at `src/deletepy/config/logging.yaml`:

```yaml
version: 1
disable_existing_loggers: false

formatters:
  console:
    format: "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    datefmt: "%Y-%m-%d %H:%M:%S"
    class: deletepy.utils.logging_utils.ColoredFormatter

  detailed:
    format: "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    datefmt: "%Y-%m-%d %H:%M:%S"
    class: deletepy.utils.logging_utils.DetailedFormatter

  json:
    class: deletepy.utils.logging_utils.StructuredFormatter

handlers:
  console:
    class: logging.StreamHandler
    level: INFO
    formatter: console
    stream: ext://sys.stderr

loggers:
  deletepy:
    level: INFO
    handlers: [console]
    propagate: false
```

## Log Formats

### Rich Format (Default)
Beautiful, interactive console output powered by Rich (auto-fallbacks to Console if Rich is unavailable):
```
2025-07-31 08:00:00 | INFO     | deletepy.operations.user_ops | Deleting user: auth0|123456
2025-07-31 08:00:01 | INFO     | deletepy.operations.user_ops | ✅ Successfully deleted user auth0|123456
```

### Console Format
Human-readable colored output for terminal use:
```
2025-07-31 08:00:00 | INFO     | deletepy.operations.user_ops | Deleting user: auth0|123456
2025-07-31 08:00:01 | INFO     | deletepy.operations.user_ops | ✅ Successfully deleted user auth0|123456
```

### Detailed Format
Console format with additional context information:
```
2025-07-31 08:00:00 | INFO     | deletepy.operations.user_ops | Deleting user: auth0|123456 [op=delete_user, user=auth0|123456]
2025-07-31 08:00:01 | INFO     | deletepy.operations.user_ops | ✅ Successfully deleted user auth0|123456 [op=delete_user, user=auth0|123456, duration=1.234s]
```

### JSON Format
Structured JSON for machine processing:
```json
{
  "timestamp": "2025-07-31T08:00:00.000000+00:00",
  "level": "INFO",
  "logger": "deletepy.operations.user_ops",
  "message": "Deleting user: auth0|123456",
  "module": "user_ops",
  "function": "delete_user",
  "line": 32,
  "operation": "delete_user",
  "user_id": "auth0|123456"
}
```

## Context Information

The structured logging system automatically includes relevant context information:

- **operation**: Current operation being performed (delete_user, export_csv, etc.)
- **user_id**: Auth0 user ID when applicable
- **checkpoint_id**: Checkpoint ID for resumable operations
- **batch_number**: Batch number for batch operations
- **duration**: Operation duration in seconds
- **api_endpoint**: API endpoint for HTTP requests
- **status_code**: HTTP status code for API responses
- **error**: Error message for failed operations

## Usage Examples

### Basic Logging
```python
from deletepy.utils.legacy_print import print_info, print_error

# Simple message
print_info("Operation started")

# With context
print_info("Processing user", user_id="auth0|123456", operation="delete_user")

# Error with context
print_error("Operation failed", user_id="auth0|123456", error="User not found")
```

### Using Logger Directly
```python
from deletepy.utils.logging_utils import get_logger

logger = get_logger(__name__)

# Log with context
logger.info("User operation completed", extra={
    "user_id": "auth0|123456",
    "operation": "delete_user",
    "duration": 1.234,
    "status": "success"
})
```

### Programmatic Configuration
```python
from deletepy.utils.logging_utils import setup_logging

# Configure logging programmatically
logger = setup_logging(
    level="DEBUG",
    log_file="deletepy.log",
    structured=True,
    operation="batch_delete"
)
```

## Migration from Print Functions

The legacy print functions have been updated to use structured logging while maintaining backward compatibility:

- `print_info()` → Uses structured logging with INFO level
- `print_success()` → Uses structured logging with INFO level + success status
- `print_warning()` → Uses structured logging with WARNING level
- `print_error()` → Uses structured logging with ERROR level

All existing code continues to work without changes, but now benefits from structured logging.

## Best Practices

1. **Include Context**: Always include relevant context like `user_id`, `operation`, etc.
   ```python
   print_info("User deleted", user_id=user_id, operation="delete_user")
   ```

2. **Use Appropriate Log Levels**:
   - `DEBUG`: Detailed diagnostic information
   - `INFO`: General information about program execution
   - `WARNING`: Something unexpected happened, but the program continues
   - `ERROR`: A serious problem occurred

3. **Structure Your Messages**: Write clear, actionable log messages
   ```python
   # Good
   print_error("Failed to delete user", user_id=user_id, error=str(e))

   # Less helpful
   print_error("Something went wrong")
   ```

4. **Use JSON Format for Production**: Enable structured logging in production environments for better log analysis
   ```bash
   export DELETEPY_LOG_STRUCTURED=true
   export DELETEPY_LOG_FILE=/var/log/deletepy.log
   ```

## Troubleshooting

### No Log Output
- Check that the log level is appropriate (DEBUG shows all messages)
- Verify environment variables are set correctly
- Ensure the logger is properly initialized

### Missing Context Information
- Make sure you're passing context parameters to print functions
- Use the `extra` parameter when logging directly with the logger

### Performance Issues
- Avoid logging in tight loops
- Use appropriate log levels (DEBUG only when needed)
- Consider using file logging for high-volume operations
