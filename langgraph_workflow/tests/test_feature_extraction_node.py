"""Tests for the feature extraction node in the workflow."""

import tempfile
from pathlib import Path

import pytest

from langgraph_workflow.enums import ModelRouter, WorkflowPhase
from langgraph_workflow.langgraph_workflow import MultiAgentWorkflow, WorkflowState
from langgraph_workflow.tests.mocks import create_mock_agents


class TestFeatureExtractionNode:
    """Test the feature extraction node functionality."""

    @pytest.fixture
    def temp_repo(self):
        """Create a temporary repository for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            (repo_path / "main.py").write_text("# Main application")
            (repo_path / "README.md").write_text("# Test Project")
            yield str(repo_path)

    @pytest.fixture
    def workflow(self, temp_repo):
        """Create a workflow instance for testing."""
        from langgraph_workflow.real_codebase_analyzer import RealCodebaseAnalyzer

        analyzer = RealCodebaseAnalyzer(temp_repo)
        agents = create_mock_agents()

        workflow = MultiAgentWorkflow(
            repo_path=temp_repo,
            thread_id="test-feature-extraction",
            agents=agents,  # type: ignore
            codebase_analyzer=analyzer,
        )
        return workflow

    @pytest.mark.asyncio
    async def test_extract_feature_with_simple_description(self, workflow, temp_repo):
        """Test feature extraction with a simple feature description."""
        # Create initial state with simple feature
        state = WorkflowState(
            thread_id="test-thread",
            feature_description="Add user authentication",
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
            repo_path=temp_repo,
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

        # Execute the feature extraction node
        updated_state = await workflow.extract_feature(state)

        # Verify feature was stored
        assert updated_state["feature_description"] == "Add user authentication"
        assert "feature_description" in updated_state["artifacts_index"]

        # Check artifact was created
        artifact_path = Path(updated_state["artifacts_index"]["feature_description"])
        assert artifact_path.exists()
        assert artifact_path.read_text() == "Add user authentication"

    @pytest.mark.asyncio
    async def test_extract_feature_with_prd(self, workflow, temp_repo):
        """Test feature extraction with a full PRD document."""
        prd_content = """# Product Requirements Document

## Feature 1: User Authentication
Users should be able to register and login.

## Feature 2: Data Export
Users should be able to export their data.
"""

        state = WorkflowState(
            thread_id="test-thread",
            feature_description="",  # Will be updated by extraction
            raw_feature_input=prd_content,
            extracted_feature=None,  # No specific extraction
            current_phase=WorkflowPhase.PHASE_0_CODE_CONTEXT,
            messages_window=[],
            summary_log="",
            artifacts_index={},
            code_context_document=None,
            design_constraints_document=None,
            design_document=None,
            arbitration_log=[],
            repo_path=temp_repo,
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

        # Execute the feature extraction node
        updated_state = await workflow.extract_feature(state)

        # Verify entire PRD was used as feature
        assert updated_state["feature_description"] == prd_content
        assert "feature_description" in updated_state["artifacts_index"]

        # Check artifact contains full PRD
        artifact_path = Path(updated_state["artifacts_index"]["feature_description"])
        assert artifact_path.exists()
        assert artifact_path.read_text() == prd_content

    @pytest.mark.asyncio
    async def test_extract_feature_with_extracted_feature(self, workflow, temp_repo):
        """Test feature extraction with a pre-extracted feature from PRD."""
        prd_content = """# Product Requirements Document
Multiple features here..."""

        extracted_feature = """## User Authentication Feature
Detailed requirements for authentication..."""

        state = WorkflowState(
            thread_id="test-thread",
            feature_description="",  # Will be updated
            raw_feature_input=prd_content,
            extracted_feature=extracted_feature,  # Pre-extracted
            current_phase=WorkflowPhase.PHASE_0_CODE_CONTEXT,
            messages_window=[],
            summary_log="",
            artifacts_index={},
            code_context_document=None,
            design_constraints_document=None,
            design_document=None,
            arbitration_log=[],
            repo_path=temp_repo,
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

        # Execute the feature extraction node
        updated_state = await workflow.extract_feature(state)

        # Verify extracted feature was used
        assert updated_state["feature_description"] == extracted_feature
        assert "feature_description" in updated_state["artifacts_index"]

        # Check artifact contains extracted feature, not full PRD
        artifact_path = Path(updated_state["artifacts_index"]["feature_description"])
        assert artifact_path.exists()
        assert artifact_path.read_text() == extracted_feature

    @pytest.mark.asyncio
    async def test_artifact_directory_creation(self, workflow, temp_repo):
        """Test that artifact directory is created properly."""
        state = WorkflowState(
            thread_id="unique-test-thread",
            feature_description="Test feature",
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
            repo_path=temp_repo,
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

        # Execute the feature extraction node
        updated_state = await workflow.extract_feature(state)

        # Verify artifact directory structure
        artifact_path = Path(updated_state["artifacts_index"]["feature_description"])
        assert "unique-test-thread" in str(artifact_path)
        assert artifact_path.parent.name == "unique-test-thread"
        assert artifact_path.parent.parent.name == "artifacts"
