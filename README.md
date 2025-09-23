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

### Checkpoint System

- **Automatic checkpointing** - All operations create recovery points automatically
- **Interruption recovery** - Resume operations from exactly where they left off
- **Progress preservation** - Never lose work on large datasets or long-running operations
- **Production ready** - Robust handling of network failures, system restarts, and interruptions
- **Zero configuration** - Works automatically without any setup or maintenance

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

- **Python 3.11+** - The tool requires Python 3.11 or higher
- Auth0 account with appropriate API permissions
- Auth0 Management API access

### Python Version Management

If you need to install or manage Python versions, we recommend using version managers:

**For macOS:**

- [pyenv](https://github.com/pyenv/pyenv) - Simple Python version management
- [Homebrew](https://brew.sh/) - Package manager that can install Python versions

**For Windows:**

- [pyenv-win](https://github.com/pyenv-win/pyenv-win) - Python version management for Windows (install via `winget install pyenv-win` or download from GitHub)
- [Python.org](https://www.python.org/downloads/) - Official Python installer

**For Linux:**

- [pyenv](https://github.com/pyenv/pyenv) - Simple Python version management
- [asdf](https://asdf-vm.com/) - Extendable version manager with Python plugin

## Installation

### Installation with uv (Recommended)

```bash
# Create or update the virtual environment from the lockfile
uv sync --group dev

# (Optional) Activate the environment if you prefer not to use `uv run`
source .venv/bin/activate

# Verify setup
deletepy doctor dev
```

Alternative via Makefile targets:

```bash
make uv-install        # sync default groups
make uv-install-dev    # sync with dev group
make uv-upgrade        # upgrade lockfile + sync dev
```

### Modern Installation (Recommended)

1. Clone the repository and create virtual environment:

   ```bash
   git clone https://github.com/nikosalonen/deletepy
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
deletepy unlink-social-ids social_ids.txt [dev|prod] [--dry-run]

# User management operations
deletepy users block users.txt [dev|prod] [--dry-run]
deletepy users delete users.txt [dev|prod] [--dry-run]
deletepy users revoke-grants-only users.txt [dev|prod] [--dry-run]
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

```
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
