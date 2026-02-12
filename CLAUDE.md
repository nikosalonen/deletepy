# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is DeletePy, an Auth0 User Management Tool written in Python that allows bulk operations on Auth0 users including deletion, blocking, session/grant revocation, identity unlinking, and domain checking. The tool supports both development and production environments with safety confirmations for production operations.

## Architecture

The codebase follows a modern modular architecture with clear separation of concerns:

```text
deletepy/
├── src/
│   └── deletepy/
│       ├── cli/                 # Command-line interface
│       │   ├── main.py          # Click-based CLI entry point
│       │   ├── commands.py      # Operation handlers
│       │   └── validators.py    # Argument validation
│       ├── core/                # Core functionality
│       │   ├── auth.py          # Auth0 authentication
│       │   ├── auth0_client.py  # Unified Auth0 API client
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
│       │   ├── request_utils.py # Batch processing utilities
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

The application uses a generator pattern for memory-efficient file processing and implements adaptive rate limiting (0.4-0.5s between API calls, with automatic backoff) to prevent Auth0 API throttling.

## Environment Configuration

The tool requires a `.env` file with separate credentials for dev and prod:

- Dev environment uses `DEV_*` prefixed variables
- Prod environment uses standard variable names
- All operations in prod require explicit user confirmation

## Common Commands

### Setup (Recommended: uv)

```bash
# Install dependencies with uv (creates .venv automatically)
uv sync --extra dev

# Or use a specific Python version (e.g., 3.14)
uv python install 3.14
uv sync --python 3.14 --extra dev

# Or using make
make sync-dev
```

### Alternative: Traditional pip setup

```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -e ".[dev]"
```

### Running Tests

```bash
# With uv (recommended)
uv run pytest

# Or using make (auto-detects uv)
make test

# Run tests with verbose output
uv run pytest -v

# Run specific test file
uv run pytest tests/test_auth.py

# Run specific test function
uv run pytest tests/test_auth.py::test_get_access_token_success
```

### Main Operations

```bash
# With uv (recommended)
uv run deletepy doctor [dev|prod]
uv run deletepy check-unblocked users.txt [dev|prod]
uv run deletepy check-domains users.txt [dev|prod]
uv run deletepy export-last-login emails.txt [dev|prod] [--connection CONNECTION]
uv run deletepy fetch-emails user_ids.txt [dev|prod]
uv run deletepy unlink-social-ids social_ids.txt [dev|prod]
uv run deletepy users block users.txt [dev|prod]
uv run deletepy users delete users.txt [dev|prod]
uv run deletepy users revoke-grants-only users.txt [dev|prod]

# Or using make
make run ARGS="doctor dev"
make run ARGS="users block users.txt dev --dry-run"

# Or direct (if virtual environment is activated)
deletepy doctor dev
deletepy users block users.txt dev
```

### Code Quality

```bash
# With uv (recommended)
uv run ruff format src/ tests/
uv run ruff check src/ tests/
uv run ruff check src/ tests/ --fix
uv run mypy src/

# Or using make (auto-detects uv)
make format
make lint
make lint-fix
make type-check
make check-all
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
- `conftest.py` provides `mock_client` fixture (`MagicMock(spec=Auth0Client)`) and `mock_requests` for auth bootstrap tests
- Each module has corresponding test files following `test_*.py` naming
- Tests mock `Auth0Client` methods and assert on `APIResponse` return values
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

## Important Instructions

Do what has been asked; nothing more, nothing less.
NEVER create files unless they're absolutely necessary for achieving your goal.
ALWAYS prefer editing an existing file to creating a new one.
NEVER proactively create documentation files (*.md) or README files. Only create documentation files if explicitly requested by the User.
