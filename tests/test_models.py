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
