#!/usr/bin/env python3
"""
Step 3: Finalize Design Document with GitHub Feedback
Reads GitHub PR comments on the design document and updates it to address feedback.

Usage:
    python step3_finalize_design_document.py --pr PR_NUMBER
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from common_utils import add_common_arguments, print_step_header, setup_common_environment
from task_context import TaskContext
from workflow_orchestrator import WorkflowOrchestrator

logger = logging.getLogger(__name__)


class DesignFinalizer:
    """Handles design document finalization with GitHub feedback integration."""

    def __init__(
        self, orchestrator: WorkflowOrchestrator, context: TaskContext, pr_number: int
    ):
        self.orchestrator = orchestrator
        self.context = context
        self.pr_number = pr_number
        self.repo_name = orchestrator.repo_name

    async def get_design_feedback(self) -> list[dict[str, Any]]:
        """Fetch GitHub comments related to the design document."""
        logger.info(f"Fetching PR comments for {self.repo_name} PR #{self.pr_number}")

        try:
            # Get all PR comments using the direct method
            from github_tools import execute_get_pr_comments

            result_json = await execute_get_pr_comments(
                repo_name=self.repo_name, pr_number=self.pr_number
            )

            # Parse the JSON response
            result = json.loads(result_json)

            if result.get("error"):
                logger.error(f"Failed to fetch PR comments: {result['error']}")
                return []

            # Extract comments from the correct fields in the result
            review_comments = result.get("review_comments", [])
            issue_comments = result.get("issue_comments", [])
            comments = review_comments + issue_comments

            logger.info(
                f"Parsed JSON result: review_comments={len(review_comments)}, issue_comments={len(issue_comments)}, total={len(comments)}"
            )

            # Debug: Show result structure if no comments found
            if not comments and result:
                logger.warning(
                    f"No comments found in result. Result keys: {list(result.keys())}"
                )
                logger.warning(f"Result structure: {str(result)[:500]}...")

            # Debug: check what we actually got
            logger.info(
                f"Raw comments result: {type(comments)}, length: {len(comments)}"
            )
            if comments:
                logger.info(f"First comment type: {type(comments[0])}")
                logger.info(f"First comment preview: {str(comments[0])[:200]}...")

            # Filter for comments on the consolidated design document only
            design_comments = []
            target_file = ".workflow/round_2_design/consolidated_design.md"

            for i, comment in enumerate(comments):
                # Handle case where comment might be a string or dict
                if isinstance(comment, str):
                    logger.warning(
                        f"Got string comment instead of dict: {comment[:100]}..."
                    )
                    # Skip string comments as we can't process them properly
                    continue
                elif not isinstance(comment, dict):
                    logger.warning(f"Got unexpected comment type: {type(comment)}")
                    continue

                # Debug: log each comment to understand what we're getting
                comment_path = comment.get("path", "") or comment.get(
                    "file", ""
                )  # Try both 'path' and 'file'
                comment_body = comment.get("body", "")[:100]
                comment_id = comment.get("id", "unknown")
                logger.info(
                    f"Comment {i} (id={comment_id}): path='{comment_path}', body='{comment_body}...'"
                )

                # Only include comments on the consolidated design document
                if comment_path == target_file:
                    design_comments.append(comment)
                    logger.info("  -> INCLUDED (comment on consolidated_design.md)")
                else:
                    logger.info(
                        f"  -> EXCLUDED (comment on different file: '{comment_path}')"
                    )

            logger.info(f"Found {len(design_comments)} design-related comments")
            return design_comments

        except Exception as e:
            logger.error(f"Error fetching GitHub comments: {e}")
            # Return empty list on error
            return []

    async def analyze_feedback(
        self, comments: list[dict[str, Any]]
    ) -> dict[str, list[Any]]:
        """Categorize and analyze feedback comments."""
        feedback_categories: dict[str, list[Any]] = {
            "architecture": [],
            "implementation": [],
            "testing": [],
            "security": [],
            "performance": [],
            "general": [],
        }

        for comment in comments:
            # Get comment body
            body = comment.get("body", "").lower()

            # Categorize based on content
            if any(
                word in body for word in ["architecture", "design pattern", "structure"]
            ):
                feedback_categories["architecture"].append(comment)
            elif any(word in body for word in ["implement", "code", "api"]):
                feedback_categories["implementation"].append(comment)
            elif any(word in body for word in ["test", "coverage", "qa"]):
                feedback_categories["testing"].append(comment)
            elif any(word in body for word in ["security", "auth", "permission"]):
                feedback_categories["security"].append(comment)
            elif any(word in body for word in ["performance", "scale", "optimize"]):
                feedback_categories["performance"].append(comment)
            else:
                feedback_categories["general"].append(comment)

        return feedback_categories

    async def update_design_document(
        self, feedback_categories: dict[str, list[Any]]
    ) -> bool:
        """Update the design document based on categorized feedback."""
        design_path = (
            Path(self.orchestrator.repo_path)
            / ".workflow"
            / "round_2_design"
            / "consolidated_design.md"
        )

        if not design_path.exists():
            logger.error(f"Design document not found: {design_path}")
            return False

        # Create prompt for design update
        feedback_summary = self._create_feedback_summary(feedback_categories)

        if not feedback_summary:
            logger.info("No feedback to incorporate")
            return True

        # First, read the current design document
        current_design = design_path.read_text()

        update_prompt = f"""
## Task: Update the Complete Design Document Based on PR Feedback

You need to produce a COMPLETE, UPDATED design document that incorporates the GitHub PR feedback.

## Current Design Document

{current_design}

## GitHub Feedback to Address

{feedback_summary}

## Instructions

1. Start with the ENTIRE current design document above
2. For each piece of feedback, update the relevant sections to address the concerns
3. Keep ALL existing content that doesn't need changes
4. Return the COMPLETE updated design document (not just the changes)

## Important Guidelines
- This should be a COMPLETE design document, not a list of changes
- Maintain the same structure and format as the original
- Update only the sections that need changes based on feedback
- Keep all other sections intact
- Do NOT create a "changes made" document - create the full updated design
- Be specific: Reference actual classes, methods, and patterns from the codebase
- All architectural decisions must align with the codebase analysis
"""

        # Use developer agent to update the design (better at generating complete documents)
        developer = self.orchestrator.agents["developer"]

        # Create context for the developer
        dev_context = {
            "prompt": update_prompt,
            "pr_number": self.pr_number,
            "design_path": str(design_path),
            "feedback_summary": feedback_summary,
        }

        # Use implement_code to generate the updated document
        result = await developer.implement_code(dev_context, update_prompt)
        updated_design = result.get("content", "")

        if updated_design:
            # Create round_3_design directory
            round3_dir = (
                Path(self.orchestrator.repo_path) / ".workflow" / "round_3_design"
            )
            round3_dir.mkdir(parents=True, exist_ok=True)

            # Save the updated design in round_3_design
            finalized_path = round3_dir / "finalized_design.md"
            with open(finalized_path, "w") as f:
                f.write(updated_design)

            logger.info(f"Created finalized design: {finalized_path}")

            # Create a feedback incorporation summary
            feedback_summary_path = round3_dir / "feedback_incorporation_summary.md"
            await self._create_feedback_summary_document(
                feedback_summary_path,
                feedback_categories,
                current_design,
                updated_design,
            )

            # Reply to comments to acknowledge feedback
            await self._reply_to_comments(feedback_categories)

            # Commit the finalized design documents
            await self._commit_design_documents(round3_dir)

            return True

        return False

    async def _reply_to_comments(
        self, feedback_categories: dict[str, list[Any]]
    ) -> None:
        """Reply to GitHub comments to acknowledge feedback has been addressed."""
        logger.info("Replying to GitHub comments to acknowledge feedback...")

        # Collect all comments from all categories
        all_comments = []
        for _, comments in feedback_categories.items():
            all_comments.extend(comments)

        # Filter out bot comments
        human_comments = [
            c
            for c in all_comments
            if isinstance(c, dict)
            and not any(
                bot in c.get("author", "").lower()
                for bot in ["bot", "codecov", "github-actions"]
            )
        ]

        if not human_comments:
            logger.info("No human comments to reply to")
            return

        # For each comment, generate and post a reply
        for comment in human_comments:
            comment_id = comment.get("id")
            author = comment.get("author", "Unknown")
            body = comment.get("body", "")

            if not comment_id:
                logger.warning(f"Skipping comment without ID from {author}")
                continue

            # Generate a reply based on the feedback
            reply_prompt = f"""Based on the PR comment below, write a professional reply explaining how this feedback was addressed in the finalized design document.

PR Comment by {author}:
"{body[:500]}..."

Write a concise reply (2-4 sentences) that:
1. Briefly acknowledges the point
2. Explains how it was incorporated into the finalized design
3. References that the update is in consolidated_design_final.md

Keep the tone professional but direct. Avoid excessive politeness or thanking."""

            # Use architect agent to generate the reply
            architect = self.orchestrator.agents.get("architect")
            if architect:
                reply_response = architect.persona.ask(reply_prompt)

                if reply_response and len(reply_response.strip()) > 10:
                    # Post the reply
                    comment_body = f"""{reply_response}

---
*The feedback has been incorporated into the [finalized design document](.workflow/round_3_design/finalized_design.md).*"""

                    try:
                        from github_tools import execute_post_pr_reply

                        await execute_post_pr_reply(
                            repo_name=self.repo_name,
                            comment_id=comment_id,
                            message=comment_body,
                        )
                        logger.info(f"Posted reply to comment #{comment_id}")
                        print(f"✅ Replied to comment from {author}")

                    except Exception as e:
                        logger.error(
                            f"Failed to post reply to comment #{comment_id}: {e}"
                        )
                        print(f"⚠️  Failed to reply to comment from {author}: {e}")
                else:
                    logger.warning(f"Generated empty reply for comment #{comment_id}")
            else:
                logger.error("Architect agent not available for reply generation")

        logger.info("Finished replying to comments")

    async def _create_feedback_summary_document(
        self,
        output_path: Path,
        feedback_categories: dict[str, list[Any]],
        original_design: str,
        updated_design: str,
    ) -> None:
        """Create a document summarizing how feedback was incorporated."""

        # Create a prompt to identify what changed
        change_prompt = f"""Compare the original and updated design documents and create a summary of changes.

List the specific changes made to address each piece of feedback. Be concrete about what sections were updated and how.

Original design length: {len(original_design)} chars
Updated design length: {len(updated_design)} chars

Feedback that was addressed:
{self._create_feedback_summary(feedback_categories)}

Create a summary document that lists:
1. Each feedback item
2. What specific changes were made to address it
3. Which sections of the design were updated

Keep it concise and focused on the actual changes made."""

        # Use architect to summarize changes
        architect = self.orchestrator.agents.get("architect")
        if architect:
            summary_content = architect.persona.ask(change_prompt)

            # Create the summary document
            with open(output_path, "w") as f:
                f.write(
                    f"""# Feedback Incorporation Summary

**Date**: {datetime.now().isoformat()}
**PR**: #{self.pr_number}

## Overview

This document summarizes how GitHub PR feedback was incorporated into the finalized design.

## Feedback Addressed

{summary_content}

## Documents

- Original design: `.workflow/round_2_design/consolidated_design.md`
- Updated design: `.workflow/round_3_design/finalized_design.md`
"""
                )

            logger.info(f"Created feedback summary: {output_path}")

    async def _commit_design_documents(self, round3_dir: Path) -> None:
        """Commit the finalized design documents to git."""
        try:
            import subprocess

            # Change to repo directory
            original_cwd = os.getcwd()
            os.chdir(self.orchestrator.repo_path)

            # Add the round 3 design files
            subprocess.run(
                ["git", "add", str(round3_dir / "finalized_design.md")], check=True
            )
            subprocess.run(
                ["git", "add", str(round3_dir / "feedback_incorporation_summary.md")],
                check=True,
            )

            # Create commit message
            commit_message = f"""Finalize design document based on PR feedback

- Updated design to address PR #{self.pr_number} review comments
- Created feedback incorporation summary
- Ready for implementation phase

🤖 Generated with [Claude Code](https://claude.ai/code)

Co-Authored-By: Claude <noreply@anthropic.com>"""

            # Commit the changes
            subprocess.run(["git", "commit", "-m", commit_message], check=True)

            logger.info("Successfully committed finalized design documents")
            print("\n✅ Committed finalized design documents to git")
            print("Remember to push the changes to update the PR")

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to commit design documents: {e}")
            print(f"\n⚠️  Failed to commit design documents: {e}")
            print("You may need to commit them manually")
        finally:
            # Return to original directory
            os.chdir(original_cwd)

    def _create_feedback_summary(
        self, feedback_categories: dict[str, list[Any]]
    ) -> str:
        """Create a summary of feedback organized by category."""
        summary_parts = []

        for category, comments in feedback_categories.items():
            if comments:
                summary_parts.append(f"### {category.title()} Feedback\n")
                for comment in comments:
                    # Handle case where comment might not be a dict
                    if isinstance(comment, dict):
                        author = comment.get("user", {}).get("login", "Unknown")
                        body = comment.get("body", "")
                    else:
                        author = "Unknown"
                        body = str(comment)
                    summary_parts.append(f"- **{author}**: {body}\n")
                summary_parts.append("")

        return "\n".join(summary_parts)


async def main():
    """Run Step 3: Finalize design document with GitHub feedback."""

    parser = argparse.ArgumentParser(
        description="Step 3: Finalize design document with GitHub feedback",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
This step:
1. Reads GitHub PR comments on the design document
2. Analyzes and categorizes the feedback
3. Updates the design document to address all feedback
4. Creates a finalized version ready for implementation

Example:
  python step3_finalize_design_document.py --pr 123
        """,
    )

    parser.add_argument(
        "--pr",
        type=int,
        required=True,
        help="PR number containing the design document and feedback",
    )
    add_common_arguments(parser)

    args = parser.parse_args()

    # Setup common environment
    env = setup_common_environment("step3_finalize", args)
    repo_path = env["repo_path"]
    repo_name = env["repo_name"]

    print_step_header(
        "Step 3",
        "Finalize Design Document",
        repository=repo_name,
        pr_number=args.pr
    )

    # Create orchestrator
    orchestrator = WorkflowOrchestrator(repo_name, repo_path)

    # Load existing context
    print("\nLoading design context...")
    # Use absolute path based on repo_path to avoid working directory issues
    context_file = Path(repo_path) / ".workflow" / f"context_pr_{args.pr}.json"

    if not context_file.exists():
        print(f"❌ Context file not found: {context_file}")
        print("Please run step1_analysis.py and step2_create_design_document.py first")
        return 1

    context = TaskContext.load_from_file(str(context_file))
    context.set_pr_number(args.pr)

    # Check if design document exists
    design_path = (
        Path(repo_path) / ".workflow" / "round_2_design" / "consolidated_design.md"
    )
    if not design_path.exists():
        print(f"❌ Design document not found: {design_path}")
        print("Please run step2_create_design_document.py first")
        return 1

    print(f"✅ Found design document for: {context.feature_spec.name}")

    # Create finalizer
    finalizer = DesignFinalizer(orchestrator, context, args.pr)

    # Fetch and analyze feedback
    print("\nFetching GitHub PR comments...")
    comments = await finalizer.get_design_feedback()

    # Check for error (None return) vs no comments (empty list)
    if comments is None:
        print("❌ Failed to fetch GitHub PR comments due to an error.")
        print("Please check the logs and try again.")
        return 1

    if not comments:
        print("No design feedback found in PR comments.")
        print("\nOptions:")
        print("1. Add feedback as PR comments on GitHub")
        print("2. Proceed without feedback (design is already final)")
        print("\nProceed without feedback? (y/N): ", end="")
        response = input().strip().lower()
        if response == "y":
            print("\nDesign document is ready for implementation.")
            print(
                f"Run 'python step4_implementation.py --pr {args.pr}' to start implementation"
            )
            return 0
        else:
            print("Please add feedback via GitHub PR comments and run this step again.")
            return 0

    print(f"Found {len(comments)} design-related comments")

    # Categorize feedback
    print("\nAnalyzing feedback...")
    feedback_categories = await finalizer.analyze_feedback(comments)

    # Display feedback summary
    print("\nFeedback summary:")
    for category, items in feedback_categories.items():
        if items:
            print(f"  - {category.title()}: {len(items)} comments")

    # Update design document
    print("\nUpdating design document with feedback...")
    success = await finalizer.update_design_document(feedback_categories)

    if success:
        print("\n✅ Design document finalized successfully!")
        print("\nDocuments created:")
        print(
            f"  - {repo_path}/.workflow/round_3_design/finalized_design.md (complete updated design)"
        )
        print(
            f"  - {repo_path}/.workflow/round_3_design/feedback_incorporation_summary.md (summary of changes)"
        )
        print("\nNext steps:")
        print("1. Review the finalized design document")
        print("2. Commit and push the updated design to the PR")
        print(
            f"3. Run 'python step4_implementation.py --pr {args.pr}' to start implementation"
        )
        return 0
    else:
        print("❌ Failed to finalize design document")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
