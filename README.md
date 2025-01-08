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
     - `dev` (optional, will default to this if not specified): Uses development credentials and API
     - `prod`: Uses production credentials and API

   The script will:
   - Obtain an Auth0 access token
   - Delete users one by one with a half second delay between requests
