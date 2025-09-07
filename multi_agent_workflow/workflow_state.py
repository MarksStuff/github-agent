#!/usr/bin/env python3
"""
Workflow State Management for Enhanced Multi-Agent Workflow System

This module provides state persistence and recovery mechanisms to make
the workflow system idempotent and resumable from any failure point.
"""

import hashlib
import json
import logging
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class StageStatus(Enum):
    """Status of a workflow stage."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    PAUSED = "paused"


@dataclass
class StageState:
    """State information for a single workflow stage."""

    name: str
    status: StageStatus
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    output_files: list[str] = None
    metrics: dict[str, Any] = None

    def __post_init__(self):
        """Initialize default values."""
        if self.output_files is None:
            self.output_files = []
        if self.metrics is None:
            self.metrics = {}

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary with datetime serialization."""
        data = asdict(self)
        data["status"] = self.status.value
        if self.started_at:
            data["started_at"] = self.started_at.isoformat()
        if self.completed_at:
            data["completed_at"] = self.completed_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StageState":
        """Create from dictionary with datetime parsing."""
        # Convert status back to enum
        data["status"] = StageStatus(data["status"])

        # Parse datetime strings
        if data.get("started_at"):
            data["started_at"] = datetime.fromisoformat(data["started_at"])
        if data.get("completed_at"):
            data["completed_at"] = datetime.fromisoformat(data["completed_at"])

        return cls(**data)


@dataclass
class WorkflowInputs:
    """Input parameters and their checksums for change detection."""

    project_description: str
    config_overrides: dict[str, Any] = None
    template_name: Optional[str] = None

    def __post_init__(self):
        """Initialize default values."""
        if self.config_overrides is None:
            self.config_overrides = {}

    def calculate_checksum(self) -> str:
        """Calculate checksum of all inputs to detect changes."""
        # Create a canonical string representation of inputs
        canonical = {
            "project_description": self.project_description,
            "config_overrides": sorted(self.config_overrides.items())
            if self.config_overrides
            else [],
            "template_name": self.template_name or "",
        }

        # Convert to JSON string with sorted keys for consistency
        json_str = json.dumps(canonical, sort_keys=True)

        # Calculate SHA256 hash
        return hashlib.sha256(json_str.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorkflowInputs":
        """Create from dictionary."""
        return cls(**data)


class WorkflowState:
    """
    Manages workflow state persistence and recovery.

    This class provides:
    - State tracking for each workflow stage
    - Persistence to JSON files
    - Recovery from interrupted workflows
    - Input change detection via checksums
    - Rollback capabilities
    """

    # Default workflow stages in execution order
    DEFAULT_STAGES = [
        "requirements_analysis",
        "architecture_design",
        "implementation_plan",
        "code_generation",
        "testing_setup",
        "documentation",
    ]

    def __init__(self, workflow_id: str, state_file: Optional[Path] = None):
        """
        Initialize workflow state.

        Args:
            workflow_id: Unique identifier for this workflow run
            state_file: Optional custom state file path
        """
        self.workflow_id = workflow_id
        self.created_at = datetime.now(UTC)
        self.updated_at = self.created_at
        self.inputs: Optional[WorkflowInputs] = None
        self.inputs_checksum: Optional[str] = None
        self.current_stage: Optional[str] = None
        self.stages: dict[str, StageState] = {}
        self.metadata: dict[str, Any] = {}

        # Set up state file path
        if state_file:
            self.state_file = Path(state_file)
        else:
            # Default location: multi_agent_workflow/state/{workflow_id}_state.json
            state_dir = Path(__file__).parent / "state"
            state_dir.mkdir(exist_ok=True)
            self.state_file = state_dir / f"{workflow_id}_state.json"

        # Initialize default stages
        self._initialize_stages()

        logger.info(f"Initialized workflow state for {workflow_id}")

    def _initialize_stages(self):
        """Initialize all stages with PENDING status."""
        for stage_name in self.DEFAULT_STAGES:
            self.stages[stage_name] = StageState(
                name=stage_name, status=StageStatus.PENDING
            )

    def set_inputs(self, inputs: WorkflowInputs):
        """
        Set workflow inputs and calculate checksum.

        Args:
            inputs: Workflow input parameters
        """
        self.inputs = inputs
        self.inputs_checksum = inputs.calculate_checksum()
        self._update_timestamp()
        logger.info(f"Set workflow inputs with checksum: {self.inputs_checksum[:8]}...")

    def has_inputs_changed(self, new_inputs: WorkflowInputs) -> bool:
        """
        Check if inputs have changed since last run.

        Args:
            new_inputs: New input parameters to compare

        Returns:
            True if inputs have changed, False otherwise
        """
        if not self.inputs_checksum:
            return True

        new_checksum = new_inputs.calculate_checksum()
        changed = new_checksum != self.inputs_checksum

        if changed:
            logger.info(
                f"Inputs changed: {self.inputs_checksum[:8]} -> {new_checksum[:8]}"
            )
        else:
            logger.info("Inputs unchanged")

        return changed

    def get_stage(self, stage_name: str) -> Optional[StageState]:
        """Get stage state by name."""
        return self.stages.get(stage_name)

    def start_stage(self, stage_name: str):
        """Mark a stage as started."""
        if stage_name not in self.stages:
            self.stages[stage_name] = StageState(
                name=stage_name, status=StageStatus.PENDING
            )

        stage = self.stages[stage_name]
        stage.status = StageStatus.RUNNING
        stage.started_at = datetime.now(UTC)
        self.current_stage = stage_name
        self._update_timestamp()

        logger.info(f"Started stage: {stage_name}")

    def complete_stage(
        self,
        stage_name: str,
        output_files: list[str] = None,
        metrics: dict[str, Any] = None,
    ):
        """Mark a stage as completed."""
        if stage_name not in self.stages:
            logger.error(f"Cannot complete unknown stage: {stage_name}")
            return

        stage = self.stages[stage_name]
        stage.status = StageStatus.COMPLETED
        stage.completed_at = datetime.now(UTC)

        if output_files:
            stage.output_files.extend(output_files)
        if metrics:
            stage.metrics.update(metrics)

        self._update_timestamp()
        logger.info(f"Completed stage: {stage_name}")

    def fail_stage(self, stage_name: str, error_message: str):
        """Mark a stage as failed."""
        if stage_name not in self.stages:
            logger.error(f"Cannot fail unknown stage: {stage_name}")
            return

        stage = self.stages[stage_name]
        stage.status = StageStatus.FAILED
        stage.error_message = error_message
        stage.completed_at = datetime.now(UTC)

        self._update_timestamp()
        logger.error(f"Failed stage {stage_name}: {error_message}")

    def get_next_stage(self) -> Optional[str]:
        """Get the next stage to execute."""
        for stage_name in self.DEFAULT_STAGES:
            stage = self.stages.get(stage_name)
            if stage and stage.status in [StageStatus.PENDING, StageStatus.FAILED]:
                return stage_name
        return None

    def get_completed_stages(self) -> list[str]:
        """Get list of completed stage names."""
        return [
            name
            for name, stage in self.stages.items()
            if stage.status == StageStatus.COMPLETED
        ]

    def is_workflow_complete(self) -> bool:
        """Check if all stages are completed."""
        return all(
            stage.status == StageStatus.COMPLETED for stage in self.stages.values()
        )

    def can_resume(self) -> bool:
        """Check if workflow can be resumed (has some incomplete stages)."""
        return not self.is_workflow_complete() and bool(self.stages)

    def _update_timestamp(self):
        """Update the last modified timestamp."""
        self.updated_at = datetime.now(UTC)

    def save(self):
        """Save state to JSON file."""
        try:
            # Prepare data for serialization
            data = {
                "workflow_id": self.workflow_id,
                "created_at": self.created_at.isoformat(),
                "updated_at": self.updated_at.isoformat(),
                "inputs": self.inputs.to_dict() if self.inputs else None,
                "inputs_checksum": self.inputs_checksum,
                "current_stage": self.current_stage,
                "stages": {
                    name: stage.to_dict() for name, stage in self.stages.items()
                },
                "metadata": self.metadata,
            }

            # Ensure directory exists
            self.state_file.parent.mkdir(parents=True, exist_ok=True)

            # Write to file atomically (write to temp file, then rename)
            temp_file = self.state_file.with_suffix(".tmp")
            with open(temp_file, "w") as f:
                json.dump(data, f, indent=2, sort_keys=True)

            # Atomic rename
            temp_file.replace(self.state_file)

            logger.info(f"Saved workflow state to {self.state_file}")

        except Exception as e:
            logger.error(f"Failed to save workflow state: {e}")
            raise

    @classmethod
    def load(
        cls, workflow_id: str, state_file: Optional[Path] = None
    ) -> Optional["WorkflowState"]:
        """
        Load workflow state from JSON file.

        Args:
            workflow_id: Workflow identifier
            state_file: Optional custom state file path

        Returns:
            WorkflowState instance if file exists, None otherwise
        """
        instance = cls(workflow_id, state_file)

        if not instance.state_file.exists():
            logger.info(f"No existing state file found: {instance.state_file}")
            return None

        try:
            with open(instance.state_file) as f:
                data = json.load(f)

            # Restore basic fields
            instance.created_at = datetime.fromisoformat(data["created_at"])
            instance.updated_at = datetime.fromisoformat(data["updated_at"])
            instance.inputs_checksum = data.get("inputs_checksum")
            instance.current_stage = data.get("current_stage")
            instance.metadata = data.get("metadata", {})

            # Restore inputs
            if data.get("inputs"):
                instance.inputs = WorkflowInputs.from_dict(data["inputs"])

            # Restore stages
            instance.stages = {}
            for name, stage_data in data.get("stages", {}).items():
                instance.stages[name] = StageState.from_dict(stage_data)

            logger.info(f"Loaded workflow state from {instance.state_file}")
            return instance

        except Exception as e:
            logger.error(f"Failed to load workflow state: {e}")
            return None

    def rollback_to_stage(self, stage_name: str):
        """
        Rollback workflow to a specific stage.

        This marks all stages after the specified stage as PENDING,
        allowing them to be re-executed.

        Args:
            stage_name: Name of stage to rollback to
        """
        if stage_name not in self.stages:
            logger.error(f"Cannot rollback to unknown stage: {stage_name}")
            return

        # Find the index of the rollback stage
        try:
            rollback_index = self.DEFAULT_STAGES.index(stage_name)
        except ValueError:
            logger.error(f"Stage {stage_name} not in default stages list")
            return

        # Reset all stages after the rollback point
        stages_reset = []
        for i in range(rollback_index + 1, len(self.DEFAULT_STAGES)):
            stage_name_to_reset = self.DEFAULT_STAGES[i]
            if stage_name_to_reset in self.stages:
                stage = self.stages[stage_name_to_reset]
                stage.status = StageStatus.PENDING
                stage.started_at = None
                stage.completed_at = None
                stage.error_message = None
                stage.output_files = []
                stage.metrics = {}
                stages_reset.append(stage_name_to_reset)

        self._update_timestamp()
        logger.info(f"Rolled back to stage {stage_name}, reset stages: {stages_reset}")

    def get_summary(self) -> dict[str, Any]:
        """Get a summary of the current workflow state."""
        completed_count = len(
            [s for s in self.stages.values() if s.status == StageStatus.COMPLETED]
        )
        failed_count = len(
            [s for s in self.stages.values() if s.status == StageStatus.FAILED]
        )

        return {
            "workflow_id": self.workflow_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "current_stage": self.current_stage,
            "total_stages": len(self.stages),
            "completed_stages": completed_count,
            "failed_stages": failed_count,
            "progress_percent": (completed_count / len(self.stages)) * 100
            if self.stages
            else 0,
            "is_complete": self.is_workflow_complete(),
            "can_resume": self.can_resume(),
            "inputs_checksum": self.inputs_checksum[:8]
            if self.inputs_checksum
            else None,
        }


def generate_workflow_id() -> str:
    """Generate a unique workflow ID based on timestamp with microseconds."""
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S_%f")
    return f"workflow_{timestamp}"
