"""Checkpoint manager for handling resumable operations."""

import shutil
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from ..models.checkpoint import (
    BatchProgress,
    Checkpoint,
    CheckpointStatus,
    OperationConfig,
    OperationType,
    ProcessingResults,
)
from ..utils.display_utils import (
    CYAN,
    GREEN,
    RED,
    RESET,
    YELLOW,
    print_error,
    print_info,
    print_success,
    print_warning,
)


class CheckpointManager:
    """Manages checkpoint operations for resumable batch processing."""

    def __init__(self, checkpoint_dir: str | Path = ".checkpoints"):
        """Initialize checkpoint manager.

        Args:
            checkpoint_dir: Directory to store checkpoint files
        """
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

    def generate_checkpoint_id(self, operation_type: OperationType, env: str) -> str:
        """Generate a unique checkpoint ID.

        Args:
            operation_type: Type of operation
            env: Environment (dev/prod)

        Returns:
            str: Unique checkpoint ID
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        return f"{operation_type.value}_{env}_{timestamp}_{unique_id}"

    def get_checkpoint_path(self, checkpoint_id: str) -> Path:
        """Get the file path for a checkpoint.

        Args:
            checkpoint_id: Checkpoint ID

        Returns:
            Path: File path for the checkpoint
        """
        return self.checkpoint_dir / f"{checkpoint_id}.json"

    def save_checkpoint(self, checkpoint: Checkpoint) -> bool:
        """Save a checkpoint to disk.

        Args:
            checkpoint: Checkpoint to save

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            checkpoint.updated_at = datetime.now()
            checkpoint_path = self.get_checkpoint_path(checkpoint.checkpoint_id)

            # Create backup if checkpoint already exists
            if checkpoint_path.exists():
                backup_path = checkpoint_path.with_suffix(".json.backup")
                shutil.copy2(checkpoint_path, backup_path)

            checkpoint.save_to_file(checkpoint_path)

            print_info(f"Checkpoint saved: {checkpoint.checkpoint_id}")
            return True

        except Exception as e:
            print_error(f"Failed to save checkpoint {checkpoint.checkpoint_id}: {e}")
            return False

    def load_checkpoint(self, checkpoint_id: str) -> Checkpoint | None:
        """Load a checkpoint from disk.

        Args:
            checkpoint_id: Checkpoint ID to load

        Returns:
            Optional[Checkpoint]: Loaded checkpoint or None if not found
        """
        try:
            checkpoint_path = self.get_checkpoint_path(checkpoint_id)

            if not checkpoint_path.exists():
                print_error(f"Checkpoint not found: {checkpoint_id}")
                return None

            checkpoint = Checkpoint.load_from_file(checkpoint_path)
            print_success(f"Checkpoint loaded: {checkpoint_id}")
            return checkpoint

        except Exception as e:
            print_error(f"Failed to load checkpoint {checkpoint_id}: {e}")
            return None

    def list_checkpoints(
        self,
        operation_type: OperationType | None = None,
        status: CheckpointStatus | None = None,
        environment: str | None = None,
    ) -> list[Checkpoint]:
        """List all checkpoints with optional filters.

        Args:
            operation_type: Filter by operation type
            status: Filter by status
            environment: Filter by environment

        Returns:
            List[Checkpoint]: List of matching checkpoints
        """
        checkpoints = []

        try:
            for checkpoint_file in self.checkpoint_dir.glob("*.json"):
                if checkpoint_file.suffix == ".backup":
                    continue

                try:
                    checkpoint = Checkpoint.load_from_file(checkpoint_file)

                    # Apply filters
                    if operation_type and checkpoint.operation_type != operation_type:
                        continue
                    if status and checkpoint.status != status:
                        continue
                    if environment and checkpoint.config.environment != environment:
                        continue

                    checkpoints.append(checkpoint)

                except Exception as e:
                    print_warning(
                        f"Failed to load checkpoint file {checkpoint_file}: {e}"
                    )
                    continue

            # Sort by created_at (newest first)
            checkpoints.sort(key=lambda x: x.created_at, reverse=True)

        except Exception as e:
            print_error(f"Failed to list checkpoints: {e}")

        return checkpoints

    def delete_checkpoint(self, checkpoint_id: str) -> bool:
        """Delete a checkpoint.

        Args:
            checkpoint_id: Checkpoint ID to delete

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            checkpoint_path = self.get_checkpoint_path(checkpoint_id)

            if not checkpoint_path.exists():
                print_warning(f"Checkpoint not found: {checkpoint_id}")
                return False

            checkpoint_path.unlink()

            # Also delete backup if it exists
            backup_path = checkpoint_path.with_suffix(".json.backup")
            if backup_path.exists():
                backup_path.unlink()

            print_success(f"Checkpoint deleted: {checkpoint_id}")
            return True

        except Exception as e:
            print_error(f"Failed to delete checkpoint {checkpoint_id}: {e}")
            return False

    def clean_old_checkpoints(self, days_old: int = 30) -> int:
        """Clean up old checkpoints.

        Args:
            days_old: Delete checkpoints older than this many days

        Returns:
            int: Number of checkpoints deleted
        """
        deleted_count = 0
        cutoff_date = datetime.now() - timedelta(days=days_old)

        try:
            for checkpoint_file in self.checkpoint_dir.glob("*.json"):
                if checkpoint_file.suffix == ".backup":
                    continue

                try:
                    checkpoint = Checkpoint.load_from_file(checkpoint_file)

                    # Only delete completed, failed, or cancelled checkpoints
                    if (
                        checkpoint.status
                        in [
                            CheckpointStatus.COMPLETED,
                            CheckpointStatus.FAILED,
                            CheckpointStatus.CANCELLED,
                        ]
                        and checkpoint.created_at < cutoff_date
                    ):
                        if self.delete_checkpoint(checkpoint.checkpoint_id):
                            deleted_count += 1

                except Exception as e:
                    print_warning(
                        f"Failed to process checkpoint file {checkpoint_file}: {e}"
                    )
                    continue

            if deleted_count > 0:
                print_success(f"Cleaned up {deleted_count} old checkpoints")
            else:
                print_info("No old checkpoints to clean up")

        except Exception as e:
            print_error(f"Failed to clean old checkpoints: {e}")

        return deleted_count

    def clean_failed_checkpoints(self) -> int:
        """Clean up failed checkpoints.

        Returns:
            int: Number of checkpoints deleted
        """
        deleted_count = 0

        try:
            checkpoints = self.list_checkpoints(status=CheckpointStatus.FAILED)

            for checkpoint in checkpoints:
                if self.delete_checkpoint(checkpoint.checkpoint_id):
                    deleted_count += 1

            if deleted_count > 0:
                print_success(f"Cleaned up {deleted_count} failed checkpoints")
            else:
                print_info("No failed checkpoints to clean up")

        except Exception as e:
            print_error(f"Failed to clean failed checkpoints: {e}")

        return deleted_count

    def clean_completed_checkpoints(self, dry_run: bool = False) -> int:
        """Clean up completed checkpoints regardless of age.

        Args:
            dry_run: If True, only show what would be deleted without deleting

        Returns:
            int: Number of checkpoints deleted (or would be deleted in dry-run)
        """
        deleted_count = 0

        try:
            checkpoints = self.list_checkpoints(status=CheckpointStatus.COMPLETED)

            if dry_run:
                if checkpoints:
                    print_info(
                        f"Would delete {len(checkpoints)} completed checkpoints:"
                    )
                    self.display_checkpoints(checkpoints)
                    return len(checkpoints)
                else:
                    print_info("No completed checkpoints found to clean up")
                    return 0

            for checkpoint in checkpoints:
                if self.delete_checkpoint(checkpoint.checkpoint_id):
                    deleted_count += 1

            if deleted_count > 0:
                print_success(f"Cleaned up {deleted_count} completed checkpoints")
            else:
                print_info("No completed checkpoints to clean up")

        except Exception as e:
            print_error(f"Failed to clean completed checkpoints: {e}")

        return deleted_count

    def create_checkpoint(
        self,
        operation_type: OperationType,
        config: OperationConfig,
        items: list[str],
        batch_size: int = 50,
    ) -> Checkpoint:
        """Create a new checkpoint.

        Args:
            operation_type: Type of operation
            config: Operation configuration
            items: List of items to process
            batch_size: Batch size for processing

        Returns:
            Checkpoint: New checkpoint instance
        """
        checkpoint_id = self.generate_checkpoint_id(operation_type, config.environment)
        now = datetime.now()

        total_items = len(items)
        total_batches = (total_items + batch_size - 1) // batch_size

        progress = BatchProgress(
            current_batch=0,
            total_batches=total_batches,
            current_item=0,
            total_items=total_items,
            batch_size=batch_size,
        )

        results = ProcessingResults()

        checkpoint = Checkpoint(
            checkpoint_id=checkpoint_id,
            operation_type=operation_type,
            status=CheckpointStatus.ACTIVE,
            created_at=now,
            updated_at=now,
            config=config,
            progress=progress,
            results=results,
            remaining_items=items.copy(),
            processed_items=[],
        )

        return checkpoint

    def update_checkpoint_progress(
        self,
        checkpoint: Checkpoint,
        processed_items: list[str],
        results_update: dict[str, Any],
    ) -> None:
        """Update checkpoint progress after processing a batch.

        Args:
            checkpoint: Checkpoint to update
            processed_items: Items that were processed in this batch
            results_update: Results to add to the checkpoint
        """
        self._update_progress_counters(checkpoint, processed_items)
        self._update_results(checkpoint, results_update)
        self._update_item_lists(checkpoint, processed_items)
        self._check_and_update_completion_status(checkpoint)
        self._update_timestamp(checkpoint)

    def _update_progress_counters(
        self, checkpoint: Checkpoint, processed_items: list[str]
    ) -> None:
        """Update progress counters for the checkpoint.

        Args:
            checkpoint: Checkpoint to update
            processed_items: Items that were processed in this batch
        """
        checkpoint.progress.current_batch += 1
        checkpoint.progress.current_item += len(processed_items)

    def _update_results(
        self, checkpoint: Checkpoint, results_update: dict[str, Any]
    ) -> None:
        """Update results data in the checkpoint.

        Args:
            checkpoint: Checkpoint to update
            results_update: Results to add to the checkpoint
        """
        for key, value in results_update.items():
            if hasattr(checkpoint.results, key):
                if isinstance(value, int):
                    setattr(
                        checkpoint.results,
                        key,
                        getattr(checkpoint.results, key) + value,
                    )
                elif isinstance(value, list):
                    getattr(checkpoint.results, key).extend(value)
                elif isinstance(value, dict):
                    getattr(checkpoint.results, key).update(value)

    def _update_item_lists(
        self, checkpoint: Checkpoint, processed_items: list[str]
    ) -> None:
        """Update processed and remaining item lists.

        Args:
            checkpoint: Checkpoint to update
            processed_items: Items that were processed in this batch
        """
        checkpoint.processed_items.extend(processed_items)
        # Optimize removal by using set operation instead of loop (O(n) vs O(n²))
        processed_set = set(processed_items)
        checkpoint.remaining_items = [
            item for item in checkpoint.remaining_items if item not in processed_set
        ]

    def _check_and_update_completion_status(self, checkpoint: Checkpoint) -> None:
        """Check if operation is complete and update status accordingly.

        Args:
            checkpoint: Checkpoint to check and update
        """
        if len(checkpoint.remaining_items) == 0:
            checkpoint.status = CheckpointStatus.COMPLETED

    def _update_timestamp(self, checkpoint: Checkpoint) -> None:
        """Update the checkpoint's last updated timestamp.

        Args:
            checkpoint: Checkpoint to update
        """
        checkpoint.updated_at = datetime.now()

    def mark_checkpoint_failed(self, checkpoint: Checkpoint, error: str) -> None:
        """Mark a checkpoint as failed.

        Args:
            checkpoint: Checkpoint to mark as failed
            error: Error message
        """
        checkpoint.status = CheckpointStatus.FAILED
        checkpoint.updated_at = datetime.now()

        # Add error to results
        checkpoint.results.errors.append(
            {
                "error": error,
                "timestamp": datetime.now().isoformat(),
                "operation": checkpoint.operation_type.value,
            }
        )

        checkpoint.results.error_count += 1

    def mark_checkpoint_cancelled(self, checkpoint: Checkpoint) -> None:
        """Mark a checkpoint as cancelled.

        Args:
            checkpoint: Checkpoint to mark as cancelled
        """
        checkpoint.status = CheckpointStatus.CANCELLED
        checkpoint.updated_at = datetime.now()

    def reactivate_checkpoint(self, checkpoint: Checkpoint) -> None:
        """Reactivate a cancelled or failed checkpoint for resumption.

        Args:
            checkpoint: Checkpoint to reactivate
        """
        if checkpoint.status in (CheckpointStatus.CANCELLED, CheckpointStatus.FAILED):
            checkpoint.status = CheckpointStatus.ACTIVE
            checkpoint.updated_at = datetime.now()
            self.save_checkpoint(checkpoint)
            print_info(
                f"Checkpoint {checkpoint.checkpoint_id} reactivated for resumption"
            )

    def display_checkpoints(self, checkpoints: list[Checkpoint]) -> None:
        """Display checkpoints in a formatted table.

        Args:
            checkpoints: List of checkpoints to display
        """
        if not checkpoints:
            print_info("No checkpoints found.")
            return

        print(f"\n{GREEN}Available Checkpoints:{RESET}")
        print(
            f"{'ID':<20} {'Type':<18} {'Status':<12} {'Progress':<10} {'Created':<20} {'Environment':<6}"
        )
        print("-" * 95)

        for checkpoint in checkpoints:
            status_color = {
                CheckpointStatus.ACTIVE: YELLOW,
                CheckpointStatus.COMPLETED: GREEN,
                CheckpointStatus.FAILED: RED,
                CheckpointStatus.CANCELLED: CYAN,
            }.get(checkpoint.status, RESET)

            progress_pct = checkpoint.get_completion_percentage()

            print(
                f"{checkpoint.checkpoint_id:<20} "
                f"{checkpoint.operation_type.value:<18} "
                f"{status_color}{checkpoint.status.value:<12}{RESET} "
                f"{progress_pct:>6.1f}%   "
                f"{checkpoint.created_at.strftime('%Y-%m-%d %H:%M'):<20} "
                f"{checkpoint.config.environment:<6}"
            )

        print("")

    def display_checkpoint_details(self, checkpoint: Checkpoint) -> None:
        """Display detailed information about a checkpoint.

        Args:
            checkpoint: Checkpoint to display details for
        """
        summary = checkpoint.get_summary()

        print(f"\n{GREEN}Checkpoint Details:{RESET}")
        print(f"ID: {CYAN}{summary['checkpoint_id']}{RESET}")
        print(f"Operation: {summary['operation_type']}")
        print(f"Status: {summary['status']}")
        print(f"Environment: {summary['environment']}")
        print(f"Created: {summary['created_at']}")
        print(f"Updated: {summary['updated_at']}")
        print(
            f"Progress: {summary['completion_percentage']:.1f}% ({summary['processed_items']}/{summary['total_items']})"
        )
        print(f"Success Rate: {summary['success_rate']:.1f}%")
        print(f"Remaining Items: {summary['remaining_items']}")
        print(f"Resumable: {'Yes' if summary['is_resumable'] else 'No'}")

        if summary["input_file"]:
            print(f"Input File: {summary['input_file']}")
        if summary["output_file"]:
            print(f"Output File: {summary['output_file']}")

        print("\nResults:")
        results = checkpoint.results
        print(f"  Processed: {results.processed_count}")
        print(f"  Skipped: {results.skipped_count}")
        print(f"  Errors: {results.error_count}")
        print(f"  Not Found: {results.not_found_count}")
        print(f"  Multiple Users: {results.multiple_users_count}")

        if results.errors:
            print("\nRecent Errors:")
            for error in results.errors[-3:]:  # Show last 3 errors
                print(f"  - {error.get('error', 'Unknown error')}")

        print("")

    def get_checkpoint_size(self, checkpoint_id: str) -> int:
        """Get the size of a checkpoint file in bytes.

        Args:
            checkpoint_id: Checkpoint ID

        Returns:
            int: File size in bytes, or 0 if not found
        """
        try:
            checkpoint_path = self.get_checkpoint_path(checkpoint_id)
            if checkpoint_path.exists():
                return checkpoint_path.stat().st_size
            return 0
        except Exception:
            return 0

    def get_total_checkpoint_size(self) -> int:
        """Get the total size of all checkpoint files.

        Returns:
            int: Total size in bytes
        """
        total_size = 0
        try:
            for checkpoint_file in self.checkpoint_dir.glob("*.json"):
                total_size += checkpoint_file.stat().st_size
        except Exception:
            pass
        return total_size

    def backup_checkpoint(self, checkpoint_id: str) -> bool:
        """Create a backup of a checkpoint.

        Args:
            checkpoint_id: Checkpoint ID to backup

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            checkpoint_path = self.get_checkpoint_path(checkpoint_id)

            if not checkpoint_path.exists():
                print_error(f"Checkpoint not found: {checkpoint_id}")
                return False

            backup_path = checkpoint_path.with_suffix(".json.backup")
            shutil.copy2(checkpoint_path, backup_path)

            print_success(f"Checkpoint backed up: {checkpoint_id}")
            return True

        except Exception as e:
            print_error(f"Failed to backup checkpoint {checkpoint_id}: {e}")
            return False
