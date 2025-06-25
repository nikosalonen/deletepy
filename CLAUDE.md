# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview
This is an Auth0 User Management Tool written in Python that allows bulk operations on Auth0 users including deletion, blocking, session/grant revocation, and domain checking. The tool supports both development and production environments with safety confirmations for production operations.

## Architecture
The codebase follows a modular architecture with clear separation of concerns:

- **main.py**: Entry point with argument validation, operation routing, and user confirmation logic
- **auth.py**: Auth0 authentication handling and token management with timeout and error handling
- **config.py**: Environment configuration management with validation for dev/prod environments
- **user_operations.py**: Core Auth0 API operations (delete, block, revoke sessions/grants, user lookups)
- **utils.py**: Shared utilities (argument parsing, file reading, progress display, color output)
- **email_domain_checker.py**: Domain validation and blocking status checking
- **cleanup_csv.py**: CSV preprocessing utility for input file preparation

The application uses a generator pattern for memory-efficient file processing and implements rate limiting (0.2s between API calls) to prevent Auth0 API throttling.

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

# Install dependencies
pip install -r requirements.txt
```

### Running Tests
```bash
# Run all tests
pytest

# Run tests with verbose output
pytest -v

# Run specific test file
pytest tests/test_auth.py

# Run specific test function
pytest tests/test_auth.py::test_get_access_token_success
```

### Main Operations
```bash
# Check authentication configuration
python main.py doctor [dev|prod]

# Block users (dev environment)
python main.py users.txt dev --block

# Delete users (production - requires confirmation)
python main.py users.txt prod --delete

# Revoke grants only
python main.py users.txt dev --revoke-grants-only

# Check unblocked users
python main.py users.txt dev --check-unblocked

# Check email domains
python main.py users.txt dev --check-domains

# Find users by social media IDs (deletes single-identity users, unlinks from multi-identity users)
python main.py social_ids.txt dev --find-social-ids
```

### Code Quality
```bash
# Format code with ruff
ruff format .

# Lint code with ruff
ruff check .

# Fix auto-fixable lint issues
ruff check --fix .
```

## Development Guidelines

### Input File Handling
- Input files should contain one Auth0 user ID or email per line
- The tool handles both Auth0 user IDs (auth0|123456) and email addresses
- Use `cleanup_csv.py` to prepare single-column files from CSV exports
- Large files are processed using generators to minimize memory usage

### Error Handling
- All Auth0 API calls include proper timeout handling (30s for operations, 5s for auth)
- Rate limiting prevents API throttling
- Production operations require explicit confirmation
- Email resolution handles multiple users per email with detailed reporting

### Testing
- Tests use pytest with fixtures for mock objects
- `conftest.py` provides automatic module-based request mocking
- Each module has corresponding test files following `test_*.py` naming
- Tests cover both success and error scenarios for Auth0 API interactions

### Auth0 API Requirements
Required Auth0 Management API scopes:
- `delete:users` - for user deletion
- `update:users` - for user blocking
- `delete:sessions` - for session revocation (Enterprise plan)
- `delete:grants` - for application grant revocation