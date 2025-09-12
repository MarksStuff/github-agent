"""Mock GitHub integration for testing."""

from datetime import datetime
from typing import Any

from ...interfaces import GitHubInterface


class MockGitHub(GitHubInterface):
    """Mock GitHub integration for testing."""

    def __init__(self):
        """Initialize mock GitHub."""
        self.branches = {}
        self.prs = {}
        self.pr_comments = {}
        self.ci_statuses = {}
        self.commits = {}
        self.next_pr_number = 1

    async def create_branch(self, branch_name: str, base_branch: str = "main") -> str:
        """Mock create branch."""
        self.branches[branch_name] = base_branch
        return branch_name

    async def create_pull_request(
        self,
        title: str,
        body: str,
        branch: str,
        base_branch: str = "main",
        labels: list[str] | None = None,
    ) -> int:
        """Mock create PR."""
        pr_number = self.next_pr_number
        self.next_pr_number += 1

        self.prs[pr_number] = {
            "title": title,
            "body": body,
            "branch": branch,
            "base_branch": base_branch,
            "labels": labels or [],
            "created_at": datetime.now(),
        }
        self.pr_comments[pr_number] = []

        return pr_number

    async def get_pr_comments(
        self, pr_number: int, since: datetime | None = None
    ) -> list[dict]:
        """Mock get PR comments."""
        comments = self.pr_comments.get(pr_number, [])
        if since:
            comments = [c for c in comments if c["created_at"] > since]
        return comments

    async def add_pr_comment(self, pr_number: int, comment: str) -> bool:
        """Mock add PR comment."""
        if pr_number not in self.pr_comments:
            return False

        self.pr_comments[pr_number].append(
            {
                "id": len(self.pr_comments[pr_number]) + 1,
                "type": "issue_comment",
                "author": "test_user",
                "body": comment,
                "created_at": datetime.now(),
                "html_url": f"https://github.com/test/repo/pull/{pr_number}",
            }
        )
        return True

    async def get_ci_status(self, pr_number: int) -> dict[str, Any]:
        """Mock get CI status."""
        return self.ci_statuses.get(
            pr_number,
            {
                "status": "success",
                "checks": [],
                "commit_sha": "abc123",
                "pr_number": pr_number,
            },
        )

    async def push_changes(self, branch: str, commit_message: str) -> str:
        """Mock push changes."""
        commit_sha = f"sha_{len(self.commits)}"
        self.commits[commit_sha] = {
            "branch": branch,
            "message": commit_message,
            "timestamp": datetime.now(),
        }
        return commit_sha

    async def wait_for_checks(
        self, pr_number: int, timeout: int = 1800, poll_interval: int = 30
    ) -> dict[str, Any]:
        """Mock wait for checks."""
        return await self.get_ci_status(pr_number)

    def set_ci_status(self, pr_number: int, status: dict[str, Any]) -> None:
        """Helper to set CI status for testing."""
        self.ci_statuses[pr_number] = status