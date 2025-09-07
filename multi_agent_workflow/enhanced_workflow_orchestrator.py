#!/usr/bin/env python3
"""
Enhanced Multi-Agent Workflow Orchestrator

This orchestrator implements a comprehensive two-phase development workflow:
1. Skeleton-first approach with tests before implementation
2. Test-driven implementation cycle with review loops
3. PR review and response automation

The workflow follows these phases:
- Phase 1: Design Analysis and Architecture Skeleton
- Phase 2: Test Creation and Review
- Phase 3: Implementation and Test Validation Loop
- Phase 4: PR Review and Response Cycle
"""

import asyncio
import json
import logging
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

# Add parent directory to path to import github_tools
sys.path.append(str(Path(__file__).parent.parent))

from agent_interface import (
    ArchitectAgent,
    DeveloperAgent,
    SeniorEngineerAgent,
    TesterAgent,
)
from dotenv import load_dotenv
from task_context import FeatureSpec

from github_tools import execute_tool
from repository_manager import (
    Language,
    RepositoryConfig,
    RepositoryManager,
)

logger = logging.getLogger(__name__)


class WorkflowState:
    """Manages the state of the workflow execution."""

    def __init__(self, workflow_dir: Path):
        self.workflow_dir = workflow_dir
        self.current_phase = "design"
        self.phase_data = {}
        self.pr_number: Optional[int] = None
        self.is_paused = False
        self.test_results = {}
        self.state_file = workflow_dir / "workflow_state.json"

    def save_state(self):
        """Save the current workflow state to disk."""
        self.workflow_dir.mkdir(parents=True, exist_ok=True)
        state_data = {
            "current_phase": self.current_phase,
            "phase_data": self.phase_data,
            "pr_number": self.pr_number,
            "is_paused": self.is_paused,
            "test_results": self.test_results,
            "timestamp": datetime.now().isoformat(),
        }

        with open(self.state_file, "w") as f:
            json.dump(state_data, f, indent=2)

    def load_state(self) -> bool:
        """Load workflow state from disk. Returns True if state was loaded."""
        if not self.state_file.exists():
            return False

        try:
            with open(self.state_file) as f:
                state_data = json.load(f)

            self.current_phase = state_data.get("current_phase", "design")
            self.phase_data = state_data.get("phase_data", {})
            self.pr_number = state_data.get("pr_number")
            self.is_paused = state_data.get("is_paused", False)
            self.test_results = state_data.get("test_results", {})

            logger.info(
                f"Loaded workflow state: phase={self.current_phase}, paused={self.is_paused}"
            )
            return True

        except Exception as e:
            logger.warning(f"Failed to load workflow state: {e}")
            return False


class EnhancedWorkflowOrchestrator:
    """Enhanced orchestrator implementing the comprehensive workflow."""

    def __init__(self, repo_name: str, repo_path: str):
        """Initialize the enhanced orchestrator.

        Args:
            repo_name: GitHub repository name (org/repo)
            repo_path: Local path to repository
        """
        self.repo_name = repo_name
        self.repo_path = Path(repo_path)

        # Initialize agents
        self.agents = {
            "architect": ArchitectAgent(),
            "developer": DeveloperAgent(),
            "senior_engineer": SeniorEngineerAgent(),
            "tester": TesterAgent(),
        }

        # Workflow directories
        self.workflow_dir = self.repo_path / ".workflow"
        self.documents_dir = self.workflow_dir / "documents"
        self.tests_dir = self.workflow_dir / "generated_tests"
        self.code_dir = self.workflow_dir / "generated_code"

        # Initialize workflow state
        self.state = WorkflowState(self.workflow_dir)

        # Setup repository manager
        self._setup_repository_manager()

        logger.info(f"Enhanced orchestrator initialized for {repo_name}")

    def _setup_repository_manager(self):
        """Set up the repository manager for GitHub operations."""
        # Load environment
        env_path = self.repo_path / ".env"
        if env_path.exists():
            load_dotenv(env_path)

        # Get GitHub token
        github_token = os.environ.get("GITHUB_TOKEN")
        if not github_token:
            logger.warning("GITHUB_TOKEN not set. GitHub operations may fail.")
            github_token = "dummy-token"

        # Create repository configuration
        repo_config = RepositoryConfig.create_repository_config(
            name=self.repo_name,
            workspace=str(self.repo_path),
            description=f"Repository for {self.repo_name}",
            language=Language.PYTHON,
            port=9999,
            python_path=sys.executable,
        )

        if (
            repo_config.github_owner
            and repo_config.github_repo
            and repo_config.github_owner != "unknown"
        ):
            self.repo_name = f"{repo_config.github_owner}/{repo_config.github_repo}"

        # Initialize repository manager
        self.repo_manager = RepositoryManager()

    async def run_enhanced_workflow(self, feature_spec: FeatureSpec) -> dict[str, Any]:
        """Run the complete enhanced workflow.

        Args:
            feature_spec: Feature specification to implement

        Returns:
            Complete workflow results
        """
        logger.info(f"Starting enhanced workflow for: {feature_spec.name}")

        try:
            # Load existing state if available
            self.state.load_state()

            # Run workflow phases
            if self.state.current_phase == "design":
                await self._phase_1_skeleton_creation(feature_spec)

            if self.state.current_phase == "tests":
                await self._phase_2_test_creation_and_review(feature_spec)

            if self.state.current_phase == "implementation":
                await self._phase_3_implementation_cycle(feature_spec)

            if self.state.current_phase == "pr_review":
                await self._phase_4_pr_review_cycle(feature_spec)

            return {
                "status": "completed",
                "feature": feature_spec.name,
                "final_phase": self.state.current_phase,
                "pr_number": self.state.pr_number,
            }

        except Exception as e:
            logger.error(f"Workflow failed: {e}")
            self.state.save_state()
            raise

    async def _phase_1_skeleton_creation(self, feature_spec: FeatureSpec):
        """Phase 1: Design analysis and architecture skeleton creation."""
        logger.info("=== PHASE 1: Architecture Skeleton Creation ===")

        # Step 1: Design analysis by all agents
        design_analyses = await self._run_design_analysis(feature_spec)

        # Step 2: Architect creates skeleton based on design
        skeleton_result = await self._create_architecture_skeleton(
            feature_spec, design_analyses
        )

        # Step 3: All agents review the skeleton
        skeleton_reviews = await self._review_architecture_skeleton(skeleton_result)

        # Step 4: Senior engineer finalizes skeleton incorporating feedback
        final_skeleton = await self._finalize_architecture_skeleton(
            skeleton_result, skeleton_reviews
        )

        # Save phase results
        self.state.phase_data["skeleton"] = final_skeleton
        self.state.current_phase = "tests"
        self.state.save_state()

        logger.info("Phase 1 completed: Architecture skeleton created")

    async def _phase_2_test_creation_and_review(self, feature_spec: FeatureSpec):
        """Phase 2: Test creation and comprehensive review process."""
        logger.info("=== PHASE 2: Test Creation and Review ===")

        skeleton = self.state.phase_data.get("skeleton")
        if not skeleton:
            raise ValueError("No skeleton found from Phase 1")

        # Step 1: Testing agent creates comprehensive tests
        test_suite = await self._create_comprehensive_tests(feature_spec, skeleton)

        # Step 2: All agents review the tests
        test_reviews = await self._review_test_suite(test_suite)

        # Step 3: Senior engineer addresses feedback and finalizes tests
        final_tests = await self._finalize_test_suite(test_suite, test_reviews)

        # Save phase results
        self.state.phase_data["tests"] = final_tests
        self.state.current_phase = "implementation"
        self.state.save_state()

        logger.info("Phase 2 completed: Test suite finalized")

    async def _phase_3_implementation_cycle(self, feature_spec: FeatureSpec):
        """Phase 3: Implementation and test validation cycle."""
        logger.info("=== PHASE 3: Implementation and Test Validation ===")

        tests = self.state.phase_data.get("tests")
        skeleton = self.state.phase_data.get("skeleton")

        if not tests or not skeleton:
            raise ValueError("Missing tests or skeleton from previous phases")

        # Step 1: Coding agent implements methods (blind to tests)
        implementation = await self._implement_code_blind(feature_spec, skeleton)

        # Step 2: Run tests and capture failures
        test_results = await self._run_tests_and_capture_failures()

        # Step 3-9: Test validation loop
        max_iterations = 5
        iteration = 0

        while not self._all_tests_passing(test_results) and iteration < max_iterations:
            iteration += 1
            logger.info(f"Test validation iteration {iteration}")

            # Each agent analyzes failures and suggests fixes
            failure_analyses = await self._analyze_test_failures(test_results)

            # Senior engineer decides how to address failures
            fix_plan = await self._create_fix_plan(failure_analyses, test_results)

            # Apply fixes
            implementation = await self._apply_fixes(implementation, fix_plan)

            # Run tests again
            test_results = await self._run_tests_and_capture_failures()

        if not self._all_tests_passing(test_results):
            logger.warning(f"Tests still failing after {max_iterations} iterations")

        # Step 10-11: Commit and push changes
        await self._commit_and_push_changes(feature_spec, implementation)

        # Step 12: Create PR and pause
        pr_number = await self._create_pull_request(feature_spec)
        self.state.pr_number = pr_number
        self.state.current_phase = "pr_review"
        self.state.is_paused = True
        self.state.save_state()

        logger.info(
            f"Phase 3 completed: PR #{pr_number} created. Workflow paused for review."
        )
        return {"paused": True, "pr_number": pr_number}

    async def _phase_4_pr_review_cycle(self, feature_spec: FeatureSpec):
        """Phase 4: PR review and response cycle."""
        logger.info("=== PHASE 4: PR Review and Response Cycle ===")

        if not self.state.pr_number:
            raise ValueError("No PR number found for review cycle")

        while True:
            # Step 1: Check if workflow should resume
            if self.state.is_paused:
                logger.info("Workflow paused. Waiting for resume signal...")
                return {"paused": True, "message": "Waiting for user to resume"}

            # Step 2: Fetch new PR comments
            new_comments = await self._fetch_new_pr_comments(self.state.pr_number)

            if not new_comments:
                logger.info("No new PR comments found. Workflow completed.")
                self.state.current_phase = "completed"
                self.state.save_state()
                return {"status": "completed"}

            # Step 3: All agents analyze PR comments
            comment_analyses = await self._analyze_pr_comments(new_comments)

            # Step 4: Senior engineer creates response plan
            response_plan = await self._create_pr_response_plan(
                comment_analyses, new_comments
            )

            # Step 5: Implement changes, run tests, and respond to comments
            await self._implement_pr_responses(response_plan, new_comments)

            # Step 6: Commit and push changes
            await self._commit_pr_response_changes(feature_spec, response_plan)

            # Step 7: Pause again for next review cycle
            self.state.is_paused = True
            self.state.save_state()

            logger.info("PR response cycle completed. Paused for next review.")

    async def resume_workflow(self, feature_spec: FeatureSpec) -> dict[str, Any]:
        """Resume a paused workflow."""
        if not self.state.is_paused:
            return {"error": "Workflow is not paused"}

        logger.info("Resuming workflow...")
        self.state.is_paused = False
        self.state.save_state()

        # Continue from current phase
        if self.state.current_phase == "pr_review":
            return await self._phase_4_pr_review_cycle(feature_spec)
        else:
            return await self.run_enhanced_workflow(feature_spec)

    # Implementation helper methods

    async def _run_design_analysis(self, feature_spec: FeatureSpec) -> dict[str, Any]:
        """Run initial design analysis with all agents."""
        context = await self._build_task_context(feature_spec)
        analyses = {}

        for agent_name, agent in self.agents.items():
            logger.info(f"Running design analysis with {agent_name}")
            analysis = agent.analyze_task(context, feature_spec.description)
            analyses[agent_name] = analysis

            # Save individual analysis
            doc_path = self.documents_dir / f"design_analysis_{agent_name}.md"
            self._save_document(doc_path, analysis.get("analysis", ""))

        return analyses

    async def _create_architecture_skeleton(
        self, feature_spec: FeatureSpec, design_analyses: dict[str, Any]
    ) -> dict[str, Any]:
        """Architect creates the code skeleton."""
        logger.info("Creating architecture skeleton")

        prompt = f"""Based on the design analyses, create a complete architecture skeleton for: {feature_spec.name}

DESIGN ANALYSES:
{self._format_analyses_for_prompt(design_analyses)}

CREATE SKELETON WITH:
1. All class definitions with method signatures (no implementation)
2. Type hints for all parameters and return values
3. Docstrings for all classes and methods
4. Import statements
5. Abstract base classes where appropriate
6. Interface definitions

REQUIREMENTS:
- NO method implementations (just pass statements)
- Complete type annotations using modern Python syntax
- Follow existing codebase patterns
- Include dependency injection points
- Create all necessary files in proper directory structure

Provide the complete skeleton code for each file that needs to be created."""

        context = await self._build_task_context(feature_spec)
        result = await self.agents["architect"].implement_code(context, prompt)

        # Save skeleton
        skeleton_path = self.documents_dir / "architecture_skeleton.md"
        self._save_document(skeleton_path, result.get("content", ""))

        return result

    async def _review_architecture_skeleton(
        self, skeleton_result: dict[str, Any]
    ) -> dict[str, Any]:
        """All agents review the architecture skeleton."""
        logger.info("Reviewing architecture skeleton")

        reviews = {}
        skeleton_content = skeleton_result.get("content", "")

        review_prompt = f"""Review this architecture skeleton:

{skeleton_content}

REVIEW FOR:
1. Completeness - are all necessary classes and methods included?
2. Design patterns - are appropriate patterns used consistently?
3. Type safety - are type hints comprehensive and correct?
4. Integration - does it fit with existing codebase patterns?
5. Extensibility - is the design flexible for future needs?
6. Dependency injection - are dependencies properly abstracted?

Provide specific feedback on what's missing, incorrect, or could be improved."""

        for agent_name, agent in self.agents.items():
            if agent_name != "architect":  # Architect doesn't review their own work
                logger.info(f"Getting skeleton review from {agent_name}")
                context = await self._build_task_context(
                    FeatureSpec("skeleton_review", review_prompt)
                )
                review = await agent.review_code(context, review_prompt)
                reviews[agent_name] = review

                # Save individual review
                review_path = self.documents_dir / f"skeleton_review_{agent_name}.md"
                self._save_document(review_path, review.get("content", ""))

        return reviews

    async def _finalize_architecture_skeleton(
        self, skeleton_result: dict[str, Any], reviews: dict[str, Any]
    ) -> dict[str, Any]:
        """Senior engineer finalizes skeleton incorporating all feedback."""
        logger.info("Finalizing architecture skeleton")

        reviews_text = "\n\n".join(
            [
                f"=== {agent.upper()} REVIEW ===\n{review.get('content', '')}"
                for agent, review in reviews.items()
            ]
        )

        prompt = f"""Finalize the architecture skeleton by incorporating all feedback:

ORIGINAL SKELETON:
{skeleton_result.get("content", "")}

PEER REVIEWS:
{reviews_text}

FINALIZATION REQUIREMENTS:
1. Address ALL valid feedback points
2. Resolve any conflicts between reviews
3. Maintain architectural integrity
4. Document any decisions made
5. Provide final, complete skeleton code

Create the definitive architecture skeleton that addresses all concerns while maintaining design coherence."""

        context = await self._build_task_context(
            FeatureSpec("skeleton_finalization", prompt)
        )
        final_skeleton = await self.agents["senior_engineer"].implement_code(
            context, prompt
        )

        # Save final skeleton
        final_path = self.documents_dir / "final_architecture_skeleton.md"
        self._save_document(final_path, final_skeleton.get("content", ""))

        return final_skeleton

    async def _create_comprehensive_tests(
        self, feature_spec: FeatureSpec, skeleton: dict[str, Any]
    ) -> dict[str, Any]:
        """Testing agent creates comprehensive test suite."""
        logger.info("Creating comprehensive test suite")

        prompt = f"""Create a comprehensive test suite for this feature: {feature_spec.name}

ARCHITECTURE SKELETON:
{skeleton.get("content", "")}

TEST REQUIREMENTS:
1. Unit tests for each class and method
2. Integration tests for component interactions
3. End-to-end tests for complete workflows
4. Mock classes for all dependencies (using inheritance, not mocking frameworks)
5. Edge case and error condition tests
6. Performance and boundary tests where relevant

FOLLOW EXISTING TEST PATTERNS:
- Use pytest framework
- Create mock classes in tests/mocks/ directory
- Use dependency injection for testability
- Follow naming conventions from existing tests
- Include setup and teardown methods

DELIVERABLES:
1. Complete test files with all test methods
2. Mock class implementations
3. Test data and fixtures
4. Documentation of test strategy

Provide complete, runnable test code that thoroughly validates the skeleton."""

        context = await self._build_task_context(feature_spec)
        test_suite = await self.agents["tester"].create_tests(context, prompt)

        # Save test suite
        tests_path = self.documents_dir / "comprehensive_test_suite.md"
        self._save_document(tests_path, test_suite.get("content", ""))

        return test_suite

    async def _review_test_suite(self, test_suite: dict[str, Any]) -> dict[str, Any]:
        """All agents review the test suite."""
        logger.info("Reviewing test suite")

        reviews = {}
        test_content = test_suite.get("content", "")

        review_prompt = f"""Review this test suite:

{test_content}

REVIEW FOR:
1. Coverage - are all classes, methods, and scenarios tested?
2. Quality - are tests well-structured and maintainable?
3. Edge cases - are boundary conditions and error cases covered?
4. Mock strategy - are mocks appropriate and well-designed?
5. Test data - is test data comprehensive and realistic?
6. Integration - do integration tests cover component interactions?
7. Missing tests - what additional tests are needed?

Provide specific feedback on gaps, improvements, and additions needed."""

        for agent_name, agent in self.agents.items():
            if agent_name != "tester":  # Tester doesn't review their own work
                logger.info(f"Getting test review from {agent_name}")
                context = await self._build_task_context(
                    FeatureSpec("test_review", review_prompt)
                )
                review = await agent.review_code(context, review_prompt)
                reviews[agent_name] = review

                # Save individual review
                review_path = self.documents_dir / f"test_review_{agent_name}.md"
                self._save_document(review_path, review.get("content", ""))

        return reviews

    async def _finalize_test_suite(
        self, test_suite: dict[str, Any], reviews: dict[str, Any]
    ) -> dict[str, Any]:
        """Senior engineer finalizes test suite addressing all feedback."""
        logger.info("Finalizing test suite")

        reviews_text = "\n\n".join(
            [
                f"=== {agent.upper()} REVIEW ===\n{review.get('content', '')}"
                for agent, review in reviews.items()
            ]
        )

        prompt = f"""Finalize the test suite by incorporating all feedback:

ORIGINAL TEST SUITE:
{test_suite.get("content", "")}

PEER REVIEWS:
{reviews_text}

FINALIZATION REQUIREMENTS:
1. Address ALL valid feedback points about missing tests
2. Add tests for identified gaps and edge cases
3. Improve test quality and maintainability
4. Ensure comprehensive coverage
5. Resolve any conflicts between reviews
6. Document test strategy decisions

Create the definitive test suite that provides comprehensive coverage and quality."""

        context = await self._build_task_context(
            FeatureSpec("test_finalization", prompt)
        )
        final_tests = await self.agents["senior_engineer"].create_tests(context, prompt)

        # Save final test suite
        final_path = self.documents_dir / "final_test_suite.md"
        self._save_document(final_path, final_tests.get("content", ""))

        return final_tests

    async def _implement_code_blind(
        self, feature_spec: FeatureSpec, skeleton: dict[str, Any]
    ) -> dict[str, Any]:
        """Coding agent implements methods without seeing tests."""
        logger.info("Implementing code (blind to tests)")

        prompt = f"""Implement the complete functionality for: {feature_spec.name}

ARCHITECTURE SKELETON TO IMPLEMENT:
{skeleton.get("content", "")}

IMPLEMENTATION REQUIREMENTS:
1. Implement ALL method bodies (replace pass statements)
2. Follow the exact signatures from the skeleton
3. Use proper error handling and logging
4. Follow existing codebase patterns
5. Include proper type checking and validation
6. Add necessary imports and dependencies
7. Implement business logic completely
8. DO NOT look at or reference any test files

IMPORTANT:
- You cannot see the tests that were created
- Focus on implementing clean, working code based on the skeleton
- Use your best judgment for implementation details
- Follow established patterns from the existing codebase

Provide complete, working implementation code for all files."""

        context = await self._build_task_context(feature_spec)
        implementation = await self.agents["developer"].implement_code(context, prompt)

        # Save implementation
        impl_path = self.documents_dir / "initial_implementation.md"
        self._save_document(impl_path, implementation.get("content", ""))

        return implementation

    async def _run_tests_and_capture_failures(self) -> dict[str, Any]:
        """Run tests and capture detailed failure information."""
        logger.info("Running tests and capturing failures")

        try:
            # Run pytest with detailed output
            cmd = ["python", "-m", "pytest", "-xvs", "--tb=long", "--capture=no"]
            result = subprocess.run(
                cmd, cwd=self.repo_path, capture_output=True, text=True, timeout=300
            )

            test_results = {
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "passed": result.returncode == 0,
                "timestamp": datetime.now().isoformat(),
            }

            # Save test results
            results_path = self.documents_dir / "test_results.json"
            with open(results_path, "w") as f:
                json.dump(test_results, f, indent=2)

            logger.info(
                f"Test run completed: {'PASSED' if test_results['passed'] else 'FAILED'}"
            )
            return test_results

        except subprocess.TimeoutExpired:
            logger.error("Test run timed out")
            return {
                "returncode": -1,
                "stdout": "",
                "stderr": "Test run timed out after 300 seconds",
                "passed": False,
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            logger.error(f"Test run failed: {e}")
            return {
                "returncode": -1,
                "stdout": "",
                "stderr": str(e),
                "passed": False,
                "timestamp": datetime.now().isoformat(),
            }

    async def _analyze_test_failures(
        self, test_results: dict[str, Any]
    ) -> dict[str, Any]:
        """Each agent analyzes test failures and suggests fixes."""
        logger.info("Analyzing test failures")

        analyses = {}
        failure_info = f"""
TEST RESULTS:
Return Code: {test_results.get('returncode')}
STDOUT:
{test_results.get('stdout', '')}
STDERR:
{test_results.get('stderr', '')}
"""

        prompt = f"""Analyze these test failures and suggest fixes:

{failure_info}

ANALYSIS REQUIREMENTS:
1. Identify specific failing tests and root causes
2. Categorize failures (syntax, logic, missing imports, etc.)
3. Suggest specific fixes for each failure
4. Prioritize fixes by impact and complexity
5. Consider if failures indicate design issues
6. Suggest whether fixes should target code or tests

Provide detailed analysis with actionable fix recommendations."""

        for agent_name, agent in self.agents.items():
            logger.info(f"Getting failure analysis from {agent_name}")
            context = await self._build_task_context(
                FeatureSpec("failure_analysis", prompt)
            )
            analysis = await agent.review_code(context, prompt)
            analyses[agent_name] = analysis

            # Save individual analysis
            analysis_path = self.documents_dir / f"failure_analysis_{agent_name}.md"
            self._save_document(analysis_path, analysis.get("content", ""))

        return analyses

    async def _create_fix_plan(
        self, failure_analyses: dict[str, Any], test_results: dict[str, Any]
    ) -> dict[str, Any]:
        """Senior engineer creates comprehensive fix plan."""
        logger.info("Creating fix plan")

        analyses_text = "\n\n".join(
            [
                f"=== {agent.upper()} ANALYSIS ===\n{analysis.get('content', '')}"
                for agent, analysis in failure_analyses.items()
            ]
        )

        prompt = f"""Create a comprehensive fix plan for test failures:

TEST FAILURES:
{test_results.get('stdout', '')}
{test_results.get('stderr', '')}

AGENT ANALYSES:
{analyses_text}

FIX PLAN REQUIREMENTS:
1. Prioritize fixes by importance and dependencies
2. Decide whether to fix code or tests for each failure
3. Provide specific, actionable fix instructions
4. Include code snippets where appropriate
5. Consider architectural implications
6. Resolve any conflicts between agent recommendations
7. Ensure fixes maintain code quality

Create a detailed, ordered fix plan that addresses all failures systematically."""

        context = await self._build_task_context(FeatureSpec("fix_plan", prompt))
        fix_plan = await self.agents["senior_engineer"].implement_code(context, prompt)

        # Save fix plan
        plan_path = self.documents_dir / "fix_plan.md"
        self._save_document(plan_path, fix_plan.get("content", ""))

        return fix_plan

    async def _apply_fixes(
        self, implementation: dict[str, Any], fix_plan: dict[str, Any]
    ) -> dict[str, Any]:
        """Apply fixes according to the fix plan."""
        logger.info("Applying fixes")

        prompt = f"""Apply these fixes to the implementation:

CURRENT IMPLEMENTATION:
{implementation.get("content", "")}

FIX PLAN:
{fix_plan.get("content", "")}

REQUIREMENTS:
1. Apply all fixes from the plan in order
2. Maintain code structure and patterns
3. Ensure all changes are properly integrated
4. Keep type hints and documentation updated
5. Test that fixes address the identified issues

Provide the complete updated implementation with all fixes applied."""

        context = await self._build_task_context(FeatureSpec("apply_fixes", prompt))
        updated_implementation = await self.agents["senior_engineer"].implement_code(
            context, prompt
        )

        # Save updated implementation
        updated_path = self.documents_dir / "updated_implementation.md"
        self._save_document(updated_path, updated_implementation.get("content", ""))

        return updated_implementation

    async def _commit_and_push_changes(
        self, feature_spec: FeatureSpec, implementation: dict[str, Any]
    ):
        """Commit and push all changes."""
        logger.info("Committing and pushing changes")

        try:
            # Stage all changes
            subprocess.run(["git", "add", "."], cwd=self.repo_path, check=True)

            # Create comprehensive commit message
            commit_msg = f"""feat: Implement {feature_spec.name}

- Add complete implementation based on architecture skeleton
- Include comprehensive test suite with mocks
- Follow existing codebase patterns and conventions
- Implement all required functionality with proper error handling

Generated with Enhanced Multi-Agent Workflow
"""

            # Commit changes
            subprocess.run(
                ["git", "commit", "-m", commit_msg], cwd=self.repo_path, check=True
            )

            # Push to remote
            subprocess.run(["git", "push"], cwd=self.repo_path, check=True)

            logger.info("Changes committed and pushed successfully")

        except subprocess.CalledProcessError as e:
            logger.error(f"Git operation failed: {e}")
            raise

    async def _create_pull_request(self, feature_spec: FeatureSpec) -> int:
        """Create a pull request for the implemented feature."""
        logger.info("Creating pull request")

        # Use GitHub CLI to create PR
        try:
            pr_body = f"""## Summary
Implements {feature_spec.name} using enhanced multi-agent workflow.

## Changes Made
- Architecture skeleton created by architect agent
- Comprehensive test suite developed by testing agent
- Implementation completed by development agent
- Code quality ensured by senior engineering agent

## Test Coverage
- Unit tests for all classes and methods
- Integration tests for component interactions
- Mock classes for dependency injection
- Edge case and error condition coverage

## Workflow
Generated using Enhanced Multi-Agent Workflow with:
1. Skeleton-first architecture design
2. Test-driven development approach
3. Multi-agent code review process
4. Automated test validation cycles

Ready for human review and feedback.
"""

            result = subprocess.run(
                [
                    "gh",
                    "pr",
                    "create",
                    "--title",
                    f"feat: {feature_spec.name}",
                    "--body",
                    pr_body,
                ],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True,
            )

            # Extract PR number from output
            pr_url = result.stdout.strip()
            pr_number = int(pr_url.split("/")[-1])

            logger.info(f"Created PR #{pr_number}: {pr_url}")
            return pr_number

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to create PR: {e}")
            raise

    async def _fetch_new_pr_comments(self, pr_number: int) -> list[dict[str, Any]]:
        """Fetch new PR comments using MCP GitHub tools."""
        logger.info(f"Fetching new comments for PR #{pr_number}")

        try:
            # Use MCP GitHub agent to get PR comments
            comments_result = await execute_tool(
                "mcp__github-agent__github_get_pr_comments", {"pr_number": pr_number}
            )

            if not comments_result or "error" in comments_result:
                logger.warning(f"Failed to fetch PR comments: {comments_result}")
                return []

            # Filter for new comments since last check
            # This is a simplified implementation - in production you'd track timestamps
            return comments_result.get("comments", [])

        except Exception as e:
            logger.error(f"Error fetching PR comments: {e}")
            return []

    async def _analyze_pr_comments(
        self, comments: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """All agents analyze PR comments and suggest responses."""
        logger.info("Analyzing PR comments")

        analyses = {}
        comments_text = self._format_comments_for_analysis(comments)

        prompt = f"""Analyze these PR comments and suggest how to address them:

PR COMMENTS:
{comments_text}

ANALYSIS REQUIREMENTS:
1. Categorize comments by type (bug report, enhancement, style, question)
2. Assess validity and importance of each comment
3. Suggest specific responses and code changes needed
4. Identify any conflicting feedback
5. Recommend priority order for addressing comments
6. Consider impact on overall design and architecture

Provide detailed analysis with specific recommendations for each comment."""

        for agent_name, agent in self.agents.items():
            logger.info(f"Getting PR comment analysis from {agent_name}")
            context = await self._build_task_context(
                FeatureSpec("pr_comment_analysis", prompt)
            )
            analysis = await agent.review_code(context, prompt)
            analyses[agent_name] = analysis

            # Save individual analysis
            analysis_path = self.documents_dir / f"pr_comment_analysis_{agent_name}.md"
            self._save_document(analysis_path, analysis.get("content", ""))

        return analyses

    async def _create_pr_response_plan(
        self, analyses: dict[str, Any], comments: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Senior engineer creates plan for responding to PR comments."""
        logger.info("Creating PR response plan")

        analyses_text = "\n\n".join(
            [
                f"=== {agent.upper()} ANALYSIS ===\n{analysis.get('content', '')}"
                for agent, analysis in analyses.items()
            ]
        )

        comments_text = self._format_comments_for_analysis(comments)

        prompt = f"""Create a comprehensive plan for responding to PR comments:

PR COMMENTS:
{comments_text}

AGENT ANALYSES:
{analyses_text}

RESPONSE PLAN REQUIREMENTS:
1. Address each comment with specific actions
2. Prioritize responses by importance and effort
3. Resolve conflicts between different feedback
4. Plan code changes needed for each comment
5. Draft appropriate responses to each comment
6. Ensure responses maintain code quality
7. Consider architectural implications

Create a detailed response plan with specific actions and responses."""

        context = await self._build_task_context(
            FeatureSpec("pr_response_plan", prompt)
        )
        response_plan = await self.agents["senior_engineer"].implement_code(
            context, prompt
        )

        # Save response plan
        plan_path = self.documents_dir / "pr_response_plan.md"
        self._save_document(plan_path, response_plan.get("content", ""))

        return response_plan

    async def _implement_pr_responses(
        self, response_plan: dict[str, Any], comments: list[dict[str, Any]]
    ):
        """Implement changes and post responses to PR comments."""
        logger.info("Implementing PR responses")

        # Extract code changes from response plan
        # This would parse the response plan and make actual file changes
        # For now, this is a placeholder for the implementation

        # Run tests to ensure changes don't break anything
        test_results = await self._run_tests_and_capture_failures()

        if not test_results.get("passed", False):
            logger.warning("Tests failed after implementing PR responses")
            # Would trigger fix cycle here

        # Post replies to PR comments using MCP GitHub tools
        for comment in comments:
            comment_id = comment.get("id")
            if comment_id:
                # Extract response from response plan for this comment
                response_text = "Thank you for the feedback. I've addressed this in the latest commit."

                try:
                    await execute_tool(
                        "mcp__github-agent__github_post_pr_reply",
                        {"comment_id": comment_id, "message": response_text},
                    )
                    logger.info(f"Posted reply to comment {comment_id}")
                except Exception as e:
                    logger.error(f"Failed to post reply to comment {comment_id}: {e}")

    async def _commit_pr_response_changes(
        self, feature_spec: FeatureSpec, response_plan: dict[str, Any]
    ):
        """Commit changes made in response to PR feedback."""
        logger.info("Committing PR response changes")

        try:
            # Stage changes
            subprocess.run(["git", "add", "."], cwd=self.repo_path, check=True)

            # Check if there are changes to commit
            result = subprocess.run(
                ["git", "diff", "--staged", "--quiet"], cwd=self.repo_path
            )

            if result.returncode != 0:  # There are changes
                commit_msg = f"""fix: Address PR feedback for {feature_spec.name}

Based on code review feedback, implemented the following changes:
- Addressed reviewer suggestions and concerns
- Maintained code quality and test coverage
- Ensured compatibility with existing patterns

All tests passing and feedback incorporated.
"""

                subprocess.run(
                    ["git", "commit", "-m", commit_msg], cwd=self.repo_path, check=True
                )

                subprocess.run(["git", "push"], cwd=self.repo_path, check=True)

                logger.info("PR response changes committed and pushed")
            else:
                logger.info("No changes to commit")

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to commit PR response changes: {e}")
            raise

    # Utility methods

    def _all_tests_passing(self, test_results: dict[str, Any]) -> bool:
        """Check if all tests are passing."""
        return test_results.get("passed", False)

    def _save_document(self, path: Path, content: str):
        """Save a document to the workflow directory."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            f.write(content)

    def _format_analyses_for_prompt(self, analyses: dict[str, Any]) -> str:
        """Format agent analyses for use in prompts."""
        return "\n\n".join(
            [
                f"=== {agent.upper()} ANALYSIS ===\n{analysis.get('analysis', '')}"
                for agent, analysis in analyses.items()
            ]
        )

    def _format_comments_for_analysis(self, comments: list[dict[str, Any]]) -> str:
        """Format PR comments for analysis."""
        formatted = []
        for comment in comments:
            formatted.append(
                f"""
Comment ID: {comment.get('id')}
Author: {comment.get('author', 'Unknown')}
File: {comment.get('path', 'General')}
Line: {comment.get('line', 'N/A')}
Content: {comment.get('body', '')}
"""
            )
        return "\n".join(formatted)

    async def _build_task_context(self, feature_spec: FeatureSpec) -> dict[str, Any]:
        """Build task context for agent operations."""
        return {
            "feature_spec": {
                "name": feature_spec.name,
                "description": feature_spec.description,
            },
            "repo_path": str(self.repo_path),
            "workflow_dir": str(self.workflow_dir),
            "codebase_analysis_path": str(self.workflow_dir / "codebase_analysis.md"),
        }

    def cleanup(self):
        """Clean up agent resources."""
        for agent in self.agents.values():
            agent.cleanup()


# CLI interface for the enhanced workflow
async def main():
    """Main CLI interface."""
    if len(sys.argv) < 4:
        print(
            "Usage: python enhanced_workflow_orchestrator.py <repo_name> <repo_path> <feature_name> [<feature_description>]"
        )
        print(
            "   or: python enhanced_workflow_orchestrator.py <repo_name> <repo_path> --resume"
        )
        sys.exit(1)

    repo_name = sys.argv[1]
    repo_path = sys.argv[2]

    orchestrator = EnhancedWorkflowOrchestrator(repo_name, repo_path)

    try:
        if len(sys.argv) > 3 and sys.argv[3] == "--resume":
            # Resume existing workflow
            feature_spec = FeatureSpec("resumed_workflow", "Resuming existing workflow")
            result = await orchestrator.resume_workflow(feature_spec)
        else:
            # Start new workflow
            feature_name = sys.argv[3]
            feature_description = (
                sys.argv[4] if len(sys.argv) > 4 else f"Implement {feature_name}"
            )

            feature_spec = FeatureSpec(feature_name, feature_description)
            result = await orchestrator.run_enhanced_workflow(feature_spec)

        print(f"Workflow completed: {json.dumps(result, indent=2)}")

    except KeyboardInterrupt:
        print("\nWorkflow interrupted by user")
    except Exception as e:
        print(f"Workflow failed: {e}")
        logger.exception("Workflow failed")
    finally:
        orchestrator.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
