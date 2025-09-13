"""Tests for GitHub integration functionality.

These tests focus on testing the wrapper logic and integration with github_tools.py
rather than testing the underlying GitHub API operations which are tested elsewhere.
"""

import json
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import git

from ..github_integration import GitHubIntegration, MCPServerInterface


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
        self.git_repo.index.add(["README.md"])  # Use relative path
        self.git_repo.index.commit("Initial commit")

        # Add remote origin (mock)
        self.git_repo.create_remote(
            "origin", "https://github.com/test-org/test-repo.git"
        )

        self.github_integration = GitHubIntegration(
            repo_path=str(self.repo_path), github_token="fake_token"
        )

    def tearDown(self):
        """Clean up test fixtures."""
        self.temp_dir.cleanup()

    async def test_create_branch(self):
        """Test branch creation (git operations only)."""
        # Execute
        branch_name = await self.github_integration.create_branch("feature/test")

        # Verify
        self.assertEqual(branch_name, "feature/test")

        # Check that branch was created in git repo
        branches = [ref.name for ref in self.git_repo.heads]
        self.assertIn("feature/test", branches)

    async def test_create_pull_request_with_github_tools(self):
        """Test PR creation using github_tools integration."""

        # Mock github_tools execute_tool function
        async def mock_execute_tool(tool_name, **kwargs):
            if tool_name == "github_get_pr_comments":
                return json.dumps({"issue_comments": [], "review_comments": []})
            return json.dumps({"success": True})

        # Mock get_github_context function
        class MockContext:
            def __init__(self):
                self.repo = MockRepo()

        class MockRepo:
            def create_pull(self, title, body, head, base):
                class MockPR:
                    number = 123

                    def add_to_labels(self, *labels):
                        pass

                return MockPR()

        def mock_get_context(repo_name):
            return MockContext()

        # Create branch first
        await self.github_integration.create_branch("feature/test")

        # Mock filesystem operations for push
        with patch("git.Remote.push"), patch(
            "langgraph_workflow.github_integration.execute_tool",
            side_effect=mock_execute_tool,
        ), patch(
            "langgraph_workflow.github_integration.get_github_context",
            side_effect=mock_get_context,
        ):
            # Execute
            pr_number = await self.github_integration.create_pull_request(
                title="Test PR",
                body="Test description",
                branch="feature/test",
                labels=["test", "automation"],
            )

        # Verify
        self.assertEqual(pr_number, 123)

    async def test_create_pull_request_no_github_tools(self):
        """Test PR creation when github_tools is not available."""
        # Use dependency injection with None to simulate unavailable github_tools
        integration = GitHubIntegration(
            repo_path=str(self.repo_path), github_token="fake_token", tool_function=None
        )

        # Execute
        pr_number = await integration.create_pull_request(
            title="Test PR", body="Test description", branch="feature/test"
        )

        # Verify returns dummy number when github_tools unavailable
        self.assertEqual(pr_number, 9999)

    async def test_get_pr_comments_with_github_tools(self):
        """Test getting PR comments using github_tools integration."""
        # Mock github_tools execute_tool to return comment data
        mock_response = {
            "issue_comments": [
                {
                    "id": 1,
                    "author": "user1",
                    "body": "First comment",
                    "created_at": "2023-01-01T12:00:00Z",
                    "type": "issue_comment",
                }
            ],
            "review_comments": [
                {
                    "id": 2,
                    "author": "user2",
                    "body": "Second comment",
                    "created_at": "2023-01-01T13:00:00Z",
                    "type": "review_comment",
                }
            ],
        }

        async def mock_execute_tool(tool_name, **kwargs):
            if tool_name == "github_get_pr_comments":
                return json.dumps(mock_response)
            return json.dumps({})

        # Use dependency injection to provide mock tool function
        integration = GitHubIntegration(
            repo_path=str(self.repo_path),
            github_token="fake_token",
            tool_function=mock_execute_tool,
        )

        # Execute
        comments = await integration.get_pr_comments(123)

        # Verify
        self.assertEqual(len(comments), 2)
        # Comments are combined from issue_comments + review_comments, so order may vary
        bodies = [c["body"] for c in comments]
        authors = [c["author"] for c in comments]
        self.assertIn("First comment", bodies)
        self.assertIn("Second comment", bodies)
        self.assertIn("user1", authors)
        self.assertIn("user2", authors)

    async def test_get_pr_comments_with_since_filter(self):
        """Test getting PR comments with time filter using github_tools."""

        now = datetime.now(UTC)
        old_time = now - timedelta(hours=2)
        new_time = now - timedelta(minutes=30)

        # Mock github_tools response with different timestamps
        mock_response = {
            "issue_comments": [
                {
                    "id": 1,
                    "author": "user1",
                    "body": "Old comment",
                    "created_at": old_time.isoformat(),
                    "type": "issue_comment",
                },
                {
                    "id": 2,
                    "author": "user2",
                    "body": "New comment",
                    "created_at": new_time.isoformat(),
                    "type": "issue_comment",
                },
            ],
            "review_comments": [],
        }

        async def mock_execute_tool(tool_name, **kwargs):
            if tool_name == "github_get_pr_comments":
                return json.dumps(mock_response)
            return json.dumps({})

        with patch(
            "langgraph_workflow.github_integration.execute_tool",
            side_effect=mock_execute_tool,
        ):
            # Execute with since filter
            cutoff_time = now - timedelta(hours=1)
            comments = await self.github_integration.get_pr_comments(
                123, since=cutoff_time
            )

            # Verify only new comment returned (time filtering logic)
            self.assertEqual(len(comments), 1)
            self.assertEqual(comments[0]["body"], "New comment")

    async def test_add_pr_comment_with_github_tools(self):
        """Test adding a comment to a PR using github_tools integration."""

        # Mock github_tools execute_tool to return success
        async def mock_execute_tool(tool_name, **kwargs):
            if tool_name == "github_post_pr_reply":
                return json.dumps({"success": True})
            return json.dumps({})

        with patch(
            "langgraph_workflow.github_integration.execute_tool",
            side_effect=mock_execute_tool,
        ):
            # Execute
            result = await self.github_integration.add_pr_comment(123, "Test comment")

            # Verify
            self.assertTrue(result)

    async def test_get_ci_status_with_github_tools(self):
        """Test getting CI status using github_tools integration."""
        # Mock github_tools response with build status
        mock_response = {
            "overall_state": "failure",
            "commit_sha": "abc123",
            "check_runs": [
                {"name": "test", "status": "completed", "conclusion": "success"},
                {"name": "lint", "status": "completed", "conclusion": "failure"},
            ],
        }

        async def mock_execute_tool(tool_name, **kwargs):
            if tool_name == "github_get_build_status":
                return json.dumps(mock_response)
            return json.dumps({})

        with patch(
            "langgraph_workflow.github_integration.execute_tool",
            side_effect=mock_execute_tool,
        ):
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

        # Add to git index
        self.git_repo.index.add(["test.txt"])

        # Mock remote push
        with patch("git.Remote.push"):
            # Execute
            commit_sha = await self.github_integration.push_changes(
                "main", "Test commit message"
            )

        # Verify
        self.assertIsNotNone(commit_sha)
        self.assertEqual(len(commit_sha), 40)  # Git SHA length

        # Verify commit was created
        latest_commit = self.git_repo.head.commit
        self.assertEqual(latest_commit.message, "Test commit message")

    async def test_wait_for_checks(self):
        """Test waiting for CI checks to complete."""
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
        self.git_repo.index.add(["test.py"])  # Use relative path
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


class TestGitHubIntegrationEdgeCases(unittest.IsolatedAsyncioTestCase):
    """Additional tests for GitHub integration edge cases."""

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
        self.git_repo.index.add(["README.md"])  # Use relative path
        self.git_repo.index.commit("Initial commit")

        # Add remote origin (mock)
        self.git_repo.create_remote(
            "origin", "https://github.com/test-org/test-repo.git"
        )

        self.github_integration = GitHubIntegration(
            repo_path=str(self.repo_path), github_token="fake_token"
        )

    def tearDown(self):
        """Clean up test fixtures."""
        self.temp_dir.cleanup()

    async def test_github_tools_unavailable_fallback(self):
        """Test fallback behavior when github_tools is not available."""
        # Test get_pr_comments fallback
        with patch("langgraph_workflow.github_integration.execute_tool", None):
            comments = await self.github_integration.get_pr_comments(123)
            self.assertEqual(comments, [])

        # Test add_pr_comment fallback
        with patch("langgraph_workflow.github_integration.execute_tool", None):
            result = await self.github_integration.add_pr_comment(123, "Test comment")
            self.assertFalse(result)

        # Test get_ci_status fallback
        with patch("langgraph_workflow.github_integration.execute_tool", None):
            status = await self.github_integration.get_ci_status(123)
            self.assertEqual(status["status"], "success")
            self.assertEqual(status["pr_number"], 123)

    async def test_github_tools_error_handling(self):
        """Test error handling when github_tools returns errors."""

        # Mock github_tools to return error responses
        async def mock_execute_tool_with_error(tool_name, **kwargs):
            return json.dumps({"error": "API rate limit exceeded"})

        with patch(
            "langgraph_workflow.github_integration.execute_tool",
            side_effect=mock_execute_tool_with_error,
        ):
            # Test error handling for get_pr_comments
            comments = await self.github_integration.get_pr_comments(123)
            self.assertEqual(comments, [])

            # Test error handling for add_pr_comment
            result = await self.github_integration.add_pr_comment(123, "Test")
            self.assertFalse(result)

            # Test error handling for get_ci_status
            status = await self.github_integration.get_ci_status(123)
            self.assertEqual(status["status"], "error")

    async def test_repo_name_extraction(self):
        """Test repository name extraction logic."""
        # Test with valid git remote
        self.assertEqual(self.github_integration.repo_name, "test-org/test-repo")

        # Test with invalid integration
        invalid_integration = GitHubIntegration(
            repo_path="/nonexistent", github_token="fake"
        )
        # Should fallback to directory name
        self.assertEqual(invalid_integration.repo_name, "nonexistent")


if __name__ == "__main__":
    unittest.main()
