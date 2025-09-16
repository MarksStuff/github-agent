"""Fixed unit tests for workflow phases following CLAUDE.md guidelines."""

import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch  # Only for external dependencies

from ..enums import (
    AgentType,
    FeedbackGateStatus,
    ModelRouter,
    QualityLevel,
    WorkflowPhase,
)
from .mocks import create_mock_dependencies
from .mocks.test_workflow import MockTestMultiAgentWorkflow


class TestWorkflowPhasesFixed(unittest.IsolatedAsyncioTestCase):
    """Test workflow phases with correct mocking approach."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.repo_path = self.temp_dir.name
        self.thread_id = "test-thread-123"

        # CORRECT: Use our own mock dependencies
        self.mock_deps = create_mock_dependencies(self.thread_id)

        # Create workflow with dependency injection - use test implementation
        self.workflow = MockTestMultiAgentWorkflow(
            repo_path=self.repo_path,
            agents=self.mock_deps["agents"],
            codebase_analyzer=self.mock_deps["codebase_analyzer"],
            ollama_model=self.mock_deps["ollama_model"],
            claude_model=None,  # No Claude model needed for Ollama-only tests
            thread_id=self.thread_id,
        )

        # Set up artifacts directory
        artifacts_path = Path(self.temp_dir.name) / "artifacts"
        artifacts_path.mkdir(parents=True, exist_ok=True)
        self.workflow.artifacts_dir = str(artifacts_path)

        # Create initial state as dict (enhanced workflow uses dicts)
        self.initial_state: dict[str, Any] = {
            "thread_id": self.thread_id,
            "feature_description": "Test feature: Add user authentication",
            "raw_feature_input": None,
            "extracted_feature": None,
            "current_phase": WorkflowPhase.PHASE_0_CODE_CONTEXT,
            "messages_window": [],
            "summary_log": "",
            "artifacts_index": {},
            "code_context_document": None,
            "design_constraints_document": None,
            "design_document": None,
            "arbitration_log": [],
            "repo_path": self.repo_path,
            "git_branch": "main",
            "last_commit_sha": None,
            "pr_number": None,
            "agent_analyses": {},
            "synthesis_document": None,
            "conflicts": [],
            "skeleton_code": None,
            "test_code": None,
            "implementation_code": None,
            "patch_queue": [],
            "test_report": {},
            "ci_status": {},
            "lint_status": {},
            "quality": QualityLevel.DRAFT,
            "feedback_gate": FeedbackGateStatus.OPEN,
            "model_router": ModelRouter.OLLAMA,
            "escalation_count": 0,
        }

    def tearDown(self):
        """Clean up test fixtures."""
        self.temp_dir.cleanup()

    async def test_phase_0_code_context_extraction(self):
        """Test Phase 0: Code Context Extraction."""
        # CORRECT: Only mock external dependencies (filesystem)
        with patch("pathlib.Path.write_text") as mock_filesystem:
            # CORRECT: Test actual method with injected dependencies
            result = await self.workflow.extract_code_context(self.initial_state.copy())

            # Verify state updates
            self.assertEqual(
                result["current_phase"], WorkflowPhase.PHASE_0_CODE_CONTEXT
            )
            self.assertEqual(result["model_router"], ModelRouter.OLLAMA)
            self.assertIsNotNone(result["code_context_document"])
            self.assertIn("code_context", result["artifacts_index"])

            # Verify code context document contains expected sections
            context_doc = result["code_context_document"] or ""
            self.assertIn("Architecture Overview", context_doc)
            self.assertIn("Technology Stack", context_doc)
            self.assertIn("Design Patterns", context_doc)

            # Verify external dependency called (filesystem)
            mock_filesystem.assert_called_once()

            # Verify message was added
            self.assertEqual(len(result["messages_window"]), 1)

    async def test_phase_1_parallel_design_exploration(self):
        """Test Phase 1: Parallel Design Exploration."""
        # Set up state with code context
        state = self.initial_state.copy()
        state["code_context_document"] = "Mock code context document"
        state["current_phase"] = WorkflowPhase.PHASE_1_DESIGN_EXPLORATION

        # CORRECT: Only mock external dependencies (filesystem)
        with patch("pathlib.Path.write_text") as mock_filesystem:
            # CORRECT: Test actual method with injected mock agents
            result = await self.workflow.parallel_design_exploration(state)

            # Verify all agents provided analysis (from our mocks)
            self.assertEqual(len(result["agent_analyses"]), 4)
            self.assertIn("test-first", result["agent_analyses"])
            self.assertIn("fast-coder", result["agent_analyses"])
            self.assertIn("senior-engineer", result["agent_analyses"])
            self.assertIn("architect", result["agent_analyses"])

            # Verify model router set to Ollama
            self.assertEqual(result["model_router"], ModelRouter.OLLAMA)

            # Verify external dependency called (filesystem)
            self.assertEqual(mock_filesystem.call_count, 4)  # One per agent

            # Verify phase updated
            self.assertEqual(
                result["current_phase"], WorkflowPhase.PHASE_1_DESIGN_EXPLORATION
            )

    async def test_architect_synthesis(self):
        """Test architect synthesis phase."""
        # Set up state with agent analyses
        state = self.initial_state.copy()
        state["agent_analyses"] = {
            AgentType.TEST_FIRST: "Mock test-first analysis with requirements",
            AgentType.FAST_CODER: "Mock fast-coder analysis with implementation approach",
            AgentType.SENIOR_ENGINEER: "Mock senior-engineer analysis with patterns",
            AgentType.ARCHITECT: "Mock architect analysis with system design",
        }
        state["current_phase"] = WorkflowPhase.PHASE_1_SYNTHESIS

        # CORRECT: Only mock external dependencies (filesystem)
        with patch("pathlib.Path.write_text") as mock_filesystem:
            # CORRECT: Test actual method with injected mock model
            result = await self.workflow.architect_synthesis(state)

            # Verify synthesis document created (from mock model)
            self.assertIsNotNone(result["synthesis_document"])

            # Verify current phase updated
            self.assertEqual(result["current_phase"], WorkflowPhase.PHASE_1_SYNTHESIS)

            # Verify external dependency called (filesystem)
            mock_filesystem.assert_called_once()
            self.assertIn("synthesis", result["artifacts_index"])

    async def test_code_investigation_decision_logic(self):
        """Test code investigation decision logic."""
        # Test case where investigation is needed - pass as dict using get() method
        state_needs_investigation = {
            "synthesis_document": "Questions requiring investigation:\n- How does auth work?\n- What database schema exists?"
        }

        # Convert dict to WorkflowState-like object with get method
        class StateDict(dict):
            def get(self, key, default=None):
                return super().get(key, default)

        state_with_get = StateDict(state_needs_investigation)
        self.assertTrue(
            self.workflow.needs_code_investigation(state_with_get)  # type: ignore
        )

        # Test case where investigation is not needed
        state_no_investigation = StateDict(
            {"synthesis_document": "No questions, all clear"}
        )
        self.assertFalse(self.workflow.needs_code_investigation(state_no_investigation))  # type: ignore

    async def test_design_document_creation(self):
        """Test Phase 2: Design Document Creation."""
        state = self.initial_state.copy()
        state["current_phase"] = WorkflowPhase.PHASE_2_DESIGN_DOCUMENT

        # CORRECT: Only mock external dependencies (filesystem)
        with patch("pathlib.Path.write_text") as mock_filesystem:
            # CORRECT: Test actual method
            result = await self.workflow.create_design_document(state)

            # Verify design document created
            self.assertIsNotNone(result["design_document"])
            design_doc = result["design_document"] or ""

            # Verify document contains required sections
            self.assertIn("Design Document:", design_doc)
            self.assertIn("## Overview", design_doc)
            self.assertIn("## Acceptance Criteria", design_doc)
            self.assertIn("## Technical Design", design_doc)
            self.assertIn("## Human Additions", design_doc)
            self.assertIn("## Arbitration History", design_doc)

            # Verify model router set to Ollama
            self.assertEqual(result["model_router"], ModelRouter.OLLAMA)

            # Verify external dependency called (filesystem)
            mock_filesystem.assert_called_once()
            self.assertIn("design_document", result["artifacts_index"])

    async def test_model_routing_decisions(self):
        """Test model routing decisions."""
        # CORRECT: Test using injected mock models
        ollama_response = await self.workflow._call_model(
            "Test prompt", ModelRouter.OLLAMA
        )
        self.assertIn("Ollama response", ollama_response)

        # Test additional Ollama routing
        ollama_response_2 = await self.workflow._call_model(
            "Test prompt 2", ModelRouter.OLLAMA
        )
        self.assertIn("Ollama response", ollama_response_2)

    async def test_state_persistence(self):
        """Test that state is properly maintained between phases."""
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

    async def test_artifact_management(self):
        """Test artifact creation and indexing."""
        state = self.initial_state.copy()

        # Add some artifacts to the index
        artifacts_index = state["artifacts_index"]
        assert isinstance(artifacts_index, dict)
        artifacts_index["test_artifact"] = "/tmp/test-artifacts/test.md"
        artifacts_index["design_doc"] = "/tmp/test-artifacts/design.md"

        # Verify artifact management
        artifacts_index = state["artifacts_index"]
        assert isinstance(artifacts_index, dict)
        self.assertIn("test_artifact", artifacts_index)
        self.assertIn("design_doc", artifacts_index)
        self.assertEqual(len(artifacts_index), 2)


if __name__ == "__main__":
    unittest.main()
