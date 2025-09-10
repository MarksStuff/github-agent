#!/usr/bin/env python3
"""
Step 2: Create Consolidated Design Document
Executes Round 2 of the workflow where agents review each other's analysis and create a unified design.

Usage:
    python step2_create_design_document.py --pr PR_NUMBER [--claude-code | --amp]
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from common_utils import (
    add_common_arguments,
    print_step_header,
    setup_common_environment,
    validate_github_token,
)
from task_context import TaskContext
from workflow_orchestrator import WorkflowOrchestrator

logger = logging.getLogger(__name__)


async def main():
    """Run Step 2: Create consolidated design document from agent analyses."""

    parser = argparse.ArgumentParser(
        description="Step 2: Create consolidated design document",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
This step:
1. Loads the analysis documents from Step 1
2. Has agents review each other's analyses
3. Resolves conflicts between different approaches
4. Creates a consolidated design document

Works with features from either:
- Single task files (step1_analysis.py task.md)
- PRD extractions (step1_analysis.py --prd-file prd.md --feature "Feature Name")

Example:
  python step2_create_design_document.py --pr 123
        """,
    )

    parser.add_argument(
        "--pr",
        type=int,
        required=True,
        help="PR number containing the analysis documents",
    )

    # Add CLI selection arguments
    cli_group = parser.add_mutually_exclusive_group()
    cli_group.add_argument(
        "--claude-code",
        action="store_true",
        help="Use Claude Code CLI instead of Sourcegraph Amp",
    )
    cli_group.add_argument(
        "--amp", action="store_true", help="Use Sourcegraph Amp CLI (default)"
    )

    add_common_arguments(parser)

    args = parser.parse_args()

    # Setup common environment
    env = setup_common_environment("step2_design", args)
    repo_path = env["repo_path"]
    repo_name = env["repo_name"]

    # Check for GITHUB_TOKEN early - fail fast if missing
    if not validate_github_token():
        return 1

    # Determine which CLI to use
    use_claude_code = args.claude_code or not args.amp

    print_step_header(
        "Step 2",
        "Create Consolidated Design Document",
        repository=repo_name,
        pr_number=args.pr,
        cli_type="Claude Code" if use_claude_code else "Sourcegraph Amp",
    )

    # Create orchestrator with CLI preference
    orchestrator = WorkflowOrchestrator(
        repo_name, repo_path, use_claude_code=use_claude_code
    )

    # Load existing context
    print("\nLoading analysis context...")
    # Use absolute path based on repo_path to avoid working directory issues
    context_file = (
        Path(repo_path).resolve() / ".workflow" / f"context_pr_{args.pr}.json"
    )

    if not context_file.exists():
        print(f"❌ Context file not found: {context_file}")
        print("Please run step1_analysis.py first")
        return 1

    context = TaskContext.load_from_file(str(context_file))
    context.set_pr_number(args.pr)

    print(f"✅ Loaded context for: {context.feature_spec.name}")

    # Debug: check analysis content lengths
    for agent_type, result in context.analysis_results.items():
        print(f"  - {agent_type}: {len(result.content)} chars")

    # Fetch PR comments for feedback integration
    print("\nFetching PR comments for feedback integration...")
    await orchestrator._fetch_pr_comments_for_context(context, args.pr)

    # Check if design already exists
    design_dir = Path(repo_path).resolve() / ".workflow" / "round_2_design"
    consolidated_design = design_dir / "consolidated_design.md"

    if consolidated_design.exists():
        print(f"\n⚠️  Design document already exists: {consolidated_design}")
        print("Do you want to regenerate it? (y/N): ", end="")
        response = input().strip().lower()
        if response != "y":
            print(
                "Skipping design generation. Run step3_finalize_design_document.py next."
            )
            return 0

    # Run design consolidation
    print("\nStarting design consolidation workflow...")
    print("Agents will:")
    print("  1. Review each other's analyses")
    print("  2. Identify and resolve conflicts")
    print("  3. Create a unified design document")

    try:
        result = await orchestrator.consolidate_design(context)

        print("\n" + "=" * 60)
        print("DESIGN CONSOLIDATION RESULTS")
        print("=" * 60)

        if result["status"] == "success":
            print("✅ Design document created successfully!")

            if "design_artifacts" in result:
                print("\nDesign artifacts created:")
                for artifact, path in result["design_artifacts"].items():
                    print(f"  - {artifact}: {path}")

            print("\nKey design elements:")
            if "conflicts_resolved" in result:
                print(f"  - Conflicts resolved: {result['conflicts_resolved']}")
            if "design_decisions" in result:
                print(f"  - Design decisions made: {len(result['design_decisions'])}")

            print("\nNext steps:")
            print(
                f"1. Review the consolidated design in {repo_path}/.workflow/round_2_design/"
            )
            print("2. Provide feedback via GitHub PR comments")
            print(f"3. Run 'python step3_finalize_design_document.py --pr {args.pr}'")

            return 0
        else:
            error_msg = result.get("error", "Unknown error")
            print(f"❌ Design consolidation failed: {error_msg}")
            logger.error(f"Design consolidation failed: {error_msg}")

            # Fail fast - don't continue if design consolidation fails
            if "thread creation" in error_msg.lower() or "405" in error_msg:
                print(
                    "\n💡 Tip: If using Sourcegraph Amp, try --claude-code flag instead"
                )

            return 1

    except Exception as e:
        error_msg = f"Unexpected error during design consolidation: {e}"
        logger.error(error_msg)
        print(f"❌ {error_msg}")

        # Check if it's a CLI-related error
        if "thread creation" in str(e).lower() or "405" in str(e):
            print("\n💡 Tip: If using Sourcegraph Amp, try --claude-code flag instead")

        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
