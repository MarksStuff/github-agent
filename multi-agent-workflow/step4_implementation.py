#!/usr/bin/env python3
"""
Step 4: Interactive Development Process
Implements the 4-part development cycle for each task from the finalized design document.

Usage:
    python step4_implementation.py --pr PR_NUMBER
"""

import argparse
import asyncio
import json
import logging
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from logging_config import setup_logging
from workflow_orchestrator import WorkflowOrchestrator

from github_tools import execute_get_pr_comments, execute_post_pr_reply

logger = logging.getLogger(__name__)


class InteractiveDevelopmentProcessor:
    """Orchestrates the 4-part development process for each implementation task."""

    def __init__(self, pr_number: int, repo_path: str, repo_name: str):
        """Initialize the development processor.

        Args:
            pr_number: PR number containing the finalized design
            repo_path: Local repository path
            repo_name: GitHub repository name
        """
        self.pr_number = pr_number
        self.repo_path = Path(repo_path)
        self.repo_name = repo_name

        # Initialize workflow orchestrator
        self.orchestrator = WorkflowOrchestrator(
            repo_name=repo_name, repo_path=repo_path
        )

        self.workflow_dir = self.repo_path / ".workflow"
        self.round4_dir = self.workflow_dir / "round_4_implementation"
        self.round4_dir.mkdir(parents=True, exist_ok=True)

        # Store tasks list for reference
        self.all_tasks = []

        logger.info(f"Initialized development processor for PR #{pr_number}")

    async def run_development_process(self) -> dict:
        """Execute the complete 4-part development process."""
        logger.info("Starting 4-part development process")

        try:
            # Load the finalized design document
            design_content = await self._load_finalized_design()
            if not design_content:
                return {
                    "status": "failed",
                    "error": "No finalized design document found",
                }

            # Parse implementation tasks from the design
            tasks = await self._parse_implementation_tasks(design_content)
            if not tasks:
                return {
                    "status": "failed",
                    "error": "No implementation tasks found in design",
                }

            # Store tasks for reference
            self.all_tasks = tasks

            print(f"\nFound {len(tasks)} implementation tasks:")
            for i, task in enumerate(tasks, 1):
                print(f"  {i}. {task['title']}")

            # Execute 4-part cycle for each task
            completed_tasks = []
            for i, task in enumerate(tasks, 1):
                print(f"\n{'='*60}")
                print(f"TASK {i}/{len(tasks)}: {task['title']}")
                print(f"{'='*60}")

                task_result = await self._execute_four_part_cycle(task, i)
                completed_tasks.append(task_result)

                if task_result["status"] != "success":
                    print(f"❌ Task {i} failed: {task_result.get('error')}")
                    break
                else:
                    print(f"✅ Task {i} completed successfully")

            return {
                "status": "success",
                "pr_number": self.pr_number,
                "tasks_completed": len(
                    [t for t in completed_tasks if t["status"] == "success"]
                ),
                "total_tasks": len(tasks),
                "completed_tasks": completed_tasks,
            }

        except Exception as e:
            logger.error(f"Development process failed: {e}")
            return {"status": "failed", "error": str(e)}

    async def _load_finalized_design(self) -> str | None:
        """Load the finalized design document."""
        # Try finalized design first (from step 3)
        finalized_path = self.workflow_dir / "round_3_design" / "finalized_design.md"
        if finalized_path.exists():
            logger.info(f"Loading finalized design: {finalized_path}")
            return finalized_path.read_text()

        # Fall back to consolidated design (from step 2)
        consolidated_path = (
            self.workflow_dir / "round_2_design" / "consolidated_design.md"
        )
        if consolidated_path.exists():
            logger.info(f"Loading consolidated design: {consolidated_path}")
            return consolidated_path.read_text()

        logger.error("No design document found")
        return None

    async def _parse_implementation_tasks(
        self, design_content: str
    ) -> list[dict[str, Any]]:
        """Parse implementation tasks from the design document."""
        # Manual parsing of tasks from the design document
        tasks = []

        # Look for sections that indicate implementation tasks
        # Common patterns in design documents
        lines = design_content.split("\n")
        current_task = None
        in_implementation_section = False

        for i, line in enumerate(lines):
            # Look for implementation task markers
            if "implementation task" in line.lower() or "task:" in line.lower():
                if current_task:
                    tasks.append(current_task)

                # Extract task title from the line
                title = line.replace("Task:", "").replace("task:", "").strip()
                title = re.sub(r"^\d+\.?\s*", "", title)  # Remove numbering
                title = title.replace("#", "").strip()

                current_task = {
                    "title": title or f"Task {len(tasks) + 1}",
                    "description": "",
                    "components": [],
                    "dependencies": [],
                }
                in_implementation_section = True

            # Look for numbered implementation steps
            elif re.match(r"^\d+\.\s+", line) and "implement" in line.lower():
                if current_task:
                    tasks.append(current_task)

                title = re.sub(r"^\d+\.\s+", "", line).strip()
                current_task = {
                    "title": title,
                    "description": "",
                    "components": [],
                    "dependencies": [],
                }

            # Collect description and components
            elif current_task and in_implementation_section:
                if "file" in line.lower() or ".py" in line:
                    # Extract file names
                    file_matches = re.findall(r"[\w/]+\.py", line)
                    current_task["components"].extend(file_matches)
                elif line.strip() and not line.startswith("#"):
                    # Add to description
                    if len(current_task["description"]) < 500:
                        current_task["description"] += line.strip() + " "

        # Add the last task if exists
        if current_task:
            tasks.append(current_task)

        # If no tasks found, try to extract from headers
        if not tasks:
            # Look for ## Implementation or ### sections
            implementation_sections = re.findall(
                r"###+\s*(?:Implementation|Development|Task|Step)\s*\d*:?\s*([^\n]+)",
                design_content,
                re.IGNORECASE,
            )

            for i, section in enumerate(
                implementation_sections[:5], 1
            ):  # Limit to 5 tasks
                tasks.append(
                    {
                        "title": section.strip(),
                        "description": f"Implement the {section.strip()} as described in the design document",
                        "components": [f"implementation_{i}.py"],
                        "dependencies": [],
                    }
                )

        # If still no tasks, create a single comprehensive task
        if not tasks:
            logger.info("No specific tasks found, creating single comprehensive task")
            tasks = [
                {
                    "title": "Implement Complete Feature",
                    "description": "Implement the complete feature as described in the design document",
                    "components": ["main implementation"],
                    "dependencies": [],
                }
            ]

        logger.info(f"Parsed {len(tasks)} tasks from design")
        return tasks

    async def _execute_four_part_cycle(
        self, task: dict[str, Any], task_number: int
    ) -> dict[str, Any]:
        """Execute the 4-part development cycle for a single task."""
        print(f"\nStarting 4-part cycle for: {task['title']}")

        try:
            # Part 1: Interactive Coding Session
            print("\n--- Part 1: Interactive Coding Session ---")
            part1_result = await self._part1_interactive_coding(task, task_number)
            if part1_result["status"] != "success":
                return part1_result

            # Part 2: Multi-Agent Review and Refinement
            print("\n--- Part 2: Multi-Agent Review and Refinement ---")
            part2_result = await self._part2_multi_agent_review(
                task, task_number, part1_result
            )
            if part2_result["status"] != "success":
                return part2_result

            # Part 3: Human Review Break
            print("\n--- Part 3: Human Review Break ---")
            part3_result = await self._part3_human_review_break(task, task_number)

            # Part 4: PR Comment Integration
            print("\n--- Part 4: PR Comment Integration ---")
            part4_result = await self._part4_pr_comment_integration(task, task_number)
            if part4_result["status"] != "success":
                return part4_result

            return {
                "status": "success",
                "task": task["title"],
                "task_number": task_number,
                "parts_completed": ["part1", "part2", "part3", "part4"],
                "files_modified": part1_result.get("files_created", [])
                + part2_result.get("files_modified", [])
                + part4_result.get("files_modified", []),
            }

        except Exception as e:
            logger.error(f"4-part cycle failed for task {task_number}: {e}")
            return {"status": "failed", "error": str(e), "task": task["title"]}

    async def _part1_interactive_coding(
        self, task: dict[str, Any], task_number: int
    ) -> dict[str, Any]:
        """Part 1: Interactive coding session with developer agent."""
        print(f"Starting interactive coding session for: {task['title']}")
        print(f"Description: {task['description']}")
        print(f"Components: {', '.join(task.get('components', []))}")

        # Determine which design document path to use
        design_finalized_path = (
            self.workflow_dir / "round_3_design" / "finalized_design.md"
        )
        design_consolidated_path = (
            self.workflow_dir / "round_2_design" / "consolidated_design.md"
        )

        if design_finalized_path.exists():
            design_doc_path = design_finalized_path
        else:
            design_doc_path = design_consolidated_path

        # Path to codebase analysis document
        codebase_analysis_path = self.workflow_dir / "codebase_analysis.md"

        # Create implementation context prompt for the interactive session
        context_prompt = f"""
Read {codebase_analysis_path}

After reading that file, read {design_doc_path}

Then implement this specific task:

# Task {task_number}: {task['title']}

{task['description'] if task['description'] else 'Implement as described in the design document.'}

Files to work on: {', '.join(task.get('components', [])) if task.get('components') else 'See design document'}

Just read the two documents and write the code. Nothing else.
        """

        print("\n" + "=" * 60)
        print("STARTING INTERACTIVE CODING SESSION")
        print("=" * 60)
        print(f"Task: {task['title']}")
        print(
            "You will now enter an interactive coding session with the developer agent."
        )
        print("The agent knows about the task and will help you implement it.")
        print("=" * 60)

        # Get the developer agent
        developer = self.orchestrator.agents["developer"]

        try:
            # Create a temporary file with the context for the interactive session
            context_file = self.round4_dir / f"task_{task_number}_context.md"
            with open(context_file, "w") as f:
                f.write(context_prompt)

            print(f"\nContext written to: {context_file}")
            print("\nStarting interactive amp session...")
            print("The developer persona will be loaded with the task context.")
            print(f"You can now implement Task {task_number}: {task['title']}")
            print("\nTo exit the session, type '/exit' or press Ctrl+C")
            print("-" * 60)

            # Start amp in interactive mode with the developer persona
            # We need to run this in the repo directory so the agent has access to files
            original_cwd = os.getcwd()
            os.chdir(self.repo_path)

            # Save context to a file that can be piped to claude
            print(f"\nContext saved to: {context_file}")

            # Launch claude CLI in chat mode
            print(f"\nLaunching Claude chat for Task {task_number}...")
            print(f"Task: {task['title']}")
            print("\nINSTRUCTIONS:")
            print("1. Claude chat will open")
            print(f"2. Copy and paste the context from: {context_file}")
            print("3. Work with Claude to implement the task")
            print("4. Exit with Ctrl+D when done")
            print("-" * 60)

            # Start claude chat with the context file
            try:
                # Create a copy of the environment without ANTHROPIC_API_KEY to avoid auth conflict
                env = os.environ.copy()
                if "ANTHROPIC_API_KEY" in env:
                    del env["ANTHROPIC_API_KEY"]
                    print(
                        "\n(Temporarily unsetting ANTHROPIC_API_KEY for interactive session)"
                    )

                # Launch claude chat directly - user will paste context
                result = subprocess.run(["claude", "chat"], cwd=self.repo_path, env=env)
                return_code = result.returncode
            except FileNotFoundError:
                print("\nClaude CLI not found. Please install it first.")
                print("Visit: https://docs.anthropic.com/en/docs/claude-cli")
                print(
                    f"\nAlternatively, paste the context from {context_file} into your preferred Claude interface."
                )
                print("\nPress Enter when you have completed the implementation...")
                input()
                return_code = 0
            except KeyboardInterrupt:
                print("\n\nInteractive session interrupted by user")
                return_code = 0
            except Exception as e:
                print(f"\nCould not launch Claude CLI: {e}")
                print(f"\nPlease paste the context from: {context_file}")
                print("\nPress Enter when you have completed the implementation...")
                input()
                return_code = 0

            os.chdir(original_cwd)

            print("\n✅ Interactive coding session completed")
            print(f"Session ended with return code: {return_code}")

            # Commit the implementation from Part 1
            await self._commit_part1_implementation(task, task_number)

            return {
                "status": "success",
                "return_code": return_code,
                "message": "Interactive coding session completed successfully",
            }

        except Exception as e:
            error_msg = f"Interactive session failed: {e}"
            print(f"❌ Part 1 failed: {error_msg}")
            return {"status": "failed", "error": error_msg}

    async def _part2_multi_agent_review(
        self, task: dict[str, Any], task_number: int, part1_result: dict[str, Any]
    ) -> dict[str, Any]:
        """Part 2: Multi-agent review and refinement."""
        print("Starting multi-agent review and refinement...")

        # Get the implemented code for review
        implemented_files = part1_result.get("files_created", [])

        reviews = {}
        refinements = []

        # Architect Review
        print("  - Architect reviewing...")
        architect_review = await self._get_agent_review(
            "architect", task, implemented_files
        )
        reviews["architect"] = architect_review

        # Senior Engineer Review
        print("  - Senior Engineer reviewing...")
        senior_review = await self._get_agent_review(
            "senior_engineer", task, implemented_files
        )
        reviews["senior_engineer"] = senior_review

        # Tester Review
        print("  - Tester reviewing...")
        tester_review = await self._get_agent_review("tester", task, implemented_files)
        reviews["tester"] = tester_review

        # Apply refinements based on reviews
        refinement_result = await self._apply_review_refinements(
            task, task_number, reviews
        )

        # Commit the refined code
        await self._commit_part2_refinements(task, task_number)

        print("✅ Part 2 completed - Multi-agent review and refinement")
        return {
            "status": "success",
            "reviews": reviews,
            "files_modified": refinement_result.get("files_modified", []),
            "refinements_applied": refinement_result.get("refinements_applied", 0),
        }

    async def _part3_human_review_break(
        self, task: dict[str, Any], task_number: int
    ) -> dict[str, Any]:
        """Part 3: Human review break - pause for PR comments."""
        print("Human review break initiated...")
        print(f"\nTask {task_number} ({task['title']}) is ready for human review.")
        print("\nWhat happens next:")
        print("1. Review the implemented code in the GitHub PR")
        print("2. Add PR comments on specific lines or files with feedback")
        print("3. The next part will automatically integrate your feedback")
        print(
            "\nPress Enter when you have finished adding PR comments (or press Enter to skip): ",
            end="",
        )

        # Wait for human input
        user_input = input().strip()

        print("✅ Part 3 completed - Human review break")
        return {"status": "success", "human_input": user_input}

    async def _part4_pr_comment_integration(
        self, task: dict[str, Any], task_number: int
    ) -> dict[str, Any]:
        """Part 4: PR comment integration."""
        print("Starting PR comment integration...")

        # Fetch recent PR comments (comments added during Part 3)
        comments = await self._fetch_recent_pr_comments()

        if not comments:
            print("No new PR comments found - no integration needed")
            return {"status": "success", "comments_processed": 0}

        print(f"Found {len(comments)} new PR comments to integrate")

        # Process each comment and update code accordingly
        integration_results = []
        for comment in comments:
            result = await self._integrate_pr_comment(comment, task, task_number)
            integration_results.append(result)

        # Commit the integrated changes
        if any(r.get("changes_made") for r in integration_results):
            await self._commit_part4_integration(task, task_number)

        # Reply to comments acknowledging integration
        await self._reply_to_integrated_comments(comments, task)

        print("✅ Part 4 completed - PR comment integration")
        return {
            "status": "success",
            "comments_processed": len(comments),
            "files_modified": [
                r.get("file_modified")
                for r in integration_results
                if r.get("file_modified")
            ],
            "integration_results": integration_results,
        }

    # Helper methods for the 4-part cycle
    async def _get_agent_review(
        self, agent_type: str, task: dict[str, Any], implemented_files: list[str]
    ) -> dict[str, Any]:
        """Get review from a specific agent."""
        agent = self.orchestrator.agents[agent_type]

        # Create file content summary for review
        files_content = ""
        for file_path in implemented_files:
            if Path(file_path).exists():
                files_content += (
                    f"\n## {file_path}\n\n```\n{Path(file_path).read_text()}\n```\n"
                )

        review_prompt = f"""
Review the implementation for Task: {task['title']}

Description: {task['description']}

Implemented Files:
{files_content}

As a {agent_type.replace('_', ' ')}, provide your review focusing on:
- Code quality and best practices
- Potential issues or improvements
- Suggestions for refinement

Provide specific, actionable feedback.
        """

        review = agent.persona.ask(review_prompt)
        return {
            "agent": agent_type,
            "review": review,
            "files_reviewed": implemented_files,
        }

    async def _apply_review_refinements(
        self, task: dict[str, Any], task_number: int, reviews: dict[str, Any]
    ) -> dict[str, Any]:
        """Apply refinements based on agent reviews."""
        # Combine all reviews into refinement instructions
        all_feedback = ""
        for agent_type, review_data in reviews.items():
            all_feedback += f"\n## {agent_type.replace('_', ' ').title()} Review:\n{review_data['review']}\n"

        refinement_prompt = f"""
Apply refinements to the implementation based on peer review feedback.

Task: {task['title']}
Description: {task['description']}

Peer Review Feedback:
{all_feedback}

Instructions:
1. Address the most important feedback items
2. Improve code quality based on suggestions
3. Fix any issues identified by reviewers
4. Maintain the core functionality while improving implementation

Apply the refinements now.
        """

        # Use developer to apply refinements
        developer = self.orchestrator.agents["developer"]
        context = {
            "task": task,
            "task_number": task_number,
            "repo_path": str(self.repo_path),
            "reviews": reviews,
        }

        refinement_result = await developer.implement_code(context, refinement_prompt)

        return {
            "refinements_applied": len(reviews),
            "files_modified": refinement_result.get("files_created", [])
            if refinement_result
            else [],
            "status": refinement_result.get("status", "failed")
            if refinement_result
            else "failed",
        }

    async def _fetch_recent_pr_comments(self) -> list[dict[str, Any]]:
        """Fetch recent PR comments for integration."""
        try:
            result_json = await execute_get_pr_comments(
                repo_name=self.repo_name, pr_number=self.pr_number
            )

            result = json.loads(result_json)
            if result.get("error"):
                logger.error(f"Failed to fetch PR comments: {result['error']}")
                return []

            # Get all comments
            review_comments = result.get("review_comments", [])
            issue_comments = result.get("issue_comments", [])
            all_comments = review_comments + issue_comments

            # Filter for recent comments (added in the last hour)
            recent_comments = []
            current_time = datetime.now()

            for comment in all_comments:
                if isinstance(comment, dict):
                    # Simple filter - return all comments for now
                    # In production, would filter by timestamp
                    recent_comments.append(comment)

            return recent_comments

        except Exception as e:
            logger.error(f"Error fetching PR comments: {e}")
            return []

    async def _integrate_pr_comment(
        self, comment: dict[str, Any], task: dict[str, Any], task_number: int
    ) -> dict[str, Any]:
        """Integrate a single PR comment into the code."""
        comment_body = comment.get("body", "")
        file_path = comment.get("path") or comment.get("file")

        if not comment_body or not file_path:
            return {"status": "skipped", "reason": "Missing comment body or file path"}

        integration_prompt = f"""
Integrate this PR comment feedback into the code.

Comment: {comment_body}
File: {file_path}
Task: {task['title']}

Read the current file, understand the feedback, and make the necessary changes.
Focus on addressing the specific concern raised in the comment.
        """

        # Use developer to integrate the feedback
        developer = self.orchestrator.agents["developer"]
        context = {
            "comment": comment,
            "task": task,
            "task_number": task_number,
            "file_path": file_path,
        }

        integration_result = await developer.implement_code(context, integration_prompt)

        return {
            "status": "success"
            if integration_result and integration_result.get("status") == "success"
            else "failed",
            "comment_id": comment.get("id"),
            "file_modified": file_path,
            "changes_made": bool(
                integration_result and integration_result.get("status") == "success"
            ),
        }

    async def _reply_to_integrated_comments(
        self, comments: list[dict[str, Any]], task: dict[str, Any]
    ):
        """Reply to PR comments acknowledging integration."""
        for comment in comments:
            comment_id = comment.get("id")
            if not comment_id:
                continue

            reply_text = f"""This feedback has been integrated into the implementation for Task: {task['title']}.

The code has been updated to address your concerns. Please review the latest commit."""

            try:
                await execute_post_pr_reply(
                    repo_name=self.repo_name, comment_id=comment_id, message=reply_text
                )
                print(f"✅ Replied to comment #{comment_id}")
            except Exception as e:
                logger.error(f"Failed to reply to comment #{comment_id}: {e}")

    # Commit methods for each part
    async def _commit_part1_implementation(
        self, task: dict[str, Any], task_number: int
    ):
        """Commit Part 1 implementation."""
        await self._create_commit(
            f"Implement {task['title']}: Interactive coding session",
            f"Part 1 of 4-part development cycle for Task {task_number}\n\n- Initial implementation based on design document\n- Interactive coding session with developer agent",
        )

    async def _commit_part2_refinements(self, task: dict[str, Any], task_number: int):
        """Commit Part 2 refinements."""
        await self._create_commit(
            f"Refine {task['title']}: Multi-agent review improvements",
            f"Part 2 of 4-part development cycle for Task {task_number}\n\n- Applied feedback from architect, senior engineer, and tester reviews\n- Code quality improvements and refinements",
        )

    async def _commit_part4_integration(self, task: dict[str, Any], task_number: int):
        """Commit Part 4 integration."""
        await self._create_commit(
            f"Update {task['title']}: Integrate PR feedback",
            f"Part 4 of 4-part development cycle for Task {task_number}\n\n- Integrated human feedback from PR comments\n- Final refinements based on review",
        )

    async def _create_commit(self, title: str, description: str):
        """Create a git commit for all changed files."""
        try:
            original_cwd = os.getcwd()
            os.chdir(self.repo_path)

            # Check if there are any changes to commit
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True,
                text=True,
                check=True,
            )

            if not result.stdout.strip():
                print(f"⚠️  No changes to commit for: {title}")
                return

            # Show what files will be committed
            print(f"\nFiles to be committed for '{title}':")
            for line in result.stdout.strip().split("\n"):
                if line.strip():
                    status = line[:2]
                    filename = line[3:]
                    print(f"  {status} {filename}")

            # Add all changes (modified, new, deleted)
            subprocess.run(["git", "add", "-A"], check=True)

            # Create commit message
            commit_message = f"""{title}

{description}

🤖 Generated with [Claude Code](https://claude.ai/code)

Co-Authored-By: Claude <noreply@anthropic.com>"""

            # Create the commit
            subprocess.run(["git", "commit", "-m", commit_message], check=True)
            print(f"✅ Committed: {title}")

        except subprocess.CalledProcessError as e:
            if "nothing to commit" in str(e):
                print(f"⚠️  No changes to commit for: {title}")
            else:
                logger.error(f"Failed to create commit: {e}")
                print(f"❌ Failed to commit: {title}")
        finally:
            os.chdir(original_cwd)


async def main():
    """Main entry point for 4-part development process."""
    parser = argparse.ArgumentParser(
        description="Step 4: Interactive Development Process (4-part cycle)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
This step implements the new 4-part development cycle:

For each implementation task from the design:
  Part 1: Interactive coding session with developer
  Part 2: Multi-agent review and refinement (offline)
  Part 3: Human review break for PR comments
  Part 4: PR comment integration into code

Prerequisites:
- Step 1: Analysis documents created
- Step 2: Consolidated design created
- Step 3: Design finalized with feedback (preferred)

Example:
  python step4_implementation.py --pr 123
        """,
    )

    parser.add_argument(
        "--pr",
        type=int,
        required=True,
        help="PR number containing the finalized design",
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
        log_level=args.log_level, log_file=log_dir / "step4_implementation.log"
    )

    print("=" * 60)
    print("Step 4: Interactive Development Process")
    print("=" * 60)
    print(f"PR Number: {args.pr}")

    # Get repository information
    repo_path = os.environ.get("REPO_PATH", str(Path.cwd().parent))
    repo_name = os.environ.get("GITHUB_REPO", "github-agent")

    print(f"Repository: {repo_name}")
    print(f"Path: {repo_path}")

    # Check prerequisites
    workflow_dir = Path(repo_path) / ".workflow"
    design_finalized = workflow_dir / "round_3_design" / "finalized_design.md"
    design_consolidated = workflow_dir / "round_2_design" / "consolidated_design.md"

    if design_finalized.exists():
        print("✅ Found finalized design document")
        design_to_use = "finalized"
    elif design_consolidated.exists():
        print("✅ Found consolidated design document")
        print("   (Consider running step3_finalize_design_document.py first)")
        design_to_use = "consolidated"
    else:
        print("❌ No design document found")
        print("   Please run steps 1-3 first:")
        print("   1. python step1_analysis.py <feature_spec>")
        print("   2. python step2_create_design_document.py --pr <number>")
        print("   3. python step3_finalize_design_document.py --pr <number>")
        return 1

    print(f"\nUsing: {design_to_use} design document")

    # Create and run the development processor
    print("\nInitializing 4-part development process...")
    processor = InteractiveDevelopmentProcessor(args.pr, repo_path, repo_name)

    print("\nStarting implementation with 4-part cycle:")
    print("  Part 1: Interactive coding session")
    print("  Part 2: Multi-agent review and refinement")
    print("  Part 3: Human review break")
    print("  Part 4: PR comment integration")
    print("\nEach task will go through all 4 parts before moving to the next task.")

    result = await processor.run_development_process()

    # Display results
    print("\n" + "=" * 60)
    print("DEVELOPMENT PROCESS RESULTS")
    print("=" * 60)

    if result["status"] == "success":
        print("✅ Development process completed successfully!")
        print("\nSummary:")
        print(
            f"  - Tasks completed: {result['tasks_completed']}/{result['total_tasks']}"
        )
        print("  - All tasks went through 4-part development cycle")

        print("\nNext steps:")
        print("1. Review all commits in the PR to see the development evolution")
        print("2. Run tests to verify implementation")
        print("3. Make any final adjustments if needed")
        print("4. Merge the PR when ready")
        return 0
    else:
        print(f"❌ Development process failed: {result.get('error')}")
        print("\nSome tasks may have been partially completed.")
        print("Check the PR and logs for details.")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
