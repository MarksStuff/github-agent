#!/usr/bin/env python3
"""
Tests for GitHub Integration Module in Enhanced Multi-Agent Workflow System
"""

import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import requests_mock

from multi_agent_workflow.github_integrator import (
    ConventionalCommitGenerator,
    GitHubComment,
    GitHubIntegrator,
    PullRequest,
)
from multi_agent_workflow.workflow_state import WorkflowInputs, WorkflowState


class TestGitHubComment:
    """Test GitHubComment functionality."""

    def test_comment_creation(self):
        """Test creating a GitHub comment."""
        comment = GitHubComment(
            id=123,
            author="test_user",
            body="This looks great! @workflow approve",
            created_at=datetime.now(),
            updated_at=datetime.now(),
            url="https://github.com/owner/repo/issues/1#issuecomment-123",
        )

        assert comment.id == 123
        assert comment.author == "test_user"
        assert "@workflow approve" in comment.body
        assert comment.url.endswith("123")

    def test_parse_workflow_commands(self):
        """Test parsing workflow commands from comments."""
        # Test explicit workflow commands
        comment = GitHubComment(
            id=1,
            author="user1",
            body="Please @workflow pause this until we review. Also @workflow resume testing",
            created_at=datetime.now(),
            updated_at=datetime.now(),
            url="https://example.com",
        )

        commands = comment.parse_workflow_commands()
        assert "pause" in commands
        assert "resume testing" in commands

    def test_parse_approval_commands(self):
        """Test parsing approval/rejection commands."""
        # Test approval
        approval_comment = GitHubComment(
            id=2,
            author="maintainer",
            body="LGTM! This looks good to merge.",
            created_at=datetime.now(),
            updated_at=datetime.now(),
            url="https://example.com",
        )

        commands = approval_comment.parse_workflow_commands()
        assert "approve" in commands

        # Test rejection
        rejection_comment = GitHubComment(
            id=3,
            author="reviewer",
            body="Changes requested - this needs more work.",
            created_at=datetime.now(),
            updated_at=datetime.now(),
            url="https://example.com",
        )

        commands = rejection_comment.parse_workflow_commands()
        assert "reject" in commands


class TestPullRequest:
    """Test PullRequest functionality."""

    def test_from_github_api(self):
        """Test creating PullRequest from GitHub API data."""
        pr_data = {
            "number": 42,
            "title": "Add new feature",
            "body": "This PR adds a new feature",
            "state": "open",
            "user": {"login": "contributor"},
            "head": {"ref": "feature-branch"},
            "base": {"ref": "main"},
            "html_url": "https://github.com/owner/repo/pull/42",
            "created_at": "2023-01-01T12:00:00Z",
            "updated_at": "2023-01-01T13:00:00Z",
            "mergeable": True,
            "comments": 5,
        }

        pr = PullRequest.from_github_api(pr_data)

        assert pr.number == 42
        assert pr.title == "Add new feature"
        assert pr.author == "contributor"
        assert pr.branch == "feature-branch"
        assert pr.target_branch == "main"
        assert pr.comments_count == 5


class TestConventionalCommitGenerator:
    """Test conventional commit message generation."""

    def test_basic_commit_message(self):
        """Test basic commit message generation."""
        state = WorkflowState("test_workflow")
        state.inputs = WorkflowInputs(
            project_description="Web application for task management",
            target_directory="/tmp/test",
        )

        result = {"output_files": ["requirements.md", "api_spec.yaml"]}

        commit_msg = ConventionalCommitGenerator.generate_commit_message(
            "requirements_analysis", result, state
        )

        assert commit_msg.startswith("feat(web): analyze project requirements")
        assert "requirements.md" in commit_msg
        assert "api_spec.yaml" in commit_msg

    def test_commit_with_metrics(self):
        """Test commit message with metrics."""
        state = WorkflowState("test_workflow")
        state.inputs = WorkflowInputs(
            project_description="CLI tool for developers",
            target_directory="/tmp/test",
        )

        # Complete some stages to show progress
        state.start_stage("requirements_analysis")
        state.complete_stage("requirements_analysis")

        result = {
            "output_files": ["design.md"],
            "metrics": {"components_designed": 5, "interfaces_defined": 3},
        }

        commit_msg = ConventionalCommitGenerator.generate_commit_message(
            "architecture_design", result, state
        )

        assert "feat(cli):" in commit_msg
        assert "Components Designed: 5" in commit_msg
        assert "Interfaces Defined: 3" in commit_msg
        assert "1/6 stages complete" in commit_msg

    def test_scope_extraction(self):
        """Test scope extraction from project descriptions."""
        # Test web scope
        web_state = WorkflowState("web_test")
        web_state.inputs = WorkflowInputs(
            project_description="Frontend web application with React",
            target_directory="/tmp/test",
        )

        scope = ConventionalCommitGenerator._extract_scope_from_state(web_state)
        assert scope == "web"

        # Test API scope
        api_state = WorkflowState("api_test")
        api_state.inputs = WorkflowInputs(
            project_description="RESTful API backend service",
            target_directory="/tmp/test",
        )

        scope = ConventionalCommitGenerator._extract_scope_from_state(api_state)
        assert scope == "api"

    def test_breaking_changes(self):
        """Test commit message with breaking changes."""
        state = WorkflowState("test_workflow")
        state.inputs = WorkflowInputs(
            project_description="API service",
            target_directory="/tmp/test",
        )

        result = {
            "output_files": ["api.yaml"],
            "breaking_changes": [
                "Changed authentication method",
                "Removed deprecated endpoints",
            ],
        }

        commit_msg = ConventionalCommitGenerator.generate_commit_message(
            "architecture_design", result, state, include_breaking_changes=True
        )

        assert "BREAKING CHANGE:" in commit_msg
        assert "Changed authentication method" in commit_msg
        assert "Removed deprecated endpoints" in commit_msg


class TestGitHubIntegrator:
    """Test GitHub integration functionality."""

    def test_initialization_with_params(self):
        """Test initializing with explicit parameters."""
        with patch("multi_agent_workflow.github_integrator.GitIntegrator"):
            integrator = GitHubIntegrator(
                repo_path=Path("/tmp/test"),
                github_token="test_token",
                repo_owner="test_owner",
                repo_name="test_repo",
            )

            assert integrator.repo_owner == "test_owner"
            assert integrator.repo_name == "test_repo"
            assert integrator.github_token == "test_token"
            assert (
                integrator.base_url
                == "https://api.github.com/repos/test_owner/test_repo"
            )

    def test_extract_repo_info_ssh(self):
        """Test extracting repository info from SSH remote."""
        with patch("multi_agent_workflow.github_integrator.GitIntegrator") as mock_git:
            mock_git.return_value._run_git_command.return_value.stdout = (
                "git@github.com:owner/repo.git"
            )

            integrator = GitHubIntegrator()
            assert integrator.repo_owner == "owner"
            assert integrator.repo_name == "repo"

    def test_extract_repo_info_https(self):
        """Test extracting repository info from HTTPS remote."""
        with patch("multi_agent_workflow.github_integrator.GitIntegrator") as mock_git:
            mock_git.return_value._run_git_command.return_value.stdout = (
                "https://github.com/owner/repo.git"
            )

            integrator = GitHubIntegrator()
            assert integrator.repo_owner == "owner"
            assert integrator.repo_name == "repo"

    @patch("multi_agent_workflow.github_integrator.GitIntegrator")
    def test_create_enhanced_commit(self, mock_git):
        """Test creating enhanced commits."""
        mock_git.return_value._run_git_command.side_effect = [
            MagicMock(stdout="git@github.com:owner/repo.git"),  # remote get-url
            MagicMock(),  # git add
            MagicMock(),  # git commit
            MagicMock(stdout="abc123def456"),  # git rev-parse HEAD
        ]

        integrator = GitHubIntegrator()

        state = WorkflowState("test_workflow")
        state.inputs = WorkflowInputs(
            project_description="Test project",
            target_directory="/tmp/test",
        )

        result = {"output_files": ["test.py"]}

        commit_hash = integrator.create_enhanced_commit("testing", result, state)

        assert commit_hash == "abc123def456"
        assert mock_git.return_value._run_git_command.call_count == 4

    @requests_mock.Mocker()
    def test_create_pull_request(self, m):
        """Test creating a pull request."""
        with patch("multi_agent_workflow.github_integrator.GitIntegrator") as mock_git:
            mock_git.return_value._run_git_command.side_effect = [
                MagicMock(stdout="git@github.com:owner/repo.git"),  # remote get-url
                MagicMock(stdout="feature-branch"),  # current branch
            ]

            # Mock GitHub API response
            pr_response = {
                "number": 123,
                "title": "Test PR",
                "body": "Test body",
                "state": "open",
                "user": {"login": "test_user"},
                "head": {"ref": "feature-branch"},
                "base": {"ref": "main"},
                "html_url": "https://github.com/owner/repo/pull/123",
                "created_at": "2023-01-01T12:00:00Z",
                "updated_at": "2023-01-01T12:00:00Z",
                "mergeable": True,
            }

            m.post("https://api.github.com/repos/owner/repo/pulls", json=pr_response)

            integrator = GitHubIntegrator(github_token="test_token")

            state = WorkflowState("test_workflow")
            state.inputs = WorkflowInputs(
                project_description="Test project",
                target_directory="/tmp/test",
            )

            pr = integrator.create_pull_request("workflow_123", state)

            assert pr is not None
            assert pr.number == 123
            assert pr.workflow_id == "workflow_123"

    @requests_mock.Mocker()
    def test_poll_comments(self, m):
        """Test polling for GitHub comments."""
        with patch("multi_agent_workflow.github_integrator.GitIntegrator") as mock_git:
            mock_git.return_value._run_git_command.return_value.stdout = (
                "git@github.com:owner/repo.git"
            )

            # Mock GitHub API response
            comments_response = [
                {
                    "id": 1,
                    "user": {"login": "reviewer"},
                    "body": "This looks good! LGTM",
                    "created_at": "2023-01-01T12:00:00Z",
                    "updated_at": "2023-01-01T12:00:00Z",
                    "html_url": "https://github.com/owner/repo/issues/1#issuecomment-1",
                },
                {
                    "id": 2,
                    "user": {"login": "contributor"},
                    "body": "@workflow pause - need to review this",
                    "created_at": "2023-01-01T12:30:00Z",
                    "updated_at": "2023-01-01T12:30:00Z",
                    "html_url": "https://github.com/owner/repo/issues/1#issuecomment-2",
                },
            ]

            m.get(
                "https://api.github.com/repos/owner/repo/issues/1/comments",
                json=comments_response,
            )

            integrator = GitHubIntegrator(github_token="test_token")
            comments = integrator.poll_comments(1)

            assert len(comments) == 2
            assert comments[0].author == "reviewer"
            assert "approve" in comments[0].workflow_commands
            assert comments[1].author == "contributor"
            assert "pause" in comments[1].workflow_commands

    @requests_mock.Mocker()
    def test_process_feedback(self, m):
        """Test processing comments into feedback."""
        with patch("multi_agent_workflow.github_integrator.GitIntegrator") as mock_git:
            mock_git.return_value._run_git_command.return_value.stdout = (
                "git@github.com:owner/repo.git"
            )

            integrator = GitHubIntegrator(github_token="test_token")

            # Create test comments
            comments = [
                GitHubComment(
                    id=1,
                    author="reviewer",
                    body="LGTM! This looks great.",
                    created_at=datetime.now(),
                    updated_at=datetime.now(),
                    url="https://example.com/1",
                    workflow_commands=["approve"],
                ),
                GitHubComment(
                    id=2,
                    author="contributor",
                    body="@workflow pause testing",
                    created_at=datetime.now(),
                    updated_at=datetime.now(),
                    url="https://example.com/2",
                    workflow_commands=["pause testing"],
                ),
            ]

            feedback_list = integrator.process_feedback(comments, pr_number=1)

            assert len(feedback_list) == 2
            assert feedback_list[0].feedback_type == "approve"
            assert feedback_list[0].author == "reviewer"
            assert feedback_list[1].feedback_type == "pause testing"
            assert feedback_list[1].stage_name == "testing"

    @requests_mock.Mocker()
    def test_post_comment(self, m):
        """Test posting a comment to GitHub."""
        with patch("multi_agent_workflow.github_integrator.GitIntegrator") as mock_git:
            mock_git.return_value._run_git_command.return_value.stdout = (
                "git@github.com:owner/repo.git"
            )

            # Mock GitHub API response
            comment_response = {
                "id": 123,
                "user": {"login": "bot"},
                "body": "Workflow paused successfully",
                "created_at": "2023-01-01T12:00:00Z",
                "updated_at": "2023-01-01T12:00:00Z",
                "html_url": "https://github.com/owner/repo/issues/1#issuecomment-123",
            }

            m.post(
                "https://api.github.com/repos/owner/repo/issues/1/comments",
                json=comment_response,
            )

            integrator = GitHubIntegrator(github_token="test_token")
            comment = integrator.post_comment(1, "Workflow paused successfully")

            assert comment is not None
            assert comment.id == 123
            assert comment.body == "Workflow paused successfully"

    def test_pr_body_generation(self):
        """Test generating PR body from workflow state."""
        with patch("multi_agent_workflow.github_integrator.GitIntegrator") as mock_git:
            mock_git.return_value._run_git_command.return_value.stdout = (
                "git@github.com:owner/repo.git"
            )

            integrator = GitHubIntegrator()

            # Create a workflow state with some completed stages
            state = WorkflowState("test_workflow")
            state.inputs = WorkflowInputs(
                project_description="Test project for PR",
                target_directory="/tmp/test",
            )

            # Complete a few stages
            state.start_stage("requirements_analysis")
            state.complete_stage(
                "requirements_analysis", output_files=["requirements.md"]
            )

            state.start_stage("architecture_design")
            state.complete_stage(
                "architecture_design", output_files=["design.md", "api.yaml"]
            )

            body = integrator._generate_pr_body(state)

            assert "Enhanced Multi-Agent Workflow" in body
            assert "test_workflow" in body
            assert "Test project for PR" in body
            assert "requirements.md" in body
            assert "design.md" in body
            assert "@workflow pause" in body
            assert "@workflow resume" in body

    def test_extract_requested_changes(self):
        """Test extracting requested changes from rejection comments."""
        with patch("multi_agent_workflow.github_integrator.GitIntegrator") as mock_git:
            mock_git.return_value._run_git_command.return_value.stdout = (
                "git@github.com:owner/repo.git"
            )

            integrator = GitHubIntegrator()

            comment_body = """
            Changes requested:
            - Add more unit tests for the API endpoints
            - Fix the error handling in the authentication module
            - Update the documentation to reflect the new changes
            - Remove the deprecated functions
            """

            changes = integrator._extract_requested_changes(comment_body)

            assert "testing" in changes
            assert "bug_fixes" in changes
            assert "documentation" in changes
            assert "general" in changes

    def test_get_stage_files(self):
        """Test getting files to stage for commits."""
        with patch("multi_agent_workflow.github_integrator.GitIntegrator") as mock_git:
            mock_git.return_value._run_git_command.return_value.stdout = (
                "git@github.com:owner/repo.git"
            )

            integrator = GitHubIntegrator()

            with tempfile.TemporaryDirectory() as tmpdir:
                # Create some test files
                test_file = Path(tmpdir) / "test_output.py"
                test_file.write_text("# Test file")

                result = {"output_files": [str(test_file)]}

                files = integrator._get_stage_files("testing", result)

                assert len(files) >= 1
                assert test_file in files
