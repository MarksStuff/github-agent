#!/usr/bin/env python3
"""
Step 1: Multi-Agent Analysis
Executes Round 1 of the workflow where all four agents analyze the feature requirements.

Usage:
    python step1_analysis.py <task_file>
    python step1_analysis.py  # Interactive mode
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

from logging_config import setup_logging
from workflow_orchestrator import WorkflowOrchestrator


async def main():
    """Run Step 1: Multi-agent analysis of feature requirements."""

    parser = argparse.ArgumentParser(
        description="Step 1: Multi-agent analysis of feature requirements",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python step1_analysis.py                              # Interactive mode
  python step1_analysis.py task.md                      # Read task from file
  python step1_analysis.py --codebase-analysis-only     # Only create codebase analysis
  python step1_analysis.py task.md --log-level DEBUG    # Debug output
        """,
    )

    parser.add_argument(
        "task_file",
        nargs="?",
        help="Path to task specification file (optional, interactive if not provided)",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Set the logging level",
    )
    parser.add_argument(
        "--codebase-analysis-only",
        action="store_true",
        help="Stop after creating the codebase analysis document (skip feature analysis)",
    )

    args = parser.parse_args()

    # Setup logging
    log_dir = Path.home() / ".local" / "share" / "multi-agent-workflow" / "logs"
    setup_logging(log_level=args.log_level, log_file=log_dir / "step1_analysis.log")

    # Get repository information
    repo_path = os.environ.get("REPO_PATH", str(Path.cwd().parent))
    repo_name = os.environ.get("GITHUB_REPO", "github-agent")

    print("=" * 60)
    print("Step 1: Multi-Agent Analysis")
    print("=" * 60)
    print(f"Repository: {repo_name}")
    print(f"Path: {repo_path}")

    # Load task specification (skip if only doing codebase analysis)
    task_spec = ""
    if not args.codebase_analysis_only:
        if args.task_file:
            task_file = Path(args.task_file)
            if not task_file.exists():
                print(f"Error: Task file not found: {task_file}")
                return 1

            print(f"\nReading task from: {task_file}")
            with open(task_file) as f:
                task_spec = f.read()
        else:
            # Interactive mode
            print("\nEnter task specification (end with empty line):")
            lines = []
            while True:
                try:
                    line = input()
                    if not line:
                        break
                    lines.append(line)
                except EOFError:
                    break
            task_spec = "\n".join(lines)

            if not task_spec.strip():
                print("Error: Empty task specification")
                return 1

        # Display task summary
        first_line = task_spec.strip().split("\n")[0]
        print(f"\nTask: {first_line[:80]}...")

    # Create orchestrator and run analysis
    print("\nInitializing workflow orchestrator...")
    orchestrator = WorkflowOrchestrator(repo_name, repo_path)

    # Run codebase analysis first if not already done
    print("\nChecking for codebase analysis...")
    codebase_analysis_path = orchestrator.get_absolute_path(
        ".workflow/codebase_analysis.md"
    )
    if not codebase_analysis_path.exists():
        print("Running initial codebase analysis with Senior Engineer...")
        await orchestrator.analyze_codebase()
    else:
        print(f"Using existing codebase analysis from: {codebase_analysis_path}")

    # If --codebase-analysis-only flag is set, stop here
    if args.codebase_analysis_only:
        print("\n" + "=" * 60)
        print("CODEBASE ANALYSIS COMPLETE")
        print("=" * 60)
        print(f"✅ Codebase analysis saved to: {codebase_analysis_path}")
        print(
            "\nTo run the full feature analysis, run without --codebase-analysis-only"
        )
        return 0

    print("\nStarting multi-agent analysis...")
    print("(This will create analysis documents from all four agent personas)")

    result = await orchestrator.analyze_feature(task_spec)

    # Display results
    print("\n" + "=" * 60)
    print("ANALYSIS RESULTS")
    print("=" * 60)

    if result["status"] == "success":
        print("✅ Analysis completed successfully!")
        print(f"📝 PR Number: {result['pr_number']}")
        if result.get("pr_url"):
            print(f"🔗 PR URL: {result['pr_url']}")
        print(f"💾 Context saved to: {result['context_file']}")
        print()

        print("Analysis documents created:")
        for agent, path in result["analysis_artifacts"].items():
            print(f"  - {agent}: {path}")

        print("\nNext steps:")
        print(
            f"1. Review the analysis documents in {repo_path}/.workflow/round_1_analysis/"
        )
        print("2. Provide feedback via GitHub PR comments")
        print(
            "3. Run 'python step2_create_design_document.py --pr {}'".format(
                result["pr_number"]
            )
        )

        return 0
    else:
        print(f"❌ Analysis failed: {result.get('error', 'Unknown error')}")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
