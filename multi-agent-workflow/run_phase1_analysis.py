#!/usr/bin/env python3
"""Example script for running Phase 1 analysis workflow."""

import asyncio
import os
import sys
from pathlib import Path

from logging_config import setup_logging
from workflow_orchestrator import WorkflowOrchestrator, resume_workflow


async def main():
    """Run the Phase 1 analysis example."""

    # Setup logging
    log_dir = Path.home() / ".local" / "share" / "multi-agent-workflow" / "logs"
    setup_logging(log_level="INFO", log_file=log_dir / "phase1_analysis.log")

    # Get repository information from environment or use defaults
    repo_path = os.environ.get("REPO_PATH", str(Path.cwd().parent))

    # For the repo name, we'll use a placeholder since create_repository_config
    # will extract the actual GitHub owner/repo from the git remote
    repo_name = os.environ.get("GITHUB_REPO", "github-agent")

    # Example task specifications
    example_tasks = {
        "logging": """Add request logging to API endpoints

Requirements:
- Log all incoming API requests with timestamp, method, path, and response status
- Include request duration in milliseconds
- Support different log levels (INFO for success, ERROR for failures)
- Ensure sensitive data (passwords, tokens) are not logged

Acceptance Criteria:
- All API endpoints have request logging
- Logs are structured (JSON format)
- Performance impact is minimal (<1ms per request)
- Sensitive data is properly filtered

Constraints:
- Must use existing logging infrastructure
- Cannot break existing functionality
- Must be configurable (can be disabled)
""",
        "validation": """Implement user input validation

Requirements:
- Validate all user inputs before processing
- Provide clear error messages for invalid inputs
- Support common validation rules (email, phone, required fields)
- Client-side and server-side validation

Acceptance Criteria:
- All forms have proper validation
- Error messages are user-friendly
- Validation is consistent across the application
- API returns proper error responses for invalid data
""",
        "caching": """Add Redis caching to user profile service

Requirements:
- Cache user profile data to reduce database load
- Implement cache invalidation on profile updates
- Support configurable TTL (time-to-live)
- Add cache hit/miss metrics

Acceptance Criteria:
- User profile queries are cached
- Cache is properly invalidated on updates
- Performance improvement of at least 50% for cached queries
- Monitoring shows cache effectiveness

Constraints:
- Must use Redis (already in infrastructure)
- Cannot cache sensitive data unencrypted
- Must handle Redis connection failures gracefully
""",
    }

    print("=" * 80)
    print("Multi-Agent Workflow - Phase 1 Analysis Demo")
    print("=" * 80)
    print(f"Repository: {repo_name}")
    print(f"Path: {repo_path}")
    print()

    # Check command line arguments
    if len(sys.argv) > 1:
        if sys.argv[1] == "resume":
            # Optional PR number, will auto-detect if not provided
            pr_number = None
            if len(sys.argv) >= 3:
                pr_number = int(sys.argv[2])

            print("Resuming workflow...")
            await resume_workflow(repo_name, repo_path, pr_number)
            return

        elif sys.argv[1] == "--help" or sys.argv[1] == "-h":
            print("Usage:")
            print(
                "  python run_phase1_analysis.py                    # Interactive mode"
            )
            print(
                "  python run_phase1_analysis.py <task_file>        # Read task from file"
            )
            print(
                "  python run_phase1_analysis.py resume [pr_number] # Resume workflow (auto-detects PR)"
            )
            print()
            print("Environment variables:")
            print("  GITHUB_REPO - Repository name (default: myorg/myrepo)")
            print("  REPO_PATH   - Repository path (default: parent directory)")
            return

        else:
            # Assume it's a file path
            task_file = Path(sys.argv[1])
            if not task_file.exists():
                print(f"Error: Task file not found: {task_file}")
                return

            print(f"Reading task specification from: {task_file}")
            with open(task_file) as f:
                task_spec = f.read()

            print(f"Loaded task: {task_spec.strip().split(chr(10))[0][:60]}...")
            print()

    # Select task - skip if already loaded from file
    if "task_spec" not in locals():
        print("Available example tasks:")
        for i, (key, task) in enumerate(example_tasks.items(), 1):
            first_line = task.strip().split("\n")[0]
            print(f"{i}. {key}: {first_line}")

        print("\nSelect a task (1-3) or press Enter to use custom task: ", end="")
        choice = input().strip()

        if choice in ["1", "2", "3"]:
            task_key = list(example_tasks.keys())[int(choice) - 1]
            task_spec = example_tasks[task_key]
            print(f"\nUsing {task_key} task")
        else:
            print("\nEnter your task specification (end with empty line):")
            lines = []
            while True:
                line = input()
                if not line:
                    break
                lines.append(line)
            task_spec = "\n".join(lines)

    # Create orchestrator and run analysis
    print("\nInitializing workflow orchestrator...")
    orchestrator = WorkflowOrchestrator(repo_name, repo_path)

    print("Starting Phase 1 analysis workflow...")
    print("(This will create analysis documents from all four agent personas)")
    print()

    result = await orchestrator.analyze_feature(task_spec)

    # Display results
    print("\n" + "=" * 80)
    print("WORKFLOW RESULTS")
    print("=" * 80)

    if result["status"] == "success":
        print("✓ Analysis completed successfully!")
        print(f"✓ PR Number: {result['pr_number']}")
        if result["pr_number"] > 0:
            print(f"✓ PR URL: {result['pr_url']}")
        print(f"✓ Context saved to: {result['context_file']}")
        print()
        print("Analysis artifacts created:")
        for agent, path in result["analysis_artifacts"].items():
            print(f"  - {agent}: {path}")
        print()
        print("Next steps:")
        print(
            "1. Review the analysis documents in the .workflow/round_1_analysis/ directory"
        )
        print("2. Create a GitHub PR if not already created")
        print("3. Commit and push the .workflow directory to your PR branch")
        print("4. Review analyses and provide feedback via GitHub comments")
        print(
            "5. Run 'python run_phase1_analysis.py resume <pr_number>' to check for feedback"
        )
    else:
        print(f"✗ Workflow failed: {result.get('error', 'Unknown error')}")


if __name__ == "__main__":
    asyncio.run(main())
