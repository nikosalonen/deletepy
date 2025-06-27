# DeletePy - Auth0 User Management Tool

![CodeRabbit Pull Request Reviews](https://img.shields.io/coderabbit/prs/github/nikosalonen/deletepy?utm_source=oss&utm_medium=github&utm_campaign=nikosalonen%2Fdeletepy&labelColor=171717&color=FF570A&link=https%3A%2F%2Fcoderabbit.ai&label=CodeRabbit+Reviews)

A comprehensive Python tool for managing Auth0 users with support for bulk operations across development and production environments. DeletePy provides safe, rate-limited operations for user management, session control, identity management, and domain validation with a modern modular architecture.

## Features

### Core User Operations
- **Delete users** - Permanently remove users from Auth0 with all associated data
- **Block users** - Prevent users from logging in while preserving their data
- **Revoke sessions** - Force logout from all active sessions (Enterprise plan required)
- **Revoke application grants** - Invalidate all authorized applications and refresh tokens

### Advanced Operations
- **Identity unlinking** (`find-social-ids`) - Smart social identity management:
  - Unlinks social identities from multi-identity users
  - Deletes users with only the matching social identity
  - Protects users with Auth0 as main identity
- **Revoke-only mode** (`revoke-grants-only`) - Revoke sessions and grants without blocking/deleting
- **Block status checking** (`check-unblocked`) - Identify users who are not currently blocked
- **Domain validation** (`check-domains`) - Check email domains against blocklists with optional bulk actions
- **Data export** (`export-last-login`) - Export user last login data to timestamped CSV files
- **Credential testing** (`doctor`) - Validate Auth0 API credentials and permissions

### Input & Safety Features
- **Multiple input formats** - Support for Auth0 user IDs, email addresses, or social media IDs
- **CSV preprocessing** - Convert multi-column CSV files to single-column input using cleanup utilities
- **Email resolution** - Automatically resolve emails to Auth0 user IDs with multi-user detection
- **Environment separation** - Separate development and production configurations
- **Production safeguards** - Explicit confirmation required for production operations
- **Advanced rate limiting** - Built-in delays with exponential backoff and retry logic
- **Progress tracking** - Real-time progress indicators for bulk operations
- **Graceful shutdown** - Handle interruption signals safely
- **Memory efficient** - Generator-based file processing for large datasets
- **Robust error handling** - Comprehensive exception handling with detailed error reporting

## Architecture

DeletePy follows a modern modular architecture for maintainability and scalability:

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

### Key Benefits
- **Modular design** - Clear separation of concerns for easier maintenance
- **Type safety** - Comprehensive type hints throughout the codebase
- **Modern CLI** - Click-based command-line interface with better UX
- **Backward compatibility** - Legacy CLI still works with deprecation warnings
- **Test coverage** - Comprehensive test suite with module-based mocking

## Prerequisites

- Python 3.9+
- Auth0 account with appropriate API permissions
- Auth0 Management API access

## Installation

### Modern Installation (Recommended)

1. Clone the repository and create virtual environment:
   ```bash
   git clone <repository-url>
   cd deletepy
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. Install in development mode:
   ```bash
   pip install -e .
   ```

### Traditional Installation

1. Create and activate virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   pip install -e .
   ```

   Or with development dependencies:
   ```bash
   pip install -e ".[dev]"
   ```

### Environment Configuration

Create a `.env` file with your Auth0 credentials:
```bash
# Production credentials
CLIENT_ID=your_prod_client_id_here
CLIENT_SECRET=your_prod_client_secret_here
AUTH0_DOMAIN=your_auth0_domain_here
URL=your_custom_domain_here

# Development credentials
DEV_CLIENT_ID=your_dev_client_id_here
DEV_CLIENT_SECRET=your_dev_client_secret_here
DEV_AUTH0_DOMAIN=your_dev_auth0_domain_here
DEV_URL=your_dev_custom_domain_here
```

There's also a `.env.example` file that you can use as a template.

## Usage

### Modern CLI (Recommended)

```bash
# Check authentication configuration
deletepy doctor [dev|prod]

# Check if specified users are unblocked
deletepy check-unblocked users.txt [dev|prod]

# Check email domains for specified users
deletepy check-domains users.txt [dev|prod]

# Export user last_login data to CSV
deletepy export-last-login emails.txt [dev|prod] [--connection CONNECTION]

# Find users by social media IDs (unlinks identities or deletes users)
deletepy find-social-ids social_ids.txt [dev|prod]

# User management operations
deletepy users block users.txt [dev|prod]
deletepy users delete users.txt [dev|prod]
deletepy users revoke-grants-only users.txt [dev|prod]
```


## Preparing Input Files

### CSV Cleanup Utility

If you have a CSV file with columns like `ip,userId,userName,user_name_prefix,user_name_suffix`, use the provided `cleanup_csv.py` script:

```bash
# Basic cleanup
python cleanup_csv.py

# With specific output type
python cleanup_csv.py --output-type=email
python cleanup_csv.py --output-type=username
python cleanup_csv.py --output-type=user_id

# With environment for Auth0 API resolution
python cleanup_csv.py dev --output-type=email
python cleanup_csv.py prod --output-type=username
```

**Enhanced Features:**
- **Output type control** - Specify identifier type: `user_id`, `email`, or `username`
- **Smart column detection** - Automatically finds the best column
- **Auth0 API integration** - Resolves encoded usernames when environment is specified
- **Rate limiting** - Proper API call throttling to prevent 429 errors

### Input File Formats

1. **User Management Files** - Auth0 user IDs or email addresses:
   ```
   auth0|123456789
   user@example.com
   ```

2. **Social ID Files** - Social media IDs for identity management:
   ```
   10157490928027692
   115346286307134396784
   ```

3. **Email Files** - Email addresses for domain checking or export:
   ```
   user1@example.com
   user2@company.org
   ```

## Operation Details

### Social Identity Management (`find-social-ids`)

DeletePy provides sophisticated social identity management:

- **Single Identity Users**: Users with only the matching social identity are deleted entirely
- **Multi-Identity Users**: Only the matching social identity is unlinked, preserving the user account
- **Protected Users**: Users with Auth0 as main identity are protected from deletion
- **Production Safety**: Explicit confirmation required with operation counts

Example workflow:
1. Provide a file with social media IDs (Facebook, Google, LinkedIn, etc.)
2. DeletePy searches Auth0 for users with those identities
3. Categorizes users based on their identity configuration
4. Performs safe unlinking or deletion based on user type

### Domain Checking (`check-domains`)

1. Fetches email addresses for each user in the input file
2. Checks each domain against blocklist APIs
3. Categorizes results: BLOCKED, ALLOWED, UNRESOLVABLE, INVALID, ERROR
4. Provides summary with counts for each category
5. For blocked domains, prompts for bulk block/revoke action

### Data Export (`export-last-login`)

1. Processes email addresses from input file in configurable batches
2. Resolves emails to Auth0 user IDs with comprehensive error handling
3. Fetches user details including last_login timestamps
4. Exports to timestamped CSV with columns: email, user_id, last_login, created_at, updated_at, status
5. Handles edge cases: NOT_FOUND, MULTIPLE_USERS, ERROR_FETCHING_DETAILS
6. Automatic batch size optimization based on dataset size

### Production Safety

- All production operations require explicit confirmation
- Clear warnings about irreversible actions
- Separate credential sets prevent accidental cross-environment operations
- Detailed operation summaries before execution

## API Permissions

The tool requires appropriate Auth0 Management API scopes:

- `read:users` - for user lookups and identity management
- `delete:users` - for user deletion
- `update:users` - for user blocking
- `delete:sessions` - for session revocation (Enterprise plan)
- `delete:grants` - for application grant revocation

## Development

### Running Tests

```bash
# Install test dependencies
pip install -e .[dev]

# Run all tests
pytest

# Run with coverage
pytest --cov=src/deletepy

# Run specific test file
pytest tests/test_auth.py
```

### Code Quality

```bash
# Format code
ruff format .

# Lint code
ruff check .

# Fix auto-fixable issues
ruff check --fix .

# Type checking (if mypy is installed)
mypy src/
```

## Technical Notes

### Rate Limiting & Performance
- Advanced rate limiting with exponential backoff prevents API throttling
- Memory-efficient generator-based processing for large datasets
- Automatic batch size optimization for export operations
- Graceful handling of interruption signals

### Error Handling
- Comprehensive exception hierarchy for structured error handling
- Detailed error reporting with color-coded output
- Automatic cleanup of temporary files
- Multiple user detection for email addresses with connection details

### Session & Grant Management
- **Session revocation** logs users out of all Auth0 SSO/browser sessions
- **Grant revocation** invalidates all refresh tokens and prevents new access tokens
- **Access tokens** already issued remain valid until they expire
- Grant revocation now handles refresh token invalidation automatically

## Migration from Legacy CLI

The legacy CLI (`main.py`) continues to work with deprecation warnings. To migrate to the modern CLI:

1. Replace `python main.py` with `deletepy`
2. Use the new command structure with subcommands
3. Update any scripts or automation to use the new syntax

## Contributing

1. Follow the established module boundaries
2. Maintain test coverage at 100%
3. Use type hints throughout
4. Follow the function complexity guidelines (max 50 lines per function)
5. Run code quality checks before submitting PRs

## License

[Add your license information here]
