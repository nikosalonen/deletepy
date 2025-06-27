#!/usr/bin/env python3
"""CSV cleanup utility for Auth0 user management.

This script provides CSV processing functionality for extracting and cleaning
user identifiers from CSV files. It supports various output formats and can
resolve usernames to emails using Auth0 API.
"""

from deletepy.cli.csv_commands import main

if __name__ == "__main__":
    main()