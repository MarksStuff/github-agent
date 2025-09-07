#!/usr/bin/env python3
"""
GitHub Integration Module for Enhanced Multi-Agent Workflow System

Provides GitHub-specific operations including:
- Enhanced commit message generation with conventional commits
- Pull request creation and management
- Comment polling and parsing
- Webhook listener for real-time updates
- Feedback incorporation from GitHub discussions
"""

import logging
import re
import subprocess
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Optional

import requests

try:
    from .git_integrator import GitIntegrator
    from .workflow_state import StageStatus, WorkflowState
except ImportError:
    from git_integrator import GitIntegrator
    from workflow_state import StageStatus, WorkflowState

logger = logging.getLogger(__name__)


@dataclass
class GitHubComment:
    """Represents a GitHub comment."""

    id: int
    author: str
    body: str
    created_at: datetime
    updated_at: datetime
    url: str
    is_reply: bool = False
    parent_comment_id: Optional[int] = None
    workflow_commands: list[str] = field(default_factory=list)

    def parse_workflow_commands(self) -> list[str]:
        """Parse workflow commands from comment body."""
        commands = []

        # Look for workflow commands like: @workflow pause, @workflow resume stage_name
        workflow_pattern = r"@workflow\s+(\w+)(?:\s+(\w+))?"
        matches = re.findall(workflow_pattern, self.body.lower())

        for match in matches:
            command = match[0]
            arg = match[1] if match[1] else None
            if arg:
                commands.append(f"{command} {arg}")
            else:
                commands.append(command)

        # Look for approval/rejection commands
        if re.search(r"\b(approve|approved|lgtm|looks good)\b", self.body.lower()):
            commands.append("approve")
        elif re.search(
            r"\b(reject|rejected|needs work|changes requested)\b", self.body.lower()
        ):
            commands.append("reject")

        self.workflow_commands = commands
        return commands


@dataclass
class PullRequest:
    """Represents a GitHub Pull Request."""

    number: int
    title: str
    body: str
    state: str
    author: str
    branch: str
    target_branch: str
    url: str
    created_at: datetime
    updated_at: datetime
    mergeable: bool = True
    comments_count: int = 0
    workflow_id: Optional[str] = None

    @classmethod
    def from_github_api(cls, pr_data: dict) -> "PullRequest":
        """Create PullRequest from GitHub API response."""
        return cls(
            number=pr_data["number"],
            title=pr_data["title"],
            body=pr_data["body"] or "",
            state=pr_data["state"],
            author=pr_data["user"]["login"],
            branch=pr_data["head"]["ref"],
            target_branch=pr_data["base"]["ref"],
            url=pr_data["html_url"],
            created_at=datetime.fromisoformat(
                pr_data["created_at"].replace("Z", "+00:00")
            ),
            updated_at=datetime.fromisoformat(
                pr_data["updated_at"].replace("Z", "+00:00")
            ),
            mergeable=pr_data.get("mergeable", True),
            comments_count=pr_data.get("comments", 0),
        )


@dataclass
class WorkflowFeedback:
    """Represents feedback from GitHub for workflow processing."""

    pr_number: int
    comment_id: int
    author: str
    feedback_type: str  # 'approve', 'reject', 'pause', 'resume', 'modify'
    message: str
    stage_name: Optional[str] = None
    requested_changes: dict[str, Any] = field(default_factory=dict)
    processed: bool = False
    processed_at: Optional[datetime] = None


class ConventionalCommitGenerator:
    """Generates conventional commit messages."""

    # Conventional commit types
    COMMIT_TYPES = {
        "requirements_analysis": "feat",
        "architecture_design": "feat",
        "implementation_planning": "feat",
        "code_implementation": "feat",
        "testing": "test",
        "documentation": "docs",
        "deployment": "ci",
    }

    # Stage descriptions for better commit messages
    STAGE_DESCRIPTIONS = {
        "requirements_analysis": "analyze project requirements and define scope",
        "architecture_design": "design system architecture and components",
        "implementation_planning": "create implementation plan and task breakdown",
        "code_implementation": "implement core functionality and features",
        "testing": "add comprehensive test coverage",
        "documentation": "create project documentation",
        "deployment": "prepare deployment configuration",
    }

    @classmethod
    def generate_commit_message(
        cls,
        stage_name: str,
        result: dict[str, Any],
        state: WorkflowState,
        include_breaking_changes: bool = False,
    ) -> str:
        """Generate a conventional commit message."""
        commit_type = cls.COMMIT_TYPES.get(stage_name, "feat")
        stage_desc = cls.STAGE_DESCRIPTIONS.get(
            stage_name, stage_name.replace("_", " ")
        )

        # Create scope from project context
        scope = cls._extract_scope_from_state(state)
        scope_str = f"({scope})" if scope else ""

        # Create main commit message
        summary = f"{commit_type}{scope_str}: {stage_desc}"

        # Add detailed body
        body_lines = []

        # Add stage completion details
        if result.get("output_files"):
            files = result["output_files"]
            if len(files) <= 3:
                body_lines.append(f"Generated files: {', '.join(files)}")
            else:
                body_lines.append(f"Generated {len(files)} files including {files[0]}")

        # Add metrics if available
        if result.get("metrics"):
            metrics = result["metrics"]
            for key, value in metrics.items():
                if key != "duration":
                    body_lines.append(f"{key.replace('_', ' ').title()}: {value}")

        # Add workflow progress
        summary_data = state.get_summary()
        progress = f"{summary_data['completed_stages']}/{summary_data['total_stages']} stages complete"
        body_lines.append(f"Workflow progress: {progress}")

        # Add breaking changes if specified
        if include_breaking_changes and result.get("breaking_changes"):
            body_lines.append("")
            body_lines.append("BREAKING CHANGE:")
            for change in result["breaking_changes"]:
                body_lines.append(f"- {change}")

        # Construct final message
        if body_lines:
            commit_message = summary + "\n\n" + "\n".join(body_lines)
        else:
            commit_message = summary

        return commit_message

    @classmethod
    def _extract_scope_from_state(cls, state: WorkflowState) -> Optional[str]:
        """Extract a meaningful scope from workflow state."""
        if not state.inputs:
            return None

        # Try to extract scope from project description
        desc = state.inputs.project_description.lower()

        # Common project types
        if "web" in desc or "frontend" in desc or "ui" in desc:
            return "web"
        elif "api" in desc or "backend" in desc or "server" in desc:
            return "api"
        elif "mobile" in desc or "app" in desc:
            return "mobile"
        elif "cli" in desc or "command" in desc:
            return "cli"
        elif "ml" in desc or "ai" in desc or "model" in desc:
            return "ml"
        else:
            # Extract first significant word
            words = desc.split()
            for word in words:
                if len(word) > 3 and word not in [
                    "the",
                    "and",
                    "for",
                    "with",
                    "that",
                    "this",
                ]:
                    return word

        return None


class GitHubIntegrator:
    """Enhanced GitHub integration for workflow system."""

    def __init__(
        self,
        repo_path: Optional[Path] = None,
        github_token: Optional[str] = None,
        repo_owner: Optional[str] = None,
        repo_name: Optional[str] = None,
    ):
        """
        Initialize GitHub integrator.

        Args:
            repo_path: Path to git repository
            github_token: GitHub API token
            repo_owner: Repository owner/organization
            repo_name: Repository name
        """
        self.git = GitIntegrator(repo_path)
        self.logger = logging.getLogger("github_integrator")

        # GitHub API configuration
        self.github_token = github_token
        self.repo_owner = repo_owner
        self.repo_name = repo_name

        # If not provided, try to extract from git remote
        if not (repo_owner and repo_name):
            self._extract_repo_info()

        # GitHub API session
        self.session = requests.Session()
        if github_token:
            self.session.headers.update({"Authorization": f"token {github_token}"})

        self.base_url = (
            f"https://api.github.com/repos/{self.repo_owner}/{self.repo_name}"
        )

        # Feedback tracking
        self.feedback_history: list[WorkflowFeedback] = []
        self.last_comment_check: Optional[datetime] = None

    def _extract_repo_info(self):
        """Extract repository owner and name from git remote."""
        try:
            result = self.git._run_git_command(["remote", "get-url", "origin"])
            remote_url = result.stdout.strip()

            # Parse GitHub URL
            if "github.com" in remote_url:
                # Handle both SSH and HTTPS URLs
                if remote_url.startswith("git@"):
                    # SSH: git@github.com:owner/repo.git
                    match = re.search(
                        r"git@github\.com:([^/]+)/([^\.]+)(?:\.git)?", remote_url
                    )
                else:
                    # HTTPS: https://github.com/owner/repo.git
                    match = re.search(
                        r"github\.com/([^/]+)/([^\.]+)(?:\.git)?", remote_url
                    )

                if match:
                    self.repo_owner = match.group(1)
                    self.repo_name = match.group(2)
                    self.logger.info(
                        f"Detected GitHub repo: {self.repo_owner}/{self.repo_name}"
                    )
                else:
                    raise ValueError(f"Could not parse GitHub URL: {remote_url}")
            else:
                raise ValueError("Remote origin is not a GitHub repository")

        except subprocess.CalledProcessError:
            raise ValueError("Could not determine GitHub repository from git remote")

    def create_enhanced_commit(
        self,
        stage_name: str,
        result: dict[str, Any],
        state: WorkflowState,
        include_breaking_changes: bool = False,
    ) -> Optional[str]:
        """Create an enhanced commit with conventional commit format."""
        try:
            # Generate conventional commit message
            commit_message = ConventionalCommitGenerator.generate_commit_message(
                stage_name, result, state, include_breaking_changes
            )

            # Stage relevant files
            files_to_stage = self._get_stage_files(stage_name, result)
            if files_to_stage:
                for file_path in files_to_stage:
                    self.git._run_git_command(["add", str(file_path)])

            # Create commit
            self.git._run_git_command(["commit", "-m", commit_message])

            # Get commit hash
            result = self.git._run_git_command(["rev-parse", "HEAD"])
            commit_hash = result.stdout.strip()

            self.logger.info(
                f"Created enhanced commit {commit_hash[:8]} for stage {stage_name}"
            )
            return commit_hash

        except subprocess.CalledProcessError as e:
            self.logger.error(
                f"Failed to create enhanced commit for stage {stage_name}: {e}"
            )
            return None

    def create_pull_request(
        self,
        workflow_id: str,
        state: WorkflowState,
        title: Optional[str] = None,
        body: Optional[str] = None,
        target_branch: str = "main",
    ) -> Optional[PullRequest]:
        """Create a pull request for the workflow."""
        if not self.github_token:
            self.logger.warning("No GitHub token provided, cannot create PR")
            return None

        try:
            # Get current branch
            result = self.git._run_git_command(["branch", "--show-current"])
            current_branch = result.stdout.strip()

            # Generate PR title and body if not provided
            if not title:
                summary = state.get_summary()
                title = f"Enhanced Multi-Agent Workflow: {workflow_id}"

            if not body:
                body = self._generate_pr_body(state)

            # Create PR via GitHub API
            pr_data = {
                "title": title,
                "body": body,
                "head": current_branch,
                "base": target_branch,
            }

            response = self.session.post(f"{self.base_url}/pulls", json=pr_data)
            response.raise_for_status()

            pr_info = response.json()
            pr = PullRequest.from_github_api(pr_info)
            pr.workflow_id = workflow_id

            self.logger.info(f"Created PR #{pr.number}: {pr.title}")
            return pr

        except requests.RequestException as e:
            self.logger.error(f"Failed to create pull request: {e}")
            return None

    def _generate_pr_body(self, state: WorkflowState) -> str:
        """Generate pull request body from workflow state."""
        summary = state.get_summary()

        body = [
            "## 🤖 Enhanced Multi-Agent Workflow",
            "",
            f"**Workflow ID**: `{state.workflow_id}`",
            f"**Project**: {state.inputs.project_description if state.inputs else 'Multi-Agent Project'}",
            f"**Progress**: {summary['completed_stages']}/{summary['total_stages']} stages complete",
            "",
            "### 📋 Completed Stages",
        ]

        for stage_name, stage in state.stages.items():
            if stage.status == StageStatus.COMPLETED:
                icon = "✅"
                duration = ""
                if stage.started_at and stage.completed_at:
                    delta = stage.completed_at - stage.started_at
                    duration = f" ({delta.total_seconds():.1f}s)"

                body.append(
                    f"- {icon} **{stage_name.replace('_', ' ').title()}**{duration}"
                )

                if stage.output_files:
                    files = stage.output_files[:3]  # Show first 3 files
                    file_list = ", ".join(f"`{f}`" for f in files)
                    if len(stage.output_files) > 3:
                        file_list += f" and {len(stage.output_files) - 3} more"
                    body.append(f"  - Generated: {file_list}")

        # Add pending stages
        pending_stages = [
            name
            for name, stage in state.stages.items()
            if stage.status in [StageStatus.PENDING, StageStatus.RUNNING]
        ]
        if pending_stages:
            body.extend(["", "### ⏳ Remaining Stages"])
            for stage_name in pending_stages:
                body.append(f"- ⏳ **{stage_name.replace('_', ' ').title()}**")

        body.extend(
            [
                "",
                "### 🎯 Workflow Commands",
                "Comment on this PR to control the workflow:",
                "- `@workflow pause` - Pause the workflow",
                "- `@workflow resume` - Resume the workflow",
                "- `@workflow resume <stage_name>` - Resume from specific stage",
                "- `approve` or `LGTM` - Approve current stage",
                "- `reject` or `needs work` - Request changes",
                "",
                "---",
                "*This PR was created automatically by the Enhanced Multi-Agent Workflow System*",
            ]
        )

        return "\n".join(body)

    def poll_comments(
        self,
        pr_number: int,
        since: Optional[datetime] = None,
    ) -> list[GitHubComment]:
        """Poll for new GitHub comments on a PR."""
        if not self.github_token:
            self.logger.warning("No GitHub token provided, cannot poll comments")
            return []

        try:
            # Use since timestamp or last check time
            since_time = since or self.last_comment_check

            # Get comments from GitHub API
            url = f"{self.base_url}/issues/{pr_number}/comments"
            params = {}
            if since_time:
                params["since"] = since_time.isoformat()

            response = self.session.get(url, params=params)
            response.raise_for_status()

            comments_data = response.json()
            comments = []

            for comment_data in comments_data:
                comment = GitHubComment(
                    id=comment_data["id"],
                    author=comment_data["user"]["login"],
                    body=comment_data["body"],
                    created_at=datetime.fromisoformat(
                        comment_data["created_at"].replace("Z", "+00:00")
                    ),
                    updated_at=datetime.fromisoformat(
                        comment_data["updated_at"].replace("Z", "+00:00")
                    ),
                    url=comment_data["html_url"],
                )

                # Parse workflow commands
                comment.parse_workflow_commands()
                comments.append(comment)

            self.last_comment_check = datetime.now(UTC)
            self.logger.info(f"Polled {len(comments)} new comments for PR #{pr_number}")

            return comments

        except requests.RequestException as e:
            self.logger.error(f"Failed to poll comments for PR #{pr_number}: {e}")
            return []

    def process_feedback(
        self,
        comments: list[GitHubComment],
        pr_number: int,
    ) -> list[WorkflowFeedback]:
        """Process comments into actionable workflow feedback."""
        feedback_list = []

        for comment in comments:
            if not comment.workflow_commands:
                continue

            for command in comment.workflow_commands:
                parts = command.split()
                command_type = parts[0]
                stage_name = parts[1] if len(parts) > 1 else None

                feedback = WorkflowFeedback(
                    pr_number=pr_number,
                    comment_id=comment.id,
                    author=comment.author,
                    feedback_type=command_type,
                    message=comment.body,
                    stage_name=stage_name,
                )

                # Extract requested changes for reject feedback
                if command_type == "reject":
                    feedback.requested_changes = self._extract_requested_changes(
                        comment.body
                    )

                feedback_list.append(feedback)
                self.logger.info(
                    f"Processed feedback: {command_type} from {comment.author}"
                )

        self.feedback_history.extend(feedback_list)
        return feedback_list

    def _extract_requested_changes(self, comment_body: str) -> dict[str, Any]:
        """Extract structured changes from rejection comments."""
        changes = {}

        # Look for specific change requests
        lines = comment_body.split("\n")
        for line in lines:
            line = line.strip()

            # Look for bullet points or numbered lists
            if re.match(r"^\s*[-*•]\s+", line) or re.match(r"^\s*\d+\.\s+", line):
                # Remove bullet/number prefix
                clean_line = re.sub(r"^\s*[-*•]\s+", "", line)
                clean_line = re.sub(r"^\s*\d+\.\s+", "", clean_line)

                # Categorize the change request
                if "test" in clean_line.lower():
                    changes.setdefault("testing", []).append(clean_line)
                elif "doc" in clean_line.lower():
                    changes.setdefault("documentation", []).append(clean_line)
                elif "error" in clean_line.lower() or "bug" in clean_line.lower():
                    changes.setdefault("bug_fixes", []).append(clean_line)
                else:
                    changes.setdefault("general", []).append(clean_line)

        return changes

    def post_comment(self, pr_number: int, message: str) -> Optional[GitHubComment]:
        """Post a comment to a GitHub PR."""
        if not self.github_token:
            self.logger.warning("No GitHub token provided, cannot post comment")
            return None

        try:
            comment_data = {"body": message}

            response = self.session.post(
                f"{self.base_url}/issues/{pr_number}/comments", json=comment_data
            )
            response.raise_for_status()

            comment_info = response.json()
            comment = GitHubComment(
                id=comment_info["id"],
                author=comment_info["user"]["login"],
                body=comment_info["body"],
                created_at=datetime.fromisoformat(
                    comment_info["created_at"].replace("Z", "+00:00")
                ),
                updated_at=datetime.fromisoformat(
                    comment_info["updated_at"].replace("Z", "+00:00")
                ),
                url=comment_info["html_url"],
            )

            self.logger.info(f"Posted comment to PR #{pr_number}")
            return comment

        except requests.RequestException as e:
            self.logger.error(f"Failed to post comment to PR #{pr_number}: {e}")
            return None

    def _get_stage_files(self, stage_name: str, result: dict[str, Any]) -> list[Path]:
        """Get files to stage for a given workflow stage."""
        files_to_stage = []

        # Add output files from the stage
        if result.get("output_files"):
            for file_path in result["output_files"]:
                path = Path(file_path)
                if path.exists():
                    files_to_stage.append(path)

        # Add common workflow files
        workflow_files = [
            "multi_agent_workflow/",
            "improvements/enhanced_workflow_system.md",
        ]

        for file_pattern in workflow_files:
            if Path(file_pattern).exists():
                files_to_stage.append(Path(file_pattern))

        return files_to_stage
