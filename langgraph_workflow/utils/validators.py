"""State validation utilities for the workflow."""

import logging
from typing import Any, Optional

from langgraph_workflow.state import (
    WorkflowState, 
    WorkflowPhase, 
    AgentType, 
    QualityState, 
    FeedbackGate
)

logger = logging.getLogger(__name__)

class StateValidator:
    """Validates workflow state integrity and transitions."""
    
    @staticmethod
    def validate_state(state: WorkflowState) -> tuple[bool, list[str]]:
        """Validate complete workflow state.
        
        Args:
            state: State to validate
            
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        
        # Required fields
        required_fields = ["thread_id", "repo_name", "repo_path"]
        for field in required_fields:
            if not state.get(field):
                errors.append(f"Missing required field: {field}")
        
        # Validate enum fields
        phase_error = StateValidator._validate_enum_field(
            state.get("current_phase"), WorkflowPhase, "current_phase"
        )
        if phase_error:
            errors.append(phase_error)
        
        quality_error = StateValidator._validate_enum_field(
            state.get("quality_state"), QualityState, "quality_state"
        )
        if quality_error:
            errors.append(quality_error)
        
        gate_error = StateValidator._validate_enum_field(
            state.get("feedback_gate"), FeedbackGate, "feedback_gate"
        )
        if gate_error:
            errors.append(gate_error)
        
        # Validate agent analyses
        agent_analyses = state.get("agent_analyses", {})
        for agent_key in agent_analyses.keys():
            if not any(agent_key == agent_type.value for agent_type in AgentType):
                errors.append(f"Invalid agent type in analyses: {agent_key}")
        
        # Validate state consistency
        consistency_errors = StateValidator._validate_state_consistency(state)
        errors.extend(consistency_errors)
        
        return len(errors) == 0, errors
    
    @staticmethod
    def validate_phase_transition(current_phase: WorkflowPhase, next_phase: WorkflowPhase) -> bool:
        """Validate if a phase transition is allowed.
        
        Args:
            current_phase: Current workflow phase
            next_phase: Desired next phase
            
        Returns:
            True if transition is valid
        """
        # Define valid transitions
        valid_transitions = {
            WorkflowPhase.ANALYSIS: [WorkflowPhase.DESIGN],
            WorkflowPhase.DESIGN: [WorkflowPhase.FINALIZATION, WorkflowPhase.IMPLEMENTATION],
            WorkflowPhase.FINALIZATION: [WorkflowPhase.IMPLEMENTATION, WorkflowPhase.DESIGN],
            WorkflowPhase.IMPLEMENTATION: [WorkflowPhase.FINALIZATION]  # Can go back for fixes
        }
        
        allowed_next = valid_transitions.get(current_phase, [])
        return next_phase in allowed_next
    
    @staticmethod
    def validate_required_artifacts(state: WorkflowState) -> tuple[bool, list[str]]:
        """Validate that required artifacts exist for current phase.
        
        Args:
            state: State to validate
            
        Returns:
            Tuple of (is_valid, list_of_missing_artifacts)
        """
        missing = []
        current_phase = state.get("current_phase")
        
        if current_phase == WorkflowPhase.DESIGN:
            # Require codebase analysis and agent analyses
            if not state.get("codebase_analysis"):
                missing.append("codebase_analysis")
            
            agent_analyses = state.get("agent_analyses", {})
            expected_agents = {agent_type.value for agent_type in AgentType}
            missing_agents = expected_agents - set(agent_analyses.keys())
            if missing_agents:
                missing.extend([f"agent_analysis:{agent}" for agent in missing_agents])
        
        elif current_phase == WorkflowPhase.FINALIZATION:
            # Require consolidated design
            if not state.get("consolidated_design"):
                missing.append("consolidated_design")
        
        elif current_phase == WorkflowPhase.IMPLEMENTATION:
            # Require finalized or consolidated design
            if not (state.get("finalized_design") or state.get("consolidated_design")):
                missing.append("design_document")
        
        return len(missing) == 0, missing
    
    @staticmethod
    def validate_pr_integration(state: WorkflowState) -> tuple[bool, list[str]]:
        """Validate PR integration requirements.
        
        Args:
            state: State to validate
            
        Returns:
            Tuple of (is_valid, list_of_issues)
        """
        issues = []
        
        # If PR number is set, validate related fields
        pr_number = state.get("pr_number")
        if pr_number:
            if not isinstance(pr_number, int) or pr_number <= 0:
                issues.append("Invalid PR number format")
            
            # If we have PR comments, validate they're properly formatted
            pr_comments = state.get("pr_comments", [])
            for i, comment in enumerate(pr_comments):
                if not isinstance(comment, dict):
                    issues.append(f"PR comment {i} is not a dict")
                elif "id" not in comment:
                    issues.append(f"PR comment {i} missing ID")
        
        # Validate feedback addressing
        feedback_addressed = state.get("feedback_addressed", {})
        pr_comments = state.get("pr_comments", [])
        
        # Check if all comments are accounted for
        comment_ids = {str(comment.get("id", "")) for comment in pr_comments if comment.get("id")}
        addressed_ids = set(feedback_addressed.keys())
        
        untracked_comments = comment_ids - addressed_ids
        if untracked_comments:
            issues.append(f"Untracked PR comments: {list(untracked_comments)}")
        
        return len(issues) == 0, issues
    
    @staticmethod
    def validate_test_integration(state: WorkflowState) -> tuple[bool, list[str]]:
        """Validate test execution integration.
        
        Args:
            state: State to validate
            
        Returns:
            Tuple of (is_valid, list_of_issues)
        """
        issues = []
        
        test_results = state.get("test_results")
        if test_results:
            # Validate test results structure
            required_fields = ["returncode", "passed", "timestamp"]
            for field in required_fields:
                if field not in test_results:
                    issues.append(f"Test results missing field: {field}")
            
            # Validate consistency
            passed = test_results.get("passed")
            returncode = test_results.get("returncode")
            
            if passed and returncode != 0:
                issues.append("Test results inconsistent: passed=True but returncode != 0")
            elif not passed and returncode == 0:
                issues.append("Test results inconsistent: passed=False but returncode == 0")
        
        # Validate quality state alignment
        quality_state = state.get("quality_state")
        if test_results and quality_state:
            test_passed = test_results.get("passed", False)
            
            if test_passed and quality_state == QualityState.FAIL:
                issues.append("Quality state inconsistent with test results")
            elif not test_passed and quality_state == QualityState.OK:
                issues.append("Quality state inconsistent with failing tests")
        
        return len(issues) == 0, issues
    
    @staticmethod
    def validate_retry_logic(state: WorkflowState) -> tuple[bool, list[str]]:
        """Validate retry count and escalation logic.
        
        Args:
            state: State to validate
            
        Returns:
            Tuple of (is_valid, list_of_issues)
        """
        issues = []
        
        retry_count = state.get("retry_count", 0)
        escalation_needed = state.get("escalation_needed", False)
        
        # Validate retry count
        if not isinstance(retry_count, int) or retry_count < 0:
            issues.append("Invalid retry count")
        
        if retry_count > 10:  # Reasonable upper limit
            issues.append("Retry count unexpectedly high")
        
        # Validate escalation logic
        if retry_count >= 2 and not escalation_needed:
            issues.append("High retry count but no escalation flag")
        
        return len(issues) == 0, issues
    
    @staticmethod
    def _validate_enum_field(value: Any, enum_class: type, field_name: str) -> Optional[str]:
        """Validate a field that should be an enum value.
        
        Args:
            value: Value to validate
            enum_class: Expected enum class
            field_name: Field name for error message
            
        Returns:
            Error message or None if valid
        """
        if value is None:
            return None  # Optional field
        
        if not isinstance(value, enum_class):
            return f"Invalid {field_name}: {value} (expected {enum_class.__name__})"
        
        return None
    
    @staticmethod
    def _validate_state_consistency(state: WorkflowState) -> list[str]:
        """Validate internal state consistency.
        
        Args:
            state: State to validate
            
        Returns:
            List of consistency errors
        """
        errors = []
        
        # Validate messages window size
        messages_window = state.get("messages_window", [])
        if len(messages_window) > 20:  # Reasonable limit
            errors.append("Messages window too large (should be truncated)")
        
        # Validate artifact index consistency
        artifacts_index = state.get("artifacts_index", {})
        if artifacts_index:
            # All paths should be strings
            invalid_paths = [
                key for key, path in artifacts_index.items() 
                if not isinstance(path, str)
            ]
            if invalid_paths:
                errors.append(f"Invalid artifact paths: {invalid_paths}")
        
        # Validate code artifacts consistency
        skeleton_code = state.get("skeleton_code", {})
        implementation_code = state.get("implementation_code", {})
        test_code = state.get("test_code", {})
        
        # If we have implementation, we should have skeleton
        if implementation_code and not skeleton_code:
            errors.append("Implementation exists without skeleton")
        
        # If we have tests, we should have skeleton
        if test_code and not skeleton_code:
            errors.append("Tests exist without skeleton")
        
        return errors
    
    @staticmethod
    def get_validation_summary(state: WorkflowState) -> dict:
        """Get comprehensive validation summary.
        
        Args:
            state: State to validate
            
        Returns:
            Validation summary with all checks
        """
        summary = {
            "overall_valid": True,
            "total_errors": 0,
            "checks": {}
        }
        
        # Run all validation checks
        checks = [
            ("state_structure", StateValidator.validate_state),
            ("required_artifacts", StateValidator.validate_required_artifacts),
            ("pr_integration", StateValidator.validate_pr_integration),
            ("test_integration", StateValidator.validate_test_integration),
            ("retry_logic", StateValidator.validate_retry_logic)
        ]
        
        for check_name, check_func in checks:
            try:
                is_valid, errors = check_func(state)
                summary["checks"][check_name] = {
                    "valid": is_valid,
                    "errors": errors,
                    "error_count": len(errors)
                }
                
                if not is_valid:
                    summary["overall_valid"] = False
                    summary["total_errors"] += len(errors)
                    
            except Exception as e:
                logger.error(f"Validation check {check_name} failed: {e}")
                summary["checks"][check_name] = {
                    "valid": False,
                    "errors": [f"Check failed: {str(e)}"],
                    "error_count": 1
                }
                summary["overall_valid"] = False
                summary["total_errors"] += 1
        
        return summary