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

3. Create a `.env` file with your credentials:
   ```bash
   # For dev environment
   DEVELOPMENT_CLIENT_ID=your_dev_client_id
   DEVELOPMENT_CLIENT_SECRET=your_dev_client_secret

   # For prod environment
   CLIENT_ID=your_prod_client_id
   CLIENT_SECRET=your_prod_client_secret
   ```

   You can get your client id and secret from the Auth0 dashboard.

   There's also a `.env.example` file that you can use as a template.

4. Fill user_ids into `ids.csv` (1 per line!)

5. Run the script:
   ```bash
   python delete.py ids.csv [env]
   ```
   where:
   - `ids.csv` is your file containing user IDs
   - `[env]` is optional, either "dev" (default) or "prod"
