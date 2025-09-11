"""Tool nodes interface definition."""

from abc import ABC, abstractmethod

from langgraph_workflow.state import WorkflowState


class ToolNodesInterface(ABC):
    """Abstract interface for tool nodes."""

    @abstractmethod
    async def run_tests(self, state: WorkflowState) -> dict:
        """Execute tests and parse results."""
        pass

    @abstractmethod
    async def run_linter(self, state: WorkflowState) -> dict:
        """Execute linter and parse results."""
        pass

    @abstractmethod
    async def run_formatter(self, state: WorkflowState) -> dict:
        """Execute formatter and auto-fix issues."""
        pass

    @abstractmethod
    async def apply_patch(
        self, state: WorkflowState, patch_content: str, target_file: str
    ) -> dict:
        """Apply a unified diff patch to a file."""
        pass

    @abstractmethod
    async def check_ci_status(self, state: WorkflowState) -> dict:
        """Check CI/CD status using GitHub CLI."""
        pass
