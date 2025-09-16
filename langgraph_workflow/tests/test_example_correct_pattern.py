"""Example test showing the correct testing pattern according to CLAUDE.md."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch  # Only for external dependencies

from ..enums import FeedbackGateStatus, ModelRouter, QualityLevel, WorkflowPhase
from ..workflow_state import WorkflowState
from .mocks import create_mock_dependencies
from .mocks.test_workflow import MockTestMultiAgentWorkflow


class TestCorrectPattern(unittest.IsolatedAsyncioTestCase):
    """Example of correct testing pattern following CLAUDE.md guidelines."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.repo_path = self.temp_dir.name
        self.thread_id = "correct-test-123"

        # Use our own mock dependencies (NOT MagicMock for internal objects)
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

        # Set up artifacts directory
        artifacts_path = Path(self.temp_dir.name) / "artifacts"
        artifacts_path.mkdir(parents=True, exist_ok=True)
        self.workflow.artifacts_dir = str(artifacts_path)

    def tearDown(self):
        """Clean up test fixtures."""
        self.temp_dir.cleanup()

    async def test_workflow_phase_with_correct_mocking(self):
        """Test workflow phase using CORRECT mocking approach."""
        # Create initial state
        state = WorkflowState(
            thread_id=self.thread_id,
            feature_description="Test authentication",
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
            quality=QualityLevel.DRAFT,
            feedback_gate=FeedbackGateStatus.OPEN,
            model_router=ModelRouter.OLLAMA,
            escalation_count=0,
        )

        # CORRECT: Mock external dependencies only (filesystem in this case)
        with patch("pathlib.Path.write_text") as mock_filesystem:
            # CORRECT: Test the actual workflow method using injected dependencies
            # state is a WorkflowState (TypedDict), cast to dict for type checker
            result = await self.workflow.extract_code_context(dict(state))

            # Verify the workflow behavior through state changes
            self.assertEqual(
                result["current_phase"], WorkflowPhase.PHASE_0_CODE_CONTEXT
            )
            self.assertEqual(result["model_router"], ModelRouter.OLLAMA)
            self.assertIsNotNone(result["code_context_document"])

            # Verify external dependency was called (filesystem)
            mock_filesystem.assert_called_once()

    async def test_model_routing_with_correct_injection(self):
        """Test model routing using CORRECT dependency injection."""
        # CORRECT: Use our injected mock models (not MagicMock patch)
        ollama_response = await self.workflow._call_model(
            "Test prompt", ModelRouter.OLLAMA
        )

        # Verify responses from our mock implementations
        self.assertIn("Ollama response", ollama_response)

    # INCORRECT pattern for comparison (DON'T DO THIS):
    """
    async def test_incorrect_pattern_do_not_use(self):
        # WRONG: Using MagicMock for our own objects
        from unittest.mock import MagicMock
        mock_workflow = MagicMock()

        # WRONG: Patching our internal methods
        with patch.object(workflow, 'extract_code_context'):
            pass

        # WRONG: Using MagicMock for our agents
        mock_agent = MagicMock()
        workflow.agents['test-first'] = mock_agent
    """


if __name__ == "__main__":
    unittest.main()
