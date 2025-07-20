"""Mock repository manager for testing."""

from typing import Any

from repository_manager import AbstractRepositoryManager


class MockRepositoryManager(AbstractRepositoryManager):
    """Mock implementation of repository manager for testing."""

    def __init__(self):
        self._repositories: dict[str, Any] = {}
        self._fail_on_access = False
        self._should_fail_load = False

    @property
    def repositories(self) -> dict[str, Any]:
        """Get dictionary of repositories."""
        if self._fail_on_access:
            raise Exception("Test exception")
        return self._repositories

    def get_repository(self, name: str) -> Any | None:
        """Get repository by name."""
        if self._fail_on_access:
            raise Exception("Test exception")
        return self._repositories.get(name)

    def add_repository(self, name: str, config: Any):
        """Add a repository configuration."""
        self._repositories[name] = config

    def load_configuration(self) -> bool:
        """Load repository configuration from file.

        Returns:
            True if configuration loaded successfully, False otherwise
        """
        if self._fail_on_access:
            raise Exception("Test configuration load failure")
        if self._should_fail_load:
            raise Exception("Mock configuration load failure")
        return True

    def remove_repository(self, name: str):
        """Remove a repository configuration."""
        self._repositories.pop(name, None)

    def clear_repositories(self):
        """Clear all repositories."""
        self._repositories.clear()

    def set_fail_on_access(self, fail: bool):
        """Set whether to fail when accessing repositories."""
        self._fail_on_access = fail

    def set_fail_load(self, should_fail: bool) -> None:
        """Set whether load_configuration should fail."""
        self._should_fail_load = should_fail

    def get_lsp_client(self, repo_name: str) -> Any | None:
        """Get LSP client for repository (mock implementation)."""
        repo_config = self.get_repository(repo_name)
        if not repo_config:
            return None
        # Return MockLSPClientForTests for test compatibility if repository exists
        from tests.mocks import MockLSPClientForTests

        return MockLSPClientForTests("mock_workspace")
