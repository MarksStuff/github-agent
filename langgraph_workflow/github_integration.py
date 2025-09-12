"""GitHub integration for PR-based human arbitration and CI/CD feedback."""

import asyncio
import json
import logging
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from github import Github, GithubException
from github.PullRequest import PullRequest
from github.Repository import Repository
import git

logger = logging.getLogger(__name__)


class GitHubIntegration:
    """Manages GitHub interactions for the workflow."""
    
    def __init__(self, repo_path: str, github_token: str | None = None):
        """Initialize GitHub integration.
        
        Args:
            repo_path: Local path to the repository
            github_token: GitHub API token (or from GITHUB_TOKEN env var)
        """
        self.repo_path = Path(repo_path)
        self.token = github_token or os.getenv("GITHUB_TOKEN")
        
        if not self.token:
            logger.warning("No GitHub token provided. PR operations will be limited.")
            self.github = None
            self.repo = None
        else:
            self.github = Github(self.token)
            self.repo = self._get_github_repo()
        
        self.git_repo = git.Repo(self.repo_path)
        
    def _get_github_repo(self) -> Repository | None:
        """Get the GitHub repository object from remote URL."""
        try:
            # Get origin remote URL
            origin = self.git_repo.remote("origin")
            url = origin.url
            
            # Extract owner/repo from URL
            # Handle both https and ssh URLs
            if "github.com" in url:
                if url.startswith("git@"):
                    # SSH format: git@github.com:owner/repo.git
                    parts = url.split(":")[-1].replace(".git", "").split("/")
                else:
                    # HTTPS format: https://github.com/owner/repo.git
                    parts = url.split("github.com/")[-1].replace(".git", "").split("/")
                
                if len(parts) >= 2:
                    repo_name = f"{parts[0]}/{parts[1]}"
                    return self.github.get_repo(repo_name)
            
        except Exception as e:
            logger.error(f"Failed to get GitHub repo: {e}")
        
        return None
    
    async def create_branch(self, branch_name: str, base_branch: str = "main") -> str:
        """Create a new branch.
        
        Args:
            branch_name: Name for the new branch
            base_branch: Base branch to create from
            
        Returns:
            Branch name
        """
        try:
            # Fetch latest
            self.git_repo.remotes.origin.fetch()
            
            # Create and checkout new branch
            base = self.git_repo.branches[base_branch]
            new_branch = self.git_repo.create_head(branch_name, base)
            new_branch.checkout()
            
            logger.info(f"Created branch: {branch_name}")
            return branch_name
            
        except Exception as e:
            logger.error(f"Failed to create branch: {e}")
            raise
    
    async def create_pull_request(
        self,
        title: str,
        body: str,
        branch: str,
        base_branch: str = "main",
        labels: list[str] | None = None
    ) -> int:
        """Create a GitHub pull request.
        
        Args:
            title: PR title
            body: PR description
            branch: Source branch
            base_branch: Target branch
            labels: Labels to add
            
        Returns:
            PR number
        """
        if not self.repo:
            logger.warning("No GitHub repo available. Returning dummy PR number.")
            return 9999
        
        try:
            # Push branch
            self.git_repo.remotes.origin.push(branch)
            
            # Create PR
            pr = self.repo.create_pull(
                title=title,
                body=body,
                head=branch,
                base=base_branch
            )
            
            # Add labels
            if labels:
                pr.add_to_labels(*labels)
            
            logger.info(f"Created PR #{pr.number}: {pr.html_url}")
            return pr.number
            
        except GithubException as e:
            logger.error(f"Failed to create PR: {e}")
            raise
    
    async def get_pr_comments(self, pr_number: int, since: datetime | None = None) -> list[dict]:
        """Get comments from a PR.
        
        Args:
            pr_number: PR number
            since: Only get comments after this time
            
        Returns:
            List of comment data
        """
        if not self.repo:
            return []
        
        try:
            pr = self.repo.get_pull(pr_number)
            
            comments = []
            
            # Get issue comments
            for comment in pr.get_issue_comments():
                if since and comment.created_at < since:
                    continue
                    
                comments.append({
                    "id": comment.id,
                    "type": "issue_comment",
                    "author": comment.user.login,
                    "body": comment.body,
                    "created_at": comment.created_at.isoformat(),
                    "html_url": comment.html_url
                })
            
            # Get review comments
            for comment in pr.get_review_comments():
                if since and comment.created_at < since:
                    continue
                    
                comments.append({
                    "id": comment.id,
                    "type": "review_comment",
                    "author": comment.user.login,
                    "body": comment.body,
                    "path": comment.path,
                    "line": comment.line,
                    "created_at": comment.created_at.isoformat(),
                    "html_url": comment.html_url
                })
            
            # Get reviews
            for review in pr.get_reviews():
                if since and review.submitted_at < since:
                    continue
                if not review.body:
                    continue
                    
                comments.append({
                    "id": review.id,
                    "type": "review",
                    "author": review.user.login,
                    "body": review.body,
                    "state": review.state,
                    "created_at": review.submitted_at.isoformat(),
                    "html_url": review.html_url
                })
            
            return sorted(comments, key=lambda x: x["created_at"])
            
        except Exception as e:
            logger.error(f"Failed to get PR comments: {e}")
            return []
    
    async def add_pr_comment(self, pr_number: int, comment: str) -> bool:
        """Add a comment to a PR.
        
        Args:
            pr_number: PR number
            comment: Comment text
            
        Returns:
            Success status
        """
        if not self.repo:
            return False
        
        try:
            pr = self.repo.get_pull(pr_number)
            pr.create_issue_comment(comment)
            logger.info(f"Added comment to PR #{pr_number}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add PR comment: {e}")
            return False
    
    async def get_ci_status(self, pr_number: int) -> dict[str, Any]:
        """Get CI status for a PR.
        
        Args:
            pr_number: PR number
            
        Returns:
            CI status information
        """
        if not self.repo:
            return {"status": "unknown", "checks": []}
        
        try:
            pr = self.repo.get_pull(pr_number)
            
            # Get the latest commit
            commits = pr.get_commits()
            latest_commit = list(commits)[-1]
            
            # Get check runs
            check_runs = latest_commit.get_check_runs()
            
            checks = []
            overall_status = "success"
            
            for run in check_runs:
                check_info = {
                    "name": run.name,
                    "status": run.status,
                    "conclusion": run.conclusion,
                    "started_at": run.started_at.isoformat() if run.started_at else None,
                    "completed_at": run.completed_at.isoformat() if run.completed_at else None,
                    "details_url": run.details_url,
                    "output": {
                        "title": run.output.title if run.output else None,
                        "summary": run.output.summary if run.output else None
                    }
                }
                checks.append(check_info)
                
                # Update overall status
                if run.status == "in_progress":
                    overall_status = "pending"
                elif run.conclusion and run.conclusion != "success":
                    overall_status = "failure"
            
            return {
                "status": overall_status,
                "checks": checks,
                "commit_sha": latest_commit.sha,
                "pr_number": pr_number
            }
            
        except Exception as e:
            logger.error(f"Failed to get CI status: {e}")
            return {"status": "error", "checks": [], "error": str(e)}
    
    async def get_check_logs(self, pr_number: int, check_name: str) -> str:
        """Get logs for a specific CI check.
        
        Args:
            pr_number: PR number
            check_name: Name of the check
            
        Returns:
            Log content
        """
        if not self.repo:
            return ""
        
        try:
            pr = self.repo.get_pull(pr_number)
            commits = pr.get_commits()
            latest_commit = list(commits)[-1]
            
            check_runs = latest_commit.get_check_runs()
            
            for run in check_runs:
                if run.name == check_name:
                    # GitHub API doesn't provide direct log access
                    # Would need to use Actions API for detailed logs
                    if run.output:
                        return f"{run.output.title}\n\n{run.output.summary}\n\n{run.output.text or ''}"
            
            return "Logs not available"
            
        except Exception as e:
            logger.error(f"Failed to get check logs: {e}")
            return f"Error: {e}"
    
    async def push_changes(self, branch: str, commit_message: str) -> str:
        """Commit and push changes to GitHub.
        
        Args:
            branch: Branch to push to
            commit_message: Commit message
            
        Returns:
            Commit SHA
        """
        try:
            # Stage all changes
            self.git_repo.index.add("*")
            
            # Commit
            commit = self.git_repo.index.commit(commit_message)
            
            # Push
            self.git_repo.remotes.origin.push(branch)
            
            logger.info(f"Pushed commit {commit.hexsha[:8]} to {branch}")
            return commit.hexsha
            
        except Exception as e:
            logger.error(f"Failed to push changes: {e}")
            raise
    
    async def wait_for_checks(
        self, 
        pr_number: int, 
        timeout: int = 1800,
        poll_interval: int = 30
    ) -> dict[str, Any]:
        """Wait for CI checks to complete.
        
        Args:
            pr_number: PR number
            timeout: Maximum wait time in seconds
            poll_interval: Time between polls in seconds
            
        Returns:
            Final CI status
        """
        start_time = datetime.now()
        
        while (datetime.now() - start_time).total_seconds() < timeout:
            status = await self.get_ci_status(pr_number)
            
            if status["status"] not in ["pending", "queued"]:
                return status
            
            logger.info(f"CI still running for PR #{pr_number}. Waiting...")
            await asyncio.sleep(poll_interval)
        
        logger.warning(f"CI timeout for PR #{pr_number}")
        return await self.get_ci_status(pr_number)
    
    def extract_actionable_feedback(self, comments: list[dict]) -> list[dict]:
        """Extract actionable items from PR comments.
        
        Args:
            comments: List of PR comments
            
        Returns:
            List of actionable items
        """
        actionable = []
        
        for comment in comments:
            body = comment["body"].lower()
            
            # Look for action indicators
            if any(indicator in body for indicator in [
                "please", "should", "must", "need to", "required",
                "fix", "change", "update", "add", "remove"
            ]):
                actionable.append({
                    "comment_id": comment["id"],
                    "author": comment["author"],
                    "task": comment["body"],
                    "type": comment["type"],
                    "priority": "high" if "must" in body or "required" in body else "normal"
                })
        
        return actionable
    
    async def create_worktree(self, branch: str, path: str | None = None) -> str:
        """Create a git worktree for parallel development.
        
        Args:
            branch: Branch name
            path: Path for worktree (auto-generated if None)
            
        Returns:
            Path to worktree
        """
        if path is None:
            path = self.repo_path.parent / f"worktrees/{branch}"
        
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            # Create worktree
            self.git_repo.git.worktree("add", str(path), branch)
            logger.info(f"Created worktree at {path}")
            return str(path)
            
        except Exception as e:
            logger.error(f"Failed to create worktree: {e}")
            raise
    
    async def apply_patch(self, patch_path: str, branch: str) -> bool:
        """Apply a patch file to a branch.
        
        Args:
            patch_path: Path to patch file
            branch: Branch to apply to
            
        Returns:
            Success status
        """
        try:
            # Checkout branch
            self.git_repo.heads[branch].checkout()
            
            # Apply patch
            result = subprocess.run(
                ["git", "apply", patch_path],
                cwd=self.repo_path,
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                logger.error(f"Failed to apply patch: {result.stderr}")
                return False
            
            logger.info(f"Applied patch {patch_path} to {branch}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to apply patch: {e}")
            return False


class MCPServerInterface:
    """Interface to MCP server for GitHub operations."""
    
    def __init__(self, server_url: str | None = None):
        """Initialize MCP server interface.
        
        Args:
            server_url: MCP server URL (or from MCP_SERVER_URL env var)
        """
        self.server_url = server_url or os.getenv("MCP_SERVER_URL", "http://localhost:8080")
        logger.info(f"MCP server interface initialized: {self.server_url}")
    
    async def get_pr_comments(self, pr_number: int, since: str | None = None) -> list[dict]:
        """Get PR comments via MCP server.
        
        Args:
            pr_number: PR number
            since: ISO timestamp for filtering
            
        Returns:
            List of comments
        """
        # This would call the actual MCP server
        # For now, return empty list as placeholder
        logger.info(f"MCP: Getting comments for PR #{pr_number}")
        return []
    
    async def get_check_runs(self, pr_number: int) -> list[dict]:
        """Get check runs via MCP server.
        
        Args:
            pr_number: PR number
            
        Returns:
            List of check runs
        """
        logger.info(f"MCP: Getting check runs for PR #{pr_number}")
        return []
    
    async def get_check_log(self, pr_number: int, check_id: str) -> str:
        """Get check log via MCP server.
        
        Args:
            pr_number: PR number
            check_id: Check run ID
            
        Returns:
            Log content
        """
        logger.info(f"MCP: Getting log for check {check_id}")
        return ""