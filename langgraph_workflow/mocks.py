"""Mock implementations for testing the LangGraph workflow."""

from datetime import datetime
from pathlib import Path
from typing import Any, Sequence
from langchain_core.messages import BaseMessage, AIMessage

from .interfaces import (
    ModelInterface,
    GitHubInterface,
    AgentInterface,
    CodebaseAnalyzerInterface,
    CheckpointerInterface,
    FileSystemInterface,
    GitInterface,
    TestRunnerInterface,
    ConflictResolverInterface,
    ArtifactManagerInterface,
)


class MockModel(ModelInterface):
    """Mock language model for testing."""
    
    def __init__(self, responses: list[str] | None = None):
        """Initialize with predefined responses.
        
        Args:
            responses: List of responses to return (cycles through)
        """
        self.responses = responses or ["Mock response"]
        self.call_count = 0
        self.last_messages = None
    
    async def ainvoke(self, messages: Sequence[BaseMessage]) -> Any:
        """Return mock response."""
        self.last_messages = list(messages)
        response = self.responses[self.call_count % len(self.responses)]
        self.call_count += 1
        
        # Return object with content attribute like real models
        class MockResponse:
            def __init__(self, content: str):
                self.content = content
        
        return MockResponse(response)


class MockGitHub(GitHubInterface):
    """Mock GitHub integration for testing."""
    
    def __init__(self):
        """Initialize mock GitHub."""
        self.branches = {}
        self.prs = {}
        self.pr_comments = {}
        self.ci_statuses = {}
        self.commits = {}
        self.next_pr_number = 1
    
    async def create_branch(self, branch_name: str, base_branch: str = "main") -> str:
        """Mock create branch."""
        self.branches[branch_name] = base_branch
        return branch_name
    
    async def create_pull_request(
        self,
        title: str,
        body: str,
        branch: str,
        base_branch: str = "main",
        labels: list[str] | None = None
    ) -> int:
        """Mock create PR."""
        pr_number = self.next_pr_number
        self.next_pr_number += 1
        
        self.prs[pr_number] = {
            "title": title,
            "body": body,
            "branch": branch,
            "base_branch": base_branch,
            "labels": labels or [],
            "created_at": datetime.now()
        }
        self.pr_comments[pr_number] = []
        
        return pr_number
    
    async def get_pr_comments(self, pr_number: int, since: datetime | None = None) -> list[dict]:
        """Mock get PR comments."""
        comments = self.pr_comments.get(pr_number, [])
        if since:
            comments = [c for c in comments if c["created_at"] > since]
        return comments
    
    async def add_pr_comment(self, pr_number: int, comment: str) -> bool:
        """Mock add PR comment."""
        if pr_number not in self.pr_comments:
            return False
        
        self.pr_comments[pr_number].append({
            "id": len(self.pr_comments[pr_number]) + 1,
            "type": "issue_comment",
            "author": "test_user",
            "body": comment,
            "created_at": datetime.now(),
            "html_url": f"https://github.com/test/repo/pull/{pr_number}"
        })
        return True
    
    async def get_ci_status(self, pr_number: int) -> dict[str, Any]:
        """Mock get CI status."""
        return self.ci_statuses.get(pr_number, {
            "status": "success",
            "checks": [],
            "commit_sha": "abc123",
            "pr_number": pr_number
        })
    
    async def push_changes(self, branch: str, commit_message: str) -> str:
        """Mock push changes."""
        commit_sha = f"sha_{len(self.commits)}"
        self.commits[commit_sha] = {
            "branch": branch,
            "message": commit_message,
            "timestamp": datetime.now()
        }
        return commit_sha
    
    async def wait_for_checks(self, pr_number: int, timeout: int = 1800, poll_interval: int = 30) -> dict[str, Any]:
        """Mock wait for checks."""
        return await self.get_ci_status(pr_number)
    
    def set_ci_status(self, pr_number: int, status: dict[str, Any]) -> None:
        """Helper to set CI status for testing."""
        self.ci_statuses[pr_number] = status


class MockAgent(AgentInterface):
    """Mock agent for testing."""
    
    def __init__(self, agent_type: str, responses: dict[str, str] | None = None):
        """Initialize mock agent.
        
        Args:
            agent_type: Type of agent
            responses: Dict of prompt_keyword -> response
        """
        self.agent_type = agent_type
        self.responses = responses or {}
        self.call_history = []
    
    async def analyze(self, prompt: str) -> str:
        """Mock analysis."""
        self.call_history.append(("analyze", prompt))
        
        # Return specific response if keyword matches
        for keyword, response in self.responses.items():
            if keyword.lower() in prompt.lower():
                return response
        
        return f"Mock {self.agent_type} analysis: {prompt[:50]}..."
    
    async def review(self, content: str, context: dict[str, Any]) -> str:
        """Mock review."""
        self.call_history.append(("review", content, context))
        return f"Mock {self.agent_type} review: Looks good"


class MockCodebaseAnalyzer(CodebaseAnalyzerInterface):
    """Mock codebase analyzer for testing."""
    
    def __init__(self, analysis_result: dict[str, Any] | None = None):
        """Initialize with mock analysis result."""
        self.analysis_result = analysis_result or {
            "architecture": "Mock architecture",
            "languages": ["Python", "JavaScript"],
            "frameworks": ["FastAPI", "React"],
            "patterns": "Mock patterns",
            "conventions": "Mock conventions",
            "interfaces": "Mock interfaces",
            "services": "Mock services",
            "testing": "pytest",
            "recent_changes": "Mock recent changes"
        }
    
    async def analyze(self) -> dict[str, Any]:
        """Return mock analysis."""
        return self.analysis_result.copy()


class MockCheckpointer(CheckpointerInterface):
    """Mock checkpointer for testing."""
    
    def __init__(self):
        """Initialize mock checkpointer."""
        self.checkpoints = {}
    
    async def put(self, config: dict, checkpoint: dict, metadata: dict) -> None:
        """Save mock checkpoint."""
        thread_id = config.get("configurable", {}).get("thread_id", "default")
        self.checkpoints[thread_id] = {
            "config": config.copy(),
            "checkpoint": checkpoint.copy(),
            "metadata": metadata.copy()
        }
    
    async def get(self, config: dict) -> dict | None:
        """Get mock checkpoint."""
        thread_id = config.get("configurable", {}).get("thread_id", "default")
        saved = self.checkpoints.get(thread_id)
        return saved["checkpoint"].copy() if saved else None


class MockFileSystem(FileSystemInterface):
    """Mock file system for testing."""
    
    def __init__(self):
        """Initialize mock file system."""
        self.files = {}
        self.directories = set()
    
    async def write_text(self, path: Path, content: str) -> None:
        """Mock write text."""
        self.files[str(path)] = content
        # Add parent directories
        parent = path.parent
        while parent != Path("."):
            self.directories.add(str(parent))
            parent = parent.parent
    
    async def read_text(self, path: Path) -> str:
        """Mock read text."""
        content = self.files.get(str(path))
        if content is None:
            raise FileNotFoundError(f"Mock file not found: {path}")
        return content
    
    async def exists(self, path: Path) -> bool:
        """Mock exists check."""
        return str(path) in self.files or str(path) in self.directories
    
    async def mkdir(self, path: Path, parents: bool = True, exist_ok: bool = True) -> None:
        """Mock mkdir."""
        if parents:
            current = path
            while current != Path("."):
                self.directories.add(str(current))
                current = current.parent
        else:
            self.directories.add(str(path))


class MockGit(GitInterface):
    """Mock Git operations for testing."""
    
    def __init__(self):
        """Initialize mock Git."""
        self.branches = {"main": "sha_initial"}
        self.current_branch = "main"
        self.commits = {"sha_initial": {"message": "Initial commit"}}
        self.next_sha_num = 1
    
    async def create_branch(self, branch_name: str) -> str:
        """Mock create branch."""
        current_sha = self.branches[self.current_branch]
        self.branches[branch_name] = current_sha
        return branch_name
    
    async def commit_changes(self, message: str) -> str:
        """Mock commit changes."""
        sha = f"sha_{self.next_sha_num}"
        self.next_sha_num += 1
        
        self.commits[sha] = {
            "message": message,
            "branch": self.current_branch,
            "timestamp": datetime.now()
        }
        self.branches[self.current_branch] = sha
        
        return sha
    
    async def checkout(self, branch: str) -> None:
        """Mock checkout branch."""
        if branch not in self.branches:
            raise ValueError(f"Branch not found: {branch}")
        self.current_branch = branch
    
    async def get_current_sha(self) -> str:
        """Mock get current SHA."""
        return self.branches[self.current_branch]


class MockTestRunner(TestRunnerInterface):
    """Mock test runner for testing."""
    
    def __init__(self, test_results: dict[str, Any] | None = None, lint_results: dict[str, Any] | None = None):
        """Initialize with mock results."""
        self.test_results = test_results or {
            "passed": 10,
            "failed": 0,
            "errors": 0,
            "total": 10,
            "failed_tests": []
        }
        self.lint_results = lint_results or {
            "errors": 0,
            "warnings": 0,
            "issues": []
        }
        self.runs = []
    
    async def run_tests(self, test_path: str | None = None) -> dict[str, Any]:
        """Mock run tests."""
        self.runs.append(("tests", test_path))
        return self.test_results.copy()
    
    async def run_lint(self) -> dict[str, Any]:
        """Mock run lint."""
        self.runs.append(("lint", None))
        return self.lint_results.copy()
    
    def set_test_results(self, results: dict[str, Any]) -> None:
        """Helper to set test results."""
        self.test_results = results
    
    def set_lint_results(self, results: dict[str, Any]) -> None:
        """Helper to set lint results."""
        self.lint_results = results


class MockConflictResolver(ConflictResolverInterface):
    """Mock conflict resolver for testing."""
    
    def __init__(self):
        """Initialize mock resolver."""
        self.identified_conflicts = []
        self.resolutions = {}
    
    async def identify_conflicts(self, analyses: dict[str, str]) -> list[dict[str, Any]]:
        """Mock identify conflicts."""
        conflicts = []
        
        # Simple mock logic: create conflict if analyses mention "disagree"
        disagreeing_agents = []
        for agent, analysis in analyses.items():
            if "disagree" in analysis.lower() or "conflict" in analysis.lower():
                disagreeing_agents.append(agent)
        
        if disagreeing_agents:
            conflict = {
                "id": f"conflict_{len(self.identified_conflicts)}",
                "agents": disagreeing_agents,
                "description": "Mock conflict detected",
                "analyses": {agent: analyses[agent] for agent in disagreeing_agents}
            }
            conflicts.append(conflict)
            self.identified_conflicts.append(conflict)
        
        return conflicts
    
    async def resolve_conflict(self, conflict: dict[str, Any]) -> str:
        """Mock resolve conflict."""
        conflict_id = conflict.get("id", "unknown")
        resolution = self.resolutions.get(conflict_id, "Mock resolution: compromise reached")
        return resolution
    
    def set_resolution(self, conflict_id: str, resolution: str) -> None:
        """Helper to set resolution for conflict."""
        self.resolutions[conflict_id] = resolution


class MockArtifactManager(ArtifactManagerInterface):
    """Mock artifact manager for testing."""
    
    def __init__(self, thread_id: str):
        """Initialize mock artifact manager."""
        self.thread_id = thread_id
        self.artifacts = {}  # key -> content
        self.artifact_paths = {}  # key -> path
    
    async def save_artifact(self, key: str, content: str, artifact_type: str) -> str:
        """Mock save artifact."""
        path = f"mock/artifacts/{self.thread_id}/{artifact_type}_{key}.txt"
        self.artifacts[key] = content
        self.artifact_paths[key] = path
        return path
    
    async def get_artifact(self, key: str) -> str | None:
        """Mock get artifact."""
        return self.artifacts.get(key)
    
    async def list_artifacts(self) -> dict[str, str]:
        """Mock list artifacts."""
        return self.artifact_paths.copy()


# Factory functions for creating mock objects

def create_mock_agents() -> dict[str, MockAgent]:
    """Create mock agents for all types."""
    return {
        "test-first": MockAgent("test-first", {
            "test": "Mock test scenarios created",
            "skeleton": "Mock tests for skeleton created"
        }),
        "fast-coder": MockAgent("fast-coder", {
            "implement": "Mock implementation created",
            "skeleton": "Mock implementation completed"
        }),
        "senior-engineer": MockAgent("senior-engineer", {
            "analyze": "Mock codebase analysis completed",
            "skeleton": "Mock skeleton structure created",
            "refactor": "Mock refactoring suggestions"
        }),
        "architect": MockAgent("architect", {
            "synthesize": "Mock synthesis document created",
            "review": "Mock architectural review completed"
        })
    }


def create_mock_dependencies(thread_id: str = "test-thread") -> dict[str, Any]:
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
        "artifact_manager": MockArtifactManager(thread_id)
    }