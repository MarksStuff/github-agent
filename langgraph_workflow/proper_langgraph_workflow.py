"""Proper LangGraph Workflow Implementation.

This demonstrates how to use LangGraph's built-in capabilities instead of
manual state management and file-based tracking.
"""

import logging
from typing import Any, Literal

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import StateGraph

from .enums import WorkflowStep
from .workflow_state import WorkflowState

logger = logging.getLogger(__name__)


class ProperLangGraphWorkflow:
    """LangGraph workflow using native capabilities instead of manual workarounds."""

    def __init__(
        self,
        repo_path: str,
        agents: dict[str, Any],
        codebase_analyzer: Any,
        thread_id: str | None = None,
        checkpoint_path: str = "proper_workflow.db",
    ):
        self.repo_path = repo_path
        self.agents = agents
        self.codebase_analyzer = codebase_analyzer
        self.thread_id = thread_id or "proper-workflow"

        # Create SQLite checkpointer for state persistence
        import sqlite3
        conn = sqlite3.connect(checkpoint_path)
        self.checkpointer = SqliteSaver(conn)

        # Build the graph with proper LangGraph patterns
        self.app = self._build_proper_graph()

    def _build_proper_graph(self) -> Any:
        """Build workflow graph using LangGraph's native capabilities."""

        workflow = StateGraph(WorkflowState)

        # Add all nodes
        workflow.add_node("extract_feature", self._extract_feature)
        workflow.add_node("extract_code_context", self._extract_code_context)
        workflow.add_node("parallel_design_exploration", self._parallel_design_exploration)
        workflow.add_node("design_synthesis", self._design_synthesis)
        workflow.add_node("create_design_document", self._create_design_document)

        # Set entry point
        workflow.set_entry_point("extract_feature")

        # Use LangGraph's conditional edges for smart execution
        workflow.add_conditional_edges(
            "extract_feature",
            self._should_extract_code_context,
            {
                "extract": "extract_code_context",
                "skip": "parallel_design_exploration"
            }
        )

        workflow.add_conditional_edges(
            "extract_code_context",
            self._should_run_design_exploration,
            {
                "run": "parallel_design_exploration",
                "skip": "design_synthesis"
            }
        )

        workflow.add_conditional_edges(
            "parallel_design_exploration",
            self._should_run_synthesis,
            {
                "synthesis": "design_synthesis",
                "retry": "parallel_design_exploration"
            }
        )

        workflow.add_conditional_edges(
            "design_synthesis",
            self._should_create_design_doc,
            {
                "create": "create_design_document",
                "end": "__end__"
            }
        )

        workflow.add_edge("create_design_document", "__end__")

        # Compile with checkpointer - LangGraph handles persistence automatically!
        return workflow.compile(checkpointer=self.checkpointer)

    # ========== CONDITIONAL FUNCTIONS ==========
    # These replace our manual "step completion" checking

    def _should_extract_code_context(self, state: dict) -> Literal["extract", "skip"]:
        """Check if code context extraction is needed."""
        code_context = state.get("code_context_document")
        if code_context and len(code_context) >= 2000:
            logger.info("✅ Code context already exists and is valid")
            return "skip"
        return "extract"

    def _should_run_design_exploration(self, state: dict) -> Literal["run", "skip"]:
        """Check if design exploration is needed."""
        agent_analyses = state.get("agent_analyses", {})
        if len(agent_analyses) >= 4:
            logger.info("✅ All 4 agent analyses already completed")
            return "skip"
        return "run"

    def _should_run_synthesis(self, state: dict) -> Literal["synthesis", "retry"]:
        """Check if synthesis can proceed."""
        agent_analyses = state.get("agent_analyses", {})
        if len(agent_analyses) >= 4:
            return "synthesis"
        else:
            logger.warning(f"Only {len(agent_analyses)} agent analyses available, retrying...")
            return "retry"

    def _should_create_design_doc(self, state: dict) -> Literal["create", "end"]:
        """Check if design document creation is needed."""
        if state.get("synthesis_document"):
            return "create"
        return "end"

    # ========== NODE IMPLEMENTATIONS ==========

    async def _extract_feature(self, state: dict) -> dict:
        """Extract feature from description (no-op if already present)."""
        if not state.get("feature_description"):
            logger.error("No feature description provided")
            raise ValueError("Feature description is required")

        logger.info(f"📝 Feature: {state['feature_description']}")
        return state

    async def _extract_code_context(self, state: dict) -> dict:
        """Extract code context using existing implementation."""
        from .nodes.extract_code_context import extract_code_context_handler

        logger.info("🔍 Extracting code context...")
        return await extract_code_context_handler(state)

    async def _parallel_design_exploration(self, state: dict) -> dict:
        """Run parallel design exploration using existing implementation."""
        from .nodes.parallel_design_exploration import parallel_design_exploration_handler

        logger.info("🎨 Running parallel design exploration...")
        return await parallel_design_exploration_handler(state)

    async def _design_synthesis(self, state: dict) -> dict:
        """Run design synthesis using existing implementation."""
        from .nodes.design_synthesis import design_synthesis_handler

        logger.info("🔀 Running design synthesis...")
        return await design_synthesis_handler(state)

    async def _create_design_document(self, state: dict) -> dict:
        """Create design document using existing implementation."""
        from .nodes.create_design_document import create_design_document_handler

        logger.info("📋 Creating design document...")
        return await create_design_document_handler(state)

    # ========== PUBLIC API ==========

    async def run_full_workflow(self, initial_state: dict) -> dict:
        """Run the complete workflow using LangGraph's native execution."""
        config = {"configurable": {"thread_id": self.thread_id}}

        logger.info(f"🚀 Starting workflow for thread: {self.thread_id}")

        # LangGraph automatically handles:
        # - Checkpointing after each step
        # - Resumption from last checkpoint
        # - Conditional execution based on state
        # - Error recovery
        result = await self.app.ainvoke(initial_state, config)

        logger.info("✅ Workflow completed successfully")
        return result

    async def resume_workflow(self) -> dict:
        """Resume workflow from last checkpoint - LangGraph handles this automatically!"""
        config = {"configurable": {"thread_id": self.thread_id}}

        logger.info(f"🔄 Resuming workflow for thread: {self.thread_id}")

        # Magic: Pass None as input to resume from checkpoint
        result = await self.app.ainvoke(None, config)

        logger.info("✅ Workflow resumed and completed")
        return result

    async def run_until_step(self, initial_state: dict, target_step: str) -> dict:
        """Run until a specific step using LangGraph's built-in interruption."""
        config = {
            "configurable": {
                "thread_id": self.thread_id
            }
        }

        # LangGraph way: Use interrupt_before to stop at target step
        interrupt_before = [target_step] if target_step != "__end__" else []

        logger.info(f"🎯 Running until step: {target_step}")

        # This will stop BEFORE the target step, leaving it ready to execute
        async for chunk in self.app.astream(initial_state, config, interrupt_before=interrupt_before):
            logger.info(f"📍 Completed step: {list(chunk.keys())[0]}")

        # Get final state
        final_state = self.app.get_state(config)

        logger.info(f"⏸️  Workflow paused before: {target_step}")
        return dict(final_state.values)

    def get_workflow_history(self) -> list:
        """Get complete execution history using LangGraph's time travel."""
        config = {"configurable": {"thread_id": self.thread_id}}

        # LangGraph provides complete history automatically
        history = []
        for state in self.app.get_state_history(config):
            history.append({
                "step": state.next,
                "values": dict(state.values),
                "metadata": state.metadata
            })

        return history

    def get_current_state(self) -> dict:
        """Get current workflow state."""
        config = {"configurable": {"thread_id": self.thread_id}}
        current = self.app.get_state(config)
        return dict(current.values) if current else {}