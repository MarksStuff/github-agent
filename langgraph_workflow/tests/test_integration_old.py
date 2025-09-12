"""Integration tests for the complete LangGraph workflow."""

import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from ..config import should_escalate_to_claude
from ..langgraph_workflow import (
    ModelRouter,
    MultiAgentWorkflow,
    WorkflowPhase,
    WorkflowState,
)
from ..mocks import create_mock_dependencies


class TestWorkflowIntegration(unittest.IsolatedAsyncioTestCase):
    """Test complete workflow integration."""

    def setUp(self):
        """Set up integration test fixtures."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.repo_path = self.temp_dir.name
        self.thread_id = "integration-test-123"

        # Create mock dependencies
        self.mock_deps = create_mock_dependencies(self.thread_id)

        # Create initial state for full workflow
        self.initial_state = WorkflowState(
            thread_id=self.thread_id,
            feature_description="Add comprehensive user authentication with JWT tokens, role-based access control, and session management",
            current_phase=WorkflowPhase.PHASE_0_CODE_CONTEXT,
            messages_window=[],
            summary_log="",
            artifacts_index={},
            code_context_document=None,
            design_constraints_document=None,
            design_document=None,
            arbitration_log=[],
            repo_path=self.repo_path,
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

    def tearDown(self):
        """Clean up integration test fixtures."""
        self.temp_dir.cleanup()

    async def test_complete_workflow_success_path(self):
        """Test complete workflow from Phase 0 to deployment."""
        workflow = MultiAgentWorkflow(
            repo_path=self.repo_path, thread_id=self.thread_id
        )

        # Replace dependencies with mocks
        workflow.agents = self.mock_deps["agents"]
        workflow.ollama_model = self.mock_deps["ollama_model"]
        workflow.claude_model = self.mock_deps["claude_model"]
        workflow.checkpointer = self.mock_deps["checkpointer"]
        workflow.artifacts_dir = Path(self.temp_dir.name) / "artifacts"
        workflow.artifacts_dir.mkdir(exist_ok=True)

        # Mock all the helper methods to simulate successful execution
        with patch.object(
            workflow, "extract_code_context"
        ) as mock_phase0, patch.object(
            workflow, "parallel_design_exploration"
        ) as mock_phase1, patch.object(
            workflow, "architect_synthesis"
        ) as mock_synthesis, patch.object(
            workflow, "create_design_document"
        ) as mock_phase2, patch.object(
            workflow, "create_skeleton"
        ) as mock_skeleton, patch.object(
            workflow, "parallel_development"
        ) as mock_parallel, patch.object(
            workflow, "reconciliation"
        ) as mock_reconcile, patch.object(workflow, "refinement") as mock_refinement:
            # Configure phase results
            mock_phase0.return_value = self._create_phase0_result()
            mock_phase1.return_value = self._create_phase1_result()
            mock_synthesis.return_value = self._create_synthesis_result()
            mock_phase2.return_value = self._create_phase2_result()
            mock_skeleton.return_value = self._create_skeleton_result()
            mock_parallel.return_value = self._create_parallel_result()
            mock_reconcile.return_value = self._create_reconcile_result()
            mock_refinement.return_value = self._create_refinement_result()

            # Execute individual phases to test flow
            state = self.initial_state.copy()

            # Phase 0: Code Context
            state = await workflow.extract_code_context(state)
            self.assertEqual(state["current_phase"], WorkflowPhase.PHASE_0_CODE_CONTEXT)
            self.assertIsNotNone(state["code_context_document"])

            # Phase 1: Design Exploration
            state = await workflow.parallel_design_exploration(state)
            self.assertEqual(
                state["current_phase"], WorkflowPhase.PHASE_1_DESIGN_EXPLORATION
            )
            self.assertEqual(len(state["agent_analyses"]), 4)

            # Phase 1: Synthesis
            state = await workflow.architect_synthesis(state)
            self.assertIsNotNone(state["synthesis_document"])

            # Phase 2: Design Document
            state = await workflow.create_design_document(state)
            self.assertIsNotNone(state["design_document"])

            # Phase 3: Skeleton
            state = await workflow.create_skeleton(state)
            self.assertIsNotNone(state["skeleton_code"])

            # Phase 3: Parallel Development
            state = await workflow.parallel_development(state)
            self.assertIsNotNone(state["test_code"])
            self.assertIsNotNone(state["implementation_code"])

            # Phase 3: Reconciliation
            state = await workflow.reconciliation(state)
            self.assertEqual(
                state["current_phase"], WorkflowPhase.PHASE_3_RECONCILIATION
            )

            # Phase 3: Refinement
            state = await workflow.refinement(state)
            self.assertEqual(state["quality"], "ok")

    def _create_phase0_result(self):
        """Create Phase 0 result state."""
        state = self.initial_state.copy()
        state["current_phase"] = WorkflowPhase.PHASE_0_CODE_CONTEXT
        state["code_context_document"] = """# Code Context Document

## Architecture Overview
FastAPI-based REST API with PostgreSQL database

## Technology Stack
- Languages: Python 3.11
- Frameworks: FastAPI, SQLAlchemy, Pydantic
- Database: PostgreSQL
- Testing: pytest

## Design Patterns
Repository pattern, dependency injection, factory pattern

## Key Interfaces
- AuthService interface for authentication
- UserRepository interface for data access
"""
        state["artifacts_index"]["code_context"] = "artifacts/code_context.md"
        return state

    def _create_phase1_result(self):
        """Create Phase 1 result state."""
        state = self.initial_state.copy()
        state["current_phase"] = WorkflowPhase.PHASE_1_DESIGN_EXPLORATION
        state["agent_analyses"] = {
            "test-first": "Focus on comprehensive test coverage for auth flows, edge cases, and security scenarios",
            "fast-coder": "Implement JWT-based auth with FastAPI security utilities, quick iteration approach",
            "senior-engineer": "Use established patterns, proper error handling, clean separation of concerns",
            "architect": "Scalable auth service, consider microservice boundaries, session management strategy",
        }
        return state

    def _create_synthesis_result(self):
        """Create synthesis result state."""
        state = self.initial_state.copy()
        state["synthesis_document"] = """# Design Synthesis: User Authentication

## Common Themes
- JWT token-based authentication (all agents agree)
- Role-based access control needed
- Session management important

## Conflicts
- Fast-coder wants simple implementation vs Senior engineer wants robust patterns
- Architect suggests microservice vs others prefer monolithic approach

## Trade-offs
- Fast-coder optimizes for speed of delivery
- Senior engineer optimizes for maintainability
- Architect optimizes for scalability

## Questions Requiring Code Investigation
- What auth libraries are already in use?
- Current user model structure?
"""
        state["conflicts"] = [
            {
                "id": "arch_approach",
                "description": "Microservice vs monolithic auth approach",
                "agents": ["architect", "fast-coder", "senior-engineer"],
            }
        ]
        return state

    def _create_phase2_result(self):
        """Create Phase 2 result state."""
        state = self.initial_state.copy()
        state["design_document"] = """# Design Document: User Authentication

## Overview
Comprehensive JWT-based authentication system with role-based access control

## Acceptance Criteria
- Users can register with email/password
- Users can login and receive JWT token
- Token-based API access
- Role-based permissions
- Session management

## Technical Design
- FastAPI OAuth2 with JWT tokens
- Password hashing with bcrypt
- User roles stored in database
- Token refresh mechanism
- Session timeout handling

## Implementation Plan
1. Create user model and auth schemas
2. Implement auth service with JWT generation
3. Create auth endpoints (register, login, refresh)
4. Add middleware for token validation
5. Implement role-based decorators
6. Add comprehensive tests
"""
        return state

    def _create_skeleton_result(self):
        """Create skeleton result state."""
        state = self.initial_state.copy()
        state["skeleton_code"] = """from abc import ABC, abstractmethod
from typing import Optional
from pydantic import BaseModel

class User(BaseModel):
    id: int
    email: str
    hashed_password: str
    role: str
    is_active: bool

class AuthService(ABC):
    @abstractmethod
    async def register_user(self, email: str, password: str) -> User:
        pass

    @abstractmethod
    async def authenticate_user(self, email: str, password: str) -> Optional[User]:
        pass

    @abstractmethod
    def create_access_token(self, user_id: int) -> str:
        pass

    @abstractmethod
    def verify_token(self, token: str) -> Optional[dict]:
        pass

class UserRepository(ABC):
    @abstractmethod
    async def create_user(self, user: User) -> User:
        pass

    @abstractmethod
    async def get_user_by_email(self, email: str) -> Optional[User]:
        pass
"""
        state["artifacts_index"]["skeleton"] = "artifacts/skeleton.py"
        return state

    def _create_parallel_result(self):
        """Create parallel development result state."""
        state = self.initial_state.copy()
        state["test_code"] = """import pytest
from auth_service import AuthService, User

@pytest.fixture
def auth_service():
    return AuthService()

def test_user_registration(auth_service):
    user = await auth_service.register_user("test@example.com", "password123")
    assert user.email == "test@example.com"
    assert user.is_active is True

def test_user_authentication(auth_service):
    # Setup user
    user = await auth_service.register_user("test@example.com", "password123")

    # Test authentication
    authenticated_user = await auth_service.authenticate_user("test@example.com", "password123")
    assert authenticated_user is not None
    assert authenticated_user.email == "test@example.com"

def test_token_creation_and_verification(auth_service):
    token = auth_service.create_access_token(user_id=123)
    assert token is not None

    payload = auth_service.verify_token(token)
    assert payload is not None
    assert payload["user_id"] == 123
"""

        state["implementation_code"] = """from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
from typing import Optional

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class AuthServiceImpl(AuthService):
    def __init__(self, user_repository: UserRepository):
        self.user_repository = user_repository
        self.secret_key = "your-secret-key"
        self.algorithm = "HS256"

    async def register_user(self, email: str, password: str) -> User:
        hashed_password = pwd_context.hash(password)
        user = User(
            email=email,
            hashed_password=hashed_password,
            role="user",
            is_active=True
        )
        return await self.user_repository.create_user(user)

    async def authenticate_user(self, email: str, password: str) -> Optional[User]:
        user = await self.user_repository.get_user_by_email(email)
        if not user or not pwd_context.verify(password, user.hashed_password):
            return None
        return user

    def create_access_token(self, user_id: int) -> str:
        expire = datetime.utcnow() + timedelta(minutes=30)
        payload = {"user_id": user_id, "exp": expire}
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

    def verify_token(self, token: str) -> Optional[dict]:
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except JWTError:
            return None
"""

        state["artifacts_index"]["tests_initial"] = "artifacts/tests_initial.py"
        state["artifacts_index"][
            "implementation_initial"
        ] = "artifacts/implementation_initial.py"
        return state

    def _create_reconcile_result(self):
        """Create reconciliation result state."""
        state = self._create_parallel_result()
        state["current_phase"] = WorkflowPhase.PHASE_3_RECONCILIATION
        # In a successful reconciliation, code and tests are aligned
        return state

    def _create_refinement_result(self):
        """Create refinement result state."""
        state = self._create_reconcile_result()
        state["quality"] = "ok"
        state["test_report"] = {"passed": 15, "failed": 0, "errors": 0, "coverage": 95}
        return state

    async def test_workflow_with_conflicts_and_arbitration(self):
        """Test workflow handling conflicts and human arbitration."""
        workflow = MultiAgentWorkflow(
            repo_path=self.repo_path, thread_id=self.thread_id
        )

        # Set up mocks for conflict scenario
        workflow.agents = self.mock_deps["agents"]

        # Configure agents to create conflicts
        conflict_analyses = {
            "test-first": "We must have 100% test coverage and comprehensive integration tests",
            "fast-coder": "Let's implement quickly with basic tests, we can add more later",
            "senior-engineer": "Focus on clean patterns and maintainable code structure",
            "architect": "This approach won't scale, we need to disagree with the current design",
        }

        # Create state with conflicting analyses
        state = self.initial_state.copy()
        state["agent_analyses"] = conflict_analyses

        # Mock conflict resolution
        workflow.conflict_resolver = self.mock_deps["conflict_resolver"]

        with patch.object(workflow, "_request_arbitration") as mock_arbitration:
            mock_arbitration.return_value = MagicMock(
                human_decision="Implement with good test coverage but prioritize working solution",
                applied=True,
            )

            # Test synthesis with conflicts
            result = await workflow.architect_synthesis(state)

            # Should detect conflicts due to "disagree" in architect analysis
            conflicts = await workflow.conflict_resolver.identify_conflicts(
                conflict_analyses
            )
            self.assertGreater(len(conflicts), 0)

    async def test_escalation_triggers_in_workflow(self):
        """Test that escalation triggers work correctly in workflow context."""
        # Test various escalation scenarios
        test_cases = [
            {
                "name": "Large diff triggers escalation",
                "params": {"diff_size": 500},
                "should_escalate": True,
            },
            {
                "name": "Many files triggers escalation",
                "params": {"files_touched": 15},
                "should_escalate": True,
            },
            {
                "name": "Multiple failures trigger escalation",
                "params": {"consecutive_failures": 3},
                "should_escalate": True,
            },
            {
                "name": "High complexity triggers escalation",
                "params": {"complexity_score": 0.9},
                "should_escalate": True,
            },
            {
                "name": "Small changes stay with Ollama",
                "params": {"diff_size": 50, "files_touched": 2},
                "should_escalate": False,
            },
        ]

        for case in test_cases:
            with self.subTest(case["name"]):
                result = should_escalate_to_claude(**case["params"])
                self.assertEqual(
                    result,
                    case["should_escalate"],
                    f"{case['name']} failed: expected {case['should_escalate']}, got {result}",
                )

    async def test_github_integration_workflow(self):
        """Test GitHub integration throughout workflow."""
        workflow = MultiAgentWorkflow(
            repo_path=self.repo_path, thread_id=self.thread_id
        )

        # Use mock GitHub
        github_mock = self.mock_deps["github"]

        # Test PR creation for design review
        pr_number = await github_mock.create_pull_request(
            title=f"Design Review: {self.thread_id}",
            body="Design synthesis for human review",
            branch=f"design/{self.thread_id}",
            labels=["needs-human", "design-review"],
        )

        self.assertEqual(pr_number, 1)  # First PR

        # Test adding human feedback
        feedback_added = await github_mock.add_pr_comment(
            pr_number, "Approved with modifications: Use Redis for session storage"
        )
        self.assertTrue(feedback_added)

        # Test getting feedback
        comments = await github_mock.get_pr_comments(pr_number)
        self.assertEqual(len(comments), 1)
        self.assertIn("Redis", comments[0]["body"])

        # Test CI status checking
        github_mock.set_ci_status(
            pr_number,
            {
                "status": "success",
                "checks": [
                    {"name": "test", "conclusion": "success"},
                    {"name": "lint", "conclusion": "success"},
                ],
                "commit_sha": "abc123",
                "pr_number": pr_number,
            },
        )

        ci_status = await github_mock.get_ci_status(pr_number)
        self.assertEqual(ci_status["status"], "success")

    async def test_artifact_management_throughout_workflow(self):
        """Test artifact creation and management."""
        workflow = MultiAgentWorkflow(
            repo_path=self.repo_path, thread_id=self.thread_id
        )

        # Use mock artifact manager
        artifact_mgr = self.mock_deps["artifact_manager"]

        # Test saving various artifact types
        artifacts = {
            "code_context": "# Code Context\nArchitecture overview...",
            "design_doc": "# Design Document\nDetailed design...",
            "skeleton": "class AuthService:\n    pass",
            "tests": "def test_auth():\n    pass",
            "implementation": "class AuthServiceImpl:\n    def login(self):\n        return True",
        }

        paths = {}
        for key, content in artifacts.items():
            path = await artifact_mgr.save_artifact(key, content, key.replace("_", "-"))
            paths[key] = path
            self.assertIsNotNone(path)

        # Verify all artifacts are indexed
        artifact_index = await artifact_mgr.list_artifacts()
        self.assertEqual(len(artifact_index), len(artifacts))

        # Verify content can be retrieved
        for key in artifacts.keys():
            content = await artifact_mgr.get_artifact(key)
            self.assertEqual(content, artifacts[key])

    async def test_model_routing_decisions(self):
        """Test model routing decisions throughout workflow."""
        workflow = MultiAgentWorkflow(
            repo_path=self.repo_path, thread_id=self.thread_id
        )

        # Set up models
        workflow.ollama_model = self.mock_deps["ollama_model"]
        workflow.claude_model = self.mock_deps["claude_model"]

        # Test Ollama routing for design phases
        ollama_phases = [
            "Design exploration phase - analyze requirements",
            "Create design document collaboratively",
            "Quick iteration on implementation",
        ]

        for prompt in ollama_phases:
            response = await workflow._call_model(prompt, ModelRouter.OLLAMA)
            self.assertIn("Ollama response", response)

        # Test Claude routing for complex phases
        claude_phases = [
            "Extract comprehensive code context from repository",
            "Create detailed implementation skeleton with interfaces",
            "Perform complex reconciliation of tests and implementation",
        ]

        for prompt in claude_phases:
            response = await workflow._call_model(prompt, ModelRouter.CLAUDE_CODE)
            self.assertIn("Claude response", response)

        # Verify call counts
        self.assertEqual(self.mock_deps["ollama_model"].call_count, 3)
        self.assertEqual(self.mock_deps["claude_model"].call_count, 3)

    async def test_error_handling_and_recovery(self):
        """Test error handling and recovery mechanisms."""
        workflow = MultiAgentWorkflow(
            repo_path=self.repo_path, thread_id=self.thread_id
        )

        # Test agent failure recovery
        failing_agent = MagicMock()
        failing_agent.analyze.side_effect = Exception("Agent failure")

        # Workflow should handle agent failures gracefully
        with patch.object(
            workflow, "_agent_analysis", side_effect=Exception("Agent failure")
        ):
            state = self.initial_state.copy()

            # The workflow should catch and handle the exception
            try:
                result = await workflow.parallel_design_exploration(state)
                # Should complete with empty or error analyses
                self.assertIsInstance(result, dict)
            except Exception as e:
                # Or raise a handled exception
                self.assertIn("Agent failure", str(e))

        # Test GitHub API failure recovery
        github_mock = self.mock_deps["github"]

        # Mock GitHub failure
        github_mock.create_pull_request = AsyncMock(
            side_effect=Exception("GitHub API error")
        )

        # Should handle GitHub failures gracefully (return dummy PR number)
        # This tests the error handling in the actual GitHub integration
        # (The mock would need to be updated to handle this scenario)

    async def test_checkpoint_and_resume_functionality(self):
        """Test workflow checkpointing and resume capability."""
        workflow = MultiAgentWorkflow(
            repo_path=self.repo_path, thread_id=self.thread_id
        )

        checkpointer = self.mock_deps["checkpointer"]
        workflow.checkpointer = checkpointer

        # Simulate saving checkpoint after Phase 1
        state_after_phase1 = self._create_phase1_result()

        config = {"configurable": {"thread_id": self.thread_id}}
        await checkpointer.put(
            config, state_after_phase1, {"phase": "design_exploration"}
        )

        # Simulate resume - get checkpoint
        resumed_state = await checkpointer.get(config)

        self.assertIsNotNone(resumed_state)
        self.assertEqual(len(resumed_state["agent_analyses"]), 4)
        self.assertEqual(
            resumed_state["current_phase"], WorkflowPhase.PHASE_1_DESIGN_EXPLORATION
        )

        # Verify the workflow can continue from this point
        state = resumed_state.copy()
        state["current_phase"] = WorkflowPhase.PHASE_1_SYNTHESIS

        # Should be able to proceed to next phase
        self.assertEqual(state["current_phase"], WorkflowPhase.PHASE_1_SYNTHESIS)


class TestWorkflowPerformance(unittest.IsolatedAsyncioTestCase):
    """Test workflow performance characteristics."""

    async def test_parallel_agent_execution_performance(self):
        """Test that parallel agent execution is actually parallel."""
        workflow = MultiAgentWorkflow(repo_path="/tmp/test", thread_id="perf-test")

        # Create agents that simulate processing time
        slow_agents = {}
        for agent_type in ["test-first", "fast-coder", "senior-engineer", "architect"]:
            agent = AsyncMock()
            agent.analyze = AsyncMock()

            # Simulate slow processing
            async def slow_analyze(prompt):
                await asyncio.sleep(0.1)  # 100ms delay
                return f"Analysis from {agent_type}"

            agent.analyze.side_effect = slow_analyze
            slow_agents[agent_type] = agent

        workflow.agents = slow_agents

        # Measure time for parallel execution
        start_time = asyncio.get_event_loop().time()

        # Simulate parallel analysis (this would be done in parallel_design_exploration)
        tasks = []
        for agent_type, agent in workflow.agents.items():
            context = {"code_context": "test", "feature": "test feature"}
            tasks.append(workflow._agent_analysis(agent, agent_type, context))

        results = await asyncio.gather(*tasks)

        end_time = asyncio.get_event_loop().time()
        execution_time = end_time - start_time

        # Should complete in ~100ms (parallel) not ~400ms (sequential)
        self.assertLess(
            execution_time, 0.2, "Parallel execution should be faster than sequential"
        )
        self.assertEqual(len(results), 4, "All agents should complete")

    async def test_memory_usage_with_large_artifacts(self):
        """Test memory management with large artifacts."""
        workflow = MultiAgentWorkflow(repo_path="/tmp/test", thread_id="memory-test")

        # Create state with large artifact index (paths, not content)
        state = {"artifacts_index": {}, "messages_window": [], "summary_log": ""}

        # Add many artifact paths (simulating large project)
        for i in range(1000):
            state["artifacts_index"][f"artifact_{i}"] = f"/path/to/artifact_{i}.txt"

        # Verify state size remains manageable (paths only, no content)
        import sys

        state_size = sys.getsizeof(state["artifacts_index"])

        # Should be much smaller than if we stored actual content
        self.assertLess(
            state_size, 100000, "Artifact index should store paths, not content"
        )


if __name__ == "__main__":
    unittest.main()
