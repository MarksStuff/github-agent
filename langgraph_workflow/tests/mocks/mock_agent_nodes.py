"""Mock implementation of agent nodes for testing."""

from langgraph_workflow.interfaces.agent_interface import AgentNodesInterface
from langgraph_workflow.state import AgentType, WorkflowState


class MockAgentNodes(AgentNodesInterface):
    """Mock implementation of agent nodes for testing."""

    def __init__(self, repo_name: str, repo_path: str):
        """Initialize mock agent nodes."""
        self.repo_name = repo_name
        self.repo_path = repo_path
        self.call_log = []  # Track method calls for verification

    async def analyze_codebase(self, state: WorkflowState) -> dict:
        """Mock codebase analysis."""
        self.call_log.append("analyze_codebase")
        
        # Update state with mock analysis
        state["codebase_analysis"] = {
            "content": "Mock codebase analysis",
            "status": "completed"
        }
        
        return state

    async def analyze_feature(self, state: WorkflowState) -> dict:
        """Mock feature analysis."""
        self.call_log.append("analyze_feature")
        
        # Mock analyses from all agents
        for agent_type in AgentType:
            state["agent_analyses"][agent_type.value] = f"Mock {agent_type.value} analysis"
        
        return state

    async def consolidate_design(self, state: WorkflowState) -> dict:
        """Mock design consolidation."""
        self.call_log.append("consolidate_design")
        
        state["consolidated_design"] = "Mock consolidated design document"
        state["design_conflicts"] = []  # No conflicts in mock
        
        return state

    async def incorporate_feedback(self, state: WorkflowState) -> dict:
        """Mock feedback incorporation."""
        self.call_log.append("incorporate_feedback")
        
        state["finalized_design"] = "Mock finalized design with feedback"
        
        # Mark all comments as addressed
        for comment in state.get("pr_comments", []):
            comment_id = comment.get("id")
            if comment_id:
                state["feedback_addressed"][str(comment_id)] = True
        
        return state

    async def create_skeleton(self, state: WorkflowState) -> dict:
        """Mock skeleton creation."""
        self.call_log.append("create_skeleton")
        
        state["skeleton_code"] = {
            "main.py": "# Mock skeleton code\nclass MockClass:\n    pass"
        }
        
        return state

    async def create_tests(self, state: WorkflowState) -> dict:
        """Mock test creation."""
        self.call_log.append("create_tests")
        
        state["test_code"] = {
            "test_main.py": "# Mock test code\ndef test_mock():\n    assert True"
        }
        
        return state

    async def implement_code(self, state: WorkflowState) -> dict:
        """Mock code implementation."""
        self.call_log.append("implement_code")
        
        state["implementation_code"] = {
            "main.py": "# Mock implementation\nclass MockClass:\n    def mock_method(self):\n        return 'mock'"
        }
        
        return state

    async def fix_failures(self, state: WorkflowState) -> dict:
        """Mock failure fixes."""
        self.call_log.append("fix_failures")
        
        # Increment retry count
        state["retry_count"] = state.get("retry_count", 0) + 1
        
        # Mock successful fix after 2 attempts
        if state["retry_count"] >= 2:
            from langgraph_workflow.state import QualityState
            state["quality_state"] = QualityState.OK
        
        return state