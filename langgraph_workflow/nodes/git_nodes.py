"""GitHub and Git operations using existing MCP integration."""

import logging
import subprocess
import sys
from pathlib import Path

# Add parent directories for imports
sys.path.append(str(Path(__file__).parent.parent.parent))

from langgraph_workflow.state import WorkflowState

logger = logging.getLogger(__name__)


class GitNodes:
    """GitHub operations using existing github_tools.py MCP integration."""

    def __init__(self, repo_name: str, repo_path: str):
        """Initialize Git nodes with repository context."""
        self.repo_name = repo_name
        self.repo_path = Path(repo_path)

    async def initialize_git(self, state: WorkflowState) -> dict:
        """Initialize Git branch and worktree for the workflow."""
        logger.info("Initializing Git branch for workflow")

        try:
            # Create feature branch based on thread ID
            branch_name = f"feature/{state['thread_id']}"
            state["git_branch"] = branch_name

            # Change to repo directory
            original_cwd = Path.cwd()
            os.chdir(self.repo_path)

            try:
                # Create and checkout new branch
                subprocess.run(
                    ["git", "checkout", "-b", branch_name],
                    check=True,
                    capture_output=True,
                )

                # Get initial commit SHA
                result = subprocess.run(
                    ["git", "rev-parse", "HEAD"],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                state["last_commit_sha"] = result.stdout.strip()

                logger.info(f"Created branch {branch_name}")

            finally:
                os.chdir(original_cwd)

            state["messages_window"].append(
                {"role": "git", "content": f"Initialized branch {branch_name}"}
            )

        except subprocess.CalledProcessError as e:
            logger.error(f"Git initialization failed: {e}")
            state["messages_window"].append(
                {
                    "role": "system",
                    "content": f"Git initialization failed: {e!s}",
                    "error": True,
                }
            )

        return state

    async def commit_changes(self, state: WorkflowState, message: str = None) -> dict:
        """Commit changes to the current branch."""
        logger.info("Committing changes")

        if not message:
            message = f"Progress update for {state['thread_id']}"

        try:
            import os

            original_cwd = Path.cwd()
            os.chdir(self.repo_path)

            try:
                # Stage all changes
                subprocess.run(["git", "add", "."], check=True)

                # Check if there are changes to commit
                result = subprocess.run(["git", "diff", "--staged", "--quiet"])

                if result.returncode != 0:  # There are changes
                    # Create commit
                    full_message = f"""{message}

🤖 Generated with [Claude Code](https://claude.ai/code)

Co-Authored-By: Claude <noreply@anthropic.com>"""

                    subprocess.run(["git", "commit", "-m", full_message], check=True)

                    # Update commit SHA
                    result = subprocess.run(
                        ["git", "rev-parse", "HEAD"],
                        check=True,
                        capture_output=True,
                        text=True,
                    )
                    state["last_commit_sha"] = result.stdout.strip()

                    logger.info("Changes committed successfully")

                    state["messages_window"].append(
                        {"role": "git", "content": f"Committed changes: {message}"}
                    )
                else:
                    logger.info("No changes to commit")

            finally:
                os.chdir(original_cwd)

        except subprocess.CalledProcessError as e:
            logger.error(f"Git commit failed: {e}")
            state["messages_window"].append(
                {
                    "role": "system",
                    "content": f"Git commit failed: {e!s}",
                    "error": True,
                }
            )

        return state

    async def push_branch_and_pr(self, state: WorkflowState) -> dict:
        """Push branch and create/update PR using MCP tools."""
        logger.info("Pushing branch and creating PR")

        try:
            # Import github_tools here to avoid circular imports

            # Push current branch
            import os

            original_cwd = Path.cwd()
            os.chdir(self.repo_path)

            try:
                # Push with upstream
                subprocess.run(
                    ["git", "push", "--set-upstream", "origin", state["git_branch"]],
                    check=True,
                )

                logger.info(f"Pushed branch {state['git_branch']}")

            finally:
                os.chdir(original_cwd)

            # Create PR if not already created
            if not state.get("pr_number"):
                pr_title = f"Implementation: {state['feature_name']}"
                pr_body = self._create_pr_body(state)

                # Use GitHub CLI to create PR
                result = subprocess.run(
                    ["gh", "pr", "create", "--title", pr_title, "--body", pr_body],
                    cwd=self.repo_path,
                    capture_output=True,
                    text=True,
                    check=True,
                )

                # Extract PR number from URL
                pr_url = result.stdout.strip()
                pr_number = int(pr_url.split("/")[-1])

                state["pr_number"] = pr_number

                logger.info(f"Created PR #{pr_number}: {pr_url}")

                state["messages_window"].append(
                    {"role": "github", "content": f"Created PR #{pr_number}"}
                )
            else:
                logger.info(f"PR #{state['pr_number']} already exists")

        except Exception as e:
            logger.error(f"Push/PR creation failed: {e}")
            state["messages_window"].append(
                {"role": "system", "content": f"Push/PR failed: {e!s}", "error": True}
            )

        return state

    async def fetch_pr_comments(self, state: WorkflowState) -> dict:
        """Fetch PR comments using MCP tools."""
        logger.info("Fetching PR comments")

        pr_number = state.get("pr_number")
        if not pr_number:
            logger.warning("No PR number available for comment fetching")
            return state

        try:
            # Import MCP GitHub tools
            import github_tools

            # Use the existing MCP function
            comments_json = await github_tools.execute_get_pr_comments(
                repo_name=self.repo_name, pr_number=pr_number
            )

            # Parse comments
            import json

            if isinstance(comments_json, str):
                comments_data = json.loads(comments_json)
            else:
                comments_data = comments_json

            if comments_data.get("error"):
                logger.error(f"Failed to fetch PR comments: {comments_data['error']}")
                return state

            # Combine review and issue comments
            review_comments = comments_data.get("review_comments", [])
            issue_comments = comments_data.get("issue_comments", [])
            all_comments = review_comments + issue_comments

            # Filter for new comments (not already addressed)
            new_comments = []
            for comment in all_comments:
                comment_id = str(comment.get("id", ""))
                if not state["feedback_addressed"].get(comment_id, False):
                    new_comments.append(comment)

            state["pr_comments"] = new_comments

            logger.info(f"Fetched {len(new_comments)} new PR comments")

            state["messages_window"].append(
                {
                    "role": "github",
                    "content": f"Fetched {len(new_comments)} new comments",
                }
            )

        except Exception as e:
            logger.error(f"PR comment fetching failed: {e}")
            state["messages_window"].append(
                {
                    "role": "system",
                    "content": f"PR comment fetch failed: {e!s}",
                    "error": True,
                }
            )

        return state

    async def post_pr_reply(
        self, state: WorkflowState, comment_id: int, message: str
    ) -> dict:
        """Post reply to a specific PR comment."""
        logger.info(f"Posting reply to comment {comment_id}")

        try:
            # Import MCP GitHub tools
            import github_tools

            # Post reply using MCP function
            await github_tools.execute_post_pr_reply(
                repo_name=self.repo_name, comment_id=comment_id, message=message
            )

            logger.info(f"Posted reply to comment {comment_id}")

        except Exception as e:
            logger.error(f"PR reply posting failed: {e}")

        return state

    def _create_pr_body(self, state: WorkflowState) -> str:
        """Create PR body based on workflow state."""
        phase = state.get("current_phase", "unknown")

        body = f"""## Multi-Agent Workflow Implementation

**Phase**: {phase.value if hasattr(phase, 'value') else phase}
**Feature**: {state.get('feature_name', 'Unknown')}

### Process Used
- Multi-agent analysis with Architect, Developer, Senior Engineer, and Tester
- Design consolidation with conflict resolution
- LangGraph-based stateful workflow with checkpointing

### Artifacts Created
"""

        # Add artifact links
        for artifact_name, artifact_path in state.get("artifacts_index", {}).items():
            body += f"- [{artifact_name}]({artifact_path})\n"

        body += f"""
### Current Status
- Phase: {phase}
- Quality State: {state.get('quality_state', 'unknown')}
- Tests: {'Passing' if state.get('test_results', {}).get('passed') else 'In Progress'}

Generated using LangGraph Multi-Agent Workflow
"""

        return body
