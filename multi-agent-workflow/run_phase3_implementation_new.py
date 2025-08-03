#!/usr/bin/env python3
"""
Round 3 (Phase 3) Implementation Cycles Runner

This script executes Phase 3 of the multi-agent workflow:
1. Loads the consolidated design document from Phase 2
2. Parses implementation tasks from the design
3. Uses coding agents to generate actual code
4. Creates tests for the implementation
5. Commits the implementation to the PR

Usage:
    python multi-agent-workflow/run_phase3_implementation.py [--pr-number PR]
"""

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from logging_config import setup_logging
from workflow_orchestrator import WorkflowOrchestrator

logger = logging.getLogger(__name__)


class Phase3ImplementationRunner:
    """Orchestrates the Phase 3 implementation workflow."""

    def __init__(self, pr_number: int | None = None):
        """Initialize the Phase 3 runner.

        Args:
            pr_number: PR number (optional, auto-detects if not provided)
        """
        self.pr_number = pr_number

        # Get repository information
        self.repo_path = os.environ.get("REPO_PATH", str(Path.cwd().parent))
        self.repo_name = os.environ.get("GITHUB_REPO", "github-agent")

        # Initialize workflow orchestrator
        self.workflow = WorkflowOrchestrator(
            repo_name=self.repo_name, repo_path=self.repo_path
        )

        logger.info(f"Initialized Phase 3 runner for {self.repo_name}")

    async def run(self) -> dict:
        """Run the Phase 3 implementation workflow."""
        logger.info("🚀 Starting Phase 3 (Round 3) Implementation Cycles")

        try:
            # Call the workflow orchestrator's implement_feature method
            result = await self.workflow.implement_feature(self.pr_number)

            if result["status"] == "success":
                logger.info("✅ Phase 3 Implementation completed successfully!")
                self._log_summary(result)
            else:
                logger.error(f"❌ Phase 3 Implementation failed: {result.get('error')}")

            return result

        except Exception as e:
            logger.error(f"Phase 3 workflow failed: {e}")
            return {"status": "failed", "error": str(e), "pr_number": self.pr_number}

    def _log_summary(self, result: dict):
        """Log implementation summary."""
        logger.info("=" * 60)
        logger.info("🎉 PHASE 3 IMPLEMENTATION COMPLETE")
        logger.info("=" * 60)
        logger.info(f"PR Number: {result.get('pr_number')}")
        logger.info(f"Tasks Completed: {result.get('tasks_completed')}")
        logger.info(f"Files Created: {result.get('files_created')}")
        logger.info(f"Tests Created: {result.get('tests_created')}")

        # Log implementation details
        for impl in result.get("implementation_results", []):
            logger.info(f"  ✓ {impl.get('task')}")
            for file in impl.get("files_created", []):
                logger.info(f"    - Created: {file}")

        logger.info("=" * 60)


async def main():
    """Main entry point for Phase 3 implementation runner."""
    parser = argparse.ArgumentParser(
        description="Run Phase 3 (Round 3) Implementation Cycles",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python multi-agent-workflow/run_phase3_implementation.py
  python multi-agent-workflow/run_phase3_implementation.py --pr-number 123
        """,
    )

    parser.add_argument(
        "--pr-number",
        type=int,
        help="PR number containing the approved design (optional - auto-detects if not provided)",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Set the logging level",
    )

    args = parser.parse_args()

    # Setup logging
    log_dir = Path.home() / ".local" / "share" / "multi-agent-workflow" / "logs"
    setup_logging(
        log_level=args.log_level, log_file=log_dir / "phase3_implementation.log"
    )

    try:
        # Run Phase 3 implementation workflow
        runner = Phase3ImplementationRunner(args.pr_number)
        result = await runner.run()

        # Exit with appropriate code
        exit_code = 0 if result["status"] == "success" else 1
        sys.exit(exit_code)

    except KeyboardInterrupt:
        logger.info("Phase 3 workflow interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error in Phase 3 workflow: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
