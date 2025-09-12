"""Simple test implementation of MultiAgentWorkflow for CLI testing."""

import tempfile
from pathlib import Path
from uuid import uuid4

from .mock_agent import MockAgent
from .mock_codebase_analyzer import MockCodebaseAnalyzer
from .mock_github import MockGitHub
from .mock_model import MockModel


class TestMultiAgentWorkflow:
    """Simplified test implementation for CLI testing."""

    def __init__(self, repo_path: str, thread_id: str | None = None, checkpoint_path: str = ":memory:"):
        """Initialize test workflow."""
        self.repo_path = Path(repo_path)
        self.thread_id = thread_id or f"test-{uuid4().hex[:8]}"
        self.checkpoint_path = checkpoint_path
        
        # Create test filesystem
        self.temp_dir = tempfile.TemporaryDirectory()
        self.artifacts_dir = Path(self.temp_dir.name) / "artifacts" / self.thread_id
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        
        # Test dependencies
        self.agents = {
            "test-first": MockAgent("test-first", response_patterns={
                "authentication": "Authentication tests needed",
                "default": "Comprehensive tests needed"
            }),
            "fast-coder": MockAgent("fast-coder", response_patterns={
                "authentication": "Quick JWT implementation", 
                "default": "Rapid implementation"
            }),
        }
        
        # Mock app that returns a simple state
        self.app = self
        
    async def ainvoke(self, initial_state, config=None):
        """Mock LangGraph app invocation."""
        if initial_state is None:
            # Resume mode - return a simple resume state with a test feature
            return {
                "thread_id": self.thread_id,
                "feature_description": "Test authentication feature (resumed)",
                "current_phase": "resumed",
                "quality": "ok"
            }
        
        # Regular mode - return the initial state with some processing
        return {
            "thread_id": self.thread_id, 
            "feature_description": initial_state["feature_description"],
            "current_phase": "completed",
            "quality": "ok",
            "artifacts_index": {"test": "artifact"},
            "messages_window": [],
            "summary_log": "Test workflow completed"
        }
        
    def cleanup(self):
        """Clean up test resources."""
        self.temp_dir.cleanup()