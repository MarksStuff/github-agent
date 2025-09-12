"""LangGraph-based multi-agent workflow implementation following multiagent-workflow.md specification."""

import asyncio
import logging
import os
import random
import sys
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any, TypedDict
from uuid import uuid4

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_ollama import ChatOllama
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, StateGraph
from pydantic import BaseModel, Field

# Import enums from separate module to avoid circular imports
from .enums import AgentType, ModelRouter, WorkflowPhase

# Import agent personas and interfaces
from .interfaces import CodebaseAnalyzerInterface

# Load environment variables from .env file
load_dotenv()

# Import codebase analyzer - this should be available or it's a configuration error
sys.path.append(str(Path(__file__).parent.parent / "multi_agent_workflow"))

logger = logging.getLogger(__name__)


class Artifact(BaseModel):
    """Represents an artifact created during the workflow."""

    key: str
    path: str
    type: str  # "code_context", "design", "test", "implementation", "patch", "report"
    content_digest: str | None = None
    created_at: datetime = Field(default_factory=datetime.now)


class Arbitration(BaseModel):
    """Represents a human arbitration decision."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    phase: str
    conflict_description: str
    agents_involved: list[str]
    human_decision: str | None = None
    timestamp: datetime = Field(default_factory=datetime.now)
    applied: bool = False


class WorkflowState(TypedDict):
    """State for the LangGraph workflow."""

    # Core workflow info
    thread_id: str
    feature_description: str
    current_phase: WorkflowPhase

    # Messages and summary
    messages_window: Annotated[list[BaseMessage], lambda x, y: y[-10:]]  # Keep last 10
    summary_log: str

    # Artifacts and documents
    artifacts_index: dict[str, str]  # key -> path mapping
    code_context_document: str | None
    design_constraints_document: str | None
    design_document: str | None
    arbitration_log: list[Arbitration]

    # Git integration
    repo_path: str
    git_branch: str
    last_commit_sha: str | None
    pr_number: int | None

    # Agent outputs
    agent_analyses: dict[str, str]  # agent_type -> analysis
    synthesis_document: str | None
    conflicts: list[dict[str, Any]]

    # Implementation artifacts
    skeleton_code: str | None
    test_code: str | None
    implementation_code: str | None
    patch_queue: list[str]  # Paths to patches

    # Quality and status
    test_report: dict[str, Any]
    ci_status: dict[str, Any]
    lint_status: dict[str, Any]
    quality: str  # "draft", "ok", "fail"
    feedback_gate: str  # "open", "hold"

    # Resource routing
    model_router: ModelRouter
    escalation_count: int


class MultiAgentWorkflow:
    """LangGraph-based implementation of the multi-agent workflow."""

    def __init__(
        self,
        repo_path: str,
        agents: dict[AgentType, Any],
        codebase_analyzer: CodebaseAnalyzerInterface,
        ollama_model: Any | None = None,
        claude_model: Any | None = None,
        thread_id: str | None = None,
        checkpoint_path: str = "agent_state.db",
    ):
        """Initialize the workflow.

        Args:
            repo_path: Path to the repository
            agents: Dict of agents to use (required for dependency injection)
            codebase_analyzer: Codebase analyzer implementation (required)
            ollama_model: Ollama model instance (optional, creates default if None)
            claude_model: Claude model instance (optional, creates default if None)
            thread_id: Thread ID for persistence (e.g., "pr-1234")
            checkpoint_path: Path to SQLite checkpoint database
        """
        self.repo_path = Path(repo_path)
        self.thread_id = (
            thread_id or f"session-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        )
        self.checkpoint_path = checkpoint_path

        # Use dependency-injected agents and analyzer
        self.agents = agents
        self.codebase_analyzer = codebase_analyzer

        # Initialize models - use injected models or create defaults
        if ollama_model is not None:
            self.ollama_model = ollama_model
        else:
            self.ollama_model = ChatOllama(
                model="qwen2.5-coder:7b",
                base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
            )

        if claude_model is not None:
            self.claude_model = claude_model
        else:
            from langchain_core.utils import SecretStr

            api_key = os.getenv("ANTHROPIC_API_KEY")
            if api_key:
                self.claude_model = ChatAnthropic(
                    model_name="claude-3-sonnet-20240229", api_key=SecretStr(api_key)
                )
            else:
                self.claude_model = None

        # Create artifacts directory
        self.artifacts_dir = self.repo_path / "agents" / "artifacts" / self.thread_id
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)

        # Build the graph
        self.graph = self._build_graph()

        # Set up checkpointing
        import sqlite3

        conn = sqlite3.connect(checkpoint_path)
        self.checkpointer = SqliteSaver(conn)
        self.app = self.graph.compile(checkpointer=self.checkpointer)

        logger.info(f"Initialized workflow for thread {self.thread_id}")

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph state graph."""
        workflow = StateGraph(WorkflowState)

        # Phase 0: Code Context Extraction
        workflow.add_node("extract_code_context", self.extract_code_context)

        # Phase 1: Design Exploration
        workflow.add_node(
            "parallel_design_exploration", self.parallel_design_exploration
        )
        workflow.add_node("architect_synthesis", self.architect_synthesis)
        workflow.add_node("code_investigation", self.code_investigation)
        workflow.add_node("human_review", self.human_review)

        # Phase 2: Design Document
        workflow.add_node("create_design_document", self.create_design_document)
        workflow.add_node("iterate_design_document", self.iterate_design_document)
        workflow.add_node("finalize_design_document", self.finalize_design_document)

        # Phase 3: Implementation
        workflow.add_node("create_skeleton", self.create_skeleton)
        workflow.add_node("parallel_development", self.parallel_development)
        workflow.add_node("reconciliation", self.reconciliation)
        workflow.add_node("component_tests", self.component_tests)
        workflow.add_node("integration_tests", self.integration_tests)
        workflow.add_node("refinement", self.refinement)

        # Helper nodes
        workflow.add_node("update_summary", self.update_summary)
        workflow.add_node("push_to_github", self.push_to_github)
        workflow.add_node("wait_for_ci", self.wait_for_ci)
        workflow.add_node("apply_patches", self.apply_patches)

        # Set entry point
        workflow.set_entry_point("extract_code_context")

        # Add edges for Phase 0 -> Phase 1
        workflow.add_edge("extract_code_context", "parallel_design_exploration")

        # Phase 1 flow
        workflow.add_edge("parallel_design_exploration", "architect_synthesis")
        workflow.add_conditional_edges(
            "architect_synthesis",
            self.needs_code_investigation,
            {True: "code_investigation", False: "human_review"},
        )
        workflow.add_edge("code_investigation", "human_review")
        workflow.add_edge("human_review", "create_design_document")

        # Phase 2 flow
        workflow.add_edge("create_design_document", "iterate_design_document")
        workflow.add_conditional_edges(
            "iterate_design_document",
            self.design_document_complete,
            {True: "finalize_design_document", False: "iterate_design_document"},
        )
        workflow.add_edge("finalize_design_document", "create_skeleton")

        # Phase 3 flow
        workflow.add_edge("create_skeleton", "parallel_development")
        workflow.add_edge("parallel_development", "reconciliation")
        workflow.add_conditional_edges(
            "reconciliation",
            self.needs_human_arbitration,
            {True: "human_review", False: "component_tests"},
        )
        workflow.add_edge("component_tests", "integration_tests")
        workflow.add_edge("integration_tests", "refinement")
        workflow.add_edge("refinement", "push_to_github")
        workflow.add_edge("push_to_github", "wait_for_ci")
        workflow.add_conditional_edges(
            "wait_for_ci", self.ci_passed, {True: END, False: "apply_patches"}
        )
        workflow.add_edge("apply_patches", "push_to_github")

        return workflow

    async def extract_code_context(self, state: WorkflowState) -> WorkflowState:
        """Phase 0: Extract code context using Senior Engineer (Claude Code)."""
        logger.info("Phase 0: Extracting code context")

        # Use Claude Code for thorough analysis
        state["model_router"] = ModelRouter.CLAUDE_CODE
        state["current_phase"] = WorkflowPhase.PHASE_0_CODE_CONTEXT

        # Senior engineer analyzes codebase using injected analyzer
        analysis = self.codebase_analyzer.analyze()

        # Create Code Context Document
        context_doc = f"""# Code Context Document

## Architecture Overview
{analysis.get('architecture', 'To be analyzed')}

## Technology Stack
- Languages: {', '.join(analysis.get('languages', ['Python']))}
- Frameworks: {', '.join(analysis.get('frameworks', []))}
- Databases: {', '.join(analysis.get('databases', []))}

## Design Patterns
{analysis.get('patterns', 'To be identified')}

## Code Conventions
{analysis.get('conventions', 'To be documented')}

## Key Interfaces
{analysis.get('interfaces', 'To be extracted')}

## Infrastructure Services
{analysis.get('services', 'To be catalogued')}

## Testing Approach
{analysis.get('testing', 'To be analyzed')}

## Recent Changes
{analysis.get('recent_changes', 'No recent changes analyzed')}
"""

        # Save to artifacts
        context_path = self.artifacts_dir / "code_context.md"
        context_path.write_text(context_doc)

        state["code_context_document"] = context_doc
        state["artifacts_index"]["code_context"] = str(context_path)
        state["messages_window"].append(
            AIMessage(
                content=f"Extracted code context document (saved to {context_path})"
            )
        )

        return state

    async def parallel_design_exploration(self, state: WorkflowState) -> WorkflowState:
        """Phase 1 Step 1: All agents analyze in parallel using Ollama."""
        logger.info("Phase 1: Parallel design exploration")

        state["model_router"] = ModelRouter.OLLAMA
        state["current_phase"] = WorkflowPhase.PHASE_1_DESIGN_EXPLORATION

        # All agents work in parallel
        tasks = []
        for agent_type, agent in self.agents.items():
            context = {
                "code_context": state["code_context_document"],
                "feature": state["feature_description"],
            }
            tasks.append(self._agent_analysis(agent, agent_type, context))

        # Wait for all analyses
        analyses = await asyncio.gather(*tasks)

        # Store analyses
        for agent_type, analysis in analyses:
            state["agent_analyses"][str(agent_type)] = analysis

            # Save to artifacts
            analysis_path = self.artifacts_dir / f"analysis_{agent_type}.md"
            analysis_path.write_text(analysis)
            state["artifacts_index"][f"analysis:{agent_type}"] = str(analysis_path)

        state["messages_window"].append(
            AIMessage(content="All agents completed parallel analysis")
        )

        return state

    async def architect_synthesis(self, state: WorkflowState) -> WorkflowState:
        """Phase 1 Step 2: Architect synthesizes all perspectives."""
        logger.info("Phase 1: Architect synthesis")

        state["current_phase"] = WorkflowPhase.PHASE_1_SYNTHESIS

        # Architect creates synthesis
        synthesis_prompt = f"""As the Architect, synthesize the following agent analyses:

Test-first perspective:
{state['agent_analyses'].get(AgentType.TEST_FIRST, 'Not available')}

Fast-coder perspective:
{state['agent_analyses'].get(AgentType.FAST_CODER, 'Not available')}

Senior Engineer perspective:
{state['agent_analyses'].get(AgentType.SENIOR_ENGINEER, 'Not available')}

Your own analysis:
{state['agent_analyses'].get(AgentType.ARCHITECT, 'Not available')}

Create a synthesis document with:
1. Common Themes (where 2+ agents align)
2. Conflicts (explicit disagreements)
3. Trade-offs (what each approach optimizes for)
4. Questions requiring code investigation

Remain neutral and document rather than judge."""

        synthesis = await self._call_model(synthesis_prompt, ModelRouter.OLLAMA)

        # Parse for conflicts and questions
        conflicts = self._extract_conflicts(synthesis)
        questions = self._extract_questions(synthesis)

        state["synthesis_document"] = synthesis
        state["conflicts"] = conflicts

        # Save synthesis
        synthesis_path = self.artifacts_dir / "synthesis.md"
        synthesis_path.write_text(synthesis)
        state["artifacts_index"]["synthesis"] = str(synthesis_path)

        # Determine if code investigation needed
        state["messages_window"].append(
            AIMessage(
                content=f"Synthesis complete. Found {len(conflicts)} conflicts, {len(questions)} questions."
            )
        )

        return state

    async def code_investigation(self, state: WorkflowState) -> WorkflowState:
        """Phase 1 Step 3: Targeted code investigation if needed."""
        logger.info("Phase 1: Code investigation")

        state["model_router"] = ModelRouter.CLAUDE_CODE
        state["current_phase"] = WorkflowPhase.PHASE_1_CODE_INVESTIGATION

        # Investigate specific questions
        synthesis_doc = state["synthesis_document"] or ""
        questions = self._extract_questions(synthesis_doc)

        investigation_results = []
        for question in questions:
            result = await self._investigate_code_question(question)
            investigation_results.append(result)

        # Update synthesis with findings
        updated_synthesis = synthesis_doc + "\n\n## Code Investigation Results\n"
        for q, r in zip(questions, investigation_results, strict=False):
            updated_synthesis += f"\n**Q:** {q}\n**A:** {r}\n"

        state["synthesis_document"] = updated_synthesis

        # Update synthesis file
        synthesis_path = Path(state["artifacts_index"]["synthesis"])
        synthesis_path.write_text(updated_synthesis)

        state["messages_window"].append(
            AIMessage(content=f"Investigated {len(questions)} code questions")
        )

        return state

    async def human_review(self, state: WorkflowState) -> WorkflowState:
        """Phase 1 Step 4: Human review and decision via GitHub PR."""
        logger.info("Phase 1: Human review")

        state["current_phase"] = WorkflowPhase.PHASE_1_HUMAN_REVIEW
        state["feedback_gate"] = "hold"

        # Create PR with synthesis for review
        pr_body = f"""## Design Synthesis for: {state['feature_description']}

{state['synthesis_document']}

## Additional Considerations
<!-- Please add your thoughts here -->

## Decisions Needed
"""
        for conflict in state["conflicts"]:
            pr_body += f"\n- [ ] {conflict['description']}"

        # Push branch and create PR
        branch_name = f"design/{self.thread_id}"
        pr_number = await self._create_design_pr(branch_name, pr_body)
        state["pr_number"] = pr_number
        state["git_branch"] = branch_name

        # Wait for human feedback (interrupt)
        state["messages_window"].append(
            HumanMessage(content=f"Awaiting human review on PR #{pr_number}")
        )

        # In production, this would pause until human provides feedback
        # For now, simulate receiving feedback
        state["design_constraints_document"] = await self._get_human_feedback(pr_number)
        state["feedback_gate"] = "open"

        return state

    async def create_design_document(self, state: WorkflowState) -> WorkflowState:
        """Phase 2: Start collaborative design document."""
        logger.info("Phase 2: Creating design document")

        state["model_router"] = ModelRouter.OLLAMA
        state["current_phase"] = WorkflowPhase.PHASE_2_DESIGN_DOCUMENT

        # Initialize design document with template
        design_doc = f"""# Design Document: {state['feature_description']}

## Overview
{state['feature_description']}

## Acceptance Criteria
<!-- From Test-first agent -->

## Technical Design
<!-- Detailed technical approach -->

## Implementation Plan
<!-- Step-by-step implementation -->

## Human Additions
<!-- Empty section for human to comment -->

## Arbitration History
<!-- Auto-populated from PR comments -->

## Unresolved Questions
<!-- Agents add items needing human input -->
"""

        state["design_document"] = design_doc

        # Save initial document
        design_path = self.artifacts_dir / "design_document.md"
        design_path.write_text(design_doc)
        state["artifacts_index"]["design_document"] = str(design_path)

        state["messages_window"].append(
            AIMessage(content="Created initial design document")
        )

        return state

    async def iterate_design_document(self, state: WorkflowState) -> WorkflowState:
        """Phase 2: Iteratively build design document with all agents."""
        logger.info("Phase 2: Iterating on design document")

        # Random agent adds/modifies a section
        agent_type = random.choice(list(self.agents.keys()))
        agent = self.agents[agent_type]

        # Agent contributes to document
        contribution = await self._agent_design_contribution(
            agent,
            agent_type,
            state["design_document"] or "",
            state["design_constraints_document"],
        )

        # Other agents review
        reviews = []
        for other_type, other_agent in self.agents.items():
            if other_type != agent_type:
                review = await self._agent_review_contribution(
                    other_agent, other_type, contribution
                )
                reviews.append((other_type, review))

        # Check for objections
        objections = [(t, r) for t, r in reviews if "object" in r.lower()]

        if objections:
            # Create conflict for arbitration
            conflict = {
                "phase": "design_document",
                "contributor": str(agent_type),
                "objectors": [str(t) for t, _ in objections],
                "contribution": contribution,
                "objections": [r for _, r in objections],
            }
            state["conflicts"].append(conflict)

            # Request human arbitration
            arbitration = await self._request_arbitration(conflict)
            state["arbitration_log"].append(arbitration)

            # Apply arbitration decision
            if arbitration.human_decision:
                state["design_document"] = await self._apply_arbitration(
                    state["design_document"] or "", arbitration
                )
        else:
            # No objections, apply contribution
            state["design_document"] = self._merge_contribution(
                state["design_document"] or "", contribution
            )

        # Update document file
        design_path = Path(state["artifacts_index"]["design_document"])
        design_path.write_text(state["design_document"] or "")

        state["messages_window"].append(
            AIMessage(content=f"Agent {agent_type} contributed to design document")
        )

        return state

    async def finalize_design_document(self, state: WorkflowState) -> WorkflowState:
        """Phase 2: Finalize design document when all agents agree."""
        logger.info("Phase 2: Finalizing design document")

        # All agents must agree document is complete
        agreements = []
        for agent_type, agent in self.agents.items():
            agrees = await self._agent_agrees_complete(
                agent, agent_type, state["design_document"] or ""
            )
            agreements.append(agrees)

        if all(agreements):
            state["messages_window"].append(
                AIMessage(content="All agents agree: design document complete")
            )
        else:
            # Continue iteration
            return await self.iterate_design_document(state)

        return state

    async def create_skeleton(self, state: WorkflowState) -> WorkflowState:
        """Phase 3 Round 1 Step 1: Senior engineer creates skeleton."""
        logger.info("Phase 3: Creating skeleton")

        state["model_router"] = ModelRouter.CLAUDE_CODE
        state["current_phase"] = WorkflowPhase.PHASE_3_SKELETON

        # Senior engineer creates skeleton
        skeleton = await self._create_code_skeleton(state["design_document"] or "")

        # Architect reviews
        review = await self._architect_review_skeleton(skeleton)

        if "disagree" in review.lower():
            # Need human arbitration
            conflict = {
                "phase": "skeleton",
                "description": "Skeleton structure disagreement",
                "senior_engineer": skeleton,
                "architect_review": review,
            }
            arbitration = await self._request_arbitration(conflict)
            state["arbitration_log"].append(arbitration)
            skeleton = await self._apply_skeleton_arbitration(skeleton, arbitration)

        state["skeleton_code"] = skeleton

        # Save skeleton
        skeleton_path = self.artifacts_dir / "skeleton.py"
        skeleton_path.write_text(skeleton)
        state["artifacts_index"]["skeleton"] = str(skeleton_path)

        # Create branch for implementation
        impl_branch = f"impl/{self.thread_id}"
        await self._create_branch(impl_branch)
        state["git_branch"] = impl_branch

        state["messages_window"].append(
            AIMessage(content="Skeleton created and approved")
        )

        return state

    async def parallel_development(self, state: WorkflowState) -> WorkflowState:
        """Phase 3 Round 1 Step 2: Parallel test and implementation development."""
        logger.info("Phase 3: Parallel development")

        state["current_phase"] = WorkflowPhase.PHASE_3_PARALLEL_DEV

        # Test-first writes tests WITHOUT seeing implementation
        test_task = self._write_tests(
            state["skeleton_code"] or "", state["design_document"] or ""
        )

        # Fast-coder implements WITHOUT seeing tests
        impl_task = self._write_implementation(
            state["skeleton_code"] or "", state["design_document"] or ""
        )

        # Run in parallel
        test_code, impl_code = await asyncio.gather(test_task, impl_task)

        state["test_code"] = test_code
        state["implementation_code"] = impl_code

        # Save both
        test_path = self.artifacts_dir / "tests_initial.py"
        test_path.write_text(test_code)
        state["artifacts_index"]["tests_initial"] = str(test_path)

        impl_path = self.artifacts_dir / "implementation_initial.py"
        impl_path.write_text(impl_code)
        state["artifacts_index"]["implementation_initial"] = str(impl_path)

        state["messages_window"].append(
            AIMessage(content="Parallel development complete")
        )

        return state

    async def reconciliation(self, state: WorkflowState) -> WorkflowState:
        """Phase 3 Round 1 Step 3: Reconcile tests and implementation."""
        logger.info("Phase 3: Reconciliation")

        state["current_phase"] = WorkflowPhase.PHASE_3_RECONCILIATION

        # Identify mismatches
        mismatches = await self._identify_mismatches(
            state["test_code"] or "", state["implementation_code"] or ""
        )

        if mismatches:
            # Each agent argues their case
            test_argument = await self._agent_argument(
                self.agents[AgentType.TEST_FIRST], "tests", mismatches
            )
            impl_argument = await self._agent_argument(
                self.agents[AgentType.FAST_CODER], "implementation", mismatches
            )

            # Senior engineer proposes solution
            senior_solution = await self._senior_engineer_solution(
                mismatches, test_argument, impl_argument
            )

            # Architect weighs in
            architect_impact = await self._architect_system_impact(senior_solution)

            # Check for consensus
            if not await self._has_consensus(
                [test_argument, impl_argument, senior_solution, architect_impact]
            ):
                # Need human arbitration
                conflict = {
                    "phase": "reconciliation",
                    "mismatches": mismatches,
                    "test_argument": test_argument,
                    "impl_argument": impl_argument,
                    "senior_solution": senior_solution,
                    "architect_impact": architect_impact,
                }
                arbitration = await self._request_arbitration(conflict)
                state["arbitration_log"].append(arbitration)

                # Apply arbitration
                (
                    state["test_code"],
                    state["implementation_code"],
                ) = await self._apply_reconciliation(
                    state["test_code"] or "",
                    state["implementation_code"] or "",
                    arbitration,
                )

        state["messages_window"].append(
            AIMessage(
                content=f"Reconciliation complete. {len(mismatches)} mismatches resolved"
            )
        )

        return state

    async def component_tests(self, state: WorkflowState) -> WorkflowState:
        """Phase 3 Round 2: Component tests."""
        logger.info("Phase 3: Component tests")

        state["current_phase"] = WorkflowPhase.PHASE_3_COMPONENT_TESTS
        state["model_router"] = ModelRouter.CLAUDE_CODE

        # Test-first writes component tests
        component_tests = await self._write_component_tests(
            state["implementation_code"] or "", state["test_code"] or ""
        )

        # Run tests
        test_results = await self._run_tests(component_tests)
        state["test_report"] = test_results

        if test_results["failed"] > 0:
            # Fast-coder refactors
            refactored = await self._refactor_for_tests(
                state["implementation_code"] or "", test_results
            )
            state["implementation_code"] = refactored

            # Senior engineer reviews
            review = await self._senior_review_refactor(refactored)
            if "improve" in review.lower():
                state["implementation_code"] = await self._apply_senior_improvements(
                    refactored, review
                )

        state["messages_window"].append(
            AIMessage(
                content=f"Component tests: {test_results['passed']} passed, {test_results['failed']} failed"
            )
        )

        return state

    async def integration_tests(self, state: WorkflowState) -> WorkflowState:
        """Phase 3 Round 3: Integration tests."""
        logger.info("Phase 3: Integration tests")

        state["current_phase"] = WorkflowPhase.PHASE_3_INTEGRATION_TESTS

        # Test-first writes integration tests
        integration_tests = await self._write_integration_tests(
            state["implementation_code"] or "", state["design_document"] or ""
        )

        # Architect ensures scalability concerns tested
        scalability_tests = await self._architect_scalability_tests(integration_tests)

        # Run all tests
        test_results = await self._run_tests(integration_tests + scalability_tests)
        state["test_report"] = test_results

        if test_results["failed"] > 0:
            # Fast-coder optimizes
            optimized = await self._optimize_implementation(
                state["implementation_code"] or "", test_results
            )
            state["implementation_code"] = optimized

        state["messages_window"].append(
            AIMessage(
                content=f"Integration tests: {test_results['passed']} passed, {test_results['failed']} failed"
            )
        )

        return state

    async def refinement(self, state: WorkflowState) -> WorkflowState:
        """Phase 3 Round 4: Final refinement."""
        logger.info("Phase 3: Refinement")

        state["current_phase"] = WorkflowPhase.PHASE_3_REFINEMENT
        state["model_router"] = ModelRouter.CLAUDE_CODE

        # Senior engineer leads refactoring
        refined = await self._senior_refactor_for_quality(
            state["implementation_code"] or "", state["test_code"] or ""
        )

        # All agents review
        reviews = []
        for agent_type, agent in self.agents.items():
            review = await self._final_review(agent, agent_type, refined)
            reviews.append(review)

        if all("approve" in r.lower() for r in reviews):
            state["implementation_code"] = refined
            state["quality"] = "ok"
        else:
            state["quality"] = "fail"
            # Would need another iteration

        # Create final patch
        patch = await self._create_patch(refined)
        patch_path = self.artifacts_dir / f"final_{datetime.now().isoformat()}.patch"
        patch_path.write_text(patch)
        state["patch_queue"].append(str(patch_path))

        state["messages_window"].append(
            AIMessage(content="Refinement complete. Code ready for deployment")
        )

        return state

    # Helper methods for model calls and utilities

    async def _call_model(self, prompt: str, router: ModelRouter) -> str:
        """Call the appropriate model based on routing decision."""
        if router == ModelRouter.OLLAMA:
            response = await self.ollama_model.ainvoke([HumanMessage(content=prompt)])
        else:
            response = await self.claude_model.ainvoke([HumanMessage(content=prompt)])
        return response.content

    async def _agent_analysis(
        self, agent: Any, agent_type: AgentType, context: dict
    ) -> tuple[AgentType, str]:
        """Get analysis from an agent."""
        prompt = f"As {agent_type}, analyze this feature request given the code context:\n{context}"
        # Use the agent's persona for analysis
        analysis = agent.persona.ask(prompt)
        return agent_type, analysis

    def _extract_conflicts(self, synthesis: str) -> list[dict]:
        """Extract conflicts from synthesis document."""
        # Simple extraction logic - would be more sophisticated in production
        conflicts: list[dict[str, Any]] = []
        if "Conflicts" in synthesis:
            # Parse conflicts section
            pass
        return conflicts

    def _extract_questions(self, synthesis: str) -> list[str]:
        """Extract questions requiring investigation."""
        questions = []
        if "Questions" in synthesis or "questions" in synthesis:
            # Simple parsing - look for question marks
            lines = synthesis.split("\n")
            for line in lines:
                if "?" in line:
                    questions.append(line.strip())
        return questions

    async def _investigate_code_question(self, question: str) -> str:
        """Investigate a specific code question."""
        # Use Claude Code to investigate
        prompt = f"Investigate this code question in the repository: {question}"
        return await self._call_model(prompt, ModelRouter.CLAUDE_CODE)

    async def _create_design_pr(self, branch: str, body: str) -> int:
        """Create a GitHub PR for design review."""
        # Implementation would use GitHub API
        # For now, return dummy PR number
        return 1234

    async def _get_human_feedback(self, pr_number: int) -> str:
        """Get human feedback from PR."""
        # In production, would poll GitHub API
        # For now, return dummy constraints
        return "Constraints: Use existing authentication system. Minimize external dependencies."

    # ... Additional helper methods would be implemented similarly ...

    # Conditional edge functions

    def needs_code_investigation(self, state: WorkflowState) -> bool:
        """Check if code investigation is needed."""
        questions = self._extract_questions(state.get("synthesis_document") or "")
        return len(questions) > 0

    def design_document_complete(self, state: WorkflowState) -> bool:
        """Check if design document is complete."""
        # Would check if all agents agree
        design_doc = state.get("design_document") or ""
        return design_doc.count("TODO") == 0

    def needs_human_arbitration(self, state: WorkflowState) -> bool:
        """Check if human arbitration is needed."""
        return len(state.get("conflicts", [])) > 0

    def ci_passed(self, state: WorkflowState) -> bool:
        """Check if CI has passed."""
        ci_status = state.get("ci_status", {})
        return ci_status.get("status") == "success"

    # Stub methods for remaining functionality
    async def update_summary(self, state: WorkflowState) -> WorkflowState:
        """Update the summary log when messages grow."""
        return state

    async def push_to_github(self, state: WorkflowState) -> WorkflowState:
        """Push changes to GitHub."""
        return state

    async def wait_for_ci(self, state: WorkflowState) -> WorkflowState:
        """Wait for CI to complete."""
        return state

    async def apply_patches(self, state: WorkflowState) -> WorkflowState:
        """Apply patches from the queue."""
        return state

    # Additional stub methods for complete workflow
    async def _agent_design_contribution(
        self, agent: Any, agent_type: str, document: str, constraints: str | None
    ) -> str:
        """Get agent contribution to design document."""
        return f"Mock {agent_type} contribution"

    async def _agent_review_contribution(
        self, agent: Any, agent_type: str, contribution: str
    ) -> str:
        """Get agent review of contribution."""
        return f"Mock {agent_type} review"

    async def _request_arbitration(self, conflict: dict[str, Any]) -> Arbitration:
        """Request human arbitration."""
        return Arbitration(
            phase=conflict.get("phase", "unknown"),
            conflict_description=conflict.get("description", "Mock conflict"),
            agents_involved=conflict.get("agents_involved", []),
            human_decision="Mock human decision",
        )

    async def _apply_arbitration(self, document: str, arbitration: Arbitration) -> str:
        """Apply arbitration decision."""
        return (
            document + f"\n\n<!-- Applied arbitration: {arbitration.human_decision} -->"
        )

    def _merge_contribution(self, document: str, contribution: str) -> str:
        """Merge contribution into document."""
        return document + f"\n\n{contribution}"

    async def _agent_agrees_complete(
        self, agent: Any, agent_type: str, document: str
    ) -> bool:
        """Check if agent agrees document is complete."""
        return True  # Mock agreement

    async def _create_code_skeleton(self, design: str) -> str:
        """Create code skeleton from design."""
        return "# Mock code skeleton\npass"

    async def _architect_review_skeleton(self, skeleton: str) -> str:
        """Get architect review of skeleton."""
        return "approve"

    async def _apply_skeleton_arbitration(
        self, skeleton: str, arbitration: Arbitration
    ) -> str:
        """Apply skeleton arbitration."""
        return skeleton + f"\n# Applied arbitration: {arbitration.human_decision}"

    async def _create_branch(self, branch_name: str) -> None:
        """Create new git branch."""
        pass  # Mock implementation

    async def _write_tests(self, skeleton: str, design: str) -> str:
        """Write tests for skeleton."""
        return "# Mock test code\ndef test_example():\n    pass"

    async def _write_implementation(self, skeleton: str, design: str) -> str:
        """Write implementation for skeleton."""
        return "# Mock implementation\ndef example():\n    pass"

    async def _identify_mismatches(
        self, test_code: str, impl_code: str
    ) -> list[dict[str, Any]]:
        """Identify mismatches between tests and implementation."""
        return []  # Mock no mismatches

    async def _agent_argument(
        self, agent: Any, role: str, mismatches: list[dict[str, Any]]
    ) -> str:
        """Get agent argument about mismatches."""
        return f"Mock {role} argument"

    async def _senior_engineer_solution(
        self, mismatches: list[dict[str, Any]], test_arg: str, impl_arg: str
    ) -> str:
        """Get senior engineer solution."""
        return "Mock senior engineer solution"

    async def _architect_system_impact(self, solution: str) -> str:
        """Get architect system impact assessment."""
        return "Mock architect impact assessment"

    async def _has_consensus(self, arguments: list[str]) -> bool:
        """Check if there is consensus among arguments."""
        return True  # Mock consensus

    async def _apply_reconciliation(
        self, test_code: str, impl_code: str, arbitration: Arbitration
    ) -> tuple[str, str]:
        """Apply reconciliation arbitration."""
        return test_code, impl_code  # Mock no changes

    async def _write_component_tests(self, implementation: str, unit_tests: str) -> str:
        """Write component tests."""
        return "# Mock component tests\ndef test_component():\n    pass"

    async def _run_tests(self, test_code: str) -> dict[str, Any]:
        """Run tests and return results."""
        return {"passed": 1, "failed": 0, "errors": []}

    async def _refactor_for_tests(self, code: str, test_results: dict[str, Any]) -> str:
        """Refactor code to fix test failures."""
        return code  # Mock no changes needed

    async def _senior_review_refactor(self, code: str) -> str:
        """Get senior engineer review of refactor."""
        return "looks good"

    async def _apply_senior_improvements(self, code: str, review: str) -> str:
        """Apply senior engineer improvements."""
        return code + f"\n# Applied improvements: {review}"

    async def _write_integration_tests(self, implementation: str, design: str) -> str:
        """Write integration tests."""
        return "# Mock integration tests\ndef test_integration():\n    pass"

    async def _architect_scalability_tests(self, integration_tests: str) -> str:
        """Design scalability tests."""
        return "# Mock scalability tests\ndef test_scalability():\n    pass"

    async def _optimize_implementation(
        self, code: str, test_results: dict[str, Any]
    ) -> str:
        """Optimize implementation for performance."""
        return code  # Mock no optimization needed

    async def _senior_refactor_for_quality(self, impl_code: str, test_code: str) -> str:
        """Senior engineer refactor for quality."""
        return impl_code  # Mock no changes

    async def _final_review(self, agent: Any, agent_type: str, code: str) -> str:
        """Get final review from agent."""
        return "approve"

    async def _create_patch(self, code: str) -> str:
        """Create patch from code."""
        return f"# Mock patch\n{code}"


# Main execution
async def main():
    """Run the multi-agent workflow."""
    import argparse

    parser = argparse.ArgumentParser(description="Multi-agent workflow with LangGraph")
    parser.add_argument("--repo-path", required=True, help="Path to repository")
    parser.add_argument("--feature", required=True, help="Feature description")
    parser.add_argument("--thread-id", help="Thread ID for persistence")
    args = parser.parse_args()

    # Initialize workflow with mock dependencies for main execution
    from .tests.mocks import create_mock_dependencies

    mock_deps = create_mock_dependencies(args.thread_id or "main-thread")

    workflow = MultiAgentWorkflow(
        repo_path=args.repo_path,
        thread_id=args.thread_id,
        agents=mock_deps["agents"],
        codebase_analyzer=mock_deps["codebase_analyzer"],
    )

    # Initial state
    initial_state = WorkflowState(
        thread_id=workflow.thread_id,
        feature_description=args.feature,
        current_phase=WorkflowPhase.PHASE_0_CODE_CONTEXT,
        messages_window=[],
        summary_log="",
        artifacts_index={},
        code_context_document=None,
        design_constraints_document=None,
        design_document=None,
        arbitration_log=[],
        repo_path=args.repo_path,
        git_branch="main",
        last_commit_sha=None,
        pr_number=None,
        agent_analyses={},
        synthesis_document=None,
        conflicts=[],
        skeleton_code=None,
        test_code=None,
        implementation_code=None,
        patch_queue=[],
        test_report={},
        ci_status={},
        lint_status={},
        quality="draft",
        feedback_gate="open",
        model_router=ModelRouter.OLLAMA,
        escalation_count=0,
    )

    # Run workflow
    config = {"configurable": {"thread_id": workflow.thread_id}}
    result = await workflow.app.ainvoke(initial_state, config)

    print(f"Workflow completed. Final quality: {result['quality']}")
    print(f"Artifacts saved to: {workflow.artifacts_dir}")


if __name__ == "__main__":
    asyncio.run(main())
