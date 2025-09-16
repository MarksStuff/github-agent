"""Declarative node configuration system for LangGraph workflow nodes."""

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from .enums import AgentType, ArtifactName, ModelRouter

logger = logging.getLogger(__name__)


class OutputLocation(str, Enum):
    """Where to store node outputs."""

    LOCAL = "local"  # .local directory (intermediate)
    REPOSITORY = "repository"  # Repository for review


class CodeQualityCheck(str, Enum):
    """Standard code quality checks."""

    LINT = "lint"
    TEST = "test"
    TYPE_CHECK = "type_check"
    FORMAT = "format"


@dataclass
class CommandResult:
    """Result of running a command."""

    command: str
    returncode: int
    stdout: str
    stderr: str
    duration: float

    @property
    def failed(self) -> bool:
        return self.returncode != 0

    @property
    def succeeded(self) -> bool:
        return self.returncode == 0


@dataclass
class CodeQualityResult:
    """Results from code quality checks."""

    overall_success: bool = True
    lint_results: list[CommandResult] = field(default_factory=list)
    test_results: list[CommandResult] = field(default_factory=list)
    type_check_results: list[CommandResult] = field(default_factory=list)
    format_results: list[CommandResult] = field(default_factory=list)


@dataclass
class PRFeedbackResult:
    """Results from PR feedback processing."""

    has_feedback: bool = False
    comments_processed: int = 0
    changes_made: dict[str, str] = field(default_factory=dict)


@dataclass
class NodeConfig:
    """Declarative configuration for workflow nodes."""

    # Model selection
    needs_code_access: bool = False
    model_preference: ModelRouter = ModelRouter.OLLAMA

    # Agents and prompts
    agents: list[AgentType] = field(default_factory=list)
    prompt_template: str = ""
    agent_prompt_customizations: dict[AgentType, str] = field(default_factory=dict)

    # Output configuration
    output_location: OutputLocation = OutputLocation.LOCAL
    artifact_names: list[ArtifactName] = field(default_factory=list)
    artifact_path_template: str = "{base_path}/pr-{pr_number}/{artifact_name}"

    # Standard workflow integrations
    requires_code_changes: bool = False  # Triggers lint/test workflow
    requires_pr_feedback: bool = False  # Triggers GitHub PR interaction

    # Code quality configuration
    pre_commit_checks: list[CodeQualityCheck] = field(default_factory=list)
    test_commands: list[str] = field(default_factory=lambda: ["python -m pytest"])
    lint_commands: list[str] = field(
        default_factory=lambda: [
            "scripts/ruff-autofix.sh",
            "scripts/run-code-checks.sh",
        ]
    )

    # PR feedback configuration
    pr_feedback_prompt: str = ""  # How to process PR comments
    pr_reply_template: str = ""  # Template for final outcome replies

    def get_model_router(self) -> ModelRouter:
        """Determine which model to use based on code access needs and preference."""
        if self.needs_code_access or self.model_preference == ModelRouter.CLAUDE_CODE:
            return ModelRouter.CLAUDE_CODE
        return ModelRouter.OLLAMA

    def get_artifact_path(
        self, artifact_name: str, pr_number: int | None, base_path: str
    ) -> str:
        """Generate artifact path with PR number inclusion."""
        if pr_number:
            return self.artifact_path_template.format(
                base_path=base_path, pr_number=pr_number, artifact_name=artifact_name
            )
        else:
            return f"{base_path}/{artifact_name}"


@dataclass
class NodeDefinition:
    """Complete node definition with config and handler."""

    config: NodeConfig
    handler: Callable
    description: str = ""

    def __post_init__(self):
        """Validate the node definition."""
        if self.handler is None:
            raise ValueError("Node handler is required")
        if not self.config.agents and self.config.prompt_template:
            raise ValueError("Agents are required when prompt_template is specified")


class StandardWorkflows:
    """Composable standard workflow components."""

    @staticmethod
    async def run_command(command: str, cwd: str | None = None) -> CommandResult:
        """Run a shell command and return structured result."""
        import time

        start_time = time.time()

        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )

            stdout, stderr = await process.communicate()
            duration = time.time() - start_time

            return CommandResult(
                command=command,
                returncode=process.returncode or 0,
                stdout=stdout.decode("utf-8") if stdout else "",
                stderr=stderr.decode("utf-8") if stderr else "",
                duration=duration,
            )

        except Exception as e:
            duration = time.time() - start_time
            return CommandResult(
                command=command,
                returncode=1,
                stdout="",
                stderr=str(e),
                duration=duration,
            )

    @staticmethod
    async def run_code_quality_checks(
        config: NodeConfig, repo_path: str, changed_files: list[str] | None = None
    ) -> CodeQualityResult:
        """Run standard code quality checks."""
        results = CodeQualityResult()

        logger.info("🔍 Running code quality checks...")

        # Run lint checks
        if CodeQualityCheck.LINT in config.pre_commit_checks:
            for cmd in config.lint_commands:
                logger.info(f"Running lint: {cmd}")
                result = await StandardWorkflows.run_command(cmd, cwd=repo_path)
                results.lint_results.append(result)
                if result.failed:
                    logger.error(f"❌ Lint check failed: {cmd}")
                    logger.error(f"Error: {result.stderr}")
                    results.overall_success = False
                else:
                    logger.info(f"✅ Lint check passed: {cmd}")

        # Run tests
        if CodeQualityCheck.TEST in config.pre_commit_checks:
            for cmd in config.test_commands:
                logger.info(f"Running test: {cmd}")
                result = await StandardWorkflows.run_command(cmd, cwd=repo_path)
                results.test_results.append(result)
                if result.failed:
                    logger.error(f"❌ Test failed: {cmd}")
                    logger.error(f"Error: {result.stderr}")
                    results.overall_success = False
                else:
                    logger.info(f"✅ Test passed: {cmd}")

        # Run type checks
        if CodeQualityCheck.TYPE_CHECK in config.pre_commit_checks:
            type_check_cmd = "python -m mypy ."
            logger.info(f"Running type check: {type_check_cmd}")
            result = await StandardWorkflows.run_command(type_check_cmd, cwd=repo_path)
            results.type_check_results.append(result)
            if result.failed:
                logger.error(f"❌ Type check failed: {type_check_cmd}")
                logger.error(f"Error: {result.stderr}")
                results.overall_success = False
            else:
                logger.info(f"✅ Type check passed: {type_check_cmd}")

        if results.overall_success:
            logger.info("✅ All code quality checks passed")
        else:
            logger.error("❌ Code quality checks failed - must fix before proceeding")

        return results

    @staticmethod
    async def handle_pr_feedback_workflow(
        config: NodeConfig,
        pr_number: int,
        github_integration: Any,  # GitHubIntegration
        last_check_time: datetime | None = None,
    ) -> PRFeedbackResult:
        """Handle PR feedback workflow: read comments -> process -> reply."""

        logger.info(f"📝 Checking PR #{pr_number} for feedback...")

        try:
            # Get PR comments since last check
            comments = await github_integration.get_pr_comments(
                pr_number, since=last_check_time
            )

            if not comments:
                logger.info("No new PR comments found")
                return PRFeedbackResult(has_feedback=False)

            logger.info(f"📥 Found {len(comments)} new PR comments")

            # Process comments using configured prompt
            feedback_summary = await StandardWorkflows.process_pr_comments(
                comments, config.pr_feedback_prompt
            )

            # Apply feedback (implementation-specific)
            changes_made = await StandardWorkflows.apply_pr_feedback(
                feedback_summary, config
            )

            # Reply to each comment with outcome
            for comment in comments:
                reply_message = config.pr_reply_template.format(
                    outcome=changes_made.get(
                        str(comment.get("id", "")), "Acknowledged"
                    ),
                    timestamp=datetime.now().isoformat(),
                )

                await github_integration.reply_to_comment(comment["id"], reply_message)
                logger.info(f"✅ Replied to comment #{comment['id']}")

            return PRFeedbackResult(
                has_feedback=True,
                comments_processed=len(comments),
                changes_made=changes_made,
            )

        except Exception as e:
            logger.error(f"❌ Error handling PR feedback: {e}")
            return PRFeedbackResult(has_feedback=False)

    @staticmethod
    async def process_pr_comments(comments: list[dict], prompt_template: str) -> str:
        """Process PR comments into actionable feedback summary."""
        # For now, just concatenate comments - in real implementation,
        # this would use LLM to process and summarize
        comment_texts = []
        for comment in comments:
            comment_texts.append(
                f"Comment #{comment.get('id', '')}: {comment.get('body', '')}"
            )

        combined_comments = "\n\n".join(comment_texts)

        if prompt_template:
            return prompt_template.format(comments=combined_comments)
        else:
            return combined_comments

    @staticmethod
    async def apply_pr_feedback(
        feedback_summary: str, config: NodeConfig
    ) -> dict[str, str]:
        """Apply PR feedback and return changes made."""
        # Placeholder implementation - in real system, this would:
        # 1. Parse the feedback summary
        # 2. Make actual code/document changes
        # 3. Return summary of what was changed

        logger.info(f"📝 Processing feedback: {feedback_summary[:100]}...")

        # For now, just return a generic acknowledgment
        return {"general": "Feedback reviewed and incorporated where applicable"}


async def create_configured_node_handler(
    original_handler: Callable, config: NodeConfig, github_integration: Any = None
) -> Callable:
    """Create an enhanced node handler that integrates standard workflows."""

    async def configured_handler(state: dict) -> dict:
        """Enhanced node handler that integrates standard workflows."""

        # 1. Setup phase
        state["model_router"] = config.get_model_router()

        # 2. Handle PR feedback if required (BEFORE main work)
        if (
            config.requires_pr_feedback
            and state.get("pr_number")
            and github_integration
        ):
            pr_result = await StandardWorkflows.handle_pr_feedback_workflow(
                config,
                state["pr_number"],
                github_integration,
                state.get("last_pr_check_time"),
            )

            # Update state with feedback results
            state["last_pr_check_time"] = datetime.now()
            if pr_result.has_feedback:
                state["pr_feedback_applied"] = pr_result.changes_made
                logger.info(
                    f"📝 Applied feedback from {pr_result.comments_processed} PR comments"
                )

        # 3. Execute main node logic
        result_state = await original_handler(state)

        # 4. Code quality checks if code changes were made
        if config.requires_code_changes:
            quality_result = await StandardWorkflows.run_code_quality_checks(
                config,
                result_state.get("repo_path", "."),
                changed_files=result_state.get("modified_files", []),
            )

            # Store quality results
            result_state["quality_check_results"] = quality_result

            # HALT if quality checks fail
            if not quality_result.overall_success:
                from .enums import QualityLevel

                result_state["quality"] = QualityLevel.FAIL
                logger.error("⛔ Node execution halted due to code quality failures")

                # Log specific failures
                for lint_result in quality_result.lint_results:
                    if lint_result.failed:
                        logger.error(
                            f"Lint failure in {lint_result.command}: {lint_result.stderr}"
                        )

                for test_result in quality_result.test_results:
                    if test_result.failed:
                        logger.error(
                            f"Test failure in {test_result.command}: {test_result.stderr}"
                        )

                return result_state

            from .enums import QualityLevel

            result_state["quality"] = QualityLevel.OK
            logger.info("✅ Code quality checks passed")

        return result_state

    return configured_handler
