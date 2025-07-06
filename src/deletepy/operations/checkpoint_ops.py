"""Checkpoint operations for resumable batch processing."""

import json
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class CheckpointData:
    """Data structure for checkpoint state."""

    operation_id: str
    operation_type: str
    environment: str
    total_items: int
    processed_items: int
    failed_items: int
    remaining_items: list[str] = field(default_factory=list)
    processed_results: list[dict[str, Any]] = field(default_factory=list)
    failed_results: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_updated: str = field(default_factory=lambda: datetime.now().isoformat())

    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        if self.processed_items + self.failed_items == 0:
            return 0.0
        return (
            self.processed_items / (self.processed_items + self.failed_items)
        ) * 100.0

    @property
    def completion_rate(self) -> float:
        """Calculate completion rate as percentage."""
        if self.total_items == 0:
            return 0.0
        return ((self.processed_items + self.failed_items) / self.total_items) * 100.0


class CheckpointService:
    """Service for managing operation checkpoints."""

    def __init__(self, checkpoint_dir: str = ".checkpoints"):
        """Initialize checkpoint service.

        Args:
            checkpoint_dir: Directory to store checkpoint files
        """
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(exist_ok=True)

    def create_checkpoint(
        self,
        operation_type: str,
        environment: str,
        items: list[str],
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Create a new checkpoint for an operation.

        Args:
            operation_type: Type of operation (delete, block, etc.)
            environment: Environment (dev/prod)
            items: List of items to process
            metadata: Additional metadata to store

        Returns:
            str: Checkpoint ID
        """
        operation_id = self._generate_operation_id(operation_type)

        checkpoint = CheckpointData(
            operation_id=operation_id,
            operation_type=operation_type,
            environment=environment,
            total_items=len(items),
            processed_items=0,
            failed_items=0,
            remaining_items=items.copy(),
            metadata=metadata or {},
        )

        self._save_checkpoint(checkpoint)
        return operation_id

    def update_checkpoint(
        self,
        operation_id: str,
        processed_item: str | None = None,
        failed_item: str | None = None,
        result_data: dict[str, Any] | None = None,
    ) -> None:
        """Update checkpoint with processing results.

        Args:
            operation_id: Checkpoint operation ID
            processed_item: Item that was successfully processed
            failed_item: Item that failed processing
            result_data: Additional result data to store
        """
        checkpoint = self.load_checkpoint(operation_id)
        if not checkpoint:
            raise ValueError(f"Checkpoint {operation_id} not found")

        if processed_item:
            if processed_item in checkpoint.remaining_items:
                checkpoint.remaining_items.remove(processed_item)
            checkpoint.processed_items += 1
            if result_data:
                checkpoint.processed_results.append(
                    {
                        "item": processed_item,
                        "timestamp": datetime.now().isoformat(),
                        "data": result_data,
                    }
                )

        if failed_item:
            if failed_item in checkpoint.remaining_items:
                checkpoint.remaining_items.remove(failed_item)
            checkpoint.failed_items += 1
            if result_data:
                checkpoint.failed_results.append(
                    {
                        "item": failed_item,
                        "timestamp": datetime.now().isoformat(),
                        "error": result_data,
                    }
                )

        checkpoint.last_updated = datetime.now().isoformat()
        self._save_checkpoint(checkpoint)

    def load_checkpoint(self, operation_id: str) -> CheckpointData | None:
        """Load checkpoint data.

        Args:
            operation_id: Checkpoint operation ID

        Returns:
            CheckpointData or None if not found
        """
        checkpoint_file = self.checkpoint_dir / f"{operation_id}.json"
        if not checkpoint_file.exists():
            return None

        try:
            with open(checkpoint_file, encoding="utf-8") as f:
                data = json.load(f)
                return CheckpointData(**data)
        except (json.JSONDecodeError, TypeError) as e:
            print(f"Error loading checkpoint {operation_id}: {e}")
            return None

    def list_checkpoints(
        self, operation_type: str | None = None
    ) -> list[CheckpointData]:
        """List all available checkpoints.

        Args:
            operation_type: Filter by operation type (optional)

        Returns:
            List of checkpoint data
        """
        checkpoints = []

        for checkpoint_file in self.checkpoint_dir.glob("*.json"):
            try:
                with open(checkpoint_file, encoding="utf-8") as f:
                    data = json.load(f)
                    checkpoint = CheckpointData(**data)

                    if (
                        operation_type is None
                        or checkpoint.operation_type == operation_type
                    ):
                        checkpoints.append(checkpoint)
            except (json.JSONDecodeError, TypeError):
                continue

        # Sort by creation time (newest first)
        checkpoints.sort(key=lambda x: x.created_at, reverse=True)
        return checkpoints

    def delete_checkpoint(self, operation_id: str) -> bool:
        """Delete a checkpoint file.

        Args:
            operation_id: Checkpoint operation ID

        Returns:
            bool: True if deleted successfully
        """
        checkpoint_file = self.checkpoint_dir / f"{operation_id}.json"
        if checkpoint_file.exists():
            try:
                checkpoint_file.unlink()
                return True
            except OSError:
                return False
        return False

    def cleanup_old_checkpoints(self, days: int = 7) -> int:
        """Clean up old checkpoint files.

        Args:
            days: Number of days to keep checkpoints

        Returns:
            int: Number of checkpoints deleted
        """
        cutoff_time = time.time() - (days * 24 * 60 * 60)
        deleted_count = 0

        for checkpoint_file in self.checkpoint_dir.glob("*.json"):
            if checkpoint_file.stat().st_mtime < cutoff_time:
                try:
                    checkpoint_file.unlink()
                    deleted_count += 1
                except OSError:
                    continue

        return deleted_count

    def get_checkpoint_info(self, operation_id: str) -> dict[str, Any] | None:
        """Get checkpoint information without loading full data.

        Args:
            operation_id: Checkpoint operation ID

        Returns:
            Basic checkpoint info or None if not found
        """
        checkpoint = self.load_checkpoint(operation_id)
        if not checkpoint:
            return None

        return {
            "operation_id": checkpoint.operation_id,
            "operation_type": checkpoint.operation_type,
            "environment": checkpoint.environment,
            "total_items": checkpoint.total_items,
            "processed_items": checkpoint.processed_items,
            "failed_items": checkpoint.failed_items,
            "remaining_items": len(checkpoint.remaining_items),
            "success_rate": checkpoint.success_rate,
            "completion_rate": checkpoint.completion_rate,
            "created_at": checkpoint.created_at,
            "last_updated": checkpoint.last_updated,
        }

    def _generate_operation_id(self, operation_type: str) -> str:
        """Generate a unique operation ID."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{operation_type}_{timestamp}_{int(time.time() * 1000) % 10000}"

    def _save_checkpoint(self, checkpoint: CheckpointData) -> None:
        """Save checkpoint data to file."""
        checkpoint_file = self.checkpoint_dir / f"{checkpoint.operation_id}.json"

        try:
            with open(checkpoint_file, "w", encoding="utf-8") as f:
                json.dump(asdict(checkpoint), f, indent=2, ensure_ascii=False)
        except OSError as e:
            raise RuntimeError(f"Failed to save checkpoint: {e}") from e


class ResumableOperation:
    """Base class for resumable operations."""

    def __init__(self, checkpoint_service: CheckpointService):
        """Initialize resumable operation.

        Args:
            checkpoint_service: Checkpoint service instance
        """
        self.checkpoint_service = checkpoint_service
        self.current_checkpoint_id: str | None = None

    def start_operation(
        self,
        operation_type: str,
        environment: str,
        items: list[str],
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Start a new resumable operation.

        Args:
            operation_type: Type of operation
            environment: Environment
            items: Items to process
            metadata: Additional metadata

        Returns:
            str: Operation ID
        """
        self.current_checkpoint_id = self.checkpoint_service.create_checkpoint(
            operation_type, environment, items, metadata
        )
        return self.current_checkpoint_id

    def resume_operation(self, operation_id: str) -> CheckpointData | None:
        """Resume an existing operation.

        Args:
            operation_id: Operation ID to resume

        Returns:
            CheckpointData or None if not found
        """
        checkpoint = self.checkpoint_service.load_checkpoint(operation_id)
        if checkpoint:
            self.current_checkpoint_id = operation_id
        return checkpoint

    def record_success(
        self, item: str, result_data: dict[str, Any] | None = None
    ) -> None:
        """Record successful processing of an item.

        Args:
            item: Item that was processed
            result_data: Additional result data
        """
        if self.current_checkpoint_id:
            self.checkpoint_service.update_checkpoint(
                self.current_checkpoint_id, processed_item=item, result_data=result_data
            )

    def record_failure(
        self, item: str, error_data: dict[str, Any] | None = None
    ) -> None:
        """Record failed processing of an item.

        Args:
            item: Item that failed
            error_data: Error information
        """
        if self.current_checkpoint_id:
            self.checkpoint_service.update_checkpoint(
                self.current_checkpoint_id, failed_item=item, result_data=error_data
            )

    def get_remaining_items(self) -> list[str]:
        """Get remaining items to process.

        Returns:
            List of remaining items
        """
        if not self.current_checkpoint_id:
            return []

        checkpoint = self.checkpoint_service.load_checkpoint(self.current_checkpoint_id)
        return checkpoint.remaining_items if checkpoint else []

    def is_complete(self) -> bool:
        """Check if operation is complete.

        Returns:
            bool: True if no remaining items
        """
        return len(self.get_remaining_items()) == 0

    def cleanup_checkpoint(self) -> None:
        """Clean up checkpoint after successful completion."""
        if self.current_checkpoint_id:
            self.checkpoint_service.delete_checkpoint(self.current_checkpoint_id)
            self.current_checkpoint_id = None


def display_checkpoint_summary(checkpoint: CheckpointData) -> None:
    """Display a summary of checkpoint status.

    Args:
        checkpoint: Checkpoint data to display
    """
    from ..utils.display_utils import CYAN, GREEN, RED, RESET, YELLOW

    print(f"\n{GREEN}📋 CHECKPOINT SUMMARY{RESET}")
    print(f"Operation ID: {CYAN}{checkpoint.operation_id}{RESET}")
    print(f"Operation Type: {checkpoint.operation_type}")
    print(f"Environment: {checkpoint.environment}")
    print(f"Created: {checkpoint.created_at}")
    print(f"Last Updated: {checkpoint.last_updated}")

    print(f"\n{GREEN}Progress:{RESET}")
    print(f"Total Items: {checkpoint.total_items}")
    print(f"Processed: {GREEN}{checkpoint.processed_items}{RESET}")
    print(f"Failed: {RED}{checkpoint.failed_items}{RESET}")
    print(f"Remaining: {YELLOW}{len(checkpoint.remaining_items)}{RESET}")
    print(
        f"Completion Rate: {GREEN if checkpoint.completion_rate > 90 else YELLOW}{checkpoint.completion_rate:.1f}%{RESET}"
    )

    if checkpoint.processed_items + checkpoint.failed_items > 0:
        print(
            f"Success Rate: {GREEN if checkpoint.success_rate > 90 else YELLOW}{checkpoint.success_rate:.1f}%{RESET}"
        )

    if checkpoint.metadata:
        print(f"\n{GREEN}Metadata:{RESET}")
        for key, value in checkpoint.metadata.items():
            print(f"  {key}: {value}")


def list_available_checkpoints(checkpoint_service: CheckpointService) -> None:
    """Display list of available checkpoints.

    Args:
        checkpoint_service: Checkpoint service instance
    """
    from ..utils.display_utils import GREEN, RED, RESET, YELLOW

    checkpoints = checkpoint_service.list_checkpoints()

    if not checkpoints:
        print(f"\n{YELLOW}No checkpoints found.{RESET}")
        return

    print(f"\n{GREEN}📁 AVAILABLE CHECKPOINTS{RESET}")
    print(
        f"{'ID':<25} {'Type':<15} {'Env':<4} {'Progress':<12} {'Status':<10} {'Created':<16}"
    )
    print("-" * 90)

    for checkpoint in checkpoints:
        progress = f"{checkpoint.completion_rate:.1f}%"
        if checkpoint.completion_rate == 100:
            status = f"{GREEN}Complete{RESET}"
        elif checkpoint.completion_rate > 0:
            status = f"{YELLOW}In Progress{RESET}"
        else:
            status = f"{RED}Not Started{RESET}"

        created = datetime.fromisoformat(checkpoint.created_at).strftime("%m/%d %H:%M")

        print(
            f"{checkpoint.operation_id:<25} {checkpoint.operation_type:<15} {checkpoint.environment:<4} {progress:<12} {status:<20} {created:<16}"
        )
