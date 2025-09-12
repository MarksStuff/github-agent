"""Mock Git operations for testing."""

from datetime import datetime

from ...interfaces import GitInterface


class MockGit(GitInterface):
    """Mock Git operations for testing."""

    def __init__(self):
        """Initialize mock Git."""
        self.branches = {"main": "sha_initial"}
        self.current_branch = "main"
        self.commits = {"sha_initial": {"message": "Initial commit"}}
        self.next_sha_num = 1

    async def create_branch(self, branch_name: str) -> str:
        """Mock create branch."""
        current_sha = self.branches[self.current_branch]
        self.branches[branch_name] = current_sha
        return branch_name

    async def commit_changes(self, message: str) -> str:
        """Mock commit changes."""
        sha = f"sha_{self.next_sha_num}"
        self.next_sha_num += 1

        self.commits[sha] = {
            "message": message,
            "branch": self.current_branch,
            "timestamp": datetime.now().isoformat(),
        }
        self.branches[self.current_branch] = sha

        return sha

    async def checkout(self, branch: str) -> None:
        """Mock checkout branch."""
        if branch not in self.branches:
            raise ValueError(f"Branch not found: {branch}")
        self.current_branch = branch

    async def get_current_sha(self) -> str:
        """Mock get current SHA."""
        return self.branches[self.current_branch]
