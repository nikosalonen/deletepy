"""Domain operations for Auth0 user management."""

from typing import Any

from ..utils.display_utils import (
    live_progress,
    shutdown_requested,
)
from ..utils.logging_utils import user_output
from ..utils.validators import InputValidator


def check_email_domains(
    emails: list[str],
    allowed_domains: list[str] | None = None,
    blocked_domains: list[str] | None = None,
) -> dict[str, Any]:
    """Check email domains against allowed/blocked domain lists.

    Args:
        emails: List of email addresses to check
        allowed_domains: List of allowed domains (if None, all domains allowed)
        blocked_domains: List of blocked domains (if None, no domains blocked)

    Returns:
        Dict[str, Any]: Results summary with categorized emails
    """
    results: dict[str, Any] = {
        "allowed": [],
        "blocked": [],
        "unknown": [],
        "errors": [],
        "total_checked": 0,
    }

    with live_progress(len(emails), "Checking domains") as advance:
        for email in emails:
            if shutdown_requested():
                break

            try:
                # Validate email format first
                validation_result = InputValidator.validate_email_comprehensive(email)
                if not validation_result.is_valid:
                    results["errors"].append(
                        {
                            "email": email,
                            "reason": f"Invalid email format: {validation_result.error_message}",
                        }
                    )
                    advance()
                    continue

                # Extract domain from email
                domain = email.split("@")[-1].lower() if "@" in email else ""

                if not domain:
                    results["errors"].append(
                        {"email": email, "reason": "Invalid email format"}
                    )
                    advance()
                    continue

                # Check against domain lists
                if blocked_domains and domain in blocked_domains:
                    results["blocked"].append(
                        {
                            "email": email,
                            "domain": domain,
                            "reason": "Domain in blocked list",
                        }
                    )
                elif allowed_domains and domain not in allowed_domains:
                    results["blocked"].append(
                        {
                            "email": email,
                            "domain": domain,
                            "reason": "Domain not in allowed list",
                        }
                    )
                else:
                    results["allowed"].append({"email": email, "domain": domain})

                results["total_checked"] += 1

            except Exception as e:
                results["errors"].append(
                    {"email": email, "reason": f"Error processing: {str(e)}"}
                )

            advance()

    # Display results
    _display_domain_check_results(results, allowed_domains, blocked_domains)

    return results


def _display_domain_check_results(
    results: dict[str, Any],
    allowed_domains: list[str] | None,
    blocked_domains: list[str] | None,
) -> None:
    """Display domain check results summary.

    Args:
        results: Results dictionary from check_email_domains
        allowed_domains: List of allowed domains
        blocked_domains: List of blocked domains
    """
    user_output("\nDomain Check Results:", style="success")
    user_output(f"Total emails checked: {results['total_checked']}")
    user_output(f"Allowed emails: {len(results['allowed'])}")
    user_output(f"Blocked emails: {len(results['blocked'])}")
    user_output(f"Unknown/errors: {len(results['unknown']) + len(results['errors'])}")

    if allowed_domains:
        user_output(f"Allowed domains: {', '.join(allowed_domains)}")
    if blocked_domains:
        user_output(f"Blocked domains: {', '.join(blocked_domains)}")

    if results["blocked"]:
        user_output("\nBlocked emails:", style="warning")
        for item in results["blocked"][:10]:  # Show first 10
            user_output(f"  {item['email']} - {item['reason']}", style="info")
        if len(results["blocked"]) > 10:
            user_output(f"  ... and {len(results['blocked']) - 10} more")

    if results["errors"]:
        user_output("\nErrors:", style="error")
        for item in results["errors"][:5]:  # Show first 5
            user_output(f"  {item['email']} - {item['reason']}", style="info")
        if len(results["errors"]) > 5:
            user_output(f"  ... and {len(results['errors']) - 5} more")


def validate_domain_format(domain: str) -> bool:
    """Validate domain format.

    Args:
        domain: Domain string to validate

    Returns:
        bool: True if valid domain format, False otherwise
    """
    if not domain or len(domain) > 253:
        return False

    # Check for valid characters
    valid_chars = set("abcdefghijklmnopqrstuvwxyz0123456789-.")
    domain_lower = domain.lower()

    for char in domain_lower:
        if char not in valid_chars:
            return False

    # Check for valid structure
    parts = domain_lower.split(".")
    if len(parts) < 2:
        return False

    # Check each part
    for part in parts:
        if not part or len(part) > 63:
            return False
        if part.startswith("-") or part.endswith("-"):
            return False

    return True


def extract_domains_from_emails(emails: list[str]) -> list[str]:
    """Extract unique domains from a list of email addresses.

    Args:
        emails: List of email addresses

    Returns:
        List[str]: List of unique domains
    """
    domains = set()

    for email in emails:
        if "@" in email:
            domain = email.split("@")[-1].lower()
            if validate_domain_format(domain):
                domains.add(domain)

    return sorted(domains)


def get_domain_statistics(emails: list[str]) -> dict[str, int]:
    """Get statistics about domains in email list.

    Args:
        emails: List of email addresses

    Returns:
        Dict[str, int]: Dictionary with domain counts
    """
    domain_counts: dict[str, int] = {}

    for email in emails:
        if "@" in email:
            domain = email.split("@")[-1].lower()
            if validate_domain_format(domain):
                domain_counts[domain] = domain_counts.get(domain, 0) + 1

    return domain_counts


def filter_emails_by_domain(
    emails: list[str], domains: list[str], include: bool = True
) -> list[str]:
    """Filter emails by domain list.

    Args:
        emails: List of email addresses
        domains: List of domains to filter by
        include: If True, include emails from specified domains; if False, exclude them

    Returns:
        List[str]: Filtered list of email addresses
    """
    filtered_emails = []
    domains_set = {domain.lower() for domain in domains}

    for email in emails:
        if "@" in email:
            email_domain = email.split("@")[-1].lower()
            if include:
                if email_domain in domains_set:
                    filtered_emails.append(email)
            else:
                if email_domain not in domains_set:
                    filtered_emails.append(email)

    return filtered_emails
