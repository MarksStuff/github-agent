#!/usr/bin/env python3
"""
Pause/Resume Functionality for Enhanced Multi-Agent Workflow System

This module provides workflow suspension and resumption capabilities,
configurable pause points, and manual pause/continue controls.
"""

import json
import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional

try:
    from .output_manager import workflow_logger
    from .workflow_state import StageStatus, WorkflowState
except ImportError:
    # Fallback for when modules are not available
    from workflow_state import StageStatus, WorkflowState

logger = logging.getLogger(__name__)


class PauseReason(Enum):
    """Reasons for workflow pause."""

    MANUAL = "manual"
    SCHEDULED = "scheduled"
    ERROR_RECOVERY = "error_recovery"
    RESOURCE_WAIT = "resource_wait"
    USER_INPUT = "user_input"
    MAINTENANCE = "maintenance"
    EXTERNAL_DEPENDENCY = "external_dependency"


class PausePolicy(Enum):
    """Policies for handling pause requests."""

    IMMEDIATE = "immediate"  # Pause immediately
    AFTER_CURRENT_STAGE = "after_current_stage"  # Wait for current stage to complete
    AT_NEXT_CHECKPOINT = "at_next_checkpoint"  # Wait for next designated pause point
    NEVER = "never"  # Ignore pause requests


@dataclass
class PausePoint:
    """Configuration for a pause point in the workflow."""

    stage_name: str
    condition: Optional[Callable[[WorkflowState], bool]] = None
    description: str = ""
    auto_resume_after: Optional[float] = None  # Seconds to wait before auto-resume
    require_confirmation: bool = True
    metadata: dict[str, Any] = None

    def __post_init__(self):
        """Initialize default values."""
        if self.metadata is None:
            self.metadata = {}

    def should_pause(self, workflow_state: WorkflowState) -> bool:
        """Check if workflow should pause at this point."""
        if self.condition is None:
            return True
        return self.condition(workflow_state)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "stage_name": self.stage_name,
            "description": self.description,
            "auto_resume_after": self.auto_resume_after,
            "require_confirmation": self.require_confirmation,
            "metadata": self.metadata,
        }


@dataclass
class PauseRequest:
    """Request to pause workflow execution."""

    request_id: str
    timestamp: datetime
    reason: PauseReason
    requested_by: str
    stage_name: Optional[str] = None
    message: str = ""
    policy: PausePolicy = PausePolicy.AFTER_CURRENT_STAGE
    auto_resume_after: Optional[float] = None
    metadata: dict[str, Any] = None

    def __post_init__(self):
        """Initialize default values."""
        if self.metadata is None:
            self.metadata = {}

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "request_id": self.request_id,
            "timestamp": self.timestamp.isoformat(),
            "reason": self.reason.value,
            "requested_by": self.requested_by,
            "stage_name": self.stage_name,
            "message": self.message,
            "policy": self.policy.value,
            "auto_resume_after": self.auto_resume_after,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PauseRequest":
        """Create from dictionary."""
        return cls(
            request_id=data["request_id"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            reason=PauseReason(data["reason"]),
            requested_by=data["requested_by"],
            stage_name=data.get("stage_name"),
            message=data.get("message", ""),
            policy=PausePolicy(
                data.get("policy", PausePolicy.AFTER_CURRENT_STAGE.value)
            ),
            auto_resume_after=data.get("auto_resume_after"),
            metadata=data.get("metadata", {}),
        )


@dataclass
class WorkflowSuspension:
    """Information about a suspended workflow."""

    workflow_id: str
    suspension_id: str
    suspended_at: datetime
    suspended_stage: str
    pause_reason: PauseReason
    pause_message: str
    suspension_data: dict[str, Any]
    auto_resume_at: Optional[datetime] = None
    can_resume: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "workflow_id": self.workflow_id,
            "suspension_id": self.suspension_id,
            "suspended_at": self.suspended_at.isoformat(),
            "suspended_stage": self.suspended_stage,
            "pause_reason": self.pause_reason.value,
            "pause_message": self.pause_message,
            "suspension_data": self.suspension_data,
            "auto_resume_at": self.auto_resume_at.isoformat()
            if self.auto_resume_at
            else None,
            "can_resume": self.can_resume,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorkflowSuspension":
        """Create from dictionary."""
        return cls(
            workflow_id=data["workflow_id"],
            suspension_id=data["suspension_id"],
            suspended_at=datetime.fromisoformat(data["suspended_at"]),
            suspended_stage=data["suspended_stage"],
            pause_reason=PauseReason(data["pause_reason"]),
            pause_message=data["pause_message"],
            suspension_data=data["suspension_data"],
            auto_resume_at=datetime.fromisoformat(data["auto_resume_at"])
            if data.get("auto_resume_at")
            else None,
            can_resume=data.get("can_resume", True),
        )


class WorkflowPauseManager:
    """Manages workflow pause, resume, and suspension functionality."""

    def __init__(self, state_dir: Optional[Path] = None):
        """
        Initialize pause manager.

        Args:
            state_dir: Directory for storing pause/suspension data
        """
        if state_dir:
            self.state_dir = state_dir
        else:
            self.state_dir = Path(__file__).parent / "state" / "pause"

        self.state_dir.mkdir(parents=True, exist_ok=True)

        # Configuration
        self.pause_points: dict[str, PausePoint] = {}
        self.active_suspensions: dict[str, WorkflowSuspension] = {}
        self.pending_requests: dict[str, PauseRequest] = {}

        # Runtime state
        self._pause_event = threading.Event()
        self._resume_event = threading.Event()
        self._resume_event.set()  # Start in resumed state

        # Load existing suspensions
        self._load_suspensions()

        logger.info("Initialized WorkflowPauseManager")

    def configure_pause_point(
        self,
        stage_name: str,
        condition: Optional[Callable[[WorkflowState], bool]] = None,
        description: str = "",
        auto_resume_after: Optional[float] = None,
        require_confirmation: bool = True,
        metadata: Optional[dict[str, Any]] = None,
    ):
        """
        Configure a pause point for a specific stage.

        Args:
            stage_name: Name of the stage
            condition: Optional condition function to check if pause should occur
            description: Human-readable description of the pause point
            auto_resume_after: Seconds to wait before auto-resume (None = manual resume required)
            require_confirmation: Whether user confirmation is required to resume
            metadata: Additional metadata for the pause point
        """
        pause_point = PausePoint(
            stage_name=stage_name,
            condition=condition,
            description=description,
            auto_resume_after=auto_resume_after,
            require_confirmation=require_confirmation,
            metadata=metadata or {},
        )

        self.pause_points[stage_name] = pause_point
        logger.info(f"Configured pause point for stage: {stage_name}")

    def request_pause(
        self,
        reason: PauseReason,
        requested_by: str,
        message: str = "",
        stage_name: Optional[str] = None,
        policy: PausePolicy = PausePolicy.AFTER_CURRENT_STAGE,
        auto_resume_after: Optional[float] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> str:
        """
        Request a workflow pause.

        Args:
            reason: Reason for the pause
            requested_by: Identifier of who requested the pause
            message: Optional message explaining the pause
            stage_name: Specific stage to pause at (None = current stage)
            policy: Policy for when to apply the pause
            auto_resume_after: Seconds to wait before auto-resume
            metadata: Additional metadata

        Returns:
            Request ID
        """
        request_id = f"pause_{int(time.time() * 1000)}"

        request = PauseRequest(
            request_id=request_id,
            timestamp=datetime.now(UTC),
            reason=reason,
            requested_by=requested_by,
            stage_name=stage_name,
            message=message,
            policy=policy,
            auto_resume_after=auto_resume_after,
            metadata=metadata or {},
        )

        self.pending_requests[request_id] = request

        # Apply pause based on policy
        if policy == PausePolicy.IMMEDIATE:
            self._apply_pause_immediately(request)
        elif policy == PausePolicy.NEVER:
            logger.info(f"Pause request {request_id} ignored due to NEVER policy")
            del self.pending_requests[request_id]
            return request_id

        logger.info(f"Pause requested: {request_id} by {requested_by} - {message}")
        return request_id

    def check_pause_point(self, stage_name: str, workflow_state: WorkflowState) -> bool:
        """
        Check if workflow should pause at this stage.

        Args:
            stage_name: Name of the current stage
            workflow_state: Current workflow state

        Returns:
            True if workflow should pause, False otherwise
        """
        # Check configured pause points
        if stage_name in self.pause_points:
            pause_point = self.pause_points[stage_name]
            if pause_point.should_pause(workflow_state):
                self._suspend_workflow_at_pause_point(
                    stage_name, workflow_state, pause_point
                )
                return True

        # Check pending pause requests
        for request_id, request in list(self.pending_requests.items()):
            if self._should_apply_pause_request(request, stage_name):
                self._apply_pause_request(request, stage_name, workflow_state)
                del self.pending_requests[request_id]
                return True

        return False

    def suspend_workflow(
        self,
        workflow_state: WorkflowState,
        reason: PauseReason,
        message: str = "",
        auto_resume_after: Optional[float] = None,
        suspension_data: Optional[dict[str, Any]] = None,
    ) -> str:
        """
        Suspend a workflow with detailed information.

        Args:
            workflow_state: Workflow state to suspend
            reason: Reason for suspension
            message: Descriptive message
            auto_resume_after: Seconds until auto-resume (None = manual resume required)
            suspension_data: Additional data about the suspension

        Returns:
            Suspension ID
        """
        suspension_id = f"suspend_{workflow_state.workflow_id}_{int(time.time())}"

        # Calculate auto-resume time
        auto_resume_at = None
        if auto_resume_after:
            auto_resume_at = datetime.now(UTC).replace(
                microsecond=0
            ) + datetime.timedelta(seconds=auto_resume_after)

        suspension = WorkflowSuspension(
            workflow_id=workflow_state.workflow_id,
            suspension_id=suspension_id,
            suspended_at=datetime.now(UTC),
            suspended_stage=workflow_state.current_stage or "unknown",
            pause_reason=reason,
            pause_message=message,
            suspension_data=suspension_data or {},
            auto_resume_at=auto_resume_at,
        )

        # Store suspension
        self.active_suspensions[workflow_state.workflow_id] = suspension
        self._save_suspension(suspension)

        # Update workflow state
        if (
            workflow_state.current_stage
            and workflow_state.current_stage in workflow_state.stages
        ):
            stage = workflow_state.stages[workflow_state.current_stage]
            stage.status = StageStatus.PAUSED
            stage.error_message = f"Suspended: {message}"
            workflow_state.save()

        # Set pause event
        self._pause_event.set()
        self._resume_event.clear()

        logger.info(
            f"Workflow {workflow_state.workflow_id} suspended: {suspension_id} - {message}"
        )

        return suspension_id

    def resume_workflow(self, workflow_id: str, resumed_by: str = "system") -> bool:
        """
        Resume a suspended workflow.

        Args:
            workflow_id: ID of the workflow to resume
            resumed_by: Identifier of who resumed the workflow

        Returns:
            True if resume was successful, False otherwise
        """
        if workflow_id not in self.active_suspensions:
            logger.warning(f"No active suspension found for workflow: {workflow_id}")
            return False

        suspension = self.active_suspensions[workflow_id]

        # Check if resumption is allowed
        if not suspension.can_resume:
            logger.warning(f"Workflow {workflow_id} cannot be resumed")
            return False

        # Load workflow state and update it
        try:
            workflow_state = WorkflowState.load(workflow_id)
            if workflow_state and workflow_state.current_stage:
                if workflow_state.current_stage in workflow_state.stages:
                    stage = workflow_state.stages[workflow_state.current_stage]
                    if stage.status == StageStatus.PAUSED:
                        stage.status = StageStatus.PENDING
                        stage.error_message = None
                        workflow_state.save()

            # Clear suspension
            del self.active_suspensions[workflow_id]
            self._remove_suspension_file(suspension.suspension_id)

            # Clear pause state
            self._pause_event.clear()
            self._resume_event.set()

            logger.info(f"Workflow {workflow_id} resumed by {resumed_by}")
            return True

        except Exception as e:
            logger.error(f"Failed to resume workflow {workflow_id}: {e}")
            return False

    def is_workflow_suspended(self, workflow_id: str) -> bool:
        """Check if a workflow is currently suspended."""
        return workflow_id in self.active_suspensions

    def get_suspension_info(self, workflow_id: str) -> Optional[WorkflowSuspension]:
        """Get suspension information for a workflow."""
        return self.active_suspensions.get(workflow_id)

    def list_suspended_workflows(self) -> list[WorkflowSuspension]:
        """List all currently suspended workflows."""
        return list(self.active_suspensions.values())

    def wait_if_paused(self, timeout: Optional[float] = None) -> bool:
        """
        Wait if workflow is currently paused.

        Args:
            timeout: Maximum time to wait (None = wait indefinitely)

        Returns:
            True if workflow can continue, False if timeout occurred
        """
        if self._pause_event.is_set():
            logger.info("Workflow is paused, waiting for resume...")
            return self._resume_event.wait(timeout)
        return True

    def check_auto_resume(self):
        """Check for workflows that should be auto-resumed."""
        current_time = datetime.now(UTC)

        for workflow_id, suspension in list(self.active_suspensions.items()):
            if (
                suspension.auto_resume_at
                and current_time >= suspension.auto_resume_at
                and suspension.can_resume
            ):
                logger.info(f"Auto-resuming workflow {workflow_id}")
                self.resume_workflow(workflow_id, "auto-resume")

    def cancel_pause_request(self, request_id: str) -> bool:
        """
        Cancel a pending pause request.

        Args:
            request_id: ID of the request to cancel

        Returns:
            True if request was cancelled, False if not found
        """
        if request_id in self.pending_requests:
            del self.pending_requests[request_id]
            logger.info(f"Cancelled pause request: {request_id}")
            return True
        return False

    def get_pending_requests(self) -> list[PauseRequest]:
        """Get all pending pause requests."""
        return list(self.pending_requests.values())

    # Private methods
    def _apply_pause_immediately(self, request: PauseRequest):
        """Apply a pause request immediately."""
        self._pause_event.set()
        self._resume_event.clear()
        logger.info(f"Applied immediate pause: {request.request_id}")

    def _should_apply_pause_request(
        self, request: PauseRequest, current_stage: str
    ) -> bool:
        """Check if a pause request should be applied at the current stage."""
        if request.policy == PausePolicy.IMMEDIATE:
            return True
        elif request.policy == PausePolicy.AFTER_CURRENT_STAGE:
            return True  # Will be applied after current stage completes
        elif request.policy == PausePolicy.AT_NEXT_CHECKPOINT:
            return current_stage in self.pause_points
        elif request.policy == PausePolicy.NEVER:
            return False

        return False

    def _apply_pause_request(
        self, request: PauseRequest, stage_name: str, workflow_state: WorkflowState
    ):
        """Apply a pause request at a specific stage."""
        self.suspend_workflow(
            workflow_state=workflow_state,
            reason=request.reason,
            message=request.message,
            auto_resume_after=request.auto_resume_after,
            suspension_data={
                "request_id": request.request_id,
                "requested_by": request.requested_by,
                "policy": request.policy.value,
                "metadata": request.metadata,
            },
        )

    def _suspend_workflow_at_pause_point(
        self, stage_name: str, workflow_state: WorkflowState, pause_point: PausePoint
    ):
        """Suspend workflow at a configured pause point."""
        message = (
            pause_point.description or f"Paused at configured pause point: {stage_name}"
        )

        self.suspend_workflow(
            workflow_state=workflow_state,
            reason=PauseReason.SCHEDULED,
            message=message,
            auto_resume_after=pause_point.auto_resume_after,
            suspension_data={
                "pause_point": True,
                "require_confirmation": pause_point.require_confirmation,
                "metadata": pause_point.metadata,
            },
        )

    def _save_suspension(self, suspension: WorkflowSuspension):
        """Save suspension information to file."""
        suspension_file = self.state_dir / f"{suspension.suspension_id}.json"
        try:
            with open(suspension_file, "w") as f:
                json.dump(suspension.to_dict(), f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to save suspension {suspension.suspension_id}: {e}")

    def _load_suspensions(self):
        """Load existing suspension information from files."""
        for suspension_file in self.state_dir.glob("suspend_*.json"):
            try:
                with open(suspension_file) as f:
                    data = json.load(f)

                suspension = WorkflowSuspension.from_dict(data)
                self.active_suspensions[suspension.workflow_id] = suspension

                logger.info(f"Loaded suspension: {suspension.suspension_id}")

            except Exception as e:
                logger.warning(f"Failed to load suspension from {suspension_file}: {e}")

    def _remove_suspension_file(self, suspension_id: str):
        """Remove suspension file."""
        suspension_file = self.state_dir / f"{suspension_id}.json"
        try:
            if suspension_file.exists():
                suspension_file.unlink()
        except Exception as e:
            logger.warning(f"Failed to remove suspension file {suspension_file}: {e}")


# Decorator for adding pause point checking
def with_pause_support(
    stage_name: str,
    pause_manager: Optional[WorkflowPauseManager] = None,
    auto_resume_after: Optional[float] = None,
):
    """
    Decorator for adding pause point support to stage execution functions.

    Args:
        stage_name: Name of the stage
        pause_manager: Pause manager instance
        auto_resume_after: Auto-resume timeout for this stage
    """
    if pause_manager is None:
        pause_manager = WorkflowPauseManager()

    def decorator(func: Callable):
        def wrapper(workflow_state: WorkflowState, *args, **kwargs):
            # Check for pause before stage execution
            if pause_manager.check_pause_point(stage_name, workflow_state):
                logger.info(f"Stage {stage_name} paused")

                # Wait for resume
                if not pause_manager.wait_if_paused():
                    raise RuntimeError(
                        f"Timeout waiting for resume in stage {stage_name}"
                    )

            # Execute the stage
            result = func(workflow_state, *args, **kwargs)

            # Check for pause after stage execution
            if pause_manager.check_pause_point(f"{stage_name}_post", workflow_state):
                logger.info(f"Stage {stage_name} paused after execution")

                # Wait for resume
                if not pause_manager.wait_if_paused():
                    raise RuntimeError(
                        f"Timeout waiting for resume after stage {stage_name}"
                    )

            return result

        return wrapper

    return decorator


# Global pause manager instance
pause_manager = WorkflowPauseManager()
