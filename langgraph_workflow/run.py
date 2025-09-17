#!/usr/bin/env python
"""Run the LangGraph multi-agent workflow."""

import argparse
import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path

from langgraph_workflow import (
    EnhancedMultiAgentWorkflow,
    FeedbackGateStatus,
    ModelRouter,
    QualityLevel,
    WorkflowPhase,
    WorkflowState,
)

# Set up logging
from langgraph_workflow.config import (
    WORKFLOW_CONFIG,
    get_checkpoint_path,
    get_ollama_base_url,
    get_ollama_model,
)
from langgraph_workflow.startup_validation import (
    check_mock_mode,
    run_startup_validation,
)

# Ensure logs directory exists
logs_dir = Path(WORKFLOW_CONFIG["paths"]["logs_root"])
logs_dir.mkdir(parents=True, exist_ok=True)
log_file = logs_dir / f'workflow_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(str(log_file)),
    ],
)
logger = logging.getLogger(__name__)


async def extract_feature_from_prd(
    prd_content: str, feature_name: str, debug: bool = False
) -> str | None:
    """Extract a specific feature from a PRD document using LLM.

    Args:
        prd_content: Full PRD content
        feature_name: Name/title of the feature to extract
        debug: Enable verbose output

    Returns:
        Feature description or None if not found
    """
    import os
    import subprocess

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
        from langchain_ollama import ChatOllama

        # Use configuration for Ollama setup
        ollama_base_url = get_ollama_base_url()
        ollama_model = os.getenv("OLLAMA_MODEL", get_ollama_model("default"))

        logger.info("Attempting feature extraction with Ollama")
        ollama_client = ChatOllama(
            base_url=ollama_base_url,
            model=ollama_model,
        )

        from langchain_core.messages import HumanMessage

        response = await ollama_client.ainvoke(
            [HumanMessage(content=extraction_prompt)]
        )
        extracted_content = str(response.content).strip() if response.content else ""

        if extracted_content and len(extracted_content) > 10:
            logger.info("✅ Successfully extracted feature using Ollama")

            # Check if feature was not found
            if extracted_content == "FEATURE_NOT_FOUND":
                return None

            # Clean up extracted content - remove LLM thinking
            cleaned_content = extracted_content
            if cleaned_content.startswith("<think>"):
                # Find the end of thinking section and extract clean content
                import re

                # Remove <think>...</think> sections
                cleaned_content = re.sub(
                    r"<think>.*?</think>", "", cleaned_content, flags=re.DOTALL
                ).strip()

            # Only show full extracted content in debug mode
            if debug:
                logger.info(f"📄 Extracted content: {extracted_content}")

            return cleaned_content
        else:
            logger.warning("Ollama returned empty or very short response")

    except Exception as e:
        logger.warning(f"Ollama feature extraction failed: {e}")

    # Fall back to Claude CLI if available
    try:
        # Check if Claude CLI is available
        claude_result = subprocess.run(
            ["claude", "--version"], capture_output=True, text=True, timeout=5
        )
        use_claude_cli = (
            claude_result.returncode == 0 and "Claude Code" in claude_result.stdout
        )

        if use_claude_cli:
            logger.info("Attempting feature extraction with Claude CLI")
            claude_result = subprocess.run(
                ["claude"],
                input=extraction_prompt,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if claude_result.returncode == 0:
                extracted_content = claude_result.stdout.strip()
                logger.info("Successfully extracted feature using Claude CLI")

                # Check if feature was not found
                if extracted_content == "FEATURE_NOT_FOUND":
                    return None
                return extracted_content
            else:
                logger.warning(f"Claude CLI failed: {claude_result.stderr}")

    except Exception as e:
        logger.warning(f"Claude CLI failed: {e}")

    # Fall back to Claude API if available
    try:
        from langchain_anthropic import ChatAnthropic
        from langchain_core.messages import HumanMessage

        api_key = os.getenv("ANTHROPIC_API_KEY")
        if api_key:
            logger.info("Attempting feature extraction with Claude API")
            claude_model = ChatAnthropic()  # type: ignore
            response = await claude_model.ainvoke(
                [HumanMessage(content=extraction_prompt)]
            )
            extracted_content = (
                str(response.content).strip() if response.content else ""
            )

            if extracted_content:
                logger.info("Successfully extracted feature using Claude API")

                # Check if feature was not found
                if extracted_content == "FEATURE_NOT_FOUND":
                    return None
                return extracted_content
        else:
            logger.warning("ANTHROPIC_API_KEY not available")

    except Exception as e:
        logger.warning(f"Claude API failed: {e}")

    # If all LLM methods failed, fall back to simple text search
    logger.error("All LLM methods failed for feature extraction")
    logger.warning("Falling back to simple text extraction")

    lines = prd_content.split("\n")
    feature_lines = []
    in_feature = False

    for line in lines:
        # Look for feature headers (markdown headers or numbered items)
        if feature_name.lower() in line.lower():
            # Found the feature
            in_feature = True
            feature_lines.append(line)
        elif in_feature:
            # Check if we've hit the next feature/section
            if (
                line.startswith("#")
                or line.startswith("##")
                or (line.strip() and line[0].isdigit() and "." in line[:5])
            ):
                # This looks like a new section
                break
            feature_lines.append(line)

    return "\n".join(feature_lines).strip() if feature_lines else None


async def run_workflow_until_step(workflow, initial_state, config, stop_after):
    """Run workflow progressively until a specific step.

    Args:
        workflow: EnhancedMultiAgentWorkflow instance
        initial_state: Initial workflow state
        config: LangGraph config with thread_id
        stop_after: Step name or number to stop after

    Returns:
        Final state after stopping
    """

    # Get list of all steps in order
    all_steps = await list_available_steps()

    # Parse stop_after - could be step name or number
    if stop_after.isdigit():
        stop_index = int(stop_after) - 1  # Convert to 0-based index
        if stop_index < 0 or stop_index >= len(all_steps):
            raise ValueError(
                f"Step number {stop_after} is out of range (1-{len(all_steps)})"
            )
        stop_step = all_steps[stop_index]
    else:
        if stop_after not in all_steps:
            raise ValueError(
                f"Unknown step '{stop_after}'. Use --list-steps to see available steps."
            )
        stop_step = stop_after
        stop_index = all_steps.index(stop_step)

    print(f"🎯 Progressive execution: Running until step {stop_index + 1}: {stop_step}")
    print(f"📋 Will execute steps 1-{stop_index + 1}:")
    for i, step in enumerate(all_steps[: stop_index + 1], 1):
        print(f"   {i:2}. {step}")

    # Check if there's an existing checkpoint for this thread using sync methods
    try:
        # For SqliteSaver, we can check the state synchronously by examining files
        # Check if artifacts already exist that indicate completed steps
        from pathlib import Path

        artifacts_path = Path.home() / ".local" / "share" / "github-agent" / "artifacts"
        completed_artifacts = {}

        # Check for existing artifacts
        if artifacts_path.exists():
            code_context_file = artifacts_path / "code_context_document.md"
            if code_context_file.exists() and code_context_file.stat().st_size > 2000:
                completed_artifacts["code_context_document"] = str(code_context_file)

            design_dir = artifacts_path / "design" / "explorations"
            if design_dir.exists():
                design_files = list(design_dir.glob("*-design.md"))
                if len(design_files) >= 4:  # All 4 agent designs exist
                    for design_file in design_files:
                        key = design_file.stem.replace("-", "_")
                        completed_artifacts[key] = str(design_file)

        if completed_artifacts:
            print("📍 Found existing artifacts indicating completed work")
            print(f"📁 Found {len(completed_artifacts)} completed artifacts")

            # Determine which steps are already complete based on artifacts
            completed_steps = []
            if "code_context_document" in completed_artifacts:
                completed_steps.append("extract_code_context")
            if any(key.endswith("_design") for key in completed_artifacts.keys()):
                completed_steps.append("parallel_design_exploration")

            print(f"✅ Already completed steps: {completed_steps}")

            # Update initial state with the found artifacts
            initial_state["artifacts_index"] = completed_artifacts

            # If we have design files, also populate agent_analyses for synthesis
            if any(key.endswith("_design") for key in completed_artifacts.keys()):
                from .enums import AgentType

                agent_analyses = {}
                for key, path in completed_artifacts.items():
                    if key.endswith("_design"):
                        # Read the design document content
                        try:
                            with open(path) as f:
                                content = f.read()
                            # Map file names to agent types
                            if "architect" in key:
                                agent_analyses[AgentType.ARCHITECT] = content
                            elif "senior_engineer" in key:
                                agent_analyses[AgentType.SENIOR_ENGINEER] = content
                            elif "fast_coder" in key:
                                agent_analyses[AgentType.FAST_CODER] = content
                            elif "test_first" in key:
                                agent_analyses[AgentType.TEST_FIRST] = content
                        except Exception as e:
                            print(f"⚠️  Could not read design file {path}: {e}")

                if agent_analyses:
                    initial_state["agent_analyses"] = agent_analyses
                    print(f"📄 Loaded {len(agent_analyses)} agent design documents")

            # If the target step is already complete, no need to run anything
            if stop_step in completed_steps:
                print(f"🎯 Target step '{stop_step}' already completed!")
                # Return the initial state with artifacts
                return initial_state

        else:
            print("📍 No existing artifacts found, starting fresh")
            completed_steps = []

        current_state = initial_state

    except Exception as e:
        print(f"⚠️  Could not check existing artifacts: {e}")
        print("📍 Starting fresh execution")
        completed_steps = []
        current_state = initial_state

    # Use the actual LangGraph workflow execution
    print(f"\n🚀 Executing workflow until step: {stop_step}")

    # For steps that haven't been completed yet, we need to execute them
    # We'll use the direct step execution to avoid async checkpoint issues
    steps_to_run = []
    all_steps_until_target = all_steps[: stop_index + 1]

    for step in all_steps_until_target:
        if step not in completed_steps:
            steps_to_run.append(step)

    if not steps_to_run:
        print(f"✅ All steps up to {stop_step} are already completed!")
        return current_state

    print(f"📋 Steps to execute: {steps_to_run}")

    # Execute remaining steps one by one
    for step in steps_to_run:
        print(f"\n🔧 Executing step: {step}")

        # Use execute_single_step for each step to avoid checkpoint issues
        current_state = await execute_single_step(
            type(workflow),
            step,
            current_state["repo_path"] if isinstance(current_state, dict) else ".",
            current_state.get("feature_description", "")
            if isinstance(current_state, dict)
            else "",
            workflow.thread_id,
            input_state=current_state
            if isinstance(current_state, dict)
            else initial_state,
        )

        print(f"✅ Step completed: {step}")

    print("\n🏁 Workflow execution completed")
    result = (
        current_state
        if isinstance(current_state, dict)
        else {"thread_id": workflow.thread_id}
    )
    print(
        f"💾 State saved with thread_id: {result.get('thread_id', workflow.thread_id)}"
    )
    print(
        f"🔄 To continue from here, use: --thread-id {result.get('thread_id', workflow.thread_id)} --resume"
    )

    return result


async def run_workflow(
    repo_path: str,
    feature_description: str,
    thread_id: str | None = None,
    checkpoint_path: str | None = None,
    resume: bool = False,
    feature_file: str | None = None,
    feature_name: str | None = None,
    workflow_class=None,
    stop_after: str | None = None,
    debug: bool = False,
):
    """Run the multi-agent workflow.

    Args:
        repo_path: Path to the repository
        feature_description: Description of the feature to implement (or path to PRD file)
        thread_id: Thread ID for persistence (auto-generated if None)
        checkpoint_path: Path to SQLite checkpoint database
        resume: Whether to resume from existing checkpoint
        feature_file: Path to file containing feature description
        feature_name: Name of specific feature within a larger PRD
        workflow_class: Workflow class to use (defaults to EnhancedMultiAgentWorkflow)
        stop_after: Stop execution after this step (step name or number)
        debug: Enable debug logging and verbose output
    """

    # Handle feature input variations
    raw_feature_input = None
    extracted_feature = None

    if feature_file:
        # Load feature from file
        feature_path = Path(feature_file)
        if not feature_path.exists():
            raise FileNotFoundError(f"Feature file not found: {feature_file}")

        prd_content = feature_path.read_text()
        raw_feature_input = prd_content  # Store the raw PRD

        if feature_name:
            # Extract specific feature from PRD using LLM
            extracted_feature = await extract_feature_from_prd(
                prd_content, feature_name, debug
            )
            if not extracted_feature:
                raise ValueError(f"Feature '{feature_name}' not found in PRD")
            feature_description = extracted_feature
        else:
            # Use entire file content
            feature_description = prd_content
    elif feature_name and not feature_file:
        raise ValueError("feature_name requires feature_file to be specified")
    if debug:
        logger.info(f"Starting workflow for: {feature_description}")
    else:
        # Show truncated feature description in normal mode
        truncated = (
            feature_description[:100] + "..."
            if len(feature_description) > 100
            else feature_description
        )
        logger.info(f"Starting workflow for: {truncated}")

    # Initialize workflow
    if workflow_class is None:
        workflow_class = EnhancedMultiAgentWorkflow

    # Use REAL dependencies for CLI execution (NOT mocks!)
    from .real_codebase_analyzer import RealCodebaseAnalyzer

    # Create real codebase analyzer
    codebase_analyzer = RealCodebaseAnalyzer(repo_path)

    # For now, we still use mocks for other dependencies until they're implemented
    # TODO: Replace these with real implementations
    from .tests.mocks import create_mock_agents

    agents = create_mock_agents()

    # Use config-based checkpoint path if not specified
    if checkpoint_path is None:
        checkpoint_path = get_checkpoint_path("agent_state")

    workflow = workflow_class(
        repo_path=repo_path,
        thread_id=thread_id,
        agents=agents,
        codebase_analyzer=codebase_analyzer,
        checkpoint_path=checkpoint_path,
    )

    if resume and thread_id:
        logger.info(f"Resuming workflow from thread: {thread_id}")
        # Resume from checkpoint
        config = {"configurable": {"thread_id": thread_id}}
        result = await workflow.app.ainvoke(None, config)
    else:
        # Create initial state
        initial_state = dict(
            WorkflowState(
                thread_id=workflow.thread_id,
                feature_description=feature_description,
                raw_feature_input=raw_feature_input,
                extracted_feature=extracted_feature,
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
        )

        # Import any existing valid artifacts into the state (migration helper)
        from .utils import populate_all_artifacts_from_files

        initial_state = populate_all_artifacts_from_files(initial_state, repo_path)

        # Run workflow (with optional stop_after)
        config = {"configurable": {"thread_id": workflow.thread_id}}

        if stop_after:
            # Progressive execution - stop after specified step
            result = await run_workflow_until_step(
                workflow, initial_state, config, stop_after
            )
        else:
            # Normal full execution
            result = await workflow.app.ainvoke(initial_state, config)

    # Print results
    print("\n" + "=" * 60)
    print("WORKFLOW COMPLETE")
    print("=" * 60)
    print(f"Thread ID: {workflow.thread_id}")
    print(f"Final Phase: {result['current_phase']}")
    print(f"Quality: {result['quality']}")
    print(f"PR Number: {result.get('pr_number', 'N/A')}")
    print(f"Git Branch: {result.get('git_branch', 'N/A')}")
    print(f"Artifacts: {workflow.artifacts_dir}")

    if result.get("conflicts"):
        print(f"\nConflicts Resolved: {len(result['conflicts'])}")
        for conflict in result["conflicts"]:
            print(f"  - {conflict.get('description', 'Unnamed conflict')}")

    if result.get("test_report"):
        report = result["test_report"]
        print("\nTest Results:")
        print(f"  Passed: {report.get('passed', 0)}")
        print(f"  Failed: {report.get('failed', 0)}")

    print("\n" + "=" * 60)

    return result


async def interactive_mode():
    """Run in interactive mode with menu options."""
    print("\n" + "=" * 60)
    print("LANGGRAPH MULTI-AGENT WORKFLOW")
    print("=" * 60)

    while True:
        print("\n1. Start new workflow")
        print("2. Resume existing workflow")
        print("3. List existing threads")
        print("4. View thread artifacts")
        print("5. Exit")

        choice = input("\nSelect option: ").strip()

        if choice == "1":
            repo_path = input("Repository path: ").strip()
            feature = input("Feature description: ").strip()
            thread_id = input(
                "Thread ID (optional, press Enter to auto-generate): "
            ).strip()

            if not repo_path or not feature:
                print("Repository path and feature description are required!")
                continue

            await run_workflow(
                repo_path=repo_path,
                feature_description=feature,
                thread_id=thread_id if thread_id else None,
            )

        elif choice == "2":
            thread_id = input("Thread ID to resume: ").strip()
            repo_path = input("Repository path: ").strip()

            if not thread_id or not repo_path:
                print("Thread ID and repository path are required!")
                continue

            await run_workflow(
                repo_path=repo_path,
                feature_description="",  # Will be loaded from checkpoint
                thread_id=thread_id,
                resume=True,
            )

        elif choice == "3":
            # List threads from SQLite database
            import sqlite3

            db_path = (
                input("Database path (default: agent_state.db): ").strip()
                or "agent_state.db"
            )

            if Path(db_path).exists():
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT DISTINCT thread_id FROM checkpoints")
                threads = cursor.fetchall()
                conn.close()

                if threads:
                    print("\nExisting threads:")
                    for thread in threads:
                        print(f"  - {thread[0]}")
                else:
                    print("No threads found")
            else:
                print(f"Database not found: {db_path}")

        elif choice == "4":
            thread_id = input("Thread ID: ").strip()
            repo_path = input("Repository path: ").strip()

            from .config import get_artifacts_path

            artifacts_dir = get_artifacts_path(thread_id)
            if artifacts_dir.exists():
                print(f"\nArtifacts in {artifacts_dir}:")
                for item in artifacts_dir.rglob("*"):
                    if item.is_file():
                        print(f"  - {item.relative_to(artifacts_dir)}")
            else:
                print(f"No artifacts found for thread: {thread_id}")

        elif choice == "5":
            print("Exiting...")
            break

        else:
            print("Invalid option!")


async def execute_single_step(
    workflow_class,
    step_name: str,
    repo_path: str,
    feature_description: str = "",
    thread_id: str | None = None,
    checkpoint_path: str | None = None,
    input_state: dict | None = None,
) -> dict:
    """Execute a single workflow step for testing/debugging.

    Args:
        workflow_class: The workflow class to use
        step_name: Name of the step to execute
        repo_path: Path to the repository
        feature_description: Feature description
        thread_id: Thread ID for persistence
        checkpoint_path: SQLite checkpoint path
        input_state: Optional input state (will create default if None)

    Returns:
        Updated state after step execution
    """
    from .enums import ModelRouter, WorkflowPhase, WorkflowStep
    from .real_codebase_analyzer import RealCodebaseAnalyzer
    from .tests.mocks import create_mock_agents

    print(f"🔧 Executing single step: {step_name}")

    # Create workflow with REAL dependencies (NOT mocks!)
    codebase_analyzer = RealCodebaseAnalyzer(repo_path)
    agents = create_mock_agents()  # Still using mock agents until implemented

    if workflow_class is None:
        workflow_class = EnhancedMultiAgentWorkflow

    # Use config-based checkpoint path if not specified
    if checkpoint_path is None:
        checkpoint_path = get_checkpoint_path("agent_state")

    # Don't log workflow creation for single steps
    import logging

    enhanced_logger = logging.getLogger("langgraph_workflow.enhanced_workflow")
    original_level = enhanced_logger.level
    enhanced_logger.setLevel(logging.WARNING)

    workflow = workflow_class(
        repo_path=repo_path,
        thread_id=thread_id or "step-test",
        agents=agents,
        codebase_analyzer=codebase_analyzer,
        checkpoint_path=checkpoint_path,
    )

    # Create initial state if not provided
    if input_state is None:
        initial_state = {
            "thread_id": workflow.thread_id,
            "feature_description": feature_description,
            "raw_feature_input": None,
            "extracted_feature": None,
            "current_phase": WorkflowPhase.PHASE_0_CODE_CONTEXT,
            "messages_window": [],
            "summary_log": "",
            "artifacts_index": {},
            "code_context_document": None,
            "design_constraints_document": None,
            "design_document": None,
            "arbitration_log": [],
            "repo_path": repo_path,
            "git_branch": "main",
            "last_commit_sha": None,
            "pr_number": None,
            "agent_analyses": {},
            "synthesis_document": None,
            "conflicts": [],
            "skeleton_code": None,
            "test_code": None,
            "implementation_code": None,
            "patch_queue": [],
            "test_report": {},
            "ci_status": {},
            "lint_status": {},
            "quality": "draft",
            "feedback_gate": "open",
            "model_router": ModelRouter.OLLAMA,
            "escalation_count": 0,
        }
    else:
        initial_state = input_state.copy()

    # Get the step method - map step names to workflow methods
    step_methods = {
        WorkflowStep.EXTRACT_FEATURE.value: workflow.extract_feature,
        WorkflowStep.EXTRACT_CODE_CONTEXT.value: workflow.extract_code_context,
        WorkflowStep.PARALLEL_DESIGN_EXPLORATION.value: workflow.parallel_design_exploration,
        WorkflowStep.DESIGN_SYNTHESIS.value: workflow.design_synthesis,
        WorkflowStep.ARCHITECT_SYNTHESIS.value: workflow.architect_synthesis,
        WorkflowStep.CODE_INVESTIGATION.value: workflow.code_investigation,
        WorkflowStep.HUMAN_REVIEW.value: workflow.human_review,
        WorkflowStep.CREATE_DESIGN_DOCUMENT.value: workflow.create_design_document,
        WorkflowStep.ITERATE_DESIGN_DOCUMENT.value: workflow.iterate_design_document,
        WorkflowStep.FINALIZE_DESIGN_DOCUMENT.value: workflow.finalize_design_document,
        WorkflowStep.CREATE_SKELETON.value: workflow.create_skeleton,
        WorkflowStep.PARALLEL_DEVELOPMENT.value: workflow.parallel_development,
        WorkflowStep.RECONCILIATION.value: workflow.reconciliation,
        WorkflowStep.COMPONENT_TESTS.value: workflow.component_tests,
        WorkflowStep.INTEGRATION_TESTS.value: workflow.integration_tests,
        WorkflowStep.REFINEMENT.value: workflow.refinement,
    }

    if step_name not in step_methods:
        raise ValueError(
            f"Unknown step: {step_name}. Available steps: {list(step_methods.keys())}"
        )

    # Execute the step
    print(f"📍 Initial phase: {initial_state.get('current_phase', 'Unknown')}")
    result_state = await step_methods[step_name](initial_state)

    # Restore logging level
    enhanced_logger.setLevel(original_level)

    print(f"📍 Final phase: {result_state.get('current_phase', 'Unknown')}")

    # Show key changes
    print("📊 Step Results:")
    print(f"   - Messages: {len(result_state.get('messages_window', []))}")
    print(f"   - Artifacts: {len(result_state.get('artifacts_index', {}))}")
    print(f"   - Quality: {result_state.get('quality', 'unknown')}")

    if result_state.get("artifacts_index"):
        print("📁 Artifacts created:")
        for key, path in result_state["artifacts_index"].items():
            print(f"   - {key}: {path}")

    return result_state


async def list_available_steps() -> list[str]:
    """List all available workflow steps."""
    from .enums import WorkflowStep

    # Return steps in execution order (excluding deployment steps)
    steps = [
        WorkflowStep.EXTRACT_FEATURE.value,
        WorkflowStep.EXTRACT_CODE_CONTEXT.value,
        WorkflowStep.PARALLEL_DESIGN_EXPLORATION.value,
        WorkflowStep.DESIGN_SYNTHESIS.value,
        WorkflowStep.ARCHITECT_SYNTHESIS.value,
        WorkflowStep.CODE_INVESTIGATION.value,
        WorkflowStep.HUMAN_REVIEW.value,
        WorkflowStep.CREATE_DESIGN_DOCUMENT.value,
        WorkflowStep.ITERATE_DESIGN_DOCUMENT.value,
        WorkflowStep.FINALIZE_DESIGN_DOCUMENT.value,
        WorkflowStep.CREATE_SKELETON.value,
        WorkflowStep.PARALLEL_DEVELOPMENT.value,
        WorkflowStep.RECONCILIATION.value,
        WorkflowStep.COMPONENT_TESTS.value,
        WorkflowStep.INTEGRATION_TESTS.value,
        WorkflowStep.REFINEMENT.value,
    ]
    return steps


async def interactive_step_mode():
    """Interactive mode for step-by-step execution."""
    print("\n" + "=" * 60)
    print("🔧 STEP-BY-STEP WORKFLOW EXECUTION")
    print("=" * 60)

    repo_path = input("Repository path: ").strip()
    if not repo_path:
        print("Repository path is required!")
        return

    feature = input("Feature description: ").strip()
    if not feature:
        print("Feature description is required!")
        return

    thread_id = input("Thread ID (optional): ").strip() or None

    # Track state between steps
    current_state = None

    while True:
        print("\n🔧 Step-by-Step Workflow Execution")
        print("=" * 40)

        steps = await list_available_steps()

        print("Available steps:")
        for i, step in enumerate(steps, 1):
            print(f"  {i:2}. {step}")

        print("\n  0. Exit")
        print("  s. Show current state")
        print("  r. Reset state")

        choice = (
            input(f"\nSelect step to execute (1-{len(steps)}) or command: ")
            .strip()
            .lower()
        )

        if choice == "0" or choice == "exit":
            break
        elif choice == "s":
            if current_state:
                print("\n📊 Current State:")
                print(f"   Phase: {current_state.get('current_phase')}")
                print(f"   Messages: {len(current_state.get('messages_window', []))}")
                print(f"   Artifacts: {len(current_state.get('artifacts_index', {}))}")
                print(f"   Quality: {current_state.get('quality')}")
            else:
                print("\n📊 No state yet - execute a step first")
            continue
        elif choice == "r":
            current_state = None
            print("\n🔄 State reset")
            continue

        try:
            step_index = int(choice) - 1
            if 0 <= step_index < len(steps):
                step_name = steps[step_index]

                print(f"\n⚡ Executing step: {step_name}")
                result_state = await execute_single_step(
                    EnhancedMultiAgentWorkflow,
                    step_name,
                    repo_path,
                    feature,
                    thread_id,
                    input_state=current_state,
                )
                current_state = result_state
                print("✅ Step completed successfully!")

                # Ask if user wants to continue
                continue_choice = (
                    input("\nContinue to next step? (y/N): ").strip().lower()
                )
                if continue_choice == "y":
                    continue
            else:
                print("Invalid step number!")
        except ValueError:
            print("Invalid input! Please enter a number or command.")
        except Exception as e:
            print(f"❌ Error executing step: {e}")


def main():
    """Main entry point."""
    # Run startup validation unless in mock mode, listing steps, or showing help
    if (
        "--list-steps" not in sys.argv
        and "--help" not in sys.argv
        and "-h" not in sys.argv
        and not check_mock_mode()
    ):
        print("🔍 Validating startup requirements...")
        validation_results = run_startup_validation(verbose=False)

        if not validation_results["overall_valid"]:
            print("❌ Startup validation failed!")
            print("\n💡 To run anyway with mock dependencies:")
            print("   export USE_MOCK_DEPENDENCIES=true")
            print("\n🔧 Or fix the issues and try again:")
            for rec in validation_results["recommendations"]:
                print(f"   - {rec}")
            sys.exit(1)
        else:
            print("✅ Startup validation passed!")

    parser = argparse.ArgumentParser(
        description="Run the LangGraph multi-agent workflow",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start full workflow with direct feature description
  python run.py --repo-path /path/to/repo --feature "Add user authentication"

  # Start workflow from feature file
  python run.py --repo-path /path/to/repo --feature-file features.md

  # Start workflow with specific feature from PRD
  python run.py --repo-path /path/to/repo --feature-file prd.md --feature-name "User Authentication"

  # Resume existing workflow
  python run.py --repo-path /path/to/repo --thread-id pr-1234 --resume

  # Interactive mode
  python run.py --interactive

  # STEP-BY-STEP EXECUTION (NEW!)
  # List all available steps
  python run.py --list-steps

  # Execute a single step
  python run.py --repo-path /path/to/repo --feature "Add auth" --step extract_code_context

  # Interactive step-by-step mode
  python run.py --step-mode

  # PROGRESSIVE EXECUTION (NEW!)
  # Run just the first step
  python run.py --repo-path /path/to/repo --feature "Add auth" --stop-after 1

  # Run first 3 steps
  python run.py --repo-path /path/to/repo --feature "Add auth" --stop-after 3

  # Run until specific step by name
  python run.py --repo-path /path/to/repo --feature "Add auth" --stop-after create_design_document

  # Continue from where you left off
  python run.py --repo-path /path/to/repo --thread-id <saved-id> --resume
        """,
    )

    parser.add_argument("--repo-path", help="Path to the repository")
    parser.add_argument("--feature", help="Feature description (text)")
    parser.add_argument(
        "--feature-file", help="Path to file containing feature description or PRD"
    )
    parser.add_argument(
        "--feature-name",
        help="Name of specific feature within PRD (requires --feature-file)",
    )
    parser.add_argument("--thread-id", help="Thread ID for persistence")
    parser.add_argument(
        "--checkpoint-path",
        default="agent_state.db",
        help="SQLite checkpoint database path",
    )
    parser.add_argument(
        "--resume", action="store_true", help="Resume from existing checkpoint"
    )
    parser.add_argument(
        "--interactive", action="store_true", help="Run in interactive mode"
    )
    parser.add_argument(
        "--step-mode", action="store_true", help="Run in step-by-step interactive mode"
    )
    parser.add_argument(
        "--step",
        help="Execute a single workflow step (use with --list-steps to see options)",
    )
    parser.add_argument(
        "--list-steps", action="store_true", help="List all available workflow steps"
    )
    parser.add_argument(
        "--stop-after", help="Stop execution after this step (use step name or number)"
    )
    parser.add_argument(
        "--validate", action="store_true", help="Run startup validation and exit"
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")

    args = parser.parse_args()

    # Handle help early - argparse already printed help and called sys.exit
    # If we're here after --help, it means sys.exit was mocked, so we should return
    if "--help" in sys.argv or "-h" in sys.argv:
        return

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    if args.validate:
        if check_mock_mode():
            print("🧪 Mock mode enabled - all services will be mocked")
        else:
            results = run_startup_validation(verbose=True)
            sys.exit(0 if results["overall_valid"] else 1)
        return

    if args.list_steps:
        steps = asyncio.run(list_available_steps())
        print("\n🔧 Available Workflow Steps:")
        print("=" * 40)
        for i, step in enumerate(steps, 1):
            print(f"  {i:2}. {step}")
        print("\nUse --step <step_name> to execute a single step")
        print("Use --step-mode for interactive step-by-step execution")

    elif args.step_mode:
        asyncio.run(interactive_step_mode())

    elif args.step:
        if not args.repo_path:
            print("Error: --repo-path is required when using --step")
            sys.exit(1)
            return  # Ensure we don't continue even if sys.exit is mocked
        if not args.feature and not args.feature_file:
            print("Error: --feature or --feature-file is required when using --step")
            sys.exit(1)
            return  # Ensure we don't continue even if sys.exit is mocked

        # Handle feature extraction if needed
        feature_description = args.feature or ""
        if args.feature_file:
            feature_path = Path(args.feature_file)
            if not feature_path.exists():
                print(f"Error: Feature file not found: {args.feature_file}")
                sys.exit(1)
                return  # Ensure we don't continue even if sys.exit is mocked

            prd_content = feature_path.read_text()
            if args.feature_name:
                extracted_feature = asyncio.run(
                    extract_feature_from_prd(prd_content, args.feature_name)
                )
                if not extracted_feature:
                    print(f"Error: Feature '{args.feature_name}' not found in PRD")
                    sys.exit(1)
                    return  # Ensure we don't continue even if sys.exit is mocked
                feature_description = extracted_feature
            else:
                feature_description = prd_content

        # Execute single step
        asyncio.run(
            execute_single_step(
                EnhancedMultiAgentWorkflow,
                args.step,
                args.repo_path,
                feature_description,
                args.thread_id,
                args.checkpoint_path,
            )
        )

    elif args.interactive:
        asyncio.run(interactive_mode())
    elif args.repo_path:
        if not args.resume and not args.feature and not args.feature_file:
            print("Error: --feature or --feature-file is required when not resuming")
            sys.exit(1)

        if args.feature_name and not args.feature_file:
            print("Error: --feature-name requires --feature-file")
            sys.exit(1)

        asyncio.run(
            run_workflow(
                repo_path=args.repo_path,
                feature_description=args.feature or "",
                thread_id=args.thread_id,
                checkpoint_path=args.checkpoint_path,
                resume=args.resume,
                feature_file=args.feature_file,
                feature_name=args.feature_name,
                stop_after=args.stop_after,
                debug=args.debug,
            )
        )
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
