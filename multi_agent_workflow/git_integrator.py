#!/usr/bin/env python3
"""
Git Integration Module for Enhanced Multi-Agent Workflow System

Provides automated git operations including:
- Auto-commit after each workflow stage
- Descriptive commit message generation
- Branch creation with timestamp naming
- Push functionality
- Git status checking and validation
"""

import logging
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

try:
    # Try relative import first (when used as module)
    from .workflow_state import StageStatus, WorkflowState
except ImportError:
    # Fallback to direct import (when run as standalone script)
    from workflow_state import StageStatus, WorkflowState


class GitIntegrator:
    """Handles git operations for workflow automation."""

    def __init__(self, repo_path: Optional[Path] = None):
        """
        Initialize git integrator.

        Args:
            repo_path: Path to git repository (defaults to current directory)
        """
        self.repo_path = repo_path or Path.cwd()
        self.logger = logging.getLogger("git_integrator")

        # Ensure we're in a git repository
        if not self._is_git_repo():
            raise ValueError(f"Path {self.repo_path} is not a git repository")

    def _is_git_repo(self) -> bool:
        """Check if current directory is a git repository."""
        git_dir = self.repo_path / ".git"
        return git_dir.exists()

    def _run_git_command(
        self, args: list[str], check_output: bool = True
    ) -> subprocess.CompletedProcess:
        """
        Run a git command safely.

        Args:
            args: Git command arguments (without 'git')
            check_output: Whether to capture output

        Returns:
            Completed process result

        Raises:
            subprocess.CalledProcessError: If git command fails
        """
        cmd = ["git"] + args

        try:
            if check_output:
                result = subprocess.run(
                    cmd, cwd=self.repo_path, capture_output=True, text=True, check=True
                )
            else:
                result = subprocess.run(cmd, cwd=self.repo_path, check=True)

            self.logger.debug(f"Git command succeeded: {' '.join(cmd)}")
            return result

        except subprocess.CalledProcessError as e:
            self.logger.error(f"Git command failed: {' '.join(cmd)}")
            if hasattr(e, "stderr") and e.stderr:
                self.logger.error(f"Git error output: {e.stderr}")
            raise

    def get_current_branch(self) -> str:
        """Get the current git branch name."""
        try:
            result = self._run_git_command(["rev-parse", "--abbrev-ref", "HEAD"])
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            self.logger.warning("Could not determine current branch")
            return "main"  # Default fallback

    def get_repo_status(self) -> dict[str, Any]:
        """
        Get current repository status.

        Returns:
            Dictionary with status information including:
            - has_changes: Whether there are uncommitted changes
            - staged_files: List of staged files
            - unstaged_files: List of unstaged files
            - untracked_files: List of untracked files
            - current_branch: Current branch name
        """
        try:
            # Get status in porcelain format for easy parsing
            result = self._run_git_command(["status", "--porcelain"])
            status_lines = (
                result.stdout.strip().split("\n") if result.stdout.strip() else []
            )

            staged_files = []
            unstaged_files = []
            untracked_files = []

            for line in status_lines:
                if len(line) >= 3:
                    staged_status = line[0]
                    unstaged_status = line[1]
                    file_path = line[3:]  # Skip the two status characters and space

                    # Handle untracked files first (both chars are ?)
                    if staged_status == "?" and unstaged_status == "?":
                        untracked_files.append(file_path)
                    else:
                        # Handle staged changes
                        if staged_status != " ":
                            staged_files.append(file_path)

                        # Handle unstaged changes
                        if unstaged_status != " ":
                            unstaged_files.append(file_path)

            return {
                "has_changes": bool(status_lines),
                "staged_files": staged_files,
                "unstaged_files": unstaged_files,
                "untracked_files": untracked_files,
                "current_branch": self.get_current_branch(),
            }

        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to get git status: {e}")
            return {
                "has_changes": False,
                "staged_files": [],
                "unstaged_files": [],
                "untracked_files": [],
                "current_branch": self.get_current_branch(),
            }

    def create_workflow_branch(
        self, workflow_id: str, base_branch: Optional[str] = None
    ) -> str:
        """
        Create a new branch for the workflow.

        Args:
            workflow_id: Unique workflow identifier
            base_branch: Base branch to create from (defaults to current branch)

        Returns:
            Name of the created branch
        """
        if not base_branch:
            base_branch = self.get_current_branch()

        # Create branch name with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        branch_name = f"workflow/{workflow_id}_{timestamp}"

        try:
            # Check if branch already exists
            try:
                self._run_git_command(["rev-parse", "--verify", branch_name])
                self.logger.info(f"Branch {branch_name} already exists, using it")
                return branch_name
            except subprocess.CalledProcessError:
                pass  # Branch doesn't exist, create it

            # Create and checkout new branch
            self._run_git_command(["checkout", "-b", branch_name, base_branch])
            self.logger.info(f"Created and switched to branch: {branch_name}")

            return branch_name

        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to create branch {branch_name}: {e}")
            raise RuntimeError(f"Could not create workflow branch: {e}")

    def generate_stage_commit_message(
        self,
        stage_name: str,
        stage_result: dict[str, Any],
        workflow_state: WorkflowState,
    ) -> str:
        """
        Generate a descriptive commit message for a workflow stage.

        Args:
            stage_name: Name of the completed stage
            stage_result: Results from stage execution
            workflow_state: Current workflow state

        Returns:
            Formatted commit message
        """
        # Format stage name for display
        stage_display = stage_name.replace("_", " ").title()

        # Get project description
        project_desc = "Multi-Agent Project"
        if workflow_state.inputs and workflow_state.inputs.project_description:
            project_desc = workflow_state.inputs.project_description

        # Build commit message
        commit_lines = [
            f"feat: Complete {stage_display}",
            "",
            f"Completed {stage_display} for: {project_desc}",
            f"Workflow ID: {workflow_state.workflow_id}",
            "",
        ]

        # Add metrics if available
        if stage_result.get("metrics"):
            commit_lines.append("📊 Stage Metrics:")
            for key, value in stage_result["metrics"].items():
                metric_name = key.replace("_", " ").title()
                commit_lines.append(f"- {metric_name}: {value}")
            commit_lines.append("")

        # Add output files if available
        if stage_result.get("output_files"):
            files = stage_result["output_files"]
            if len(files) <= 5:
                commit_lines.append("📁 Files Created:")
                for file_path in files:
                    commit_lines.append(f"- {file_path}")
            else:
                commit_lines.append(f"📁 Created {len(files)} files:")
                for file_path in files[:3]:
                    commit_lines.append(f"- {file_path}")
                commit_lines.append(f"- ... and {len(files) - 3} more")
            commit_lines.append("")

        # Add next actions if available
        if stage_result.get("next_actions"):
            commit_lines.append("🔄 Next Actions:")
            for action in stage_result["next_actions"]:
                commit_lines.append(f"- {action}")
            commit_lines.append("")

        # Add workflow progress
        summary = workflow_state.get_summary()
        commit_lines.extend(
            [
                f"Progress: {summary['progress_percent']:.1f}% ({summary['completed_stages']}/{summary['total_stages']} stages)",
                "",
                "🤖 Generated with [Claude Code](https://claude.ai/code)",
                "",
                "Co-Authored-By: Claude <noreply@anthropic.com>",
            ]
        )

        return "\n".join(commit_lines)

    def stage_workflow_files(
        self, stage_name: str, stage_result: dict[str, Any]
    ) -> list[str]:
        """
        Stage relevant files for commit after a workflow stage.

        Args:
            stage_name: Name of the completed stage
            stage_result: Results from stage execution

        Returns:
            List of files that were staged
        """
        staged_files = []

        try:
            # Always stage workflow state files
            state_files = list(
                self.repo_path.glob("multi_agent_workflow/state/*_state.json")
            )
            for state_file in state_files:
                if state_file.exists():
                    rel_path = state_file.relative_to(self.repo_path)
                    self._run_git_command(["add", str(rel_path)])
                    staged_files.append(str(rel_path))

            # Stage output files if they exist in the repo
            if stage_result.get("output_files"):
                for file_path in stage_result["output_files"]:
                    full_path = self.repo_path / file_path
                    if full_path.exists():
                        self._run_git_command(["add", file_path])
                        staged_files.append(file_path)
                        self.logger.debug(f"Staged output file: {file_path}")
                    else:
                        self.logger.debug(f"Output file not found in repo: {file_path}")

            # Stage any other modified files that look workflow-related
            status = self.get_repo_status()
            for file_path in status["unstaged_files"]:
                if (
                    file_path.startswith("multi_agent_workflow/")
                    or file_path.startswith("workflow_")
                    or file_path.endswith("_workflow.md")
                    or file_path.endswith("_state.json")
                ):
                    self._run_git_command(["add", file_path])
                    staged_files.append(file_path)
                    self.logger.debug(f"Staged workflow file: {file_path}")

            self.logger.info(f"Staged {len(staged_files)} files for {stage_name}")
            return staged_files

        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to stage files for {stage_name}: {e}")
            return staged_files

    def commit_stage(
        self,
        stage_name: str,
        stage_result: dict[str, Any],
        workflow_state: WorkflowState,
    ) -> Optional[str]:
        """
        Create a commit for a completed workflow stage.

        Args:
            stage_name: Name of the completed stage
            stage_result: Results from stage execution
            workflow_state: Current workflow state

        Returns:
            Commit hash if successful, None if failed
        """
        try:
            # Stage relevant files
            staged_files = self.stage_workflow_files(stage_name, stage_result)

            if not staged_files:
                self.logger.info(f"No files to commit for stage: {stage_name}")
                return None

            # Generate commit message
            commit_message = self.generate_stage_commit_message(
                stage_name, stage_result, workflow_state
            )

            # Create commit
            self._run_git_command(["commit", "-m", commit_message])

            # Get commit hash
            result = self._run_git_command(["rev-parse", "HEAD"])
            commit_hash = result.stdout.strip()

            self.logger.info(
                f"Created commit {commit_hash[:8]} for stage: {stage_name}"
            )
            return commit_hash

        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to commit stage {stage_name}: {e}")
            return None

    def push_branch(
        self, branch_name: Optional[str] = None, force: bool = False
    ) -> bool:
        """
        Push current branch or specified branch to remote.

        Args:
            branch_name: Branch to push (defaults to current branch)
            force: Whether to force push

        Returns:
            True if push succeeded, False otherwise
        """
        if not branch_name:
            branch_name = self.get_current_branch()

        try:
            push_args = ["push"]

            # Check if remote tracking is set up
            try:
                self._run_git_command(
                    ["rev-parse", "--abbrev-ref", f"{branch_name}@{{upstream}}"]
                )
            except subprocess.CalledProcessError:
                # No upstream set, use -u flag to set it
                push_args.extend(["-u", "origin", branch_name])

            if force:
                push_args.append("--force-with-lease")

            self._run_git_command(push_args)
            self.logger.info(f"Successfully pushed branch: {branch_name}")
            return True

        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to push branch {branch_name}: {e}")
            return False

    def create_workflow_summary_commit(
        self, workflow_state: WorkflowState
    ) -> Optional[str]:
        """
        Create a final summary commit when workflow completes.

        Args:
            workflow_state: Completed workflow state

        Returns:
            Commit hash if successful, None if failed
        """
        try:
            # Generate comprehensive summary commit message
            summary = workflow_state.get_summary()
            project_desc = "Multi-Agent Project"
            if workflow_state.inputs and workflow_state.inputs.project_description:
                project_desc = workflow_state.inputs.project_description

            commit_lines = [
                "feat: Complete Enhanced Multi-Agent Workflow",
                "",
                f"🎉 Successfully completed workflow: {project_desc}",
                f"Workflow ID: {workflow_state.workflow_id}",
                "",
                "📊 Final Summary:",
                f"- Total Stages: {summary['total_stages']}",
                f"- Completed Stages: {summary['completed_stages']}",
                f"- Success Rate: {summary['progress_percent']:.1f}%",
                f"- Started: {summary['created_at'][:19]}",
                f"- Completed: {summary['updated_at'][:19]}",
                "",
            ]

            # Add stage breakdown
            commit_lines.append("🔄 Stages Completed:")
            for stage_name, stage in workflow_state.stages.items():
                if stage.status == StageStatus.COMPLETED:
                    stage_display = stage_name.replace("_", " ").title()
                    duration = ""
                    if stage.started_at and stage.completed_at:
                        delta = stage.completed_at - stage.started_at
                        duration = f" ({delta.total_seconds():.1f}s)"
                    commit_lines.append(f"- ✅ {stage_display}{duration}")

            commit_lines.extend(
                [
                    "",
                    "Ready for deployment and further development! 🚀",
                    "",
                    "🤖 Generated with [Claude Code](https://claude.ai/code)",
                    "",
                    "Co-Authored-By: Claude <noreply@anthropic.com>",
                ]
            )

            commit_message = "\n".join(commit_lines)

            # Stage final state files
            self.stage_workflow_files("workflow_complete", {})

            # Create commit
            self._run_git_command(["commit", "-m", commit_message])

            # Get commit hash
            result = self._run_git_command(["rev-parse", "HEAD"])
            commit_hash = result.stdout.strip()

            self.logger.info(f"Created workflow summary commit: {commit_hash[:8]}")
            return commit_hash

        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to create workflow summary commit: {e}")
            return None


# Singleton instance for easy import
git_integrator = GitIntegrator()
