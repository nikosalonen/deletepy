"""Abstract batch operation processor for Auth0 operations.

This module provides a template for batch processing operations with:
- Checkpoint support
- Progress tracking
- Shutdown signal handling
- Standardized result tracking
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from deletepy.utils.display_utils import (
    clear_progress_line,
    show_progress,
    shutdown_requested,
)

from ..core.auth0_client import Auth0Client, Auth0Context
from ..models.checkpoint import Checkpoint, OperationType
from ..utils.checkpoint_manager import CheckpointManager
from ..utils.checkpoint_utils import (
    CheckpointConfig,
    finalize_checkpoint,
    handle_checkpoint_error,
    handle_checkpoint_interruption,
    load_or_create_checkpoint,
    update_checkpoint_batch,
)
from ..utils.legacy_print import print_info, print_warning


@dataclass
class BatchResult:
    """Result of processing a single item in a batch.

    Attributes:
        success: Whether the operation succeeded
        item_id: Identifier of the processed item
        message: Optional status message
        data: Optional additional data from the operation
    """

    success: bool
    item_id: str
    message: str | None = None
    data: dict[str, Any] | None = None


@dataclass
class BatchResults:
    """Aggregated results from batch processing.

    Attributes:
        processed_count: Number of successfully processed items
        skipped_count: Number of skipped items
        error_count: Number of errors
        not_found_count: Number of items not found
        multiple_users_count: Number of items with multiple users
        custom_counts: Additional custom counters
        items_by_status: Items categorized by their result status
        items_attempted: List of items that were actually attempted (for checkpoint)
        was_interrupted: Whether processing was interrupted by shutdown signal
    """

    processed_count: int = 0
    skipped_count: int = 0
    error_count: int = 0
    not_found_count: int = 0
    multiple_users_count: int = 0
    custom_counts: dict[str, int] = field(default_factory=dict)
    items_by_status: dict[str, list[str]] = field(default_factory=dict)
    items_attempted: list[str] = field(default_factory=list)
    was_interrupted: bool = False

    def to_checkpoint_update(self) -> dict[str, Any]:
        """Convert results to checkpoint update format.

        Returns:
            Dictionary suitable for checkpoint progress update
        """
        update = {
            "processed_count": self.processed_count,
            "skipped_count": self.skipped_count,
            "error_count": self.error_count,
            "not_found_count": self.not_found_count,
            "multiple_users_count": self.multiple_users_count,
        }
        update.update(self.custom_counts)
        return update

    def merge(self, other: "BatchResults") -> None:
        """Merge another BatchResults into this one.

        Args:
            other: BatchResults to merge
        """
        self.processed_count += other.processed_count
        self.skipped_count += other.skipped_count
        self.error_count += other.error_count
        self.not_found_count += other.not_found_count
        self.multiple_users_count += other.multiple_users_count

        for key, value in other.custom_counts.items():
            self.custom_counts[key] = self.custom_counts.get(key, 0) + value

        for status, items in other.items_by_status.items():
            if status not in self.items_by_status:
                self.items_by_status[status] = []
            self.items_by_status[status].extend(items)

        self.items_attempted.extend(other.items_attempted)
        # Propagate interruption flag
        if other.was_interrupted:
            self.was_interrupted = True


@dataclass
class OperationContext:
    """Context for batch operations.

    Encapsulates all the configuration and dependencies needed
    for batch processing.

    Attributes:
        auth: Auth0 context with authentication info
        client: Auth0 API client instance
        env: Environment name
        checkpoint_manager: Optional checkpoint manager
        resume_checkpoint_id: Optional checkpoint ID to resume from
        auto_delete: Whether to auto-delete (for social operations)
        rotate_password: Whether to rotate passwords during operation
    """

    auth: Auth0Context
    client: Auth0Client
    env: str = "dev"
    checkpoint_manager: CheckpointManager | None = None
    resume_checkpoint_id: str | None = None
    auto_delete: bool = True
    rotate_password: bool = False

    @classmethod
    def from_token(
        cls,
        token: str,
        base_url: str,
        env: str = "dev",
        **kwargs: Any,
    ) -> "OperationContext":
        """Create context from basic parameters.

        Args:
            token: Auth0 access token
            base_url: Auth0 API base URL
            env: Environment name
            **kwargs: Additional context attributes

        Returns:
            Configured OperationContext
        """
        auth = Auth0Context(token=token, base_url=base_url, env=env)
        client = Auth0Client(auth)
        return cls(auth=auth, client=client, env=env, **kwargs)


class BatchOperationProcessor(ABC):
    """Abstract base class for batch operations with checkpointing.

    Subclasses must implement:
    - process_item: Process a single item (items are strings from checkpoint)
    - get_operation_name: Return the operation display name
    - get_operation_type: Return the checkpoint operation type

    Optionally override:
    - display_summary: Custom summary display logic
    - validate_item: Item validation before processing

    Note: Items are always strings because checkpoints store items as strings.
    """

    def __init__(self, context: OperationContext):
        """Initialize the processor.

        Args:
            context: Operation context with auth and configuration
        """
        self.context = context
        self.client = context.client

    @abstractmethod
    def process_item(self, item: str) -> BatchResult:
        """Process a single item in the batch.

        Args:
            item: Item to process

        Returns:
            BatchResult indicating success/failure
        """

    @abstractmethod
    def get_operation_name(self) -> str:
        """Get the human-readable operation name.

        Returns:
            Operation name for display and logging
        """

    @abstractmethod
    def get_operation_type(self) -> OperationType:
        """Get the checkpoint operation type.

        Returns:
            OperationType enum value
        """

    def validate_item(self, item: str) -> tuple[bool, str | None]:
        """Validate an item before processing.

        Override this method to add custom validation.

        Args:
            item: Item to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        return True, None

    def process_batch(
        self,
        items: list[str],
        batch_number: int = 1,
    ) -> BatchResults:
        """Process a batch of items.

        Args:
            items: Items to process
            batch_number: Current batch number for progress display

        Returns:
            BatchResults with aggregated results (including which items were attempted)
        """
        results = BatchResults()

        for idx, item in enumerate(items, 1):
            if shutdown_requested():
                results.was_interrupted = True
                break

            show_progress(
                idx, len(items), f"{self.get_operation_name()} batch {batch_number}"
            )

            # Track this item as attempted (for checkpoint purposes)
            results.items_attempted.append(item)

            # Validate item
            is_valid, error_msg = self.validate_item(item)
            if not is_valid:
                results.skipped_count += 1
                if error_msg:
                    results.items_by_status.setdefault("invalid", []).append(str(item))
                continue

            # Process item
            try:
                result = self.process_item(item)
                if result.success:
                    results.processed_count += 1
                else:
                    results.skipped_count += 1
                    if result.message:
                        results.items_by_status.setdefault("skipped", []).append(
                            str(item)
                        )
            except Exception:
                results.error_count += 1
                results.items_by_status.setdefault("error", []).append(str(item))

        clear_progress_line()
        return results

    def run(
        self,
        items: list[str],
        batch_size: int = 50,
    ) -> str | None:
        """Run the batch operation with checkpoint support.

        Args:
            items: Items to process
            batch_size: Number of items per batch

        Returns:
            Checkpoint ID if operation was interrupted, None if completed
        """
        # Set up checkpoint
        config = CheckpointConfig(
            operation_type=self.get_operation_type(),
            env=self.context.env,
            items=items,
            batch_size=batch_size,
            auto_delete=self.context.auto_delete,
            operation_name=self.get_operation_name(),
        )

        checkpoint_result = load_or_create_checkpoint(
            resume_checkpoint_id=self.context.resume_checkpoint_id,
            checkpoint_manager=self.context.checkpoint_manager,
            config=config,
        )

        checkpoint = checkpoint_result.checkpoint
        checkpoint_manager = checkpoint_result.checkpoint_manager

        try:
            return self._execute_batches(
                checkpoint=checkpoint,
                checkpoint_manager=checkpoint_manager,
                batch_size=batch_size,
            )
        except KeyboardInterrupt:
            return handle_checkpoint_interruption(
                checkpoint,
                checkpoint_manager,
                self.get_operation_name(),
            )
        except Exception as e:
            return handle_checkpoint_error(
                checkpoint,
                checkpoint_manager,
                self.get_operation_name(),
                e,
            )

    def _execute_batches(
        self,
        checkpoint: Checkpoint,
        checkpoint_manager: CheckpointManager,
        batch_size: int,
    ) -> str | None:
        """Execute batch processing loop.

        Args:
            checkpoint: Checkpoint to track progress
            checkpoint_manager: Checkpoint manager instance
            batch_size: Number of items per batch

        Returns:
            Checkpoint ID if interrupted, None if completed
        """
        remaining_items = checkpoint.remaining_items.copy()
        operation_name = self.get_operation_name()

        if not remaining_items:
            print_info(f"No remaining items to process for {operation_name}")
            finalize_checkpoint(checkpoint, checkpoint_manager, operation_name)
            return None

        print_info(
            f"Processing {len(remaining_items)} remaining items for {operation_name}..."
        )

        aggregated_results = BatchResults()

        for batch_start in range(0, len(remaining_items), batch_size):
            if shutdown_requested():
                print_warning(f"\n{operation_name} interrupted")
                checkpoint_manager.save_checkpoint(checkpoint)
                return checkpoint.checkpoint_id

            batch_end = min(batch_start + batch_size, len(remaining_items))
            batch_items = remaining_items[batch_start:batch_end]

            current_batch = checkpoint.progress.current_batch + 1
            total_batches = checkpoint.progress.total_batches

            print_info(
                f"\nProcessing batch {current_batch}/{total_batches} "
                f"({batch_start + 1}-{batch_end} of {len(remaining_items)} remaining)"
            )

            # Process this batch
            batch_results = self.process_batch(batch_items, current_batch)
            aggregated_results.merge(batch_results)

            # Update checkpoint with only the items that were actually attempted
            # This is critical for proper resumption after interruption
            update_checkpoint_batch(
                checkpoint,
                checkpoint_manager,
                batch_results.items_attempted,
                batch_results.to_checkpoint_update(),
            )

            # If batch was interrupted mid-processing, save and return
            if batch_results.was_interrupted:
                print_warning(f"\n{operation_name} interrupted during batch processing")
                checkpoint_manager.save_checkpoint(checkpoint)
                return checkpoint.checkpoint_id

        # Display summary and finalize
        self.display_summary(aggregated_results)
        finalize_checkpoint(checkpoint, checkpoint_manager, operation_name)

        return None

    def display_summary(self, results: BatchResults) -> None:
        """Display operation summary.

        Override this method for custom summary display.

        Args:
            results: Aggregated batch results
        """
        print_info("\nOperation Summary:")
        print_info(f"  Processed: {results.processed_count}")
        print_info(f"  Skipped: {results.skipped_count}")
        if results.error_count > 0:
            print_info(f"  Errors: {results.error_count}")
        if results.not_found_count > 0:
            print_info(f"  Not found: {results.not_found_count}")
