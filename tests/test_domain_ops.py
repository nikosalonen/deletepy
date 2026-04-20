"""Tests for domain-ops helpers."""

from unittest.mock import patch

from src.deletepy.operations.domain_ops import check_email_domains


class TestCheckEmailDomainsCaseInsensitivity:
    """Domain-list matching must be case-insensitive."""

    @patch("src.deletepy.operations.domain_ops.shutdown_requested", return_value=False)
    def test_blocked_list_mixed_case(self, _mock_shutdown):
        """A mixed-case entry in blocked_domains must still match a lowercase email domain."""
        result = check_email_domains(
            ["user@gmail.com"],
            blocked_domains=["Gmail.com"],
        )

        assert len(result["blocked"]) == 1
        assert result["blocked"][0]["email"] == "user@gmail.com"
        assert not result["allowed"]

    @patch("src.deletepy.operations.domain_ops.shutdown_requested", return_value=False)
    def test_allowed_list_mixed_case(self, _mock_shutdown):
        """A mixed-case entry in allowed_domains must still match a lowercase email domain."""
        result = check_email_domains(
            ["user@example.com"],
            allowed_domains=["Example.COM"],
        )

        assert len(result["allowed"]) == 1
        assert result["allowed"][0]["email"] == "user@example.com"
        assert not result["blocked"]

    @patch("src.deletepy.operations.domain_ops.shutdown_requested", return_value=False)
    def test_no_domain_lists_all_allowed(self, _mock_shutdown):
        """When no domain lists are provided, valid emails fall into `allowed`."""
        result = check_email_domains(["a@x.com", "b@y.com"])

        assert len(result["allowed"]) == 2
        assert not result["blocked"]


class TestCheckEmailDomainsTotalChecked:
    """`total_checked` must reflect every email that entered the loop."""

    @patch("src.deletepy.operations.domain_ops.shutdown_requested", return_value=False)
    def test_counts_validation_errors(self, _mock_shutdown):
        """Validation failures must still bump total_checked."""
        emails = ["invalid@", "foo@bar.com"]
        result = check_email_domains(emails)

        assert result["total_checked"] == len(emails)
        assert len(result["errors"]) >= 1
