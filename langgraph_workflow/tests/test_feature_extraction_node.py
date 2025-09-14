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
    async def test_extract_feature_error_handling(self, workflow, temp_repo):
        """Test feature extraction handles file system errors gracefully."""
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

        # Mock filesystem error in get_artifacts_path
        from unittest.mock import patch

        with patch(
            "langgraph_workflow.config.get_artifacts_path", 
            side_effect=PermissionError("Permission denied")
        ):
            # Should raise the underlying error
            with pytest.raises(PermissionError):
                await workflow.extract_feature(state)

    @pytest.mark.asyncio
    async def test_extract_feature_empty_inputs(self, workflow, temp_repo):
        """Test feature extraction with empty or None inputs."""
        # Test with empty feature description
        state = WorkflowState(
            thread_id="test-thread",
            feature_description="",  # Empty
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

        # Should handle empty gracefully
        updated_state = await workflow.extract_feature(state)
        assert updated_state["feature_description"] == ""
        assert "feature_description" in updated_state["artifacts_index"]

        # Check artifact was created (even if empty)
        artifact_path = Path(updated_state["artifacts_index"]["feature_description"])
        assert artifact_path.exists()
        assert artifact_path.read_text() == ""

    @pytest.mark.asyncio
    async def test_extract_feature_none_handling(self, workflow, temp_repo):
        """Test feature extraction with None values."""
        state = WorkflowState(
            thread_id="test-thread",
            feature_description="Valid feature",
            raw_feature_input=None,
            extracted_feature=None,  # This should trigger the fallback path
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

        # Should fall back to feature_description when others are None
        updated_state = await workflow.extract_feature(state)
        assert updated_state["feature_description"] == "Valid feature"

    @pytest.mark.asyncio
    async def test_extract_feature_state_transitions(self, workflow, temp_repo):
        """Test that feature extraction properly manages workflow state."""
        initial_artifacts = {"existing": "/some/path"}

        state = WorkflowState(
            thread_id="test-thread",
            feature_description="Test feature",
            raw_feature_input=None,
            extracted_feature=None,
            current_phase=WorkflowPhase.PHASE_0_CODE_CONTEXT,
            messages_window=[],
            summary_log="",
            artifacts_index=initial_artifacts.copy(),  # Should preserve existing artifacts
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

        updated_state = await workflow.extract_feature(state)

        # Should preserve existing artifacts and add new one
        assert "existing" in updated_state["artifacts_index"]
        assert updated_state["artifacts_index"]["existing"] == "/some/path"
        assert "feature_description" in updated_state["artifacts_index"]

        # Should preserve all other state fields
        assert updated_state["thread_id"] == "test-thread"
        assert updated_state["current_phase"] == WorkflowPhase.PHASE_0_CODE_CONTEXT
        assert updated_state["repo_path"] == temp_repo

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

    @pytest.mark.asyncio
    async def test_extract_feature_with_complex_content(self, workflow, temp_repo):
        """Test feature extraction with complex multi-line content and validation."""
        complex_feature = """## User Authentication & Authorization System

### Core Requirements:
- JWT-based authentication with refresh tokens
- Role-based access control (RBAC) with granular permissions
- Multi-factor authentication (MFA) support
- Session management with configurable timeouts

### Technical Specifications:
- Integration with OAuth2 providers (Google, GitHub, etc.)
- Password policy enforcement (complexity, rotation)
- Audit logging for all authentication events
- Rate limiting for failed login attempts

### Security Considerations:
- Secure password storage with bcrypt hashing
- Protection against brute force attacks
- CSRF token validation
- Secure cookie handling with HTTPOnly and SameSite flags

### Implementation Notes:
This feature requires updates to:
1. Database schema (users, roles, permissions tables)
2. API middleware for authentication/authorization
3. Frontend login/registration components
4. Admin panel for user management
"""

        state = WorkflowState(
            thread_id="test-complex-content",
            feature_description="",  # Will be overwritten
            raw_feature_input=complex_feature,
            extracted_feature=None,  # Should use the full raw input
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

        # Execute feature extraction
        updated_state = await workflow.extract_feature(state)

        # Verify complex content was stored correctly
        assert updated_state["feature_description"] == complex_feature

        # Check artifact file contains the full complex content
        artifact_path = Path(updated_state["artifacts_index"]["feature_description"])
        assert artifact_path.exists()
        stored_content = artifact_path.read_text()

        # Verify content integrity
        assert stored_content == complex_feature
        assert "JWT-based authentication" in stored_content
        assert "Role-based access control" in stored_content
        assert "Multi-factor authentication" in stored_content
        assert "Database schema" in stored_content

        # Verify line structure is preserved
        lines = stored_content.split("\n")
        assert lines[0] == "## User Authentication & Authorization System"
        assert (
            len([line for line in lines if line.strip().startswith("-")]) >= 8
        )  # Multiple bullet points
        assert (
            len([line for line in lines if line.strip().startswith("#")]) >= 3
        )  # Multiple headers
