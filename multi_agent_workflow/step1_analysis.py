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
import json
import sys
from datetime import datetime
from pathlib import Path

from common_utils import (
    add_common_arguments,
    print_step_header,
    setup_common_environment,
    validate_github_token,
)
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
  python step1_analysis.py --prd-file prd.md --feature "User Authentication"  # Extract feature from PRD
        """,
    )

    parser.add_argument(
        "task_file",
        nargs="?",
        help="Path to task specification file (optional, interactive if not provided)",
    )
    add_common_arguments(parser)
    parser.add_argument(
        "--codebase-analysis-only",
        action="store_true",
        help="Stop after creating the codebase analysis document (skip feature analysis)",
    )
    parser.add_argument(
        "--prd-file",
        help="Path to PRD file containing multiple features",
    )
    parser.add_argument(
        "--feature",
        help="Feature name/identifier to extract from PRD file (required with --prd-file)",
    )
    parser.add_argument(
        "--claude-code",
        action="store_true",
        help="Use Claude Code CLI instead of Amp CLI",
    )
    parser.add_argument(
        "--amp",
        action="store_true",
        help="Use Amp CLI (default if neither CLI option specified)",
    )

    args = parser.parse_args()

    # Validate PRD arguments
    if args.prd_file and not args.feature:
        parser.error("--feature is required when using --prd-file")
    if args.feature and not args.prd_file:
        parser.error("--prd-file is required when using --feature")
    if args.prd_file and args.task_file:
        parser.error("Cannot use both task_file and --prd-file")

    # Setup common environment
    env = setup_common_environment("step1_analysis", args)
    repo_path = env["repo_path"]
    repo_name = env["repo_name"]

    # Check for GITHUB_TOKEN early - fail fast if missing
    if not validate_github_token():
        return 1

    print_step_header(
        "Step 1", "Multi-Agent Analysis", repository=repo_name, path=repo_path
    )

    # Load task specification (skip if only doing codebase analysis)
    task_spec = ""
    if not args.codebase_analysis_only:
        if args.prd_file:
            # Extract feature from PRD file
            prd_file = Path(args.prd_file)
            if not prd_file.exists():
                print(f"Error: PRD file not found: {prd_file}")
                return 1

            print(f"\nReading PRD from: {prd_file}")
            with open(prd_file) as f:
                prd_content = f.read()

            print(f"Extracting feature: {args.feature}")

            # Determine CLI choice
            use_claude_code = None
            if args.claude_code:
                use_claude_code = True
            elif args.amp:
                use_claude_code = False
            # else None - will check environment variable

            # Use senior engineer agent to extract the feature
            orchestrator = WorkflowOrchestrator(
                repo_name, repo_path, use_claude_code=use_claude_code
            )
            senior_engineer = orchestrator.agents["senior_engineer"]

            extraction_prompt = f"""Extract the complete feature description for "{args.feature}" from the following PRD document.

PRD Document:
{prd_content}

Instructions:
1. Find the section that describes the feature "{args.feature}"
2. Extract ALL relevant information about this feature including:
   - Feature name and description
   - Requirements and specifications
   - Acceptance criteria
   - Technical constraints
   - Implementation details
   - Dependencies
   - Any other relevant information

Return ONLY the extracted feature content in a clear, structured format.
If the feature "{args.feature}" is not found in the PRD, respond with "FEATURE_NOT_FOUND".
"""

            extracted_feature = senior_engineer.persona.ask(extraction_prompt)

            if "FEATURE_NOT_FOUND" in extracted_feature:
                print(f"Error: Feature '{args.feature}' not found in PRD")
                return 1

            task_spec = extracted_feature
            print(f"✅ Successfully extracted feature: {args.feature}")

            # Add metadata about PRD extraction to the beginning of task_spec
            task_spec = f"""# Feature: {args.feature}
(Extracted from PRD: {prd_file.name})

{task_spec}"""

        elif args.task_file:
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

    # Save the task specification to a file for subsequent steps
    workflow_dir = Path(repo_path) / ".workflow"
    workflow_dir.mkdir(parents=True, exist_ok=True)

    task_spec_file = workflow_dir / "task_specification.md"
    with open(task_spec_file, "w") as f:
        f.write(task_spec)
    print(f"\nSaved task specification to: {task_spec_file}")

    # Save extraction metadata if from PRD
    if args.prd_file:
        metadata = {
            "source": "prd",
            "prd_file": str(prd_file.absolute()),
            "feature": args.feature,
            "extracted_at": datetime.now().isoformat(),
        }
        metadata_file = workflow_dir / "task_metadata.json"
        with open(metadata_file, "w") as f:
            json.dump(metadata, f, indent=2)
        print(f"Saved extraction metadata to: {metadata_file}")

    # Determine CLI choice (if not already set from PRD extraction)
    if "use_claude_code" not in locals():
        use_claude_code = None
        if args.claude_code:
            use_claude_code = True
        elif args.amp:
            use_claude_code = False
        # else None - will check environment variable

    # Create orchestrator and run analysis
    print("\nInitializing workflow orchestrator...")
    orchestrator = WorkflowOrchestrator(
        repo_name, repo_path, use_claude_code=use_claude_code
    )

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
        if result.get("next_step"):
            # Use the orchestrator-provided next steps
            if isinstance(result["next_step"], str) and "\n" in result["next_step"]:
                for i, step in enumerate(result["next_step"].split("\n"), 1):
                    if step.strip():
                        print(f"{i}. {step.strip()}")
            else:
                print(f"1. {result['next_step']}")
        else:
            # Fallback to default steps
            print(
                f"1. Review the analysis documents in {repo_path}/.workflow/round_1_analysis/"
            )
            if result["pr_number"] and result["pr_number"] > 0:
                print("2. Provide feedback via GitHub PR comments")
                print(
                    f"3. Run 'python step2_create_design_document.py --pr {result['pr_number']}'"
                )
            else:
                print("2. Manually create a GitHub PR if desired")
                print(
                    "3. Set GITHUB_TOKEN environment variable for automatic PR management"
                )
                print(
                    "4. Run 'python step2_create_design_document.py --pr <pr_number>' once PR is available"
                )

        return 0
    else:
        print(f"❌ Analysis failed: {result.get('error', 'Unknown error')}")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
