#!/usr/bin/env python3
"""Tests for workflow state management."""

import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from multi_agent_workflow.workflow_state import (
    StageState,
    StageStatus,
    WorkflowInputs,
    WorkflowState,
    generate_workflow_id,
)


class TestWorkflowInputs(unittest.TestCase):
    """Test WorkflowInputs functionality."""

    def test_checksum_consistency(self):
        """Test that checksum is consistent for same inputs."""
        inputs1 = WorkflowInputs(
            project_description="Build a todo app",
            config_overrides={"theme": "dark", "db": "sqlite"},
            template_name="web_app",
        )

        inputs2 = WorkflowInputs(
            project_description="Build a todo app",
            config_overrides={"db": "sqlite", "theme": "dark"},  # Different order
            template_name="web_app",
        )

        # Should produce same checksum despite different dict order
        self.assertEqual(inputs1.calculate_checksum(), inputs2.calculate_checksum())

    def test_checksum_changes(self):
        """Test that checksum changes when inputs change."""
        inputs1 = WorkflowInputs(project_description="Build a todo app")
        inputs2 = WorkflowInputs(project_description="Build a chat app")

        self.assertNotEqual(inputs1.calculate_checksum(), inputs2.calculate_checksum())

    def test_serialization(self):
        """Test inputs serialization/deserialization."""
        original = WorkflowInputs(
            project_description="Test project",
            config_overrides={"key": "value"},
            template_name="test",
        )

        # Serialize to dict
        data = original.to_dict()

        # Deserialize back
        restored = WorkflowInputs.from_dict(data)

        # Should be equal
        self.assertEqual(original.project_description, restored.project_description)
        self.assertEqual(original.config_overrides, restored.config_overrides)
        self.assertEqual(original.template_name, restored.template_name)
        self.assertEqual(original.calculate_checksum(), restored.calculate_checksum())


class TestStageState(unittest.TestCase):
    """Test StageState functionality."""

    def test_creation(self):
        """Test stage creation."""
        stage = StageState("test_stage", StageStatus.PENDING)

        self.assertEqual(stage.name, "test_stage")
        self.assertEqual(stage.status, StageStatus.PENDING)
        self.assertIsNone(stage.started_at)
        self.assertIsNone(stage.completed_at)
        self.assertEqual(stage.output_files, [])
        self.assertEqual(stage.metrics, {})

    def test_serialization(self):
        """Test stage serialization/deserialization."""
        now = datetime.now(UTC)
        original = StageState(
            name="test_stage",
            status=StageStatus.COMPLETED,
            started_at=now,
            completed_at=now,
            output_files=["file1.py", "file2.md"],
            metrics={"duration": 30.5},
        )

        # Serialize to dict
        data = original.to_dict()

        # Verify dict structure
        self.assertEqual(data["name"], "test_stage")
        self.assertEqual(data["status"], "completed")
        self.assertIsInstance(data["started_at"], str)
        self.assertIsInstance(data["completed_at"], str)

        # Deserialize back
        restored = StageState.from_dict(data)

        # Should be equal
        self.assertEqual(original.name, restored.name)
        self.assertEqual(original.status, restored.status)
        self.assertEqual(original.started_at, restored.started_at)
        self.assertEqual(original.completed_at, restored.completed_at)
        self.assertEqual(original.output_files, restored.output_files)
        self.assertEqual(original.metrics, restored.metrics)


class TestWorkflowState(unittest.TestCase):
    """Test WorkflowState functionality."""

    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.workflow_id = "test_workflow_123"
        self.state_file = Path(self.temp_dir) / "test_state.json"

    def test_initialization(self):
        """Test workflow state initialization."""
        state = WorkflowState(self.workflow_id, self.state_file)

        self.assertEqual(state.workflow_id, self.workflow_id)
        self.assertIsInstance(state.created_at, datetime)
        self.assertIsInstance(state.updated_at, datetime)
        self.assertIsNone(state.inputs)
        self.assertIsNone(state.current_stage)

        # Should have default stages
        self.assertTrue(len(state.stages) > 0)
        for stage in state.stages.values():
            self.assertEqual(stage.status, StageStatus.PENDING)

    def test_input_management(self):
        """Test input setting and change detection."""
        state = WorkflowState(self.workflow_id, self.state_file)

        # Set initial inputs
        inputs1 = WorkflowInputs("Build a todo app")
        state.set_inputs(inputs1)

        self.assertIsNotNone(state.inputs_checksum)
        self.assertEqual(state.inputs, inputs1)

        # Same inputs should not be detected as changed
        inputs2 = WorkflowInputs("Build a todo app")
        self.assertFalse(state.has_inputs_changed(inputs2))

        # Different inputs should be detected as changed
        inputs3 = WorkflowInputs("Build a chat app")
        self.assertTrue(state.has_inputs_changed(inputs3))

    def test_stage_lifecycle(self):
        """Test stage lifecycle management."""
        state = WorkflowState(self.workflow_id, self.state_file)
        stage_name = "requirements_analysis"

        # Get initial stage
        stage = state.get_stage(stage_name)
        self.assertEqual(stage.status, StageStatus.PENDING)

        # Start stage
        state.start_stage(stage_name)
        stage = state.get_stage(stage_name)
        self.assertEqual(stage.status, StageStatus.RUNNING)
        self.assertIsNotNone(stage.started_at)
        self.assertEqual(state.current_stage, stage_name)

        # Complete stage
        output_files = ["requirements.md", "analysis.json"]
        metrics = {"duration": 45.2, "files_created": 2}
        state.complete_stage(stage_name, output_files, metrics)

        stage = state.get_stage(stage_name)
        self.assertEqual(stage.status, StageStatus.COMPLETED)
        self.assertIsNotNone(stage.completed_at)
        self.assertEqual(stage.output_files, output_files)
        self.assertEqual(stage.metrics, metrics)

    def test_stage_failure(self):
        """Test stage failure handling."""
        state = WorkflowState(self.workflow_id, self.state_file)
        stage_name = "requirements_analysis"
        error_msg = "Failed to parse requirements"

        state.start_stage(stage_name)
        state.fail_stage(stage_name, error_msg)

        stage = state.get_stage(stage_name)
        self.assertEqual(stage.status, StageStatus.FAILED)
        self.assertEqual(stage.error_message, error_msg)
        self.assertIsNotNone(stage.completed_at)

    def test_workflow_progress(self):
        """Test workflow progress tracking."""
        state = WorkflowState(self.workflow_id, self.state_file)

        # Initially not complete
        self.assertFalse(state.is_workflow_complete())
        self.assertTrue(state.can_resume())

        # Complete first stage
        first_stage = state.get_next_stage()
        self.assertIsNotNone(first_stage)

        state.start_stage(first_stage)
        state.complete_stage(first_stage)

        completed = state.get_completed_stages()
        self.assertEqual(len(completed), 1)
        self.assertIn(first_stage, completed)

        # Still not complete overall
        self.assertFalse(state.is_workflow_complete())
        self.assertTrue(state.can_resume())

    def test_persistence(self):
        """Test state save/load functionality."""
        # Create and configure state
        original_state = WorkflowState(self.workflow_id, self.state_file)
        inputs = WorkflowInputs("Build a todo app", {"theme": "dark"})
        original_state.set_inputs(inputs)

        # Start and complete a stage
        stage_name = "requirements_analysis"
        original_state.start_stage(stage_name)
        original_state.complete_stage(stage_name, ["file1.md"], {"duration": 30})

        # Save state
        original_state.save()
        self.assertTrue(self.state_file.exists())

        # Load state
        loaded_state = WorkflowState.load(self.workflow_id, self.state_file)
        self.assertIsNotNone(loaded_state)

        # Verify loaded state matches original
        self.assertEqual(loaded_state.workflow_id, original_state.workflow_id)
        self.assertEqual(loaded_state.inputs_checksum, original_state.inputs_checksum)
        self.assertEqual(loaded_state.current_stage, original_state.current_stage)

        # Verify stage state
        original_stage = original_state.get_stage(stage_name)
        loaded_stage = loaded_state.get_stage(stage_name)

        self.assertEqual(loaded_stage.status, original_stage.status)
        self.assertEqual(loaded_stage.output_files, original_stage.output_files)
        self.assertEqual(loaded_stage.metrics, original_stage.metrics)

    def test_rollback(self):
        """Test workflow rollback functionality."""
        state = WorkflowState(self.workflow_id, self.state_file)

        # Complete first two stages
        stages = state.DEFAULT_STAGES[:3]
        for stage_name in stages:
            state.start_stage(stage_name)
            state.complete_stage(stage_name)

        # Verify stages are completed
        for stage_name in stages:
            stage = state.get_stage(stage_name)
            self.assertEqual(stage.status, StageStatus.COMPLETED)

        # Rollback to first stage
        rollback_stage = stages[0]
        state.rollback_to_stage(rollback_stage)

        # First stage should still be completed
        stage = state.get_stage(rollback_stage)
        self.assertEqual(stage.status, StageStatus.COMPLETED)

        # Later stages should be reset to pending
        for stage_name in stages[1:]:
            stage = state.get_stage(stage_name)
            self.assertEqual(stage.status, StageStatus.PENDING)
            self.assertIsNone(stage.started_at)
            self.assertIsNone(stage.completed_at)
            self.assertEqual(stage.output_files, [])

    def test_summary(self):
        """Test workflow summary generation."""
        state = WorkflowState(self.workflow_id, self.state_file)

        # Set inputs
        inputs = WorkflowInputs("Build a test app")
        state.set_inputs(inputs)

        # Complete one stage
        first_stage = state.get_next_stage()
        state.start_stage(first_stage)
        state.complete_stage(first_stage)

        summary = state.get_summary()

        self.assertEqual(summary["workflow_id"], self.workflow_id)
        self.assertIn("created_at", summary)
        self.assertIn("updated_at", summary)
        self.assertEqual(summary["total_stages"], len(state.stages))
        self.assertEqual(summary["completed_stages"], 1)
        self.assertEqual(summary["failed_stages"], 0)
        self.assertFalse(summary["is_complete"])
        self.assertTrue(summary["can_resume"])
        self.assertGreater(summary["progress_percent"], 0)
        self.assertIsNotNone(summary["inputs_checksum"])

    def test_load_nonexistent(self):
        """Test loading from non-existent state file."""
        nonexistent_file = Path(self.temp_dir) / "nonexistent.json"
        loaded_state = WorkflowState.load("test_id", nonexistent_file)
        self.assertIsNone(loaded_state)


class TestUtilities(unittest.TestCase):
    """Test utility functions."""

    def test_generate_workflow_id(self):
        """Test workflow ID generation."""
        id1 = generate_workflow_id()
        id2 = generate_workflow_id()

        # Should be strings
        self.assertIsInstance(id1, str)
        self.assertIsInstance(id2, str)

        # Should start with "workflow_"
        self.assertTrue(id1.startswith("workflow_"))
        self.assertTrue(id2.startswith("workflow_"))

        # Should be unique (highly likely)
        self.assertNotEqual(id1, id2)


if __name__ == "__main__":
    unittest.main()
