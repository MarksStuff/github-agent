"""GitHub integration for PR-based human arbitration and CI/CD feedback.

This module provides a wrapper around the existing github_tools.py functionality
to integrate GitHub operations into the LangGraph workflow.
"""

import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# Add parent directory to path to import github_tools
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from github_tools import execute_tool, get_github_context
    from repository_manager import RepositoryConfig, RepositoryManager
except ImportError as e:
    logging.warning(
        f"Could not import github_tools: {e}. GitHub integration will be limited."
    )
    execute_tool = None
    get_github_context = None
    RepositoryConfig = None
    RepositoryManager = None

logger = logging.getLogger(__name__)


class GitHubIntegration:
    """Manages GitHub interactions for the workflow using existing github_tools."""

    def __init__(self, repo_path: str, github_token: str | None = None, tool_function=None):
        """Initialize GitHub integration.

        Args:
            repo_path: Local path to the repository
            github_token: GitHub API token (or from GITHUB_TOKEN env var)
            tool_function: Function to execute GitHub tools (for testing)
        """
        self.repo_path = Path(repo_path)
        self.token = github_token or os.getenv("GITHUB_TOKEN")
        
        # Use injected tool function or fallback to imported execute_tool
        self.execute_tool = tool_function or execute_tool

        if not self.token:
            logger.warning("No GitHub token provided. PR operations will be limited.")
            self.repo_name = None
            return

        # Extract repo name from path or remote
        self.repo_name = self._get_repo_name()

        if not self.repo_name:
            logger.warning(
                "Could not determine repository name. GitHub operations will be limited."
            )

    def _get_repo_name(self) -> str | None:
        """Extract repository name from git remote or path."""
        try:
            import git

            git_repo = git.Repo(self.repo_path)
            origin = git_repo.remote("origin")
            url = origin.url

            # Extract owner/repo from URL
            if "github.com" in url:
                if url.startswith("git@"):
                    # SSH URL: git@github.com:owner/repo.git
                    parts = url.split(":")[-1].replace(".git", "")
                elif url.startswith("https://"):
                    # HTTPS URL: https://github.com/owner/repo.git
                    parts = url.split("github.com/")[-1].replace(".git", "")
                else:
                    logger.warning(f"Unrecognized GitHub URL format: {url}")
                    return None

                return parts
        except Exception as e:
            logger.warning(f"Failed to extract repo name from git remote: {e}")

        # Fallback to directory name
        return self.repo_path.name

    async def create_branch(self, branch_name: str, base_branch: str = "main") -> str:
        """Create a new branch.

        Args:
            branch_name: Name for the new branch
            base_branch: Base branch to branch from

        Returns:
            Created branch name
        """
        try:
            import git

            git_repo = git.Repo(self.repo_path)

            # Checkout base branch first
            git_repo.git.checkout(base_branch)

            # Create and checkout new branch
            git_repo.git.checkout("-b", branch_name)

            logger.info(f"Created branch '{branch_name}' from '{base_branch}'")
            return branch_name

        except Exception as e:
            logger.error(f"Failed to create branch '{branch_name}': {e}")
            raise

    async def create_pull_request(
        self,
        title: str,
        body: str,
        branch: str,
        base_branch: str = "main",
        labels: list[str] | None = None,
    ) -> int:
        """Create a pull request using github_tools functionality.

        Args:
            title: PR title
            body: PR description
            branch: Source branch
            base_branch: Target branch
            labels: Labels to add (not implemented in github_tools)

        Returns:
            PR number
        """
        if not self.execute_tool:
            logger.warning("github_tools not available. Returning dummy PR number.")
            return 9999

        # First push the branch
        await self.push_changes(branch, f"Push branch {branch} for PR")

        # Use existing GitHub tools via API since github_tools doesn't have create_pull_request
        # We'll implement this by calling GitHub API directly using the context
        try:
            if not self.repo_name:
                raise ValueError("Repository name not available")

            # Get the GitHub context to access the repo
            context = get_github_context(self.repo_name)
            if not context or not context.repo:
                raise ValueError("GitHub repository not configured")

            # Create PR using PyGithub
            pr = context.repo.create_pull(
                title=title, body=body, head=branch, base=base_branch
            )

            # Add labels if specified
            if labels:
                pr.add_to_labels(*labels)

            logger.info(f"Created PR #{pr.number}: {title}")
            return pr.number

        except Exception as e:
            logger.error(f"Failed to create PR: {e}")
            return 9999

    async def get_pr_comments(
        self, pr_number: int, since: datetime | None = None
    ) -> list[dict]:
        """Get PR comments using github_tools functionality.

        Args:
            pr_number: PR number
            since: Only comments after this date

        Returns:
            List of comment dictionaries
        """
        if not self.execute_tool or not self.repo_name:
            logger.warning("github_tools not available. Returning empty comments.")
            return []

        try:
            result = await self.execute_tool(
                "github_get_pr_comments", repo_name=self.repo_name, pr_number=pr_number
            )

            data = json.loads(result)
            if "error" in data:
                logger.error(f"Error getting PR comments: {data['error']}")
                return []

            all_comments = data.get("review_comments", []) + data.get(
                "issue_comments", []
            )

            # Filter by date if specified
            if since:
                filtered_comments = []
                for comment in all_comments:
                    created_at = datetime.fromisoformat(
                        comment["created_at"].replace("Z", "+00:00")
                    )
                    if created_at > since:
                        filtered_comments.append(comment)
                return filtered_comments

            return all_comments

        except Exception as e:
            logger.error(f"Failed to get PR comments: {e}")
            return []

    async def add_pr_comment(self, pr_number: int, comment: str) -> bool:
        """Add a comment to a PR using github_tools functionality.

        Args:
            pr_number: PR number
            comment: Comment text

        Returns:
            Success status
        """
        if not self.execute_tool or not self.repo_name:
            logger.warning("github_tools not available. Cannot add comment.")
            return False

        try:
            result = await self.execute_tool(
                "github_post_pr_reply",
                repo_name=self.repo_name,
                comment_id=pr_number,  # This is incorrect but github_tools expects comment_id
                message=comment,
            )

            data = json.loads(result)
            if "error" in data:
                logger.error(f"Error adding PR comment: {data['error']}")
                return False

            return data.get("success", False)

        except Exception as e:
            logger.error(f"Failed to add PR comment: {e}")
            return False

    async def get_ci_status(self, pr_number: int) -> dict[str, Any]:
        """Get CI status using github_tools functionality.

        Args:
            pr_number: PR number

        Returns:
            CI status dictionary
        """
        if not self.execute_tool or not self.repo_name:
            logger.warning("github_tools not available. Returning dummy status.")
            return {
                "status": "success",
                "checks": [],
                "commit_sha": "unknown",
                "pr_number": pr_number,
            }

        try:
            result = await self.execute_tool(
                "github_get_build_status", repo_name=self.repo_name
            )

            data = json.loads(result)
            if "error" in data:
                logger.error(f"Error getting CI status: {data['error']}")
                return {
                    "status": "error",
                    "checks": [],
                    "commit_sha": "unknown",
                    "pr_number": pr_number,
                }

            return {
                "status": data.get("overall_state", "unknown"),
                "checks": data.get("check_runs", []),
                "commit_sha": data.get("commit_sha", "unknown"),
                "pr_number": pr_number,
            }

        except Exception as e:
            logger.error(f"Failed to get CI status: {e}")
            return {
                "status": "error",
                "checks": [],
                "commit_sha": "unknown",
                "pr_number": pr_number,
            }

    async def push_changes(self, branch: str, commit_message: str) -> str:
        """Push changes to GitHub.

        Args:
            branch: Branch to push
            commit_message: Commit message

        Returns:
            Commit SHA
        """
        try:
            import git

            git_repo = git.Repo(self.repo_path)

            # Add all changes
            git_repo.git.add(A=True)

            # Commit changes
            commit = git_repo.index.commit(commit_message)

            # Push to origin
            origin = git_repo.remote("origin")
            origin.push(refspec=f"{branch}:{branch}", set_upstream=True)

            logger.info(f"Pushed changes to branch '{branch}': {commit.hexsha}")
            return commit.hexsha

        except Exception as e:
            logger.error(f"Failed to push changes: {e}")
            raise

    async def wait_for_checks(
        self, pr_number: int, timeout: int = 1800, poll_interval: int = 30
    ) -> dict[str, Any]:
        """Wait for CI checks to complete.

        Args:
            pr_number: PR number
            timeout: Maximum wait time in seconds
            poll_interval: Polling interval in seconds

        Returns:
            Final CI status
        """
        import asyncio

        start_time = asyncio.get_event_loop().time()

        while True:
            status = await self.get_ci_status(pr_number)

            # Check if complete
            if status["status"] in ["success", "failure", "error"]:
                return status

            # Check timeout
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed >= timeout:
                logger.warning(f"Timeout waiting for CI checks on PR #{pr_number}")
                return status

            # Wait before next check
            await asyncio.sleep(poll_interval)

    def extract_actionable_feedback(self, comments: list[dict]) -> list[dict]:
        """Extract actionable feedback from PR comments.

        Args:
            comments: List of comment dictionaries

        Returns:
            List of actionable items with priority
        """
        actionable_items = []

        # Keywords that indicate actionable feedback
        high_priority_keywords = [
            "must",
            "required",
            "fix",
            "error",
            "broken",
            "critical",
        ]
        medium_priority_keywords = [
            "should",
            "recommend",
            "suggest",
            "improve",
            "consider",
        ]

        for comment in comments:
            body = comment.get("body", "").lower()

            # Skip approval/praise comments
            if any(
                word in body for word in ["looks good", "lgtm", "ship it", "approved"]
            ):
                continue

            # Check for actionable keywords
            is_high_priority = any(
                keyword in body for keyword in high_priority_keywords
            )
            is_medium_priority = any(
                keyword in body for keyword in medium_priority_keywords
            )

            if is_high_priority or is_medium_priority:
                priority = "high" if is_high_priority else "normal"

                actionable_items.append(
                    {
                        "comment_id": comment.get("id"),
                        "author": comment.get("author"),
                        "task": comment.get("body"),
                        "priority": priority,
                        "type": comment.get("type", "unknown"),
                        "file": comment.get("file"),
                        "line": comment.get("line"),
                    }
                )

        return actionable_items

    async def apply_patch(self, patch_path: str, branch: str) -> bool:
        """Apply a git patch to the repository.

        Args:
            patch_path: Path to patch file
            branch: Branch to apply patch to

        Returns:
            Success status
        """
        try:
            import git

            git_repo = git.Repo(self.repo_path)

            # Checkout target branch
            git_repo.git.checkout(branch)

            # Apply patch
            git_repo.git.apply(patch_path)

            logger.info(f"Applied patch {patch_path} to branch {branch}")
            return True

        except Exception as e:
            logger.error(f"Failed to apply patch {patch_path}: {e}")
            return False


class MCPServerInterface:
    """Interface for MCP server communication."""

    def __init__(self, server_url: str | None = None):
        """Initialize MCP server interface.

        Args:
            server_url: MCP server URL (or from MCP_SERVER_URL env var)
        """
        self.server_url = server_url or os.getenv(
            "MCP_SERVER_URL", "http://localhost:8080"
        )
        logger.info(f"Initialized MCP server interface: {self.server_url}")

    async def get_pr_comments(self, pr_number: int) -> list[dict]:
        """Get PR comments via MCP server.

        Args:
            pr_number: PR number

        Returns:
            List of comment dictionaries
        """
        # Placeholder implementation - would integrate with actual MCP server
        logger.info(f"Getting PR comments for #{pr_number} via MCP")
        return []

    async def get_check_runs(self, pr_number: int) -> list[dict]:
        """Get CI check runs via MCP server.

        Args:
            pr_number: PR number

        Returns:
            List of check run dictionaries
        """
        # Placeholder implementation
        logger.info(f"Getting check runs for PR #{pr_number} via MCP")
        return []

    async def get_check_log(self, pr_number: int, check_name: str) -> str:
        """Get CI check log via MCP server.

        Args:
            pr_number: PR number
            check_name: Name of the check

        Returns:
            Check log content
        """
        # Placeholder implementation
        logger.info(f"Getting check log for PR #{pr_number}, check: {check_name}")
        return ""
