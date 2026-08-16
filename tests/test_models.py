"""Tests for data models."""

import pytest


class TestOperationConfigValidation:
    """Test OperationConfig validation functionality."""

    def test_validate_export_operation_with_output_file(self):
        """Test that export operations pass validation when output_file is provided."""
        from src.deletepy.models.checkpoint import OperationConfig, OperationType

        config = OperationConfig(environment="dev", output_file="test_export.csv")

        # Should not raise any exception
        config.validate_for_operation(OperationType.EXPORT_LAST_LOGIN)

    def test_validate_export_operation_without_output_file(self):
        """Test that export operations fail validation when output_file is missing."""
        from src.deletepy.models.checkpoint import OperationConfig, OperationType

        config = OperationConfig(environment="dev", output_file=None)

        with pytest.raises(
            ValueError, match="output_file is required for export_last_login operations"
        ):
            config.validate_for_operation(OperationType.EXPORT_LAST_LOGIN)

    def test_validate_export_operation_with_empty_output_file(self):
        """Test that export operations fail validation when output_file is empty."""
        from src.deletepy.models.checkpoint import OperationConfig, OperationType

        config = OperationConfig(environment="dev", output_file="")

        with pytest.raises(
            ValueError, match="output_file is required for export_last_login operations"
        ):
            config.validate_for_operation(OperationType.EXPORT_LAST_LOGIN)

    def test_validate_non_export_operations_without_output_file(self):
        """Test that non-export operations don't require output_file."""
        from src.deletepy.models.checkpoint import OperationConfig, OperationType

        config = OperationConfig(environment="dev", output_file=None)

        # These should not raise any exceptions
        config.validate_for_operation(OperationType.BATCH_DELETE)
        config.validate_for_operation(OperationType.BATCH_BLOCK)
        config.validate_for_operation(OperationType.BATCH_REVOKE_GRANTS)
        config.validate_for_operation(OperationType.CHECK_UNBLOCKED)
        config.validate_for_operation(OperationType.SOCIAL_UNLINK)


class TestCheckpointValidation:
    """Test Checkpoint validation functionality."""

    def test_checkpoint_creation_with_valid_export_config(self):
        """Test that creating a checkpoint with valid export config succeeds."""
        from src.deletepy.models.checkpoint import OperationConfig, OperationType
        from src.deletepy.utils.checkpoint_manager import CheckpointManager

        config = OperationConfig(environment="dev", output_file="test_export.csv")

        manager = CheckpointManager()
        checkpoint = manager.create_checkpoint(
            operation_type=OperationType.EXPORT_LAST_LOGIN,
            config=config,
            items=["test1@example.com", "test2@example.com"],
            batch_size=10,
        )

        assert checkpoint.config.output_file == "test_export.csv"

    def test_checkpoint_creation_with_invalid_export_config(self):
        """Test that creating a checkpoint with invalid export config fails."""
        from src.deletepy.models.checkpoint import OperationConfig, OperationType
        from src.deletepy.utils.checkpoint_manager import CheckpointManager

        config = OperationConfig(
            environment="dev",
            output_file=None,  # Missing required field for export
        )

        manager = CheckpointManager()
        with pytest.raises(
            ValueError, match="Cannot create checkpoint.*output_file is required"
        ):
            manager.create_checkpoint(
                operation_type=OperationType.EXPORT_LAST_LOGIN,
                config=config,
                items=["test1@example.com", "test2@example.com"],
                batch_size=10,
            )

    def test_checkpoint_loading_with_invalid_config(self):
        """Test that loading a checkpoint with invalid config fails."""
        from datetime import datetime

        from src.deletepy.models.checkpoint import Checkpoint

        # Create checkpoint data with missing output_file for export operation
        checkpoint_data = {
            "checkpoint_id": "test_checkpoint",
            "operation_type": "export_last_login",
            "status": "active",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "config": {
                "environment": "dev",
                "output_file": None,  # Missing required field
            },
            "progress": {},
            "results": {},
            "remaining_items": ["test@example.com"],
            "processed_items": [],
        }

        with pytest.raises(
            ValueError,
            match="Invalid checkpoint configuration.*output_file is required",
        ):
            Checkpoint.from_dict(checkpoint_data)


class TestProcessingResultsSerialization:
    """Round-trip coverage for ProcessingResults.

    CheckpointManager._update_results dispatches on hasattr(), so a field that
    is dropped from the dataclass or from to_dict is silently discarded rather
    than raising. These tests are the only thing standing between that and a
    lost record of which users a security flag failed to apply to.
    """

    def test_force_otp_lists_round_trip(self):
        from src.deletepy.models.checkpoint import ProcessingResults

        original = ProcessingResults(
            processed_count=3,
            force_otp_failed=["auth0|1", "auth0|2"],
            force_otp_orphaned=["auth0|3"],
        )

        restored = ProcessingResults.from_dict(original.to_dict())

        assert restored.force_otp_failed == ["auth0|1", "auth0|2"]
        assert restored.force_otp_orphaned == ["auth0|3"]
        assert restored.to_dict() == original.to_dict()

    def test_legacy_checkpoint_without_force_otp_keys_deserializes(self):
        """Checkpoints written before the flag existed still load."""
        from src.deletepy.models.checkpoint import ProcessingResults

        restored = ProcessingResults.from_dict({"processed_count": 7})

        assert restored.processed_count == 7
        assert restored.force_otp_failed == []
        assert restored.force_otp_orphaned == []

    def test_update_results_lands_force_otp_keys_on_the_dataclass(self, tmp_path):
        """The results_update key names actually match the dataclass fields."""
        from unittest.mock import MagicMock

        from src.deletepy.models.checkpoint import ProcessingResults
        from src.deletepy.utils.checkpoint_manager import CheckpointManager

        manager = CheckpointManager(checkpoint_dir=str(tmp_path))
        # Only .results is touched; a real ProcessingResults is what matters.
        checkpoint = MagicMock()
        checkpoint.results = ProcessingResults()

        manager._update_results(
            checkpoint,
            {
                "force_otp_failed": ["auth0|1"],
                "force_otp_orphaned": ["auth0|2"],
            },
        )

        assert checkpoint.results.force_otp_failed == ["auth0|1"]
        assert checkpoint.results.force_otp_orphaned == ["auth0|2"]
