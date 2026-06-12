"""Domain operations for Auth0 user management."""

from typing import Any

from ..utils.display_utils import (
    live_progress,
    shutdown_requested,
)
from ..utils.logging_utils import user_output
from ..utils.validators import InputValidator


def _normalize_domain_sets(
    allowed_domains: list[str] | None,
    blocked_domains: list[str] | None,
) -> tuple[set[str] | None, set[str] | None]:
    """Lower-case allowed/blocked lists once for O(1) case-insensitive lookups."""
    allowed_set = {d.lower() for d in allowed_domains} if allowed_domains else None
    blocked_set = {d.lower() for d in blocked_domains} if blocked_domains else None
    return allowed_set, blocked_set


def _classify_email_domain(
    email: str,
    allowed_set: set[str] | None,
    blocked_set: set[str] | None,
) -> tuple[str, dict[str, str]]:
    """Classify a single email into (category, entry) for aggregation."""
    validation_result = InputValidator.validate_email_comprehensive(email)
    if not validation_result.is_valid:
        return "errors", {
            "email": email,
            "reason": f"Invalid email format: {validation_result.error_message}",
        }

    domain = email.split("@")[-1].lower() if "@" in email else ""
    if not domain:
        return "errors", {"email": email, "reason": "Invalid email format"}

    if blocked_set and domain in blocked_set:
        return "blocked", {
            "email": email,
            "domain": domain,
            "reason": "Domain in blocked list",
        }
    if allowed_set and domain not in allowed_set:
        return "blocked", {
            "email": email,
            "domain": domain,
            "reason": "Domain not in allowed list",
        }
    return "allowed", {"email": email, "domain": domain}


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

    allowed_set, blocked_set = _normalize_domain_sets(allowed_domains, blocked_domains)

    with live_progress(len(emails), "Checking domains") as advance:
        for email in emails:
            if shutdown_requested():
                break

            results["total_checked"] += 1
            try:
                category, entry = _classify_email_domain(
                    email, allowed_set, blocked_set
                )
                results[category].append(entry)
            except Exception as e:
                results["errors"].append(
                    {"email": email, "reason": f"Error processing: {str(e)}"}
                )
            advance()

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
