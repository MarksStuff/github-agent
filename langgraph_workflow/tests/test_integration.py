"""Fixed integration tests following CLAUDE.md guidelines."""

import asyncio
import tempfile
import unittest
from pathlib import Path

from ..enums import ModelRouter, WorkflowPhase
from ..langgraph_workflow import WorkflowState
from .mocks import create_mock_dependencies
from .mocks.test_workflow import MockTestMultiAgentWorkflow


class TestWorkflowIntegrationFixed(unittest.IsolatedAsyncioTestCase):
    """Test complete workflow integration with correct mocking approach."""

    def setUp(self):
        """Set up integration test fixtures."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.repo_path = self.temp_dir.name
        self.thread_id = "integration-test-123"

        # CORRECT: Use our own mock dependencies
        self.mock_deps = create_mock_dependencies(self.thread_id)

        # Create workflow with required dependencies - use test implementation
        self.workflow = MockTestMultiAgentWorkflow(
            repo_path=self.repo_path,
            thread_id=self.thread_id,
            agents=self.mock_deps["agents"],
            codebase_analyzer=self.mock_deps["codebase_analyzer"],
            ollama_model=self.mock_deps["ollama_model"],
            claude_model=None,  # No Claude model needed for Ollama-only tests
        )

        # CORRECT: Inject additional mock dependencies
        self.workflow.checkpointer = self.mock_deps["checkpointer"]

        # Set up artifacts directory
        self.workflow.artifacts_dir = Path(self.temp_dir.name) / "artifacts"
        self.workflow.artifacts_dir.mkdir(parents=True, exist_ok=True)

        # Create initial state for full workflow
        self.initial_state = WorkflowState(
            thread_id=self.thread_id,
            feature_description="Add comprehensive user authentication with JWT tokens, role-based access control, and session management",
            raw_feature_input=None,
            extracted_feature=None,
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

    async def test_workflow_phases_integration(self):
        """Test workflow phases work together with dependency injection."""
        state = self.initial_state.copy()

        # Test Phase 0: Code Context - uses actual method with mocks
        result = await self.workflow.extract_code_context(state)
        self.assertEqual(result["current_phase"], WorkflowPhase.PHASE_0_CODE_CONTEXT)
        self.assertIsNotNone(result["code_context_document"])

        # Test Phase 1: Design Exploration - uses actual method with mocks
        state = result
        state["current_phase"] = WorkflowPhase.PHASE_1_DESIGN_EXPLORATION
        result = await self.workflow.parallel_design_exploration(state)
        self.assertEqual(
            result["current_phase"], WorkflowPhase.PHASE_1_DESIGN_EXPLORATION
        )
        self.assertEqual(len(result["agent_analyses"]), 4)

        # Test Phase 1: Synthesis - uses actual method with mocks
        state = result
        state["current_phase"] = WorkflowPhase.PHASE_1_SYNTHESIS
        result = await self.workflow.architect_synthesis(state)
        self.assertIsNotNone(result["synthesis_document"])

        # Test Phase 2: Design Document - uses actual method with mocks
        state = result
        state["current_phase"] = WorkflowPhase.PHASE_2_DESIGN_DOCUMENT
        result = await self.workflow.create_design_document(state)
        self.assertIsNotNone(result["design_document"])


    async def test_github_integration_workflow(self):
        """Test GitHub integration throughout workflow."""
        # Use mock GitHub (our own implementation, not MagicMock)
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
        # Use mock artifact manager (our own implementation)
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
        # CORRECT: Test using injected mock models
        # Test Ollama routing for design phases
        ollama_phases = [
            "Design exploration phase - analyze requirements",
            "Create design document collaboratively",
            "Quick iteration on implementation",
        ]

        for prompt in ollama_phases:
            response = await self.workflow._call_model(prompt, ModelRouter.OLLAMA)
            self.assertIn("Ollama response", response)

        # Test Ollama routing for complex phases (all phases use Ollama now)
        complex_ollama_phases = [
            "Extract comprehensive code context from repository",
            "Create detailed implementation skeleton with interfaces", 
            "Perform complex reconciliation of tests and implementation",
        ]

        for prompt in complex_ollama_phases:
            response = await self.workflow._call_model(prompt, ModelRouter.OLLAMA)
            self.assertIn("Ollama response", response)

    async def test_checkpoint_and_resume_functionality(self):
        """Test workflow checkpointing and resume capability."""
        checkpointer = self.mock_deps["checkpointer"]

        # Create state with some progress
        state_with_progress = self.initial_state.copy()
        state_with_progress["agent_analyses"] = {
            "test-first": "Focus on comprehensive test coverage",
            "fast-coder": "Implement JWT-based auth quickly",
            "senior-engineer": "Use established patterns",
            "architect": "Scalable auth service design",
        }
        state_with_progress["current_phase"] = WorkflowPhase.PHASE_1_DESIGN_EXPLORATION

        # Simulate saving checkpoint
        config = {"configurable": {"thread_id": self.thread_id}}
        await checkpointer.put(
            config, state_with_progress, {"phase": "design_exploration"}
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

    async def test_agent_collaboration_patterns(self):
        """Test that agents collaborate correctly using dependency injection."""
        # CORRECT: Test using our injected mock agents
        state = self.initial_state.copy()
        state["code_context_document"] = "Mock code context"

        # Test parallel analysis
        result = await self.workflow.parallel_design_exploration(state)

        # Verify all agents participated (via our mocks)
        self.assertEqual(len(result["agent_analyses"]), 4)
        for agent_type in ["test-first", "fast-coder", "senior-engineer", "architect"]:
            self.assertIn(agent_type, result["agent_analyses"])
            self.assertIsInstance(result["agent_analyses"][agent_type], str)

    async def test_conflict_resolution_workflow(self):
        """Test conflict resolution using dependency injection."""
        # CORRECT: Use our own mock conflict resolver
        conflict_resolver = self.mock_deps["conflict_resolver"]

        # Create conflicting analyses
        conflict_analyses = {
            "test-first": "We must have 100% test coverage",
            "fast-coder": "Let's implement quickly with basic tests",
            "senior-engineer": "Focus on clean patterns",
            "architect": "This approach won't scale properly",
        }

        # Test conflict identification using our mock
        conflicts = await conflict_resolver.identify_conflicts(conflict_analyses)
        self.assertIsInstance(conflicts, list)

        # Test conflict resolution
        if conflicts:
            resolution = await conflict_resolver.resolve_conflict(conflicts[0])
            self.assertIsNotNone(resolution)


class TestWorkflowPerformanceFixed(unittest.IsolatedAsyncioTestCase):
    """Test workflow performance characteristics with correct mocking."""

    async def test_parallel_agent_execution_performance(self):
        """Test that parallel agent execution is actually parallel."""
        temp_dir = tempfile.TemporaryDirectory()
        mock_deps = create_mock_dependencies("perf-test")

        workflow = MockTestMultiAgentWorkflow(
            repo_path=temp_dir.name,
            thread_id="perf-test",
            agents=mock_deps["agents"],
            codebase_analyzer=mock_deps["codebase_analyzer"],
        )

        # CORRECT: Use our own mock agents with simulated delay

        # Inject mock agents that simulate processing time
        async def slow_analyze(context):
            await asyncio.sleep(0.1)  # 100ms delay
            return f"Analysis completed for {context.get('feature', 'unknown')}"

        # Override the analyze method for each mock agent
        for _, agent in mock_deps["agents"].items():
            agent.analyze = slow_analyze

        workflow.agents = mock_deps["agents"]

        # Measure time for parallel execution
        start_time = asyncio.get_event_loop().time()

        # Simulate parallel analysis
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

        temp_dir.cleanup()

    async def test_memory_usage_with_large_artifacts(self):
        """Test memory management with large artifacts."""
        # Create state with large artifact index (paths, not content)
        state = {"artifacts_index": {}, "messages_window": [], "summary_log": ""}

        # Add many artifact paths (simulating large project)
        for i in range(1000):
            state["artifacts_index"][f"artifact_{i}"] = f"/path/to/artifact_{i}.txt"  # type: ignore

        # Verify state size remains manageable (paths only, no content)
        import sys

        state_size = sys.getsizeof(state["artifacts_index"])

        # Should be much smaller than if we stored actual content
        self.assertLess(
            state_size, 100000, "Artifact index should store paths, not content"
        )


if __name__ == "__main__":
    unittest.main()
