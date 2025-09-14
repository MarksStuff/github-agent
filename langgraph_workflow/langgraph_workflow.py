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
from .enums import AgentType, ModelRouter, WorkflowPhase, WorkflowStep

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
    raw_feature_input: str | None  # Original PRD or feature file content
    extracted_feature: str | None  # Extracted feature from PRD
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
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if api_key:
                # Create with minimal parameters that should work
                self.claude_model = ChatAnthropic()  # type: ignore
            else:
                self.claude_model = None

        # Create artifacts directory using configured path
        from .config import get_artifacts_path

        self.artifacts_dir = get_artifacts_path(self.thread_id)

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

        # Phase 0: Feature and Code Context Extraction
        workflow.add_node(WorkflowStep.EXTRACT_FEATURE.value, self.extract_feature)
        workflow.add_node(
            WorkflowStep.EXTRACT_CODE_CONTEXT.value, self.extract_code_context
        )

        # Phase 1: Design Exploration
        workflow.add_node(
            WorkflowStep.PARALLEL_DESIGN_EXPLORATION.value,
            self.parallel_design_exploration,
        )
        workflow.add_node(
            WorkflowStep.ARCHITECT_SYNTHESIS.value, self.architect_synthesis
        )
        workflow.add_node(
            WorkflowStep.CODE_INVESTIGATION.value, self.code_investigation
        )
        workflow.add_node(WorkflowStep.HUMAN_REVIEW.value, self.human_review)

        # Phase 2: Design Document
        workflow.add_node(
            WorkflowStep.CREATE_DESIGN_DOCUMENT.value, self.create_design_document
        )
        workflow.add_node(
            WorkflowStep.ITERATE_DESIGN_DOCUMENT.value, self.iterate_design_document
        )
        workflow.add_node(
            WorkflowStep.FINALIZE_DESIGN_DOCUMENT.value, self.finalize_design_document
        )

        # Phase 3: Implementation
        workflow.add_node(WorkflowStep.CREATE_SKELETON.value, self.create_skeleton)
        workflow.add_node(
            WorkflowStep.PARALLEL_DEVELOPMENT.value, self.parallel_development
        )
        workflow.add_node(WorkflowStep.RECONCILIATION.value, self.reconciliation)
        workflow.add_node(WorkflowStep.COMPONENT_TESTS.value, self.component_tests)
        workflow.add_node(WorkflowStep.INTEGRATION_TESTS.value, self.integration_tests)
        workflow.add_node(WorkflowStep.REFINEMENT.value, self.refinement)

        # Helper nodes
        workflow.add_node("update_summary", self.update_summary)
        workflow.add_node(WorkflowStep.PUSH_TO_GITHUB.value, self.push_to_github)
        workflow.add_node(WorkflowStep.WAIT_FOR_CI.value, self.wait_for_ci)
        workflow.add_node(WorkflowStep.APPLY_PATCHES.value, self.apply_patches)

        # Set entry point
        workflow.set_entry_point(WorkflowStep.EXTRACT_FEATURE.value)

        # Add edges for Phase 0
        workflow.add_edge(
            WorkflowStep.EXTRACT_FEATURE.value, WorkflowStep.EXTRACT_CODE_CONTEXT.value
        )
        workflow.add_edge(
            WorkflowStep.EXTRACT_CODE_CONTEXT.value,
            WorkflowStep.PARALLEL_DESIGN_EXPLORATION.value,
        )

        # Phase 1 flow
        workflow.add_edge(
            WorkflowStep.PARALLEL_DESIGN_EXPLORATION.value,
            WorkflowStep.ARCHITECT_SYNTHESIS.value,
        )
        workflow.add_conditional_edges(
            WorkflowStep.ARCHITECT_SYNTHESIS.value,
            self.needs_code_investigation,
            {
                True: WorkflowStep.CODE_INVESTIGATION.value,
                False: WorkflowStep.HUMAN_REVIEW.value,
            },
        )
        workflow.add_edge(
            WorkflowStep.CODE_INVESTIGATION.value, WorkflowStep.HUMAN_REVIEW.value
        )
        workflow.add_edge(
            WorkflowStep.HUMAN_REVIEW.value, WorkflowStep.CREATE_DESIGN_DOCUMENT.value
        )

        # Phase 2 flow
        workflow.add_edge(
            WorkflowStep.CREATE_DESIGN_DOCUMENT.value,
            WorkflowStep.ITERATE_DESIGN_DOCUMENT.value,
        )
        workflow.add_conditional_edges(
            WorkflowStep.ITERATE_DESIGN_DOCUMENT.value,
            self.design_document_complete,
            {
                True: WorkflowStep.FINALIZE_DESIGN_DOCUMENT.value,
                False: WorkflowStep.ITERATE_DESIGN_DOCUMENT.value,
            },
        )
        workflow.add_edge(
            WorkflowStep.FINALIZE_DESIGN_DOCUMENT.value,
            WorkflowStep.CREATE_SKELETON.value,
        )

        # Phase 3 flow
        workflow.add_edge(
            WorkflowStep.CREATE_SKELETON.value, WorkflowStep.PARALLEL_DEVELOPMENT.value
        )
        workflow.add_edge(
            WorkflowStep.PARALLEL_DEVELOPMENT.value, WorkflowStep.RECONCILIATION.value
        )
        workflow.add_conditional_edges(
            WorkflowStep.RECONCILIATION.value,
            self.needs_human_arbitration,
            {
                True: WorkflowStep.HUMAN_REVIEW.value,
                False: WorkflowStep.COMPONENT_TESTS.value,
            },
        )
        workflow.add_edge(
            WorkflowStep.COMPONENT_TESTS.value, WorkflowStep.INTEGRATION_TESTS.value
        )
        workflow.add_edge(
            WorkflowStep.INTEGRATION_TESTS.value, WorkflowStep.REFINEMENT.value
        )
        workflow.add_edge(
            WorkflowStep.REFINEMENT.value, WorkflowStep.PUSH_TO_GITHUB.value
        )
        workflow.add_edge(
            WorkflowStep.PUSH_TO_GITHUB.value, WorkflowStep.WAIT_FOR_CI.value
        )
        workflow.add_conditional_edges(
            WorkflowStep.WAIT_FOR_CI.value,
            self.ci_passed,
            {True: END, False: WorkflowStep.APPLY_PATCHES.value},
        )
        workflow.add_edge(
            WorkflowStep.APPLY_PATCHES.value, WorkflowStep.PUSH_TO_GITHUB.value
        )

        return workflow

    async def extract_feature(self, state: WorkflowState) -> WorkflowState:
        """Extract specific feature from PRD if needed and store as artifact."""
        logger.info("Phase 0: Extracting feature from input")

        # If raw_feature_input is provided (PRD file), we may need to extract
        if state.get("raw_feature_input") and state.get("extracted_feature"):
            # Feature was already extracted from PRD
            feature_to_use = state["extracted_feature"]
            logger.info("Using pre-extracted feature from PRD")
        elif state.get("raw_feature_input"):
            # We have a PRD but no extraction - use the whole thing
            feature_to_use = state["raw_feature_input"]
            logger.info("Using entire PRD as feature description")
        else:
            # Simple feature description provided directly
            feature_to_use = state["feature_description"]
            logger.info("Using direct feature description")

        # Store the feature as an artifact

        # Use the proper artifacts directory (in ~/.local/share/github-agent/langgraph/artifacts/)
        # Use thread_id from state to support per-thread artifacts
        from .config import get_artifacts_path

        thread_id = state.get("thread_id", self.thread_id)
        artifacts_dir = get_artifacts_path(thread_id)
        feature_artifact_path = artifacts_dir / "feature_description.md"
        if feature_to_use:
            feature_artifact_path.write_text(feature_to_use)
        else:
            # Should not happen, but handle gracefully
            feature_artifact_path.write_text("")

        # Update artifacts index
        if "artifacts_index" not in state:
            state["artifacts_index"] = {}
        state["artifacts_index"]["feature_description"] = str(feature_artifact_path)

        # Store the final feature description
        state["feature_description"] = feature_to_use or ""

        logger.info(f"Feature description stored as artifact: {feature_artifact_path}")

        return state

    async def extract_code_context(self, state: WorkflowState) -> WorkflowState:
        """Phase 0: Extract code context using Senior Engineer (Claude Code)."""
        logger.info("Phase 0: Extracting code context")

        # Use Claude Code for thorough analysis
        state["model_router"] = ModelRouter.CLAUDE_CODE
        state["current_phase"] = WorkflowPhase.PHASE_0_CODE_CONTEXT

        # Senior engineer analyzes codebase using injected analyzer
        analysis = self.codebase_analyzer.analyze()

        # Create comprehensive context document using LLM
        context_doc = await self._generate_intelligent_code_context(
            analysis, state["feature_description"]
        )

        # Save to artifacts
        context_path = self.artifacts_dir / "code_context.md"
        context_path.write_text(context_doc)

        state["code_context_document"] = context_doc
        state["artifacts_index"]["code_context"] = str(context_path)
        state["messages_window"].append(
            AIMessage(
                content=f"Extracted comprehensive code context document (saved to {context_path})"
            )
        )

        return state

    async def _generate_intelligent_code_context(
        self, analysis: dict, feature_description: str
    ) -> str:
        """Generate an intelligent, comprehensive code context document using LLM.

        Note: feature_description is included for compatibility but not used
        to keep analysis unbiased.
        """

        # Get the repository path from the analyzer
        repo_path = self.codebase_analyzer.repo_path

        # Create structured prompt for comprehensive analysis
        # Import json for formatting analysis data
        import json

        # Create optimized prompt that uses pre-analyzed data instead of asking for full re-analysis
        analysis_json = json.dumps(analysis, indent=2)

        analysis_prompt = f"""You are a Senior Software Engineer creating a comprehensive Code Context Document.

I have already analyzed the repository structure and extracted key information. Please synthesize this data into a well-formatted, actionable Code Context Document.

## Repository: {repo_path}

## PRE-ANALYZED REPOSITORY DATA:
```json
{analysis_json}
```

## TASK:
Create a comprehensive, UNBIASED Code Context Document using ONLY the pre-analyzed data above.

IMPORTANT RULES:
1. This is an OBJECTIVE analysis - do NOT reference any specific features or implementation targets
2. Only list languages found in ACTUAL SOURCE CODE files (not libraries, dependencies, or .venv)
3. Be factual and accurate - only describe what's actually in the analysis data
4. Focus on understanding the current system AS IT IS

Structure the document as follows:

### 1. SYSTEM OVERVIEW
- What this system actually does (based on the analyzed structure)
- Primary architecture patterns found in the code
- Key entry points and main components

### 2. TECHNOLOGY STACK
- **Languages**: ONLY languages used in source code files (exclude .venv/, node_modules/, etc.)
- **Frameworks**: Actually imported and used in the code
- **Development Tools**: Testing, linting, deployment tools

### 3. CODEBASE STRUCTURE
- Directory organization and actual purpose
- Key modules and what they do
- Testing structure and conventions

### 4. DEVELOPMENT CONTEXT
- Current git branch and recent work
- Dependencies and how they're managed
- Design patterns and conventions observed

### 5. ARCHITECTURE INSIGHTS
- How components interact
- Key abstractions and interfaces
- Extension points and modularity

Base everything on the provided analysis data. Be precise and factual.
"""

        try:
            # Log prompt metadata for visibility
            prompt_length = len(analysis_prompt)
            logger.info(
                f"Using evidence-based code analysis prompt ({prompt_length} chars)"
            )
            logger.info(f"Repository path: {repo_path}")

            # Log the full prompt for debugging
            logger.debug("Code context analysis prompt:")
            logger.debug("=" * 80)
            logger.debug(analysis_prompt)
            logger.debug("=" * 80)

            # Use Ollama first if available, then fall back to Claude
            import os

            context_doc = None

            # Code context generation requires file system access - only Claude Code CLI can do this
            # Ollama and Claude API cannot read files, they just generate generic fictional content

            # Try Claude CLI first since it has file access
            try:
                import subprocess

                # Check if Claude CLI is available
                claude_result = subprocess.run(
                    ["claude", "--version"], capture_output=True, text=True, timeout=5
                )
                use_claude_cli = (
                    claude_result.returncode == 0
                    and "Claude Code" in claude_result.stdout
                )

                if use_claude_cli:
                    logger.info(
                        "Using Claude CLI for code context generation (has file access)"
                    )
                    claude_result = subprocess.run(
                        ["claude"],
                        input=analysis_prompt,
                        capture_output=True,
                        text=True,
                        timeout=600,  # 10 minutes - optimize for quality, not speed
                    )

                    if claude_result.returncode == 0:
                        context_doc = claude_result.stdout.strip()
                        logger.info(
                            "Successfully generated code context using Claude CLI"
                        )
                        logger.info(
                            f"Generated context length: {len(context_doc)} chars"
                        )

                        # Log the actual response for debugging
                        if len(context_doc) > 0:
                            logger.info(
                                f"Claude CLI response preview: {context_doc[:500]}..."
                            )

                            # Lower threshold since we're using pre-analyzed data now
                            if len(context_doc.strip()) > 50:
                                return context_doc
                            else:
                                logger.warning(
                                    f"Claude CLI returned very short response ({len(context_doc)} chars): {context_doc}"
                                )
                        else:
                            logger.warning("Claude CLI returned empty response")
                    else:
                        logger.warning(f"Claude CLI failed: {claude_result.stderr}")
                else:
                    logger.warning(
                        "Claude Code CLI not available - cannot access repository files"
                    )

            except Exception as e:
                logger.warning(f"Claude CLI failed: {e}")

            # Fall back to Claude API if available (but warn it can't read files)
            if self.claude_model is not None:
                logger.warning(
                    "Falling back to Claude API - but it cannot read your actual files!"
                )
                logger.warning(
                    "This will generate generic content, not analyze your real codebase"
                )
                try:
                    logger.info(
                        "Using Claude API for code context generation (no file access)"
                    )
                    response = await self._call_model(
                        analysis_prompt, ModelRouter.CLAUDE_CODE
                    )
                    context_doc = str(response).strip() if response else ""

                    if context_doc and len(context_doc.strip()) > 100:
                        logger.warning(
                            "Generated generic context using Claude API (not real codebase)"
                        )
                        return context_doc
                    else:
                        logger.warning(
                            "Claude API returned empty or very short response"
                        )

                except Exception as e:
                    logger.warning(f"Claude API failed: {e}")

            # If no methods worked, generate a helpful error message
            logger.error("CRITICAL: Code context generation failed!")

            error_msg = """Code context generation failed - Claude Code CLI required for file access!

ISSUE: Code context generation needs to read your actual repository files, but:
- Ollama cannot read files (generates generic fictional content)
- Claude API cannot read files (generates generic fictional content)
- Only Claude Code CLI can access and analyze your real codebase

SOLUTIONS:
1. Install Claude Code CLI: https://docs.anthropic.com/en/docs/claude-code
2. Or set ANTHROPIC_API_KEY (but this will generate generic content, not analyze real files)
3. Make sure you're running from the correct repository directory

REQUIRED: Claude Code CLI with file system access for accurate codebase analysis."""

            raise RuntimeError(error_msg)

            # This old fallback code is no longer needed
            if False:
                # Fall back to API key
                from langchain_anthropic import ChatAnthropic
                from langchain_core.messages import HumanMessage

                api_key = os.getenv("ANTHROPIC_API_KEY")
                if not api_key:
                    raise ValueError(
                        "Neither Claude CLI nor ANTHROPIC_API_KEY available"
                    )

                claude_model = ChatAnthropic()  # type: ignore
                response = await claude_model.ainvoke(
                    [HumanMessage(content=analysis_prompt)]
                )
                context_doc = str(response.content).strip() if response.content else ""
                logger.info("Successfully generated code context using Anthropic API")
                logger.debug(f"Generated context length: {len(context_doc)} chars")
                logger.debug("LLM Response (first 1000 chars):")
                logger.debug("=" * 60)
                logger.debug(context_doc[:1000])
                logger.debug("=" * 60)
                if len(context_doc) > 1000:
                    logger.debug(
                        f"... (truncated, full response is {len(context_doc)} chars)"
                    )

                # Validate API response
                if not context_doc or len(context_doc.strip()) == 0:
                    raise ValueError(
                        "Anthropic API returned empty response - no content generated"
                    )
                if len(context_doc.strip()) < 100:
                    logger.warning(
                        f"API response suspiciously short: {len(context_doc.strip())} chars"
                    )
                    logger.warning("Response content:")
                    logger.warning(repr(context_doc))

            return context_doc

        except Exception as e:
            logger.error("CRITICAL: Code context generation failed!")
            logger.error(f"Error details: {e}")
            logger.error(f"Error type: {type(e).__name__}")

            # Don't fallback - fail clearly with detailed error information
            error_details = str(e)
            if "ANTHROPIC_API_KEY" in error_details:
                error_msg = (
                    f"Code context generation failed - No API access available!\n\n"
                    f"ISSUE: {error_details}\n\n"
                    f"SOLUTIONS:\n"
                    f"1. Set ANTHROPIC_API_KEY environment variable\n"
                    f"2. Ensure Claude CLI is working: 'claude --version'\n"
                    f"3. Check Claude CLI permissions if using file-based prompts\n\n"
                    f"Cannot proceed without LLM access for code analysis."
                )
            elif "timeout" in error_details.lower():
                error_msg = (
                    f"Code context generation failed - LLM call timed out!\n\n"
                    f"ISSUE: {error_details}\n\n"
                    f"POSSIBLE CAUSES:\n"
                    f"1. Large repository taking too long to analyze\n"
                    f"2. Network connectivity issues\n"
                    f"3. LLM service overloaded\n\n"
                    f"Try again or check your connection."
                )
            else:
                error_msg = (
                    f"Code context generation failed with unexpected error!\n\n"
                    f"ERROR: {error_details}\n"
                    f"TYPE: {type(e).__name__}\n\n"
                    f"Please check logs for more details and ensure LLM access is configured."
                )

            raise RuntimeError(error_msg) from e

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
        raw_feature_input=None,
        extracted_feature=None,
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
    from langchain_core.runnables import RunnableConfig

    config: RunnableConfig = {"configurable": {"thread_id": workflow.thread_id}}  # type: ignore
    result = await workflow.app.ainvoke(dict(initial_state), config)  # type: ignore

    print(f"Workflow completed. Final quality: {result['quality']}")
    print(f"Artifacts saved to: {workflow.artifacts_dir}")


if __name__ == "__main__":
    asyncio.run(main())
