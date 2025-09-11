"""Git nodes interface definition."""

from abc import ABC, abstractmethod

from langgraph_workflow.state import WorkflowState


class GitNodesInterface(ABC):
    """Abstract interface for git nodes."""

    @abstractmethod
    async def initialize_git(self, state: WorkflowState) -> dict:
        """Initialize git branch for workflow."""
        pass

    @abstractmethod
    async def commit_changes(self, state: WorkflowState, message: str = None) -> dict:
        """Commit changes to current branch."""
        pass

    @abstractmethod
    async def push_branch_and_pr(self, state: WorkflowState) -> dict:
        """Push branch and create/update PR."""
        pass

    @abstractmethod
    async def fetch_pr_comments(self, state: WorkflowState) -> dict:
        """Fetch PR comments for feedback processing."""
        pass

    @abstractmethod
    async def post_pr_reply(
        self, state: WorkflowState, comment_id: int, message: str
    ) -> dict:
        """Post reply to specific PR comment."""
        pass
