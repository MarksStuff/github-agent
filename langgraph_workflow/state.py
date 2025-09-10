"""State schema definitions for the LangGraph workflow."""

from enum import Enum
from typing import Optional, TypedDict


class WorkflowPhase(Enum):
    """Workflow phases."""

    ANALYSIS = "analysis"
    DESIGN = "design"
    FINALIZATION = "finalization"
    IMPLEMENTATION = "implementation"


class AgentType(Enum):
    """Agent types in the workflow."""

    ARCHITECT = "architect"
    DEVELOPER = "developer"
    SENIOR_ENGINEER = "senior_engineer"
    TESTER = "tester"


class QualityState(Enum):
    """Quality assessment states."""

    DRAFT = "draft"
    OK = "ok"
    FAIL = "fail"


class FeedbackGate(Enum):
    """Feedback gate states."""

    OPEN = "open"
    HOLD = "hold"


class WorkflowState(TypedDict, total=False):
    """Complete workflow state for LangGraph.

    This state is persisted in SQLite and used throughout the workflow.
    """

    # Core workflow tracking
    thread_id: str  # e.g., "pr-123" or "issue-456"
    current_phase: WorkflowPhase
    pr_number: Optional[int]

    # Task specification
    task_spec: str
    feature_name: str
    prd_source: Optional[str]  # If extracted from PRD

    # Repository context
    repo_name: str  # e.g., "owner/repo"
    repo_path: str  # Absolute path to workspace
    git_branch: str
    last_commit_sha: str

    # Agent outputs (compact)
    messages_window: list[dict]  # Last 5-10 messages only
    summary_log: str  # Rolling summary of decisions

    # Analysis artifacts
    codebase_analysis: dict  # Senior engineer's analysis
    agent_analyses: dict[str, str]  # Each agent's analysis, keyed by AgentType value

    # Design artifacts
    design_conflicts: list[dict]  # Identified conflicts
    consolidated_design: str  # Unified design document
    finalized_design: Optional[str]  # After feedback incorporation

    # Implementation artifacts
    skeleton_code: dict[str, str]  # File path -> skeleton content
    test_code: dict[str, str]  # File path -> test content
    implementation_code: dict[str, str]  # File path -> implementation

    # Quality gates
    test_results: dict  # Compact test report
    lint_status: dict  # Lint findings
    ci_status: dict  # CI/CD check status
    quality_state: QualityState

    # Feedback management
    pr_comments: list[dict]  # GitHub PR comments
    feedback_addressed: dict[str, bool]  # Comment ID -> addressed
    feedback_gate: FeedbackGate

    # Artifact index (paths only, not content)
    artifacts_index: dict[str, str]

    # Execution control
    retry_count: int
    escalation_needed: bool
    paused_for_review: bool


def initialize_state(thread_id: str, repo_name: str, repo_path: str) -> WorkflowState:
    """Initialize a new workflow state."""
    return WorkflowState(
        thread_id=thread_id,
        current_phase=WorkflowPhase.ANALYSIS,
        pr_number=None,
        task_spec="",
        feature_name="",
        prd_source=None,
        repo_name=repo_name,
        repo_path=repo_path,
        git_branch="",
        last_commit_sha="",
        messages_window=[],
        summary_log="",
        codebase_analysis={},
        agent_analyses={},
        design_conflicts=[],
        consolidated_design="",
        finalized_design=None,
        skeleton_code={},
        test_code={},
        implementation_code={},
        test_results={},
        lint_status={},
        ci_status={},
        quality_state=QualityState.DRAFT,
        pr_comments=[],
        feedback_addressed={},
        feedback_gate=FeedbackGate.OPEN,
        artifacts_index={},
        retry_count=0,
        escalation_needed=False,
        paused_for_review=False,
    )


def update_messages_window(
    state: WorkflowState, new_message: dict, max_size: int = 10
) -> None:
    """Update the messages window, maintaining max size."""
    state["messages_window"].append(new_message)
    if len(state["messages_window"]) > max_size:
        # Summarize old messages before removing
        old_messages = state["messages_window"][:5]
        summary = f"[Previous {len(old_messages)} messages summarized]\n"
        state["summary_log"] += summary
        state["messages_window"] = state["messages_window"][-max_size:]


def should_escalate(state: WorkflowState) -> bool:
    """Determine if current task should escalate to Claude."""
    return any(
        [
            state.get("retry_count", 0) >= 2,
            state.get("escalation_needed", False),
            len(state.get("design_conflicts", [])) > 5,
            state.get("current_phase") == WorkflowPhase.FINALIZATION,
            state.get("quality_state") == QualityState.FAIL
            and state.get("retry_count", 0) >= 1,
        ]
    )
