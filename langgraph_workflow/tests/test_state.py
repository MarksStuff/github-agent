"""Tests for workflow state management."""


from langgraph_workflow.state import (
    AgentType,
    FeedbackGate,
    QualityState,
    WorkflowPhase,
    WorkflowState,
    initialize_state,
    should_escalate,
    update_messages_window,
)


class TestEnums:
    """Test enum definitions."""

    def test_workflow_phase_values(self):
        """Test WorkflowPhase enum values."""
        assert WorkflowPhase.ANALYSIS.value == "analysis"
        assert WorkflowPhase.DESIGN.value == "design"
        assert WorkflowPhase.FINALIZATION.value == "finalization"
        assert WorkflowPhase.IMPLEMENTATION.value == "implementation"

    def test_agent_type_values(self):
        """Test AgentType enum values."""
        assert AgentType.ARCHITECT.value == "architect"
        assert AgentType.DEVELOPER.value == "developer"
        assert AgentType.SENIOR_ENGINEER.value == "senior_engineer"
        assert AgentType.TESTER.value == "tester"

    def test_quality_state_values(self):
        """Test QualityState enum values."""
        assert QualityState.DRAFT.value == "draft"
        assert QualityState.OK.value == "ok"
        assert QualityState.FAIL.value == "fail"

    def test_feedback_gate_values(self):
        """Test FeedbackGate enum values."""
        assert FeedbackGate.OPEN.value == "open"
        assert FeedbackGate.HOLD.value == "hold"


class TestStateInitialization:
    """Test state initialization."""

    def test_initialize_state_creates_valid_state(self):
        """Test that initialize_state creates a valid initial state."""
        state = initialize_state(
            thread_id="test-thread", repo_name="owner/repo", repo_path="/path/to/repo"
        )

        # Check required fields
        assert state["thread_id"] == "test-thread"
        assert state["repo_name"] == "owner/repo"
        assert state["repo_path"] == "/path/to/repo"
        assert state["current_phase"] == WorkflowPhase.ANALYSIS

        # Check initialized containers
        assert state["messages_window"] == []
        assert state["agent_analyses"] == {}
        assert state["pr_comments"] == []
        assert state["feedback_addressed"] == {}
        assert state["artifacts_index"] == {}

        # Check default values
        assert state["retry_count"] == 0
        assert state["escalation_needed"] is False
        assert state["paused_for_review"] is False
        assert state["quality_state"] == QualityState.DRAFT
        assert state["feedback_gate"] == FeedbackGate.OPEN

    def test_initialize_state_with_optional_fields(self):
        """Test that optional fields are properly initialized."""
        state = initialize_state("thread-1", "repo", "/path")

        assert state["pr_number"] is None
        assert state["prd_source"] is None
        assert state["finalized_design"] is None


class TestMessagesWindow:
    """Test messages window management."""

    def test_update_messages_window_adds_message(self):
        """Test adding messages to the window."""
        state = initialize_state("thread", "repo", "/path")
        message = {"role": "system", "content": "Test message"}

        update_messages_window(state, message)

        assert len(state["messages_window"]) == 1
        assert state["messages_window"][0] == message

    def test_update_messages_window_maintains_max_size(self):
        """Test that messages window respects max size."""
        state = initialize_state("thread", "repo", "/path")

        # Add 15 messages
        for i in range(15):
            update_messages_window(
                state, {"role": "system", "content": f"Message {i}"}, max_size=10
            )

        # Should only have 10 messages
        assert len(state["messages_window"]) == 10

        # Should have the last 10 messages
        assert state["messages_window"][0]["content"] == "Message 5"
        assert state["messages_window"][-1]["content"] == "Message 14"

    def test_update_messages_window_updates_summary_log(self):
        """Test that old messages are summarized."""
        state = initialize_state("thread", "repo", "/path")

        # Add 15 messages with max size 10
        for i in range(15):
            update_messages_window(
                state, {"role": "system", "content": f"Message {i}"}, max_size=10
            )

        # Summary log should have been updated
        assert "[Previous 5 messages summarized]" in state["summary_log"]


class TestEscalationLogic:
    """Test escalation decision logic."""

    def test_should_escalate_on_retry_count(self):
        """Test escalation based on retry count."""
        state = initialize_state("thread", "repo", "/path")

        # Should not escalate initially
        assert should_escalate(state) is False

        # Should escalate after 2 retries
        state["retry_count"] = 2
        assert should_escalate(state) is True

    def test_should_escalate_on_explicit_flag(self):
        """Test escalation based on explicit flag."""
        state = initialize_state("thread", "repo", "/path")
        state["escalation_needed"] = True
        assert should_escalate(state) is True

    def test_should_escalate_on_design_conflicts(self):
        """Test escalation based on design conflicts."""
        state = initialize_state("thread", "repo", "/path")

        # Add 6 design conflicts
        state["design_conflicts"] = [{"conflict": i} for i in range(6)]
        assert should_escalate(state) is True

        # Should not escalate with 5 or fewer
        state["design_conflicts"] = [{"conflict": i} for i in range(5)]
        assert should_escalate(state) is False

    def test_should_escalate_on_finalization_phase(self):
        """Test escalation during finalization phase."""
        state = initialize_state("thread", "repo", "/path")
        state["current_phase"] = WorkflowPhase.FINALIZATION
        assert should_escalate(state) is True

    def test_should_escalate_on_quality_failure_with_retry(self):
        """Test escalation on quality failure after retry."""
        state = initialize_state("thread", "repo", "/path")
        state["quality_state"] = QualityState.FAIL
        state["retry_count"] = 1
        assert should_escalate(state) is True

        # Should not escalate without retry
        state["retry_count"] = 0
        assert should_escalate(state) is False


class TestWorkflowStateTypedDict:
    """Test WorkflowState TypedDict structure."""

    def test_workflow_state_accepts_all_fields(self):
        """Test that WorkflowState accepts all defined fields."""
        state: WorkflowState = {
            "thread_id": "test",
            "current_phase": WorkflowPhase.ANALYSIS,
            "pr_number": 123,
            "task_spec": "Test task",
            "feature_name": "Test feature",
            "prd_source": "prd.md",
            "repo_name": "owner/repo",
            "repo_path": "/path",
            "git_branch": "feature/test",
            "last_commit_sha": "abc123",
            "messages_window": [],
            "summary_log": "",
            "codebase_analysis": {},
            "agent_analyses": {},
            "design_conflicts": [],
            "consolidated_design": "Design doc",
            "finalized_design": "Final design",
            "skeleton_code": {},
            "test_code": {},
            "implementation_code": {},
            "test_results": {},
            "lint_status": {},
            "ci_status": {},
            "quality_state": QualityState.DRAFT,
            "pr_comments": [],
            "feedback_addressed": {},
            "feedback_gate": FeedbackGate.OPEN,
            "artifacts_index": {},
            "retry_count": 0,
            "escalation_needed": False,
            "paused_for_review": False,
        }

        # Should not raise any errors
        assert state["thread_id"] == "test"
        assert state["current_phase"] == WorkflowPhase.ANALYSIS

    def test_workflow_state_optional_fields(self):
        """Test that optional fields work correctly."""
        state: WorkflowState = {
            "thread_id": "test",
            "repo_name": "repo",
            "repo_path": "/path",
        }

        # Optional fields should be accessible
        assert state.get("pr_number") is None
        assert state.get("finalized_design") is None
