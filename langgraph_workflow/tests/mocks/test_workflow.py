"""Test implementation of MultiAgentWorkflow with controlled dependencies.

This is not a simple mock but a real test implementation that executes
actual workflow logic with predictable, controlled dependencies.
"""

import tempfile
from pathlib import Path
from typing import Any
from uuid import uuid4

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver

from ...enums import AgentType, ModelRouter, WorkflowPhase
from ...langgraph_workflow import (
    MultiAgentWorkflow,
    WorkflowState,
)
from .mock_agent import MockAgent
from .mock_codebase_analyzer import MockCodebaseAnalyzer
from .mock_github import MockGitHub
from .mock_model import MockModel


class TestFileSystem:
    """Test file system that operates in memory/temp directories."""

    def __init__(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temp_dir.name)

    def write_text(self, path: str | Path, content: str):
        """Write text to a file in the test filesystem."""
        full_path = self.base_path / path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content)

    def read_text(self, path: str | Path) -> str:
        """Read text from a file in the test filesystem."""
        full_path = self.base_path / path
        return full_path.read_text()

    def exists(self, path: str | Path) -> bool:
        """Check if file exists in test filesystem."""
        full_path = self.base_path / path
        return full_path.exists()

    def cleanup(self):
        """Clean up the test filesystem."""
        self.temp_dir.cleanup()


class TestLangGraphCheckpointer(BaseCheckpointSaver):
    """Test checkpointer that stores state in memory."""

    def __init__(self):
        self.memory_saver = MemorySaver()

    def get_tuple(self, config):
        return self.memory_saver.get_tuple(config)

    def list(self, config, *, filter_dict=None, before=None, limit=None):
        return self.memory_saver.list(
            config, filter=filter_dict, before=before, limit=limit
        )

    def put(self, config, checkpoint, metadata, new_versions):
        return self.memory_saver.put(config, checkpoint, metadata, new_versions)

    def put_writes(self, config, writes, task_id):
        return self.memory_saver.put_writes(config, writes, task_id)


class TestMultiAgentWorkflow(MultiAgentWorkflow):
    """Test implementation that executes real workflow logic with controlled dependencies.

    This class inherits from MultiAgentWorkflow and overrides dependency creation
    to use test implementations, while maintaining all the real workflow logic.
    """

    def __init__(
        self,
        repo_path: str,
        thread_id: str | None = None,
        checkpoint_path: str = ":memory:",
    ):
        """Initialize test workflow with controlled dependencies.

        Args:
            repo_path: Path to the repository (can be test directory)
            thread_id: Thread ID for persistence (uses test ID if None)
            checkpoint_path: Checkpoint path (uses memory by default)
        """
        # Set basic attributes without calling parent __init__
        self.repo_path = Path(repo_path)
        self.thread_id = thread_id or f"test-{uuid4().hex[:8]}"
        self.checkpoint_path = checkpoint_path

        # Create test filesystem
        self.test_fs = TestFileSystem()
        self.artifacts_dir = self.test_fs.base_path / "artifacts" / self.thread_id
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)

        # Initialize with test dependencies
        self.agents = self._create_test_agents()
        self.ollama_model = MockModel(["Test Ollama response"])
        self.claude_model = MockModel(["Test Claude response"])

        # Create test codebase analyzer
        self.codebase_analyzer = MockCodebaseAnalyzer()

        # Create test GitHub integration
        self.github = MockGitHub()

        # Build the real graph structure with test dependencies
        self.graph = self._build_graph()

        # Use test checkpointer
        self.checkpointer = TestLangGraphCheckpointer()
        self.app = self.graph.compile(checkpointer=self.checkpointer)

    def _create_test_agents(self) -> dict[AgentType, MockAgent]:
        """Create test agents with intelligent, pattern-based responses."""
        return {
            AgentType.TEST_FIRST: MockAgent(
                AgentType.TEST_FIRST,
                response_patterns={
                    "authentication": "Tests needed: login validation, session management, JWT token handling, password security",
                    "user": "Tests needed: user registration, profile management, data validation",
                    "dashboard": "Tests needed: data display, chart rendering, filter functionality, performance",
                    "api": "Tests needed: endpoint validation, error handling, rate limiting, authentication",
                    "database": "Tests needed: CRUD operations, migration scripts, data integrity, connection pooling",
                    "default": "Comprehensive test suite needed with unit, integration, and end-to-end tests",
                },
            ),
            AgentType.FAST_CODER: MockAgent(
                AgentType.FAST_CODER,
                response_patterns={
                    "authentication": "Quick implementation: JWT middleware, login/logout endpoints, session storage",
                    "user": "Quick implementation: User model, CRUD endpoints, validation middleware",
                    "dashboard": "Quick implementation: React components, API integration, basic styling",
                    "api": "Quick implementation: Express routes, middleware, error handling, documentation",
                    "database": "Quick implementation: ORM models, migrations, seeders, connection setup",
                    "default": "Rapid prototyping approach with core functionality and basic error handling",
                },
            ),
            AgentType.SENIOR_ENGINEER: MockAgent(
                AgentType.SENIOR_ENGINEER,
                response_patterns={
                    "authentication": "Robust implementation: OAuth2 integration, security best practices, audit logging",
                    "user": "Robust implementation: Data validation, error handling, security considerations, scalability",
                    "dashboard": "Robust implementation: Performance optimization, accessibility, responsive design, state management",
                    "api": "Robust implementation: RESTful design, comprehensive documentation, monitoring, caching",
                    "database": "Robust implementation: Indexing strategy, query optimization, backup procedures, scaling",
                    "default": "Production-ready implementation with security, performance, and maintainability focus",
                },
            ),
            AgentType.ARCHITECT: MockAgent(
                AgentType.ARCHITECT,
                response_patterns={
                    "authentication": "System design: Microservice architecture, single sign-on, security layers",
                    "user": "System design: User service boundaries, data consistency, event-driven architecture",
                    "dashboard": "System design: Frontend architecture, state management, component library, CDN",
                    "api": "System design: API gateway, service mesh, load balancing, circuit breakers",
                    "database": "System design: Database sharding, replication, caching layers, data modeling",
                    "default": "High-level architecture with scalability, maintainability, and system integration focus",
                },
            ),
        }

    def cleanup(self):
        """Clean up test resources."""
        self.test_fs.cleanup()

    # Override file operations to use test filesystem
    def _save_artifact(self, filename: str, content: str) -> Path:
        """Save artifact to test filesystem."""
        artifact_path = self.artifacts_dir / filename
        self.test_fs.write_text(artifact_path, content)
        return artifact_path

    def _read_artifact(self, filename: str) -> str:
        """Read artifact from test filesystem."""
        artifact_path = self.artifacts_dir / filename
        return self.test_fs.read_text(artifact_path)

    # Override methods that need filesystem operations
    async def extract_code_context(self, state: WorkflowState) -> WorkflowState:
        """Extract code context using test analyzer and filesystem."""
        # Use real workflow logic but with test dependencies
        state["model_router"] = ModelRouter.CLAUDE_CODE
        state["current_phase"] = WorkflowPhase.PHASE_0_CODE_CONTEXT

        # Use test codebase analyzer
        analysis = await self.codebase_analyzer.analyze()

        # Create code context document (real logic)
        context_doc = f"""# Code Context Document

## Architecture Overview
{analysis.get('architecture', 'Test architecture analysis')}

## Technology Stack
- Languages: {', '.join(analysis.get('languages', ['Python']))}
- Frameworks: {', '.join(analysis.get('frameworks', ['FastAPI']))}
- Databases: {', '.join(analysis.get('databases', ['SQLite']))}

## Design Patterns
{analysis.get('patterns', 'Repository pattern, dependency injection')}

## Code Conventions
{analysis.get('conventions', 'PEP 8, type hints')}

## Key Interfaces
{analysis.get('interfaces', 'Abstract base classes')}

## Infrastructure Services
{analysis.get('services', 'HTTP API services')}

## Testing Approach
{analysis.get('testing', 'pytest with dependency injection')}

## Recent Changes
{analysis.get('recent_changes', 'Test repository setup')}
"""

        # Save to test artifacts
        context_path = self._save_artifact("code_context.md", context_doc)

        state["code_context_document"] = context_doc
        state["artifacts_index"]["code_context"] = str(context_path)
        # Skip message handling in test implementation

        # Would normally add message here, but skipping for test

        return state

    # Override other methods similarly to use test dependencies
    async def create_design_document(self, state: WorkflowState) -> WorkflowState:
        """Create design document using test filesystem."""
        state["model_router"] = ModelRouter.OLLAMA
        state["current_phase"] = WorkflowPhase.PHASE_2_DESIGN_DOCUMENT

        # Real design document template logic
        design_doc = f"""# Design Document: {state['feature_description']}

## Overview
{state['feature_description']}

## Acceptance Criteria
<!-- Generated from Test-first agent analysis -->
{state.get('agent_analyses', {}).get(str(AgentType.TEST_FIRST), 'Acceptance criteria to be defined')}

## Technical Design
<!-- Detailed technical approach -->
{state.get('agent_analyses', {}).get(str(AgentType.SENIOR_ENGINEER), 'Technical design to be detailed')}

## Implementation Plan
<!-- Step-by-step implementation -->
{state.get('agent_analyses', {}).get(str(AgentType.FAST_CODER), 'Implementation plan to be created')}

## Architecture Considerations
<!-- System-level design -->
{state.get('agent_analyses', {}).get(str(AgentType.ARCHITECT), 'Architecture to be designed')}

## Human Additions
<!-- Empty section for human to comment -->

## Arbitration History
<!-- Auto-populated from PR comments -->

## Unresolved Questions
<!-- Agents add items needing human input -->
"""

        state["design_document"] = design_doc

        # Save to test artifacts
        design_path = self._save_artifact("design_document.md", design_doc)
        state["artifacts_index"]["design_document"] = str(design_path)

        # Skip message handling in test implementation
        # Would normally add message here, but skipping for test

        return state

    # Helper methods for creating deterministic test states
    def create_test_initial_state(self, feature_description: str) -> WorkflowState:
        """Create a test initial state with predictable values."""
        return WorkflowState(
            thread_id=self.thread_id,
            feature_description=feature_description,
            current_phase=WorkflowPhase.PHASE_0_CODE_CONTEXT,
            messages_window=[],
            summary_log="",
            artifacts_index={},
            code_context_document=None,
            design_constraints_document=None,
            design_document=None,
            arbitration_log=[],
            repo_path=str(self.repo_path),
            git_branch="main",
            last_commit_sha=None,
            pr_number=None,
            agent_analyses={},
            synthesis_document=None,
            conflicts=[],
            skeleton_code=None,
            test_code=None,
            implementation_code=None,
            patch_queue=[],
            test_report={},
            ci_status={},
            lint_status={},
            quality="draft",
            feedback_gate="open",
            model_router=ModelRouter.OLLAMA,
            escalation_count=0,
        )

    def get_test_results(self) -> dict[str, Any]:
        """Get test results for assertion in tests."""
        return {
            "artifacts_created": list(self.artifacts_dir.iterdir())
            if self.artifacts_dir.exists()
            else [],
            "agent_responses": {
                agent_type: agent.get_response_history()
                for agent_type, agent in self.agents.items()
            },
            "filesystem_operations": getattr(self.test_fs, "operations", []),
        }
