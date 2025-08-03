"""Task context management for multi-agent workflow."""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class FeatureSpec:
    """Feature specification details."""

    name: str
    description: str
    requirements: list[str]
    acceptance_criteria: list[str]
    constraints: list[str] = field(default_factory=list)


@dataclass
class CodebaseState:
    """Current state of the codebase."""

    repository: str
    branch: str
    commit_sha: str
    analysis_summary: str
    patterns_identified: list[str] = field(default_factory=list)
    existing_tests: dict[str, Any] = field(default_factory=dict)


@dataclass
class FeedbackItem:
    """Human feedback item from GitHub."""

    comment_id: int
    author: str
    content: str
    file_path: str | None
    line_number: int | None
    created_at: str
    addressed: bool = False
    agent_response: str | None = None


@dataclass
class AnalysisResult:
    """Result from an agent's analysis."""

    agent_type: str
    content: str
    timestamp: str
    status: str
    error: str | None = None


class TaskContext:
    """Maintains shared state and context for the workflow."""

    def __init__(self, feature_spec: FeatureSpec, codebase_state: CodebaseState, repo_path: str | None = None):
        """Initialize task context.

        Args:
            feature_spec: Feature specification
            codebase_state: Current codebase state
            repo_path: Repository path for absolute path resolution
        """
        self.feature_spec = feature_spec
        self.codebase_state = codebase_state
        self.repo_path = Path(repo_path) if repo_path else Path.cwd()
        self.analysis_results: dict[str, AnalysisResult] = {}
        self.human_feedback: list[FeedbackItem] = []
        self.workflow_phase = "initialization"
        self.pr_number: int | None = None
        self.created_at = datetime.now().isoformat()

        logger.info(f"Initialized task context for feature: {feature_spec.name}")

    def update_from_analysis(self, agent_type: str, analysis: dict[str, Any]):
        """Update context with agent analysis results.

        Args:
            agent_type: Type of agent providing analysis
            analysis: Analysis results from agent
        """
        result = AnalysisResult(
            agent_type=agent_type,
            content=analysis.get("analysis", ""),
            timestamp=datetime.now().isoformat(),
            status=analysis.get("status", "success"),
            error=analysis.get("error"),
        )

        self.analysis_results[agent_type] = result
        logger.info(f"Updated context with {agent_type} analysis")

    def add_human_feedback(self, feedback_data: dict[str, Any]):
        """Add human feedback from GitHub.

        Args:
            feedback_data: Feedback data from GitHub API
        """
        # Handle both raw API format and formatted format
        if "author" in feedback_data:
            # Formatted comment from our API
            author = feedback_data["author"]
        elif "user" in feedback_data:
            # Raw GitHub API format
            author = feedback_data["user"]["login"]
        else:
            author = "unknown"

        feedback = FeedbackItem(
            comment_id=feedback_data["id"],
            author=author,
            content=feedback_data["body"],
            file_path=feedback_data.get("file") or feedback_data.get("path"),  # Try 'file' first, then 'path'
            line_number=feedback_data.get("line"),
            created_at=feedback_data.get("created_at", ""),
        )

        self.human_feedback.append(feedback)
        logger.info(f"Added feedback from {feedback.author}")

    def get_context_for_agent(self, agent_type: str) -> dict[str, Any]:
        """Get context tailored for specific agent.

        Args:
            agent_type: Type of agent requesting context

        Returns:
            Context dictionary for the agent
        """
        context = {
            "feature_spec": {
                "name": self.feature_spec.name,
                "description": self.feature_spec.description,
                "requirements": self.feature_spec.requirements,
                "acceptance_criteria": self.feature_spec.acceptance_criteria,
                "constraints": self.feature_spec.constraints,
            },
            "codebase_analysis_path": str((self.repo_path / ".workflow/codebase_analysis.md").resolve()),
            "repository": self.codebase_state.repository,
            "branch": self.codebase_state.branch,
            "patterns": self.codebase_state.patterns_identified,
            "workflow_phase": self.workflow_phase,
            "pr_number": self.pr_number,
        }

        # Add peer analyses for later rounds
        if self.workflow_phase != "round_1_analysis":
            peer_analyses = {}
            for other_agent, result in self.analysis_results.items():
                if other_agent != agent_type and result.status == "success":
                    peer_analyses[other_agent] = result.content
            context["peer_analyses"] = peer_analyses

        # Add relevant human feedback
        relevant_feedback = []
        for feedback in self.human_feedback:
            if not feedback.addressed:
                relevant_feedback.append(
                    {
                        "author": feedback.author,
                        "content": feedback.content,
                        "file_path": feedback.file_path,
                        "created_at": feedback.created_at,
                    }
                )
        context["human_feedback"] = relevant_feedback

        return context

    def set_pr_number(self, pr_number: int):
        """Set the PR number for this workflow.

        Args:
            pr_number: GitHub PR number
        """
        self.pr_number = pr_number
        logger.info(f"Set PR number to {pr_number}")

    def update_phase(self, phase: str):
        """Update the current workflow phase.

        Args:
            phase: New workflow phase
        """
        self.workflow_phase = phase
        logger.info(f"Updated workflow phase to: {phase}")

    def save_to_file(self, filepath: Path):
        """Save context to file for persistence.

        Args:
            filepath: Path to save context
        """
        data = {
            "feature_spec": {
                "name": self.feature_spec.name,
                "description": self.feature_spec.description,
                "requirements": self.feature_spec.requirements,
                "acceptance_criteria": self.feature_spec.acceptance_criteria,
                "constraints": self.feature_spec.constraints,
            },
            "codebase_state": {
                "repository": self.codebase_state.repository,
                "branch": self.codebase_state.branch,
                "commit_sha": self.codebase_state.commit_sha,
                "analysis_summary": self.codebase_state.analysis_summary,
                "patterns_identified": self.codebase_state.patterns_identified,
                "existing_tests": self.codebase_state.existing_tests,
            },
            "analysis_results": {
                agent: {
                    "content": result.content,
                    "timestamp": result.timestamp,
                    "status": result.status,
                    "error": result.error,
                }
                for agent, result in self.analysis_results.items()
            },
            "workflow_phase": self.workflow_phase,
            "pr_number": self.pr_number,
            "created_at": self.created_at,
            "repo_path": str(self.repo_path),
        }

        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)

        logger.info(f"Saved context to {filepath}")

    @classmethod
    def load_from_file(cls, filepath: Path) -> "TaskContext":
        """Load context from file.

        Args:
            filepath: Path to load context from

        Returns:
            Loaded TaskContext instance
        """
        with open(filepath) as f:
            data = json.load(f)

        # Reconstruct objects
        feature_spec = FeatureSpec(**data["feature_spec"])
        codebase_state = CodebaseState(**data["codebase_state"])
        repo_path = data.get("repo_path", str(Path.cwd()))

        context = cls(feature_spec, codebase_state, repo_path)
        context.workflow_phase = data["workflow_phase"]
        context.pr_number = data["pr_number"]
        context.created_at = data["created_at"]

        # Restore analysis results
        for agent_type, result_data in data["analysis_results"].items():
            context.analysis_results[agent_type] = AnalysisResult(
                agent_type=agent_type, **result_data
            )

        logger.info(f"Loaded context from {filepath}")
        return context
