#!/usr/bin/env python3
"""
Feedback Processor Module for Enhanced Multi-Agent Workflow System

Processes GitHub feedback and incorporates it into workflow execution:
- Analyzes feedback from GitHub comments
- Modifies workflow state based on feedback
- Implements feedback-driven workflow continuation
- Tracks feedback history and outcomes
"""

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Optional

try:
    from .github_integrator import GitHubComment, WorkflowFeedback
    from .pause_resume import PauseReason, WorkflowPauseManager
    from .workflow_state import StageStatus, WorkflowInputs, WorkflowState
except ImportError:
    from github_integrator import WorkflowFeedback
    from pause_resume import PauseReason, WorkflowPauseManager
    from workflow_state import StageStatus, WorkflowState

logger = logging.getLogger(__name__)


class FeedbackAction(Enum):
    """Types of actions that can result from feedback processing."""

    CONTINUE = "continue"
    PAUSE = "pause"
    RESUME = "resume"
    RESTART_STAGE = "restart_stage"
    SKIP_STAGE = "skip_stage"
    MODIFY_INPUTS = "modify_inputs"
    ABORT_WORKFLOW = "abort_workflow"
    APPROVE_STAGE = "approve_stage"
    REJECT_STAGE = "reject_stage"


@dataclass
class FeedbackProcessingResult:
    """Result of processing workflow feedback."""

    action: FeedbackAction
    stage_name: Optional[str] = None
    message: str = ""
    input_modifications: dict[str, Any] = field(default_factory=dict)
    processing_notes: list[str] = field(default_factory=list)
    requires_human_approval: bool = False
    confidence_score: float = 1.0  # 0.0 to 1.0
    auto_executable: bool = True


@dataclass
class FeedbackContext:
    """Context for feedback processing decisions."""

    current_stage: Optional[str]
    workflow_progress: float
    completed_stages: list[str]
    failed_stages: list[str]
    feedback_author: str
    feedback_history: list[WorkflowFeedback]
    is_maintainer: bool = False
    has_approval_rights: bool = False


class FeedbackAnalyzer:
    """Analyzes feedback content to understand intent and requirements."""

    # Keywords that indicate different feedback types
    APPROVAL_KEYWORDS = [
        "approve",
        "approved",
        "lgtm",
        "looks good",
        "ship it",
        "ready",
        "good to go",
        "✅",
        "👍",
        "merge",
        "perfect",
        "excellent",
    ]

    REJECTION_KEYWORDS = [
        "reject",
        "rejected",
        "needs work",
        "changes requested",
        "not ready",
        "issues",
        "problems",
        "❌",
        "👎",
        "hold",
        "wait",
        "block",
    ]

    PAUSE_KEYWORDS = ["pause", "stop", "hold", "wait", "suspend", "halt", "break"]

    RESUME_KEYWORDS = [
        "resume",
        "continue",
        "proceed",
        "restart",
        "go ahead",
        "carry on",
    ]

    MODIFICATION_KEYWORDS = [
        "change",
        "modify",
        "update",
        "adjust",
        "fix",
        "improve",
        "add",
        "remove",
    ]

    @classmethod
    def analyze_sentiment(cls, feedback_text: str) -> dict[str, float]:
        """Analyze the sentiment and intent of feedback text."""
        text_lower = feedback_text.lower()

        scores = {
            "approval": 0.0,
            "rejection": 0.0,
            "pause": 0.0,
            "resume": 0.0,
            "modification": 0.0,
        }

        # Count keyword matches
        for keyword in cls.APPROVAL_KEYWORDS:
            if keyword in text_lower:
                scores["approval"] += 1.0

        for keyword in cls.REJECTION_KEYWORDS:
            if keyword in text_lower:
                scores["rejection"] += 1.0

        for keyword in cls.PAUSE_KEYWORDS:
            if keyword in text_lower:
                scores["pause"] += 1.0

        for keyword in cls.RESUME_KEYWORDS:
            if keyword in text_lower:
                scores["resume"] += 1.0

        for keyword in cls.MODIFICATION_KEYWORDS:
            if keyword in text_lower:
                scores["modification"] += 1.0

        # Normalize scores
        total = sum(scores.values())
        if total > 0:
            scores = {k: v / total for k, v in scores.items()}

        return scores

    @classmethod
    def extract_stage_references(cls, feedback_text: str) -> list[str]:
        """Extract references to specific workflow stages."""
        stage_names = [
            "requirements_analysis",
            "requirements",
            "analysis",
            "architecture_design",
            "architecture",
            "design",
            "implementation_planning",
            "implementation",
            "planning",
            "code_implementation",
            "code",
            "coding",
            "testing",
            "tests",
            "test",
            "documentation",
            "docs",
            "deployment",
            "deploy",
        ]

        referenced_stages = []
        text_lower = feedback_text.lower()

        for stage in stage_names:
            if stage in text_lower:
                # Map common names to actual stage names
                if stage in ["requirements", "analysis"]:
                    referenced_stages.append("requirements_analysis")
                elif stage in ["architecture", "design"]:
                    referenced_stages.append("architecture_design")
                elif stage in ["planning"]:
                    referenced_stages.append("implementation_planning")
                elif stage in ["code", "coding"]:
                    referenced_stages.append("code_implementation")
                elif stage in ["tests", "test"]:
                    referenced_stages.append("testing")
                elif stage in ["docs"]:
                    referenced_stages.append("documentation")
                elif stage in ["deploy"]:
                    referenced_stages.append("deployment")
                else:
                    referenced_stages.append(stage)

        return list(set(referenced_stages))  # Remove duplicates


class WorkflowFeedbackProcessor:
    """Processes GitHub feedback and applies it to workflow execution."""

    def __init__(self, workflow_state: WorkflowState):
        """
        Initialize feedback processor.

        Args:
            workflow_state: Current workflow state
        """
        self.state = workflow_state
        self.logger = logging.getLogger("feedback_processor")
        self.pause_manager = WorkflowPauseManager(workflow_state)

        # Feedback processing history
        self.processing_history: list[
            tuple[WorkflowFeedback, FeedbackProcessingResult]
        ] = []

        # Configuration for feedback processing
        self.config = {
            "require_maintainer_approval": False,
            "auto_apply_simple_changes": True,
            "confidence_threshold": 0.7,
            "max_modifications_per_feedback": 5,
        }

    def process_feedback(
        self,
        feedback: WorkflowFeedback,
        context: Optional[FeedbackContext] = None,
    ) -> FeedbackProcessingResult:
        """
        Process a single piece of workflow feedback.

        Args:
            feedback: The feedback to process
            context: Additional context for processing decisions

        Returns:
            FeedbackProcessingResult with the determined action
        """
        if not context:
            context = self._build_context(feedback)

        result = FeedbackProcessingResult(
            action=FeedbackAction.CONTINUE,
            message=f"Processing feedback from {feedback.author}",
        )

        try:
            # Handle direct workflow commands first
            if feedback.feedback_type in ["pause", "resume", "approve", "reject"]:
                result = self._process_direct_command(feedback, context)
            else:
                # Analyze natural language feedback
                result = self._process_natural_feedback(feedback, context)

            # Apply confidence scoring
            result.confidence_score = self._calculate_confidence(
                feedback, context, result
            )

            # Determine if human approval is needed
            result.requires_human_approval = self._requires_human_approval(
                feedback, context, result
            )

            # Log processing result
            self.logger.info(
                f"Processed feedback from {feedback.author}: {result.action.value} "
                f"(confidence: {result.confidence_score:.2f})"
            )

            # Store in processing history
            self.processing_history.append((feedback, result))

            return result

        except Exception as e:
            self.logger.error(f"Error processing feedback: {e}")
            result.action = FeedbackAction.CONTINUE
            result.message = f"Error processing feedback: {e}"
            result.confidence_score = 0.0
            result.auto_executable = False
            return result

    def _process_direct_command(
        self,
        feedback: WorkflowFeedback,
        context: FeedbackContext,
    ) -> FeedbackProcessingResult:
        """Process direct workflow commands like pause, resume, approve, reject."""
        command = feedback.feedback_type

        if command == "pause":
            return FeedbackProcessingResult(
                action=FeedbackAction.PAUSE,
                message=f"Workflow paused by {feedback.author}",
                processing_notes=[f"Direct pause command from {feedback.author}"],
            )

        elif command == "resume":
            target_stage = feedback.stage_name or context.current_stage
            return FeedbackProcessingResult(
                action=FeedbackAction.RESUME,
                stage_name=target_stage,
                message=f"Workflow resumed by {feedback.author}"
                + (f" from stage {target_stage}" if target_stage else ""),
                processing_notes=[f"Direct resume command from {feedback.author}"],
            )

        elif command == "approve":
            return FeedbackProcessingResult(
                action=FeedbackAction.APPROVE_STAGE,
                stage_name=context.current_stage,
                message=f"Current stage approved by {feedback.author}",
                processing_notes=[f"Stage approval from {feedback.author}"],
            )

        elif command == "reject":
            modifications = self._extract_modifications_from_rejection(feedback)
            return FeedbackProcessingResult(
                action=FeedbackAction.REJECT_STAGE,
                stage_name=context.current_stage,
                input_modifications=modifications,
                message=f"Current stage rejected by {feedback.author}",
                processing_notes=[f"Stage rejection from {feedback.author}"],
                requires_human_approval=True,
            )

        return FeedbackProcessingResult(
            action=FeedbackAction.CONTINUE,
            message=f"Unknown command: {command}",
        )

    def _process_natural_feedback(
        self,
        feedback: WorkflowFeedback,
        context: FeedbackContext,
    ) -> FeedbackProcessingResult:
        """Process natural language feedback using sentiment analysis."""
        sentiment = FeedbackAnalyzer.analyze_sentiment(feedback.message)
        referenced_stages = FeedbackAnalyzer.extract_stage_references(feedback.message)

        # Determine primary action based on sentiment
        max_score = max(sentiment.values())
        if max_score == 0:
            return FeedbackProcessingResult(
                action=FeedbackAction.CONTINUE,
                message="No clear action determined from feedback",
                confidence_score=0.0,
            )

        primary_sentiment = max(sentiment, key=sentiment.get)

        if primary_sentiment == "approval":
            return FeedbackProcessingResult(
                action=FeedbackAction.APPROVE_STAGE,
                stage_name=context.current_stage,
                message=f"Approval inferred from feedback by {feedback.author}",
                processing_notes=[f"Sentiment analysis: {sentiment}"],
                confidence_score=sentiment["approval"],
            )

        elif primary_sentiment == "rejection":
            modifications = self._extract_modifications_from_text(feedback.message)
            return FeedbackProcessingResult(
                action=FeedbackAction.REJECT_STAGE,
                stage_name=context.current_stage,
                input_modifications=modifications,
                message=f"Rejection inferred from feedback by {feedback.author}",
                processing_notes=[f"Sentiment analysis: {sentiment}"],
                confidence_score=sentiment["rejection"],
                requires_human_approval=True,
            )

        elif primary_sentiment == "pause":
            return FeedbackProcessingResult(
                action=FeedbackAction.PAUSE,
                message=f"Pause request inferred from feedback by {feedback.author}",
                processing_notes=[f"Sentiment analysis: {sentiment}"],
                confidence_score=sentiment["pause"],
            )

        elif primary_sentiment == "resume":
            target_stage = (
                referenced_stages[0] if referenced_stages else context.current_stage
            )
            return FeedbackProcessingResult(
                action=FeedbackAction.RESUME,
                stage_name=target_stage,
                message=f"Resume request inferred from feedback by {feedback.author}",
                processing_notes=[f"Sentiment analysis: {sentiment}"],
                confidence_score=sentiment["resume"],
            )

        elif primary_sentiment == "modification":
            modifications = self._extract_modifications_from_text(feedback.message)
            return FeedbackProcessingResult(
                action=FeedbackAction.MODIFY_INPUTS,
                input_modifications=modifications,
                message=f"Input modifications suggested by {feedback.author}",
                processing_notes=[f"Sentiment analysis: {sentiment}"],
                confidence_score=sentiment["modification"],
                requires_human_approval=not self.config["auto_apply_simple_changes"],
            )

        return FeedbackProcessingResult(
            action=FeedbackAction.CONTINUE,
            message="Unable to determine clear action from feedback",
            confidence_score=max_score,
        )

    def apply_feedback_result(
        self,
        result: FeedbackProcessingResult,
        force_apply: bool = False,
    ) -> bool:
        """
        Apply a feedback processing result to the workflow.

        Args:
            result: The processing result to apply
            force_apply: Force application even if approval is required

        Returns:
            True if successfully applied, False otherwise
        """
        if result.requires_human_approval and not force_apply:
            self.logger.warning(
                f"Feedback result requires human approval: {result.action.value}"
            )
            return False

        if (
            result.confidence_score < self.config["confidence_threshold"]
            and not force_apply
        ):
            self.logger.warning(
                f"Feedback confidence too low: {result.confidence_score:.2f} < "
                f"{self.config['confidence_threshold']}"
            )
            return False

        try:
            if result.action == FeedbackAction.PAUSE:
                self.pause_manager.request_pause(
                    reason=PauseReason.USER_INPUT,
                    stage_name=result.stage_name or "current",
                    message=result.message,
                    requested_by="github_feedback",
                )
                self.pause_manager.execute_pause()
                return True

            elif result.action == FeedbackAction.RESUME:
                success = self.pause_manager.resume_workflow(
                    resumed_by="github_feedback",
                    message=result.message,
                    skip_current_stage=False,
                    modified_inputs=result.input_modifications,
                )
                return success

            elif result.action == FeedbackAction.APPROVE_STAGE:
                if result.stage_name and result.stage_name in self.state.stages:
                    # Mark stage as approved (custom status)
                    stage = self.state.stages[result.stage_name]
                    if not hasattr(stage, "approval_status"):
                        stage.approval_status = "approved"
                    stage.approval_status = "approved"
                    self.state.save()
                    self.logger.info(f"Approved stage: {result.stage_name}")
                    return True

            elif result.action == FeedbackAction.REJECT_STAGE:
                if result.stage_name and result.stage_name in self.state.stages:
                    # Mark stage as rejected and potentially restart
                    stage = self.state.stages[result.stage_name]
                    if not hasattr(stage, "approval_status"):
                        stage.approval_status = "rejected"
                    stage.approval_status = "rejected"

                    # If stage was completed, reset it to pending for rework
                    if stage.status == StageStatus.COMPLETED:
                        stage.status = StageStatus.PENDING
                        stage.completed_at = None
                        stage.error_message = f"Rejected: {result.message}"

                    self.state.save()
                    self.logger.info(f"Rejected stage: {result.stage_name}")
                    return True

            elif result.action == FeedbackAction.MODIFY_INPUTS:
                if self.state.inputs and result.input_modifications:
                    # Apply input modifications
                    for key, value in result.input_modifications.items():
                        if hasattr(self.state.inputs, key):
                            setattr(self.state.inputs, key, value)
                        else:
                            # Add new dynamic attribute
                            setattr(self.state.inputs, key, value)

                    self.state.save()
                    self.logger.info(
                        f"Applied input modifications: {result.input_modifications}"
                    )
                    return True

            elif result.action == FeedbackAction.RESTART_STAGE:
                if result.stage_name and result.stage_name in self.state.stages:
                    stage = self.state.stages[result.stage_name]
                    stage.status = StageStatus.PENDING
                    stage.completed_at = None
                    stage.started_at = None
                    stage.error_message = None
                    self.state.save()
                    self.logger.info(f"Restarted stage: {result.stage_name}")
                    return True

            elif result.action == FeedbackAction.SKIP_STAGE:
                if result.stage_name and result.stage_name in self.state.stages:
                    stage = self.state.stages[result.stage_name]
                    stage.status = StageStatus.SKIPPED
                    stage.completed_at = datetime.now(UTC)
                    self.state.save()
                    self.logger.info(f"Skipped stage: {result.stage_name}")
                    return True

            return False

        except Exception as e:
            self.logger.error(f"Error applying feedback result: {e}")
            return False

    def _build_context(self, feedback: WorkflowFeedback) -> FeedbackContext:
        """Build context for feedback processing."""
        summary = self.state.get_summary()

        # Determine current stage
        current_stage = None
        for stage_name, stage in self.state.stages.items():
            if stage.status == StageStatus.RUNNING:
                current_stage = stage_name
                break

        # Get completed and failed stages
        completed_stages = [
            name
            for name, stage in self.state.stages.items()
            if stage.status == StageStatus.COMPLETED
        ]
        failed_stages = [
            name
            for name, stage in self.state.stages.items()
            if stage.status == StageStatus.FAILED
        ]

        return FeedbackContext(
            current_stage=current_stage,
            workflow_progress=summary["progress_percent"] / 100.0,
            completed_stages=completed_stages,
            failed_stages=failed_stages,
            feedback_author=feedback.author,
            feedback_history=self._get_author_feedback_history(feedback.author),
            is_maintainer=self._is_maintainer(feedback.author),
            has_approval_rights=self._has_approval_rights(feedback.author),
        )

    def _calculate_confidence(
        self,
        feedback: WorkflowFeedback,
        context: FeedbackContext,
        result: FeedbackProcessingResult,
    ) -> float:
        """Calculate confidence score for feedback processing result."""
        base_confidence = result.confidence_score

        # Adjust based on author credentials
        if context.has_approval_rights:
            base_confidence *= 1.2
        elif context.is_maintainer:
            base_confidence *= 1.1

        # Adjust based on feedback clarity
        if feedback.feedback_type in ["approve", "reject", "pause", "resume"]:
            base_confidence *= 1.3  # Direct commands are high confidence

        # Adjust based on feedback history
        if len(context.feedback_history) > 0:
            # Frequent contributors get slight boost
            base_confidence *= 1.05

        return min(base_confidence, 1.0)

    def _requires_human_approval(
        self,
        feedback: WorkflowFeedback,
        context: FeedbackContext,
        result: FeedbackProcessingResult,
    ) -> bool:
        """Determine if feedback result requires human approval."""
        # Direct rejections always need approval
        if result.action in [
            FeedbackAction.REJECT_STAGE,
            FeedbackAction.ABORT_WORKFLOW,
        ]:
            return True

        # Low confidence results need approval
        if result.confidence_score < self.config["confidence_threshold"]:
            return True

        # Input modifications need approval unless auto-apply is enabled
        if (
            result.action == FeedbackAction.MODIFY_INPUTS
            and not self.config["auto_apply_simple_changes"]
        ):
            return True

        # Non-maintainers need approval for structural changes
        if not context.has_approval_rights and result.action in [
            FeedbackAction.RESTART_STAGE,
            FeedbackAction.SKIP_STAGE,
        ]:
            return True

        return False

    def _extract_modifications_from_rejection(
        self,
        feedback: WorkflowFeedback,
    ) -> dict[str, Any]:
        """Extract structured modifications from rejection feedback."""
        if feedback.requested_changes:
            return feedback.requested_changes

        return self._extract_modifications_from_text(feedback.message)

    def _extract_modifications_from_text(self, text: str) -> dict[str, Any]:
        """Extract potential modifications from natural language text."""
        modifications = {}

        # Simple keyword-based extraction
        lines = text.split("\n")
        for line in lines:
            line = line.strip().lower()

            # Look for specific modification requests
            if "add" in line and ("test" in line or "testing" in line):
                modifications["additional_testing_requirements"] = line
            elif "change" in line or "modify" in line:
                modifications["requested_changes"] = modifications.get(
                    "requested_changes", []
                )
                modifications["requested_changes"].append(line)
            elif "fix" in line or "error" in line:
                modifications["bug_fixes_needed"] = modifications.get(
                    "bug_fixes_needed", []
                )
                modifications["bug_fixes_needed"].append(line)

        return modifications

    def _get_author_feedback_history(self, author: str) -> list[WorkflowFeedback]:
        """Get feedback history for a specific author."""
        return [
            feedback
            for feedback, _ in self.processing_history
            if feedback.author == author
        ]

    def _is_maintainer(self, author: str) -> bool:
        """Check if author is a repository maintainer."""
        # Placeholder - would integrate with GitHub API
        # For now, simple heuristic based on common maintainer names
        maintainer_keywords = ["admin", "maintainer", "owner", "lead"]
        return any(keyword in author.lower() for keyword in maintainer_keywords)

    def _has_approval_rights(self, author: str) -> bool:
        """Check if author has approval rights."""
        # Placeholder - would integrate with GitHub repository permissions
        return self._is_maintainer(author)

    def get_feedback_summary(self) -> dict[str, Any]:
        """Get summary of all processed feedback."""
        if not self.processing_history:
            return {"total_feedback": 0}

        actions = [result.action.value for _, result in self.processing_history]
        authors = [feedback.author for feedback, _ in self.processing_history]
        avg_confidence = sum(
            result.confidence_score for _, result in self.processing_history
        ) / len(self.processing_history)

        return {
            "total_feedback": len(self.processing_history),
            "unique_authors": len(set(authors)),
            "action_counts": {action: actions.count(action) for action in set(actions)},
            "average_confidence": avg_confidence,
            "approval_required_count": sum(
                1
                for _, result in self.processing_history
                if result.requires_human_approval
            ),
        }
