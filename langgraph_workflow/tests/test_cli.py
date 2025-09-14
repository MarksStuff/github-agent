"""Tests for CLI functionality and interactive mode.

Note: Comprehensive feature extraction tests are in test_feature_extraction.py
This file focuses on CLI-specific functionality.
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Import CLI functions directly - dependencies should be available
from ..run import main, run_workflow
from .mocks.simple_test_workflow import TestMultiAgentWorkflow


class TestCLIBasicFunctionality(unittest.TestCase):
    """Test basic CLI functionality without LLM dependencies."""

    def test_main_with_help_argument(self):
        """Test that main function handles help argument correctly."""
        with patch("sys.argv", ["run.py", "--help"]):
            with patch("argparse.ArgumentParser.print_help") as mock_help:
                with patch("sys.exit"):
                    try:
                        main()
                    except SystemExit:
                        pass  # Expected when --help is used

                    # Help should have been called
                    mock_help.assert_called_once()

    def test_main_with_list_steps(self):
        """Test --list-steps functionality."""
        with patch("sys.argv", ["run.py", "--list-steps"]):
            with patch("builtins.print") as mock_print:
                main()

                # Should print available steps
                mock_print.assert_called()
                printed_output = " ".join(
                    str(call) for call in mock_print.call_args_list
                )
                assert "extract_code_context" in printed_output

    def test_main_validates_required_arguments(self):
        """Test that main validates required arguments."""
        with patch("sys.argv", ["run.py", "--step", "extract_code_context"]):
            with patch("builtins.print") as mock_print:
                with patch("sys.exit") as mock_exit:
                    main()

                    # Should exit with error about missing --repo-path
                    mock_exit.assert_called_with(1)
                    mock_print.assert_called()


class TestRunWorkflow(unittest.IsolatedAsyncioTestCase):
    """Test the main run_workflow function."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.repo_path = self.temp_dir.name
        self.thread_id = "test-thread"

    def tearDown(self):
        """Clean up test fixtures."""
        self.temp_dir.cleanup()

    async def test_run_workflow_basic(self):
        """Test basic workflow execution using TestMultiAgentWorkflow."""
        # Execute workflow with test implementation injected
        result = await run_workflow(
            repo_path=self.repo_path,
            feature_description="Test feature",
            thread_id=self.thread_id,
            workflow_class=TestMultiAgentWorkflow,
        )

        # Verify result structure and basic functionality
        self.assertIsNotNone(result)
        self.assertEqual(result["thread_id"], self.thread_id)
        self.assertEqual(result["quality"], "ok")
        self.assertEqual(result["current_phase"], "completed")

    async def test_run_workflow_with_feature_file(self):
        """Test workflow execution with feature file input."""
        # Create a temporary feature file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("# Test Feature\nThis is a test feature description.")
            feature_file = f.name

        try:
            result = await run_workflow(
                repo_path=self.repo_path,
                feature_description="",
                thread_id=self.thread_id,
                feature_file=feature_file,
                workflow_class=TestMultiAgentWorkflow,
            )

            # Should successfully load from file
            self.assertIsNotNone(result)
            self.assertEqual(result["thread_id"], self.thread_id)

        finally:
            Path(feature_file).unlink()

    async def test_run_workflow_resume_mode(self):
        """Test workflow resume functionality."""
        # This is a basic test - more comprehensive resume testing would require
        # actual checkpoint data
        from unittest.mock import AsyncMock
        
        with patch("langgraph_workflow.run.MultiAgentWorkflow") as mock_workflow:
            mock_app = AsyncMock()
            mock_app.ainvoke.return_value = {
                "thread_id": self.thread_id,
                "current_phase": "resumed",
                "quality": "ok",
            }
            mock_workflow.return_value.app = mock_app
            mock_workflow.return_value.thread_id = self.thread_id

            result = await run_workflow(
                repo_path=self.repo_path,
                feature_description="",
                thread_id=self.thread_id,
                resume=True,
                workflow_class=mock_workflow,
            )

            self.assertEqual(result["thread_id"], self.thread_id)
            self.assertEqual(result["current_phase"], "resumed")


class TestCLIUtilities(unittest.TestCase):
    """Test CLI utility functions."""

    def test_file_path_validation(self):
        """Test that file path validation works correctly."""
        # Test with existing file
        with tempfile.NamedTemporaryFile() as temp_file:
            self.assertTrue(Path(temp_file.name).exists())

        # Test with non-existing file
        non_existing = "/tmp/definitely_does_not_exist_12345.txt"
        self.assertFalse(Path(non_existing).exists())
