"""Checkpoint management utilities for batch operations.

This module provides unified checkpoint loading, creation, and error handling
that is shared across all operation modules.
"""

from dataclasses import dataclass
from typing import Any

from ..models.checkpoint import (
    Checkpoint,
    CheckpointStatus,
    OperationConfig,
    OperationType,
)
from .checkpoint_manager import CheckpointManager
from .output import print_info, print_success, print_warning


@dataclass
class CheckpointConfig:
    """Configuration for checkpoint operations.

    Attributes:
        operation_type: Type of operation being checkpointed
        env: Environment (dev/prod)
        items: List of items to process
        batch_size: Number of items per batch
        auto_delete: Whether auto-delete is enabled (for social operations)
        operation_name: Human-readable name of the operation
        additional_params: Extra parameters to store in checkpoint
    """

    operation_type: OperationType
    env: str
    items: list[str]
    batch_size: int = 50
    auto_delete: bool = True
    operation_name: str = "operation"
    additional_params: dict[str, Any] | None = None


@dataclass
class CheckpointResult:
    """Result of checkpoint setup operation.

    Attributes:
        checkpoint: The checkpoint instance
        checkpoint_manager: The checkpoint manager instance
        env: Environment (possibly updated from loaded checkpoint)
        auto_delete: Auto-delete flag (possibly updated from loaded checkpoint)
        is_resuming: Whether we're resuming an existing checkpoint
    """

    checkpoint: Checkpoint
    checkpoint_manager: CheckpointManager
    env: str
    auto_delete: bool
    is_resuming: bool


def try_load_checkpoint(
    checkpoint_id: str | None,
    checkpoint_manager: CheckpointManager,
    operation_name: str = "operation",
) -> Checkpoint | None:
    """Try to load an existing checkpoint with validation.

    Args:
        checkpoint_id: Optional checkpoint ID to resume from
        checkpoint_manager: Checkpoint manager instance
        operation_name: Name of operation for logging

    Returns:
        Valid checkpoint if found and resumable, None otherwise
    """
    if not checkpoint_id:
        return None

    checkpoint = checkpoint_manager.load_checkpoint(checkpoint_id)
    if not checkpoint:
        print_warning(
            f"Could not load checkpoint {checkpoint_id}, starting fresh",
            operation=operation_name,
        )
        return None

    # Validate checkpoint is resumable (handles ACTIVE, FAILED, CANCELLED states)
    if not checkpoint.is_resumable():
        print_warning(
            f"Checkpoint {checkpoint_id} is not resumable",
            operation=operation_name,
            checkpoint_id=checkpoint_id,
        )
        return None

    return checkpoint


def create_checkpoint(
    checkpoint_manager: CheckpointManager,
    config: CheckpointConfig,
) -> Checkpoint:
    """Create a new checkpoint for the operation.

    Args:
        checkpoint_manager: Checkpoint manager instance
        config: Checkpoint configuration

    Returns:
        Newly created checkpoint
    """
    additional_params = {
        **(config.additional_params or {}),
        "operation": config.operation_name,
    }

    operation_config = OperationConfig(
        environment=config.env,
        auto_delete=config.auto_delete,
        additional_params=additional_params,
    )

    checkpoint = checkpoint_manager.create_checkpoint(
        operation_type=config.operation_type,
        config=operation_config,
        items=config.items,
        batch_size=config.batch_size,
    )

    return checkpoint


def load_or_create_checkpoint(
    resume_checkpoint_id: str | None,
    checkpoint_manager: CheckpointManager | None,
    config: CheckpointConfig,
) -> CheckpointResult:
    """Load existing checkpoint or create a new one.

    This is the main entry point for checkpoint setup. It handles:
    - Initializing checkpoint manager if not provided
    - Loading existing checkpoint if resume ID is provided
    - Creating new checkpoint if not resuming
    - Extracting configuration from loaded checkpoints

    Args:
        resume_checkpoint_id: Optional checkpoint ID to resume from
        checkpoint_manager: Optional checkpoint manager instance
        config: Checkpoint configuration for new checkpoints

    Returns:
        CheckpointResult containing checkpoint, manager, and configuration
    """
    # Initialize checkpoint manager if not provided
    if checkpoint_manager is None:
        checkpoint_manager = CheckpointManager()

    # Try to load existing checkpoint
    checkpoint = try_load_checkpoint(
        resume_checkpoint_id,
        checkpoint_manager,
        config.operation_name,
    )

    is_resuming = checkpoint is not None
    env = config.env
    auto_delete = config.auto_delete

    if checkpoint is not None:
        # Use configuration from loaded checkpoint
        if checkpoint.config:
            env = checkpoint.config.environment
            auto_delete = checkpoint.config.auto_delete

        print_success(
            f"Resuming from checkpoint: {checkpoint.checkpoint_id}",
            operation=config.operation_name,
            checkpoint_id=checkpoint.checkpoint_id,
        )
    else:
        # Create new checkpoint
        checkpoint = create_checkpoint(checkpoint_manager, config)
        print_info(
            f"Created checkpoint: {checkpoint.checkpoint_id}",
            operation=config.operation_name,
            checkpoint_id=checkpoint.checkpoint_id,
        )

    # Save initial checkpoint state
    checkpoint_manager.save_checkpoint(checkpoint)

    return CheckpointResult(
        checkpoint=checkpoint,
        checkpoint_manager=checkpoint_manager,
        env=env,
        auto_delete=auto_delete,
        is_resuming=is_resuming,
    )


def handle_checkpoint_interruption(
    checkpoint: Checkpoint,
    checkpoint_manager: CheckpointManager,
    operation_name: str,
) -> str:
    """Handle checkpoint interruption (KeyboardInterrupt).

    Args:
        checkpoint: Checkpoint to save
        checkpoint_manager: Checkpoint manager instance
        operation_name: Name of the operation for logging

    Returns:
        Checkpoint ID
    """
    print_warning(
        f"\n{operation_name} interrupted by user",
        operation=operation_name,
    )
    checkpoint_manager.mark_checkpoint_cancelled(checkpoint)
    checkpoint_manager.save_checkpoint(checkpoint)
    print_info(
        "You can resume this operation later using:",
        operation=operation_name,
    )
    print_info(
        f"  deletepy resume {checkpoint.checkpoint_id}",
        operation=operation_name,
        checkpoint_id=checkpoint.checkpoint_id,
    )
    return checkpoint.checkpoint_id


def handle_checkpoint_error(
    checkpoint: Checkpoint,
    checkpoint_manager: CheckpointManager,
    operation_name: str,
    error: Exception,
) -> str:
    """Handle checkpoint error.

    Args:
        checkpoint: Checkpoint to save
        checkpoint_manager: Checkpoint manager instance
        operation_name: Name of the operation for logging
        error: Exception that occurred

    Returns:
        Checkpoint ID
    """
    print_warning(
        f"\n{operation_name} failed: {error}",
        operation=operation_name,
        error=str(error),
    )
    checkpoint_manager.mark_checkpoint_failed(checkpoint, str(error))
    checkpoint_manager.save_checkpoint(checkpoint)
    return checkpoint.checkpoint_id


def finalize_checkpoint(
    checkpoint: Checkpoint,
    checkpoint_manager: CheckpointManager,
    operation_name: str,
) -> None:
    """Finalize checkpoint as completed.

    Args:
        checkpoint: Checkpoint to finalize
        checkpoint_manager: Checkpoint manager instance
        operation_name: Name of the operation for logging
    """
    checkpoint.status = CheckpointStatus.COMPLETED
    checkpoint_manager.save_checkpoint(checkpoint)
    print_success(
        f"{operation_name} completed! Checkpoint: {checkpoint.checkpoint_id}",
        operation=operation_name,
        checkpoint_id=checkpoint.checkpoint_id,
    )


def update_checkpoint_batch(
    checkpoint: Checkpoint,
    checkpoint_manager: CheckpointManager,
    processed_items: list[str],
    results_update: dict[str, Any],
) -> None:
    """Update checkpoint after processing a batch.

    Args:
        checkpoint: Checkpoint to update
        checkpoint_manager: Checkpoint manager instance
        processed_items: Items that were processed in this batch
        results_update: Results dictionary to merge into checkpoint
    """
    checkpoint_manager.update_checkpoint_progress(
        checkpoint=checkpoint,
        processed_items=processed_items,
        results_update=results_update,
    )
    checkpoint_manager.save_checkpoint(checkpoint)
