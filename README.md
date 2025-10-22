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

- **Identity unlinking** (`unlink-social-ids`) - Smart social identity management:
  - Unlinks social identities from multi-identity users
  - Deletes users with only the matching social identity
  - Protects users with Auth0 as main identity
- **Revoke-only mode** (`revoke-grants-only`) - Revoke sessions and grants without blocking/deleting
- **Block status checking** (`check-unblocked`) - Identify users who are not currently blocked
- **Domain validation** (`check-domains`) - Check email domains against blocklists with optional bulk actions
- **Data export** (`export-last-login`) - Export user last login data to timestamped CSV files
- **Email fetching** (`fetch-emails`) - Fetch email addresses for given Auth0 user IDs and export to CSV
- **Credential testing** (`doctor`) - Validate Auth0 API credentials and permissions

### Dry-Run Preview

- **Safe preview mode** (`--dry-run`) - Preview what would happen without executing operations
- **Comprehensive analysis** - Shows success rates, potential issues, and user categorization
- **User state detection** - Identifies already blocked users, invalid IDs, and API errors
- **Multiple user detection** - Warns about emails with multiple Auth0 accounts
- **Smart categorization** - For social unlink operations, shows what would be deleted vs unlinked
- **Interactive confirmation** - After preview, choose whether to proceed with actual operation
- **Error resilience** - Preview continues even if some API calls fail, showing partial results

### Input & Safety Features

- **Multiple input formats** - Support for Auth0 user IDs, email addresses, or social media IDs
- **CSV preprocessing** - Convert multi-column CSV files to single-column input using cleanup utilities
- **Email resolution** - Automatically resolve emails to Auth0 user IDs with multi-user detection
- **Environment separation** - Separate development and production configurations
- **Production safeguards** - Explicit confirmation required for production operations
- **Advanced rate limiting** - Built-in delays to respect Auth0 API limits
- **Progress tracking** - Real-time progress indicators for bulk operations
- **Graceful shutdown** - Handle interruption signals safely
- **Memory efficient** - Generator-based file processing for large datasets
- **Robust error handling** - Comprehensive exception handling with detailed error reporting

### Checkpoint & Recovery

- **Automatic checkpointing** - All operations create recovery points automatically
- **Interruption recovery** - Resume operations from exactly where they left off
- **Progress preservation** - Never lose work on large datasets or long-running operations
- **Production ready** - Robust handling of network failures, system restarts, and interruptions
- **Zero configuration** - Works automatically without any setup or maintenance

## Architecture

DeletePy follows a modern modular architecture for maintainability and scalability:

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

- **Python 3.11+** - The tool requires Python 3.11 or higher
- **[uv](https://docs.astral.sh/uv/)** - Fast Python package installer and resolver (recommended)
- Auth0 account with appropriate API permissions
- Auth0 Management API access

### Installing uv

uv is an extremely fast Python package installer and resolver, written in Rust. It's the recommended way to manage DeletePy. **Bonus:** uv can also automatically download and manage Python versions for you!

**For macOS (easiest with Homebrew):**

```bash
brew install uv
```

**For macOS/Linux (standalone installer):**

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**For Windows:**

```powershell
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**Alternative methods:**

- With pip: `pip install uv`

See [uv documentation](https://docs.astral.sh/uv/getting-started/installation/) for more options.

### Python Version Management

**With uv (recommended):**

uv can automatically download and manage Python versions for you:

```bash
# List available Python versions
uv python list

# Install a specific Python version (e.g., Python 3.14)
uv python install 3.14

# Install the minimum required version
uv python install 3.11

# Use a specific Python version when creating the environment
uv sync --python 3.14 --group dev
```

**Alternative version managers:**

If you prefer traditional version managers:

- **macOS:** [pyenv](https://github.com/pyenv/pyenv) or [Homebrew](https://brew.sh/) (`brew install python`)
- **Windows:** [pyenv-win](https://github.com/pyenv-win/pyenv-win) or [Python.org](https://www.python.org/downloads/)
- **Linux:** [pyenv](https://github.com/pyenv/pyenv) or [asdf](https://asdf-vm.com/)

## Installation

### Quick Start with uv (Recommended)

```bash
# Clone the repository
git clone https://github.com/nikosalonen/deletepy
cd deletepy

# (Optional) Install a specific Python version with uv
uv python install 3.14

# Install dependencies with uv (creates .venv automatically)
uv sync --group dev

# Or use a specific Python version
uv sync --python 3.14 --group dev

# Verify setup
uv run deletepy doctor dev
```

**That's it!** You can now use `uv run deletepy` for all commands.

### Using Makefile (Recommended)

The Makefile provides convenient shortcuts for common tasks:

```bash
# Install dependencies
make sync-dev          # Install with dev dependencies (recommended)
make sync              # Install production dependencies only

# Run the tool
make run ARGS="doctor dev"
make run ARGS="users block users.txt dev --dry-run"

# Development tasks
make test              # Run tests
make lint              # Check code quality
make format            # Format code
make type-check        # Run type checking
make check-all         # Run all quality checks

# Upgrade dependencies
make upgrade           # Upgrade all dependencies and sync
```

### Alternative: Traditional pip Installation

If you prefer not to use uv, you can still use pip:

1. Clone the repository and create virtual environment:

   ```bash
   git clone https://github.com/nikosalonen/deletepy
   cd deletepy
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. Install in development mode:

   ```bash
   pip install -e ".[dev]"
   ```

### Logging Configuration

DeletePy defaults to Rich-powered console logging when available. You can control logging via environment variables:

```bash
# Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
export DELETEPY_LOG_LEVEL=INFO

# Log format (rich [default], console, detailed, json)
export DELETEPY_LOG_FORMAT=rich

# Use structured JSON logging
export DELETEPY_LOG_STRUCTURED=false
```

See `docs/LOGGING.md` for full details.

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

### Command Line Interface

All commands can be run with `uv run deletepy` or directly as `deletepy` if you've activated the virtual environment.

**With uv (recommended):**

```bash
# Check authentication configuration
uv run deletepy doctor [dev|prod]

# Check if specified users are unblocked
uv run deletepy check-unblocked users.txt [dev|prod]

# Check email domains for specified users
uv run deletepy check-domains users.txt [dev|prod]

# Export user last_login data to CSV
uv run deletepy export-last-login emails.txt [dev|prod] [--connection CONNECTION]

# Fetch email addresses for given user IDs and export to CSV
uv run deletepy fetch-emails user_ids.txt [dev|prod]

# Find users by social media IDs (unlinks identities or deletes users)
uv run deletepy unlink-social-ids social_ids.txt [dev|prod] [--dry-run]

# User management operations
uv run deletepy users block users.txt [dev|prod] [--dry-run]
uv run deletepy users delete users.txt [dev|prod] [--dry-run]
uv run deletepy users revoke-grants-only users.txt [dev|prod] [--dry-run]
```

**With Makefile:**

```bash
# Run any command using make
make run ARGS="doctor dev"
make run ARGS="users block users.txt dev --dry-run"
make run ARGS="export-last-login emails.txt prod"
```

**Direct (if virtual environment is activated):**

```bash
deletepy doctor dev
deletepy users block users.txt dev --dry-run
```

## Checkpoint System

DeletePy includes a comprehensive checkpoint system that automatically creates recovery points for all major operations. This ensures you can safely resume interrupted operations and never lose progress on large datasets.

### Automatic Checkpointing

**All operations now use checkpoints by default** - no additional configuration needed:

```bash
# These operations automatically create checkpoints
deletepy users delete large_dataset.txt prod
deletepy export-last-login emails.txt dev
deletepy check-unblocked users.txt prod
deletepy unlink-social-ids social_ids.txt dev
```

**Benefits:**

- ✅ **Interruption Safe** - Safely handle Ctrl+C, network failures, or system restarts
- ✅ **Progress Preservation** - Never lose work on large operations
- ✅ **Automatic Resume** - Operations can be resumed from exactly where they left off
- ✅ **Production Ready** - Robust handling of long-running operations
- ✅ **Zero Configuration** - Works automatically without any setup

### Managing Checkpoints

#### List Checkpoints

```bash
# List all checkpoints
deletepy checkpoint list

# List with detailed information
deletepy checkpoint list --details

# Filter by operation type
deletepy checkpoint list --operation-type export-last-login
deletepy checkpoint list --operation-type batch-delete

# Filter by status
deletepy checkpoint list --status active
deletepy checkpoint list --status completed
deletepy checkpoint list --status failed

# Filter by environment
deletepy checkpoint list --env prod
deletepy checkpoint list --env dev

# Combine filters
deletepy checkpoint list --status active --env prod --details
```

#### Resume Operations

```bash
# Resume from a specific checkpoint
deletepy checkpoint resume checkpoint_20241217_142830_export_last_login_dev

# Resume with a different input file (optional)
deletepy checkpoint resume checkpoint_id --input-file new_users.txt
```

**Resume Examples:**

```bash
# Export operation was interrupted
$ deletepy export-last-login emails.txt dev
Processed 1,500/5,000 emails...
^C Operation interrupted. Resume with:
  deletepy checkpoint resume checkpoint_20241217_142830_export_last_login_dev

# Resume the export
$ deletepy checkpoint resume checkpoint_20241217_142830_export_last_login_dev
Resuming export_last_login operation from checkpoint...
Resuming from email 1,501/5,000...
```

#### Checkpoint Details

```bash
# Show detailed information about a specific checkpoint
deletepy checkpoint details checkpoint_20241217_142830_export_last_login_dev
```

**Sample Output:**

```text
📋 Checkpoint Details
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🆔 Checkpoint ID: checkpoint_20241217_142830_export_last_login_dev
📊 Operation: export_last_login
🔄 Status: active
🌍 Environment: dev
📅 Created: 2024-12-17 14:28:30
🔄 Updated: 2024-12-17 14:35:15
📁 Input File: /path/to/emails.txt
📄 Output File: users_last_login_20241217_142830.csv

📈 Progress Information
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 Completion: 30.0% (1,500/5,000 items)
✅ Success Rate: 95.5% (1,433/1,500 processed)
📦 Current Batch: 30/100
📋 Batch Size: 50

📊 Processing Results
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ Processed: 1,433
⏭️  Skipped: 45
❌ Errors: 22
🔍 Not Found: 35
👥 Multiple Users: 10

▶️ Resumable: Yes
```

### Checkpoint Cleanup

#### Clean Completed Checkpoints

```bash
# Clean all completed checkpoints (regardless of age)
deletepy checkpoint clean --completed

# Preview what would be cleaned
deletepy checkpoint clean --completed --dry-run
```

#### Clean Failed Checkpoints

```bash
# Clean only failed checkpoints
deletepy checkpoint clean --failed
```

#### Clean Old Checkpoints

```bash
# Clean checkpoints older than 30 days (default)
deletepy checkpoint clean

# Clean checkpoints older than 7 days
deletepy checkpoint clean --days-old 7

# Preview cleanup
deletepy checkpoint clean --days-old 14 --dry-run
```

#### Clean All Checkpoints (Use with Caution)

```bash
# Clean ALL checkpoints - use with extreme caution
deletepy checkpoint clean --all

# Preview before cleaning all
deletepy checkpoint clean --all --dry-run
```

#### Delete Specific Checkpoint

```bash
# Delete a specific checkpoint with confirmation
deletepy checkpoint delete checkpoint_20241217_142830_export_last_login_dev

# Delete without confirmation prompt
deletepy checkpoint delete checkpoint_id --confirm
```

### When Checkpoints Are Created

Checkpoints are automatically created for these operations:

| Operation | Checkpoint Type | Use Case |
|-----------|----------------|----------|
| `deletepy users delete` | `batch_delete` | User deletion operations |
| `deletepy users block` | `batch_block` | User blocking operations |
| `deletepy users revoke-grants-only` | `batch_revoke_grants` | Grant/session revocation |
| `deletepy export-last-login` | `export_last_login` | Data export operations |
| `deletepy fetch-emails` | `fetch_emails` | Email fetching operations |
| `deletepy check-unblocked` | `check_unblocked` | Status checking operations |
| `deletepy unlink-social-ids` | `social_unlink` | Identity management operations |

### Storage and File Management

- **Location**: Checkpoints are stored in `.checkpoints/` directory
- **Format**: JSON files with structured metadata and progress tracking
- **Backups**: Automatic backup files created during updates (`.backup` extension)
- **Cleanup**: Automatic cleanup of backup files when checkpoints are deleted
- **Size**: Checkpoint files are typically small (1-10KB) but scale with dataset size

### Advanced Features

#### Production Safety with Checkpoints

- Checkpoints preserve environment information to prevent cross-environment resume
- Production checkpoints require the same safety confirmations when resumed
- Failed production operations can be safely resumed after fixing underlying issues

#### Error Recovery

- Failed operations create checkpoints with error details for debugging
- Resume operations can handle partial failures and continue processing
- Graceful handling of network issues and API errors

#### Performance Optimization

- Batch processing state is preserved across interruptions
- Optimal batch sizes are maintained when resuming
- Rate limiting state is reset appropriately on resume

## Preparing Input Files

### CSV Cleanup Utility

If you have a CSV file with columns like `ip,userId,userName,user_name_prefix,user_name_suffix`, use the built-in cleanup-csv command:

```bash
# Basic cleanup
deletepy cleanup-csv

# With specific output type
deletepy cleanup-csv --output-type=email
deletepy cleanup-csv --output-type=username
deletepy cleanup-csv --output-type=user_id

# With environment for Auth0 API resolution
deletepy cleanup-csv ids.csv dev --output-type=email
deletepy cleanup-csv ids.csv prod --output-type=username
```

**Enhanced Features:**

- **Output type control** - Specify identifier type: `user_id`, `email`, or `username`
- **Smart column detection** - Automatically finds the best column
- **Auth0 API integration** - Resolves encoded usernames when environment is specified
- **Rate limiting** - Proper API call throttling to prevent 429 errors

### Input File Formats

1. **User Management Files** - Auth0 user IDs or email addresses:

   ```text
   auth0|123456789
   user@example.com
   ```

2. **Social ID Files** - Social media IDs for identity management:

   ```text
   10157490928027692
   115346286307134396784
   ```

3. **Email Files** - Email addresses for domain checking or export:

   ```text
   user1@example.com
   user2@company.org
   ```

4. **User ID Files** - Auth0 user IDs for email fetching:

   ```text
   auth0|123456789
   google-oauth2|987654321
   facebook|555666777
   ```

## Operation Details

### Social Identity Management (`unlink-social-ids`)

DeletePy provides sophisticated social identity management:

- **Single Identity Users**: Users with only the matching social identity are deleted entirely
- **Multi-Identity Users**: Only the matching social identity is unlinked, preserving the user account
- **Detached Identity Cleanup**: After unlinking, if a user has no remaining identities, the user is automatically deleted
- **Detached Social User Deletion**: Separate user accounts that have the unlinked social ID as their primary identity are automatically deleted
- **Protected Users**: Users with Auth0 as main identity are protected from deletion
- **Production Safety**: Explicit confirmation required with operation counts

Example workflow:

1. Provide a file with social media IDs (Facebook, Google, LinkedIn, etc.)
2. DeletePy searches Auth0 for users with those identities
3. Categorizes users based on their identity configuration
4. Performs safe unlinking or deletion based on user type
5. Automatically deletes users who become orphaned (no remaining identities) after unlinking
6. Searches for and deletes any separate user accounts that have the unlinked social ID as their primary identity

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

### Email Fetching (`fetch-emails`)

1. Processes Auth0 user IDs from input file in configurable batches
2. Fetches email addresses for each user ID with comprehensive error handling
3. Exports to timestamped CSV with columns: user_id, email, status
4. Handles edge cases: NOT_FOUND, ERROR_FETCHING
5. Automatic batch size optimization based on dataset size
6. Supports checkpoint recovery for interrupted operations

### Dry-Run Preview Operations

DeletePy includes comprehensive dry-run preview functionality for all destructive operations:

#### User Operations Preview (`--dry-run`)

```bash
# Preview blocking users
deletepy users block users.txt dev --dry-run

# Preview deleting users
deletepy users delete users.txt prod --dry-run

# Preview revoking grants
deletepy users revoke-grants-only users.txt dev --dry-run
```

**Preview Information Includes:**

- **Success Analysis**: Number of users that would be processed successfully
- **Success Rate**: Percentage of successful operations
- **User Categorization**:
  - ✅ Valid users that would be processed
  - ⚠️ Users already in target state (e.g., already blocked)
  - ❌ Invalid user IDs or malformed identifiers
  - ❌ Users not found (emails that don't exist in Auth0)
  - ⚠️ Emails with multiple users (requires manual resolution)
  - ❌ API errors or network issues
- **Detailed User Information**: Connection type, current blocked status, last login
- **Interactive Confirmation**: Choose whether to proceed after preview

#### Social Unlink Preview (`--dry-run`)

```bash
# Preview social identity operations
deletepy unlink-social-ids social_ids.txt dev --dry-run
```

**Social Preview Shows:**

- **Users to Delete**: Users where the social ID is their only/main identity
- **Identities to Unlink**: Users with multiple identities where only the social identity will be removed
- **Protected Users**: Users with Auth0 as main identity (will be skipped)
- **Detailed Reasoning**: Why each user falls into their category
- **Operation Counts**: Total numbers for each type of operation

#### Preview Benefits

1. **Risk Reduction**: See exactly what will happen before execution
2. **Data Validation**: Identify invalid inputs or missing users early
3. **Scope Verification**: Confirm you're targeting the right users
4. **Error Detection**: Find API issues or authentication problems before bulk operations
5. **Performance Estimation**: Understand how long the actual operation will take
6. **Compliance**: Review operations for audit trails in sensitive environments

### Production Safety

- All production operations require explicit confirmation
- Clear warnings about irreversible actions
- Separate credential sets prevent accidental cross-environment operations
- Detailed operation summaries before execution
- **Dry-run recommended** for all production operations

## API Permissions

The tool requires appropriate Auth0 Management API scopes:

- `read:users` - for user lookups and identity management
- `delete:users` - for user deletion
- `update:users` - for user blocking
- `delete:sessions` - for session revocation (Enterprise plan)
- `delete:grants` - for application grant revocation

## Development

### Setup Development Environment

```bash
# Install with development dependencies
uv sync --group dev

# Or using make
make sync-dev
```

### Running Tests

```bash
# Run all tests (with uv)
uv run pytest

# Or using make (automatically uses uv if available)
make test

# Run with coverage
make test-coverage

# Run specific test file
uv run pytest tests/test_auth.py
```

### Code Quality

```bash
# Format code
make format
# or: uv run ruff format src/ tests/

# Lint code
make lint
# or: uv run ruff check src/ tests/

# Fix auto-fixable issues
make lint-fix
# or: uv run ruff check src/ tests/ --fix

# Type checking
make type-check
# or: uv run mypy src/

# Run all quality checks
make check-all
```

### Pre-commit Hooks

```bash
# Install pre-commit hooks
make install-pre-commit
# or: uv run pre-commit install

# Update hooks
make update-pre-commit
# or: uv run pre-commit autoupdate
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
