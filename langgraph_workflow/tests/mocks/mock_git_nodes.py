"""Mock implementation of git nodes for testing."""

from langgraph_workflow.interfaces.git_interface import GitNodesInterface
from langgraph_workflow.state import WorkflowState


class MockGitNodes(GitNodesInterface):
    """Mock implementation of git nodes for testing."""

    def __init__(self, repo_name: str, repo_path: str):
        """Initialize mock git nodes."""
        self.repo_name = repo_name
        self.repo_path = repo_path
        self.call_log = []  # Track method calls for verification

    async def initialize_git(self, state: WorkflowState) -> dict:
        """Mock git initialization."""
        self.call_log.append("initialize_git")
        
        state["git_branch"] = f"feature/{state['thread_id']}"
        state["last_commit_sha"] = "mock_commit_sha_123456"
        
        return state

    async def commit_changes(self, state: WorkflowState, message: str = None) -> dict:
        """Mock commit changes."""
        self.call_log.append(f"commit_changes: {message}")
        
        # Generate new mock commit SHA
        import hashlib
        content = f"{state['thread_id']}{message or 'mock commit'}"
        mock_sha = hashlib.md5(content.encode()).hexdigest()[:8]
        state["last_commit_sha"] = f"mock_{mock_sha}"
        
        return state

    async def push_branch_and_pr(self, state: WorkflowState) -> dict:
        """Mock branch push and PR creation."""
        self.call_log.append("push_branch_and_pr")
        
        # Mock PR creation if not exists
        if not state.get("pr_number"):
            # Generate mock PR number based on thread_id
            mock_pr_number = hash(state["thread_id"]) % 1000
            state["pr_number"] = max(1, mock_pr_number)  # Ensure positive
        
        return state

    async def fetch_pr_comments(self, state: WorkflowState) -> dict:
        """Mock fetching PR comments."""
        self.call_log.append("fetch_pr_comments")
        
        # Mock some comments if none exist
        if not state.get("pr_comments"):
            state["pr_comments"] = [
                {
                    "id": "mock_comment_1",
                    "user": {"login": "reviewer1"},
                    "body": "Please add more documentation",
                    "created_at": "2024-01-01T00:00:00Z"
                },
                {
                    "id": "mock_comment_2", 
                    "user": {"login": "reviewer2"},
                    "body": "Consider using a different approach",
                    "created_at": "2024-01-01T01:00:00Z"
                }
            ]
        
        return state

    async def post_pr_reply(self, state: WorkflowState, comment_id: int, message: str) -> dict:
        """Mock posting PR reply."""
        self.call_log.append(f"post_pr_reply: {comment_id} -> {message[:50]}...")
        
        # Mock successful reply posting
        return state