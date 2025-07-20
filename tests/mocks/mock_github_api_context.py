"""Mock GitHub API context for testing."""

from typing import TYPE_CHECKING
from unittest.mock import Mock

if TYPE_CHECKING:
    from github import Github, Repository

from github_tools import AbstractGitHubAPIContext


class MockGitHubAPIContext(AbstractGitHubAPIContext):
    """Mock implementation of GitHub API context for testing"""

    def __init__(
        self,
        repo_name: str = "test/test-repo",
        github_token: str = "fake_token_for_testing",
    ):
        self.repo_name = repo_name
        self.github_token = github_token

        # Create a mock GitHub client and repository for testing
        from github import Github, Repository

        self.github = Mock(spec=Github)
        self.repo = Mock(spec=Repository)

        # Set up basic mock behavior
        self.github.get_repo.return_value = self.repo

    def get_repo_name(self) -> str:
        """Get the repository name"""
        return self.repo_name

    def get_repo(self) -> "Repository | None":
        """Get the GitHub repository object"""
        return self.repo

    def get_github_token(self) -> str:
        """Get the GitHub API token"""
        return self.github_token

    def get_github_client(self) -> "Github":
        """Get the GitHub API client"""
        return self.github

    def get_current_branch(self) -> str:
        """Get current branch name (mock implementation)"""
        return "test-branch"

    def get_current_commit(self) -> str:
        """Get current commit hash (mock implementation)"""
        return "abc123def456"
