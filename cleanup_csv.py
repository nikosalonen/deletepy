import csv
import re
from typing import List, Dict, Optional

def find_best_column(headers: List[str]) -> Optional[str]:
    """Find the most likely column containing user identifiers, defaulting to user_id."""
    # First check for exact match of user_id (case insensitive)
    for header in headers:
        if header.lower() == 'user_id':
            return header
    
    # Then use fuzzy matching patterns
    patterns = [
        r'detail\.data\.',
        r'user.*id',
        r'user.*name',
        r'username',
        r'userid',
        r'email',
        r'identifier',
        r'subject',
        r'principal'
    ]
    
    for pattern in patterns:
        for header in headers:
            if re.search(pattern, header.lower()):
                return header
    
    return None

def clean_identifier(value: str) -> str:
    """Clean and normalize user identifiers."""
    if not value or value.strip() == "":
        return ""
    
    value = value.strip()
    
    # Handle both _at_ and __ patterns for email encoding
    if "_at_" in value:
        value = value.replace("_at_", "@")
    elif "__" in value:
        value = value.replace("__", "@")
    
    return value

def extract_identifiers_from_csv(filename: str = "ids.csv") -> List[str]:
    """Extract user identifiers from CSV with fuzzy column matching."""
    identifiers = []
    
    with open(filename, newline="") as infile:
        # Check if file has CSV headers by peeking at first line
        first_line = infile.readline()
        infile.seek(0)
        
        # If first line looks like an Auth0 ID or email, treat as plain text file
        if (first_line.strip().startswith(('auth0|', 'google-oauth2|', 'facebook|', 'github|')) or 
            '@' in first_line or '__' in first_line or '_at_' in first_line):
            print("Detected plain text file with identifiers")
            for line in infile:
                cleaned = clean_identifier(line.strip())
                if cleaned:
                    identifiers.append(cleaned)
            return identifiers
        
        # Otherwise, treat as CSV
        reader = csv.DictReader(infile)
        headers = reader.fieldnames
        
        if not headers:
            print("No headers found in CSV file")
            return identifiers
        
        print(f"Available columns: {', '.join(headers)}")
        
        best_column = find_best_column(headers)
        
        if not best_column:
            print("Could not automatically detect identifier column. Available columns:")
            for i, header in enumerate(headers):
                print(f"  {i}: {header}")
            
            # For automated processing, use first column as fallback
            best_column = headers[0]
            print(f"Using first column as fallback: {best_column}")
        
        print(f"Using column: {best_column}")
        
        for row in reader:
            if best_column in row:
                cleaned = clean_identifier(row[best_column])
                if cleaned:
                    identifiers.append(cleaned)
    
    return identifiers

def write_identifiers_to_file(identifiers: List[str], filename: str = "ids.csv"):
    """Write cleaned identifiers to output file."""
    with open(filename, "w", newline="") as outfile:
        for identifier in identifiers:
            outfile.write(f"{identifier}\n")

if __name__ == "__main__":
    identifiers = extract_identifiers_from_csv()
    if identifiers:
        write_identifiers_to_file(identifiers)
        print(f"Processed {len(identifiers)} identifiers")
    else:
        print("No identifiers found")
