"""Tests for checkpoint management utilities."""

import tempfile
from unittest.mock import MagicMock, patch

import pytest

from src.deletepy.models.checkpoint import (
    Checkpoint,
    CheckpointStatus,
    OperationType,
)
from src.deletepy.utils.checkpoint_manager import CheckpointManager
from src.deletepy.utils.checkpoint_utils import (
    CheckpointConfig,
    CheckpointResult,
    create_checkpoint,
    finalize_checkpoint,
    handle_checkpoint_error,
    handle_checkpoint_interruption,
    load_or_create_checkpoint,
    try_load_checkpoint,
    update_checkpoint_batch,
)


class TestCheckpointConfig:
    """Tests for CheckpointConfig dataclass."""

    def test_config_creation(self):
        """Test creating checkpoint config with required fields."""
        config = CheckpointConfig(
            operation_type=OperationType.BATCH_DELETE,
            env="dev",
            items=["auth0|123", "auth0|456"],
        )

        assert config.operation_type == OperationType.BATCH_DELETE
        assert config.env == "dev"
        assert len(config.items) == 2
        assert config.batch_size == 50  # default
        assert config.auto_delete is True  # default
        assert config.operation_name == "operation"  # default

    def test_config_with_custom_values(self):
        """Test creating config with custom values."""
        config = CheckpointConfig(
            operation_type=OperationType.SOCIAL_UNLINK,
            env="prod",
            items=["123"],
            batch_size=100,
            auto_delete=False,
            operation_name="social unlink",
            additional_params={"rotate_password": True},
        )

        assert config.batch_size == 100
        assert config.auto_delete is False
        assert config.operation_name == "social unlink"
        assert config.additional_params == {"rotate_password": True}

    def test_config_with_none_additional_params(self):
        """Test that None additional_params is handled."""
        config = CheckpointConfig(
            operation_type=OperationType.BATCH_DELETE,
            env="dev",
            items=["auth0|123"],
            additional_params=None,
        )

        assert config.additional_params is None


class TestCheckpointResult:
    """Tests for CheckpointResult dataclass."""

    def test_result_creation(self):
        """Test creating checkpoint result."""
        checkpoint = MagicMock(spec=Checkpoint)
        manager = MagicMock(spec=CheckpointManager)

        result = CheckpointResult(
            checkpoint=checkpoint,
            checkpoint_manager=manager,
            env="dev",
            auto_delete=True,
            is_resuming=False,
        )

        assert result.checkpoint is checkpoint
        assert result.checkpoint_manager is manager
        assert result.env == "dev"
        assert result.auto_delete is True
        assert result.is_resuming is False


class TestTryLoadCheckpoint:
    """Tests for try_load_checkpoint function."""

    def test_load_none_checkpoint_id(self):
        """Test loading with None checkpoint ID returns None."""
        manager = MagicMock(spec=CheckpointManager)

        result = try_load_checkpoint(None, manager, "test operation")

        assert result is None
        manager.load_checkpoint.assert_not_called()

    def test_load_empty_checkpoint_id(self):
        """Test loading with empty checkpoint ID returns None."""
        manager = MagicMock(spec=CheckpointManager)

        result = try_load_checkpoint("", manager, "test operation")

        assert result is None

    @patch("src.deletepy.utils.checkpoint_utils.print_warning")
    def test_load_nonexistent_checkpoint(self, mock_print):
        """Test loading nonexistent checkpoint returns None."""
        manager = MagicMock(spec=CheckpointManager)
        manager.load_checkpoint.return_value = None

        result = try_load_checkpoint("nonexistent_id", manager, "test operation")

        assert result is None
        mock_print.assert_called()

    @patch("src.deletepy.utils.checkpoint_utils.print_warning")
    def test_load_non_resumable_checkpoint(self, mock_print):
        """Test loading non-resumable checkpoint returns None."""
        manager = MagicMock(spec=CheckpointManager)
        checkpoint = MagicMock(spec=Checkpoint)
        checkpoint.is_resumable.return_value = False
        manager.load_checkpoint.return_value = checkpoint

        result = try_load_checkpoint("completed_id", manager, "test operation")

        assert result is None
        mock_print.assert_called()

    def test_load_resumable_checkpoint(self):
        """Test loading resumable checkpoint succeeds."""
        manager = MagicMock(spec=CheckpointManager)
        checkpoint = MagicMock(spec=Checkpoint)
        checkpoint.is_resumable.return_value = True
        manager.load_checkpoint.return_value = checkpoint

        result = try_load_checkpoint("valid_id", manager, "test operation")

        assert result is checkpoint


class TestCreateCheckpoint:
    """Tests for create_checkpoint function."""

    def test_create_checkpoint_basic(self):
        """Test creating a basic checkpoint."""
        manager = MagicMock(spec=CheckpointManager)
        mock_checkpoint = MagicMock(spec=Checkpoint)
        manager.create_checkpoint.return_value = mock_checkpoint

        config = CheckpointConfig(
            operation_type=OperationType.BATCH_DELETE,
            env="dev",
            items=["auth0|123", "auth0|456"],
            batch_size=50,
            operation_name="batch delete",
        )

        result = create_checkpoint(manager, config)

        assert result is mock_checkpoint
        manager.create_checkpoint.assert_called_once()

    def test_create_checkpoint_with_additional_params(self):
        """Test creating checkpoint with additional params."""
        manager = MagicMock(spec=CheckpointManager)
        mock_checkpoint = MagicMock(spec=Checkpoint)
        manager.create_checkpoint.return_value = mock_checkpoint

        config = CheckpointConfig(
            operation_type=OperationType.SOCIAL_UNLINK,
            env="prod",
            items=["123"],
            additional_params={"rotate_password": True},
            operation_name="social unlink",
        )

        create_checkpoint(manager, config)

        call_args = manager.create_checkpoint.call_args
        operation_config = call_args.kwargs["config"]
        assert operation_config.additional_params["rotate_password"] is True
        assert operation_config.additional_params["operation"] == "social unlink"

    def test_create_checkpoint_none_additional_params(self):
        """Test creating checkpoint with None additional_params."""
        manager = MagicMock(spec=CheckpointManager)
        mock_checkpoint = MagicMock(spec=Checkpoint)
        manager.create_checkpoint.return_value = mock_checkpoint

        config = CheckpointConfig(
            operation_type=OperationType.BATCH_DELETE,
            env="dev",
            items=["auth0|123"],
            additional_params=None,
            operation_name="batch delete",
        )

        create_checkpoint(manager, config)

        call_args = manager.create_checkpoint.call_args
        operation_config = call_args.kwargs["config"]
        # Should have created dict with operation name even when additional_params was None
        assert "operation" in operation_config.additional_params


class TestLoadOrCreateCheckpoint:
    """Tests for load_or_create_checkpoint function."""

    @patch("src.deletepy.utils.checkpoint_utils.print_info")
    @patch("src.deletepy.utils.checkpoint_utils.CheckpointManager")
    def test_create_new_checkpoint(self, mock_manager_class, mock_print):
        """Test creating new checkpoint when no resume ID."""
        mock_manager = MagicMock(spec=CheckpointManager)
        mock_manager_class.return_value = mock_manager

        mock_checkpoint = MagicMock(spec=Checkpoint)
        mock_checkpoint.checkpoint_id = "new_checkpoint_123"
        mock_manager.create_checkpoint.return_value = mock_checkpoint
        mock_manager.load_checkpoint.return_value = None

        config = CheckpointConfig(
            operation_type=OperationType.BATCH_DELETE,
            env="dev",
            items=["auth0|123"],
            operation_name="batch delete",
        )

        result = load_or_create_checkpoint(None, None, config)

        assert result.checkpoint is mock_checkpoint
        assert result.is_resuming is False
        assert result.env == "dev"
        mock_manager.save_checkpoint.assert_called_once()

    @patch("src.deletepy.utils.checkpoint_utils.print_success")
    def test_resume_existing_checkpoint(self, mock_print):
        """Test resuming existing checkpoint."""
        mock_manager = MagicMock(spec=CheckpointManager)

        mock_checkpoint = MagicMock(spec=Checkpoint)
        mock_checkpoint.checkpoint_id = "existing_123"
        mock_checkpoint.is_resumable.return_value = True
        mock_checkpoint.config = MagicMock()
        mock_checkpoint.config.environment = "prod"
        mock_checkpoint.config.auto_delete = False

        mock_manager.load_checkpoint.return_value = mock_checkpoint

        config = CheckpointConfig(
            operation_type=OperationType.BATCH_DELETE,
            env="dev",  # Will be overridden
            items=["auth0|123"],
            auto_delete=True,  # Will be overridden
            operation_name="batch delete",
        )

        result = load_or_create_checkpoint("existing_123", mock_manager, config)

        assert result.checkpoint is mock_checkpoint
        assert result.is_resuming is True
        # Should use values from loaded checkpoint
        assert result.env == "prod"
        assert result.auto_delete is False

    @patch("src.deletepy.utils.checkpoint_utils.print_warning")
    @patch("src.deletepy.utils.checkpoint_utils.print_info")
    def test_create_new_when_resume_fails(self, mock_info, mock_warning):
        """Test creating new checkpoint when resume fails."""
        mock_manager = MagicMock(spec=CheckpointManager)
        mock_manager.load_checkpoint.return_value = None

        mock_checkpoint = MagicMock(spec=Checkpoint)
        mock_checkpoint.checkpoint_id = "new_123"
        mock_manager.create_checkpoint.return_value = mock_checkpoint

        config = CheckpointConfig(
            operation_type=OperationType.BATCH_DELETE,
            env="dev",
            items=["auth0|123"],
            operation_name="batch delete",
        )

        result = load_or_create_checkpoint("nonexistent_id", mock_manager, config)

        assert result.is_resuming is False
        mock_manager.create_checkpoint.assert_called_once()


class TestHandleCheckpointInterruption:
    """Tests for handle_checkpoint_interruption function."""

    @patch("src.deletepy.utils.checkpoint_utils.print_info")
    @patch("src.deletepy.utils.checkpoint_utils.print_warning")
    def test_handles_interruption(self, mock_warning, mock_info):
        """Test handling keyboard interrupt."""
        mock_checkpoint = MagicMock(spec=Checkpoint)
        mock_checkpoint.checkpoint_id = "test_123"
        mock_manager = MagicMock(spec=CheckpointManager)

        result = handle_checkpoint_interruption(
            mock_checkpoint, mock_manager, "batch delete"
        )

        assert result == "test_123"
        mock_manager.mark_checkpoint_cancelled.assert_called_once_with(mock_checkpoint)
        mock_manager.save_checkpoint.assert_called_once_with(mock_checkpoint)

    @patch("src.deletepy.utils.checkpoint_utils.print_info")
    @patch("src.deletepy.utils.checkpoint_utils.print_warning")
    def test_displays_resume_command(self, mock_warning, mock_info):
        """Test that resume command is displayed."""
        mock_checkpoint = MagicMock(spec=Checkpoint)
        mock_checkpoint.checkpoint_id = "test_123"
        mock_manager = MagicMock(spec=CheckpointManager)

        handle_checkpoint_interruption(mock_checkpoint, mock_manager, "batch delete")

        # Check that info about resuming was printed
        assert mock_info.call_count >= 2
        # At least one call should mention the checkpoint ID
        calls = [str(call) for call in mock_info.call_args_list]
        assert any("test_123" in call for call in calls)


class TestHandleCheckpointError:
    """Tests for handle_checkpoint_error function."""

    @patch("src.deletepy.utils.checkpoint_utils.print_warning")
    def test_handles_error(self, mock_warning):
        """Test handling error."""
        mock_checkpoint = MagicMock(spec=Checkpoint)
        mock_checkpoint.checkpoint_id = "test_123"
        mock_manager = MagicMock(spec=CheckpointManager)
        error = Exception("Test error message")

        result = handle_checkpoint_error(
            mock_checkpoint, mock_manager, "batch delete", error
        )

        assert result == "test_123"
        mock_manager.mark_checkpoint_failed.assert_called_once_with(
            mock_checkpoint, "Test error message"
        )
        mock_manager.save_checkpoint.assert_called_once_with(mock_checkpoint)


class TestFinalizeCheckpoint:
    """Tests for finalize_checkpoint function."""

    @patch("src.deletepy.utils.checkpoint_utils.print_success")
    def test_finalizes_checkpoint(self, mock_print):
        """Test finalizing checkpoint."""
        mock_checkpoint = MagicMock(spec=Checkpoint)
        mock_checkpoint.checkpoint_id = "test_123"
        mock_manager = MagicMock(spec=CheckpointManager)

        finalize_checkpoint(mock_checkpoint, mock_manager, "batch delete")

        assert mock_checkpoint.status == CheckpointStatus.COMPLETED
        mock_manager.save_checkpoint.assert_called_once_with(mock_checkpoint)


class TestUpdateCheckpointBatch:
    """Tests for update_checkpoint_batch function."""

    def test_updates_batch(self):
        """Test updating checkpoint batch."""
        mock_checkpoint = MagicMock(spec=Checkpoint)
        mock_manager = MagicMock(spec=CheckpointManager)

        processed_items = ["auth0|123", "auth0|456"]
        results_update = {
            "processed_count": 2,
            "error_count": 0,
        }

        update_checkpoint_batch(
            mock_checkpoint, mock_manager, processed_items, results_update
        )

        mock_manager.update_checkpoint_progress.assert_called_once_with(
            checkpoint=mock_checkpoint,
            processed_items=processed_items,
            results_update=results_update,
        )
        mock_manager.save_checkpoint.assert_called_once_with(mock_checkpoint)


class TestIntegrationWithRealObjects:
    """Integration tests using real checkpoint objects."""

    def setup_method(self):
        """Set up test fixtures with real objects."""
        self.temp_dir = tempfile.mkdtemp()

    def teardown_method(self):
        """Clean up temp directory."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_full_checkpoint_lifecycle(self):
        """Test full checkpoint lifecycle: create, update, finalize."""
        manager = CheckpointManager(checkpoint_dir=self.temp_dir)

        config = CheckpointConfig(
            operation_type=OperationType.BATCH_DELETE,
            env="dev",
            items=["auth0|123", "auth0|456", "auth0|789"],
            batch_size=2,
            operation_name="batch delete",
        )

        # Create checkpoint
        with patch("src.deletepy.utils.checkpoint_utils.print_info"):
            result = load_or_create_checkpoint(None, manager, config)

        assert result.is_resuming is False
        checkpoint = result.checkpoint

        # Update with first batch
        update_checkpoint_batch(
            checkpoint,
            manager,
            ["auth0|123", "auth0|456"],
            {"processed_count": 2},
        )

        # Verify progress
        assert checkpoint.progress.current_batch == 1
        assert len(checkpoint.processed_items) == 2

        # Finalize
        with patch("src.deletepy.utils.checkpoint_utils.print_success"):
            finalize_checkpoint(checkpoint, manager, "batch delete")

        assert checkpoint.status == CheckpointStatus.COMPLETED

    def test_checkpoint_resume_after_interruption(self):
        """Test resuming checkpoint after interruption."""
        manager = CheckpointManager(checkpoint_dir=self.temp_dir)

        config = CheckpointConfig(
            operation_type=OperationType.BATCH_DELETE,
            env="dev",
            items=["auth0|123", "auth0|456", "auth0|789"],
            batch_size=1,
            operation_name="batch delete",
        )

        # Create checkpoint
        with patch("src.deletepy.utils.checkpoint_utils.print_info"):
            result = load_or_create_checkpoint(None, manager, config)

        checkpoint = result.checkpoint
        checkpoint_id = checkpoint.checkpoint_id

        # Update with first item
        update_checkpoint_batch(
            checkpoint, manager, ["auth0|123"], {"processed_count": 1}
        )

        # Simulate interruption
        with (
            patch("src.deletepy.utils.checkpoint_utils.print_warning"),
            patch("src.deletepy.utils.checkpoint_utils.print_info"),
        ):
            handle_checkpoint_interruption(checkpoint, manager, "batch delete")

        # Resume checkpoint
        config2 = CheckpointConfig(
            operation_type=OperationType.BATCH_DELETE,
            env="dev",
            items=[],  # Will be ignored when resuming
            operation_name="batch delete",
        )

        with patch("src.deletepy.utils.checkpoint_utils.print_success"):
            result2 = load_or_create_checkpoint(checkpoint_id, manager, config2)

        assert result2.is_resuming is True
        assert len(result2.checkpoint.remaining_items) == 2

    @patch("src.deletepy.utils.checkpoint_utils.print_warning")
    @patch("src.deletepy.utils.checkpoint_utils.print_info")
    def test_checkpoint_cannot_resume_completed(self, mock_info, mock_warning):
        """Test that completed checkpoints cannot be resumed."""
        manager = CheckpointManager(checkpoint_dir=self.temp_dir)

        config = CheckpointConfig(
            operation_type=OperationType.BATCH_DELETE,
            env="dev",
            items=["auth0|123"],
            operation_name="batch delete",
        )

        # Create and complete checkpoint
        with patch("src.deletepy.utils.checkpoint_utils.print_info"):
            result = load_or_create_checkpoint(None, manager, config)

        checkpoint = result.checkpoint
        checkpoint_id = checkpoint.checkpoint_id

        # Complete the checkpoint
        checkpoint.remaining_items = []
        checkpoint.status = CheckpointStatus.COMPLETED
        manager.save_checkpoint(checkpoint)

        # Try to resume - should create new checkpoint instead
        result2 = load_or_create_checkpoint(checkpoint_id, manager, config)

        # Should not be resuming since checkpoint was completed
        assert result2.is_resuming is False


if __name__ == "__main__":
    pytest.main([__file__])
