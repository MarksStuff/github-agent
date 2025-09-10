"""Main workflow graph definition."""

import logging
from typing import Literal

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import StateGraph, END
from langgraph.types import interrupt

from langgraph_workflow.state import (
    WorkflowState, 
    WorkflowPhase, 
    QualityState, 
    FeedbackGate,
    should_escalate
)
from langgraph_workflow.nodes import AgentNodes, GitNodes, ToolNodes, InterruptNodes

logger = logging.getLogger(__name__)

class WorkflowGraph:
    """LangGraph workflow implementation of the multi-agent system."""
    
    def __init__(self, repo_name: str, repo_path: str, checkpointer_path: str = "agent_state.db"):
        """Initialize the workflow graph.
        
        Args:
            repo_name: GitHub repository name (owner/repo)
            repo_path: Local path to repository
            checkpointer_path: SQLite database path for checkpoints
        """
        self.repo_name = repo_name
        self.repo_path = repo_path
        
        # Initialize node collections
        self.agent_nodes = AgentNodes(repo_name, repo_path)
        self.git_nodes = GitNodes(repo_name, repo_path)
        self.tool_nodes = ToolNodes(repo_path)
        
        # Initialize checkpointer
        self.checkpointer = SqliteSaver.from_conn_string(f"sqlite:///{checkpointer_path}")
        
        # Build the graph
        self.graph = self._build_graph()
        self.app = self.graph.compile(checkpointer=self.checkpointer)
        
        logger.info(f"Initialized workflow graph for {repo_name}")
    
    def _build_graph(self) -> StateGraph:
        """Build the complete workflow graph."""
        graph = StateGraph(WorkflowState)
        
        # Add all nodes
        self._add_analysis_nodes(graph)
        self._add_design_nodes(graph)
        self._add_implementation_nodes(graph)
        self._add_git_nodes(graph)
        self._add_tool_nodes(graph)
        self._add_interrupt_nodes(graph)
        
        # Set entry point
        graph.set_entry_point("initialize_git")
        
        # Add edges
        self._add_graph_edges(graph)
        
        return graph
    
    def _add_analysis_nodes(self, graph: StateGraph) -> None:
        """Add analysis phase nodes."""
        graph.add_node("analyze_codebase", self.agent_nodes.analyze_codebase)
        graph.add_node("analyze_feature", self.agent_nodes.analyze_feature)
        
    def _add_design_nodes(self, graph: StateGraph) -> None:
        """Add design phase nodes."""
        graph.add_node("consolidate_design", self.agent_nodes.consolidate_design)
        graph.add_node("incorporate_feedback", self.agent_nodes.incorporate_feedback)
        
    def _add_implementation_nodes(self, graph: StateGraph) -> None:
        """Add implementation phase nodes."""
        graph.add_node("create_skeleton", self.agent_nodes.create_skeleton)
        graph.add_node("create_tests", self.agent_nodes.create_tests)
        graph.add_node("implement_code", self.agent_nodes.implement_code)
        graph.add_node("fix_failures", self.agent_nodes.fix_failures)
        
    def _add_git_nodes(self, graph: StateGraph) -> None:
        """Add Git operation nodes."""
        graph.add_node("initialize_git", self.git_nodes.initialize_git)
        graph.add_node("commit_changes", self._wrap_commit_changes)
        graph.add_node("push_to_github", self.git_nodes.push_branch_and_pr)
        graph.add_node("fetch_feedback", self.git_nodes.fetch_pr_comments)
        
    def _add_tool_nodes(self, graph: StateGraph) -> None:
        """Add tool execution nodes."""
        graph.add_node("run_tests", self.tool_nodes.run_tests)
        graph.add_node("run_linter", self.tool_nodes.run_linter)
        graph.add_node("check_ci", self.tool_nodes.check_ci_status)
        
    def _add_interrupt_nodes(self, graph: StateGraph) -> None:
        """Add interrupt/pause nodes."""
        graph.add_node("await_feedback", InterruptNodes.wait_for_review)
        graph.add_node("quality_gate", InterruptNodes.quality_gate)
        graph.add_node("preview_changes", InterruptNodes.preview_changes)
        
    def _add_graph_edges(self, graph: StateGraph) -> None:
        """Add all edges and routing logic to the graph."""
        
        # Initial flow: Git setup -> Analysis
        graph.add_edge("initialize_git", "analyze_codebase")
        graph.add_edge("analyze_codebase", "analyze_feature")
        
        # Analysis -> Design
        graph.add_edge("analyze_feature", "consolidate_design")
        graph.add_edge("consolidate_design", "commit_changes")
        graph.add_edge("commit_changes", "push_to_github")
        graph.add_edge("push_to_github", "await_feedback")
        
        # Feedback loop
        graph.add_edge("await_feedback", "fetch_feedback")
        
        # Conditional: feedback exists -> incorporate, else -> implementation
        graph.add_conditional_edges(
            "fetch_feedback",
            self._route_after_feedback,
            {
                "incorporate_feedback": "incorporate_feedback",
                "implementation": "create_skeleton"
            }
        )
        
        # Feedback incorporation loop
        graph.add_edge("incorporate_feedback", "commit_changes")
        
        # Implementation flow
        graph.add_edge("create_skeleton", "create_tests")
        graph.add_edge("create_tests", "implement_code")
        graph.add_edge("implement_code", "run_tests")
        
        # Test result routing
        graph.add_conditional_edges(
            "run_tests",
            self._route_test_results,
            {
                "fix_failures": "fix_failures",
                "quality_gate": "quality_gate",
                "success": "run_linter"
            }
        )
        
        # Fix failures routing with retry limit
        graph.add_conditional_edges(
            "fix_failures",
            self._route_after_fixes,
            {
                "retry": "run_tests",
                "escalate": "quality_gate",
                "success": "run_linter"
            }
        )
        
        # Final steps
        graph.add_edge("run_linter", "commit_changes")
        graph.add_edge("quality_gate", "check_ci")
        graph.add_conditional_edges(
            "check_ci",
            self._route_final,
            {
                "complete": END,
                "await_more_feedback": "await_feedback"
            }
        )
    
    # Routing functions
    
    def _route_after_feedback(self, state: WorkflowState) -> Literal["incorporate_feedback", "implementation"]:
        """Route based on whether new feedback exists."""
        new_comments = state.get("pr_comments", [])
        
        # Check if there are unaddressed comments
        unaddressed = []
        for comment in new_comments:
            comment_id = str(comment.get("id", ""))
            if not state.get("feedback_addressed", {}).get(comment_id, False):
                unaddressed.append(comment)
        
        if unaddressed:
            logger.info(f"Found {len(unaddressed)} unaddressed comments, incorporating feedback")
            return "incorporate_feedback"
        else:
            logger.info("No new feedback, proceeding to implementation")
            # Update phase
            state["current_phase"] = WorkflowPhase.IMPLEMENTATION
            return "implementation"
    
    def _route_test_results(self, state: WorkflowState) -> Literal["fix_failures", "quality_gate", "success"]:
        """Route based on test results."""
        test_results = state.get("test_results", {})
        quality_state = state.get("quality_state", QualityState.DRAFT)
        
        if not test_results.get("passed", False):
            if state.get("retry_count", 0) >= 3:
                logger.info("Max retries reached, escalating to quality gate")
                return "quality_gate"
            else:
                logger.info("Tests failed, attempting fixes")
                return "fix_failures"
        else:
            logger.info("All tests passed, proceeding")
            return "success"
    
    def _route_after_fixes(self, state: WorkflowState) -> Literal["retry", "escalate", "success"]:
        """Route after attempting to fix failures."""
        retry_count = state.get("retry_count", 0)
        escalation_needed = state.get("escalation_needed", False)
        
        if retry_count >= 3 or escalation_needed:
            logger.info("Escalating due to retry limit or explicit escalation request")
            return "escalate"
        elif state.get("quality_state") == QualityState.OK:
            logger.info("Fixes successful")
            return "success"
        else:
            logger.info(f"Retrying fixes (attempt {retry_count + 1})")
            return "retry"
    
    def _route_final(self, state: WorkflowState) -> Literal["complete", "await_more_feedback"]:
        """Final routing decision."""
        ci_status = state.get("ci_status", {})
        
        # Check if CI is still running
        if ci_status.get("in_progress", False):
            logger.info("CI still in progress, waiting for feedback")
            return "await_more_feedback"
        
        # Check if all quality gates passed
        all_passed = (
            state.get("quality_state") == QualityState.OK and
            state.get("test_results", {}).get("passed", False) and
            ci_status.get("all_passed", False)
        )
        
        if all_passed:
            logger.info("All quality gates passed, workflow complete")
            state["current_phase"] = WorkflowPhase.IMPLEMENTATION  # Mark as completed
            return "complete"
        else:
            logger.info("Quality issues remain, awaiting more feedback")
            return "await_more_feedback"
    
    # Wrapper functions for additional logic
    
    async def _wrap_commit_changes(self, state: WorkflowState) -> dict:
        """Wrapper for commit changes with automatic messages."""
        phase = state.get("current_phase", "unknown")
        feature = state.get("feature_name", "feature")
        
        if hasattr(phase, 'value'):
            phase_name = phase.value
        else:
            phase_name = str(phase)
        
        message = f"{phase_name}: Progress on {feature}"
        
        return await self.git_nodes.commit_changes(state, message)
    
    # Public API
    
    async def run_workflow(self, thread_id: str, task_spec: str, feature_name: str, 
                          config: dict = None) -> dict:
        """Run the complete workflow.
        
        Args:
            thread_id: Unique identifier for this workflow run
            task_spec: Task specification/requirements
            feature_name: Name of the feature being implemented
            config: LangGraph configuration options
            
        Returns:
            Final workflow state and results
        """
        from langgraph_workflow.state import initialize_state
        
        # Initialize state
        initial_state = initialize_state(thread_id, self.repo_name, self.repo_path)
        initial_state.update({
            "task_spec": task_spec,
            "feature_name": feature_name,
            "current_phase": WorkflowPhase.ANALYSIS
        })
        
        # Default config
        if not config:
            config = {"thread_id": thread_id}
        
        try:
            # Stream the workflow execution
            final_state = None
            async for event in self.app.astream(initial_state, config=config):
                # Log progress
                if "messages_window" in event:
                    latest_message = event["messages_window"][-1] if event["messages_window"] else {}
                    logger.info(f"Workflow progress: {latest_message.get('content', 'Step completed')}")
                
                final_state = event
            
            return {
                "status": "completed",
                "final_state": final_state,
                "thread_id": thread_id
            }
            
        except Exception as e:
            logger.error(f"Workflow execution failed: {e}")
            return {
                "status": "failed",
                "error": str(e),
                "thread_id": thread_id
            }
    
    async def resume_workflow(self, thread_id: str, config: dict = None) -> dict:
        """Resume a paused workflow.
        
        Args:
            thread_id: Thread ID of the paused workflow
            config: LangGraph configuration options
            
        Returns:
            Resumed workflow results
        """
        if not config:
            config = {"thread_id": thread_id}
        
        try:
            # Resume from checkpoint
            final_state = None
            async for event in self.app.astream(None, config=config):
                # Log progress
                if "messages_window" in event:
                    latest_message = event["messages_window"][-1] if event["messages_window"] else {}
                    logger.info(f"Resumed workflow progress: {latest_message.get('content', 'Step completed')}")
                
                final_state = event
            
            return {
                "status": "resumed",
                "final_state": final_state,
                "thread_id": thread_id
            }
            
        except Exception as e:
            logger.error(f"Workflow resume failed: {e}")
            return {
                "status": "failed",
                "error": str(e),
                "thread_id": thread_id
            }
    
    def get_workflow_state(self, thread_id: str) -> dict | None:
        """Get current state of a workflow thread.
        
        Args:
            thread_id: Thread ID to query
            
        Returns:
            Current state or None if not found
        """
        try:
            config = {"thread_id": thread_id}
            state = self.app.get_state(config)
            return state.values if state else None
        except Exception as e:
            logger.error(f"Failed to get workflow state: {e}")
            return None
    
    def list_threads(self) -> list[dict]:
        """List all workflow threads and their states.
        
        Returns:
            List of thread information
        """
        try:
            # This would need to be implemented based on LangGraph's state storage
            # For now, return empty list
            return []
        except Exception as e:
            logger.error(f"Failed to list threads: {e}")
            return []