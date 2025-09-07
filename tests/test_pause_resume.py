#!/usr/bin/env python3
"""
Tests for Pause/Resume Functionality in Enhanced Multi-Agent Workflow System
"""

import tempfile
import time
from pathlib import Path

from multi_agent_workflow.pause_resume import (
    PausePoint,
    PausePolicy,
    PauseReason,
    PauseRequest,
    WorkflowPauseManager,
    WorkflowSuspension,
)
from multi_agent_workflow.workflow_state import (
    StageStatus,
    WorkflowInputs,
    WorkflowState,
)


class TestPauseRequest:
    """Test PauseRequest dataclass."""

    def test_pause_request_creation(self):
        """Test creating a pause request."""
        request = PauseRequest(
            reason=PauseReason.MANUAL,
            stage_name="test_stage",
            message="Test pause",
            requested_by="user",
            policy=PausePolicy.AFTER_CURRENT_STAGE,
        )

        assert request.reason == PauseReason.MANUAL
        assert request.stage_name == "test_stage"
        assert request.message == "Test pause"
        assert request.requested_by == "user"
        assert request.policy == PausePolicy.AFTER_CURRENT_STAGE
        assert request.requested_at is not None

    def test_pause_request_serialization(self):
        """Test serializing pause request to dict."""
        request = PauseRequest(
            reason=PauseReason.SCHEDULED,
            stage_name="architecture_design",
            message="Scheduled pause for review",
        )

        data = request.to_dict()
        assert data["reason"] == "scheduled"
        assert data["stage_name"] == "architecture_design"
        assert data["message"] == "Scheduled pause for review"
        assert "requested_at" in data


class TestWorkflowSuspension:
    """Test WorkflowSuspension dataclass."""

    def test_suspension_creation(self):
        """Test creating a workflow suspension."""
        suspension = WorkflowSuspension(
            reason=PauseReason.MANUAL,
            stage_name="testing",
            message="Test suspension",
            requested_by="admin",
        )

        assert suspension.reason == PauseReason.MANUAL
        assert suspension.stage_name == "testing"
        assert suspension.message == "Test suspension"
        assert suspension.requested_by == "admin"
        assert suspension.suspended_at is not None

    def test_suspension_serialization(self):
        """Test serializing suspension to dict."""
        suspension = WorkflowSuspension(
            reason=PauseReason.SCHEDULED,
            stage_name="deployment",
            message="Scheduled suspension",
        )

        data = suspension.to_dict()
        assert data["reason"] == "scheduled"
        assert data["stage_name"] == "deployment"
        assert data["message"] == "Scheduled suspension"
        assert "suspended_at" in data


class TestPausePoint:
    """Test PausePoint configuration."""

    def test_pause_point_creation(self):
        """Test creating a pause point."""
        point = PausePoint(
            stage_name="code_implementation",
            position="before",
            condition=lambda state: state.get_summary()["completed_stages"] > 2,
            message="Review required before code implementation",
            timeout=3600,
            auto_resume=False,
        )

        assert point.stage_name == "code_implementation"
        assert point.position == "before"
        assert point.message == "Review required before code implementation"
        assert point.timeout == 3600
        assert point.auto_resume is False

    def test_pause_point_should_pause(self):
        """Test pause point condition evaluation."""
        # Create state with 3 completed stages
        state = WorkflowState("test_workflow")
        state.inputs = WorkflowInputs(
            project_description="Test project",
            target_directory="/tmp/test",
        )

        # Complete some stages
        for stage in [
            "requirements_analysis",
            "architecture_design",
            "implementation_planning",
        ]:
            state.start_stage(stage)
            state.complete_stage(stage)

        # Create pause point that triggers after 2 completed stages
        point = PausePoint(
            stage_name="code_implementation",
            position="before",
            condition=lambda s: s.get_summary()["completed_stages"] > 2,
        )

        # Should trigger pause
        assert point.should_pause(state) is True

        # Create pause point that won't trigger
        point2 = PausePoint(
            stage_name="testing",
            position="after",
            condition=lambda s: s.get_summary()["failed_stages"] > 0,
        )

        # Should not trigger pause (no failed stages)
        assert point2.should_pause(state) is False


class TestWorkflowPauseManager:
    """Test WorkflowPauseManager functionality."""

    def test_pause_manager_initialization(self):
        """Test initializing pause manager."""
        state = WorkflowState("test_workflow")
        manager = WorkflowPauseManager(state)

        assert manager.state == state
        assert manager.current_suspension is None
        assert not manager.is_paused
        assert len(manager.pause_points) == 0

    def test_request_pause(self):
        """Test requesting a workflow pause."""
        state = WorkflowState("test_workflow")
        manager = WorkflowPauseManager(state)

        # Request pause
        success = manager.request_pause(
            reason=PauseReason.USER_INPUT,
            stage_name="testing",
            message="Need user confirmation",
            policy=PausePolicy.IMMEDIATE,
        )

        assert success is True
        assert manager.current_suspension is not None
        assert manager.current_suspension.reason == PauseReason.USER_INPUT
        assert manager.current_suspension.stage_name == "testing"

    def test_execute_pause(self):
        """Test executing a pause."""
        state = WorkflowState("test_workflow")
        state.inputs = WorkflowInputs(
            project_description="Test project",
            target_directory="/tmp/test",
        )
        manager = WorkflowPauseManager(state)

        # Start a stage
        state.start_stage("requirements_analysis")

        # Request and execute pause
        manager.request_pause(
            reason=PauseReason.MANUAL,
            stage_name="requirements_analysis",
            message="Manual pause",
            policy=PausePolicy.IMMEDIATE,
        )

        manager.execute_pause()

        assert manager.is_paused is True
        assert state.stages["requirements_analysis"].status == StageStatus.PAUSED

    def test_resume_workflow(self):
        """Test resuming a paused workflow."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "test_state.json"

            # Create and pause workflow
            state = WorkflowState("test_workflow")
            state.inputs = WorkflowInputs(
                project_description="Test project",
                target_directory="/tmp/test",
            )
            state.state_file = state_file

            manager = WorkflowPauseManager(state)

            # Start and pause a stage
            state.start_stage("architecture_design")
            manager.request_pause(
                reason=PauseReason.ERROR_RECOVERY,
                stage_name="architecture_design",
                policy=PausePolicy.IMMEDIATE,
            )
            manager.execute_pause()

            assert manager.is_paused is True

            # Resume workflow
            success = manager.resume_workflow(
                resumed_by="admin",
                message="Error resolved, continuing",
                skip_current_stage=False,
            )

            assert success is True
            assert manager.is_paused is False
            assert manager.current_suspension is None
            assert state.stages["architecture_design"].status == StageStatus.RUNNING

    def test_pause_points_configuration(self):
        """Test configuring pause points."""
        state = WorkflowState("test_workflow")
        manager = WorkflowPauseManager(state)

        # Configure pause points
        points = [
            PausePoint(
                stage_name="implementation",
                position="before",
                condition=lambda s: True,  # Always pause
                message="Review design before implementation",
            ),
            PausePoint(
                stage_name="deployment",
                position="after",
                condition=lambda s: s.get_summary()["failed_stages"] > 0,
                message="Review failures before deployment",
            ),
        ]

        manager.configure_pause_points(points)
        assert len(manager.pause_points) == 2

    def test_check_pause_points(self):
        """Test checking pause points for automatic pausing."""
        state = WorkflowState("test_workflow")
        state.inputs = WorkflowInputs(
            project_description="Test project",
            target_directory="/tmp/test",
        )
        manager = WorkflowPauseManager(state)

        # Configure a pause point that will trigger
        manager.configure_pause_points(
            [
                PausePoint(
                    stage_name="testing",
                    position="before",
                    condition=lambda s: True,  # Always trigger
                    message="Pause before testing",
                )
            ]
        )

        # Check pause points
        should_pause = manager.check_pause_points("testing", "before")
        assert should_pause is True
        assert manager.current_suspension is not None
        assert manager.current_suspension.reason == PauseReason.SCHEDULED

    def test_auto_resume_timeout(self):
        """Test auto-resume after timeout."""
        state = WorkflowState("test_workflow")
        state.inputs = WorkflowInputs(
            project_description="Test project",
            target_directory="/tmp/test",
        )
        manager = WorkflowPauseManager(state)

        # Configure pause point with short timeout
        manager.configure_pause_points(
            [
                PausePoint(
                    stage_name="validation",
                    position="after",
                    condition=lambda s: True,
                    message="Brief pause",
                    timeout=0.1,  # 100ms timeout
                    auto_resume=True,
                )
            ]
        )

        # Start monitoring (would normally run in thread)
        state.start_stage("validation")
        manager.check_pause_points("validation", "after")
        manager.execute_pause()

        assert manager.is_paused is True

        # Simulate timeout check
        time.sleep(0.2)  # Wait longer than timeout
        manager._check_auto_resume()

        assert manager.is_paused is False
        assert manager.current_suspension is None
        # Check that pause was automatically cleared
        assert manager.current_suspension is None

    def test_pause_history_tracking(self):
        """Test tracking pause/resume history."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "test_state.json"

            state = WorkflowState("test_workflow")
            state.inputs = WorkflowInputs(
                project_description="Test project",
                target_directory="/tmp/test",
            )
            state.state_file = state_file

            manager = WorkflowPauseManager(state)

            # Create multiple pause/resume cycles
            for i in range(3):
                state.start_stage(f"stage_{i}")

                manager.request_pause(
                    reason=PauseReason.MANUAL,
                    stage_name=f"stage_{i}",
                    message=f"Pause {i}",
                )
                manager.execute_pause()

                manager.resume_workflow(
                    resumed_by="user",
                    message=f"Resume {i}",
                )

            # Check history
            history = manager.get_pause_history()
            assert len(history) == 3

            for i, entry in enumerate(history):
                assert entry["pause_request"]["stage_name"] == f"stage_{i}"
                assert entry["resume_request"]["message"] == f"Resume {i}"

    def test_pause_with_modified_inputs(self):
        """Test resuming with modified workflow inputs."""
        state = WorkflowState("test_workflow")
        state.inputs = WorkflowInputs(
            project_description="Original project",
            target_directory="/tmp/test",
            additional_context="Original context",
        )
        manager = WorkflowPauseManager(state)

        # Pause workflow
        state.start_stage("implementation")
        manager.request_pause(
            reason=PauseReason.USER_INPUT,
            stage_name="implementation",
        )
        manager.execute_pause()

        # Resume with modified inputs
        modified_inputs = {
            "additional_context": "Updated context with new requirements",
            "new_parameter": "Additional configuration",
        }

        manager.resume_workflow(
            resumed_by="user",
            message="Resuming with updated requirements",
            modified_inputs=modified_inputs,
        )

        # Check inputs were updated
        assert (
            state.inputs.additional_context == "Updated context with new requirements"
        )
        assert hasattr(state.inputs, "new_parameter")
        assert state.inputs.new_parameter == "Additional configuration"

    def test_pause_policy_after_current_stage(self):
        """Test AFTER_CURRENT_STAGE pause policy."""
        state = WorkflowState("test_workflow")
        state.inputs = WorkflowInputs(
            project_description="Test project",
            target_directory="/tmp/test",
        )
        manager = WorkflowPauseManager(state)

        # Start a stage
        state.start_stage("code_generation")

        # Request pause with AFTER_CURRENT_STAGE policy
        manager.request_pause(
            reason=PauseReason.SCHEDULED,
            stage_name="code_generation",
            policy=PausePolicy.AFTER_CURRENT_STAGE,
        )

        # Should not pause immediately
        assert manager.is_paused is False
        assert state.stages["code_generation"].status == StageStatus.RUNNING

        # Complete the stage
        state.complete_stage("code_generation")

        # Now check if should pause
        should_pause = manager.should_pause_after_stage("code_generation")
        assert should_pause is True

        # Execute the pause
        manager.execute_pause()
        assert manager.is_paused is True
