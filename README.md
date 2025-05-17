# Auth0 User Management Tool

![CodeRabbit Pull Request Reviews](https://img.shields.io/coderabbit/prs/github/nikosalonen/deletepy?utm_source=oss&utm_medium=github&utm_campaign=nikosalonen%2Fdeletepy&labelColor=171717&color=FF570A&link=https%3A%2F%2Fcoderabbit.ai&label=CodeRabbit+Reviews)

A Python script for managing Auth0 users, supporting both development and production environments. This tool can delete or block users, revoke their sessions, revoke all authorized applications (grants), check user block status, and check email domains for block status.

## Features

- Delete or block Auth0 users
- Revoke user sessions (force logout everywhere, if supported by your Auth0 plan)
- Revoke all application grants (authorized applications) for a user
- Support for both development and production environments
- Input can be either Auth0 user IDs or email addresses
- Rate limiting with 0.5s delay between requests
- Production environment safety confirmation
- **New:** Option to revoke all grants and sessions without deleting or blocking users (`--revoke-grants-only`)
- **New:** Check which users are not blocked (`--check-unblocked`)
- **New:** Check email domains for block status and optionally block/revoke users with blocked domains (`--check-domains`)
- **New:** Input file can be prepared from a CSV using `cleanup_csv.py`
- **New:** Modular codebase for better maintainability and extensibility

## Project Structure

The project is organized into several modules:

- `main.py`: Main entry point for the application
- `auth.py`: Authentication and token management
- `config.py`: Configuration and environment management
- `user_operations.py`: Core user management operations
- `utils.py`: Utility functions and helpers
- `email_domain_checker.py`: Email domain validation and checking
- `cleanup_csv.py`: CSV file preparation utility

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
   python main.py users.txt [env] [--block|--delete|--revoke-grants-only|--check-unblocked|--check-domains]
   ```

   Parameters:
   - `users.txt`: Path to your file containing user IDs or email addresses
   - `[env]`: Optional environment parameter
     - `dev` (default): Uses development credentials and API
     - `prod`: Uses production credentials and API
   - **Action flag (required, choose one):**
     - `--block`: Block users instead of deleting them
     - `--delete`: Delete users from Auth0
     - `--revoke-grants-only`: Revoke all application grants (authorized applications) and sessions for each user, without blocking or deleting
     - `--check-unblocked`: Check which users are not blocked (prints unblocked user IDs)
     - `--check-domains`: Check email domains for block status. If blocked domains are found, you will be prompted to block and revoke for those users.

   **Note:** You must specify exactly one of the action flags above. Using more than one will result in an error.

   The script will:
   - Validate the environment and input file
   - Request confirmation before proceeding in production environment
   - Obtain an Auth0 access token
   - Process users one by one with a 0.5s delay between requests
   - For each user:
     - Convert email to user ID if necessary
     - If `--block` or `--delete` is used:
       - Block or delete the user
     - Revoke all user sessions (if supported by your Auth0 plan)
     - Revoke all application grants (authorized applications) for the user

### Domain Checking Workflow (`--check-domains`)

- The script will check the domain of each email/user in the input file.
- Results are saved to `checked_domains_results.json` and user ID to email mappings to `user_id_to_email.json` during the run.
- If blocked domains are found, you will be prompted to confirm blocking and revoking for those users.
- At the end of the run, if these files were written to, they will be emptied (truncated).

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
- Rate limiting is implemented to prevent API throttling
- All operations are logged to the console
- Temporary files `checked_domains_results.json` and `user_id_to_email.json` are emptied at the end of the run if used

## Testing

Run the test suite with:
```bash
pytest
```
