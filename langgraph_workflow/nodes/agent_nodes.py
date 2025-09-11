"""Agent nodes wrapping existing agent interfaces."""

import asyncio
import logging
import sys
from pathlib import Path

# Add parent directories to path for imports
sys.path.append(str(Path(__file__).parent.parent.parent))
sys.path.append(str(Path(__file__).parent.parent.parent / "multi_agent_workflow"))

from langgraph_workflow.interfaces.agent_interface import AgentNodesInterface
from langgraph_workflow.state import AgentType, WorkflowState
from langgraph_workflow.utils.artifacts import ArtifactManager

# Import existing agent interfaces
from multi_agent_workflow.workflow_orchestrator import WorkflowOrchestrator

logger = logging.getLogger(__name__)


class AgentNodes(AgentNodesInterface):
    """Collection of agent nodes for the workflow graph."""

    def __init__(
        self, repo_name: str, repo_path: str, use_claude_code: bool | None = None
    ):
        """Initialize agent nodes with repository context."""
        self.repo_name = repo_name
        self.repo_path = Path(repo_path)
        self.orchestrator = WorkflowOrchestrator(repo_name, repo_path)
        self.artifact_manager = ArtifactManager(repo_path)

    async def analyze_codebase(self, state: WorkflowState) -> dict:
        """Senior Engineer analyzes codebase structure.

        This wraps the existing SeniorEngineerAgent.analyze_codebase().
        """
        logger.info("Starting codebase analysis with Senior Engineer")

        # Check if analysis already exists
        if state.get("codebase_analysis"):
            logger.info("Codebase analysis already exists, skipping")
            return state

        try:
            # Use existing orchestrator method
            analysis_result = await self.orchestrator.analyze_codebase()

            # Store in state
            state["codebase_analysis"] = analysis_result

            # Save to artifacts with feature organization
            artifact_path = self.artifact_manager.save_artifact(
                thread_id=state["thread_id"],
                artifact_type="analysis",
                filename="codebase_analysis.md",
                content=analysis_result.get("content", ""),
                feature_name=state.get("feature_name"),
            )

            # Update artifact index
            state["artifacts_index"]["codebase_analysis"] = str(artifact_path)

            # Add to messages window
            state["messages_window"].append(
                {
                    "role": "senior_engineer",
                    "content": "Completed codebase analysis",
                    "timestamp": Path(artifact_path).stat().st_mtime,
                }
            )

            logger.info("Codebase analysis completed successfully")

        except Exception as e:
            logger.error(f"Codebase analysis failed: {e}")
            state["messages_window"].append(
                {
                    "role": "system",
                    "content": f"Codebase analysis failed: {e!s}",
                    "error": True,
                }
            )

        return state

    async def analyze_feature(self, state: WorkflowState) -> dict:
        """All agents analyze the feature in parallel.

        This parallelizes the current Round 1 analysis.
        """
        logger.info("Starting multi-agent feature analysis")

        task_spec = state.get("task_spec", "")
        if not task_spec:
            logger.error("No task specification provided")
            return state

        # Build context for agents
        context = {
            "repo_path": state["repo_path"],
            "codebase_analysis_path": state["artifacts_index"].get("codebase_analysis"),
            "feature_spec": {
                "name": state.get("feature_name", "Unknown"),
                "description": task_spec,
            },
        }

        # Create analysis tasks for all agents
        analysis_tasks = []
        for agent_type in AgentType:
            agent = self.orchestrator.agents.get(agent_type.value)
            if agent:
                task = agent.analyze_task(context, task_spec)
                analysis_tasks.append((agent_type, task))

        # Run analyses in parallel
        try:
            # Execute all analyses concurrently
            for agent_type, task in analysis_tasks:
                result = await asyncio.create_task(
                    asyncio.coroutine(task)()
                    if asyncio.iscoroutine(task)
                    else asyncio.to_thread(lambda: task)
                )

                if result.get("status") == "success":
                    # Store analysis in state
                    state["agent_analyses"][agent_type.value] = result.get(
                        "analysis", ""
                    )

                    # Save to artifacts
                    artifact_path = self.artifact_manager.save_artifact(
                        thread_id=state["thread_id"],
                        artifact_type="analysis",
                        filename=f"{agent_type.value}_analysis.md",
                        content=result.get("analysis", ""),
                        feature_name=state.get("feature_name"),
                    )

                    state["artifacts_index"][f"{agent_type.value}_analysis"] = str(
                        artifact_path
                    )

                    logger.info(f"{agent_type.value} analysis completed")
                else:
                    logger.error(
                        f"{agent_type.value} analysis failed: {result.get('error')}"
                    )

            state["messages_window"].append(
                {
                    "role": "system",
                    "content": "All agents completed feature analysis",
                    "agents": list(state["agent_analyses"].keys()),
                }
            )

        except Exception as e:
            logger.error(f"Feature analysis failed: {e}")
            state["messages_window"].append(
                {
                    "role": "system",
                    "content": f"Feature analysis failed: {e!s}",
                    "error": True,
                }
            )

        return state

    async def consolidate_design(self, state: WorkflowState) -> dict:
        """Agents review and consolidate into unified design.

        This implements the current Round 2 workflow.
        """
        logger.info("Starting design consolidation")

        # Check if we have all agent analyses
        if len(state.get("agent_analyses", {})) < 4:
            logger.warning("Not all agent analyses available for consolidation")

        try:
            # Build context with analyses
            context = {
                "repo_path": state["repo_path"],
                "feature_name": state.get("feature_name"),
                "agent_analyses": state.get("agent_analyses", {}),
            }

            # Use orchestrator's consolidation logic
            from multi_agent_workflow.conflict_resolver import ConflictResolver

            resolver = ConflictResolver(self.orchestrator.architect_persona)

            # Identify conflicts
            conflicts = await self._identify_design_conflicts(state["agent_analyses"])
            state["design_conflicts"] = conflicts

            # Resolve conflicts and create unified design
            resolution_prompt = self._build_resolution_prompt(
                conflicts, state["agent_analyses"]
            )
            consolidated = self.orchestrator.architect_persona.ask(resolution_prompt)

            state["consolidated_design"] = consolidated

            # Save consolidated design
            artifact_path = self.artifact_manager.save_artifact(
                thread_id=state["thread_id"],
                artifact_type="design",
                filename="consolidated_design.md",
                content=consolidated,
                feature_name=state.get("feature_name"),
            )

            state["artifacts_index"]["consolidated_design"] = str(artifact_path)

            state["messages_window"].append(
                {
                    "role": "architect",
                    "content": f"Design consolidated with {len(conflicts)} conflicts resolved",
                }
            )

            logger.info("Design consolidation completed")

        except Exception as e:
            logger.error(f"Design consolidation failed: {e}")
            state["messages_window"].append(
                {
                    "role": "system",
                    "content": f"Design consolidation failed: {e!s}",
                    "error": True,
                }
            )

        return state

    async def incorporate_feedback(self, state: WorkflowState) -> dict:
        """Process GitHub PR feedback and update design.

        This replaces step3_finalize_design_document.py functionality.
        """
        logger.info("Incorporating PR feedback into design")

        pr_comments = state.get("pr_comments", [])
        if not pr_comments:
            logger.info("No PR comments to incorporate")
            return state

        try:
            # Categorize feedback
            feedback_categories = self._categorize_feedback(pr_comments)

            # Build feedback incorporation prompt
            feedback_summary = self._create_feedback_summary(feedback_categories)

            update_prompt = f"""
## Task: Update the Complete Design Document Based on PR Feedback

Current Design Document:
{state.get('consolidated_design', '')}

GitHub Feedback to Address:
{feedback_summary}

Instructions:
1. Start with the ENTIRE current design document above
2. For each piece of feedback, update the relevant sections to address the concerns
3. Keep ALL existing content that doesn't need changes
4. Return the COMPLETE updated design document (not just the changes)
"""

            # Use developer agent to update design
            developer = self.orchestrator.agents["developer"]
            result = await developer.implement_code(
                {"prompt": update_prompt}, update_prompt
            )

            finalized_design = result.get("content", "")
            state["finalized_design"] = finalized_design

            # Save finalized design
            artifact_path = self.artifact_manager.save_artifact(
                thread_id=state["thread_id"],
                artifact_type="design",
                filename="finalized_design.md",
                content=finalized_design,
                feature_name=state.get("feature_name"),
            )

            state["artifacts_index"]["finalized_design"] = str(artifact_path)

            # Mark feedback as addressed
            for comment in pr_comments:
                comment_id = comment.get("id")
                if comment_id:
                    state["feedback_addressed"][str(comment_id)] = True

            state["messages_window"].append(
                {
                    "role": "system",
                    "content": f"Incorporated {len(pr_comments)} PR comments into design",
                }
            )

            logger.info("Feedback incorporation completed")

        except Exception as e:
            logger.error(f"Feedback incorporation failed: {e}")
            state["messages_window"].append(
                {
                    "role": "system",
                    "content": f"Feedback incorporation failed: {e!s}",
                    "error": True,
                }
            )

        return state

    async def create_skeleton(self, state: WorkflowState) -> dict:
        """Architect creates implementation skeleton.

        From step4 enhanced implementation.
        """
        logger.info("Creating architecture skeleton")

        design_content = state.get("finalized_design") or state.get(
            "consolidated_design", ""
        )
        if not design_content:
            logger.error("No design document available for skeleton creation")
            return state

        prompt = f"""Create a complete architecture skeleton based on this design:

{design_content}

SKELETON REQUIREMENTS:
1. All class definitions with method signatures (NO implementation, just pass)
2. Complete type hints using modern Python syntax (| None, dict, list)
3. Docstrings for all classes and methods
4. Import statements
5. Abstract base classes where needed
6. Interface definitions for dependency injection

CRITICAL:
- NO method implementations - only signatures with pass
- Follow existing codebase patterns from the codebase analysis
- Use dependency injection for testability
- Create all necessary files in proper structure

Provide complete skeleton code for each file that needs to be created."""

        try:
            architect = self.orchestrator.agents["architect"]
            result = await architect.implement_code({"design": design_content}, prompt)

            skeleton = result.get("content", "")

            # Parse skeleton into individual files
            # This is simplified - would need proper parsing logic
            state["skeleton_code"] = {"main.py": skeleton}

            # Save skeleton
            artifact_path = self.artifact_manager.save_artifact(
                thread_id=state["thread_id"],
                artifact_type="code",
                filename="architecture_skeleton.py",
                content=skeleton,
                feature_name=state.get("feature_name"),
            )

            state["artifacts_index"]["skeleton"] = str(artifact_path)

            state["messages_window"].append(
                {"role": "architect", "content": "Architecture skeleton created"}
            )

            logger.info("Skeleton creation completed")

        except Exception as e:
            logger.error(f"Skeleton creation failed: {e}")
            state["messages_window"].append(
                {
                    "role": "system",
                    "content": f"Skeleton creation failed: {e!s}",
                    "error": True,
                }
            )

        return state

    async def create_tests(self, state: WorkflowState) -> dict:
        """Tester creates comprehensive test suite."""
        logger.info("Creating test suite")

        skeleton = state.get("skeleton_code", {})
        if not skeleton:
            logger.error("No skeleton available for test creation")
            return state

        skeleton_content = "\n".join(skeleton.values())

        prompt = f"""Create a comprehensive test suite for this skeleton:

{skeleton_content}

TEST REQUIREMENTS:
1. Unit tests for every class and method
2. Integration tests for component interactions
3. Mock classes using inheritance (NO mocking frameworks)
4. Edge cases and error conditions
5. Use pytest framework
6. Follow existing test patterns from tests/ directory

CRITICAL:
- Create mock classes in tests/mocks/ following dependency injection
- Use setup/teardown methods appropriately
- Test all success paths, error paths, and edge cases
- Include test data and fixtures

Provide complete, runnable test code."""

        try:
            tester = self.orchestrator.agents["tester"]
            result = await tester.create_tests({"skeleton": skeleton_content}, prompt)

            tests = result.get("content", "")

            # Parse tests into files
            state["test_code"] = {"test_main.py": tests}

            # Save tests
            artifact_path = self.artifact_manager.save_artifact(
                thread_id=state["thread_id"],
                artifact_type="tests",
                filename="test_suite.py",
                content=tests,
                feature_name=state.get("feature_name"),
            )

            state["artifacts_index"]["tests"] = str(artifact_path)

            state["messages_window"].append(
                {"role": "tester", "content": "Comprehensive test suite created"}
            )

            logger.info("Test creation completed")

        except Exception as e:
            logger.error(f"Test creation failed: {e}")
            state["messages_window"].append(
                {
                    "role": "system",
                    "content": f"Test creation failed: {e!s}",
                    "error": True,
                }
            )

        return state

    async def implement_code(self, state: WorkflowState) -> dict:
        """Developer implements based on skeleton and design."""
        logger.info("Implementing code")

        skeleton = state.get("skeleton_code", {})
        if not skeleton:
            logger.error("No skeleton available for implementation")
            return state

        skeleton_content = "\n".join(skeleton.values())

        prompt = f"""Implement complete functionality for this skeleton:

{skeleton_content}

IMPLEMENTATION REQUIREMENTS:
1. Implement ALL method bodies (replace pass statements)
2. Follow exact signatures from skeleton
3. Use proper error handling and logging
4. Follow existing codebase patterns
5. Include type checking and validation
6. CRITICAL: Do NOT look at or reference ANY test files

Focus on implementing clean, working code based solely on the skeleton and design document."""

        try:
            developer = self.orchestrator.agents["developer"]
            result = await developer.implement_code(
                {"skeleton": skeleton_content}, prompt
            )

            implementation = result.get("content", "")

            # Parse implementation into files
            state["implementation_code"] = {"main.py": implementation}

            # Save implementation
            artifact_path = self.artifact_manager.save_artifact(
                thread_id=state["thread_id"],
                artifact_type="code",
                filename="implementation.py",
                content=implementation,
                feature_name=state.get("feature_name"),
            )

            state["artifacts_index"]["implementation"] = str(artifact_path)

            state["messages_window"].append(
                {"role": "developer", "content": "Code implementation completed"}
            )

            logger.info("Implementation completed")

        except Exception as e:
            logger.error(f"Implementation failed: {e}")
            state["messages_window"].append(
                {
                    "role": "system",
                    "content": f"Implementation failed: {e!s}",
                    "error": True,
                }
            )

        return state

    async def fix_failures(self, state: WorkflowState) -> dict:
        """Fix test/lint failures with escalation logic."""
        logger.info("Fixing test failures")

        test_results = state.get("test_results", {})
        if test_results.get("passed"):
            logger.info("All tests passing, no fixes needed")
            return state

        # Increment retry count
        state["retry_count"] = state.get("retry_count", 0) + 1

        # Check if we should escalate
        if state["retry_count"] >= 2:
            state["escalation_needed"] = True
            logger.info(f"Escalating to Claude after {state['retry_count']} attempts")

        try:
            # Analyze failures
            failure_info = test_results.get("stderr", "") + test_results.get(
                "stdout", ""
            )

            prompt = f"""Fix these test failures:

{failure_info}

Current Implementation:
{state.get('implementation_code', {}).get('main.py', '')}

Provide the corrected implementation that fixes all test failures."""

            # Use senior engineer for fixes
            senior_engineer = self.orchestrator.agents["senior_engineer"]
            result = await senior_engineer.implement_code(
                {"failures": failure_info}, prompt
            )

            fixed_code = result.get("content", "")

            # Update implementation
            state["implementation_code"]["main.py"] = fixed_code

            # Save fixed implementation
            artifact_path = self.artifact_manager.save_artifact(
                thread_id=state["thread_id"],
                artifact_type="code",
                filename=f"implementation_fix_{state['retry_count']}.py",
                content=fixed_code,
                feature_name=state.get("feature_name"),
            )

            state["artifacts_index"][f"fix_{state['retry_count']}"] = str(artifact_path)

            state["messages_window"].append(
                {
                    "role": "senior_engineer",
                    "content": f"Applied fixes (attempt {state['retry_count']})",
                }
            )

            logger.info(f"Fixes applied (attempt {state['retry_count']})")

        except Exception as e:
            logger.error(f"Fix application failed: {e}")
            state["messages_window"].append(
                {
                    "role": "system",
                    "content": f"Fix application failed: {e!s}",
                    "error": True,
                }
            )

        return state

    # Helper methods

    async def _identify_design_conflicts(self, analyses: dict) -> list[dict]:
        """Identify conflicts between agent analyses."""
        conflicts = []

        # Simple conflict detection - would be more sophisticated in practice
        topics = ["architecture", "implementation", "testing", "patterns"]

        for topic in topics:
            divergent_views = []
            for agent, analysis in analyses.items():
                if topic in analysis.lower():
                    divergent_views.append(
                        {
                            "agent": agent,
                            "view": analysis[:200],  # First 200 chars
                        }
                    )

            if len(divergent_views) > 1:
                conflicts.append({"topic": topic, "views": divergent_views})

        return conflicts

    def _build_resolution_prompt(self, conflicts: list[dict], analyses: dict) -> str:
        """Build prompt for conflict resolution."""
        prompt = "Create a unified design that resolves these conflicts:\n\n"

        for conflict in conflicts:
            prompt += f"Topic: {conflict['topic']}\n"
            for view in conflict["views"]:
                prompt += f"  - {view['agent']}: {view['view']}\n"
            prompt += "\n"

        prompt += "\nProvide a consolidated design that addresses all perspectives."
        return prompt

    def _categorize_feedback(self, comments: list[dict]) -> dict[str, list]:
        """Categorize PR comments by type."""
        categories = {
            "architecture": [],
            "implementation": [],
            "testing": [],
            "security": [],
            "performance": [],
            "general": [],
        }

        for comment in comments:
            body = comment.get("body", "").lower()

            if any(word in body for word in ["architecture", "design", "structure"]):
                categories["architecture"].append(comment)
            elif any(word in body for word in ["implement", "code", "api"]):
                categories["implementation"].append(comment)
            elif any(word in body for word in ["test", "coverage", "qa"]):
                categories["testing"].append(comment)
            elif any(word in body for word in ["security", "auth", "permission"]):
                categories["security"].append(comment)
            elif any(word in body for word in ["performance", "scale", "optimize"]):
                categories["performance"].append(comment)
            else:
                categories["general"].append(comment)

        return categories

    def _create_feedback_summary(self, categories: dict[str, list]) -> str:
        """Create summary of categorized feedback."""
        summary_parts = []

        for category, comments in categories.items():
            if comments:
                summary_parts.append(f"### {category.title()} Feedback\n")
                for comment in comments:
                    author = comment.get("user", {}).get("login", "Unknown")
                    body = comment.get("body", "")
                    summary_parts.append(f"- **{author}**: {body}\n")
                summary_parts.append("")

        return "\n".join(summary_parts)
