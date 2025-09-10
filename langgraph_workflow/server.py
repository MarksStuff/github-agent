"""LangGraph server for the multi-agent workflow."""

import asyncio
import json
import logging
import os
import signal
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import uvicorn
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

# Add parent directory for imports
sys.path.append(str(Path(__file__).parent.parent))

from langgraph_workflow.graph import WorkflowGraph
from langgraph_workflow.routing.model_router import ModelRouter

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Pydantic models for API
class WorkflowRequest(BaseModel):
    task_spec: str
    feature_name: str
    thread_id: Optional[str] = None
    prd_source: Optional[str] = None

class ResumeRequest(BaseModel):
    thread_id: str

class ThreadStatusResponse(BaseModel):
    thread_id: str
    status: str
    current_phase: str
    created_at: str
    last_updated: str
    paused_for_review: bool

class WorkflowResponse(BaseModel):
    status: str
    thread_id: str
    message: str
    details: Optional[dict] = None

# Global workflow instance
workflow_graph: Optional[WorkflowGraph] = None
model_router: Optional[ModelRouter] = None

def create_app() -> FastAPI:
    """Create FastAPI application."""
    app = FastAPI(
        title="LangGraph Multi-Agent Workflow",
        description="Stateful multi-agent software development workflow",
        version="0.1.0"
    )
    
    @app.on_event("startup")
    async def startup_event():
        """Initialize workflow components on startup."""
        global workflow_graph, model_router
        
        # Load configuration
        repo_name = os.getenv("REPO_NAME", "github-agent/github-agent")
        repo_path = os.getenv("REPO_PATH", "/Users/mstriebeck/Code/github-agent")
        checkpointer_path = os.getenv("LANGGRAPH_DB_PATH", ".langgraph_checkpoints/agent_state.db")
        
        # Ensure checkpoint directory exists
        checkpoint_dir = Path(checkpointer_path).parent
        checkpoint_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize components
        try:
            workflow_graph = WorkflowGraph(repo_name, repo_path, checkpointer_path)
            model_router = ModelRouter()
            
            # Test model connections
            model_test_results = await model_router.test_connections()
            logger.info(f"Model connections: {model_test_results}")
            
            logger.info(f"LangGraph workflow server initialized for {repo_name}")
            
        except Exception as e:
            logger.error(f"Failed to initialize workflow components: {e}")
            raise e
    
    @app.get("/")
    async def root():
        """Root endpoint with server information."""
        return {
            "service": "LangGraph Multi-Agent Workflow",
            "version": "0.1.0",
            "status": "running",
            "endpoints": {
                "start_workflow": "/workflow/start",
                "resume_workflow": "/workflow/resume",
                "get_status": "/workflow/status/{thread_id}",
                "list_threads": "/workflow/threads",
                "health": "/health",
                "models": "/models/status"
            }
        }
    
    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        health_status = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "components": {
                "workflow_graph": workflow_graph is not None,
                "model_router": model_router is not None
            }
        }
        
        if model_router:
            model_stats = model_router.get_model_stats()
            health_status["models"] = model_stats
        
        return health_status
    
    @app.get("/models/status")
    async def model_status():
        """Get model connection status."""
        if not model_router:
            raise HTTPException(status_code=503, detail="Model router not initialized")
        
        test_results = await model_router.test_connections()
        model_stats = model_router.get_model_stats()
        
        return {
            "model_stats": model_stats,
            "connection_tests": test_results,
            "timestamp": datetime.now().isoformat()
        }
    
    @app.post("/workflow/start", response_model=WorkflowResponse)
    async def start_workflow(request: WorkflowRequest, background_tasks: BackgroundTasks):
        """Start a new workflow."""
        if not workflow_graph:
            raise HTTPException(status_code=503, detail="Workflow graph not initialized")
        
        # Generate thread ID if not provided
        thread_id = request.thread_id or f"workflow-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        
        logger.info(f"Starting workflow {thread_id} for feature: {request.feature_name}")
        
        try:
            # Start workflow in background
            background_tasks.add_task(
                _run_workflow_background,
                thread_id,
                request.task_spec,
                request.feature_name
            )
            
            return WorkflowResponse(
                status="started",
                thread_id=thread_id,
                message=f"Workflow started for feature: {request.feature_name}",
                details={
                    "feature_name": request.feature_name,
                    "task_spec_length": len(request.task_spec)
                }
            )
            
        except Exception as e:
            logger.error(f"Failed to start workflow: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/workflow/resume", response_model=WorkflowResponse)
    async def resume_workflow(request: ResumeRequest, background_tasks: BackgroundTasks):
        """Resume a paused workflow."""
        if not workflow_graph:
            raise HTTPException(status_code=503, detail="Workflow graph not initialized")
        
        logger.info(f"Resuming workflow {request.thread_id}")
        
        try:
            # Resume workflow in background
            background_tasks.add_task(
                _resume_workflow_background,
                request.thread_id
            )
            
            return WorkflowResponse(
                status="resumed",
                thread_id=request.thread_id,
                message=f"Workflow {request.thread_id} resumed"
            )
            
        except Exception as e:
            logger.error(f"Failed to resume workflow: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/workflow/status/{thread_id}")
    async def get_workflow_status(thread_id: str):
        """Get current status of a workflow thread."""
        if not workflow_graph:
            raise HTTPException(status_code=503, detail="Workflow graph not initialized")
        
        try:
            state = workflow_graph.get_workflow_state(thread_id)
            
            if not state:
                raise HTTPException(status_code=404, detail="Thread not found")
            
            # Extract key information from state
            current_phase = state.get("current_phase", "unknown")
            if hasattr(current_phase, 'value'):
                current_phase = current_phase.value
            
            return {
                "thread_id": thread_id,
                "status": "active",
                "current_phase": current_phase,
                "feature_name": state.get("feature_name", "Unknown"),
                "pr_number": state.get("pr_number"),
                "quality_state": state.get("quality_state", {}).get("value") if hasattr(state.get("quality_state", {}), "value") else str(state.get("quality_state", "unknown")),
                "retry_count": state.get("retry_count", 0),
                "paused_for_review": state.get("paused_for_review", False),
                "last_message": state.get("messages_window", [])[-1] if state.get("messages_window") else None,
                "artifacts_count": len(state.get("artifacts_index", {})),
                "test_status": "passed" if state.get("test_results", {}).get("passed") else "failed" if state.get("test_results") else "pending"
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to get workflow status: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/workflow/threads")
    async def list_workflow_threads():
        """List all workflow threads."""
        if not workflow_graph:
            raise HTTPException(status_code=503, detail="Workflow graph not initialized")
        
        try:
            threads = workflow_graph.list_threads()
            return {
                "threads": threads,
                "count": len(threads),
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to list threads: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/workflow/stream/{thread_id}")
    async def stream_workflow_updates(thread_id: str):
        """Stream real-time updates for a workflow thread."""
        if not workflow_graph:
            raise HTTPException(status_code=503, detail="Workflow graph not initialized")
        
        async def event_generator():
            # This would need to be implemented based on LangGraph's streaming capabilities
            # For now, return initial status
            try:
                state = workflow_graph.get_workflow_state(thread_id)
                if state:
                    yield f"data: {json.dumps(state)}\n\n"
                else:
                    yield f"data: {json.dumps({'error': 'Thread not found'})}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
        
        return StreamingResponse(
            event_generator(),
            media_type="text/plain",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
        )
    
    return app

# Background task functions

async def _run_workflow_background(thread_id: str, task_spec: str, feature_name: str):
    """Run workflow in background task."""
    try:
        logger.info(f"Background workflow starting: {thread_id}")
        result = await workflow_graph.run_workflow(thread_id, task_spec, feature_name)
        logger.info(f"Background workflow completed: {thread_id} - {result['status']}")
    except Exception as e:
        logger.error(f"Background workflow failed: {thread_id} - {e}")

async def _resume_workflow_background(thread_id: str):
    """Resume workflow in background task."""
    try:
        logger.info(f"Background workflow resuming: {thread_id}")
        result = await workflow_graph.resume_workflow(thread_id)
        logger.info(f"Background workflow resume completed: {thread_id} - {result['status']}")
    except Exception as e:
        logger.error(f"Background workflow resume failed: {thread_id} - {e}")

# Server configuration and startup

def load_config() -> dict:
    """Load configuration from environment variables."""
    config = {
        "host": os.getenv("LANGGRAPH_SERVER_HOST", "127.0.0.1"),
        "port": int(os.getenv("LANGGRAPH_SERVER_PORT", "8123")),
        "workers": int(os.getenv("LANGGRAPH_SERVER_WORKERS", "1")),
        "log_level": os.getenv("LANGGRAPH_LOG_LEVEL", "info"),
        "reload": os.getenv("LANGGRAPH_RELOAD", "false").lower() == "true"
    }
    return config

def setup_signal_handlers():
    """Set up signal handlers for graceful shutdown."""
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

def main():
    """Main entry point for the server."""
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('langgraph_workflow.log')
        ]
    )
    
    # Load configuration
    config = load_config()
    
    # Set up signal handlers
    setup_signal_handlers()
    
    # Create and run the app
    app = create_app()
    
    logger.info("Starting LangGraph Multi-Agent Workflow Server")
    logger.info(f"Configuration: {config}")
    
    # Check required environment variables
    required_vars = ["ANTHROPIC_API_KEY", "GITHUB_TOKEN"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        logger.warning(f"Missing environment variables: {missing_vars}")
        logger.warning("Some functionality may be limited")
    
    try:
        uvicorn.run(
            app,
            host=config["host"],
            port=config["port"],
            log_level=config["log_level"],
            reload=config["reload"]
        )
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server failed to start: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()