"""Example test showing the correct testing pattern according to CLAUDE.md."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch  # Only for external dependencies

from ..langgraph_workflow import (
    ModelRouter,
    MultiAgentWorkflow,
    WorkflowPhase,
    WorkflowState,
)
from ..mocks import create_mock_dependencies


class TestCorrectPattern(unittest.IsolatedAsyncioTestCase):
    """Example of correct testing pattern following CLAUDE.md guidelines."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.repo_path = self.temp_dir.name
        self.thread_id = "correct-test-123"

        # Use our own mock dependencies (NOT MagicMock for internal objects)
        self.mock_deps = create_mock_dependencies(self.thread_id)

        # Create workflow with dependency injection
        self.workflow = MultiAgentWorkflow(
            repo_path=self.repo_path, thread_id=self.thread_id
        )

        # Inject our mock dependencies (CORRECT approach)
        self.workflow.agents = self.mock_deps["agents"]
        self.workflow.ollama_model = self.mock_deps["ollama_model"]
        self.workflow.claude_model = self.mock_deps["claude_model"]

        # Set up artifacts directory
        self.workflow.artifacts_dir = Path(self.temp_dir.name) / "artifacts"
        self.workflow.artifacts_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        """Clean up test fixtures."""
        self.temp_dir.cleanup()

    async def test_workflow_phase_with_correct_mocking(self):
        """Test workflow phase using CORRECT mocking approach."""
        # Create initial state
        state = WorkflowState(
            thread_id=self.thread_id,
            feature_description="Test authentication",
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

        # CORRECT: Mock external dependencies only (filesystem in this case)
        with patch("pathlib.Path.write_text") as mock_filesystem:
            # CORRECT: Test the actual workflow method using injected dependencies
            result = await self.workflow.extract_code_context(state)

            # Verify the workflow behavior through state changes
            self.assertEqual(
                result["current_phase"], WorkflowPhase.PHASE_0_CODE_CONTEXT
            )
            self.assertEqual(result["model_router"], ModelRouter.CLAUDE_CODE)
            self.assertIsNotNone(result["code_context_document"])

            # Verify external dependency was called (filesystem)
            mock_filesystem.assert_called_once()

    async def test_model_routing_with_correct_injection(self):
        """Test model routing using CORRECT dependency injection."""
        # CORRECT: Use our injected mock models (not MagicMock patch)
        ollama_response = await self.workflow._call_model(
            "Test prompt", ModelRouter.OLLAMA
        )
        claude_response = await self.workflow._call_model(
            "Test prompt", ModelRouter.CLAUDE_CODE
        )

        # Verify responses from our mock implementations
        self.assertIn("Ollama response", ollama_response)
        self.assertIn("Claude response", claude_response)

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
