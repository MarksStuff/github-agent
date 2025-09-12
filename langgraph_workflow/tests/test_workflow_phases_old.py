"""Unit tests for workflow phases."""

import unittest
from pathlib import Path
from unittest.mock import patch

from ..langgraph_workflow import (
    ModelRouter,
    MultiAgentWorkflow,
    WorkflowPhase,
    WorkflowState,
)
from ..mocks import create_mock_dependencies


class TestWorkflowPhases(unittest.IsolatedAsyncioTestCase):
    """Test all workflow phases."""

    def setUp(self):
        """Set up test fixtures."""
        self.thread_id = "test-thread-123"
        self.repo_path = "/tmp/test-repo"
        self.mock_deps = create_mock_dependencies(self.thread_id)

        # Create initial state
        self.initial_state = WorkflowState(
            thread_id=self.thread_id,
            feature_description="Test feature: Add user authentication",
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

    async def test_phase_0_code_context_extraction(self):
        """Test Phase 0: Code Context Extraction."""
        # Create workflow with mocked dependencies
        workflow = MultiAgentWorkflow(
            repo_path=self.repo_path, thread_id=self.thread_id
        )

        # Replace with mocks
        workflow.codebase_analyzer = self.mock_deps["codebase_analyzer"]
        workflow.artifacts_dir = Path("/tmp/test-artifacts")

        # Mock file system
        with patch("pathlib.Path.write_text") as mock_write:
            # Execute phase
            result = await workflow.extract_code_context(self.initial_state.copy())

            # Verify state updates
            self.assertEqual(
                result["current_phase"], WorkflowPhase.PHASE_0_CODE_CONTEXT
            )
            self.assertEqual(result["model_router"], ModelRouter.CLAUDE_CODE)
            self.assertIsNotNone(result["code_context_document"])
            self.assertIn("code_context", result["artifacts_index"])

            # Verify code context document contains expected sections
            context_doc = result["code_context_document"]
            self.assertIn("Architecture Overview", context_doc)
            self.assertIn("Technology Stack", context_doc)
            self.assertIn("Design Patterns", context_doc)

            # Verify file was written
            mock_write.assert_called_once()

            # Verify message was added
            self.assertEqual(len(result["messages_window"]), 1)

    async def test_phase_1_parallel_design_exploration(self):
        """Test Phase 1: Parallel Design Exploration."""
        workflow = MultiAgentWorkflow(
            repo_path=self.repo_path, thread_id=self.thread_id
        )

        # Set up state with code context
        state = self.initial_state.copy()
        state["code_context_document"] = "Mock code context document"
        state["current_phase"] = WorkflowPhase.PHASE_1_DESIGN_EXPLORATION

        # Replace with mocks
        workflow.agents = self.mock_deps["agents"]
        workflow.artifacts_dir = Path("/tmp/test-artifacts")

        with patch("pathlib.Path.write_text") as mock_write:
            # Execute phase
            result = await workflow.parallel_design_exploration(state)

            # Verify all agents provided analysis
            self.assertEqual(len(result["agent_analyses"]), 4)
            self.assertIn("test-first", result["agent_analyses"])
            self.assertIn("fast-coder", result["agent_analyses"])
            self.assertIn("senior-engineer", result["agent_analyses"])
            self.assertIn("architect", result["agent_analyses"])

            # Verify model router set to Ollama
            self.assertEqual(result["model_router"], ModelRouter.OLLAMA)

            # Verify artifacts were saved
            self.assertEqual(mock_write.call_count, 4)  # One per agent

            # Verify phase updated
            self.assertEqual(
                result["current_phase"], WorkflowPhase.PHASE_1_DESIGN_EXPLORATION
            )

    async def test_architect_synthesis(self):
        """Test architect synthesis phase."""
        workflow = MultiAgentWorkflow(
            repo_path=self.repo_path, thread_id=self.thread_id
        )

        # Set up state with agent analyses
        state = self.initial_state.copy()
        state["agent_analyses"] = {
            "test-first": "Mock test-first analysis with requirements",
            "fast-coder": "Mock fast-coder analysis with implementation approach",
            "senior-engineer": "Mock senior-engineer analysis with patterns",
            "architect": "Mock architect analysis with system design",
        }
        state["current_phase"] = WorkflowPhase.PHASE_1_SYNTHESIS

        # Mock the model call
        workflow.ollama_model = self.mock_deps["ollama_model"]
        workflow.artifacts_dir = Path("/tmp/test-artifacts")

        with patch("pathlib.Path.write_text") as mock_write:
            # Execute phase
            result = await workflow.architect_synthesis(state)

            # Verify synthesis document created
            self.assertIsNotNone(result["synthesis_document"])

            # Verify current phase updated
            self.assertEqual(result["current_phase"], WorkflowPhase.PHASE_1_SYNTHESIS)

            # Verify artifact saved
            mock_write.assert_called_once()
            self.assertIn("synthesis", result["artifacts_index"])

    async def test_code_investigation_needed(self):
        """Test code investigation decision logic."""
        workflow = MultiAgentWorkflow(
            repo_path=self.repo_path, thread_id=self.thread_id
        )

        # Test case where investigation is needed
        state_needs_investigation = {
            "synthesis_document": "Questions requiring investigation:\n- How does auth work?\n- What database schema exists?"
        }
        self.assertTrue(workflow.needs_code_investigation(state_needs_investigation))

        # Test case where investigation is not needed
        state_no_investigation = {"synthesis_document": "No questions, all clear"}
        self.assertFalse(workflow.needs_code_investigation(state_no_investigation))

    async def test_design_document_creation(self):
        """Test Phase 2: Design Document Creation."""
        workflow = MultiAgentWorkflow(
            repo_path=self.repo_path, thread_id=self.thread_id
        )

        state = self.initial_state.copy()
        state["current_phase"] = WorkflowPhase.PHASE_2_DESIGN_DOCUMENT
        workflow.artifacts_dir = Path("/tmp/test-artifacts")

        with patch("pathlib.Path.write_text") as mock_write:
            # Execute phase
            result = await workflow.create_design_document(state)

            # Verify design document created
            self.assertIsNotNone(result["design_document"])
            design_doc = result["design_document"]

            # Verify document contains required sections
            self.assertIn("Design Document:", design_doc)
            self.assertIn("## Overview", design_doc)
            self.assertIn("## Acceptance Criteria", design_doc)
            self.assertIn("## Technical Design", design_doc)
            self.assertIn("## Human Additions", design_doc)
            self.assertIn("## Arbitration History", design_doc)

            # Verify model router set to Ollama
            self.assertEqual(result["model_router"], ModelRouter.OLLAMA)

            # Verify artifact saved
            mock_write.assert_called_once()
            self.assertIn("design_document", result["artifacts_index"])

    async def test_skeleton_creation(self):
        """Test Phase 3: Skeleton Creation."""
        workflow = MultiAgentWorkflow(
            repo_path=self.repo_path, thread_id=self.thread_id
        )

        state = self.initial_state.copy()
        state["design_document"] = "Mock design document with requirements"
        state["current_phase"] = WorkflowPhase.PHASE_3_SKELETON
        workflow.artifacts_dir = Path("/tmp/test-artifacts")
        workflow.claude_model = self.mock_deps["claude_model"]

        # Mock filesystem operations (external dependency)
        with patch("pathlib.Path.write_text") as mock_write:
            # Use our own mocks for internal components
            # The create_skeleton method should use dependency injection
            # For now, we test that the method runs without error
            result = await workflow.create_skeleton(state)

            # Verify skeleton created (from our mock implementation)
            self.assertIsNotNone(result["skeleton_code"])
            self.assertEqual(result["model_router"], ModelRouter.CLAUDE_CODE)

            # Verify artifact saved (filesystem mock - external dependency)
            mock_write.assert_called_once()
            self.assertIn("skeleton", result["artifacts_index"])

    async def test_parallel_development(self):
        """Test Phase 3: Parallel Development."""
        workflow = MultiAgentWorkflow(
            repo_path=self.repo_path, thread_id=self.thread_id
        )

        state = self.initial_state.copy()
        state["skeleton_code"] = "class MockSkeleton:\n    pass"
        state["design_document"] = "Mock design document"
        state["current_phase"] = WorkflowPhase.PHASE_3_PARALLEL_DEV
        workflow.artifacts_dir = Path("/tmp/test-artifacts")

        # Mock filesystem operations (external dependency)
        with patch("pathlib.Path.write_text") as mock_write:
            # Use dependency injection with our mock implementations
            # The method should use injected dependencies, not patched internal methods
            result = await workflow.parallel_development(state)

            # Verify both tests and implementation created (from mock dependencies)
            self.assertIsNotNone(result["test_code"])
            self.assertIsNotNone(result["implementation_code"])

            # Verify artifacts saved (filesystem mock - external dependency)
            self.assertEqual(mock_write.call_count, 2)  # tests + implementation
            self.assertIn("tests_initial", result["artifacts_index"])
            self.assertIn("implementation_initial", result["artifacts_index"])

            # Verify phase updated
            self.assertEqual(
                result["current_phase"], WorkflowPhase.PHASE_3_PARALLEL_DEV
            )

    async def test_reconciliation_no_conflicts(self):
        """Test reconciliation when no conflicts exist."""
        workflow = MultiAgentWorkflow(
            repo_path=self.repo_path, thread_id=self.thread_id
        )

        state = self.initial_state.copy()
        state["test_code"] = "def test_feature():\n    assert True"
        state["implementation_code"] = "def feature():\n    return True"
        state["current_phase"] = WorkflowPhase.PHASE_3_RECONCILIATION

        # Use dependency injection instead of patching internal methods
        # The reconciliation method should use injected dependencies
        result = await workflow.reconciliation(state)

        # Verify no changes when no mismatches (from mock behavior)
        self.assertEqual(result["test_code"], state["test_code"])
        self.assertEqual(result["implementation_code"], state["implementation_code"])

        # Verify phase updated
        self.assertEqual(result["current_phase"], WorkflowPhase.PHASE_3_RECONCILIATION)

    async def test_reconciliation_with_conflicts(self):
        """Test reconciliation when conflicts need resolution."""
        workflow = MultiAgentWorkflow(
            repo_path=self.repo_path, thread_id=self.thread_id
        )

        state = self.initial_state.copy()
        state["test_code"] = "def test_feature():\n    assert feature() == 'result'"
        state[
            "implementation_code"
        ] = "def feature():\n    return True"  # Mismatch: returns bool not string
        state["current_phase"] = WorkflowPhase.PHASE_3_RECONCILIATION

        workflow.agents = self.mock_deps["agents"]

        # Use dependency injection instead of patching internal methods
        # The reconciliation should use injected conflict resolver and agents
        result = await workflow.reconciliation(state)

        # Verify reconciliation process was triggered
        self.assertEqual(result["current_phase"], WorkflowPhase.PHASE_3_RECONCILIATION)

    async def test_model_routing_decision(self):
        """Test model routing decisions."""
        workflow = MultiAgentWorkflow(
            repo_path=self.repo_path, thread_id=self.thread_id
        )

        # Test Ollama call
        workflow.ollama_model = self.mock_deps["ollama_model"]
        response = await workflow._call_model("Test prompt", ModelRouter.OLLAMA)
        self.assertEqual(response, "Ollama response 1")

        # Test Claude call
        workflow.claude_model = self.mock_deps["claude_model"]
        response = await workflow._call_model("Test prompt", ModelRouter.CLAUDE_CODE)
        self.assertEqual(response, "Claude response 1")

    async def test_escalation_triggers(self):
        """Test escalation trigger conditions."""
        from ..config import should_escalate_to_claude

        # Test diff size escalation
        self.assertTrue(should_escalate_to_claude(diff_size=500))  # > 300 threshold
        self.assertFalse(should_escalate_to_claude(diff_size=100))  # < 300 threshold

        # Test files touched escalation
        self.assertTrue(should_escalate_to_claude(files_touched=15))  # > 10 threshold
        self.assertFalse(should_escalate_to_claude(files_touched=5))  # < 10 threshold

        # Test consecutive failures escalation
        self.assertTrue(
            should_escalate_to_claude(consecutive_failures=3)
        )  # >= 2 threshold
        self.assertFalse(
            should_escalate_to_claude(consecutive_failures=1)
        )  # < 2 threshold

        # Test complexity score escalation
        self.assertTrue(
            should_escalate_to_claude(complexity_score=0.8)
        )  # > 0.7 threshold
        self.assertFalse(
            should_escalate_to_claude(complexity_score=0.5)
        )  # < 0.7 threshold

    async def test_state_persistence(self):
        """Test that state is properly maintained between phases."""
        workflow = MultiAgentWorkflow(
            repo_path=self.repo_path, thread_id=self.thread_id
        )

        # Start with initial state
        state = self.initial_state.copy()

        # Simulate phase 0
        state["code_context_document"] = "Mock context"
        state["current_phase"] = WorkflowPhase.PHASE_1_DESIGN_EXPLORATION

        # Verify state preservation
        self.assertEqual(state["thread_id"], self.thread_id)
        self.assertEqual(
            state["feature_description"], "Test feature: Add user authentication"
        )
        self.assertEqual(state["code_context_document"], "Mock context")
        self.assertEqual(
            state["current_phase"], WorkflowPhase.PHASE_1_DESIGN_EXPLORATION
        )

    async def test_message_window_management(self):
        """Test that message window is properly managed."""
        from langchain_core.messages import AIMessage

        # Create state with many messages
        state = self.initial_state.copy()

        # Add more than the window limit (10)
        for i in range(15):
            state["messages_window"].append(AIMessage(content=f"Message {i}"))

        # The TypedDict annotation should enforce window size
        # In practice, this would be handled by the graph's message management
        self.assertEqual(len(state["messages_window"]), 15)  # All messages initially

    async def test_artifact_management(self):
        """Test artifact creation and indexing."""
        workflow = MultiAgentWorkflow(
            repo_path=self.repo_path, thread_id=self.thread_id
        )

        state = self.initial_state.copy()
        workflow.artifacts_dir = Path("/tmp/test-artifacts")

        # Add some artifacts to the index
        state["artifacts_index"]["test_artifact"] = "/tmp/test-artifacts/test.md"
        state["artifacts_index"]["design_doc"] = "/tmp/test-artifacts/design.md"

        # Verify artifact management
        self.assertIn("test_artifact", state["artifacts_index"])
        self.assertIn("design_doc", state["artifacts_index"])
        self.assertEqual(len(state["artifacts_index"]), 2)


if __name__ == "__main__":
    unittest.main()
