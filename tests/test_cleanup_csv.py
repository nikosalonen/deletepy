import tempfile
import os
import csv
from src.deletepy.utils.csv_utils import (
    find_best_column,
    clean_identifier,
    extract_identifiers_from_csv,
    write_identifiers_to_file,
)


class TestFindBestColumn:
    def test_finds_detail_data_pattern(self):
        headers = ["timestamp", "detail.data.userId", "region"]
        result = find_best_column(headers)
        assert result == "detail.data.userId"

    def test_finds_username_pattern(self):
        headers = ["id", "userName", "status"]
        result = find_best_column(headers)
        assert result == "userName"

    def test_finds_userid_pattern(self):
        headers = ["created", "userId", "active"]
        result = find_best_column(headers)
        assert result == "userId"

    def test_finds_email_pattern(self):
        headers = ["name", "email", "phone"]
        result = find_best_column(headers)
        assert result == "email"

    def test_case_insensitive_matching(self):
        headers = ["ID", "USERNAME", "EMAIL"]
        result = find_best_column(headers)
        assert result == "USERNAME"

    def test_returns_none_for_no_match(self):
        headers = ["column1", "column2", "column3"]
        result = find_best_column(headers)
        assert result is None


class TestCleanIdentifier:
    def test_cleans_at_pattern(self):
        result = clean_identifier("user_at_example.com")
        assert result == "user@example.com"

    def test_cleans_double_underscore_pattern(self):
        result = clean_identifier("user__example.com")
        assert result == "user@example.com"

    def test_strips_whitespace(self):
        result = clean_identifier("  user@example.com  ")
        assert result == "user@example.com"

    def test_handles_empty_string(self):
        result = clean_identifier("")
        assert result == ""

    def test_handles_none(self):
        result = clean_identifier(None)
        assert result == ""

    def test_handles_whitespace_only(self):
        result = clean_identifier("   ")
        assert result == ""

    def test_preserves_auth0_ids(self):
        result = clean_identifier("auth0|123456789")
        assert result == "auth0|123456789"

    def test_preserves_normal_emails(self):
        result = clean_identifier("user@example.com")
        assert result == "user@example.com"


class TestExtractIdentifiersFromCSV:
    def test_detects_plain_text_auth0_ids(self):
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".csv") as temp:
            temp.write("auth0|123456789\nauth0|987654321\n")
            temp_path = temp.name

        try:
            result = extract_identifiers_from_csv(temp_path)
            assert len(result) == 2
            assert result == ["auth0|123456789", "auth0|987654321"]
        finally:
            os.unlink(temp_path)

    def test_detects_plain_text_emails_with_at(self):
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".csv") as temp:
            temp.write("user@example.com\ntest@domain.org\n")
            temp_path = temp.name

        try:
            result = extract_identifiers_from_csv(temp_path)
            assert len(result) == 2
            assert result == ["user@example.com", "test@domain.org"]
        finally:
            os.unlink(temp_path)

    def test_detects_plain_text_emails_with_underscore_patterns(self):
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".csv") as temp:
            temp.write("user_at_example.com\ntest__domain.org\n")
            temp_path = temp.name

        try:
            result = extract_identifiers_from_csv(temp_path)
            assert len(result) == 2
            assert result == ["user@example.com", "test@domain.org"]
        finally:
            os.unlink(temp_path)

    def test_processes_csv_with_detail_data_column(self):
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".csv") as temp:
            writer = csv.writer(temp)
            writer.writerow(["timestamp", "detail.data.userId", "status"])
            writer.writerow(["2023-01-01", "auth0|123456789", "success"])
            writer.writerow(["2023-01-02", "auth0|987654321", "failed"])
            temp_path = temp.name

        try:
            result = extract_identifiers_from_csv(temp_path)
            assert len(result) == 2
            assert result == ["auth0|123456789", "auth0|987654321"]
        finally:
            os.unlink(temp_path)

    def test_processes_csv_with_username_column(self):
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".csv") as temp:
            writer = csv.writer(temp)
            writer.writerow(["id", "userName", "active"])
            writer.writerow(["1", "user_at_example.com", "true"])
            writer.writerow(["2", "test__domain.org", "false"])
            temp_path = temp.name

        try:
            # Use non-interactive mode to avoid prompts during testing
            result = extract_identifiers_from_csv(
                temp_path, env=None, output_type="user_id", interactive=False
            )
            assert len(result) == 2
            assert result == ["user@example.com", "test@domain.org"]
        finally:
            os.unlink(temp_path)

    def test_fallback_to_first_column(self):
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".csv") as temp:
            writer = csv.writer(temp)
            writer.writerow(["random_col", "other_col"])
            writer.writerow(["auth0|123456789", "data"])
            writer.writerow(["auth0|987654321", "more_data"])
            temp_path = temp.name

        try:
            result = extract_identifiers_from_csv(temp_path)
            assert len(result) == 2
            assert result == ["auth0|123456789", "auth0|987654321"]
        finally:
            os.unlink(temp_path)

    def test_skips_empty_identifiers(self):
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".csv") as temp:
            temp.write("auth0|123456789\n\n   \nauth0|987654321\n")
            temp_path = temp.name

        try:
            result = extract_identifiers_from_csv(temp_path)
            assert len(result) == 2
            assert result == ["auth0|123456789", "auth0|987654321"]
        finally:
            os.unlink(temp_path)


class TestWriteIdentifiersToFile:
    def test_writes_identifiers_to_file(self):
        identifiers = ["auth0|123456789", "user@example.com", "auth0|987654321"]

        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".csv") as temp:
            temp_path = temp.name

        try:
            write_identifiers_to_file(identifiers, temp_path)

            with open(temp_path, "r") as f:
                content = f.read().strip()
                lines = content.split("\n")
                assert len(lines) == 3
                assert lines == identifiers
        finally:
            os.unlink(temp_path)

    def test_writes_empty_list(self):
        identifiers = []

        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".csv") as temp:
            temp_path = temp.name

        try:
            write_identifiers_to_file(identifiers, temp_path)

            with open(temp_path, "r") as f:
                content = f.read()
                assert content == ""
        finally:
            os.unlink(temp_path)
