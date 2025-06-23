# Export Last Login Functionality

This document describes the new `--export-last-login` operation that allows you to export user last login data to a CSV file.

## Overview

The export-last-login functionality reads a list of email addresses from a file, fetches user data from Auth0, and creates a CSV file containing the users' last login information along with other relevant user details.

## Usage

```bash
python main.py <emails_file> <environment> --export-last-login [--connection <connection_type>]
```

### Parameters

- `emails_file`: Path to a text file containing email addresses (one per line)
- `environment`: Either `dev` or `prod` to specify the Auth0 environment
- `--export-last-login`: The operation flag
- `--connection`: Optional connection filter (e.g., "google-oauth2", "auth0", "facebook")

### Examples

```bash
# Export all users for the emails
python main.py user_emails.txt dev --export-last-login

# Export only Google OAuth users
python main.py user_emails.txt dev --export-last-login --connection google-oauth2

# Export only Auth0 database users
python main.py user_emails.txt dev --export-last-login --connection auth0

# Export only Facebook users
python main.py user_emails.txt dev --export-last-login --connection facebook
```

## Input File Format

Create a text file with one email address per line:

```
user1@example.com
user2@example.com
admin@company.com
test@domain.org
```

## Output

The script generates a CSV file with a timestamp in the filename (e.g., `users_last_login_20241201_143022.csv`) containing the following columns:

- `email`: The email address from the input file
- `user_id`: The Auth0 user ID (or status if not found)
- `connection`: The Auth0 connection type (e.g., "google-oauth2", "auth0", "facebook", etc.)
- `last_login`: The user's last login timestamp
- `created_at`: When the user account was created
- `updated_at`: When the user account was last updated
- `status`: Status of the operation (SUCCESS, NOT_FOUND, MULTIPLE_USERS, ERROR_FETCHING_DETAILS)

### Sample Output

```csv
email,user_id,connection,last_login,created_at,updated_at,status
user1@example.com,auth0|123456789012345678901234,auth0,2024-11-15T10:30:00.000Z,2024-01-15T09:00:00.000Z,2024-11-15T10:30:00.000Z,SUCCESS
user2@example.com,NOT_FOUND,N/A,N/A,N/A,N/A,NOT_FOUND
admin@company.com,auth0|111111111111111111111111,google-oauth2,2024-11-10T14:20:00.000Z,2024-02-01T11:00:00.000Z,2024-11-10T14:20:00.000Z,MULTIPLE_USERS (2)
admin@company.com,auth0|222222222222222222222222,auth0,2024-11-12T09:15:00.000Z,2024-03-01T12:00:00.000Z,2024-11-12T09:15:00.000Z,MULTIPLE_USERS (2)
test@domain.org,auth0|987654321098765432109876,facebook,2024-11-20T14:15:00.000Z,2024-02-01T11:00:00.000Z,2024-11-20T14:15:00.000Z,SUCCESS
```

## Status Codes

- `SUCCESS`: User found and data retrieved successfully
- `NOT_FOUND`: Email address not found in Auth0
- `MULTIPLE_USERS (N)`: Multiple users found with the same email address (all users are included in the output)
- `ERROR_FETCHING_DETAILS`: Error occurred while fetching user details

## Multiple Users Handling

When multiple users are found for the same email address, the system will:

1. **Include all users** in the CSV output (not just the first one)
2. **Add a connection column** to distinguish between different authentication methods
3. **Mark all entries** with the status `MULTIPLE_USERS (N)` where N is the total count
4. **Extract connection information** from the user's `identities` array

This allows you to see all accounts associated with an email address and understand which authentication provider each account uses (e.g., Google OAuth, Facebook, Auth0 database, etc.).

## Connection Filtering

The `--connection` parameter allows you to filter users by their authentication connection type, which can prevent multiple users from occurring:

### How It Works
- **Without filter**: Returns all users for each email address
- **With filter**: Returns only users that match the specified connection type
- **Prevents duplicates**: When filtering by connection, you'll typically get only one user per email

### Common Connection Types
- `auth0`: Auth0 database users (username/password)
- `google-oauth2`: Google OAuth users
- `facebook`: Facebook OAuth users
- `linkedin`: LinkedIn OAuth users
- `twitter`: Twitter OAuth users
- `github`: GitHub OAuth users
- `microsoft`: Microsoft OAuth users

### Benefits of Connection Filtering
1. **Prevents multiple users**: Each email will typically have only one user per connection type
2. **Targeted exports**: Export only users from specific authentication providers
3. **Cleaner data**: Avoid duplicate entries for the same email
4. **Faster processing**: Fewer API calls when filtering is applied

### Example Scenarios
```bash
# Export only Google OAuth users (prevents multiple users per email)
python main.py emails.txt dev --export-last-login --connection google-oauth2

# Export only Auth0 database users
python main.py emails.txt dev --export-last-login --connection auth0

# Export all users (may have multiple users per email)
python main.py emails.txt dev --export-last-login
```

## Rate Limiting and API Limits

The export functionality includes comprehensive rate limiting to respect Auth0's API limits:

### Auth0 API Limits
- **2 requests per second** (120 requests per minute)
- **1000 requests per hour**
- **10000 requests per day**

### Built-in Protection
- **Conservative rate limiting**: 0.5 seconds between requests (2 requests/second max)
- **Exponential backoff**: Automatic retry with increasing delays on rate limit errors
- **Retry logic**: Up to 3 retries with intelligent delay calculation
- **Batch processing**: Processes emails in configurable batches to avoid overwhelming the API
- **Progress tracking**: Real-time progress updates with estimated completion time

### Batch Processing
The system automatically adjusts batch sizes based on dataset size:
- **Small datasets** (< 500 emails): 100 emails per batch
- **Medium datasets** (500-1000 emails): 50 emails per batch
- **Large datasets** (> 1000 emails): 25 emails per batch

### Configuration
You can customize rate limiting behavior by editing `rate_limit_config.py`:
- `API_RATE_LIMIT`: Seconds between API calls (default: 0.5)
- `MAX_RETRIES`: Maximum retry attempts (default: 3)
- `BASE_RETRY_DELAY`: Initial retry delay (default: 1.0 seconds)
- `MAX_RETRY_DELAY`: Maximum retry delay (default: 60.0 seconds)

## Features

- **Progress tracking**: Shows progress as emails are processed
- **Error handling**: Gracefully handles various error conditions
- **Rate limiting**: Respects Auth0 API rate limits with exponential backoff
- **Comprehensive logging**: Provides detailed output and summary
- **Timestamped output**: Creates unique filenames with timestamps
- **Batch processing**: Processes data in configurable batches
- **Resume capability**: Saves progress after each batch
- **Estimated timing**: Shows estimated completion time before starting

## Example Script

See `export_last_login_example.py` for a complete example of how to use this functionality.

## Notes

- The script processes emails sequentially to respect API rate limits
- Users with multiple accounts for the same email are marked as `MULTIPLE_USERS`
- The operation is read-only and does not modify any user data
- Works with both development and production Auth0 environments
- Each email requires 2 API calls (email lookup + user details)
- Processing time scales linearly with the number of emails
- The system will automatically retry on rate limit errors with exponential backoff
