"""Enhanced Multi-Agent Workflow with Declarative Node Configuration.

This module implements the LangGraph workflow using declarative node definitions
with integrated standard workflows for code quality and PR feedback.
"""

import logging
from pathlib import Path
from typing import Any

from langgraph.graph import StateGraph

from .enums import (
    FeedbackGateStatus,
    ModelRouter,
    QualityLevel,
    WorkflowPhase,
    WorkflowStep,
)
from .nodes import (
    create_design_document_node,
    design_synthesis_node,
    extract_code_context_node,
    parallel_design_exploration_node,
    parallel_development_node,
)
from .workflow_state import WorkflowState

logger = logging.getLogger(__name__)


class EnhancedMultiAgentWorkflow:
    """Enhanced workflow with declarative node configuration and standard workflows."""

    def __init__(
        self,
        repo_path: str,
        agents: dict[str, Any],
        codebase_analyzer: Any,
        github_integration: Any = None,
        thread_id: str | None = None,
        checkpoint_path: str = "enhanced_workflow_state.db",
    ):
        """Initialize the enhanced workflow.

        Args:
            repo_path: Path to the repository
            agents: Dictionary of agent implementations
            codebase_analyzer: Codebase analysis interface
            github_integration: GitHub integration for PR feedback
            thread_id: Thread ID for state persistence
            checkpoint_path: Path to SQLite checkpoint database
        """
        self.repo_path = repo_path
        self.agents = agents
        self.codebase_analyzer = codebase_analyzer
        self.github_integration = github_integration
        self.thread_id = thread_id or "enhanced-workflow"
        self.checkpoint_path = checkpoint_path

        # Compatibility attribute for old run.py
        from pathlib import Path

        self.artifacts_dir = str(Path.home() / ".local/share/github-agent/artifacts")

        # Node configurations loaded from separate files
        self.node_definitions = {
            WorkflowStep.EXTRACT_CODE_CONTEXT: extract_code_context_node,
            WorkflowStep.PARALLEL_DESIGN_EXPLORATION: parallel_design_exploration_node,
            WorkflowStep.DESIGN_SYNTHESIS: design_synthesis_node,
            WorkflowStep.CREATE_DESIGN_DOCUMENT: create_design_document_node,
            WorkflowStep.PARALLEL_DEVELOPMENT: parallel_development_node,
        }

        # Build the workflow graph
        self.graph = self._build_enhanced_graph()

        # Initialize checkpointing
        self._setup_checkpointing()

        logger.info(f"Enhanced workflow initialized for thread {self.thread_id}")

    def _build_enhanced_graph(self) -> StateGraph:
        """Build the enhanced workflow graph with declarative node configuration."""

        workflow = StateGraph(WorkflowState)

        logger.info("🏗️  Building enhanced workflow graph with declarative nodes")

        # Register all configured nodes
        for step, node_def in self.node_definitions.items():
            logger.info(f"   📋 Registering {step.value}: {node_def.description}")

            # Create configured handler with standard workflow integration
            configured_handler = self._create_configured_handler(
                node_def.handler, node_def.config
            )

            # Add to workflow graph
            workflow.add_node(step.value, configured_handler)

        # Set entry point
        workflow.set_entry_point(WorkflowStep.EXTRACT_CODE_CONTEXT.value)

        # Define workflow edges (simplified for demonstration)
        workflow.add_edge(
            WorkflowStep.EXTRACT_CODE_CONTEXT.value,
            WorkflowStep.PARALLEL_DESIGN_EXPLORATION.value,
        )
        workflow.add_edge(
            WorkflowStep.PARALLEL_DESIGN_EXPLORATION.value,
            WorkflowStep.DESIGN_SYNTHESIS.value,
        )
        workflow.add_edge(
            WorkflowStep.DESIGN_SYNTHESIS.value,
            WorkflowStep.CREATE_DESIGN_DOCUMENT.value,
        )
        workflow.add_edge(
            WorkflowStep.CREATE_DESIGN_DOCUMENT.value,
            WorkflowStep.PARALLEL_DEVELOPMENT.value,
        )

        # Add conditional edges for quality gates
        workflow.add_conditional_edges(
            WorkflowStep.PARALLEL_DEVELOPMENT.value,
            self._check_quality_gate,
            {
                "success": "__end__",
                "retry": WorkflowStep.PARALLEL_DEVELOPMENT.value,
                "fail": "__end__",
            },
        )

        logger.info("✅ Enhanced workflow graph built successfully")
        return workflow

    def _create_configured_handler(self, original_handler, config):
        """Create a configured handler for the workflow node."""
        from datetime import datetime

        from .enums import QualityLevel
        from .node_config import StandardWorkflows

        async def configured_handler(state: dict) -> dict:
            """Enhanced node handler that integrates standard workflows."""

            # 1. Setup phase
            state["model_router"] = config.get_model_router()

            # 2. Handle PR feedback if required (BEFORE main work)
            if (
                config.requires_pr_feedback
                and state.get("pr_number")
                and self.github_integration
            ):
                pr_result = await StandardWorkflows.handle_pr_feedback_workflow(
                    config,
                    state["pr_number"],
                    self.github_integration,
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
                    result_state["quality"] = QualityLevel.FAIL
                    logger.error(
                        "⛔ Node execution halted due to code quality failures"
                    )

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

                result_state["quality"] = QualityLevel.OK
                logger.info("✅ Code quality checks passed")

            return result_state

        return configured_handler

    def _setup_checkpointing(self):
        """Set up workflow checkpointing."""
        import sqlite3

        from langgraph.checkpoint.sqlite import SqliteSaver

        # Create checkpoint directory if needed
        checkpoint_dir = Path(self.checkpoint_path).parent
        checkpoint_dir.mkdir(parents=True, exist_ok=True)

        # Initialize SQLite checkpointer
        conn = sqlite3.connect(self.checkpoint_path)
        self.checkpointer = SqliteSaver(conn)
        self.app = self.graph.compile(checkpointer=self.checkpointer)

        logger.info(f"📁 Checkpointing enabled: {self.checkpoint_path}")

    def _check_quality_gate(self, state: dict) -> str:
        """Check if quality gates are met for workflow continuation."""

        # Check if quality checks passed
        quality_results = state.get("quality_check_results")
        if quality_results and not quality_results.overall_success:
            retry_count = state.get("quality_retry_count", 0)
            max_retries = 2

            if retry_count < max_retries:
                state["quality_retry_count"] = retry_count + 1
                logger.warning(
                    f"⚠️  Quality checks failed, retry {retry_count + 1}/{max_retries}"
                )
                return "retry"
            else:
                logger.error("❌ Quality checks failed after maximum retries")
                return "fail"

        # Check if PR feedback is pending
        if state.get("pr_feedback_pending"):
            logger.info("⏳ Waiting for PR feedback to be processed")
            return "retry"

        logger.info("✅ All quality gates passed")
        return "success"

    async def run_workflow(
        self, feature_description: str, pr_number: int | None = None, **kwargs
    ) -> dict:
        """Run the complete enhanced workflow.

        Args:
            feature_description: Description of the feature to implement
            pr_number: PR number for GitHub integration
            **kwargs: Additional workflow parameters

        Returns:
            Final workflow state
        """

        logger.info(f"🚀 Starting enhanced workflow for: {feature_description}")
        if pr_number:
            logger.info(f"📋 PR integration enabled for PR #{pr_number}")

        # Create initial state
        initial_state: dict[str, Any] = {
            "thread_id": self.thread_id,
            "feature_description": feature_description,
            "repo_path": self.repo_path,
            "pr_number": pr_number,
            "raw_feature_input": kwargs.get("raw_feature_input"),
            "extracted_feature": kwargs.get("extracted_feature"),
            "current_phase": WorkflowPhase.PHASE_0_CODE_CONTEXT,
            "messages_window": [],
            "summary_log": "",
            "artifacts_index": {},
            "code_context_document": None,
            "design_constraints_document": None,
            "design_document": None,
            "arbitration_log": [],
            "git_branch": kwargs.get("git_branch", "main"),
            "last_commit_sha": kwargs.get("last_commit_sha"),
            "agent_analyses": {},
            "synthesis_document": None,
            "conflicts": [],
            "skeleton_code": None,
            "test_code": None,
            "implementation_code": None,
            "patch_queue": [],
            "test_report": {},
            "ci_status": {},
            "lint_status": {},
            "quality": QualityLevel.DRAFT,
            "feedback_gate": FeedbackGateStatus.OPEN,
            "model_router": ModelRouter.OLLAMA,
            "escalation_count": 0,
        }

        # Import any existing valid artifacts into the state (migration helper)
        from .utils import populate_all_artifacts_from_files

        initial_state = populate_all_artifacts_from_files(initial_state, self.repo_path)

        # Configure workflow execution
        from langchain_core.runnables import RunnableConfig

        config: RunnableConfig = {"configurable": {"thread_id": self.thread_id}}

        try:
            # Execute workflow
            logger.info("⚡ Executing enhanced workflow...")

            final_state = await self.app.ainvoke(initial_state, config=config)  # type: ignore

            logger.info("🎉 Enhanced workflow completed successfully")

            # Log final results
            self._log_workflow_results(final_state)

            return final_state

        except Exception as e:
            logger.error(f"❌ Enhanced workflow execution failed: {e}")
            raise

    def _log_workflow_results(self, final_state: dict):
        """Log summary of workflow results."""

        logger.info("📊 Workflow Results Summary:")
        logger.info(
            f"   🎯 Feature: {final_state.get('feature_description', 'Unknown')}"
        )
        logger.info(f"   📁 Repository: {final_state.get('repo_path', 'Unknown')}")
        logger.info(f"   🔧 Final Phase: {final_state.get('current_phase', 'Unknown')}")

        # Log artifacts created
        artifacts = final_state.get("artifacts_index", {})
        if artifacts:
            logger.info(f"   📄 Artifacts Created ({len(artifacts)}):")
            for name, path in artifacts.items():
                logger.info(f"      - {name}: {path}")

        # Log quality status
        quality = final_state.get("quality")
        if quality:
            logger.info(f"   ✅ Quality Status: {quality}")

        # Log PR integration status
        pr_number = final_state.get("pr_number")
        if pr_number:
            feedback_applied = final_state.get("pr_feedback_applied")
            if feedback_applied:
                logger.info(f"   📝 PR #{pr_number}: Feedback processed and applied")
            else:
                logger.info(f"   📋 PR #{pr_number}: Integrated, no feedback processed")

    async def get_node_status(self, step: WorkflowStep) -> dict:
        """Get status and configuration of a specific node.

        Args:
            step: Workflow step to check

        Returns:
            Node status and configuration information
        """

        if step not in self.node_definitions:
            return {"error": f"Node {step.value} not found"}

        node_def = self.node_definitions[step]

        return {
            "step": step.value,
            "description": node_def.description,
            "config": {
                "needs_code_access": node_def.config.needs_code_access,
                "model_preference": node_def.config.model_preference.value,
                "agents": [agent.value for agent in node_def.config.agents],
                "requires_code_changes": node_def.config.requires_code_changes,
                "requires_pr_feedback": node_def.config.requires_pr_feedback,
                "output_location": node_def.config.output_location.value,
                "pre_commit_checks": [
                    check.value for check in node_def.config.pre_commit_checks
                ],
            },
            "prompt_template_length": len(node_def.config.prompt_template),
            "agent_customizations": len(node_def.config.agent_prompt_customizations),
        }

    def list_all_nodes(self) -> dict:
        """List all configured nodes and their key properties.

        Returns:
            Summary of all workflow nodes
        """

        nodes_summary = {}

        for step, node_def in self.node_definitions.items():
            nodes_summary[step.value] = {
                "description": node_def.description,
                "agents": [agent.value for agent in node_def.config.agents],
                "model_router": node_def.config.get_model_router().value,
                "standard_workflows": {
                    "code_changes": node_def.config.requires_code_changes,
                    "pr_feedback": node_def.config.requires_pr_feedback,
                },
                "output_location": node_def.config.output_location.value,
            }

        return {
            "total_nodes": len(nodes_summary),
            "nodes": nodes_summary,
            "workflow_features": {
                "declarative_configuration": True,
                "integrated_code_quality": True,
                "pr_feedback_automation": True,
                "artifact_management": True,
            },
        }

    # Compatibility methods for old run.py interface
    async def extract_feature(self, state: dict) -> dict:
        """Extract and save the feature description to artifact file."""

        # Get feature description from multiple possible sources
        feature_description = state.get("feature_description", "")

        # If no feature description, try to extract from raw input or extracted feature
        if not feature_description:
            raw_input = state.get("raw_feature_input", "")
            extracted_feature = state.get("extracted_feature", "")

            # Prefer extracted_feature if available, otherwise use raw_feature_input
            if extracted_feature:
                feature_description = extracted_feature
            elif raw_input:
                feature_description = raw_input
            else:
                logger.warning("No feature description found in state")
                # Even with empty inputs, create an empty artifact
                feature_description = ""

            # Update the state with the extracted feature description
            state["feature_description"] = feature_description

        # Create artifact with proper base path using config function
        from .config import get_artifacts_path

        pr_number = state.get("pr_number")
        thread_id = state.get("thread_id")

        if pr_number:
            # For PR-based workflows, use the configured artifacts path with PR structure
            artifacts_base = get_artifacts_path("global")  # Use global for PR structure
            artifact_path = (
                artifacts_base.parent
                / f"pr-{pr_number}"
                / "analysis"
                / "feature_description.md"
            )
        elif thread_id:
            # Use thread-specific artifacts path
            artifacts_path = get_artifacts_path(thread_id)
            artifact_path = artifacts_path / "feature_description.md"
        else:
            # Fallback to global artifacts path
            artifacts_path = get_artifacts_path("global")
            artifact_path = artifacts_path / "feature_description.md"

        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_path.write_text(feature_description)

        # Update artifacts index
        if "artifacts_index" not in state:
            state["artifacts_index"] = {}
        state["artifacts_index"]["feature_description"] = str(artifact_path)

        logger.info(f"✅ Feature description saved: {artifact_path}")
        return state

    async def _agent_analysis(
        self, agent: Any, agent_type: str, context: dict | None = None
    ) -> tuple[str, str] | dict[str, Any]:
        """Call agent analysis method (compatibility with test interface)."""
        if hasattr(agent, "analyze"):
            result = await agent.analyze(context or {})
            if isinstance(result, str):
                return agent_type, result
            return result
        else:
            # Fallback for agents without analyze method
            return agent_type, f"Analysis from {agent_type}"

    async def extract_code_context(self, state: dict) -> dict:
        """Execute the extract_code_context node."""
        if WorkflowStep.EXTRACT_CODE_CONTEXT in self.node_definitions:
            node_def = self.node_definitions[WorkflowStep.EXTRACT_CODE_CONTEXT]
            configured_handler = self._create_configured_handler(
                node_def.handler, node_def.config
            )
            return await configured_handler(state)
        return state

    # TODO: Implement these step by step as we build the workflow
    async def parallel_design_exploration(self, state: dict) -> dict:
        """Run parallel design exploration with 4 Claude-based agents."""
        # Call the actual node handler
        from .nodes.parallel_design_exploration import (
            parallel_design_exploration_handler,
        )

        return await parallel_design_exploration_handler(state)

    async def design_synthesis(self, state: dict) -> dict:
        """Execute design synthesis to analyze agent consensus and conflicts."""
        from .nodes.design_synthesis import design_synthesis_handler

        return await design_synthesis_handler(state)

    async def architect_synthesis(self, state: dict) -> dict:
        """TODO: Implement architect synthesis."""
        logger.info("🚧 architect_synthesis: Not yet implemented")
        return state

    async def code_investigation(self, state: dict) -> dict:
        """TODO: Implement code investigation."""
        logger.info("🚧 code_investigation: Not yet implemented")
        return state

    async def human_review(self, state: dict) -> dict:
        """TODO: Implement human review."""
        logger.info("🚧 human_review: Not yet implemented")
        return state

    async def create_design_document(self, state: dict) -> dict:
        """TODO: Implement design document creation."""
        logger.info("🚧 create_design_document: Not yet implemented")
        return state

    async def iterate_design_document(self, state: dict) -> dict:
        """TODO: Implement design document iteration."""
        logger.info("🚧 iterate_design_document: Not yet implemented")
        return state

    async def finalize_design_document(self, state: dict) -> dict:
        """TODO: Implement design document finalization."""
        logger.info("🚧 finalize_design_document: Not yet implemented")
        return state

    async def create_skeleton(self, state: dict) -> dict:
        """TODO: Implement skeleton creation."""
        logger.info("🚧 create_skeleton: Not yet implemented")
        return state

    async def parallel_development(self, state: dict) -> dict:
        """TODO: Implement parallel development."""
        logger.info("🚧 parallel_development: Not yet implemented")
        return state

    async def reconciliation(self, state: dict) -> dict:
        """TODO: Implement reconciliation."""
        logger.info("🚧 reconciliation: Not yet implemented")
        return state

    async def component_tests(self, state: dict) -> dict:
        """TODO: Implement component tests."""
        logger.info("🚧 component_tests: Not yet implemented")
        return state

    async def integration_tests(self, state: dict) -> dict:
        """TODO: Implement integration tests."""
        logger.info("🚧 integration_tests: Not yet implemented")
        return state

    async def refinement(self, state: dict) -> dict:
        """TODO: Implement refinement."""
        logger.info("🚧 refinement: Not yet implemented")
        return state


# Factory function for easy workflow creation
def create_enhanced_workflow(
    repo_path: str,
    agents: dict[str, Any],
    codebase_analyzer: Any,
    github_integration: Any = None,
    **kwargs,
) -> EnhancedMultiAgentWorkflow:
    """Factory function to create an enhanced workflow instance.

    Args:
        repo_path: Path to the repository
        agents: Agent implementations
        codebase_analyzer: Codebase analysis interface
        github_integration: GitHub integration for PR feedback
        **kwargs: Additional workflow configuration

    Returns:
        Configured enhanced workflow instance
    """

    return EnhancedMultiAgentWorkflow(
        repo_path=repo_path,
        agents=agents,
        codebase_analyzer=codebase_analyzer,
        github_integration=github_integration,
        **kwargs,
    )
