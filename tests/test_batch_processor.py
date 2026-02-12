"""Tests for batch operation processor."""

import tempfile
from unittest.mock import MagicMock, patch

import pytest

from src.deletepy.core.auth0_client import Auth0Client, Auth0Context
from src.deletepy.models.checkpoint import OperationType
from src.deletepy.operations.batch_processor import (
    BatchOperationProcessor,
    BatchResult,
    BatchResults,
    OperationContext,
)


class TestBatchResult:
    """Tests for BatchResult dataclass."""

    def test_success_result(self):
        """Test creating a success result."""
        result = BatchResult(
            success=True,
            item_id="auth0|123",
            message="User deleted",
        )

        assert result.success is True
        assert result.item_id == "auth0|123"
        assert result.message == "User deleted"
        assert result.data is None

    def test_failure_result(self):
        """Test creating a failure result."""
        result = BatchResult(
            success=False,
            item_id="auth0|456",
            message="User not found",
        )

        assert result.success is False
        assert result.item_id == "auth0|456"
        assert result.message == "User not found"

    def test_result_with_data(self):
        """Test creating result with additional data."""
        result = BatchResult(
            success=True,
            item_id="auth0|789",
            data={"identities": ["google-oauth2|123"]},
        )

        assert result.data == {"identities": ["google-oauth2|123"]}


class TestBatchResults:
    """Tests for BatchResults dataclass."""

    def test_default_values(self):
        """Test default values for BatchResults."""
        results = BatchResults()

        assert results.processed_count == 0
        assert results.skipped_count == 0
        assert results.error_count == 0
        assert results.not_found_count == 0
        assert results.multiple_users_count == 0
        assert results.custom_counts == {}
        assert results.items_by_status == {}
        assert results.items_attempted == []
        assert results.was_interrupted is False

    def test_to_checkpoint_update(self):
        """Test conversion to checkpoint update format."""
        results = BatchResults(
            processed_count=10,
            skipped_count=2,
            error_count=1,
            not_found_count=3,
            multiple_users_count=0,
            custom_counts={"deleted_count": 8, "unlinked_count": 2},
        )

        update = results.to_checkpoint_update()

        assert update["processed_count"] == 10
        assert update["skipped_count"] == 2
        assert update["error_count"] == 1
        assert update["not_found_count"] == 3
        assert update["multiple_users_count"] == 0
        assert update["deleted_count"] == 8
        assert update["unlinked_count"] == 2

    def test_merge_basic_counts(self):
        """Test merging basic counts."""
        results1 = BatchResults(
            processed_count=5,
            skipped_count=1,
            error_count=0,
        )
        results2 = BatchResults(
            processed_count=3,
            skipped_count=2,
            error_count=1,
        )

        results1.merge(results2)

        assert results1.processed_count == 8
        assert results1.skipped_count == 3
        assert results1.error_count == 1

    def test_merge_custom_counts(self):
        """Test merging custom counts."""
        results1 = BatchResults(
            custom_counts={"deleted": 5, "blocked": 2},
        )
        results2 = BatchResults(
            custom_counts={"deleted": 3, "unlinked": 1},
        )

        results1.merge(results2)

        assert results1.custom_counts["deleted"] == 8
        assert results1.custom_counts["blocked"] == 2
        assert results1.custom_counts["unlinked"] == 1

    def test_merge_items_by_status(self):
        """Test merging items by status."""
        results1 = BatchResults(
            items_by_status={"error": ["auth0|1", "auth0|2"]},
        )
        results2 = BatchResults(
            items_by_status={"error": ["auth0|3"], "skipped": ["auth0|4"]},
        )

        results1.merge(results2)

        assert len(results1.items_by_status["error"]) == 3
        assert results1.items_by_status["skipped"] == ["auth0|4"]

    def test_merge_items_attempted(self):
        """Test merging items_attempted list."""
        results1 = BatchResults(
            items_attempted=["auth0|1", "auth0|2"],
        )
        results2 = BatchResults(
            items_attempted=["auth0|3", "auth0|4"],
        )

        results1.merge(results2)

        assert len(results1.items_attempted) == 4
        assert "auth0|3" in results1.items_attempted

    def test_merge_propagates_interruption(self):
        """Test that interruption flag is propagated during merge."""
        results1 = BatchResults(was_interrupted=False)
        results2 = BatchResults(was_interrupted=True)

        results1.merge(results2)

        assert results1.was_interrupted is True

    def test_merge_does_not_clear_interruption(self):
        """Test that merging non-interrupted results doesn't clear flag."""
        results1 = BatchResults(was_interrupted=True)
        results2 = BatchResults(was_interrupted=False)

        results1.merge(results2)

        assert results1.was_interrupted is True


class TestOperationContext:
    """Tests for OperationContext dataclass."""

    def test_context_creation(self):
        """Test creating operation context."""
        auth = Auth0Context(token="test", base_url="https://test.auth0.com")
        client = Auth0Client(auth)

        context = OperationContext(
            auth=auth,
            client=client,
            env="dev",
        )

        assert context.auth is auth
        assert context.client is client
        assert context.env == "dev"
        assert context.checkpoint_manager is None
        assert context.resume_checkpoint_id is None
        assert context.auto_delete is True
        assert context.rotate_password is False

    def test_context_with_checkpoint(self):
        """Test creating context with checkpoint manager."""
        auth = Auth0Context(token="test", base_url="https://test.auth0.com")
        client = Auth0Client(auth)
        mock_manager = MagicMock()

        context = OperationContext(
            auth=auth,
            client=client,
            checkpoint_manager=mock_manager,
            resume_checkpoint_id="checkpoint_123",
        )

        assert context.checkpoint_manager is mock_manager
        assert context.resume_checkpoint_id == "checkpoint_123"

    def test_from_token_factory(self):
        """Test creating context from token."""
        context = OperationContext.from_token(
            token="test_token",
            base_url="https://test.auth0.com",
            env="prod",
        )

        assert context.auth.token == "test_token"
        assert context.auth.base_url == "https://test.auth0.com"
        assert context.env == "prod"
        assert isinstance(context.client, Auth0Client)

    def test_from_token_with_kwargs(self):
        """Test creating context with extra kwargs."""
        context = OperationContext.from_token(
            token="test_token",
            base_url="https://test.auth0.com",
            env="dev",
            auto_delete=False,
            rotate_password=True,
        )

        assert context.auto_delete is False
        assert context.rotate_password is True


class ConcreteBatchProcessor(BatchOperationProcessor):
    """Concrete implementation for testing abstract class."""

    def __init__(self, context, fail_items=None, not_found_items=None):
        super().__init__(context)
        self.fail_items = fail_items or []
        self.not_found_items = not_found_items or []
        self.processed_items = []

    def process_item(self, item: str) -> BatchResult:
        """Process a single item."""
        self.processed_items.append(item)

        if item in self.fail_items:
            return BatchResult(
                success=False,
                item_id=item,
                message="Processing failed",
            )
        if item in self.not_found_items:
            return BatchResult(
                success=False,
                item_id=item,
                message="Not found",
            )

        return BatchResult(
            success=True,
            item_id=item,
            message="Processed",
        )

    def get_operation_name(self) -> str:
        return "Test Operation"

    def get_operation_type(self) -> OperationType:
        return OperationType.BATCH_DELETE


class TestBatchOperationProcessor:
    """Tests for BatchOperationProcessor abstract class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.context = OperationContext.from_token(
            token="test",
            base_url="https://test.auth0.com",
        )

    def test_processor_initialization(self):
        """Test processor initialization."""
        processor = ConcreteBatchProcessor(self.context)

        assert processor.context is self.context
        assert processor.client is self.context.client

    def test_validate_item_default(self):
        """Test default item validation always passes."""
        processor = ConcreteBatchProcessor(self.context)

        is_valid, error_msg = processor.validate_item("any_item")

        assert is_valid is True
        assert error_msg is None

    @patch("src.deletepy.operations.batch_processor.shutdown_requested")
    @patch("src.deletepy.operations.batch_processor.live_progress")
    def test_process_batch_all_success(self, mock_progress, mock_shutdown):
        """Test processing batch with all successes."""
        mock_shutdown.return_value = False
        processor = ConcreteBatchProcessor(self.context)

        items = ["auth0|1", "auth0|2", "auth0|3"]
        results = processor.process_batch(items, batch_number=1)

        assert results.processed_count == 3
        assert results.skipped_count == 0
        assert results.error_count == 0
        assert len(results.items_attempted) == 3

    @patch("src.deletepy.operations.batch_processor.shutdown_requested")
    @patch("src.deletepy.operations.batch_processor.live_progress")
    def test_process_batch_with_failures(self, mock_progress, mock_shutdown):
        """Test processing batch with some failures."""
        mock_shutdown.return_value = False
        processor = ConcreteBatchProcessor(
            self.context,
            fail_items=["auth0|2"],
        )

        items = ["auth0|1", "auth0|2", "auth0|3"]
        results = processor.process_batch(items, batch_number=1)

        assert results.processed_count == 2
        assert results.skipped_count == 1  # Failed items are counted as skipped
        assert len(results.items_attempted) == 3

    @patch("src.deletepy.operations.batch_processor.shutdown_requested")
    @patch("src.deletepy.operations.batch_processor.live_progress")
    def test_process_batch_with_exception(self, mock_progress, mock_shutdown):
        """Test processing batch when item raises exception."""
        mock_shutdown.return_value = False
        processor = ConcreteBatchProcessor(self.context)

        # Make process_item raise an exception for one item
        original_process = processor.process_item

        def raise_for_item(item):
            if item == "auth0|2":
                raise Exception("Unexpected error")
            return original_process(item)

        processor.process_item = raise_for_item

        items = ["auth0|1", "auth0|2", "auth0|3"]
        results = processor.process_batch(items, batch_number=1)

        assert results.processed_count == 2
        assert results.error_count == 1
        assert "error" in results.items_by_status
        assert "auth0|2" in results.items_by_status["error"]

    @patch("src.deletepy.operations.batch_processor.shutdown_requested")
    @patch("src.deletepy.operations.batch_processor.live_progress")
    def test_process_batch_interrupted(self, mock_progress, mock_shutdown):
        """Test that batch processing stops when shutdown is requested."""
        # Shutdown after 2 items
        mock_shutdown.side_effect = [False, False, True, True]
        processor = ConcreteBatchProcessor(self.context)

        items = ["auth0|1", "auth0|2", "auth0|3", "auth0|4"]
        results = processor.process_batch(items, batch_number=1)

        assert results.was_interrupted is True
        assert len(results.items_attempted) == 2  # Only first 2 processed

    @patch("src.deletepy.operations.batch_processor.shutdown_requested")
    @patch("src.deletepy.operations.batch_processor.live_progress")
    def test_process_batch_tracks_items_attempted(self, mock_progress, mock_shutdown):
        """Test that items_attempted tracks all items we tried to process."""
        mock_shutdown.return_value = False
        processor = ConcreteBatchProcessor(
            self.context,
            fail_items=["auth0|2"],
        )

        items = ["auth0|1", "auth0|2", "auth0|3"]
        results = processor.process_batch(items, batch_number=1)

        # All items should be in items_attempted, regardless of success/failure
        assert "auth0|1" in results.items_attempted
        assert "auth0|2" in results.items_attempted
        assert "auth0|3" in results.items_attempted


class TestBatchOperationProcessorValidation:
    """Tests for custom validation in batch processor."""

    def setup_method(self):
        """Set up test fixtures."""
        self.context = OperationContext.from_token(
            token="test",
            base_url="https://test.auth0.com",
        )

    @patch("src.deletepy.operations.batch_processor.shutdown_requested")
    @patch("src.deletepy.operations.batch_processor.live_progress")
    def test_invalid_items_are_skipped(self, mock_progress, mock_shutdown):
        """Test that invalid items are skipped."""
        mock_shutdown.return_value = False

        processor = ConcreteBatchProcessor(self.context)

        # Override validate_item to reject certain items
        def custom_validate(item):
            if item == "invalid":
                return False, "Invalid item format"
            return True, None

        processor.validate_item = custom_validate

        items = ["auth0|1", "invalid", "auth0|3"]
        results = processor.process_batch(items, batch_number=1)

        assert results.processed_count == 2
        assert results.skipped_count == 1
        assert "invalid" in results.items_by_status.get("invalid", [])


class TestBatchOperationProcessorRun:
    """Tests for the run method with full checkpoint integration."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.context = OperationContext.from_token(
            token="test",
            base_url="https://test.auth0.com",
        )

    def teardown_method(self):
        """Clean up temp directory."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch("src.deletepy.operations.batch_processor.finalize_checkpoint")
    @patch("src.deletepy.operations.batch_processor.update_checkpoint_batch")
    @patch("src.deletepy.operations.batch_processor.load_or_create_checkpoint")
    @patch("src.deletepy.operations.batch_processor.shutdown_requested")
    @patch("src.deletepy.operations.batch_processor.live_progress")
    @patch("src.deletepy.operations.batch_processor.print_info")
    def test_run_completes_successfully(
        self,
        mock_info,
        mock_progress,
        mock_shutdown,
        mock_load_checkpoint,
        mock_update,
        mock_finalize,
    ):
        """Test successful batch run with checkpointing."""
        mock_shutdown.return_value = False

        # Mock checkpoint setup
        mock_checkpoint = MagicMock()
        mock_checkpoint.remaining_items = ["auth0|1", "auth0|2"]
        mock_checkpoint.progress = MagicMock()
        mock_checkpoint.progress.current_batch = 0
        mock_checkpoint.progress.total_batches = 1

        mock_manager = MagicMock()

        mock_checkpoint_result = MagicMock()
        mock_checkpoint_result.checkpoint = mock_checkpoint
        mock_checkpoint_result.checkpoint_manager = mock_manager
        mock_load_checkpoint.return_value = mock_checkpoint_result

        processor = ConcreteBatchProcessor(self.context)

        result = processor.run(["auth0|1", "auth0|2"], batch_size=50)

        # Should complete without returning checkpoint ID
        assert result is None
        mock_finalize.assert_called_once()

    @patch("src.deletepy.operations.batch_processor.handle_checkpoint_interruption")
    @patch("src.deletepy.operations.batch_processor.load_or_create_checkpoint")
    def test_run_handles_keyboard_interrupt(
        self, mock_load_checkpoint, mock_handle_interrupt
    ):
        """Test that KeyboardInterrupt is handled properly."""
        mock_checkpoint = MagicMock()
        mock_checkpoint.remaining_items = ["auth0|1"]
        mock_manager = MagicMock()

        mock_checkpoint_result = MagicMock()
        mock_checkpoint_result.checkpoint = mock_checkpoint
        mock_checkpoint_result.checkpoint_manager = mock_manager
        mock_load_checkpoint.return_value = mock_checkpoint_result

        mock_handle_interrupt.return_value = "checkpoint_123"

        processor = ConcreteBatchProcessor(self.context)

        # Mock _execute_batches to raise KeyboardInterrupt
        processor._execute_batches = MagicMock(side_effect=KeyboardInterrupt())

        result = processor.run(["auth0|1"], batch_size=50)

        assert result == "checkpoint_123"
        mock_handle_interrupt.assert_called_once()

    @patch("src.deletepy.operations.batch_processor.handle_checkpoint_error")
    @patch("src.deletepy.operations.batch_processor.load_or_create_checkpoint")
    def test_run_handles_exception(self, mock_load_checkpoint, mock_handle_error):
        """Test that exceptions are handled properly."""
        mock_checkpoint = MagicMock()
        mock_checkpoint.remaining_items = ["auth0|1"]
        mock_manager = MagicMock()

        mock_checkpoint_result = MagicMock()
        mock_checkpoint_result.checkpoint = mock_checkpoint
        mock_checkpoint_result.checkpoint_manager = mock_manager
        mock_load_checkpoint.return_value = mock_checkpoint_result

        mock_handle_error.return_value = "checkpoint_123"

        processor = ConcreteBatchProcessor(self.context)

        # Mock _execute_batches to raise an exception
        processor._execute_batches = MagicMock(side_effect=Exception("Test error"))

        result = processor.run(["auth0|1"], batch_size=50)

        assert result == "checkpoint_123"
        mock_handle_error.assert_called_once()


class TestDisplaySummary:
    """Tests for display_summary method."""

    def setup_method(self):
        """Set up test fixtures."""
        self.context = OperationContext.from_token(
            token="test",
            base_url="https://test.auth0.com",
        )

    @patch("src.deletepy.operations.batch_processor.print_info")
    def test_display_summary_basic(self, mock_print):
        """Test basic summary display."""
        processor = ConcreteBatchProcessor(self.context)

        results = BatchResults(
            processed_count=10,
            skipped_count=2,
            error_count=0,
            not_found_count=0,
        )

        processor.display_summary(results)

        # Should print summary information
        assert mock_print.call_count >= 2

    @patch("src.deletepy.operations.batch_processor.print_info")
    def test_display_summary_with_errors(self, mock_print):
        """Test summary display with errors."""
        processor = ConcreteBatchProcessor(self.context)

        results = BatchResults(
            processed_count=8,
            skipped_count=1,
            error_count=3,
            not_found_count=2,
        )

        processor.display_summary(results)

        # Should print error and not_found counts
        calls = [str(call) for call in mock_print.call_args_list]
        assert any("Errors" in call for call in calls)
        assert any("Not found" in call for call in calls)


if __name__ == "__main__":
    pytest.main([__file__])
