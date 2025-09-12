"""Abstract interfaces for dependency injection in the LangGraph workflow."""

from abc import ABC, abstractmethod
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

from langchain_core.messages import BaseMessage


class ModelInterface(ABC):
    """Abstract interface for language models."""

    @abstractmethod
    async def ainvoke(self, messages: Sequence[BaseMessage]) -> Any:
        """Invoke the model asynchronously.

        Args:
            messages: Input messages

        Returns:
            Model response
        """
        pass


class GitHubInterface(ABC):
    """Abstract interface for GitHub operations."""

    @abstractmethod
    async def create_branch(self, branch_name: str, base_branch: str = "main") -> str:
        """Create a new branch."""
        pass

    @abstractmethod
    async def create_pull_request(
        self,
        title: str,
        body: str,
        branch: str,
        base_branch: str = "main",
        labels: list[str] | None = None,
    ) -> int:
        """Create a GitHub pull request."""
        pass

    @abstractmethod
    async def get_pr_comments(
        self, pr_number: int, since: datetime | None = None
    ) -> list[dict]:
        """Get comments from a PR."""
        pass

    @abstractmethod
    async def add_pr_comment(self, pr_number: int, comment: str) -> bool:
        """Add a comment to a PR."""
        pass

    @abstractmethod
    async def get_ci_status(self, pr_number: int) -> dict[str, Any]:
        """Get CI status for a PR."""
        pass

    @abstractmethod
    async def push_changes(self, branch: str, commit_message: str) -> str:
        """Commit and push changes."""
        pass

    @abstractmethod
    async def wait_for_checks(
        self, pr_number: int, timeout: int = 1800, poll_interval: int = 30
    ) -> dict[str, Any]:
        """Wait for CI checks to complete."""
        pass


class AgentInterface(ABC):
    """Abstract interface for workflow agents."""

    @abstractmethod
    async def analyze(self, prompt: str) -> str:
        """Analyze using the agent's expertise."""
        pass

    @abstractmethod
    async def review(self, content: str, context: dict[str, Any]) -> str:
        """Review content and provide feedback."""
        pass


class BaseAgentInterface(ABC):
    """Abstract interface for base agents that provide personas."""

    @abstractmethod
    def ask(self, prompt: str) -> str:
        """Ask the agent for a response (synchronous)."""
        pass

    @property
    @abstractmethod
    def persona(self):
        """Get the agent's persona (should have an ask method)."""
        pass


class CodebaseAnalyzerInterface(ABC):
    """Abstract interface for codebase analysis."""

    @abstractmethod
    def analyze(self) -> dict[str, Any]:
        """Analyze the codebase."""
        pass


class CheckpointerInterface(ABC):
    """Abstract interface for workflow checkpointing."""

    @abstractmethod
    async def put(self, config: dict, checkpoint: dict, metadata: dict) -> None:
        """Save a checkpoint."""
        pass

    @abstractmethod
    async def get(self, config: dict) -> dict | None:
        """Get a checkpoint."""
        pass


class FileSystemInterface(ABC):
    """Abstract interface for file system operations."""

    @abstractmethod
    async def write_text(self, path: Path, content: str) -> None:
        """Write text to a file."""
        pass

    @abstractmethod
    async def read_text(self, path: Path) -> str:
        """Read text from a file."""
        pass

    @abstractmethod
    async def exists(self, path: Path) -> bool:
        """Check if path exists."""
        pass

    @abstractmethod
    async def mkdir(
        self, path: Path, parents: bool = True, exist_ok: bool = True
    ) -> None:
        """Create directory."""
        pass


class GitInterface(ABC):
    """Abstract interface for Git operations."""

    @abstractmethod
    async def create_branch(self, branch_name: str) -> str:
        """Create a new Git branch."""
        pass

    @abstractmethod
    async def commit_changes(self, message: str) -> str:
        """Commit changes and return SHA."""
        pass

    @abstractmethod
    async def checkout(self, branch: str) -> None:
        """Checkout a branch."""
        pass

    @abstractmethod
    async def get_current_sha(self) -> str:
        """Get current commit SHA."""
        pass


class TestRunnerInterface(ABC):
    """Abstract interface for test execution."""

    @abstractmethod
    async def run_tests(self, test_path: str | None = None) -> dict[str, Any]:
        """Run tests and return results."""
        pass

    @abstractmethod
    async def run_lint(self) -> dict[str, Any]:
        """Run linting and return results."""
        pass


class ConflictResolverInterface(ABC):
    """Abstract interface for conflict resolution."""

    @abstractmethod
    async def identify_conflicts(
        self, analyses: dict[str, str]
    ) -> list[dict[str, Any]]:
        """Identify conflicts between analyses."""
        pass

    @abstractmethod
    async def resolve_conflict(self, conflict: dict[str, Any]) -> str:
        """Resolve a specific conflict."""
        pass


class ArtifactManagerInterface(ABC):
    """Abstract interface for artifact management."""

    @abstractmethod
    async def save_artifact(self, key: str, content: str, artifact_type: str) -> str:
        """Save an artifact and return its path."""
        pass

    @abstractmethod
    async def get_artifact(self, key: str) -> str | None:
        """Get artifact content by key."""
        pass

    @abstractmethod
    async def list_artifacts(self) -> dict[str, str]:
        """List all artifacts (key -> path mapping)."""
        pass
