"""Workflow state and data types for LangGraph workflows."""

from datetime import datetime
from typing import Annotated, Any, TypedDict
from uuid import uuid4

from langchain_core.messages import BaseMessage
from pydantic import BaseModel, Field

from .enums import (
    AgentType,
    ArtifactType,
    FeedbackGateStatus,
    ModelRouter,
    QualityLevel,
    WorkflowPhase,
)


class Artifact(BaseModel):
    """Represents an artifact created during the workflow."""

    key: str
    path: str
    type: ArtifactType
    content_digest: str | None = None
    created_at: datetime = Field(default_factory=datetime.now)


class Arbitration(BaseModel):
    """Represents a human arbitration decision."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    phase: WorkflowPhase
    conflict_description: str
    agents_involved: list[AgentType]
    human_decision: str | None = None
    timestamp: datetime = Field(default_factory=datetime.now)
    applied: bool = False


class WorkflowState(TypedDict):
    """State for the LangGraph workflow."""

    # Core workflow info
    thread_id: str
    feature_description: str
    raw_feature_input: str | None  # Original PRD or feature file content
    extracted_feature: str | None  # Extracted feature from PRD
    current_phase: WorkflowPhase

    # Messages and summary
    messages_window: Annotated[list[BaseMessage], lambda x, y: y[-10:]]  # Keep last 10
    summary_log: str

    # Artifacts and documents
    artifacts_index: dict[str, str]  # key -> path mapping
    code_context_document: str | None
    design_constraints_document: str | None
    design_document: str | None
    arbitration_log: list[Arbitration]

    # Git integration
    repo_path: str
    git_branch: str
    last_commit_sha: str | None
    pr_number: int | None

    # Agent outputs
    agent_analyses: dict[AgentType, str]  # agent_type -> analysis
    synthesis_document: str | None
    conflicts: list[dict[str, Any]]

    # Implementation artifacts
    skeleton_code: str | None
    test_code: str | None
    implementation_code: str | None
    patch_queue: list[str]  # Paths to patches

    # Quality and status
    test_report: dict[str, Any]
    ci_status: dict[str, Any]
    lint_status: dict[str, Any]
    quality: QualityLevel
    feedback_gate: FeedbackGateStatus

    # Resource routing
    model_router: ModelRouter
    escalation_count: int
