"""Interrupt nodes for human-in-the-loop workflow control."""

import logging
from typing import Any

from langgraph.types import interrupt
from langgraph_workflow.state import WorkflowState, FeedbackGate

logger = logging.getLogger(__name__)

class InterruptNodes:
    """Interrupt nodes for pausing workflow for human review."""
    
    @staticmethod
    async def wait_for_review(state: WorkflowState) -> dict:
        """Pause workflow for human review and feedback.
        
        This creates a static interrupt that pauses the workflow
        until manually resumed.
        """
        logger.info("Pausing workflow for human review")
        
        # Set feedback gate to hold
        state["feedback_gate"] = FeedbackGate.HOLD
        state["paused_for_review"] = True
        
        # Add pause message to window
        state["messages_window"].append({
            "role": "system",
            "content": "Workflow paused for human review",
            "pause_reason": "awaiting_feedback",
            "pr_number": state.get("pr_number")
        })
        
        # Create interrupt with context
        interrupt_message = f"""
🛑 Workflow Paused for Review

**Thread ID**: {state['thread_id']}
**Phase**: {state['current_phase'].value if hasattr(state['current_phase'], 'value') else state['current_phase']}
**Feature**: {state.get('feature_name', 'Unknown')}

**Review Required For**:
- Design documents and analysis
- PR #{state.get('pr_number', 'TBD')} feedback
- Quality assurance

**Next Steps**:
1. Review PR and artifacts on GitHub
2. Add comments and feedback
3. Resume workflow to process feedback

**Artifacts Available**:
"""
        
        # Add artifact links
        for artifact_name in state.get("artifacts_index", {}):
            interrupt_message += f"- {artifact_name}\n"
        
        # This creates a static interrupt that requires manual resume
        interrupt(interrupt_message)
        
        return state
    
    @staticmethod
    async def preview_changes(state: WorkflowState, changes_summary: str = None) -> dict:
        """Preview changes before applying them.
        
        Shows a diff or summary of changes and waits for approval.
        """
        logger.info("Pausing to preview changes")
        
        if not changes_summary:
            changes_summary = "Code changes ready for review"
        
        # Add preview to messages
        state["messages_window"].append({
            "role": "system",
            "content": "Previewing changes for approval",
            "changes": changes_summary
        })
        
        preview_message = f"""
📋 Change Preview

**Thread ID**: {state['thread_id']}
**Changes**: {changes_summary}

**Preview**:
{changes_summary}

**Options**:
- Continue: Apply these changes
- Modify: Request changes to the approach
- Skip: Skip this change set

Resume to continue with changes.
"""
        
        interrupt(preview_message)
        
        return state
    
    @staticmethod
    async def escalation_gate(state: WorkflowState, escalation_reason: str = None) -> dict:
        """Pause before escalating to more expensive models.
        
        Gives human a chance to review before using Claude for complex tasks.
        """
        logger.info("Pausing before model escalation")
        
        if not escalation_reason:
            escalation_reason = "Complex task requiring escalation"
        
        # Mark escalation needed
        state["escalation_needed"] = True
        
        # Add escalation info to messages
        state["messages_window"].append({
            "role": "system",
            "content": "Requesting escalation approval",
            "reason": escalation_reason,
            "retry_count": state.get("retry_count", 0)
        })
        
        escalation_message = f"""
⚡ Model Escalation Required

**Thread ID**: {state['thread_id']}
**Reason**: {escalation_reason}
**Current Retry Count**: {state.get('retry_count', 0)}

**Escalation Details**:
- Will switch from local Ollama to Claude
- Increased API costs
- Better reasoning for complex problems

**Options**:
- Approve: Proceed with Claude escalation
- Retry: Try local model one more time
- Manual: Pause for manual intervention

Resume to proceed with escalation.
"""
        
        interrupt(escalation_message)
        
        return state
    
    @staticmethod
    async def quality_gate(state: WorkflowState) -> dict:
        """Quality gate interrupt for critical checkpoints.
        
        Pauses at key quality checkpoints to ensure standards are met.
        """
        logger.info("Quality gate checkpoint")
        
        quality_state = state.get("quality_state")
        test_results = state.get("test_results", {})
        lint_status = state.get("lint_status", {})
        
        # Build quality summary
        quality_summary = []
        
        if test_results:
            test_status = "PASS" if test_results.get("passed") else "FAIL"
            quality_summary.append(f"Tests: {test_status}")
        
        if lint_status:
            lint_pass = lint_status.get("passed", True)
            lint_summary = f"Lint: {'PASS' if lint_pass else 'FAIL'}"
            if not lint_pass:
                lint_summary += f" ({lint_status.get('error_count', 0)} errors)"
            quality_summary.append(lint_summary)
        
        quality_summary.append(f"Overall: {quality_state.value if hasattr(quality_state, 'value') else quality_state}")
        
        state["messages_window"].append({
            "role": "system",
            "content": "Quality gate checkpoint",
            "quality_summary": quality_summary
        })
        
        gate_message = f"""
🔍 Quality Gate Checkpoint

**Thread ID**: {state['thread_id']}
**Phase**: {state['current_phase'].value if hasattr(state['current_phase'], 'value') else state['current_phase']}

**Quality Status**:
{chr(10).join(f"- {item}" for item in quality_summary)}

**Quality Details**:
- Retry Count: {state.get('retry_count', 0)}
- Escalation Needed: {state.get('escalation_needed', False)}

**Options**:
- Continue: Proceed with current quality level
- Fix: Address quality issues before continuing
- Review: Manual quality review

Resume to continue or address quality issues.
"""
        
        interrupt(gate_message)
        
        return state
    
    @staticmethod
    async def feedback_processing(state: WorkflowState) -> dict:
        """Pause after processing feedback to review responses.
        
        Shows how feedback was processed and what responses will be sent.
        """
        logger.info("Pausing after feedback processing")
        
        pr_comments = state.get("pr_comments", [])
        feedback_addressed = state.get("feedback_addressed", {})
        
        # Count addressed vs pending
        total_comments = len(pr_comments)
        addressed_count = sum(1 for addressed in feedback_addressed.values() if addressed)
        
        state["messages_window"].append({
            "role": "system",
            "content": "Feedback processing complete",
            "total_comments": total_comments,
            "addressed_count": addressed_count
        })
        
        feedback_message = f"""
💬 Feedback Processing Complete

**Thread ID**: {state['thread_id']}
**PR**: #{state.get('pr_number', 'TBD')}

**Feedback Summary**:
- Total Comments: {total_comments}
- Addressed: {addressed_count}
- Pending: {total_comments - addressed_count}

**Processing Results**:
- Design updated: {bool(state.get('finalized_design'))}
- Code changes: {len(state.get('implementation_code', {}))} files
- Responses prepared: {addressed_count}

**Next Steps**:
- Review proposed responses
- Approve changes
- Post responses to GitHub

Resume to post responses and continue workflow.
"""
        
        interrupt(feedback_message)
        
        return state