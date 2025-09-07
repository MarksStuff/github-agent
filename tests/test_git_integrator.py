#!/usr/bin/env python3
"""Tests for git integrator."""

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from multi_agent_workflow.git_integrator import GitIntegrator
from multi_agent_workflow.workflow_state import (
    WorkflowInputs,
    WorkflowState,
)


class TestGitIntegrator(unittest.TestCase):
    """Test GitIntegrator functionality."""

    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.repo_path = Path(self.temp_dir)

        # Create a mock .git directory
        (self.repo_path / ".git").mkdir()

        self.git = GitIntegrator(self.repo_path)

    def test_initialization_valid_repo(self):
        """Test initialization with valid git repository."""
        self.assertEqual(self.git.repo_path, self.repo_path)
        self.assertTrue(self.git._is_git_repo())

    def test_initialization_invalid_repo(self):
        """Test initialization with invalid git repository."""
        invalid_path = Path(tempfile.mkdtemp())

        with self.assertRaises(ValueError):
            GitIntegrator(invalid_path)

    @patch("subprocess.run")
    def test_run_git_command_success(self, mock_run):
        """Test successful git command execution."""
        mock_result = Mock()
        mock_result.stdout = "test output"
        mock_run.return_value = mock_result

        result = self.git._run_git_command(["status"])

        mock_run.assert_called_once_with(
            ["git", "status"],
            cwd=self.repo_path,
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertEqual(result.stdout, "test output")

    @patch("subprocess.run")
    def test_run_git_command_failure(self, mock_run):
        """Test git command execution failure."""
        mock_run.side_effect = subprocess.CalledProcessError(1, ["git", "status"])

        with self.assertRaises(subprocess.CalledProcessError):
            self.git._run_git_command(["status"])

    @patch("subprocess.run")
    def test_get_current_branch(self, mock_run):
        """Test getting current branch name."""
        mock_result = Mock()
        mock_result.stdout = "feature-branch\n"
        mock_run.return_value = mock_result

        branch = self.git.get_current_branch()

        mock_run.assert_called_once()
        self.assertEqual(branch, "feature-branch")

    @patch("subprocess.run")
    def test_get_current_branch_failure(self, mock_run):
        """Test getting current branch when command fails."""
        mock_run.side_effect = subprocess.CalledProcessError(1, ["git"])

        branch = self.git.get_current_branch()

        # Should return default fallback
        self.assertEqual(branch, "main")

    @patch("subprocess.run")
    def test_get_repo_status(self, mock_run):
        """Test getting repository status."""

        # Mock calls in order: status --porcelain, then get_current_branch
        def mock_run_side_effect(cmd, **kwargs):
            if "status" in cmd and "--porcelain" in cmd:
                mock_result = Mock()
                # Format: XY filename (X=staged, Y=unstaged)
                mock_result.stdout = (
                    " M modified_file.py\nA  new_file.py\n?? untracked_file.py\n"
                )
                return mock_result
            elif "rev-parse" in cmd and "--abbrev-ref" in cmd:
                mock_result = Mock()
                mock_result.stdout = "main\n"
                return mock_result
            return Mock()

        mock_run.side_effect = mock_run_side_effect

        status = self.git.get_repo_status()

        self.assertTrue(status["has_changes"])
        # A followed by space means staged file
        self.assertIn("new_file.py", status["staged_files"])
        # Space followed by M means unstaged modification
        self.assertIn("modified_file.py", status["unstaged_files"])
        # ?? means untracked
        self.assertIn("untracked_file.py", status["untracked_files"])
        self.assertEqual(status["current_branch"], "main")

    @patch("subprocess.run")
    def test_create_workflow_branch(self, mock_run):
        """Test creating workflow branch."""
        mock_run.return_value = Mock(stdout="main\n")

        # Mock the rev-parse command to simulate branch doesn't exist
        def mock_run_side_effect(cmd, **kwargs):
            if "rev-parse" in cmd and "--verify" in cmd:
                raise subprocess.CalledProcessError(1, cmd)
            return Mock(stdout="main\n")

        mock_run.side_effect = mock_run_side_effect

        workflow_id = "test_workflow_123"
        branch_name = self.git.create_workflow_branch(workflow_id)

        # Should start with workflow/
        self.assertTrue(branch_name.startswith(f"workflow/{workflow_id}"))

        # Should have called checkout -b
        checkout_call = None
        for call_args in mock_run.call_args_list:
            if "checkout" in call_args[0][0]:
                checkout_call = call_args[0][0]
                break

        self.assertIsNotNone(checkout_call)
        self.assertIn("-b", checkout_call)

    def test_generate_stage_commit_message(self):
        """Test generating commit message for stage."""
        # Create workflow state
        workflow_state = WorkflowState("test_workflow")
        inputs = WorkflowInputs("Build a test application")
        workflow_state.set_inputs(inputs)

        # Complete a stage to get realistic progress
        workflow_state.start_stage("requirements_analysis")
        workflow_state.complete_stage("requirements_analysis")

        stage_result = {
            "output_files": ["requirements.md", "user_stories.md"],
            "metrics": {"duration": 30.5, "files_created": 2},
            "next_actions": ["Review with stakeholders"],
        }

        message = self.git.generate_stage_commit_message(
            "requirements_analysis", stage_result, workflow_state
        )

        # Verify message structure
        self.assertIn("feat: Complete Requirements Analysis", message)
        self.assertIn("Build a test application", message)
        self.assertIn("test_workflow", message)
        self.assertIn("📊 Stage Metrics:", message)
        self.assertIn("Duration: 30.5", message)
        self.assertIn("📁 Files Created:", message)
        self.assertIn("requirements.md", message)
        self.assertIn("🔄 Next Actions:", message)
        self.assertIn("Review with stakeholders", message)
        self.assertIn("🤖 Generated with [Claude Code]", message)

    def test_stage_workflow_files(self):
        """Test staging workflow files."""
        # Mock get_repo_status to avoid subprocess calls
        with patch.object(self.git, "get_repo_status") as mock_status:
            with patch.object(self.git, "_run_git_command") as mock_run:
                mock_status.return_value = {
                    "unstaged_files": ["multi_agent_workflow/test.py"],
                }

                # Create some test state files
                state_dir = self.repo_path / "multi_agent_workflow" / "state"
                state_dir.mkdir(parents=True)
                state_file = state_dir / "test_workflow_state.json"
                state_file.write_text('{"test": "data"}')

                stage_result = {"output_files": ["requirements.md"]}

                # Create the output file
                output_file = self.repo_path / "requirements.md"
                output_file.write_text("# Requirements")

                staged_files = self.git.stage_workflow_files(
                    "requirements_analysis", stage_result
                )

                # Should have staged files
                self.assertTrue(len(staged_files) > 0)

                # Should have called git add
                add_calls = [
                    call_args
                    for call_args in mock_run.call_args_list
                    if "add" in call_args[0][0]
                ]
                self.assertTrue(len(add_calls) > 0)

    def test_commit_stage(self):
        """Test committing a stage."""
        # Mock stage_workflow_files and _run_git_command
        with patch.object(self.git, "stage_workflow_files") as mock_stage:
            with patch.object(self.git, "_run_git_command") as mock_run:
                mock_stage.return_value = ["state_file.json"]

                def mock_run_side_effect(cmd, **kwargs):
                    if "rev-parse" in cmd and "HEAD" in cmd:
                        return Mock(stdout="abc123def456\n")
                    return Mock()

                mock_run.side_effect = mock_run_side_effect

                # Create workflow state
                workflow_state = WorkflowState("test_workflow")
                inputs = WorkflowInputs("Test project")
                workflow_state.set_inputs(inputs)

                stage_result = {"output_files": [], "metrics": {"duration": 1.0}}

                commit_hash = self.git.commit_stage(
                    "requirements_analysis", stage_result, workflow_state
                )

                # Should return commit hash
                self.assertEqual(commit_hash, "abc123def456")

                # Should have called stage_workflow_files
                mock_stage.assert_called_once()

                # Should have called git commit
                commit_calls = [
                    call_args
                    for call_args in mock_run.call_args_list
                    if "commit" in call_args[0][0]
                ]
                self.assertTrue(len(commit_calls) > 0)

    @patch("subprocess.run")
    def test_push_branch(self, mock_run):
        """Test pushing branch to remote."""

        # Mock upstream check to fail (no upstream set)
        def mock_run_side_effect(cmd, **kwargs):
            if "rev-parse" in cmd and "@{upstream}" in str(cmd):
                raise subprocess.CalledProcessError(1, cmd)
            return Mock()

        mock_run.side_effect = mock_run_side_effect

        result = self.git.push_branch("test-branch")

        self.assertTrue(result)

        # Should have called push with -u flag
        push_calls = [
            call_args
            for call_args in mock_run.call_args_list
            if "push" in call_args[0][0]
        ]
        self.assertTrue(len(push_calls) > 0)

        push_cmd = push_calls[0][0][0]
        self.assertIn("-u", push_cmd)
        self.assertIn("origin", push_cmd)
        self.assertIn("test-branch", push_cmd)

    def test_create_workflow_summary_commit(self):
        """Test creating workflow summary commit."""
        # Create completed workflow state
        workflow_state = WorkflowState("test_workflow")
        inputs = WorkflowInputs("Test project")
        workflow_state.set_inputs(inputs)

        # Complete all stages
        for stage_name in workflow_state.stages.keys():
            workflow_state.start_stage(stage_name)
            workflow_state.complete_stage(stage_name)

        with patch.object(self.git, "stage_workflow_files") as mock_stage:
            with patch.object(self.git, "_run_git_command") as mock_run:
                mock_stage.return_value = ["state_file.json"]

                # Mock git commands
                def mock_run_side_effect(cmd, **kwargs):
                    if "rev-parse" in cmd and "HEAD" in cmd:
                        return Mock(stdout="summary123\n")
                    return Mock()

                mock_run.side_effect = mock_run_side_effect

                commit_hash = self.git.create_workflow_summary_commit(workflow_state)

                # Should return commit hash
                self.assertEqual(commit_hash, "summary123")

                # Should have called stage_workflow_files
                mock_stage.assert_called_once()

                # Should have called git commit
                commit_calls = [
                    call_args
                    for call_args in mock_run.call_args_list
                    if "commit" in call_args[0][0]
                ]
                self.assertTrue(len(commit_calls) > 0)

                # Check commit message contains summary information
                commit_args = commit_calls[0][0][
                    0
                ]  # First call, first argument (the command list)
                # Find the commit message (after -m flag)
                message_idx = commit_args.index("-m") + 1
                commit_message = commit_args[message_idx]
                self.assertIn("Complete Enhanced Multi-Agent Workflow", commit_message)
                self.assertIn("Test project", commit_message)
                self.assertIn("Final Summary:", commit_message)


if __name__ == "__main__":
    unittest.main()
