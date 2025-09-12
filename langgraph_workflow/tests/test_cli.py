"""Tests for CLI functionality and interactive mode."""

import argparse
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# Import CLI functions directly - dependencies should be available
from ..run import extract_feature_from_prd, interactive_mode, main, run_workflow
from .mocks.simple_test_workflow import TestMultiAgentWorkflow


class TestFeatureExtraction(unittest.TestCase):
    """Test PRD feature extraction functionality."""

    def test_extract_feature_simple(self):
        """Test extracting a feature with simple markdown headers."""
        prd_content = """# Product Requirements Document

## User Authentication
This feature handles user login and registration.
- Login with email/password
- Registration with email verification
- Password reset functionality

## User Profile Management
This feature manages user profile information.
- Update profile details
- Upload profile picture
- Privacy settings
"""

        result = extract_feature_from_prd(prd_content, "User Authentication")

        self.assertIsNotNone(result)
        self.assertIn("User Authentication", result)
        self.assertIn("user login and registration", result)
        self.assertIn("Login with email/password", result)
        self.assertNotIn("User Profile Management", result)

    def test_extract_feature_numbered_list(self):
        """Test extracting feature from numbered list."""
        prd_content = """# Features

1. Authentication System
   - JWT tokens
   - Role-based access
   - Session management

2. Data Processing Pipeline
   - ETL operations
   - Data validation
   - Error handling

3. Reporting Dashboard
   - Real-time metrics
   - Export functionality
"""

        result = extract_feature_from_prd(prd_content, "Authentication System")

        self.assertIsNotNone(result)
        self.assertIn("Authentication System", result)
        self.assertIn("JWT tokens", result)
        self.assertNotIn("Data Processing Pipeline", result)

    def test_extract_feature_case_insensitive(self):
        """Test case-insensitive feature extraction."""
        prd_content = """## User AUTHENTICATION
Login system with security features."""

        result = extract_feature_from_prd(prd_content, "user authentication")

        self.assertIsNotNone(result)
        self.assertIn("User AUTHENTICATION", result)

    def test_extract_feature_not_found(self):
        """Test when feature is not found in PRD."""
        prd_content = """## Payment System
Handle payments and billing."""

        result = extract_feature_from_prd(prd_content, "Authentication")

        self.assertIsNone(result)

    def test_extract_feature_empty_content(self):
        """Test with empty PRD content."""
        result = extract_feature_from_prd("", "Authentication")

        self.assertIsNone(result)

    def test_extract_feature_multiline_section(self):
        """Test extracting multiline feature section."""
        prd_content = """# Requirements

## Authentication Feature
This is a comprehensive authentication system.

It includes:
- User registration
- Login/logout
- Password management
- Two-factor authentication

The system should be secure and scalable.

## Next Feature
Something else here.
"""

        result = extract_feature_from_prd(prd_content, "Authentication Feature")

        self.assertIsNotNone(result)
        self.assertIn("comprehensive authentication system", result)
        self.assertIn("Two-factor authentication", result)
        self.assertIn("secure and scalable", result)
        self.assertNotIn("Next Feature", result)


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

    @patch("langgraph_workflow.run.MultiAgentWorkflow", TestMultiAgentWorkflow)
    async def test_run_workflow_basic(self):
        """Test basic workflow execution using TestMultiAgentWorkflow."""
        # Execute workflow with test implementation
        result = await run_workflow(
            repo_path=self.repo_path,
            feature_description="Test feature",
            thread_id=self.thread_id,
        )

        # Verify result structure and basic functionality
        self.assertIsNotNone(result)
        self.assertEqual(result["thread_id"], self.thread_id)
        self.assertEqual(result["quality"], "ok")
        self.assertEqual(result["current_phase"], "completed")
        self.assertIn("Test feature", result["feature_description"])

    @patch("langgraph_workflow.run.MultiAgentWorkflow", TestMultiAgentWorkflow)
    async def test_run_workflow_with_feature_file(self):
        """Test workflow with feature file input using TestMultiAgentWorkflow."""
        # Create temporary feature file
        feature_file = Path(self.temp_dir.name) / "features.md"
        feature_content = """# Features

## Authentication
User login system with JWT tokens.

## Dashboard
Analytics and reporting interface.
"""
        feature_file.write_text(feature_content)

        # Execute with feature file
        result = await run_workflow(
            repo_path=self.repo_path,
            feature_description="",  # Empty since using file
            feature_file=str(feature_file),
            feature_name="Authentication",
        )

        # Verify workflow executed correctly
        self.assertIsNotNone(result)
        self.assertEqual(result["quality"], "ok")
        self.assertIn("User login system", result["feature_description"])

    async def test_run_workflow_file_not_found(self):
        """Test error handling when feature file doesn't exist."""
        with self.assertRaises(FileNotFoundError):
            await run_workflow(
                repo_path=self.repo_path,
                feature_description="",
                feature_file="/nonexistent/file.md",
            )

    async def test_run_workflow_feature_not_found(self):
        """Test error when specific feature not found in PRD."""
        # Create feature file without the requested feature
        feature_file = Path(self.temp_dir.name) / "features.md"
        feature_file.write_text("## Other Feature\nSome other feature.")

        with self.assertRaises(ValueError) as context:
            await run_workflow(
                repo_path=self.repo_path,
                feature_description="",
                feature_file=str(feature_file),
                feature_name="Authentication",
            )

        self.assertIn("Authentication", str(context.exception))
        self.assertIn("not found", str(context.exception))

    async def test_run_workflow_feature_name_without_file(self):
        """Test error when feature_name provided without feature_file."""
        with self.assertRaises(ValueError) as context:
            await run_workflow(
                repo_path=self.repo_path,
                feature_description="Test feature",
                feature_name="Authentication",
            )

        self.assertIn("feature_name requires feature_file", str(context.exception))

    @patch("langgraph_workflow.run.MultiAgentWorkflow", TestMultiAgentWorkflow)  
    async def test_run_workflow_resume_mode(self):
        """Test resuming workflow from checkpoint using TestMultiAgentWorkflow."""
        # Execute in resume mode
        result = await run_workflow(
            repo_path=self.repo_path,
            feature_description="Test authentication feature",
            thread_id=self.thread_id,
            resume=True,
        )

        # Verify workflow executes correctly in resume mode
        self.assertIsNotNone(result)
        self.assertEqual(result["thread_id"], self.thread_id)
        self.assertIn("authentication", result["feature_description"].lower())


class TestInteractiveMode(unittest.IsolatedAsyncioTestCase):
    """Test interactive mode functionality."""

    @patch("builtins.input")
    @patch("langgraph_workflow.run.run_workflow")
    async def test_interactive_new_workflow(self, mock_run_workflow, mock_input):
        """Test starting new workflow in interactive mode."""
        # Mock user inputs
        mock_input.side_effect = [
            "1",  # Start new workflow
            "/tmp/test-repo",  # Repository path
            "Add authentication",  # Feature description
            "",  # Thread ID (empty for auto-generate)
            "5",  # Exit
        ]

        # Mock run_workflow
        mock_run_workflow.return_value = {"quality": "ok"}

        # Execute interactive mode
        await interactive_mode()

        # Verify run_workflow was called with correct parameters
        mock_run_workflow.assert_called_once()
        call_args = mock_run_workflow.call_args
        self.assertEqual(call_args[1]["repo_path"], "/tmp/test-repo")
        self.assertEqual(call_args[1]["feature_description"], "Add authentication")
        self.assertIsNone(call_args[1]["thread_id"])

    @patch("builtins.input")
    @patch("langgraph_workflow.run.run_workflow")
    async def test_interactive_resume_workflow(self, mock_run_workflow, mock_input):
        """Test resuming workflow in interactive mode."""
        mock_input.side_effect = [
            "2",  # Resume existing workflow
            "test-thread-123",  # Thread ID
            "/tmp/test-repo",  # Repository path
            "5",  # Exit
        ]

        mock_run_workflow.return_value = {"quality": "ok"}

        await interactive_mode()

        # Verify resume parameters
        mock_run_workflow.assert_called_once()
        call_args = mock_run_workflow.call_args[1]
        self.assertEqual(call_args["thread_id"], "test-thread-123")
        self.assertTrue(call_args["resume"])

    @patch("builtins.input")
    @patch("sqlite3.connect")
    async def test_interactive_list_threads(self, mock_sqlite, mock_input):
        """Test listing existing threads."""
        mock_input.side_effect = [
            "3",  # List existing threads
            "agent_state.db",  # Database path
            "5",  # Exit
        ]

        # Mock database
        class MockCursor:
            def fetchall(self):
                return [("thread-1",), ("thread-2",)]
            def execute(self, query):
                pass
                
        class MockConnection:
            def cursor(self):
                return MockCursor()
                
        mock_sqlite.return_value = MockConnection()

        with patch("pathlib.Path.exists", return_value=True):
            await interactive_mode()

        # Verify database was queried
        mock_sqlite.assert_called_once_with("agent_state.db")
        mock_cursor.execute.assert_called_once_with(
            "SELECT DISTINCT thread_id FROM checkpoints"
        )

    @patch("builtins.input")
    async def test_interactive_view_artifacts(self, mock_input):
        """Test viewing thread artifacts."""
        temp_dir = tempfile.TemporaryDirectory()

        try:
            # Create mock artifacts
            artifacts_dir = Path(temp_dir.name) / "agents" / "artifacts" / "test-thread"
            artifacts_dir.mkdir(parents=True, exist_ok=True)
            (artifacts_dir / "design.md").write_text("Design document")
            (artifacts_dir / "test.py").write_text("Test code")

            mock_input.side_effect = [
                "4",  # View thread artifacts
                "test-thread",  # Thread ID
                temp_dir.name,  # Repository path
                "5",  # Exit
            ]

            await interactive_mode()

            # Test completes without error - artifacts were displayed

        finally:
            temp_dir.cleanup()

    @patch("builtins.input")
    async def test_interactive_invalid_option(self, mock_input):
        """Test handling invalid menu option."""
        mock_input.side_effect = [
            "99",  # Invalid option
            "5",  # Exit
        ]

        # Should complete without error
        await interactive_mode()

    @patch("builtins.input")
    @patch("langgraph_workflow.run.run_workflow")
    async def test_interactive_missing_required_fields(
        self, mock_run_workflow, mock_input
    ):
        """Test validation of required fields."""
        mock_input.side_effect = [
            "1",  # Start new workflow
            "",  # Empty repository path
            "",  # Empty feature description
            "5",  # Exit
        ]

        await interactive_mode()

        # run_workflow should not be called due to validation
        mock_run_workflow.assert_not_called()


class TestMainFunction(unittest.TestCase):
    """Test the main CLI function."""

    @patch("sys.argv", ["run.py", "--interactive"])
    @patch("langgraph_workflow.run.interactive_mode")
    @patch("asyncio.run")
    def test_main_interactive_mode(self, mock_asyncio_run, mock_interactive):
        """Test main function with interactive flag."""
        main()

        # Verify interactive mode was called
        mock_asyncio_run.assert_called_once_with(mock_interactive.return_value)

    @patch(
        "sys.argv", ["run.py", "--repo-path", "/tmp/repo", "--feature", "Test feature"]
    )
    @patch("langgraph_workflow.run.run_workflow")
    @patch("asyncio.run")
    def test_main_direct_execution(self, mock_asyncio_run, mock_run_workflow):
        """Test main function with direct parameters."""
        main()

        # Verify run_workflow was called via asyncio.run
        mock_asyncio_run.assert_called_once()

    @patch(
        "sys.argv",
        [
            "run.py",
            "--repo-path",
            "/tmp/repo",
            "--feature-file",
            "features.md",
            "--feature-name",
            "Auth",
        ],
    )
    @patch("langgraph_workflow.run.run_workflow")
    @patch("asyncio.run")
    def test_main_with_feature_file(self, mock_asyncio_run, mock_run_workflow):
        """Test main function with feature file parameters."""
        main()

        mock_asyncio_run.assert_called_once()

    @patch(
        "sys.argv",
        ["run.py", "--repo-path", "/tmp/repo", "--thread-id", "test-123", "--resume"],
    )
    @patch("langgraph_workflow.run.run_workflow")
    @patch("asyncio.run")
    def test_main_resume_mode(self, mock_asyncio_run, mock_run_workflow):
        """Test main function in resume mode."""
        main()

        mock_asyncio_run.assert_called_once()

    @patch("sys.argv", ["run.py", "--repo-path", "/tmp/repo"])  # Missing feature
    @patch("sys.exit")
    def test_main_missing_feature(self, mock_exit):
        """Test main function with missing required feature."""
        main()

        # Should exit with error
        mock_exit.assert_called_once_with(1)

    @patch("sys.argv", ["run.py", "--feature-name", "Auth"])  # Missing feature-file
    @patch("sys.exit")
    def test_main_feature_name_without_file(self, mock_exit):
        """Test main function with feature-name but no feature-file."""
        main()

        mock_exit.assert_called_once_with(1)

    @patch("sys.argv", ["run.py", "--debug"])
    @patch("logging.getLogger")
    def test_main_debug_logging(self, mock_get_logger):
        """Test debug logging activation."""
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        with patch("sys.exit"):  # Prevent actual exit
            main()

        # Verify debug level was set
        mock_logger.setLevel.assert_called()

    @patch("sys.argv", ["run.py", "--help"])
    @patch("sys.exit")
    def test_main_help_display(self, mock_exit):
        """Test help display."""
        with patch("argparse.ArgumentParser.print_help") as mock_help:
            main()

        # Help should be displayed and program should exit
        mock_exit.assert_called()

    @patch("sys.argv", ["run.py"])  # No arguments
    @patch("argparse.ArgumentParser.print_help")
    @patch("sys.exit")
    def test_main_no_arguments(self, mock_exit, mock_help):
        """Test main function with no arguments."""
        main()

        # Should print help and exit
        mock_help.assert_called_once()
        mock_exit.assert_called_once_with(1)


class TestArgumentParsing(unittest.TestCase):
    """Test command line argument parsing."""

    def setUp(self):
        """Set up argument parser."""
        self.parser = argparse.ArgumentParser()

        # Add the same arguments as the main function
        self.parser.add_argument("--repo-path", help="Path to the repository")
        self.parser.add_argument("--feature", help="Feature description (text)")
        self.parser.add_argument(
            "--feature-file", help="Path to file containing feature description or PRD"
        )
        self.parser.add_argument(
            "--feature-name",
            help="Name of specific feature within PRD (requires --feature-file)",
        )
        self.parser.add_argument("--thread-id", help="Thread ID for persistence")
        self.parser.add_argument(
            "--checkpoint-path",
            default="agent_state.db",
            help="SQLite checkpoint database path",
        )
        self.parser.add_argument(
            "--resume", action="store_true", help="Resume from existing checkpoint"
        )
        self.parser.add_argument(
            "--interactive", action="store_true", help="Run in interactive mode"
        )
        self.parser.add_argument(
            "--debug", action="store_true", help="Enable debug logging"
        )

    def test_parse_basic_arguments(self):
        """Test parsing basic arguments."""
        args = self.parser.parse_args(
            ["--repo-path", "/tmp/repo", "--feature", "Test feature"]
        )

        self.assertEqual(args.repo_path, "/tmp/repo")
        self.assertEqual(args.feature, "Test feature")
        self.assertFalse(args.resume)
        self.assertFalse(args.interactive)
        self.assertFalse(args.debug)

    def test_parse_feature_file_arguments(self):
        """Test parsing feature file arguments."""
        args = self.parser.parse_args(
            [
                "--repo-path",
                "/tmp/repo",
                "--feature-file",
                "features.md",
                "--feature-name",
                "Authentication",
            ]
        )

        self.assertEqual(args.feature_file, "features.md")
        self.assertEqual(args.feature_name, "Authentication")

    def test_parse_resume_arguments(self):
        """Test parsing resume arguments."""
        args = self.parser.parse_args(
            ["--repo-path", "/tmp/repo", "--thread-id", "test-123", "--resume"]
        )

        self.assertEqual(args.thread_id, "test-123")
        self.assertTrue(args.resume)

    def test_parse_interactive_flag(self):
        """Test parsing interactive flag."""
        args = self.parser.parse_args(["--interactive"])

        self.assertTrue(args.interactive)

    def test_parse_debug_flag(self):
        """Test parsing debug flag."""
        args = self.parser.parse_args(["--debug"])

        self.assertTrue(args.debug)

    def test_parse_custom_checkpoint_path(self):
        """Test parsing custom checkpoint path."""
        args = self.parser.parse_args(["--checkpoint-path", "/custom/path/state.db"])

        self.assertEqual(args.checkpoint_path, "/custom/path/state.db")

    def test_default_values(self):
        """Test default argument values."""
        args = self.parser.parse_args([])

        self.assertEqual(args.checkpoint_path, "agent_state.db")
        self.assertIsNone(args.repo_path)
        self.assertIsNone(args.feature)
        self.assertIsNone(args.feature_file)
        self.assertIsNone(args.feature_name)
        self.assertIsNone(args.thread_id)
        self.assertFalse(args.resume)
        self.assertFalse(args.interactive)
        self.assertFalse(args.debug)


if __name__ == "__main__":
    unittest.main()
