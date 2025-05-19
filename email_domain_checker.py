import os
import sys
import requests
from dotenv import load_dotenv
import json
from utils import show_progress

# Load .env
load_dotenv()

API_KEY = os.getenv("ISTEMPMAIL_API_KEY")
if not API_KEY:
    sys.exit("Error: ISTEMPMAIL_API_KEY not found in .env")

API_URL = "https://www.istempmail.com/api/check/{apikey}/{domain}"
CACHE_FILE = "domain_cache.json"

CYAN = "\033[96m"
RESET = "\033[0m"

def extract_domain(email):
    if "@" not in email:
        return email
    return email.split("@")[-1].lower()

def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_cache(cache):
    try:
        with open(CACHE_FILE, "w") as f:
            json.dump(cache, f, indent=2)
    except Exception as e:
        print(f"Warning: Could not save cache: {e}")

def check_domain(domain, cache):
    if not API_KEY:
        print("Warning: ISTEMPMAIL_API_KEY not found in .env")
        return None
        
    if domain in cache:
        print(f"[CACHE] Domain {domain} found in cache.")
        return cache[domain]
    url = API_URL.format(apikey=API_KEY, domain=domain)
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        cache[domain] = data
        save_cache(cache)
        return data
    except Exception as e:
        print(f"Error checking domain {domain}: {e}")
        return None

def check_domains_for_emails(emails):
    if not API_KEY:
        print("Warning: ISTEMPMAIL_API_KEY not found in .env")
        return
        
    cache = load_cache()
    total = len(emails)
    for idx, email in enumerate(emails):
        domain = extract_domain(email)
        print(f"{CYAN}Checking {idx+1}/{total}: {email}{RESET}")
        if not domain:
            print(f"Invalid email: {email}")
            continue
        if domain == "privaterelay.appleid.com":
            print(f"{email} ({domain}): IGNORED (Apple private relay domain)")
            continue
        result = check_domain(domain, cache)
        if not result:
            print(f"{email}: Could not check domain {domain}")
            continue
        status = []
        if result.get("blocked"):
            status.append("BLOCKED")
        if result.get("unresolvable"):
            status.append("UNRESOLVABLE")
        if not status:
            status.append("ALLOWED")
        print(f"{email} ({domain}): {', '.join(status)}")

def check_domains_status_for_emails(emails):
    if not API_KEY:
        print("Warning: ISTEMPMAIL_API_KEY not found in .env")
        return {}
        
    cache = load_cache()
    results = {}
    total_emails = len(emails)
    
    for idx, email in enumerate(emails, 1):
        show_progress(idx, total_emails, "Checking domains")
        domain = extract_domain(email)
        if not domain:
            results[email] = ["INVALID"]
            continue
        if domain == "privaterelay.appleid.com":
            results[email] = ["IGNORED"]
            continue
        result = check_domain(domain, cache)
        if not result:
            results[email] = ["ERROR"]
            continue
        status = []
        if result.get("blocked"):
            status.append("BLOCKED")
        if result.get("unresolvable"):
            status.append("UNRESOLVABLE")
        if not status:
            status.append("ALLOWED")
        results[email] = status
    
    print("\n")  # Clear progress line
    return results

# CLI usage
if __name__ == "__main__":
    if not API_KEY:
        sys.exit("Error: ISTEMPMAIL_API_KEY not found in .env")
    if len(sys.argv) < 2:
        print("Usage: python email_domain_checker.py <email1> [<email2> ...]")
        sys.exit(1)
    emails = sys.argv[1:]
    check_domains_for_emails(emails)
