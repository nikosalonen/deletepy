# Auth0 User Management Tool

![CodeRabbit Pull Request Reviews](https://img.shields.io/coderabbit/prs/github/nikosalonen/deletepy?utm_source=oss&utm_medium=github&utm_campaign=nikosalonen%2Fdeletepy&labelColor=171717&color=FF570A&link=https%3A%2F%2Fcoderabbit.ai&label=CodeRabbit+Reviews)


A comprehensive Python tool for managing Auth0 users with support for bulk operations across development and production environments. This tool provides safe, rate-limited operations for user management, session control, and domain validation.

## Features

### Core User Operations
- **Delete users** - Permanently remove users from Auth0 with all associated data
- **Block users** - Prevent users from logging in while preserving their data
- **Revoke sessions** - Force logout from all active sessions (Enterprise plan required)
- **Revoke application grants** - Invalidate all authorized applications and refresh tokens

### Advanced Operations
- **Revoke-only mode** (`--revoke-grants-only`) - Revoke sessions and grants without blocking/deleting
- **Block status checking** (`--check-unblocked`) - Identify users who are not currently blocked
- **Domain validation** (`--check-domains`) - Check email domains against blocklists with optional bulk actions
- **Data export** (`--export-last-login`) - Export user last login data to timestamped CSV files
- **Credential testing** (`--doctor`) - Validate Auth0 API credentials and permissions

### Input & Safety Features
- **Multiple input formats** - Support for Auth0 user IDs or email addresses
- **CSV preprocessing** - Convert multi-column CSV files to single-column input using `cleanup_csv.py`
- **Email resolution** - Automatically resolve emails to Auth0 user IDs with multi-user detection
- **Environment separation** - Separate development and production configurations
- **Production safeguards** - Explicit confirmation required for production operations
- **Advanced rate limiting** - Built-in delays with exponential backoff and retry logic
- **Progress tracking** - Real-time progress indicators for bulk operations
- **Graceful shutdown** - Handle interruption signals safely
- **Memory efficient** - Generator-based file processing for large datasets

## Project Structure

The project is organized into several modules:

- `main.py`: Main entry point with operation routing and user confirmation logic
- `auth.py`: Auth0 authentication and token management with timeout handling
- `config.py`: Environment configuration management with dev/prod validation
- `user_operations.py`: Core Auth0 API operations with advanced rate limiting
- `utils.py`: Shared utilities for argument parsing, file reading, and progress display
- `email_domain_checker.py`: Domain validation and blocklist checking
- `rate_limit_config.py`: Rate limiting configuration and batch optimization
- `cleanup_csv.py`: CSV preprocessing utility for input file preparation
- `export_last_login_example.py`: Example script for data export operations

## Prerequisites

- Python 3.x
- Auth0 account with appropriate API permissions
- Auth0 Management API access

## Installation

1. Create and activate virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Create a `.env` file with your Auth0 credentials:
   ```bash
   # Authentication credentials
   CLIENT_ID=your_client_id_here
   CLIENT_SECRET=your_client_secret_here

   # Development credentials
   DEVELOPMENT_CLIENT_ID=your_client_id_here
   DEVELOPMENT_CLIENT_SECRET=your_client_secret_here

   # URLs
   URL=your_custom_domain_here
   DEV_URL=your_dev_custom_domain_here

   AUTH0_DOMAIN=your_auth0_domain_here
   DEV_AUTH0_DOMAIN=your_dev_auth0_domain_here
   ```

   There's also a `.env.example` file that you can use as a template.

## Preparing Input Files

If you have a CSV file (e.g., `ids.csv`) with columns like `ip,userId,userName,user_name_prefix,user_name_suffix`, use the provided `cleanup_csv.py` script to extract a single column of user IDs or emails:

```bash
python cleanup_csv.py
```

This will overwrite `ids.csv` with a single column (no header) suitable for use as input to the main script.

## Usage

1. Prepare a text file (e.g., `users.txt` or cleaned `ids.csv`) containing Auth0 user IDs or email addresses:
   - One ID or email per line
   - No headers or additional columns
   - Example:
     ```
     auth0|123456789
     user@example.com
     ```

2. Run the script:
   ```bash
   python main.py <input_file> [env] [operation_flag]
   ```

   Parameters:
   - `<input_file>`: Path to your file containing user IDs or email addresses
   - `[env]`: Optional environment parameter
     - `dev` (default): Uses development credentials and API
     - `prod`: Uses production credentials and API
   - **Operation flag (required, choose one):**
     - `--block`: Block users instead of deleting them
     - `--delete`: Delete users from Auth0
     - `--revoke-grants-only`: Revoke all application grants and sessions without blocking/deleting
     - `--check-unblocked`: Check which users are not blocked
     - `--check-domains`: Check email domains for block status with optional bulk actions
     - `--export-last-login`: Export user last login data to timestamped CSV
     - `--doctor`: Test Auth0 credentials and API access

   **Note:** You must specify exactly one operation flag. Using more than one will result in an error.

## Usage Examples

### Basic Operations

```bash
# Block users in development environment
python main.py users.txt dev --block

# Delete users in production (requires confirmation)
python main.py users.txt prod --delete

# Revoke sessions and grants only (don't block/delete)
python main.py users.txt dev --revoke-grants-only
```

### Checking Operations

```bash
# Check which users are not blocked
python main.py users.txt dev --check-unblocked

# Check email domains for blocklist status
python main.py emails.txt dev --check-domains

# Export user login data to CSV
python main.py emails.txt dev --export-last-login
```

### Credential Testing

```bash
# Test development credentials
python main.py dev --doctor

# Test production credentials with API access
python main.py prod --doctor --test-api
```

## Operation Details

### Domain Checking (`--check-domains`)
1. Fetches email addresses for each user in the input file
2. Checks each domain against blocklist APIs
3. Categorizes results: BLOCKED, ALLOWED, UNRESOLVABLE, INVALID, ERROR
4. Provides summary with counts for each category
5. For blocked domains, prompts for bulk block/revoke action
6. Temporary result files are cleaned up automatically

### Data Export (`--export-last-login`)
1. Processes email addresses from input file in configurable batches
2. Resolves emails to Auth0 user IDs with comprehensive error handling
3. Fetches user details including last_login timestamps
4. Exports to timestamped CSV with columns:
   - email, user_id, last_login, created_at, updated_at, status
5. Handles edge cases: NOT_FOUND, MULTIPLE_USERS, ERROR_FETCHING_DETAILS
6. Provides time estimates and progress tracking for large datasets
7. Automatic batch size optimization based on dataset size

### Production Safety
- All production operations require explicit "yes" confirmation
- Clear warnings about irreversible actions
- Separate credential sets prevent accidental cross-environment operations

## Notes

- The script requires appropriate Auth0 API permissions:
  - `delete:users` for deletion
  - `update:users` for blocking
  - `delete:sessions` for session revocation (Enterprise plan)
  - `delete:grants` for grant revocation
- **Session revocation** logs the user out of all Auth0 SSO/browser sessions (if supported by your plan).
- **Grant revocation** invalidates all refresh tokens and prevents applications from obtaining new access tokens for the user.
- **Access tokens** already issued remain valid until they expire.
- **Refresh token revocation** is now handled by grant revocation; there is no separate refresh token revocation step.
- Production operations require explicit confirmation
- Advanced rate limiting with exponential backoff prevents API throttling
- All operations are logged with color-coded output
- Multiple user detection for email addresses provides connection details
- Temporary files are automatically cleaned up after operations
- Memory-efficient processing handles large input files

## Testing

Run the test suite with:
```bash
pytest
```
