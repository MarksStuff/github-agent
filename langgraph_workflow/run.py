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
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(f'workflow_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
    ],
)
logger = logging.getLogger(__name__)


def extract_feature_from_prd(prd_content: str, feature_name: str) -> str | None:
    """Extract a specific feature from a PRD document.

    Args:
        prd_content: Full PRD content
        feature_name: Name/title of the feature to extract

    Returns:
        Feature description or None if not found
    """
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


async def run_workflow(
    repo_path: str,
    feature_description: str,
    thread_id: str | None = None,
    checkpoint_path: str = "agent_state.db",
    resume: bool = False,
    feature_file: str | None = None,
    feature_name: str | None = None,
    workflow_class=None,
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
    """

    # Handle feature input variations
    if feature_file:
        # Load feature from file
        feature_path = Path(feature_file)
        if not feature_path.exists():
            raise FileNotFoundError(f"Feature file not found: {feature_file}")

        prd_content = feature_path.read_text()

        if feature_name:
            # Extract specific feature from PRD
            feature_description = extract_feature_from_prd(prd_content, feature_name)
            if not feature_description:
                raise ValueError(f"Feature '{feature_name}' not found in PRD")
        else:
            # Use entire file content
            feature_description = prd_content
    elif feature_name and not feature_file:
        raise ValueError("feature_name requires feature_file to be specified")
    logger.info(f"Starting workflow for: {feature_description}")

    # Initialize workflow
    if workflow_class is None:
        workflow_class = MultiAgentWorkflow

    workflow = workflow_class(
        repo_path=repo_path, thread_id=thread_id, checkpoint_path=checkpoint_path
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

        # Run workflow
        config = {"configurable": {"thread_id": workflow.thread_id}}
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

            artifacts_dir = Path(repo_path) / "agents" / "artifacts" / thread_id
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


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Run the LangGraph multi-agent workflow",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start workflow with direct feature description
  python run.py --repo-path /path/to/repo --feature "Add user authentication"

  # Start workflow from feature file
  python run.py --repo-path /path/to/repo --feature-file features.md

  # Start workflow with specific feature from PRD
  python run.py --repo-path /path/to/repo --feature-file prd.md --feature-name "User Authentication"

  # Resume existing workflow
  python run.py --repo-path /path/to/repo --thread-id pr-1234 --resume

  # Interactive mode
  python run.py --interactive
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
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")

    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    if args.interactive:
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
            )
        )
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
