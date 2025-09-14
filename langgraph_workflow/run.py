#!/usr/bin/env python
"""Run the LangGraph multi-agent workflow."""

import argparse
import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path

from langgraph_workflow import (
    ModelRouter,
    MultiAgentWorkflow,
    WorkflowPhase,
    WorkflowState,
)

# Set up logging
from langgraph_workflow.config import WORKFLOW_CONFIG, get_checkpoint_path
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


async def extract_feature_from_prd(prd_content: str, feature_name: str) -> str | None:
    """Extract a specific feature from a PRD document using LLM.

    Args:
        prd_content: Full PRD content
        feature_name: Name/title of the feature to extract

    Returns:
        Feature description or None if not found
    """
    import os
    import subprocess

    # Try Claude CLI first, then fall back to API key
    try:
        # Check if Claude CLI is available
        claude_result = subprocess.run(
            ["claude", "--version"], capture_output=True, text=True, timeout=5
        )
        use_claude_cli = (
            claude_result.returncode == 0 and "Claude Code" in claude_result.stdout
        )
    except Exception:
        use_claude_cli = False

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

    try:
        if use_claude_cli:
            # Use Claude CLI with stdin to avoid file permission issues
            try:
                claude_result = subprocess.run(
                    ["claude"],
                    input=extraction_prompt,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )

                if claude_result.returncode == 0:
                    extracted_content = claude_result.stdout.strip()
                else:
                    raise Exception(f"Claude CLI failed: {claude_result.stderr}")
            except Exception as e:
                # If CLI fails, fall back to API
                logger.warning(f"Claude CLI failed, falling back to API: {e}")
                use_claude_cli = False

        if not use_claude_cli:
            # Fall back to API key
            from langchain_anthropic import ChatAnthropic
            from langchain_core.messages import HumanMessage

            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                raise ValueError("Neither Claude CLI nor ANTHROPIC_API_KEY available")

            claude_model = ChatAnthropic()  # type: ignore
            response = await claude_model.ainvoke(
                [HumanMessage(content=extraction_prompt)]
            )
            extracted_content = (
                str(response.content).strip() if response.content else ""
            )

        # Check if feature was not found
        if extracted_content == "FEATURE_NOT_FOUND":
            return None

        return extracted_content

    except Exception as e:
        logger.error(f"Error extracting feature with LLM: {e}")
        # Fallback to simple text search as backup
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
        workflow: MultiAgentWorkflow instance
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

    # Execute steps one by one until we reach the stop point
    current_state = initial_state.copy()

    for i, step_name in enumerate(all_steps[: stop_index + 1], 1):
        print(f"\n🔧 Executing step {i}: {step_name}")

        # Use execute_single_step to run this step
        updated_state = await execute_single_step(
            type(workflow),
            step_name,
            current_state["repo_path"],
            current_state["feature_description"],
            current_state["thread_id"],
            input_state=current_state,
        )

        current_state = updated_state
        print(f"✅ Step {i} completed: {step_name}")

    print(
        f"\n🏁 Progressive execution stopped after step {stop_index + 1}: {stop_step}"
    )
    print(f"💾 State saved with thread_id: {current_state['thread_id']}")
    print(
        f"🔄 To continue from here, use: --thread-id {current_state['thread_id']} --resume"
    )

    return current_state


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
        workflow_class: Workflow class to use (defaults to MultiAgentWorkflow)
        stop_after: Stop execution after this step (step name or number)
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
                prd_content, feature_name
            )
            if not extracted_feature:
                raise ValueError(f"Feature '{feature_name}' not found in PRD")
            feature_description = extracted_feature
        else:
            # Use entire file content
            feature_description = prd_content
    elif feature_name and not feature_file:
        raise ValueError("feature_name requires feature_file to be specified")
    logger.info(f"Starting workflow for: {feature_description}")

    # Initialize workflow
    if workflow_class is None:
        workflow_class = MultiAgentWorkflow

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
        initial_state = WorkflowState(
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
            quality="draft",
            feedback_gate="open",
            model_router=ModelRouter.OLLAMA,
            escalation_count=0,
        )

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
        workflow_class = MultiAgentWorkflow

    # Use config-based checkpoint path if not specified
    if checkpoint_path is None:
        checkpoint_path = get_checkpoint_path("agent_state")

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
                    MultiAgentWorkflow,
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
    if "--list-steps" not in sys.argv and "--help" not in sys.argv and "-h" not in sys.argv and not check_mock_mode():
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
                MultiAgentWorkflow,
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
            )
        )
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
