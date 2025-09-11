"""Agent nodes interface definition."""

from abc import ABC, abstractmethod

from langgraph_workflow.state import WorkflowState


class AgentNodesInterface(ABC):
    """Abstract interface for agent nodes."""

    @abstractmethod
    async def analyze_codebase(self, state: WorkflowState) -> dict:
        """Analyze codebase structure."""
        pass

    @abstractmethod  
    async def analyze_feature(self, state: WorkflowState) -> dict:
        """Analyze feature requirements with all agents."""
        pass

    @abstractmethod
    async def consolidate_design(self, state: WorkflowState) -> dict:
        """Consolidate agent analyses into unified design."""
        pass

    @abstractmethod
    async def incorporate_feedback(self, state: WorkflowState) -> dict:
        """Incorporate PR feedback into design."""
        pass

    @abstractmethod
    async def create_skeleton(self, state: WorkflowState) -> dict:
        """Create architecture skeleton."""
        pass

    @abstractmethod
    async def create_tests(self, state: WorkflowState) -> dict:
        """Create comprehensive test suite."""
        pass

    @abstractmethod
    async def implement_code(self, state: WorkflowState) -> dict:
        """Implement code based on skeleton."""
        pass

    @abstractmethod
    async def fix_failures(self, state: WorkflowState) -> dict:
        """Fix test/lint failures."""
        pass