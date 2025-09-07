#!/usr/bin/env python3
"""Tests for output manager."""

import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from multi_agent_workflow.output_manager import WorkflowLogger, WorkflowProgressDisplay
from multi_agent_workflow.workflow_state import (
    StageStatus,
    WorkflowInputs,
    WorkflowState,
)


class TestWorkflowProgressDisplay(unittest.TestCase):
    """Test WorkflowProgressDisplay functionality."""

    def setUp(self):
        """Set up test environment."""
        self.display = WorkflowProgressDisplay()
        self.temp_dir = tempfile.mkdtemp()
        self.workflow_id = "test_workflow_123"
        self.state_file = Path(self.temp_dir) / "test_state.json"

    def test_status_icons_and_colors(self):
        """Test that status icons and colors are properly defined."""
        # Check that all status types have icons
        for status in StageStatus:
            self.assertIn(status, self.display.status_icons)
            self.assertIn(status, self.display.status_colors)

        # Check specific mappings
        self.assertEqual(self.display.status_icons[StageStatus.COMPLETED], "✅")
        self.assertEqual(self.display.status_icons[StageStatus.RUNNING], "🔄")
        self.assertEqual(self.display.status_icons[StageStatus.FAILED], "❌")
        self.assertEqual(self.display.status_icons[StageStatus.PENDING], "⏳")

    def test_create_workflow_header(self):
        """Test workflow header creation."""
        header = self.display.create_workflow_header(
            "test_workflow", "Build a test application"
        )

        # Should be a Panel with the right content
        self.assertIsNotNone(header)
        # Test passes if no exception is thrown

    def test_create_stage_progress_table(self):
        """Test stage progress table creation."""
        # Create a workflow state with some completed stages
        state = WorkflowState(self.workflow_id, self.state_file)

        # Complete one stage
        state.start_stage("requirements_analysis")
        state.complete_stage(
            "requirements_analysis",
            output_files=["requirements.md"],
            metrics={"duration": 30.0},
        )

        # Create table
        table = self.display.create_stage_progress_table(state)

        # Should be a Table object
        self.assertIsNotNone(table)
        # Test passes if no exception is thrown

    def test_create_metrics_panel(self):
        """Test metrics panel creation."""
        # Create a workflow state
        state = WorkflowState(self.workflow_id, self.state_file)
        inputs = WorkflowInputs("Build a test app")
        state.set_inputs(inputs)

        # Create metrics panel
        panel = self.display.create_metrics_panel(state)

        # Should be a Panel object
        self.assertIsNotNone(panel)
        # Test passes if no exception is thrown

    @patch("sys.stdout", new_callable=io.StringIO)
    def test_display_workflow_status(self, mock_stdout):
        """Test full workflow status display."""
        # Create a workflow state
        state = WorkflowState(self.workflow_id, self.state_file)
        inputs = WorkflowInputs("Build a test calculator")
        state.set_inputs(inputs)

        # Display status (this should not raise an exception)
        try:
            self.display.display_workflow_status(state, "Build a test calculator")
        except Exception as e:
            self.fail(f"display_workflow_status raised an exception: {e}")

    @patch("sys.stdout", new_callable=io.StringIO)
    def test_show_stage_start(self, mock_stdout):
        """Test stage start display."""
        try:
            self.display.show_stage_start(
                "requirements_analysis",
                "Analyze requirements and create specifications",
            )
        except Exception as e:
            self.fail(f"show_stage_start raised an exception: {e}")

    @patch("sys.stdout", new_callable=io.StringIO)
    def test_show_stage_complete(self, mock_stdout):
        """Test stage completion display."""
        result = {
            "output_files": ["file1.md", "file2.py"],
            "metrics": {"duration": 45.2, "files_created": 2},
            "next_actions": ["Review files", "Run tests"],
        }

        try:
            self.display.show_stage_complete("requirements_analysis", result)
        except Exception as e:
            self.fail(f"show_stage_complete raised an exception: {e}")

    @patch("sys.stdout", new_callable=io.StringIO)
    def test_show_stage_failure(self, mock_stdout):
        """Test stage failure display."""
        try:
            self.display.show_stage_failure(
                "requirements_analysis", "Failed to parse requirements file"
            )
        except Exception as e:
            self.fail(f"show_stage_failure raised an exception: {e}")

    @patch("sys.stdout", new_callable=io.StringIO)
    def test_show_workflow_complete(self, mock_stdout):
        """Test workflow completion display."""
        # Create a completed workflow state
        state = WorkflowState(self.workflow_id, self.state_file)

        # Complete all stages
        for stage_name in state.stages.keys():
            state.start_stage(stage_name)
            state.complete_stage(stage_name)

        try:
            self.display.show_workflow_complete(state)
        except Exception as e:
            self.fail(f"show_workflow_complete raised an exception: {e}")

    @patch("sys.stdout", new_callable=io.StringIO)
    def test_show_messages(self, mock_stdout):
        """Test various message displays."""
        try:
            self.display.show_error("Test error message")
            self.display.show_info("Test info message")
            self.display.show_success("Test success message")
        except Exception as e:
            self.fail(f"Message display methods raised an exception: {e}")


class TestWorkflowLogger(unittest.TestCase):
    """Test WorkflowLogger functionality."""

    def setUp(self):
        """Set up test environment."""
        self.logger = WorkflowLogger("test_logger")

    def test_logger_initialization(self):
        """Test logger initialization."""
        self.assertIsNotNone(self.logger.logger)
        self.assertIsNotNone(self.logger.display)

    @patch("logging.Logger.info")
    def test_info_logging(self, mock_log):
        """Test info logging with rich formatting."""
        self.logger.info("Test info message")
        mock_log.assert_called_once()

        # Check that the message was formatted with rich markup
        args, kwargs = mock_log.call_args
        self.assertIn("ℹ️", args[0])

    @patch("logging.Logger.info")
    def test_success_logging(self, mock_log):
        """Test success logging with rich formatting."""
        self.logger.success("Test success message")
        mock_log.assert_called_once()

        # Check that the message was formatted with rich markup
        args, kwargs = mock_log.call_args
        self.assertIn("✅", args[0])

    @patch("logging.Logger.warning")
    def test_warning_logging(self, mock_log):
        """Test warning logging with rich formatting."""
        self.logger.warning("Test warning message")
        mock_log.assert_called_once()

        # Check that the message was formatted with rich markup
        args, kwargs = mock_log.call_args
        self.assertIn("⚠️", args[0])

    @patch("logging.Logger.error")
    def test_error_logging(self, mock_log):
        """Test error logging with rich formatting."""
        self.logger.error("Test error message")
        mock_log.assert_called_once()

        # Check that the message was formatted with rich markup
        args, kwargs = mock_log.call_args
        self.assertIn("❌", args[0])

    @patch("logging.Logger.info")
    def test_stage_logging_methods(self, mock_log):
        """Test stage-specific logging methods."""
        # Test stage start
        self.logger.stage_start("requirements_analysis", "Test description")
        self.assertTrue(mock_log.called)

        mock_log.reset_mock()

        # Test stage complete
        self.logger.stage_complete("requirements_analysis", 30.5)
        self.assertTrue(mock_log.called)

    @patch("logging.Logger.error")
    def test_stage_failed_logging(self, mock_log):
        """Test stage failed logging."""
        self.logger.stage_failed("requirements_analysis", "Test error")
        mock_log.assert_called_once()

        # Check that the message was formatted with rich markup
        args, kwargs = mock_log.call_args
        self.assertIn("❌", args[0])
        self.assertIn("Requirements Analysis", args[0])


if __name__ == "__main__":
    unittest.main()
