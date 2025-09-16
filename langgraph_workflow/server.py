#!/usr/bin/env python
"""LangGraph Studio server for the multi-agent workflow.

This module provides a LangGraph Studio-compatible server that exposes
the multi-agent workflow with a web UI for monitoring and interaction.
"""

import logging
import os
from uuid import uuid4

from dotenv import load_dotenv
from langgraph.checkpoint.sqlite import SqliteSaver

from langgraph_workflow import (
    EnhancedMultiAgentWorkflow,
    FeedbackGateStatus,
    ModelRouter,
    QualityLevel,
    WorkflowPhase,
    WorkflowState,
)
from langgraph_workflow.config import get_checkpoint_path
from langgraph_workflow.tests.mocks import create_mock_dependencies

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def create_workflow_graph(
    repo_path: str | None = None,
    thread_id: str | None = None,
    checkpoint_path: str | None = None,
):
    """Create a workflow graph for LangGraph Studio.

    Args:
        repo_path: Repository path (uses current directory if None)
        thread_id: Thread ID for persistence
        checkpoint_path: SQLite checkpoint database path

    Returns:
        Compiled LangGraph application
    """
    # Use current directory if no repo path specified
    if repo_path is None:
        repo_path = os.getcwd()

    # Generate thread ID if not provided
    if thread_id is None:
        thread_id = f"studio-{uuid4().hex[:8]}"

    logger.info(f"Creating workflow for repo: {repo_path}, thread: {thread_id}")

    # Use config-based checkpoint path if not specified
    if checkpoint_path is None:
        checkpoint_path = get_checkpoint_path("studio_state")

    # Use mock dependencies for development (production mode disabled until dependencies are implemented)
    mock_deps = create_mock_dependencies(thread_id)
    workflow = EnhancedMultiAgentWorkflow(
        repo_path=repo_path,
        thread_id=thread_id,
        agents=mock_deps["agents"],
        codebase_analyzer=mock_deps["codebase_analyzer"],
        checkpoint_path=checkpoint_path,
    )

    return workflow.app


def create_initial_state(feature_description: str, repo_path: str) -> WorkflowState:
    """Create the initial workflow state.

    Args:
        feature_description: Description of the feature to implement
        repo_path: Path to the repository

    Returns:
        Initial workflow state
    """
    thread_id = f"studio-{uuid4().hex[:8]}"

    return WorkflowState(
        thread_id=thread_id,
        feature_description=feature_description,
        raw_feature_input=None,
        extracted_feature=None,
        current_phase=WorkflowPhase.PHASE_0_CODE_CONTEXT,
        messages_window=[],
        summary_log="",
        artifacts_index={},
        code_context_document=None,
        design_constraints_document=None,
        design_document=None,
        arbitration_log=[],
        repo_path=repo_path,
        git_branch="main",
        last_commit_sha=None,
        pr_number=None,
        agent_analyses={},
        synthesis_document=None,
        conflicts=[],
        skeleton_code=None,
        test_code=None,
        implementation_code=None,
        patch_queue=[],
        test_report={},
        ci_status={},
        lint_status={},
        quality=QualityLevel.DRAFT,
        feedback_gate=FeedbackGateStatus.OPEN,
        model_router=ModelRouter.OLLAMA,
        escalation_count=0,
    )


# Create the default graph for LangGraph Studio
# This will be imported by the studio when running
graph = create_workflow_graph()


# Optional: Create a FastAPI app for more control
def create_api_app():
    """Create a FastAPI application with workflow endpoints.

    This provides additional REST API endpoints for workflow control
    beyond what LangGraph Studio provides by default.
    """
    from fastapi import FastAPI, HTTPException
    from pydantic import BaseModel

    app = FastAPI(
        title="Multi-Agent Workflow API",
        description="API for the LangGraph multi-agent development workflow",
        version="1.0.0",
    )

    class WorkflowRequest(BaseModel):
        """Request model for starting a workflow."""

        feature_description: str
        repo_path: str | None = None
        thread_id: str | None = None

    class StepRequest(BaseModel):
        """Request model for executing a single step."""

        step_name: str
        thread_id: str
        repo_path: str | None = None

    @app.get("/")
    async def root():
        """Root endpoint with API information."""
        return {
            "name": "Multi-Agent Workflow API",
            "version": "1.0.0",
            "endpoints": {
                "/workflows": "Start a new workflow",
                "/workflows/{thread_id}": "Get workflow status",
                "/workflows/{thread_id}/step": "Execute a single step",
                "/steps": "List available workflow steps",
            },
        }

    @app.post("/workflows")
    async def start_workflow(request: WorkflowRequest):
        """Start a new workflow."""
        repo_path = request.repo_path or os.getcwd()
        thread_id = request.thread_id or f"api-{uuid4().hex[:8]}"

        try:
            # Create workflow with mock dependencies (production mode disabled until dependencies are implemented)
            mock_deps = create_mock_dependencies(thread_id)
            EnhancedMultiAgentWorkflow(
                repo_path=repo_path,
                thread_id=thread_id,
                agents=mock_deps["agents"],
                codebase_analyzer=mock_deps["codebase_analyzer"],
                checkpoint_path=get_checkpoint_path("api_state"),
            )

            # Note: In production, this would be queued or run in background

            return {
                "thread_id": thread_id,
                "status": "started",
                "feature": request.feature_description,
                "repo_path": repo_path,
            }

        except Exception as e:
            logger.error(f"Failed to start workflow: {e}")
            raise HTTPException(status_code=500, detail=str(e)) from e

    @app.get("/workflows/{thread_id}")
    async def get_workflow_status(thread_id: str):
        """Get the status of a workflow."""
        try:
            # Load checkpoint to get current state
            with SqliteSaver.from_conn_string(
                get_checkpoint_path("api_state")
            ) as checkpointer:
                from langchain_core.runnables import RunnableConfig

                config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
                checkpoint = checkpointer.get(config)

                if not checkpoint:
                    raise HTTPException(status_code=404, detail="Workflow not found")

                state = checkpoint.get("channel_values", {})

            return {
                "thread_id": thread_id,
                "current_phase": state.get("current_phase", "unknown"),
                "quality": state.get("quality", "unknown"),
                "pr_number": state.get("pr_number"),
                "artifacts": list(state.get("artifacts_index", {}).keys()),
                "conflicts": len(state.get("conflicts", [])),
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to get workflow status: {e}")
            raise HTTPException(status_code=500, detail=str(e)) from e

    @app.get("/steps")
    async def list_steps():
        """List all available workflow steps."""
        steps = [
            "extract_code_context",
            "parallel_design_exploration",
            "architect_synthesis",
            "code_investigation",
            "human_review",
            "create_design_document",
            "iterate_design_document",
            "finalize_design_document",
            "create_skeleton",
            "parallel_development",
            "reconciliation",
            "component_tests",
            "integration_tests",
            "refinement",
        ]

        return {
            "steps": steps,
            "total": len(steps),
        }

    @app.post("/workflows/{thread_id}/step")
    async def execute_step(thread_id: str, request: StepRequest):
        """Execute a single workflow step."""
        repo_path = request.repo_path or os.getcwd()

        try:
            # Load workflow with mock dependencies (production mode disabled until dependencies are implemented)
            mock_deps = create_mock_dependencies(thread_id)
            workflow = EnhancedMultiAgentWorkflow(
                repo_path=repo_path,
                thread_id=thread_id,
                agents=mock_deps["agents"],
                codebase_analyzer=mock_deps["codebase_analyzer"],
                checkpoint_path=get_checkpoint_path("api_state"),
            )

            # Get the step method
            step_method = getattr(workflow, request.step_name, None)
            if not step_method:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unknown step: {request.step_name}",
                )

            # Load current state from checkpoint
            with SqliteSaver.from_conn_string(
                get_checkpoint_path("api_state")
            ) as checkpointer:
                from langchain_core.runnables import RunnableConfig

                config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
                checkpoint = checkpointer.get(config)

                if not checkpoint:
                    raise HTTPException(status_code=404, detail="Workflow not found")

                current_state = checkpoint.get("channel_values", {})

            # Execute the step
            updated_state = await step_method(current_state)

            return {
                "thread_id": thread_id,
                "step": request.step_name,
                "status": "completed",
                "new_phase": updated_state.get("current_phase"),
                "artifacts_created": list(
                    updated_state.get("artifacts_index", {}).keys()
                ),
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to execute step: {e}")
            raise HTTPException(status_code=500, detail=str(e)) from e

    return app


# Create FastAPI app if running as API server
if __name__ == "__main__":
    import uvicorn

    # Check if we're running as API server or LangGraph Studio
    if os.getenv("LANGGRAPH_STUDIO_MODE"):
        # LangGraph Studio mode - just export the graph
        logger.info("Running in LangGraph Studio mode")
    else:
        # API server mode - run FastAPI
        logger.info("Starting FastAPI server...")
        api_app = create_api_app()
        uvicorn.run(
            api_app,
            host="0.0.0.0",
            port=8000,
            log_level="info",
        )
