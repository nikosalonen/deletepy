"""Tests for checkpoint operations."""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from src.deletepy.operations.checkpoint_ops import (
    CheckpointData,
    CheckpointService,
    ResumableOperation,
    display_checkpoint_summary,
    list_available_checkpoints,
)


class TestCheckpointData:
    """Test CheckpointData dataclass."""

    def test_init_default_values(self):
        """Test CheckpointData initialization with default values."""
        checkpoint = CheckpointData(
            operation_id="test_op",
            operation_type="delete",
            environment="dev",
            total_items=10,
            processed_items=0,
            failed_items=0,
        )

        assert checkpoint.operation_id == "test_op"
        assert checkpoint.operation_type == "delete"
        assert checkpoint.environment == "dev"
        assert checkpoint.total_items == 10
        assert checkpoint.processed_items == 0
        assert checkpoint.failed_items == 0
        assert checkpoint.remaining_items == []
        assert checkpoint.processed_results == []
        assert checkpoint.failed_results == []
        assert checkpoint.metadata == {}
        assert checkpoint.created_at is not None
        assert checkpoint.last_updated is not None

    def test_success_rate_calculation(self):
        """Test success rate calculation."""
        # No items processed
        checkpoint = CheckpointData(
            operation_id="test",
            operation_type="delete",
            environment="dev",
            total_items=10,
            processed_items=0,
            failed_items=0,
        )
        assert checkpoint.success_rate == 0.0

        # All successful
        checkpoint.processed_items = 5
        checkpoint.failed_items = 0
        assert checkpoint.success_rate == 100.0

        # Mixed results
        checkpoint.processed_items = 3
        checkpoint.failed_items = 2
        assert checkpoint.success_rate == 60.0

    def test_completion_rate_calculation(self):
        """Test completion rate calculation."""
        # No items processed
        checkpoint = CheckpointData(
            operation_id="test",
            operation_type="delete",
            environment="dev",
            total_items=10,
            processed_items=0,
            failed_items=0,
        )
        assert checkpoint.completion_rate == 0.0

        # Half completed
        checkpoint.processed_items = 3
        checkpoint.failed_items = 2
        assert checkpoint.completion_rate == 50.0

        # All completed
        checkpoint.processed_items = 7
        checkpoint.failed_items = 3
        assert checkpoint.completion_rate == 100.0

    def test_empty_total_items(self):
        """Test handling of empty total_items."""
        checkpoint = CheckpointData(
            operation_id="test",
            operation_type="delete",
            environment="dev",
            total_items=0,
            processed_items=0,
            failed_items=0,
        )
        assert checkpoint.completion_rate == 0.0


class TestCheckpointService:
    """Test CheckpointService class."""

    def test_init(self):
        """Test CheckpointService initialization."""
        with tempfile.TemporaryDirectory() as temp_dir:
            service = CheckpointService(temp_dir)
            assert service.checkpoint_dir == Path(temp_dir)
            assert service.checkpoint_dir.exists()

    def test_create_checkpoint(self):
        """Test creating a checkpoint."""
        with tempfile.TemporaryDirectory() as temp_dir:
            service = CheckpointService(temp_dir)

            items = ["user1", "user2", "user3"]
            metadata = {"input_file": "test.txt"}

            operation_id = service.create_checkpoint("delete", "dev", items, metadata)

            assert operation_id.startswith("delete_")

            # Verify checkpoint file was created
            checkpoint_file = Path(temp_dir) / f"{operation_id}.json"
            assert checkpoint_file.exists()

            # Verify checkpoint content
            checkpoint = service.load_checkpoint(operation_id)
            assert checkpoint is not None
            assert checkpoint.operation_type == "delete"
            assert checkpoint.environment == "dev"
            assert checkpoint.total_items == 3
            assert checkpoint.remaining_items == items
            assert checkpoint.metadata == metadata

    def test_load_nonexistent_checkpoint(self):
        """Test loading a non-existent checkpoint."""
        with tempfile.TemporaryDirectory() as temp_dir:
            service = CheckpointService(temp_dir)
            checkpoint = service.load_checkpoint("nonexistent")
            assert checkpoint is None

    def test_update_checkpoint_success(self):
        """Test updating checkpoint with successful item."""
        with tempfile.TemporaryDirectory() as temp_dir:
            service = CheckpointService(temp_dir)

            items = ["user1", "user2"]
            operation_id = service.create_checkpoint("delete", "dev", items)

            # Update with successful item
            service.update_checkpoint(
                operation_id,
                processed_item="user1",
                result_data={"resolved_id": "auth0|123"},
            )

            checkpoint = service.load_checkpoint(operation_id)
            assert checkpoint.processed_items == 1
            assert checkpoint.failed_items == 0
            assert "user1" not in checkpoint.remaining_items
            assert len(checkpoint.processed_results) == 1
            assert checkpoint.processed_results[0]["item"] == "user1"

    def test_update_checkpoint_failure(self):
        """Test updating checkpoint with failed item."""
        with tempfile.TemporaryDirectory() as temp_dir:
            service = CheckpointService(temp_dir)

            items = ["user1", "user2"]
            operation_id = service.create_checkpoint("delete", "dev", items)

            # Update with failed item
            service.update_checkpoint(
                operation_id, failed_item="user1", result_data={"error": "Not found"}
            )

            checkpoint = service.load_checkpoint(operation_id)
            assert checkpoint.processed_items == 0
            assert checkpoint.failed_items == 1
            assert "user1" not in checkpoint.remaining_items
            assert len(checkpoint.failed_results) == 1
            assert checkpoint.failed_results[0]["item"] == "user1"

    def test_update_nonexistent_checkpoint(self):
        """Test updating a non-existent checkpoint."""
        with tempfile.TemporaryDirectory() as temp_dir:
            service = CheckpointService(temp_dir)

            with pytest.raises(ValueError, match="Checkpoint .* not found"):
                service.update_checkpoint("nonexistent", processed_item="user1")

    def test_list_checkpoints(self):
        """Test listing checkpoints."""
        with tempfile.TemporaryDirectory() as temp_dir:
            service = CheckpointService(temp_dir)

            # Create multiple checkpoints
            service.create_checkpoint("delete", "dev", ["user1"])
            service.create_checkpoint("block", "prod", ["user2"])

            # List all checkpoints
            checkpoints = service.list_checkpoints()
            assert len(checkpoints) == 2

            # List filtered by operation type
            delete_checkpoints = service.list_checkpoints("delete")
            assert len(delete_checkpoints) == 1
            assert delete_checkpoints[0].operation_type == "delete"

    def test_delete_checkpoint(self):
        """Test deleting a checkpoint."""
        with tempfile.TemporaryDirectory() as temp_dir:
            service = CheckpointService(temp_dir)

            operation_id = service.create_checkpoint("delete", "dev", ["user1"])

            # Verify checkpoint exists
            assert service.load_checkpoint(operation_id) is not None

            # Delete checkpoint
            success = service.delete_checkpoint(operation_id)
            assert success is True

            # Verify checkpoint is gone
            assert service.load_checkpoint(operation_id) is None

    def test_delete_nonexistent_checkpoint(self):
        """Test deleting a non-existent checkpoint."""
        with tempfile.TemporaryDirectory() as temp_dir:
            service = CheckpointService(temp_dir)
            success = service.delete_checkpoint("nonexistent")
            assert success is False

    def test_get_checkpoint_info(self):
        """Test getting checkpoint info."""
        with tempfile.TemporaryDirectory() as temp_dir:
            service = CheckpointService(temp_dir)

            items = ["user1", "user2", "user3"]
            operation_id = service.create_checkpoint("delete", "dev", items)

            # Update checkpoint
            service.update_checkpoint(operation_id, processed_item="user1")

            info = service.get_checkpoint_info(operation_id)
            assert info is not None
            assert info["operation_id"] == operation_id
            assert info["operation_type"] == "delete"
            assert info["environment"] == "dev"
            assert info["total_items"] == 3
            assert info["processed_items"] == 1
            assert info["remaining_items"] == 2
            assert info["completion_rate"] == pytest.approx(33.33, rel=1e-2)

    def test_cleanup_old_checkpoints(self):
        """Test cleaning up old checkpoints."""
        with tempfile.TemporaryDirectory() as temp_dir:
            service = CheckpointService(temp_dir)

            # Create a checkpoint
            _ = service.create_checkpoint("delete", "dev", ["user1"])

            # Mock the file modification time to be old
            import time

            old_time = time.time() - (8 * 24 * 60 * 60)  # 8 days ago
            with patch.object(Path, "stat") as mock_stat:
                mock_stat.return_value = Mock(st_mtime=old_time)

                deleted_count = service.cleanup_old_checkpoints(days=7)
                assert deleted_count == 1

    def test_generate_operation_id(self):
        """Test operation ID generation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            service = CheckpointService(temp_dir)

            # Test ID format
            op_id = service._generate_operation_id("delete")
            assert op_id.startswith("delete_")

            # Test uniqueness with a small delay
            import time

            time.sleep(0.001)  # Small delay to ensure uniqueness
            op_id2 = service._generate_operation_id("delete")
            assert op_id != op_id2

    def test_save_checkpoint_error(self):
        """Test handling save checkpoint errors."""
        with tempfile.TemporaryDirectory() as temp_dir:
            service = CheckpointService(temp_dir)

            # Create checkpoint
            checkpoint = CheckpointData(
                operation_id="test",
                operation_type="delete",
                environment="dev",
                total_items=1,
                processed_items=0,
                failed_items=0,
            )

            # Mock open to raise an error
            with patch("builtins.open", side_effect=OSError("Permission denied")):
                with pytest.raises(RuntimeError, match="Failed to save checkpoint"):
                    service._save_checkpoint(checkpoint)


class TestResumableOperation:
    """Test ResumableOperation class."""

    def test_init(self):
        """Test ResumableOperation initialization."""
        with tempfile.TemporaryDirectory() as temp_dir:
            service = CheckpointService(temp_dir)
            operation = ResumableOperation(service)

            assert operation.checkpoint_service == service
            assert operation.current_checkpoint_id is None

    def test_start_operation(self):
        """Test starting a resumable operation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            service = CheckpointService(temp_dir)
            operation = ResumableOperation(service)

            items = ["user1", "user2"]
            metadata = {"test": "data"}

            operation_id = operation.start_operation("delete", "dev", items, metadata)

            assert operation_id is not None
            assert operation.current_checkpoint_id == operation_id

            # Verify checkpoint was created
            checkpoint = service.load_checkpoint(operation_id)
            assert checkpoint is not None
            assert checkpoint.operation_type == "delete"

    def test_resume_operation(self):
        """Test resuming an operation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            service = CheckpointService(temp_dir)
            operation = ResumableOperation(service)

            # Create checkpoint
            items = ["user1", "user2"]
            operation_id = service.create_checkpoint("delete", "dev", items)

            # Resume operation
            checkpoint = operation.resume_operation(operation_id)

            assert checkpoint is not None
            assert operation.current_checkpoint_id == operation_id

    def test_resume_nonexistent_operation(self):
        """Test resuming a non-existent operation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            service = CheckpointService(temp_dir)
            operation = ResumableOperation(service)

            checkpoint = operation.resume_operation("nonexistent")
            assert checkpoint is None
            assert operation.current_checkpoint_id is None

    def test_record_success(self):
        """Test recording successful processing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            service = CheckpointService(temp_dir)
            operation = ResumableOperation(service)

            items = ["user1", "user2"]
            operation_id = operation.start_operation("delete", "dev", items)

            # Record success
            operation.record_success("user1", {"resolved_id": "auth0|123"})

            # Verify checkpoint was updated
            checkpoint = service.load_checkpoint(operation_id)
            assert checkpoint.processed_items == 1
            assert "user1" not in checkpoint.remaining_items

    def test_record_failure(self):
        """Test recording failed processing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            service = CheckpointService(temp_dir)
            operation = ResumableOperation(service)

            items = ["user1", "user2"]
            operation_id = operation.start_operation("delete", "dev", items)

            # Record failure
            operation.record_failure("user1", {"error": "Not found"})

            # Verify checkpoint was updated
            checkpoint = service.load_checkpoint(operation_id)
            assert checkpoint.failed_items == 1
            assert "user1" not in checkpoint.remaining_items

    def test_get_remaining_items(self):
        """Test getting remaining items."""
        with tempfile.TemporaryDirectory() as temp_dir:
            service = CheckpointService(temp_dir)
            operation = ResumableOperation(service)

            items = ["user1", "user2", "user3"]
            operation.start_operation("delete", "dev", items)

            # Initially, all items remain
            remaining = operation.get_remaining_items()
            assert len(remaining) == 3

            # After processing one item
            operation.record_success("user1")
            remaining = operation.get_remaining_items()
            assert len(remaining) == 2
            assert "user1" not in remaining

    def test_is_complete(self):
        """Test checking if operation is complete."""
        with tempfile.TemporaryDirectory() as temp_dir:
            service = CheckpointService(temp_dir)
            operation = ResumableOperation(service)

            items = ["user1", "user2"]
            operation.start_operation("delete", "dev", items)

            # Initially not complete
            assert not operation.is_complete()

            # After processing all items
            operation.record_success("user1")
            operation.record_success("user2")
            assert operation.is_complete()

    def test_cleanup_checkpoint(self):
        """Test cleaning up checkpoint."""
        with tempfile.TemporaryDirectory() as temp_dir:
            service = CheckpointService(temp_dir)
            operation = ResumableOperation(service)

            items = ["user1"]
            operation_id = operation.start_operation("delete", "dev", items)

            # Verify checkpoint exists
            assert service.load_checkpoint(operation_id) is not None

            # Cleanup
            operation.cleanup_checkpoint()

            # Verify checkpoint is gone
            assert service.load_checkpoint(operation_id) is None
            assert operation.current_checkpoint_id is None


class TestDisplayFunctions:
    """Test display utility functions."""

    @patch("src.deletepy.operations.checkpoint_ops.print")
    def test_display_checkpoint_summary(self, mock_print):
        """Test displaying checkpoint summary."""
        checkpoint = CheckpointData(
            operation_id="test_op_20240101_120000_1234",
            operation_type="delete",
            environment="dev",
            total_items=10,
            processed_items=5,
            failed_items=2,
            remaining_items=["user8", "user9", "user10"],
            metadata={"input_file": "test.txt"},
        )

        display_checkpoint_summary(checkpoint)

        # Verify print was called with expected content
        assert mock_print.called
        call_args = [call[0][0] for call in mock_print.call_args_list]
        summary_text = " ".join(call_args)

        assert "test_op_20240101_120000_1234" in summary_text
        assert "delete" in summary_text
        assert "dev" in summary_text
        assert "10" in summary_text  # total items
        assert "5" in summary_text  # processed items
        assert "2" in summary_text  # failed items
        assert "3" in summary_text  # remaining items

    @patch("src.deletepy.operations.checkpoint_ops.print")
    def test_list_available_checkpoints_empty(self, mock_print):
        """Test listing checkpoints when none exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            service = CheckpointService(temp_dir)

            list_available_checkpoints(service)

            # Verify "No checkpoints found" message
            assert mock_print.called
            call_args = [call[0][0] for call in mock_print.call_args_list]
            assert any("No checkpoints found" in arg for arg in call_args)

    @patch("src.deletepy.operations.checkpoint_ops.print")
    def test_list_available_checkpoints_with_data(self, mock_print):
        """Test listing checkpoints with data."""
        with tempfile.TemporaryDirectory() as temp_dir:
            service = CheckpointService(temp_dir)

            # Create test checkpoint
            service.create_checkpoint("delete", "dev", ["user1", "user2"])

            list_available_checkpoints(service)

            # Verify checkpoint listing
            assert mock_print.called
            call_args = [call[0][0] for call in mock_print.call_args_list]
            summary_text = " ".join(call_args)

            assert "AVAILABLE CHECKPOINTS" in summary_text
            assert "delete" in summary_text
            assert "dev" in summary_text
