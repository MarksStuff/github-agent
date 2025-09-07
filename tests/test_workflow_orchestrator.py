#!/usr/bin/env python3
"""Tests for workflow orchestrator."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from multi_agent_workflow.workflow import WorkflowOrchestrator


class TestWorkflowOrchestrator(unittest.TestCase):
    """Test WorkflowOrchestrator functionality."""

    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.orchestrator = WorkflowOrchestrator()

    def test_start_workflow(self):
        """Test starting a new workflow."""
        project_desc = "Build a test application"

        # Mock the state directory to use temp directory
        with patch("multi_agent_workflow.workflow_state.Path") as mock_path:
            mock_path.return_value.parent = Path(self.temp_dir)

            workflow_id = self.orchestrator.start_workflow(project_desc)

        # Verify workflow ID format
        self.assertTrue(workflow_id.startswith("workflow_"))
        self.assertIn("_", workflow_id)

    def test_get_workflow_status(self):
        """Test getting workflow status."""
        # Test non-existent workflow
        status = self.orchestrator.get_workflow_status("nonexistent")
        self.assertIn("error", status)

        # Test existing workflow (would require actual state file)

    def test_workflow_stages(self):
        """Test that all expected stages are defined."""
        expected_stages = [
            "requirements_analysis",
            "architecture_design",
            "implementation_plan",
            "code_generation",
            "testing_setup",
            "documentation",
        ]

        for stage_name in expected_stages:
            self.assertIn(stage_name, self.orchestrator.stages)

    def test_stage_validation(self):
        """Test stage input validation."""
        req_stage = self.orchestrator.stages["requirements_analysis"]

        # Test validation with good inputs
        from multi_agent_workflow.workflow_state import WorkflowInputs

        good_inputs = WorkflowInputs("Build a comprehensive todo app")
        errors = req_stage.validate_inputs(good_inputs)
        self.assertEqual(len(errors), 0)

        # Test validation with bad inputs
        bad_inputs = WorkflowInputs("short")  # Too short
        errors = req_stage.validate_inputs(bad_inputs)
        self.assertGreater(len(errors), 0)

    def test_list_workflows_empty(self):
        """Test listing workflows when none exist."""
        # Mock empty state directory
        with patch("pathlib.Path.glob") as mock_glob:
            mock_glob.return_value = []
            workflows = self.orchestrator.list_workflows()

        self.assertEqual(len(workflows), 0)


if __name__ == "__main__":
    unittest.main()
