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
3. Fill user_ids into `ids.csv` (1 per line!)
4. Run the script:
   ```bash
   python delete.py ids.csv <TOKEN>
   ```
