# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is DeletePy, an Auth0 User Management Tool written in Python that allows bulk operations on Auth0 users including deletion, blocking, session/grant revocation, identity unlinking, and domain checking. The tool supports both development and production environments with safety confirmations for production operations.

## Architecture

The codebase follows a modern modular architecture with clear separation of concerns:

```
deletepy/
├── src/
│   └── deletepy/
│       ├── cli/                 # Command-line interface
│       │   ├── main.py          # Click-based CLI entry point
│       │   ├── commands.py      # Operation handlers
│       │   └── validators.py    # Argument validation
│       ├── core/                # Core functionality
│       │   ├── auth.py          # Auth0 authentication
│       │   ├── config.py        # Configuration management
│       │   └── exceptions.py    # Custom exceptions
│       ├── operations/          # Business operations
│       │   ├── user_ops.py      # Core user operations
│       │   ├── batch_ops.py     # Batch processing & social ID search
│       │   ├── export_ops.py    # Export functionality
│       │   └── domain_ops.py    # Domain checking
│       ├── utils/               # Utilities
│       │   ├── file_utils.py    # File operations
│       │   ├── display_utils.py # Progress/output formatting
│       │   ├── request_utils.py # HTTP request utilities
│       │   └── auth_utils.py    # Authentication utilities
│       └── models/              # Data models
├── tests/                       # Test suite
├── legacy files (main.py, etc.) # Backward compatibility
└── pyproject.toml              # Modern Python packaging
```

### Key Components

- **CLI Layer** (`src/deletepy/cli/`): Click-based command-line interface with modern argument parsing
- **Core Layer** (`src/deletepy/core/`): Authentication, configuration, and exception handling
- **Operations Layer** (`src/deletepy/operations/`): Business logic for Auth0 operations
- **Utils Layer** (`src/deletepy/utils/`): Shared utilities and helpers
- **Models Layer** (`src/deletepy/models/`): Data structures and type definitions

The application uses a generator pattern for memory-efficient file processing and implements rate limiting (0.2s between API calls) to prevent Auth0 API throttling.

### SDK Integration

DeletePy now uses the official **auth0-python SDK** (>= 4.7.1) for Auth0 Management API interactions:

- **SDK Wrapper Layer** (`src/deletepy/core/auth0_client.py`): Manages Auth0 Management API client initialization, token caching, and connection pooling
- **SDK Operations** (`src/deletepy/core/sdk_operations.py`): Wraps SDK methods with consistent error handling and logging
- **Exception Translation** (`src/deletepy/core/exceptions.py`): Maps SDK exceptions to custom exception hierarchy via `wrap_sdk_exception()`

#### SDK Benefits

1. **Type Safety**: SDK provides typed request/response models
2. **Automatic Token Management**: SDK handles token refresh and caching
3. **Built-in Rate Limiting**: SDK manages request throttling automatically
4. **Better Error Handling**: Structured exceptions with detailed error information
5. **Connection Pooling**: SDK reuses HTTP connections for better performance
6. **API Coverage**: Official SDK stays up-to-date with Auth0 API changes

#### Hybrid Approach

While most operations use the SDK, some endpoints (e.g., session management) still use direct HTTP requests where SDK coverage is incomplete. The `requests` library remains a dependency for these legacy endpoints.

## Environment Configuration

The tool requires a `.env` file with separate credentials for dev and prod:

- Dev environment uses `DEV_*` prefixed variables
- Prod environment uses standard variable names
- All operations in prod require explicit user confirmation

## Common Commands

### Setup

```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies (modern approach)
pip install -e .

# Or with development dependencies
pip install -e ".[dev]"
```

**Important**: Always ensure the virtual environment is activated before running any commands. You can tell it's active when you see `(venv)` at the beginning of your command prompt.

### Running Tests

```bash
# Make sure virtual environment is activated first!
source venv/bin/activate

# Run all tests
pytest

# Run tests with verbose output
pytest -v

# Run specific test file
pytest tests/test_auth.py

# Run specific test function
pytest tests/test_auth.py::test_get_access_token_success
```

### Main Operations (New CLI)

```bash
# Make sure virtual environment is activated first!
source venv/bin/activate

# Check authentication configuration
python -m src.deletepy.cli.main doctor [dev|prod]

# Check if specified users are unblocked
python -m src.deletepy.cli.main check-unblocked users.txt [dev|prod]

# Check email domains for specified users
python -m src.deletepy.cli.main check-domains users.txt [dev|prod]

# Export user last_login data to CSV
python -m src.deletepy.cli.main export-last-login emails.txt [dev|prod] [--connection CONNECTION]

# Find users by social media IDs (unlinks identities or deletes users)
python -m src.deletepy.cli.main unlink-social-ids social_ids.txt [dev|prod]

# User management operations
python -m src.deletepy.cli.main users block users.txt [dev|prod]
python -m src.deletepy.cli.main users delete users.txt [dev|prod]
python -m src.deletepy.cli.main users revoke-grants-only users.txt [dev|prod]
```

### Legacy Operations (Backward Compatibility)

```bash
# Legacy CLI still works with deprecation warnings
python main.py doctor [dev|prod]
python main.py users.txt dev --block
python main.py users.txt prod --delete
python main.py users.txt dev --revoke-grants-only
python main.py users.txt dev --check-unblocked
python main.py users.txt dev --check-domains
python main.py social_ids.txt dev --unlink-social-ids
```

### Code Quality

```bash
# Format code with ruff
ruff format .

# Lint code with ruff
ruff check .

# Fix auto-fixable lint issues
ruff check --fix .

# Type checking (if mypy is installed)
mypy src/
```

## Development Guidelines

### Input File Handling

- Input files should contain one Auth0 user ID or email per line
- The tool handles both Auth0 user IDs (auth0|123456) and email addresses
- Social ID files should contain one social media ID per line for unlink-social-ids operation
- Large files are processed using generators to minimize memory usage

### Error Handling

- All Auth0 API calls include proper timeout handling (30s for operations, 5s for auth)
- Rate limiting prevents API throttling
- Production operations require explicit confirmation
- Email resolution handles multiple users per email with detailed reporting
- Custom exception hierarchy provides structured error handling

### Testing

- Tests use pytest with fixtures for mock objects
- `conftest.py` provides automatic module-based request mocking
- Each module has corresponding test files following `test_*.py` naming
- Tests cover both success and error scenarios for Auth0 API interactions
- Test coverage should be maintained at 100%

### Function Complexity Guidelines

To maintain code readability and testability, follow these rules for function complexity:

**Maximum Limits:**

- **50 lines per function** - Functions exceeding 50 lines should be refactored
- **4 levels of nesting** - Deeply nested code indicates need for extraction
- **10 variables** - Too many variables suggest the function does too much
- **5 parameters** - Functions with many parameters should be redesigned

**Refactoring Rules:**

- **Extract helper functions** when logic can be grouped into distinct operations
- **Use private functions** (prefixed with `_`) for internal utilities
- **Break down complex loops** that handle multiple concerns
- **Separate display logic** from business logic
- **Extract validation** and error handling into dedicated functions

**When to Refactor:**

- Function has multiple responsibilities (violates Single Responsibility Principle)
- Complex conditional logic with deep nesting
- Long parameter lists or too many local variables
- Repetitive code patterns within the function
- Difficulty in writing focused unit tests

### Social Identity Management

The `unlink-social-ids` operation provides sophisticated identity management:

- **Single Identity Users**: Users with only the matching social identity are deleted entirely
- **Multi-Identity Users**: Only the matching social identity is unlinked, preserving the user account
- **Protected Users**: Users with Auth0 as main identity are protected from deletion
- Production operations require explicit confirmation with operation counts

### Auth0 API Requirements

Required Auth0 Management API scopes:

- `delete:users` - for user deletion
- `update:users` - for user blocking
- `delete:sessions` - for session revocation (Enterprise plan)
- `delete:grants` - for application grant revocation
- `read:users` - for user lookups and identity management

### Module Import Guidelines

When working with the modular structure:

- Import from the new modular structure: `from deletepy.operations.user_ops import delete_user`
- Use absolute imports within the package
- Maintain backward compatibility by keeping legacy imports working
- Follow the established module boundaries and don't cross-import between operation modules

# Important Instructions

Do what has been asked; nothing more, nothing less.
NEVER create files unless they're absolutely necessary for achieving your goal.
ALWAYS prefer editing an existing file to creating a new one.
NEVER proactively create documentation files (*.md) or README files. Only create documentation files if explicitly requested by the User.
