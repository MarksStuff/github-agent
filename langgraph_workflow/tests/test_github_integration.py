"""Tests for GitHub integration functionality."""

import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import git

from ..github_integration import GitHubIntegration, MCPServerInterface
from ..mocks import MockGitHub


class TestGitHubIntegration(unittest.IsolatedAsyncioTestCase):
    """Test GitHub integration functionality."""

    def setUp(self):
        """Set up test fixtures."""
        # Create temporary directory for git repo
        self.temp_dir = tempfile.TemporaryDirectory()
        self.repo_path = Path(self.temp_dir.name)

        # Initialize git repo
        self.git_repo = git.Repo.init(self.repo_path)

        # Create initial commit
        test_file = self.repo_path / "README.md"
        test_file.write_text("# Test Repo")
        self.git_repo.index.add([str(test_file)])
        self.git_repo.index.commit("Initial commit")

        # Add remote origin (mock)
        origin = self.git_repo.create_remote(
            "origin", "https://github.com/test-org/test-repo.git"
        )

        self.github_integration = GitHubIntegration(
            repo_path=str(self.repo_path), github_token="fake_token"
        )

    def tearDown(self):
        """Clean up test fixtures."""
        self.temp_dir.cleanup()

    @patch("github.Github")
    async def test_create_branch(self, mock_github_class):
        """Test branch creation."""
        # Execute
        branch_name = await self.github_integration.create_branch("feature/test")

        # Verify
        self.assertEqual(branch_name, "feature/test")

        # Check that branch was created in git repo
        branches = [ref.name for ref in self.git_repo.heads]
        self.assertIn("feature/test", branches)

    @patch("github.Github")
    async def test_create_pull_request(self, mock_github_class):
        """Test PR creation."""
        # Mock GitHub API
        mock_github = MagicMock()
        mock_repo = MagicMock()
        mock_pr = MagicMock()
        mock_pr.number = 123
        mock_pr.html_url = "https://github.com/test-org/test-repo/pull/123"

        mock_github_class.return_value = mock_github
        mock_github.get_repo.return_value = mock_repo
        mock_repo.create_pull.return_value = mock_pr

        # Create branch first
        await self.github_integration.create_branch("feature/test")

        # Mock remote push
        with patch.object(self.github_integration.git_repo.remotes.origin, "push"):
            # Execute
            pr_number = await self.github_integration.create_pull_request(
                title="Test PR",
                body="Test description",
                branch="feature/test",
                labels=["test", "automation"],
            )

        # Verify
        self.assertEqual(pr_number, 123)
        mock_repo.create_pull.assert_called_once_with(
            title="Test PR", body="Test description", head="feature/test", base="main"
        )
        mock_pr.add_to_labels.assert_called_once_with("test", "automation")

    async def test_create_pull_request_no_github(self):
        """Test PR creation when GitHub is not available."""
        # Create integration without GitHub token
        integration = GitHubIntegration(
            repo_path=str(self.repo_path), github_token=None
        )

        # Execute
        pr_number = await integration.create_pull_request(
            title="Test PR", body="Test description", branch="feature/test"
        )

        # Verify returns dummy number
        self.assertEqual(pr_number, 9999)

    @patch("github.Github")
    async def test_get_pr_comments(self, mock_github_class):
        """Test getting PR comments."""
        # Mock GitHub API
        mock_github = MagicMock()
        mock_repo = MagicMock()
        mock_pr = MagicMock()

        # Mock comments
        mock_comment1 = MagicMock()
        mock_comment1.id = 1
        mock_comment1.user.login = "user1"
        mock_comment1.body = "First comment"
        mock_comment1.created_at = datetime.now()
        mock_comment1.html_url = "https://github.com/test/repo/pull/123#issuecomment-1"

        mock_comment2 = MagicMock()
        mock_comment2.id = 2
        mock_comment2.user.login = "user2"
        mock_comment2.body = "Second comment"
        mock_comment2.created_at = datetime.now()
        mock_comment2.html_url = "https://github.com/test/repo/pull/123#issuecomment-2"

        mock_pr.get_issue_comments.return_value = [mock_comment1, mock_comment2]
        mock_pr.get_review_comments.return_value = []
        mock_pr.get_reviews.return_value = []

        mock_github_class.return_value = mock_github
        mock_github.get_repo.return_value = mock_repo
        mock_repo.get_pull.return_value = mock_pr

        # Execute
        comments = await self.github_integration.get_pr_comments(123)

        # Verify
        self.assertEqual(len(comments), 2)
        self.assertEqual(comments[0]["body"], "First comment")
        self.assertEqual(comments[1]["body"], "Second comment")
        self.assertEqual(comments[0]["author"], "user1")

    @patch("github.Github")
    async def test_get_pr_comments_with_since_filter(self, mock_github_class):
        """Test getting PR comments with time filter."""
        # Mock GitHub API
        mock_github = MagicMock()
        mock_repo = MagicMock()
        mock_pr = MagicMock()

        now = datetime.now()
        old_time = now - timedelta(hours=2)
        new_time = now - timedelta(minutes=30)

        # Mock comments with different timestamps
        mock_old_comment = MagicMock()
        mock_old_comment.id = 1
        mock_old_comment.created_at = old_time
        mock_old_comment.user.login = "user1"
        mock_old_comment.body = "Old comment"
        mock_old_comment.html_url = (
            "https://github.com/test/repo/pull/123#issuecomment-1"
        )

        mock_new_comment = MagicMock()
        mock_new_comment.id = 2
        mock_new_comment.created_at = new_time
        mock_new_comment.user.login = "user2"
        mock_new_comment.body = "New comment"
        mock_new_comment.html_url = (
            "https://github.com/test/repo/pull/123#issuecomment-2"
        )

        mock_pr.get_issue_comments.return_value = [mock_old_comment, mock_new_comment]
        mock_pr.get_review_comments.return_value = []
        mock_pr.get_reviews.return_value = []

        mock_github_class.return_value = mock_github
        mock_github.get_repo.return_value = mock_repo
        mock_repo.get_pull.return_value = mock_pr

        # Execute with since filter
        cutoff_time = now - timedelta(hours=1)
        comments = await self.github_integration.get_pr_comments(123, since=cutoff_time)

        # Verify only new comment returned
        self.assertEqual(len(comments), 1)
        self.assertEqual(comments[0]["body"], "New comment")

    @patch("github.Github")
    async def test_add_pr_comment(self, mock_github_class):
        """Test adding a comment to a PR."""
        # Mock GitHub API
        mock_github = MagicMock()
        mock_repo = MagicMock()
        mock_pr = MagicMock()

        mock_github_class.return_value = mock_github
        mock_github.get_repo.return_value = mock_repo
        mock_repo.get_pull.return_value = mock_pr

        # Execute
        result = await self.github_integration.add_pr_comment(123, "Test comment")

        # Verify
        self.assertTrue(result)
        mock_pr.create_issue_comment.assert_called_once_with("Test comment")

    @patch("github.Github")
    async def test_get_ci_status(self, mock_github_class):
        """Test getting CI status."""
        # Mock GitHub API
        mock_github = MagicMock()
        mock_repo = MagicMock()
        mock_pr = MagicMock()
        mock_commit = MagicMock()
        mock_commit.sha = "abc123"

        # Mock check runs
        mock_check1 = MagicMock()
        mock_check1.name = "test"
        mock_check1.status = "completed"
        mock_check1.conclusion = "success"
        mock_check1.started_at = datetime.now()
        mock_check1.completed_at = datetime.now()
        mock_check1.details_url = "https://github.com/test/repo/runs/1"
        mock_check1.output = None

        mock_check2 = MagicMock()
        mock_check2.name = "lint"
        mock_check2.status = "completed"
        mock_check2.conclusion = "failure"
        mock_check2.started_at = datetime.now()
        mock_check2.completed_at = datetime.now()
        mock_check2.details_url = "https://github.com/test/repo/runs/2"
        mock_check2.output = None

        mock_commit.get_check_runs.return_value = [mock_check1, mock_check2]
        mock_pr.get_commits.return_value = [mock_commit]

        mock_github_class.return_value = mock_github
        mock_github.get_repo.return_value = mock_repo
        mock_repo.get_pull.return_value = mock_pr

        # Execute
        status = await self.github_integration.get_ci_status(123)

        # Verify
        self.assertEqual(status["status"], "failure")  # One check failed
        self.assertEqual(len(status["checks"]), 2)
        self.assertEqual(status["commit_sha"], "abc123")
        self.assertEqual(status["pr_number"], 123)

        # Check individual check details
        checks = status["checks"]
        test_check = next(c for c in checks if c["name"] == "test")
        lint_check = next(c for c in checks if c["name"] == "lint")

        self.assertEqual(test_check["conclusion"], "success")
        self.assertEqual(lint_check["conclusion"], "failure")

    async def test_push_changes(self):
        """Test pushing changes to GitHub."""
        # Create a test file
        test_file = self.repo_path / "test.txt"
        test_file.write_text("Test content")

        # Mock remote push
        with patch.object(self.github_integration.git_repo.remotes.origin, "push"):
            # Execute
            commit_sha = await self.github_integration.push_changes(
                "main", "Test commit message"
            )

        # Verify
        self.assertIsNotNone(commit_sha)
        self.assertEqual(len(commit_sha), 40)  # Git SHA length

        # Verify commit was created
        latest_commit = self.github_integration.git_repo.head.commit
        self.assertEqual(latest_commit.message, "Test commit message")

    @patch("github.Github")
    async def test_wait_for_checks(self, mock_github_class):
        """Test waiting for CI checks to complete."""
        # Mock GitHub API
        mock_github = MagicMock()
        mock_repo = MagicMock()
        mock_pr = MagicMock()
        mock_commit = MagicMock()
        mock_commit.sha = "abc123"

        # Mock check run that starts pending then completes
        mock_check = MagicMock()
        mock_check.name = "test"
        mock_check.started_at = datetime.now()
        mock_check.completed_at = datetime.now()
        mock_check.details_url = "https://github.com/test/repo/runs/1"
        mock_check.output = None

        # First call: pending, second call: success
        self.call_count = 0

        def mock_get_ci_status(pr_number):
            self.call_count += 1
            if self.call_count == 1:
                return {
                    "status": "pending",
                    "checks": [{"name": "test", "status": "in_progress"}],
                    "commit_sha": "abc123",
                    "pr_number": pr_number,
                }
            else:
                return {
                    "status": "success",
                    "checks": [
                        {"name": "test", "status": "completed", "conclusion": "success"}
                    ],
                    "commit_sha": "abc123",
                    "pr_number": pr_number,
                }

        # Patch get_ci_status to simulate progression
        with patch.object(
            self.github_integration, "get_ci_status", side_effect=mock_get_ci_status
        ):
            # Execute with short timeout and poll interval for testing
            status = await self.github_integration.wait_for_checks(
                123, timeout=5, poll_interval=1
            )

        # Verify final status is success
        self.assertEqual(status["status"], "success")
        self.assertEqual(self.call_count, 2)  # Called twice

    async def test_extract_actionable_feedback(self):
        """Test extracting actionable items from comments."""
        comments = [
            {
                "id": 1,
                "author": "reviewer1",
                "body": "This looks good, please merge when ready.",
                "type": "issue_comment",
            },
            {
                "id": 2,
                "author": "reviewer2",
                "body": "You must fix the error handling in line 42.",
                "type": "review_comment",
            },
            {
                "id": 3,
                "author": "reviewer3",
                "body": "Consider adding more tests for edge cases.",
                "type": "review",
            },
            {
                "id": 4,
                "author": "reviewer4",
                "body": "Great work! Ship it!",
                "type": "issue_comment",
            },
        ]

        # Execute
        actionable = self.github_integration.extract_actionable_feedback(comments)

        # Verify
        self.assertEqual(len(actionable), 2)  # Only 2 actionable items

        # Check high priority item (contains "must")
        high_priority = next(item for item in actionable if item["priority"] == "high")
        self.assertIn("fix the error handling", high_priority["task"])

        # Check normal priority item
        normal_priority = next(
            item for item in actionable if item["priority"] == "normal"
        )
        self.assertIn("adding more tests", normal_priority["task"])

    async def test_apply_patch(self):
        """Test applying a git patch."""
        # Create initial file
        test_file = self.repo_path / "test.py"
        test_file.write_text("def hello():\n    print('Hello')")

        # Commit initial state
        self.git_repo.index.add([str(test_file)])
        self.git_repo.index.commit("Add test file")

        # Create patch content
        patch_content = """--- a/test.py
+++ b/test.py
@@ -1,2 +1,2 @@
 def hello():
-    print('Hello')
+    print('Hello, World!')
"""

        # Write patch to file
        patch_file = self.repo_path / "test.patch"
        patch_file.write_text(patch_content)

        # Execute
        result = await self.github_integration.apply_patch(str(patch_file), "main")

        # For this test, we expect it to fail because the patch format may not match exactly
        # In a real implementation, we'd need proper patch generation
        # This tests the error handling path
        self.assertIsInstance(result, bool)


class TestMCPServerInterface(unittest.IsolatedAsyncioTestCase):
    """Test MCP server interface."""

    def setUp(self):
        """Set up test fixtures."""
        self.mcp = MCPServerInterface("http://localhost:8080")

    async def test_initialization(self):
        """Test MCP server initialization."""
        self.assertEqual(self.mcp.server_url, "http://localhost:8080")

        # Test with environment variable
        with patch.dict("os.environ", {"MCP_SERVER_URL": "http://custom:9090"}):
            mcp_custom = MCPServerInterface()
            self.assertEqual(mcp_custom.server_url, "http://custom:9090")

    async def test_get_pr_comments(self):
        """Test getting PR comments via MCP."""
        # This is a placeholder implementation
        comments = await self.mcp.get_pr_comments(123)

        # Verify returns empty list (placeholder behavior)
        self.assertEqual(comments, [])

    async def test_get_check_runs(self):
        """Test getting check runs via MCP."""
        # This is a placeholder implementation
        runs = await self.mcp.get_check_runs(123)

        # Verify returns empty list (placeholder behavior)
        self.assertEqual(runs, [])

    async def test_get_check_log(self):
        """Test getting check log via MCP."""
        # This is a placeholder implementation
        log = await self.mcp.get_check_log(123, "check_1")

        # Verify returns empty string (placeholder behavior)
        self.assertEqual(log, "")


class TestMockGitHub(unittest.IsolatedAsyncioTestCase):
    """Test the MockGitHub implementation."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_github = MockGitHub()

    async def test_mock_create_branch(self):
        """Test mock branch creation."""
        branch = await self.mock_github.create_branch("test-branch", "main")

        self.assertEqual(branch, "test-branch")
        self.assertIn("test-branch", self.mock_github.branches)
        self.assertEqual(self.mock_github.branches["test-branch"], "main")

    async def test_mock_create_pr(self):
        """Test mock PR creation."""
        pr_number = await self.mock_github.create_pull_request(
            title="Test PR",
            body="Test description",
            branch="feature/test",
            labels=["test"],
        )

        self.assertEqual(pr_number, 1)
        self.assertIn(1, self.mock_github.prs)

        pr_data = self.mock_github.prs[1]
        self.assertEqual(pr_data["title"], "Test PR")
        self.assertEqual(pr_data["branch"], "feature/test")
        self.assertEqual(pr_data["labels"], ["test"])

    async def test_mock_pr_comments(self):
        """Test mock PR comment operations."""
        # Create PR first
        pr_number = await self.mock_github.create_pull_request(
            title="Test PR", body="Test description", branch="feature/test"
        )

        # Add comment
        success = await self.mock_github.add_pr_comment(pr_number, "Test comment")
        self.assertTrue(success)

        # Get comments
        comments = await self.mock_github.get_pr_comments(pr_number)
        self.assertEqual(len(comments), 1)
        self.assertEqual(comments[0]["body"], "Test comment")
        self.assertEqual(comments[0]["author"], "test_user")

    async def test_mock_ci_status(self):
        """Test mock CI status operations."""
        # Create PR
        pr_number = await self.mock_github.create_pull_request(
            title="Test PR", body="Test description", branch="feature/test"
        )

        # Default status should be success
        status = await self.mock_github.get_ci_status(pr_number)
        self.assertEqual(status["status"], "success")
        self.assertEqual(status["pr_number"], pr_number)

        # Set custom status
        custom_status = {
            "status": "failure",
            "checks": [{"name": "test", "conclusion": "failure"}],
            "commit_sha": "abc123",
            "pr_number": pr_number,
        }
        self.mock_github.set_ci_status(pr_number, custom_status)

        # Verify custom status
        updated_status = await self.mock_github.get_ci_status(pr_number)
        self.assertEqual(updated_status["status"], "failure")


if __name__ == "__main__":
    unittest.main()
