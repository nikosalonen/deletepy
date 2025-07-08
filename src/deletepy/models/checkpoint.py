"""Checkpoint data models for resumable operations."""

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

# Current software version for checkpoint compatibility
CURRENT_VERSION = "1.0.0"


class OperationType(Enum):
    """Types of operations that can be checkpointed."""

    EXPORT_LAST_LOGIN = "export_last_login"
    BATCH_DELETE = "batch_delete"
    BATCH_BLOCK = "batch_block"
    BATCH_REVOKE_GRANTS = "batch_revoke_grants"
    SOCIAL_UNLINK = "social_unlink"
    CHECK_UNBLOCKED = "check_unblocked"
    CHECK_DOMAINS = "check_domains"


class CheckpointStatus(Enum):
    """Status of a checkpoint."""

    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ProcessingResults:
    """Results from processing operations."""

    processed_count: int = 0
    skipped_count: int = 0
    error_count: int = 0
    not_found_count: int = 0
    multiple_users_count: int = 0
    not_found_users: list[str] = field(default_factory=list)
    invalid_user_ids: list[str] = field(default_factory=list)
    multiple_users: dict[str, list[str]] = field(default_factory=dict)
    errors: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "processed_count": self.processed_count,
            "skipped_count": self.skipped_count,
            "error_count": self.error_count,
            "not_found_count": self.not_found_count,
            "multiple_users_count": self.multiple_users_count,
            "not_found_users": self.not_found_users,
            "invalid_user_ids": self.invalid_user_ids,
            "multiple_users": self.multiple_users,
            "errors": self.errors,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProcessingResults":
        """Create from dictionary."""
        return cls(
            processed_count=data.get("processed_count", 0),
            skipped_count=data.get("skipped_count", 0),
            error_count=data.get("error_count", 0),
            not_found_count=data.get("not_found_count", 0),
            multiple_users_count=data.get("multiple_users_count", 0),
            not_found_users=data.get("not_found_users", []),
            invalid_user_ids=data.get("invalid_user_ids", []),
            multiple_users=data.get("multiple_users", {}),
            errors=data.get("errors", []),
        )


@dataclass
class BatchProgress:
    """Progress tracking for batch operations."""

    current_batch: int = 0
    total_batches: int = 0
    current_item: int = 0
    total_items: int = 0
    batch_size: int = 50

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "current_batch": self.current_batch,
            "total_batches": self.total_batches,
            "current_item": self.current_item,
            "total_items": self.total_items,
            "batch_size": self.batch_size,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BatchProgress":
        """Create from dictionary."""
        return cls(
            current_batch=data.get("current_batch", 0),
            total_batches=data.get("total_batches", 0),
            current_item=data.get("current_item", 0),
            total_items=data.get("total_items", 0),
            batch_size=data.get("batch_size", 50),
        )


@dataclass
class OperationConfig:
    """Configuration for an operation."""

    environment: str
    input_file: str | None = None
    output_file: str | None = None
    connection_filter: str | None = None
    dry_run: bool = False
    auto_delete: bool = False
    batch_size: int | None = None
    additional_params: dict[str, Any] = field(default_factory=dict)

    def validate_for_operation(self, operation_type: OperationType) -> None:
        """Validate configuration for specific operation types.

        Args:
            operation_type: The type of operation to validate for

        Raises:
            ValueError: If required fields are missing for the operation type
        """
        if operation_type == OperationType.EXPORT_LAST_LOGIN:
            if not self.output_file:
                raise ValueError(
                    f"output_file is required for {operation_type.value} operations"
                )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "environment": self.environment,
            "input_file": self.input_file,
            "output_file": self.output_file,
            "connection_filter": self.connection_filter,
            "dry_run": self.dry_run,
            "auto_delete": self.auto_delete,
            "batch_size": self.batch_size,
            "additional_params": self.additional_params,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "OperationConfig":
        """Create from dictionary."""
        return cls(
            environment=data.get("environment", "dev"),
            input_file=data.get("input_file"),
            output_file=data.get("output_file"),
            connection_filter=data.get("connection_filter"),
            dry_run=data.get("dry_run", False),
            auto_delete=data.get("auto_delete", False),
            batch_size=data.get("batch_size"),
            additional_params=data.get("additional_params", {}),
        )


@dataclass
class Checkpoint:
    """Main checkpoint data structure."""

    checkpoint_id: str
    operation_type: OperationType
    status: CheckpointStatus
    created_at: datetime
    updated_at: datetime
    config: OperationConfig
    progress: BatchProgress
    results: ProcessingResults
    remaining_items: list[str] = field(default_factory=list)
    processed_items: list[str] = field(default_factory=list)
    version: str = "1.0.0"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "checkpoint_id": self.checkpoint_id,
            "operation_type": self.operation_type.value,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "config": self.config.to_dict(),
            "progress": self.progress.to_dict(),
            "results": self.results.to_dict(),
            "remaining_items": self.remaining_items,
            "processed_items": self.processed_items,
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Checkpoint":
        """Create from dictionary."""
        # Handle enum fields - require operation_type to be present
        operation_type = data.get("operation_type")
        if operation_type is None:
            raise ValueError("Missing required field: operation_type")
        operation_type = OperationType(operation_type)

        status = data.get("status")
        if status is None:
            status = CheckpointStatus.ACTIVE
        else:
            status = CheckpointStatus(status)

        # Handle timestamp fields - require them to be present or raise error
        created_at_str = data.get("created_at")
        if created_at_str is None:
            raise ValueError("Missing required field: created_at")

        updated_at_str = data.get("updated_at")
        if updated_at_str is None:
            raise ValueError("Missing required field: updated_at")

        # Create and validate configuration
        config = OperationConfig.from_dict(data.get("config", {}))
        try:
            config.validate_for_operation(operation_type)
        except ValueError as e:
            raise ValueError(f"Invalid checkpoint configuration: {e}") from e

        return cls(
            checkpoint_id=data.get("checkpoint_id", ""),
            operation_type=operation_type,
            status=status,
            created_at=datetime.fromisoformat(created_at_str),
            updated_at=datetime.fromisoformat(updated_at_str),
            config=config,
            progress=BatchProgress.from_dict(data.get("progress", {})),
            results=ProcessingResults.from_dict(data.get("results", {})),
            remaining_items=data.get("remaining_items", []),
            processed_items=data.get("processed_items", []),
            version=data.get("version", "1.0.0"),
        )

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> "Checkpoint":
        """Create from JSON string."""
        data = json.loads(json_str)
        return cls.from_dict(data)

    def save_to_file(self, file_path: str | Path) -> None:
        """Save checkpoint to file."""
        file_path = Path(file_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(self.to_json())

    @classmethod
    def load_from_file(cls, file_path: str | Path) -> "Checkpoint":
        """Load checkpoint from file."""
        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"Checkpoint file not found: {file_path}")

        with open(file_path, encoding="utf-8") as f:
            return cls.from_json(f.read())

    def get_completion_percentage(self) -> float:
        """Get completion percentage."""
        if self.progress.total_items == 0:
            return 0.0
        return (self.progress.current_item / self.progress.total_items) * 100.0

    def get_success_rate(self) -> float:
        """Get success rate of processed items."""
        total_processed = (
            self.results.processed_count
            + self.results.skipped_count
            + self.results.error_count
        )
        if total_processed == 0:
            return 0.0
        return (self.results.processed_count / total_processed) * 100.0

    def is_resumable(self) -> bool:
        """Check if checkpoint can be resumed."""
        return (
            self.status
            in (
                CheckpointStatus.ACTIVE,
                CheckpointStatus.FAILED,
                CheckpointStatus.CANCELLED,
            )
            and len(self.remaining_items) > 0
            and self._is_version_compatible()
        )

    def _is_version_compatible(self) -> bool:
        """Check if checkpoint version is compatible with current software version."""
        # For now, we only support exact version match
        # In the future, this could be extended to support version ranges
        return self.version == CURRENT_VERSION

    def get_summary(self) -> dict[str, Any]:
        """Get checkpoint summary."""
        return {
            "checkpoint_id": self.checkpoint_id,
            "operation_type": self.operation_type.value,
            "status": self.status.value,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
            "completion_percentage": self.get_completion_percentage(),
            "success_rate": self.get_success_rate(),
            "total_items": self.progress.total_items,
            "processed_items": self.progress.current_item,
            "remaining_items": len(self.remaining_items),
            "environment": self.config.environment,
            "input_file": self.config.input_file,
            "output_file": self.config.output_file,
            "is_resumable": self.is_resumable(),
        }
