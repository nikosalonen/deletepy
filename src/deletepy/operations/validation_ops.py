"""Smart validation and warning system for Auth0 operations."""

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from ..operations.user_ops import get_user_details
from ..utils.auth_utils import validate_auth0_user_id


@dataclass
class ValidationWarning:
    """Represents a validation warning."""

    severity: str  # "low", "medium", "high", "critical"
    category: str  # "data", "security", "operation", "pattern"
    title: str
    message: str
    affected_items: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    auto_fixable: bool = False

    @property
    def is_critical(self) -> bool:
        """Check if this warning is critical."""
        return self.severity == "critical"

    @property
    def is_high(self) -> bool:
        """Check if this warning is high severity."""
        return self.severity in ["high", "critical"]


@dataclass
class ValidationResult:
    """Results of a validation check."""

    total_items: int
    valid_items: int
    warnings: list[ValidationWarning] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def has_critical_warnings(self) -> bool:
        """Check if there are any critical warnings."""
        return any(w.is_critical for w in self.warnings)

    @property
    def has_high_warnings(self) -> bool:
        """Check if there are any high severity warnings."""
        return any(w.is_high for w in self.warnings)

    @property
    def warning_count_by_severity(self) -> dict[str, int]:
        """Get count of warnings by severity."""
        counts = {"low": 0, "medium": 0, "high": 0, "critical": 0}
        for warning in self.warnings:
            counts[warning.severity] += 1
        return counts

    @property
    def should_block_operation(self) -> bool:
        """Determine if operation should be blocked due to critical issues."""
        return self.has_critical_warnings or len(self.errors) > 0


class SmartValidator:
    """Smart validation service for Auth0 operations."""

    def __init__(self, token: str, base_url: str):
        """Initialize the validator.

        Args:
            token: Auth0 API token
            base_url: Auth0 API base URL
        """
        self.token = token
        self.base_url = base_url
        self.cache = {}  # Simple cache for user details

    def validate_operation(
        self,
        operation: str,
        user_identifiers: list[str],
        environment: str,
        validation_level: str = "standard",
    ) -> ValidationResult:
        """Validate an operation before execution.

        Args:
            operation: Operation type (delete, block, etc.)
            user_identifiers: List of user IDs or emails
            environment: Environment (dev/prod)
            validation_level: Validation strictness (strict/standard/lenient)

        Returns:
            ValidationResult with warnings and errors
        """
        result = ValidationResult(
            total_items=len(user_identifiers),
            valid_items=0,
        )

        # Run validation checks
        self._validate_user_identifiers(user_identifiers, result)
        self._validate_operation_patterns(operation, user_identifiers, result)
        self._validate_environment_safety(
            operation, environment, user_identifiers, result
        )

        if validation_level in ["standard", "strict"]:
            self._validate_user_data(user_identifiers, result)

        if validation_level == "strict":
            self._validate_strict_checks(operation, user_identifiers, result)

        # Calculate valid items (total minus those with errors)
        error_items = set()
        for warning in result.warnings:
            if warning.severity == "critical":
                error_items.update(warning.affected_items)

        result.valid_items = len(user_identifiers) - len(error_items)

        return result

    def _validate_user_identifiers(
        self, identifiers: list[str], result: ValidationResult
    ) -> None:
        """Validate user identifiers format and patterns."""
        email_pattern = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")

        malformed_emails = []
        suspicious_patterns = []
        duplicate_items = []

        # Check for duplicates
        seen = set()
        for identifier in identifiers:
            if identifier in seen:
                duplicate_items.append(identifier)
            seen.add(identifier)

        for identifier in identifiers:
            identifier = identifier.strip()

            # Check if it's an email
            if "@" in identifier:
                if not email_pattern.match(identifier):
                    malformed_emails.append(identifier)

                # Check for suspicious email patterns
                if self._is_suspicious_email(identifier):
                    suspicious_patterns.append(identifier)

            # Check if it's a user ID
            elif identifier.startswith(("auth0|", "google-oauth2|", "facebook|")):
                if not validate_auth0_user_id(identifier):
                    malformed_emails.append(identifier)

            # Check for other suspicious patterns
            elif self._is_suspicious_pattern(identifier):
                suspicious_patterns.append(identifier)

        # Add warnings
        if malformed_emails:
            result.warnings.append(
                ValidationWarning(
                    severity="high",
                    category="data",
                    title="Malformed User Identifiers",
                    message=f"Found {len(malformed_emails)} malformed user identifiers that may cause operation failures",
                    affected_items=malformed_emails,
                    recommendations=[
                        "Verify email addresses are correctly formatted",
                        "Ensure Auth0 user IDs follow the correct pattern",
                        "Consider using --dry-run to preview which users will be affected",
                    ],
                )
            )

        if suspicious_patterns:
            result.warnings.append(
                ValidationWarning(
                    severity="medium",
                    category="pattern",
                    title="Suspicious Patterns Detected",
                    message=f"Found {len(suspicious_patterns)} identifiers with suspicious patterns",
                    affected_items=suspicious_patterns,
                    recommendations=[
                        "Double-check these identifiers for typos",
                        "Verify these are intentional user identifiers",
                        "Consider reviewing the source data",
                    ],
                )
            )

        if duplicate_items:
            result.warnings.append(
                ValidationWarning(
                    severity="low",
                    category="data",
                    title="Duplicate User Identifiers",
                    message=f"Found {len(duplicate_items)} duplicate identifiers",
                    affected_items=duplicate_items,
                    recommendations=[
                        "Remove duplicates to improve performance",
                        "Check if duplicates indicate data quality issues",
                    ],
                    auto_fixable=True,
                )
            )

    def _validate_operation_patterns(
        self, operation: str, identifiers: list[str], result: ValidationResult
    ) -> None:
        """Validate operation-specific patterns."""

        # Check for large batch operations
        if len(identifiers) > 1000:
            result.warnings.append(
                ValidationWarning(
                    severity="high",
                    category="operation",
                    title="Large Batch Operation",
                    message=f"Operation affects {len(identifiers)} users, which may take significant time",
                    affected_items=[],
                    recommendations=[
                        "Consider breaking this into smaller batches",
                        "Use checkpoint functionality to enable resumption",
                        "Schedule during low-traffic periods",
                        "Monitor API rate limits closely",
                    ],
                )
            )

        # Check for potentially dangerous patterns
        if operation == "delete":
            # Check for admin-like emails
            admin_emails = [
                id
                for id in identifiers
                if "@" in id
                and any(
                    pattern in id.lower()
                    for pattern in ["admin", "root", "support", "service"]
                )
            ]

            if admin_emails:
                result.warnings.append(
                    ValidationWarning(
                        severity="critical",
                        category="security",
                        title="Admin Account Deletion Risk",
                        message=f"Found {len(admin_emails)} potentially administrative accounts in deletion list",
                        affected_items=admin_emails,
                        recommendations=[
                            "CRITICAL: Review these accounts carefully before deletion",
                            "Ensure these are not service accounts or admin accounts",
                            "Consider blocking instead of deleting if uncertain",
                            "Verify with team lead or admin before proceeding",
                        ],
                    )
                )

        # Check for bulk operations on similar domains
        if "@" in "".join(identifiers):
            domain_groups = self._group_by_domain(identifiers)
            for domain, emails in domain_groups.items():
                if len(emails) > 50:
                    result.warnings.append(
                        ValidationWarning(
                            severity="medium",
                            category="pattern",
                            title="Bulk Domain Operation",
                            message=f"Operation affects {len(emails)} users from domain {domain}",
                            affected_items=emails[:10],  # Show first 10
                            recommendations=[
                                f"Verify intention to affect entire {domain} domain",
                                "Consider if this indicates a data issue",
                                "Check domain reputation and legitimacy",
                            ],
                        )
                    )

    def _validate_environment_safety(
        self,
        operation: str,
        environment: str,
        identifiers: list[str],
        result: ValidationResult,
    ) -> None:
        """Validate environment-specific safety concerns."""

        # Production environment checks
        if environment == "prod":
            if operation in ["delete", "block"]:
                result.warnings.append(
                    ValidationWarning(
                        severity="high",
                        category="security",
                        title="Production Environment Risk",
                        message=f"Performing {operation} operation on {len(identifiers)} users in PRODUCTION",
                        affected_items=[],
                        recommendations=[
                            "PRODUCTION: Ensure this operation is approved",
                            "Double-check all user identifiers",
                            "Consider testing in dev environment first",
                            "Have rollback plan ready if applicable",
                            "Document the operation for audit purposes",
                        ],
                    )
                )

            # Extra safety for large production operations
            if len(identifiers) > 100:
                result.warnings.append(
                    ValidationWarning(
                        severity="critical",
                        category="security",
                        title="Large Production Operation",
                        message=f"Large scale {operation} operation ({len(identifiers)} users) in PRODUCTION",
                        affected_items=[],
                        recommendations=[
                            "CRITICAL: Ensure proper authorization for this operation",
                            "Use dry-run mode first to verify expected results",
                            "Consider implementing in smaller batches",
                            "Notify relevant stakeholders before proceeding",
                            "Schedule during maintenance window if possible",
                        ],
                    )
                )

    def _validate_user_data(
        self, identifiers: list[str], result: ValidationResult
    ) -> None:
        """Validate user data by checking with Auth0 API."""
        recently_active_users = []
        users_with_roles = []

        # Sample validation (check first 20 users to avoid rate limits)
        sample_size = min(20, len(identifiers))
        sample_identifiers = identifiers[:sample_size]

        for identifier in sample_identifiers:
            try:
                user_details = self._get_cached_user_details(identifier)
                if user_details:
                    # Check for recent activity
                    if self._is_recently_active(user_details):
                        recently_active_users.append(identifier)

                    # Check for roles/permissions
                    if self._has_important_roles(user_details):
                        users_with_roles.append(identifier)

            except Exception:
                # Skip validation errors for individual users
                continue

        # Extrapolate findings to full dataset
        if recently_active_users:
            estimated_active = int(
                len(recently_active_users) * len(identifiers) / sample_size
            )
            result.warnings.append(
                ValidationWarning(
                    severity="medium",
                    category="data",
                    title="Recently Active Users",
                    message=f"Estimated {estimated_active} recently active users in operation (based on sample of {sample_size})",
                    affected_items=recently_active_users,
                    recommendations=[
                        "Consider notifying active users before operation",
                        "Check if these users should be excluded",
                        "Verify operation timing with user activity patterns",
                    ],
                )
            )

        if users_with_roles:
            estimated_roles = int(
                len(users_with_roles) * len(identifiers) / sample_size
            )
            result.warnings.append(
                ValidationWarning(
                    severity="high",
                    category="security",
                    title="Users with Roles/Permissions",
                    message=f"Estimated {estimated_roles} users with roles/permissions in operation (based on sample)",
                    affected_items=users_with_roles,
                    recommendations=[
                        "IMPORTANT: Review users with special roles",
                        "Ensure role removal is intentional",
                        "Check if these are service accounts",
                        "Consider impact on dependent systems",
                    ],
                )
            )

    def _validate_strict_checks(
        self, operation: str, identifiers: list[str], result: ValidationResult
    ) -> None:
        """Perform strict validation checks."""

        # Check for test/development patterns in production
        test_patterns = ["test", "demo", "staging", "dev", "qa", "sandbox"]
        test_like_users = [
            id
            for id in identifiers
            if any(pattern in id.lower() for pattern in test_patterns)
        ]

        if test_like_users:
            result.warnings.append(
                ValidationWarning(
                    severity="low",
                    category="pattern",
                    title="Test-like User Patterns",
                    message=f"Found {len(test_like_users)} users with test-like patterns",
                    affected_items=test_like_users,
                    recommendations=[
                        "Verify these are legitimate user accounts",
                        "Check if these should be handled differently",
                        "Consider if this indicates data quality issues",
                    ],
                )
            )

        # Check for sequential or generated-looking patterns
        sequential_patterns = self._detect_sequential_patterns(identifiers)
        if sequential_patterns:
            result.warnings.append(
                ValidationWarning(
                    severity="medium",
                    category="pattern",
                    title="Sequential Pattern Detected",
                    message=f"Found {len(sequential_patterns)} users with sequential patterns",
                    affected_items=sequential_patterns,
                    recommendations=[
                        "Verify these are real user accounts",
                        "Check if this indicates bot/fake accounts",
                        "Consider additional verification steps",
                    ],
                )
            )

    def _is_suspicious_email(self, email: str) -> bool:
        """Check if email has suspicious patterns."""
        suspicious_patterns = [
            r"(.)\1{3,}",  # Repeated characters
            r"[0-9]{8,}",  # Long sequences of numbers
            r"[a-z]{20,}",  # Very long sequences of letters
            r"test.*\d{3,}",  # Test emails with many numbers
        ]

        return any(re.search(pattern, email.lower()) for pattern in suspicious_patterns)

    def _is_suspicious_pattern(self, identifier: str) -> bool:
        """Check if identifier has suspicious patterns."""
        # Check for obvious test patterns
        test_indicators = ["test", "fake", "dummy", "example", "placeholder"]
        return any(indicator in identifier.lower() for indicator in test_indicators)

    def _group_by_domain(self, identifiers: list[str]) -> dict[str, list[str]]:
        """Group email identifiers by domain."""
        domain_groups = {}
        for identifier in identifiers:
            if "@" in identifier:
                domain = identifier.split("@")[1].lower()
                if domain not in domain_groups:
                    domain_groups[domain] = []
                domain_groups[domain].append(identifier)
        return domain_groups

    def _get_cached_user_details(self, identifier: str) -> dict[str, Any] | None:
        """Get user details with caching."""
        if identifier in self.cache:
            return self.cache[identifier]

        try:
            # Resolve identifier to user ID if needed
            from ..operations.user_ops import get_user_id_from_email

            user_id = identifier
            if "@" in identifier:
                user_id = get_user_id_from_email(identifier, self.token, self.base_url)
                if not user_id:
                    return None

            user_details = get_user_details(user_id, self.token, self.base_url)
            if user_details:
                self.cache[identifier] = user_details
                return user_details

        except Exception:
            pass

        return None

    def _is_recently_active(self, user_details: dict[str, Any]) -> bool:
        """Check if user was recently active."""
        if "last_login" in user_details and user_details["last_login"]:
            try:
                last_login = datetime.fromisoformat(
                    user_details["last_login"].replace("Z", "+00:00")
                )
                return datetime.now(last_login.tzinfo) - last_login < timedelta(days=30)
            except (ValueError, TypeError):
                pass
        return False

    def _has_important_roles(self, user_details: dict[str, Any]) -> bool:
        """Check if user has important roles or permissions."""
        # Check for roles in app_metadata or user_metadata
        metadata_fields = ["app_metadata", "user_metadata"]

        for metadata_field in metadata_fields:
            if metadata_field in user_details and user_details[metadata_field]:
                metadata = user_details[metadata_field]
                if isinstance(metadata, dict):
                    # Check for common role indicators
                    role_indicators = [
                        "roles",
                        "permissions",
                        "groups",
                        "admin",
                        "privileges",
                    ]
                    for indicator in role_indicators:
                        if indicator in metadata and metadata[indicator]:
                            return True

        return False

    def _detect_sequential_patterns(self, identifiers: list[str]) -> list[str]:
        """Detect sequential patterns in identifiers."""
        sequential = []

        # Look for sequential numbers in emails
        email_numbers = {}
        for identifier in identifiers:
            if "@" in identifier:
                # Extract numbers from email
                numbers = re.findall(r"\d+", identifier.split("@")[0])
                if numbers:
                    base_email = re.sub(r"\d+", "X", identifier)
                    if base_email not in email_numbers:
                        email_numbers[base_email] = []
                    email_numbers[base_email].extend([int(n) for n in numbers])

        # Check for sequential patterns
        for base_email, numbers in email_numbers.items():
            if len(numbers) >= 3:
                numbers.sort()
                # Check if numbers are sequential
                is_sequential = all(
                    numbers[i] == numbers[i - 1] + 1 for i in range(1, len(numbers))
                )
                if is_sequential:
                    # Find original emails with this pattern
                    pattern_emails = [
                        id
                        for id in identifiers
                        if re.sub(r"\d+", "X", id) == base_email
                    ]
                    sequential.extend(pattern_emails)

        return sequential


def display_validation_results(result: ValidationResult, operation: str) -> None:
    """Display validation results in a user-friendly format.

    Args:
        result: Validation result to display
        operation: Operation being validated
    """
    from ..utils.display_utils import CYAN, GREEN, RED, RESET, YELLOW

    print(f"\n{CYAN}🔍 VALIDATION RESULTS{RESET}")
    print(f"Operation: {operation}")
    print(f"Total Items: {result.total_items}")
    print(f"Valid Items: {result.valid_items}")

    if result.errors:
        print(f"{RED}Errors: {len(result.errors)}{RESET}")
        for error in result.errors:
            print(f"  ❌ {error}")

    if result.warnings:
        warning_counts = result.warning_count_by_severity
        print(f"\n{YELLOW}Warnings Summary:{RESET}")
        for severity, count in warning_counts.items():
            if count > 0:
                color = (
                    RED
                    if severity == "critical"
                    else YELLOW
                    if severity == "high"
                    else CYAN
                )
                print(f"  {color}{severity.upper()}: {count}{RESET}")

        print(f"\n{YELLOW}Detailed Warnings:{RESET}")
        for warning in result.warnings:
            color = (
                RED
                if warning.severity == "critical"
                else YELLOW
                if warning.severity == "high"
                else CYAN
            )
            icon = (
                "🚨"
                if warning.severity == "critical"
                else "⚠️"
                if warning.severity == "high"
                else "ℹ️"
            )

            print(
                f"\n{color}{icon} {warning.title} [{warning.severity.upper()}]{RESET}"
            )
            print(f"  {warning.message}")

            if warning.affected_items and len(warning.affected_items) <= 5:
                print(f"  Affected items: {', '.join(warning.affected_items)}")
            elif warning.affected_items:
                print(
                    f"  Affected items: {', '.join(warning.affected_items[:3])} ... (+{len(warning.affected_items) - 3} more)"
                )

            if warning.recommendations:
                print("  Recommendations:")
                for rec in warning.recommendations:
                    print(f"    • {rec}")
    else:
        print(f"\n{GREEN}✅ No warnings detected{RESET}")

    # Show operation safety assessment
    if result.should_block_operation:
        print(f"\n{RED}🛑 OPERATION BLOCKED{RESET}")
        print("Critical issues detected that prevent safe operation execution.")
        print("Please resolve the issues above before proceeding.")
    elif result.has_high_warnings:
        print(f"\n{YELLOW}⚠️  HIGH RISK OPERATION{RESET}")
        print(
            "High severity warnings detected. Please review carefully before proceeding."
        )
    else:
        print(f"\n{GREEN}✅ OPERATION APPEARS SAFE{RESET}")
        print("No critical issues detected. Operation may proceed with normal caution.")


def get_validation_level_description(level: str) -> str:
    """Get description of validation level.

    Args:
        level: Validation level (strict/standard/lenient)

    Returns:
        Description of the validation level
    """
    descriptions = {
        "strict": "Comprehensive validation with user data checks and strict pattern detection",
        "standard": "Standard validation with basic user data checks and pattern detection",
        "lenient": "Basic validation focused on data format and critical security issues",
    }
    return descriptions.get(level, "Unknown validation level")
