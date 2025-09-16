#!/usr/bin/env python
"""Modern CLI for the Enhanced LangGraph Multi-Agent Workflow.

This CLI provides clean interface for:
- Stop at certain step
- Resume from previous process
- Rollback to previous step

Using LangGraph's built-in checkpointing and state management.
"""

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Any

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langchain_ollama import ChatOllama

from .config import get_ollama_base_url, get_ollama_model
from .enhanced_workflow import create_enhanced_workflow
from .enums import WorkflowStep
from .tests.mocks import create_mock_dependencies

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def extract_feature_from_prd(prd_content: str, feature_name: str) -> str | None:
    """Extract a specific feature from a PRD document using LLM.

    Args:
        prd_content: Full PRD content
        feature_name: Name/title of the feature to extract

    Returns:
        Feature description or None if not found
    """
    # Create prompt for feature extraction
    extraction_prompt = f"""You are a technical document analyzer. Extract the specific feature information from this PRD document.

PRD Content:
{prd_content}

Feature to Extract: "{feature_name}"

Instructions:
1. Find the section or sections that describe the "{feature_name}" feature
2. Extract the complete description including requirements, acceptance criteria, and technical details
3. If the feature is not found, return exactly "FEATURE_NOT_FOUND"
4. Return only the relevant feature content, not the entire document

Feature Extract:"""

    extracted_content = None

    # Try Ollama first if available
    try:
        # Use configuration for Ollama setup
        ollama_base_url = get_ollama_base_url()
        ollama_model = os.getenv("OLLAMA_MODEL", get_ollama_model("default"))

        logger.info("🔍 Attempting feature extraction with Ollama")
        ollama_client = ChatOllama(
            base_url=ollama_base_url,
            model=ollama_model,
        )

        response = await ollama_client.ainvoke(
            [HumanMessage(content=extraction_prompt)]
        )

        extracted_content = response.content.strip()
        logger.info("✅ Successfully extracted feature using Ollama")

    except Exception as e:
        logger.warning(f"⚠️  Ollama extraction failed: {e}")

    # Check if extraction was successful
    if extracted_content and extracted_content != "FEATURE_NOT_FOUND":
        return extracted_content

    logger.error(f"❌ Failed to extract feature '{feature_name}' from PRD")
    return None


class WorkflowCLI:
    """Enhanced workflow CLI with checkpointing support."""

    def __init__(self, repo_path: str, thread_id: str = "workflow-session"):
        """Initialize the workflow CLI.

        Args:
            repo_path: Path to the repository
            thread_id: Unique session identifier for checkpointing
        """
        self.repo_path = Path(repo_path).resolve()
        self.thread_id = thread_id
        self.workflow = None

    def _create_workflow(self, checkpoint_path: str | None = None) -> Any:
        """Create workflow instance with checkpointing."""
        # Use mock dependencies for now (production mode disabled per server.py pattern)
        mock_deps = create_mock_dependencies(self.thread_id)

        checkpoint_path = checkpoint_path or f"workflow-{self.thread_id}.db"

        return create_enhanced_workflow(
            repo_path=str(self.repo_path),
            agents=mock_deps["agents"],
            codebase_analyzer=mock_deps["codebase_analyzer"],
            thread_id=self.thread_id,
            checkpoint_path=checkpoint_path,
        )

    async def start_workflow(
        self,
        feature_file_content: str,
        stop_at: str | None = None,
        feature_name: str | None = None,
        pr_number: int | None = None,
    ) -> dict:
        """Start a new workflow execution.

        Args:
            feature_file_content: Content from the feature file
            stop_at: Workflow step to stop at (optional)
            feature_name: Specific feature name to extract from file (optional)
            pr_number: PR number for GitHub integration (optional)

        Returns:
            Final workflow state
        """
        logger.info(f"🚀 Starting new workflow session: {self.thread_id}")
        logger.info(f"📁 Repository: {self.repo_path}")

        # Handle feature extraction if needed
        if feature_name:
            logger.info(f"🔍 Extracting feature '{feature_name}' from file")
            final_feature_description = await extract_feature_from_prd(
                feature_file_content, feature_name
            )
            if not final_feature_description:
                logger.error(f"❌ Failed to extract feature '{feature_name}'")
                raise ValueError(
                    f"Could not extract feature '{feature_name}' from file"
                )
            logger.info("✅ Feature extracted successfully")
        else:
            logger.info("📋 Using entire file content as feature description")
            final_feature_description = feature_file_content

        logger.info(f"🎯 Feature: {final_feature_description[:100]}...")

        if stop_at:
            logger.info(f"⏹️  Will stop at step: {stop_at}")

        self.workflow = self._create_workflow()

        # Create config for this session
        config: RunnableConfig = {"configurable": {"thread_id": self.thread_id}}

        if stop_at:
            # Use LangGraph's interrupt functionality to stop at specific step
            config["configurable"]["interrupt_before"] = [stop_at]

        # Run workflow until interruption or completion
        try:
            final_state = await self.workflow.run_workflow(
                feature_description=final_feature_description,
                pr_number=pr_number,
                raw_feature_input=feature_file_content,
            )

            if stop_at and final_state.get("current_phase"):
                logger.info(f"⏸️  Workflow paused at step: {stop_at}")
                logger.info("💾 State saved to checkpoint - use 'resume' to continue")
            else:
                logger.info("✅ Workflow completed successfully")

            return final_state

        except Exception as e:
            logger.error(f"❌ Workflow execution failed: {e}")
            raise

    async def resume_workflow(self, stop_at: str | None = None) -> dict:
        """Resume workflow from last checkpoint.

        Args:
            stop_at: New step to stop at (optional)

        Returns:
            Final workflow state
        """
        logger.info(f"▶️  Resuming workflow session: {self.thread_id}")

        if stop_at:
            logger.info(f"⏹️  Will stop at step: {stop_at}")

        self.workflow = self._create_workflow()

        # Create config for resumption
        config: RunnableConfig = {"configurable": {"thread_id": self.thread_id}}

        if stop_at:
            config["configurable"]["interrupt_before"] = [stop_at]

        try:
            # LangGraph automatically resumes from last checkpoint
            final_state = await self.workflow.app.ainvoke({}, config=config)

            if stop_at:
                logger.info(f"⏸️  Workflow paused at step: {stop_at}")
            else:
                logger.info("✅ Workflow resumed and completed successfully")

            return final_state

        except Exception as e:
            logger.error(f"❌ Workflow resumption failed: {e}")
            raise

    async def rollback_to_step(self, target_step: str) -> dict:
        """Rollback workflow to a previous step.

        Args:
            target_step: Step to rollback to

        Returns:
            State at the target step
        """
        logger.info(f"⏪ Rolling back workflow to step: {target_step}")

        self.workflow = self._create_workflow()

        # Get checkpoint history
        config: RunnableConfig = {"configurable": {"thread_id": self.thread_id}}

        try:
            # Get all checkpoints for this thread
            checkpoints = []
            async for checkpoint in self.workflow.checkpointer.alist(config):
                checkpoints.append(checkpoint)

            if not checkpoints:
                raise ValueError("No checkpoints found for this session")

            # Find checkpoint at or before target step
            target_checkpoint = None
            for checkpoint in reversed(checkpoints):  # Start from oldest
                state = checkpoint.state
                current_step = state.get("current_phase")
                if current_step == target_step:
                    target_checkpoint = checkpoint
                    break

            if not target_checkpoint:
                available_steps = [cp.state.get("current_phase") for cp in checkpoints]
                raise ValueError(
                    f"No checkpoint found for step '{target_step}'. "
                    f"Available steps: {available_steps}"
                )

            # Restore to target checkpoint
            logger.info(f"📍 Found checkpoint at step: {target_step}")
            logger.info("🔄 Restoring workflow state...")

            # Return the state at the target step
            return target_checkpoint.state

        except Exception as e:
            logger.error(f"❌ Rollback failed: {e}")
            raise

    async def list_checkpoints(self) -> list[dict]:
        """List all available checkpoints for this session.

        Returns:
            List of checkpoint information
        """
        logger.info(f"📋 Listing checkpoints for session: {self.thread_id}")

        self.workflow = self._create_workflow()

        config: RunnableConfig = {"configurable": {"thread_id": self.thread_id}}

        checkpoints = []
        async for checkpoint in self.workflow.checkpointer.alist(config):
            state = checkpoint.state
            checkpoints.append(
                {
                    "checkpoint_id": checkpoint.id,
                    "step": state.get("current_phase"),
                    "timestamp": checkpoint.timestamp,
                    "feature": state.get("feature_description", "Unknown"),
                }
            )

        if checkpoints:
            logger.info(f"📊 Found {len(checkpoints)} checkpoints:")
            for i, cp in enumerate(checkpoints, 1):
                logger.info(f"  {i}. Step: {cp['step']} | Time: {cp['timestamp']}")
        else:
            logger.info("📭 No checkpoints found for this session")

        return checkpoints

    def list_available_steps(self) -> list[str]:
        """List all available workflow steps.

        Returns:
            List of step names
        """
        return [step.value for step in WorkflowStep]


async def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Enhanced LangGraph Multi-Agent Workflow CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start new workflow with entire file content
  python -m langgraph_workflow.cli start --feature-file feature.md --stop-at parallel_design_exploration

  # Start workflow extracting specific feature from PRD
  python -m langgraph_workflow.cli start --feature-file prd.md --feature-name "User Authentication" --stop-at parallel_development

  # Resume workflow and stop at development
  python -m langgraph_workflow.cli resume --session my-session --stop-at parallel_development

  # Rollback to previous step
  python -m langgraph_workflow.cli rollback --session my-session --to extract_code_context

  # List checkpoints
  python -m langgraph_workflow.cli list --session my-session
        """,
    )

    # Global options
    parser.add_argument(
        "--repo-path",
        default=".",
        help="Path to the repository (default: current directory)",
    )
    parser.add_argument(
        "--session",
        default="default",
        help="Session ID for checkpointing (default: 'default')",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    # Subcommands
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Start command
    start_parser = subparsers.add_parser("start", help="Start a new workflow")
    start_parser.add_argument(
        "--feature-file",
        required=True,
        help="Path to feature file (required)",
    )
    start_parser.add_argument(
        "--feature-name",
        help="Name of specific feature within file (optional - if not provided, uses entire file)",
    )
    start_parser.add_argument(
        "--stop-at",
        choices=[step.value for step in WorkflowStep],
        help="Stop execution at this step",
    )
    start_parser.add_argument(
        "--pr-number",
        type=int,
        help="PR number for GitHub integration",
    )

    # Resume command
    resume_parser = subparsers.add_parser(
        "resume", help="Resume workflow from checkpoint"
    )
    resume_parser.add_argument(
        "--stop-at",
        choices=[step.value for step in WorkflowStep],
        help="Stop execution at this step",
    )

    # Rollback command
    rollback_parser = subparsers.add_parser(
        "rollback", help="Rollback to previous step"
    )
    rollback_parser.add_argument(
        "--to",
        required=True,
        choices=[step.value for step in WorkflowStep],
        help="Step to rollback to",
    )

    # List command
    list_parser = subparsers.add_parser("list", help="List checkpoints or steps")
    list_parser.add_argument(
        "--steps",
        action="store_true",
        help="List available workflow steps",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if not args.command:
        parser.print_help()
        return

    # Initialize CLI
    cli = WorkflowCLI(repo_path=args.repo_path, thread_id=args.session)

    try:
        if args.command == "start":
            # Read feature file (required)
            feature_path = Path(args.feature_file)
            if not feature_path.exists():
                logger.error(f"❌ Feature file not found: {feature_path}")
                sys.exit(1)
            feature_file_content = feature_path.read_text()

            await cli.start_workflow(
                feature_file_content=feature_file_content,
                stop_at=args.stop_at,
                feature_name=args.feature_name,
                pr_number=args.pr_number,
            )

        elif args.command == "resume":
            await cli.resume_workflow(stop_at=args.stop_at)

        elif args.command == "rollback":
            state = await cli.rollback_to_step(args.to)
            logger.info(f"✅ Rolled back to step: {args.to}")
            logger.info(f"📊 Current state: {state.get('current_phase', 'Unknown')}")

        elif args.command == "list":
            if args.steps:
                steps = cli.list_available_steps()
                logger.info("📋 Available workflow steps:")
                for i, step in enumerate(steps, 1):
                    logger.info(f"  {i}. {step}")
            else:
                await cli.list_checkpoints()

    except Exception as e:
        logger.error(f"❌ Command failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
