#!/usr/bin/env python3
"""
Tests for Feedback Processor Module in Enhanced Multi-Agent Workflow System
"""


from multi_agent_workflow.feedback_processor import (
    FeedbackAction,
    FeedbackAnalyzer,
    FeedbackContext,
    FeedbackProcessingResult,
    WorkflowFeedbackProcessor,
)
from multi_agent_workflow.github_integrator import WorkflowFeedback
from multi_agent_workflow.workflow_state import (
    StageStatus,
    WorkflowInputs,
    WorkflowState,
)


class TestFeedbackAnalyzer:
    """Test FeedbackAnalyzer functionality."""

    def test_analyze_approval_sentiment(self):
        """Test analyzing approval sentiment."""
        approval_text = "This looks great! LGTM and ready to ship."
        sentiment = FeedbackAnalyzer.analyze_sentiment(approval_text)

        assert sentiment["approval"] > sentiment["rejection"]
        assert sentiment["approval"] > 0.5

    def test_analyze_rejection_sentiment(self):
        """Test analyzing rejection sentiment."""
        rejection_text = (
            "This needs more work. I see several issues and changes are requested."
        )
        sentiment = FeedbackAnalyzer.analyze_sentiment(rejection_text)

        assert sentiment["rejection"] > sentiment["approval"]
        assert sentiment["rejection"] > 0.5

    def test_analyze_pause_sentiment(self):
        """Test analyzing pause sentiment."""
        pause_text = "Please pause this workflow until we can review the architecture."
        sentiment = FeedbackAnalyzer.analyze_sentiment(pause_text)

        assert sentiment["pause"] > 0.5

    def test_analyze_resume_sentiment(self):
        """Test analyzing resume sentiment."""
        resume_text = (
            "Thanks for the fixes! Please resume and continue with the implementation."
        )
        sentiment = FeedbackAnalyzer.analyze_sentiment(resume_text)

        assert sentiment["resume"] > 0.5

    def test_analyze_modification_sentiment(self):
        """Test analyzing modification sentiment."""
        modification_text = (
            "Please change the database schema and fix the API endpoints."
        )
        sentiment = FeedbackAnalyzer.analyze_sentiment(modification_text)

        assert sentiment["modification"] > 0.5

    def test_extract_stage_references(self):
        """Test extracting stage references from text."""
        text = "The requirements analysis looks good, but the architecture design needs work."
        stages = FeedbackAnalyzer.extract_stage_references(text)

        assert "requirements_analysis" in stages
        assert "architecture_design" in stages

    def test_extract_common_stage_names(self):
        """Test extracting common stage name variations."""
        text = "The tests are failing and the docs need updates."
        stages = FeedbackAnalyzer.extract_stage_references(text)

        assert "testing" in stages
        assert "documentation" in stages

    def test_mixed_sentiment_analysis(self):
        """Test analyzing text with mixed sentiment."""
        mixed_text = (
            "The implementation looks good, but please pause and add more tests."
        )
        sentiment = FeedbackAnalyzer.analyze_sentiment(mixed_text)

        assert sentiment["approval"] > 0
        assert sentiment["pause"] > 0
        assert sentiment["modification"] > 0


class TestWorkflowFeedbackProcessor:
    """Test WorkflowFeedbackProcessor functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.state = WorkflowState("test_workflow")
        self.state.inputs = WorkflowInputs(
            project_description="Test project",
            target_directory="/tmp/test",
        )

        # Set up some stages
        self.state.start_stage("requirements_analysis")
        self.state.complete_stage("requirements_analysis")
        self.state.start_stage("architecture_design")

        self.processor = WorkflowFeedbackProcessor(self.state)

    def test_processor_initialization(self):
        """Test initializing feedback processor."""
        assert self.processor.state == self.state
        assert len(self.processor.processing_history) == 0
        assert self.processor.config["auto_apply_simple_changes"] is True

    def test_process_direct_approve_command(self):
        """Test processing direct approve command."""
        feedback = WorkflowFeedback(
            pr_number=1,
            comment_id=123,
            author="maintainer",
            feedback_type="approve",
            message="LGTM - approved!",
        )

        result = self.processor.process_feedback(feedback)

        assert result.action == FeedbackAction.APPROVE_STAGE
        assert result.stage_name == "architecture_design"  # Current running stage
        assert "maintainer" in result.message
        assert result.confidence_score > 0.8

    def test_process_direct_reject_command(self):
        """Test processing direct reject command."""
        feedback = WorkflowFeedback(
            pr_number=1,
            comment_id=124,
            author="reviewer",
            feedback_type="reject",
            message="Changes requested - add more error handling",
            requested_changes={
                "error_handling": ["Add try-catch blocks", "Validate inputs"]
            },
        )

        result = self.processor.process_feedback(feedback)

        assert result.action == FeedbackAction.REJECT_STAGE
        assert result.stage_name == "architecture_design"
        assert result.requires_human_approval is True
        assert "error_handling" in result.input_modifications

    def test_process_direct_pause_command(self):
        """Test processing direct pause command."""
        feedback = WorkflowFeedback(
            pr_number=1,
            comment_id=125,
            author="lead_dev",
            feedback_type="pause",
            message="Pause for architecture review",
        )

        result = self.processor.process_feedback(feedback)

        assert result.action == FeedbackAction.PAUSE
        assert "lead_dev" in result.message
        assert result.auto_executable is True

    def test_process_direct_resume_command(self):
        """Test processing direct resume command."""
        feedback = WorkflowFeedback(
            pr_number=1,
            comment_id=126,
            author="maintainer",
            feedback_type="resume",
            message="Resume from testing stage",
            stage_name="testing",
        )

        result = self.processor.process_feedback(feedback)

        assert result.action == FeedbackAction.RESUME
        assert result.stage_name == "testing"
        assert result.auto_executable is True

    def test_process_natural_approval_feedback(self):
        """Test processing natural language approval."""
        feedback = WorkflowFeedback(
            pr_number=1,
            comment_id=127,
            author="reviewer",
            feedback_type="",  # Not explicit command
            message="This looks excellent! Great work on the architecture. Ready to proceed.",
        )

        result = self.processor.process_feedback(feedback)

        assert result.action == FeedbackAction.APPROVE_STAGE
        assert result.confidence_score > 0.3  # Based on sentiment analysis

    def test_process_natural_rejection_feedback(self):
        """Test processing natural language rejection."""
        feedback = WorkflowFeedback(
            pr_number=1,
            comment_id=128,
            author="senior_dev",
            feedback_type="",
            message="I see several issues here. The error handling needs work and we need more tests.",
        )

        result = self.processor.process_feedback(feedback)

        assert result.action == FeedbackAction.REJECT_STAGE
        assert result.requires_human_approval is True
        assert len(result.input_modifications) > 0

    def test_process_modification_feedback(self):
        """Test processing modification requests."""
        feedback = WorkflowFeedback(
            pr_number=1,
            comment_id=129,
            author="architect",
            feedback_type="",
            message="Please change the database design and add authentication middleware.",
        )

        result = self.processor.process_feedback(feedback)

        assert result.action == FeedbackAction.MODIFY_INPUTS
        assert len(result.input_modifications) > 0

    def test_build_context(self):
        """Test building feedback context."""
        feedback = WorkflowFeedback(
            pr_number=1,
            comment_id=130,
            author="contributor",
            feedback_type="approve",
            message="Looks good",
        )

        context = self.processor._build_context(feedback)

        assert context.current_stage == "architecture_design"
        assert context.workflow_progress > 0.1  # Some progress made
        assert "requirements_analysis" in context.completed_stages
        assert len(context.failed_stages) == 0
        assert context.feedback_author == "contributor"

    def test_calculate_confidence_scores(self):
        """Test confidence score calculations."""
        # High confidence direct command
        direct_feedback = WorkflowFeedback(
            pr_number=1,
            comment_id=131,
            author="maintainer",
            feedback_type="approve",
            message="LGTM",
        )

        context = FeedbackContext(
            current_stage="testing",
            workflow_progress=0.5,
            completed_stages=["requirements_analysis"],
            failed_stages=[],
            feedback_author="maintainer",
            feedback_history=[],
            is_maintainer=True,
            has_approval_rights=True,
        )

        result = self.processor.process_feedback(direct_feedback, context)
        assert result.confidence_score > 0.8

        # Lower confidence natural language
        natural_feedback = WorkflowFeedback(
            pr_number=1,
            comment_id=132,
            author="contributor",
            feedback_type="",
            message="Maybe this could use some improvements",
        )

        result = self.processor.process_feedback(natural_feedback)
        assert result.confidence_score < 0.5

    def test_apply_approval_feedback(self):
        """Test applying approval feedback to workflow."""
        result = FeedbackProcessingResult(
            action=FeedbackAction.APPROVE_STAGE,
            stage_name="architecture_design",
            message="Stage approved",
            confidence_score=0.9,
            auto_executable=True,
        )

        success = self.processor.apply_feedback_result(result, force_apply=True)
        assert success is True

        # Check that stage was marked as approved
        stage = self.state.stages["architecture_design"]
        assert hasattr(stage, "approval_status")
        assert stage.approval_status == "approved"

    def test_apply_rejection_feedback(self):
        """Test applying rejection feedback to workflow."""
        # First complete the stage
        self.state.complete_stage("architecture_design")

        result = FeedbackProcessingResult(
            action=FeedbackAction.REJECT_STAGE,
            stage_name="architecture_design",
            message="Stage rejected",
            confidence_score=0.8,
            requires_human_approval=True,
        )

        success = self.processor.apply_feedback_result(result, force_apply=True)
        assert success is True

        # Check that stage was reset
        stage = self.state.stages["architecture_design"]
        assert stage.status == StageStatus.PENDING
        assert stage.approval_status == "rejected"

    def test_apply_input_modifications(self):
        """Test applying input modifications."""
        result = FeedbackProcessingResult(
            action=FeedbackAction.MODIFY_INPUTS,
            input_modifications={
                "additional_requirements": "Add user authentication",
                "new_parameter": "security_level_high",
            },
            confidence_score=0.8,
            auto_executable=True,
        )

        success = self.processor.apply_feedback_result(result, force_apply=True)
        assert success is True

        # Check that inputs were modified
        assert hasattr(self.state.inputs, "additional_requirements")
        assert self.state.inputs.additional_requirements == "Add user authentication"
        assert hasattr(self.state.inputs, "new_parameter")
        assert self.state.inputs.new_parameter == "security_level_high"

    def test_apply_stage_restart(self):
        """Test restarting a stage based on feedback."""
        # Complete the stage first
        self.state.complete_stage("architecture_design")

        result = FeedbackProcessingResult(
            action=FeedbackAction.RESTART_STAGE,
            stage_name="architecture_design",
            confidence_score=0.9,
        )

        success = self.processor.apply_feedback_result(result, force_apply=True)
        assert success is True

        # Check that stage was reset
        stage = self.state.stages["architecture_design"]
        assert stage.status == StageStatus.PENDING
        assert stage.completed_at is None
        assert stage.started_at is None

    def test_apply_stage_skip(self):
        """Test skipping a stage based on feedback."""
        result = FeedbackProcessingResult(
            action=FeedbackAction.SKIP_STAGE,
            stage_name="architecture_design",
            confidence_score=0.8,
        )

        success = self.processor.apply_feedback_result(result, force_apply=True)
        assert success is True

        # Check that stage was skipped
        stage = self.state.stages["architecture_design"]
        assert stage.status == StageStatus.SKIPPED
        assert stage.completed_at is not None

    def test_human_approval_requirements(self):
        """Test human approval requirement logic."""
        # High-impact rejection should require approval
        rejection_result = FeedbackProcessingResult(
            action=FeedbackAction.REJECT_STAGE,
            confidence_score=0.9,
        )

        requires_approval = self.processor._requires_human_approval(
            WorkflowFeedback(1, 1, "user", "reject", "needs work"),
            FeedbackContext(
                current_stage="testing",
                workflow_progress=0.5,
                completed_stages=[],
                failed_stages=[],
                feedback_author="user",
                feedback_history=[],
                has_approval_rights=False,
            ),
            rejection_result,
        )

        assert requires_approval is True

        # Low confidence should require approval
        low_confidence_result = FeedbackProcessingResult(
            action=FeedbackAction.APPROVE_STAGE,
            confidence_score=0.3,
        )

        requires_approval = self.processor._requires_human_approval(
            WorkflowFeedback(1, 1, "user", "approve", "looks ok"),
            FeedbackContext(
                current_stage="testing",
                workflow_progress=0.5,
                completed_stages=[],
                failed_stages=[],
                feedback_author="user",
                feedback_history=[],
                has_approval_rights=True,
            ),
            low_confidence_result,
        )

        assert requires_approval is True

    def test_feedback_history_tracking(self):
        """Test tracking of feedback processing history."""
        feedback1 = WorkflowFeedback(
            pr_number=1,
            comment_id=201,
            author="user1",
            feedback_type="approve",
            message="LGTM",
        )

        feedback2 = WorkflowFeedback(
            pr_number=1,
            comment_id=202,
            author="user2",
            feedback_type="reject",
            message="Needs work",
        )

        result1 = self.processor.process_feedback(feedback1)
        result2 = self.processor.process_feedback(feedback2)

        assert len(self.processor.processing_history) == 2
        assert self.processor.processing_history[0][0] == feedback1
        assert self.processor.processing_history[0][1] == result1
        assert self.processor.processing_history[1][0] == feedback2
        assert self.processor.processing_history[1][1] == result2

    def test_get_feedback_summary(self):
        """Test getting feedback summary."""
        # Process some feedback first
        feedbacks = [
            WorkflowFeedback(1, 301, "user1", "approve", "Good"),
            WorkflowFeedback(1, 302, "user2", "reject", "Bad"),
            WorkflowFeedback(1, 303, "user1", "approve", "Fixed"),
        ]

        for feedback in feedbacks:
            self.processor.process_feedback(feedback)

        summary = self.processor.get_feedback_summary()

        assert summary["total_feedback"] == 3
        assert summary["unique_authors"] == 2
        assert "approve_stage" in summary["action_counts"]
        assert "reject_stage" in summary["action_counts"]
        assert summary["average_confidence"] > 0

    def test_extract_modifications_from_text(self):
        """Test extracting modifications from natural language."""
        text = """
        Please make the following changes:
        - Add unit tests for the user service
        - Fix the authentication bug in login
        - Change the database connection timeout
        """

        modifications = self.processor._extract_modifications_from_text(text)

        assert "additional_testing_requirements" in modifications
        assert "bug_fixes_needed" in modifications
        assert "requested_changes" in modifications

    def test_maintainer_detection(self):
        """Test maintainer detection logic."""
        # This is a placeholder test - in real implementation,
        # this would integrate with GitHub API
        assert self.processor._is_maintainer("admin_user") is True
        assert self.processor._is_maintainer("regular_user") is False

    def test_approval_rights_detection(self):
        """Test approval rights detection."""
        # This is a placeholder test - in real implementation,
        # this would integrate with GitHub repository permissions
        assert self.processor._has_approval_rights("maintainer_user") is True
        assert self.processor._has_approval_rights("contributor") is False

    def test_confidence_threshold_enforcement(self):
        """Test that low confidence results are not auto-applied."""
        low_confidence_result = FeedbackProcessingResult(
            action=FeedbackAction.APPROVE_STAGE,
            confidence_score=0.3,  # Below default threshold of 0.7
        )

        success = self.processor.apply_feedback_result(low_confidence_result)
        assert success is False  # Should not apply due to low confidence

        # But should work with force_apply
        success = self.processor.apply_feedback_result(
            low_confidence_result, force_apply=True
        )
        assert success is True
