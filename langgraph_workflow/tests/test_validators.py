"""Tests for state validators."""

import pytest

from langgraph_workflow.state import (
    AgentType,
    FeedbackGate,
    QualityState,
    WorkflowPhase,
    WorkflowState,
    initialize_state,
)
from langgraph_workflow.utils.validators import StateValidator


class TestStateValidation:
    """Test state validation."""

    def test_validate_state_with_valid_state(self):
        """Test validation of a valid state."""
        state = initialize_state("thread-1", "owner/repo", "/path/to/repo")
        is_valid, errors = StateValidator.validate_state(state)

        assert is_valid is True
        assert len(errors) == 0

    def test_validate_state_with_missing_required_fields(self):
        """Test validation with missing required fields."""
        state: WorkflowState = {}
        is_valid, errors = StateValidator.validate_state(state)

        assert is_valid is False
        assert "Missing required field: thread_id" in errors
        assert "Missing required field: repo_name" in errors
        assert "Missing required field: repo_path" in errors

    def test_validate_state_with_invalid_enum_fields(self):
        """Test validation with invalid enum values."""
        state = initialize_state("thread", "repo", "/path")
        state["current_phase"] = "invalid_phase"  # type: ignore
        state["quality_state"] = "invalid_quality"  # type: ignore

        is_valid, errors = StateValidator.validate_state(state)

        assert is_valid is False
        assert any("Invalid current_phase" in error for error in errors)
        assert any("Invalid quality_state" in error for error in errors)

    def test_validate_state_with_invalid_agent_analyses(self):
        """Test validation with invalid agent types in analyses."""
        state = initialize_state("thread", "repo", "/path")
        state["agent_analyses"]["invalid_agent"] = "analysis"

        is_valid, errors = StateValidator.validate_state(state)

        assert is_valid is False
        assert any("Invalid agent type in analyses: invalid_agent" in error for error in errors)


class TestPhaseTransitionValidation:
    """Test phase transition validation."""

    def test_valid_phase_transitions(self):
        """Test valid phase transitions."""
        # Analysis -> Design
        assert StateValidator.validate_phase_transition(
            WorkflowPhase.ANALYSIS, WorkflowPhase.DESIGN
        )

        # Design -> Finalization
        assert StateValidator.validate_phase_transition(
            WorkflowPhase.DESIGN, WorkflowPhase.FINALIZATION
        )

        # Design -> Implementation
        assert StateValidator.validate_phase_transition(
            WorkflowPhase.DESIGN, WorkflowPhase.IMPLEMENTATION
        )

        # Finalization -> Implementation
        assert StateValidator.validate_phase_transition(
            WorkflowPhase.FINALIZATION, WorkflowPhase.IMPLEMENTATION
        )

        # Implementation -> Finalization (go back for fixes)
        assert StateValidator.validate_phase_transition(
            WorkflowPhase.IMPLEMENTATION, WorkflowPhase.FINALIZATION
        )

    def test_invalid_phase_transitions(self):
        """Test invalid phase transitions."""
        # Analysis cannot go directly to Implementation
        assert not StateValidator.validate_phase_transition(
            WorkflowPhase.ANALYSIS, WorkflowPhase.IMPLEMENTATION
        )

        # Analysis cannot go to Finalization
        assert not StateValidator.validate_phase_transition(
            WorkflowPhase.ANALYSIS, WorkflowPhase.FINALIZATION
        )

        # Cannot go backwards from Design to Analysis
        assert not StateValidator.validate_phase_transition(
            WorkflowPhase.DESIGN, WorkflowPhase.ANALYSIS
        )


class TestRequiredArtifactsValidation:
    """Test required artifacts validation."""

    def test_design_phase_requires_analyses(self):
        """Test that design phase requires codebase and agent analyses."""
        state = initialize_state("thread", "repo", "/path")
        state["current_phase"] = WorkflowPhase.DESIGN

        # Without analyses
        is_valid, missing = StateValidator.validate_required_artifacts(state)
        assert is_valid is False
        assert "codebase_analysis" in missing

        # With codebase analysis but missing agents
        state["codebase_analysis"] = {"content": "analysis"}
        is_valid, missing = StateValidator.validate_required_artifacts(state)
        assert is_valid is False
        assert any("agent_analysis:" in item for item in missing)

        # With all analyses
        for agent_type in AgentType:
            state["agent_analyses"][agent_type.value] = "analysis"
        is_valid, missing = StateValidator.validate_required_artifacts(state)
        assert is_valid is True
        assert len(missing) == 0

    def test_finalization_phase_requires_consolidated_design(self):
        """Test that finalization phase requires consolidated design."""
        state = initialize_state("thread", "repo", "/path")
        state["current_phase"] = WorkflowPhase.FINALIZATION

        # Without consolidated design
        is_valid, missing = StateValidator.validate_required_artifacts(state)
        assert is_valid is False
        assert "consolidated_design" in missing

        # With consolidated design
        state["consolidated_design"] = "design document"
        is_valid, missing = StateValidator.validate_required_artifacts(state)
        assert is_valid is True

    def test_implementation_phase_requires_design(self):
        """Test that implementation phase requires design document."""
        state = initialize_state("thread", "repo", "/path")
        state["current_phase"] = WorkflowPhase.IMPLEMENTATION

        # Without any design
        is_valid, missing = StateValidator.validate_required_artifacts(state)
        assert is_valid is False
        assert "design_document" in missing

        # With consolidated design
        state["consolidated_design"] = "design"
        is_valid, missing = StateValidator.validate_required_artifacts(state)
        assert is_valid is True

        # Or with finalized design
        state = initialize_state("thread", "repo", "/path")
        state["current_phase"] = WorkflowPhase.IMPLEMENTATION
        state["finalized_design"] = "final design"
        is_valid, missing = StateValidator.validate_required_artifacts(state)
        assert is_valid is True


class TestPRIntegrationValidation:
    """Test PR integration validation."""

    def test_valid_pr_integration(self):
        """Test valid PR integration."""
        state = initialize_state("thread", "repo", "/path")
        state["pr_number"] = 123
        state["pr_comments"] = [
            {"id": "1", "body": "Comment 1"},
            {"id": "2", "body": "Comment 2"},
        ]
        state["feedback_addressed"] = {"1": True, "2": False}

        is_valid, issues = StateValidator.validate_pr_integration(state)
        assert is_valid is True
        assert len(issues) == 0

    def test_invalid_pr_number(self):
        """Test invalid PR number format."""
        state = initialize_state("thread", "repo", "/path")
        state["pr_number"] = -1

        is_valid, issues = StateValidator.validate_pr_integration(state)
        assert is_valid is False
        assert "Invalid PR number format" in issues

    def test_invalid_pr_comments(self):
        """Test invalid PR comment structure."""
        state = initialize_state("thread", "repo", "/path")
        state["pr_number"] = 123
        state["pr_comments"] = [
            "invalid comment",  # Not a dict
            {"body": "Missing ID"},  # Missing id field
        ]

        is_valid, issues = StateValidator.validate_pr_integration(state)
        assert is_valid is False
        assert any("PR comment 0 is not a dict" in issue for issue in issues)
        assert any("PR comment 1 missing ID" in issue for issue in issues)

    def test_untracked_pr_comments(self):
        """Test detection of untracked PR comments."""
        state = initialize_state("thread", "repo", "/path")
        state["pr_comments"] = [
            {"id": "1", "body": "Comment 1"},
            {"id": "2", "body": "Comment 2"},
        ]
        state["feedback_addressed"] = {"1": True}  # Missing comment 2

        is_valid, issues = StateValidator.validate_pr_integration(state)
        assert is_valid is False
        assert any("Untracked PR comments" in issue for issue in issues)


class TestTestIntegrationValidation:
    """Test test execution validation."""

    def test_valid_test_results(self):
        """Test valid test results."""
        state = initialize_state("thread", "repo", "/path")
        state["test_results"] = {
            "returncode": 0,
            "passed": True,
            "timestamp": "2024-01-01T00:00:00",
        }
        state["quality_state"] = QualityState.OK

        is_valid, issues = StateValidator.validate_test_integration(state)
        assert is_valid is True
        assert len(issues) == 0

    def test_missing_test_result_fields(self):
        """Test detection of missing test result fields."""
        state = initialize_state("thread", "repo", "/path")
        state["test_results"] = {"passed": True}  # Missing returncode and timestamp

        is_valid, issues = StateValidator.validate_test_integration(state)
        assert is_valid is False
        assert any("Test results missing field: returncode" in issue for issue in issues)
        assert any("Test results missing field: timestamp" in issue for issue in issues)

    def test_inconsistent_test_results(self):
        """Test detection of inconsistent test results."""
        state = initialize_state("thread", "repo", "/path")

        # Passed but non-zero return code
        state["test_results"] = {
            "returncode": 1,
            "passed": True,
            "timestamp": "2024-01-01",
        }
        is_valid, issues = StateValidator.validate_test_integration(state)
        assert is_valid is False
        assert any("passed=True but returncode != 0" in issue for issue in issues)

        # Failed but zero return code
        state["test_results"] = {
            "returncode": 0,
            "passed": False,
            "timestamp": "2024-01-01",
        }
        is_valid, issues = StateValidator.validate_test_integration(state)
        assert is_valid is False
        assert any("passed=False but returncode == 0" in issue for issue in issues)

    def test_quality_state_alignment(self):
        """Test quality state alignment with test results."""
        state = initialize_state("thread", "repo", "/path")

        # Tests passed but quality is FAIL
        state["test_results"] = {
            "returncode": 0,
            "passed": True,
            "timestamp": "2024-01-01",
        }
        state["quality_state"] = QualityState.FAIL
        is_valid, issues = StateValidator.validate_test_integration(state)
        assert is_valid is False
        assert any("Quality state inconsistent with test results" in issue for issue in issues)

        # Tests failed but quality is OK
        state["test_results"]["passed"] = False
        state["test_results"]["returncode"] = 1
        state["quality_state"] = QualityState.OK
        is_valid, issues = StateValidator.validate_test_integration(state)
        assert is_valid is False
        assert any("Quality state inconsistent with failing tests" in issue for issue in issues)


class TestRetryLogicValidation:
    """Test retry logic validation."""

    def test_valid_retry_logic(self):
        """Test valid retry logic."""
        state = initialize_state("thread", "repo", "/path")
        state["retry_count"] = 1
        state["escalation_needed"] = False

        is_valid, issues = StateValidator.validate_retry_logic(state)
        assert is_valid is True

    def test_invalid_retry_count(self):
        """Test invalid retry count."""
        state = initialize_state("thread", "repo", "/path")
        state["retry_count"] = -1

        is_valid, issues = StateValidator.validate_retry_logic(state)
        assert is_valid is False
        assert "Invalid retry count" in issues

    def test_high_retry_count(self):
        """Test detection of unexpectedly high retry count."""
        state = initialize_state("thread", "repo", "/path")
        state["retry_count"] = 15

        is_valid, issues = StateValidator.validate_retry_logic(state)
        assert is_valid is False
        assert "Retry count unexpectedly high" in issues

    def test_missing_escalation_flag(self):
        """Test detection of missing escalation flag."""
        state = initialize_state("thread", "repo", "/path")
        state["retry_count"] = 3
        state["escalation_needed"] = False

        is_valid, issues = StateValidator.validate_retry_logic(state)
        assert is_valid is False
        assert "High retry count but no escalation flag" in issues


class TestValidationSummary:
    """Test validation summary generation."""

    def test_get_validation_summary_with_valid_state(self):
        """Test validation summary for valid state."""
        state = initialize_state("thread", "owner/repo", "/path")
        summary = StateValidator.get_validation_summary(state)

        assert summary["overall_valid"] is True
        assert summary["total_errors"] == 0
        assert len(summary["checks"]) > 0

        for check_name, check_result in summary["checks"].items():
            assert check_result["valid"] is True
            assert check_result["error_count"] == 0

    def test_get_validation_summary_with_invalid_state(self):
        """Test validation summary for invalid state."""
        state: WorkflowState = {"thread_id": "test"}  # Missing required fields

        summary = StateValidator.get_validation_summary(state)

        assert summary["overall_valid"] is False
        assert summary["total_errors"] > 0
        assert summary["checks"]["state_structure"]["valid"] is False
        assert summary["checks"]["state_structure"]["error_count"] > 0