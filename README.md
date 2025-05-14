# Auth0 User Management Tool

A Python script for managing Auth0 users, supporting both development and production environments. This tool can delete or block users, revoke their sessions and refresh tokens.

## Features

- Delete or block Auth0 users
- Revoke user sessions and refresh tokens
- Support for both development and production environments
- Input can be either Auth0 user IDs or email addresses
- Rate limiting with 0.5s delay between requests
- Production environment safety confirmation

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

## Usage

1. Prepare a text file (e.g., `users.txt`) containing Auth0 user IDs or email addresses:
   - One ID or email per line
   - No headers or additional columns
   - Example:
     ```
     auth0|123456789
     user@example.com
     ```

2. Run the script:
   ```bash
   python delete.py users.txt [env] [--block|--delete]
   ```

   Parameters:
   - `users.txt`: Path to your file containing user IDs or email addresses
   - `[env]`: Optional environment parameter
     - `dev` (default): Uses development credentials and API
     - `prod`: Uses production credentials and API
   - Action flag (required):
     - `--block`: Block users instead of deleting them
     - `--delete`: Delete users from Auth0

   The script will:
   - Validate the environment and input file
   - Request confirmation before proceeding in production environment
   - Obtain an Auth0 access token
   - Process users one by one with a 0.5s delay between requests
   - For each user:
     - Convert email to user ID if necessary
     - Block or delete the user
     - Revoke all user sessions
     - Revoke all refresh tokens

## Notes

- The script requires appropriate Auth0 API permissions:
  - `delete:users` for deletion
  - `update:users` for blocking
  - `delete:sessions` for session revocation (Enterprise plan)
  - `delete:refresh_tokens` for refresh token revocation (Enterprise plan)
- Production operations require explicit confirmation
- Rate limiting is implemented to prevent API throttling
- All operations are logged to the console

## Testing

Run the test suite with:
```bash
pytest
```
