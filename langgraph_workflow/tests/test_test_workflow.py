"""Tests for TestMultiAgentWorkflow to verify it works correctly."""

import tempfile
import unittest

from ..langgraph_workflow import WorkflowPhase
from .mocks.test_workflow import TestMultiAgentWorkflow


class TestTestMultiAgentWorkflow(unittest.IsolatedAsyncioTestCase):
    """Test the TestMultiAgentWorkflow implementation."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.repo_path = self.temp_dir.name
        self.test_workflow = TestMultiAgentWorkflow(repo_path=self.repo_path)

    def tearDown(self):
        """Clean up test fixtures."""
        self.test_workflow.cleanup()
        self.temp_dir.cleanup()

    async def test_initialization(self):
        """Test that TestMultiAgentWorkflow initializes correctly."""
        # Verify basic attributes
        self.assertIsNotNone(self.test_workflow.thread_id)
        self.assertTrue(self.test_workflow.thread_id.startswith("test-"))
        self.assertEqual(str(self.test_workflow.repo_path), self.repo_path)

        # Verify test dependencies are created
        self.assertIsNotNone(self.test_workflow.agents)
        self.assertEqual(len(self.test_workflow.agents), 4)
        self.assertIsNotNone(self.test_workflow.ollama_model)
        self.assertIsNotNone(self.test_workflow.claude_model)
        self.assertIsNotNone(self.test_workflow.codebase_analyzer)
        self.assertIsNotNone(self.test_workflow.github)

        # Verify LangGraph structure
        self.assertIsNotNone(self.test_workflow.graph)
        self.assertIsNotNone(self.test_workflow.app)

    async def test_extract_code_context(self):
        """Test the extract_code_context method with test dependencies."""
        # Create initial state
        initial_state = self.test_workflow.create_test_initial_state(
            "Add user authentication system"
        )

        # Execute the phase
        result = await self.test_workflow.extract_code_context(initial_state)

        # Verify state updates
        self.assertEqual(result["current_phase"], WorkflowPhase.PHASE_0_CODE_CONTEXT)
        self.assertIsNotNone(result["code_context_document"])
        self.assertIn("code_context", result["artifacts_index"])

        # Verify content is realistic
        context_doc = result["code_context_document"]
        self.assertIn("Code Context Document", context_doc)
        self.assertIn("Architecture Overview", context_doc)
        self.assertIn("Technology Stack", context_doc)
        self.assertIn("Python", context_doc)
        self.assertIn("FastAPI", context_doc)

    async def test_create_design_document(self):
        """Test design document creation."""
        # Create state with agent analyses
        state = self.test_workflow.create_test_initial_state(
            "Add user authentication system"
        )
        state["agent_analyses"] = {
            "test-first": "Authentication tests needed",
            "fast-coder": "Quick JWT implementation",
            "senior-engineer": "Secure authentication with OAuth2",
            "architect": "Microservice authentication design",
        }

        # Execute the phase
        result = await self.test_workflow.create_design_document(state)

        # Verify document creation
        self.assertIsNotNone(result["design_document"])
        self.assertIn("design_document", result["artifacts_index"])

        design_doc = result["design_document"]
        self.assertIn("Design Document:", design_doc)
        self.assertIn("## Overview", design_doc)
        self.assertIn("## Acceptance Criteria", design_doc)
        self.assertIn("## Technical Design", design_doc)

    async def test_agent_pattern_responses(self):
        """Test that agents respond intelligently based on feature patterns."""
        # Test authentication feature
        auth_response = self.test_workflow.agents["test-first"].ask(
            "Analyze authentication feature requirements"
        )
        self.assertIn("login validation", auth_response)
        self.assertIn("JWT token", auth_response)

        # Test dashboard feature
        dashboard_response = self.test_workflow.agents["architect"].ask(
            "Design dashboard architecture"
        )
        self.assertIn("Frontend architecture", dashboard_response)
        self.assertIn("state management", dashboard_response)

        # Test default response
        default_response = self.test_workflow.agents["senior-engineer"].ask(
            "Unknown feature request"
        )
        self.assertIn("Production-ready", default_response)

    async def test_codebase_analyzer_responses(self):
        """Test that codebase analyzer provides realistic responses."""
        analysis = await self.test_workflow.codebase_analyzer.analyze()

        # Verify structure
        self.assertIn("architecture", analysis)
        self.assertIn("languages", analysis)
        self.assertIn("frameworks", analysis)
        self.assertIn("patterns", analysis)

        # Verify content is realistic
        self.assertIn("Python", analysis["languages"])
        self.assertIn("FastAPI", analysis["frameworks"])
        self.assertIsInstance(analysis["complexity_score"], (int, float))

    async def test_feature_impact_analysis(self):
        """Test feature impact analysis patterns."""
        # Test authentication impact
        auth_impact = self.test_workflow.codebase_analyzer.analyze_feature_impact(
            "User login and authentication system"
        )

        self.assertEqual(auth_impact["complexity"], "medium")
        self.assertIn("src/auth/", auth_impact["affected_files"])
        self.assertIn("JWT library", auth_impact["dependencies"])

        # Test dashboard impact
        dashboard_impact = self.test_workflow.codebase_analyzer.analyze_feature_impact(
            "Analytics dashboard with charts"
        )

        self.assertEqual(dashboard_impact["complexity"], "medium")
        self.assertIn("frontend/src/components/", dashboard_impact["affected_files"])

    async def test_workflow_state_creation(self):
        """Test creating test workflow states."""
        state = self.test_workflow.create_test_initial_state(
            "Test feature implementation"
        )

        # Verify state structure
        self.assertEqual(state["thread_id"], self.test_workflow.thread_id)
        self.assertEqual(state["feature_description"], "Test feature implementation")
        self.assertEqual(state["current_phase"], WorkflowPhase.PHASE_0_CODE_CONTEXT)
        self.assertEqual(state["quality"], "draft")
        self.assertEqual(state["feedback_gate"], "open")
        self.assertIsInstance(state["messages_window"], list)
        self.assertIsInstance(state["artifacts_index"], dict)

    async def test_test_results_collection(self):
        """Test collecting test results for assertions."""
        # Run a simple operation
        await self.test_workflow.agents["test-first"].analyze(
            "Create tests for feature"
        )

        # Get test results
        results = self.test_workflow.get_test_results()

        # Verify results structure
        self.assertIn("artifacts_created", results)
        self.assertIn("agent_responses", results)
        self.assertIn("filesystem_operations", results)

        # Verify agent history is captured
        self.assertIn("test-first", results["agent_responses"])
        agent_history = results["agent_responses"]["test-first"]
        self.assertGreater(len(agent_history), 0)

    def test_cleanup(self):
        """Test that cleanup works correctly."""
        # Verify artifacts directory exists before cleanup
        self.assertTrue(self.test_workflow.artifacts_dir.exists())

        # Run cleanup
        self.test_workflow.cleanup()

        # Note: artifacts_dir might still exist as it's a subdirectory
        # of the temp directory, but test_fs should be cleaned up

    async def test_real_workflow_execution(self):
        """Test that the workflow can actually execute phases."""
        # Create initial state
        initial_state = self.test_workflow.create_test_initial_state(
            "Add user authentication with JWT tokens"
        )

        # Execute code context phase
        state1 = await self.test_workflow.extract_code_context(initial_state)

        # Verify it progressed correctly
        self.assertEqual(state1["current_phase"], WorkflowPhase.PHASE_0_CODE_CONTEXT)
        self.assertIsNotNone(state1["code_context_document"])

        # Execute design document phase
        state2 = await self.test_workflow.create_design_document(state1)

        # Verify it progressed correctly
        self.assertEqual(state2["current_phase"], WorkflowPhase.PHASE_2_DESIGN_DOCUMENT)
        self.assertIsNotNone(state2["design_document"])

        # Verify both artifacts exist
        self.assertIn("code_context", state2["artifacts_index"])
        self.assertIn("design_document", state2["artifacts_index"])


if __name__ == "__main__":
    unittest.main()
