# How to use

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
   # For dev environment
   DEVELOPMENT_CLIENT_ID=your_dev_client_id
   DEVELOPMENT_CLIENT_SECRET=your_dev_client_secret
   # Dev API endpoint: tunnus-dev.almamedia.net

   # For prod environment
   CLIENT_ID=your_prod_client_id
   CLIENT_SECRET=your_prod_client_secret
   # Prod API endpoint: tunnus.almamedia.fi
   ```


   There's also a `.env.example` file that you can use as a template.

4. Prepare a CSV file (e.g., `ids.csv`) containing Auth0 user IDs to be deleted:
   - One user ID per line
   - No headers or additional columns
   - IDs should be valid Auth0 user IDs

5. Run the script:
   ```bash
   python delete.py ids.csv [env]
   ```
   Parameters:
   - `ids.csv`: Path to your file containing user IDs
   - `[env]`: Optional environment parameter
     - `dev` (default): Uses development credentials and API
     - `prod`: Uses production credentials and API

   The script will:
   - Validate your input file and environment
   - Obtain an Auth0 access token
   - Delete users one by one with a half second delay between requests
   - Print status messages for each deletion attempt
