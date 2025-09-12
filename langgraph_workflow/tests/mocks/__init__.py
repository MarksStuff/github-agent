"""Mock implementations for testing the LangGraph workflow."""

from .mock_agent import MockAgent
from .mock_artifact_manager import MockArtifactManager
from .mock_checkpointer import MockCheckpointer
from .mock_codebase_analyzer import MockCodebaseAnalyzer

# from .test_workflow import TestMultiAgentWorkflow  # Avoid circular import
from .mock_conflict_resolver import MockConflictResolver
from .mock_filesystem import MockFileSystem
from .mock_git import MockGit
from .mock_github import MockGitHub
from .mock_model import MockModel
from .mock_test_runner import MockTestRunner

__all__ = [
    "MockAgent",
    "MockArtifactManager",
    "MockCheckpointer",
    "MockCodebaseAnalyzer",
    "MockConflictResolver",
    "MockFileSystem",
    "MockGit",
    "MockGitHub",
    "MockModel",
    "MockTestRunner",
    # "TestMultiAgentWorkflow",  # Avoid circular import
]


def create_mock_agents() -> dict[str, MockAgent]:
    """Create mock agents for all types."""
    return {
        "test-first": MockAgent(
            "test-first",
            {
                "test": "Mock test scenarios created",
                "skeleton": "Mock tests for skeleton created",
            },
        ),
        "fast-coder": MockAgent(
            "fast-coder",
            {
                "implement": "Mock implementation created",
                "skeleton": "Mock implementation completed",
            },
        ),
        "senior-engineer": MockAgent(
            "senior-engineer",
            {
                "analyze": "Mock codebase analysis completed",
                "skeleton": "Mock skeleton structure created",
                "refactor": "Mock refactoring suggestions",
            },
        ),
        "architect": MockAgent(
            "architect",
            {
                "synthesize": "Mock synthesis document created",
                "review": "Mock architectural review completed",
            },
        ),
    }


def create_mock_dependencies(thread_id: str = "test-thread") -> dict[str, any]:
    """Create all mock dependencies for testing."""
    return {
        "ollama_model": MockModel(["Ollama response 1", "Ollama response 2"]),
        "claude_model": MockModel(["Claude response 1", "Claude response 2"]),
        "github": MockGitHub(),
        "agents": create_mock_agents(),
        "codebase_analyzer": MockCodebaseAnalyzer(),
        "checkpointer": MockCheckpointer(),
        "filesystem": MockFileSystem(),
        "git": MockGit(),
        "test_runner": MockTestRunner(),
        "conflict_resolver": MockConflictResolver(),
        "artifact_manager": MockArtifactManager(thread_id),
    }
