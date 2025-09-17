"""Parallel Design Exploration Node Definition.

This node runs multiple agents in parallel to explore different design approaches
for the feature. Uses Claude CLI since code access is needed for detailed analysis.
"""

import asyncio
import logging

from ..enums import AgentType, ArtifactName, ModelRouter
from ..node_config import NodeConfig, NodeDefinition, OutputLocation

logger = logging.getLogger(__name__)

# Node Configuration
parallel_design_exploration_config = NodeConfig(
    # Model selection - code access needed for detailed analysis
    needs_code_access=True,
    model_preference=ModelRouter.CLAUDE_CODE,
    # Multiple agents for diverse perspectives
    agents=[
        AgentType.ARCHITECT,
        AgentType.SENIOR_ENGINEER,
        AgentType.FAST_CODER,
        AgentType.TEST_FIRST,
    ],
    # Base prompt template
    prompt_template="""You are conducting a high-level design exploration for a new feature. You have access to the codebase to analyze existing patterns and integration points.

## Context

**Feature to Implement:**
{feature_description}

**Code Context Document:**
{code_context}

## Your Task
Create a comprehensive high-level design document for implementing this feature. You have access to the codebase, so please:

1. **Analyze the existing codebase** to understand current patterns, architecture, and conventions
2. **Identify integration points** where this feature would connect with existing code
3. **Propose a detailed design approach** that fits naturally with the current system
4. **Consider implementation details** that align with existing code patterns

## Required Analysis

### 1. Codebase Analysis
- Examine existing code structure and patterns
- Identify relevant modules, classes, and functions
- Understand current architecture and design patterns
- Note coding conventions and styles

### 2. Integration Strategy
- Determine where the feature fits in the current architecture
- Identify existing components that can be leveraged or extended
- Plan data flow and interaction patterns
- Consider backward compatibility requirements

### 3. Design Approach
- Propose specific modules, classes, or functions to create/modify
- Detail the implementation approach that follows existing patterns
- Consider error handling, logging, and testing approaches
- Plan configuration and deployment aspects

### 4. Implementation Roadmap
- Break down the implementation into logical phases
- Identify dependencies and prerequisites
- Estimate complexity and effort
- Plan testing and validation approach

## Deliverable Format
Provide a detailed design document with:

1. **Executive Summary**: Brief overview of the proposed approach
2. **Codebase Analysis**: What you found in the existing code that's relevant
3. **Integration Points**: Specific files, classes, functions that will be affected
4. **Detailed Design**: Technical approach with code structure details
5. **Implementation Plan**: Step-by-step development approach
6. **Risk Assessment**: Potential challenges and mitigation strategies

Focus on creating a practical, implementable design that leverages the existing codebase effectively.""",
    # Agent-specific customizations
    agent_prompt_customizations={
        AgentType.ARCHITECT: """
## Your Role: Software Architect

As an Architect, your design document should emphasize:

**System Design Focus:**
- High-level system architecture and component relationships
- Integration patterns with existing system architecture
- Data flow and service boundaries
- Scalability and performance architecture
- Design patterns and architectural principles

**Analysis Priorities:**
- Examine existing architectural patterns in the codebase
- Identify architectural boundaries and interfaces
- Consider system-wide impacts and dependencies
- Plan for extensibility and future evolution
- Assess architectural risks and mitigation strategies

**Design Document Sections:**
- Focus heavily on "Detailed Design" with architectural diagrams
- Emphasize integration patterns and system boundaries
- Include scalability and performance considerations
- Address security and reliability architectural concerns""",
        AgentType.SENIOR_ENGINEER: """
## Your Role: Senior Engineer

As a Senior Engineer, your design document should emphasize:

**Engineering Excellence Focus:**
- Practical implementation patterns and code organization
- Technical debt and maintainability considerations
- Performance optimization and resource management
- Error handling and resilience patterns
- Code quality and engineering best practices

**Analysis Priorities:**
- Deep dive into existing code patterns and conventions
- Identify reusable components and utilities
- Analyze performance implications of design choices
- Consider deployment and operational aspects
- Evaluate technical risks and complexity

**Design Document Sections:**
- Focus heavily on "Implementation Plan" with detailed steps
- Emphasize engineering best practices and code quality
- Include performance and operational considerations
- Address technical debt and refactoring opportunities""",
        AgentType.FAST_CODER: """
## Your Role: Fast Coder

As a Fast Coder, your design document should emphasize:

**Rapid Development Focus:**
- Minimal viable implementation strategies
- Leveraging existing code and libraries
- Quick wins and iterative development
- Time-to-market optimization
- Pragmatic technical decisions

**Analysis Priorities:**
- Identify existing code that can be reused or adapted
- Find shortcuts and proven patterns to accelerate development
- Minimize custom development through existing solutions
- Plan incremental delivery approach
- Focus on essential features first

**Design Document Sections:**
- Focus heavily on "Implementation Plan" with quick delivery milestones
- Emphasize reuse of existing patterns and components
- Include phased delivery approach
- Address MVP vs. full-feature trade-offs""",
        AgentType.TEST_FIRST: """
## Your Role: Test-First Engineer

As a Test-First Engineer, your design document should emphasize:

**Testing-Driven Design Focus:**
- Testability and test automation strategies
- Test coverage and quality assurance approaches
- Mock/stub architecture for testing
- CI/CD and quality gate integration
- Defect prevention through design

**Analysis Priorities:**
- Examine existing testing patterns and infrastructure
- Identify testable interfaces and boundaries
- Plan test data and fixture requirements
- Consider test automation and coverage strategies
- Evaluate testing complexity and maintenance

**Design Document Sections:**
- Focus heavily on "Implementation Plan" with testing milestones
- Emphasize testable design and quality assurance
- Include comprehensive test strategy
- Address test automation and CI/CD integration""",
    },
    # Output configuration
    output_location=OutputLocation.LOCAL,  # Intermediate exploration
    artifact_names=[ArtifactName.AGENT_ANALYSES],
    artifact_path_template="{base_path}/pr-{pr_number}/design/explorations/{artifact_name}.md",
    # Standard workflows - no code changes, no PR feedback
    requires_code_changes=False,
    requires_pr_feedback=False,
)


async def parallel_design_exploration_handler(state: dict) -> dict:
    """Run parallel design exploration with multiple agents.

    This handler executes multiple agents in parallel to generate diverse
    design perspectives for the feature.
    """
    from ..enums import WorkflowPhase

    logger.info("🎨 Phase 1: Parallel design exploration")

    # Update phase
    state["current_phase"] = WorkflowPhase.PHASE_1_DESIGN_EXPLORATION

    # Get required context
    feature_description = state.get("feature_description", "")
    code_context = state.get("code_context_document", "")

    if not code_context:
        logger.warning("No code context available - design exploration may be limited")
        code_context = "Code context not yet available"

    # Context prepared (feature_description and code_context used directly in agent calls)

    # Run agents in parallel using Claude CLI
    logger.info("🚀 Running parallel design exploration with 4 Claude-based agents")

    # Get repository path for code access
    repo_path = state.get("repo_path", ".")

    # Create tasks for parallel execution
    tasks = []
    agent_types = [
        AgentType.ARCHITECT,
        AgentType.SENIOR_ENGINEER,
        AgentType.FAST_CODER,
        AgentType.TEST_FIRST,
    ]

    for agent_type in agent_types:
        # Create coroutine task for parallel execution
        task = asyncio.create_task(
            _call_claude_agent_for_design(
                agent_type, feature_description, code_context, repo_path
            )
        )
        tasks.append((agent_type, task))

    # Execute all agents in parallel
    logger.info(f"📋 Executing {len(tasks)} agents in parallel...")
    results = await asyncio.gather(*[task for _, task in tasks], return_exceptions=True)

    # Collect results and check for failures
    agent_analyses = {}
    failed_agents = []

    for i, (agent_type, _) in enumerate(tasks):
        result = results[i]
        if isinstance(result, Exception):
            logger.error(f"❌ {agent_type} agent failed: {result}")
            failed_agents.append(agent_type)
        else:
            # result is guaranteed to be str here since it's not an Exception
            result_str = str(result)  # Type narrowing for mypy
            logger.info(f"✅ {agent_type} agent completed ({len(result_str)} chars)")
            agent_analyses[agent_type] = result_str

    # Fail the entire workflow if any agent failed
    if failed_agents:
        error_msg = f"Parallel design exploration failed: {len(failed_agents)} agents failed: {failed_agents}"
        logger.error(f"❌ {error_msg}")
        raise RuntimeError(error_msg)

    # Store agent analyses
    state["agent_analyses"] = agent_analyses

    # Save individual agent documents using consistent artifact path
    from pathlib import Path

    # Use the consistent artifacts path like other nodes
    artifacts_path = Path.home() / ".local" / "share" / "github-agent" / "artifacts"
    artifacts_path.mkdir(parents=True, exist_ok=True)

    pr_number = state.get("pr_number")
    if pr_number:
        base_path = artifacts_path / f"pr-{pr_number}" / "design" / "explorations"
    else:
        base_path = artifacts_path / "design" / "explorations"

    base_path.mkdir(parents=True, exist_ok=True)

    # Save individual agent documents
    agent_artifact_paths = {}
    for agent_type, analysis in agent_analyses.items():
        agent_filename = f"{agent_type.lower().replace('_', '-')}-design.md"
        agent_path = base_path / agent_filename

        # Create individual agent document with header
        agent_document = f"""# {agent_type.replace('_', ' ').title()} Design Document

## Feature: {feature_description}

## Agent Role: {agent_type.replace('_', ' ').title()}

{analysis}

---
*Generated by {agent_type.replace('_', ' ').title()} agent in parallel design exploration phase*
"""
        agent_path.write_text(agent_document)
        agent_artifact_paths[agent_type] = str(agent_path)
        logger.info(f"📄 Created {agent_type} document: {agent_path}")

    # Update artifacts index with individual documents only
    if "artifacts_index" not in state:
        state["artifacts_index"] = {}

    # Add individual agent documents
    for agent_type, path in agent_artifact_paths.items():
        state["artifacts_index"][f"{agent_type.lower()}_design"] = path

    logger.info(
        f"✅ Parallel design exploration completed: {len(agent_analyses)} individual documents"
    )
    logger.info(f"📄 Individual documents: {list(agent_artifact_paths.keys())}")
    logger.info("📋 Agent analyses stored in state for synthesis step")

    return state


async def _call_claude_agent_for_design(
    agent_type: AgentType, feature_description: str, code_context: str, repo_path: str
) -> str:
    """Call Claude CLI agent for design analysis with code access."""
    # Import the Claude CLI calling function
    from .extract_code_context import _call_claude_code_agent

    # Get the base prompt and agent-specific customization
    base_prompt = parallel_design_exploration_config.prompt_template.format(
        feature_description=feature_description, code_context=code_context
    )

    # Get agent-specific customization
    agent_customization = (
        parallel_design_exploration_config.agent_prompt_customizations.get(
            agent_type, ""
        )
    )

    # Combine base prompt with agent-specific instructions
    full_prompt = f"{base_prompt}\n\n{agent_customization}"

    logger.info(
        f"🤖 Calling {agent_type} agent with Claude CLI ({len(full_prompt)} chars)"
    )

    try:
        # Call Claude CLI with code access
        analysis = await _call_claude_code_agent(full_prompt, repo_path)

        # Validate the analysis length (similar to code context validation)
        min_analysis_length = 1000  # Minimum chars for a proper design analysis

        if not analysis:
            raise RuntimeError(f"{agent_type} agent returned no analysis")

        if len(analysis) < min_analysis_length:
            logger.warning(
                f"⚠️  {agent_type} analysis is short ({len(analysis)} chars, expected >{min_analysis_length})"
            )

        return analysis

    except Exception as e:
        error_msg = f"Failed to get analysis from {agent_type} agent: {e!s}"
        logger.error(f"❌ {error_msg}")
        raise RuntimeError(error_msg) from e


def _create_combined_analysis(agent_analyses: dict, feature_description: str) -> str:
    """Combine individual agent analyses into a comprehensive exploration."""

    combined = f"""# Parallel Design Exploration: {feature_description}

## Executive Summary
Multiple agents have explored different aspects of implementing this feature.
Each perspective provides valuable insights for the design and implementation approach.

"""

    for agent_type, analysis in agent_analyses.items():
        combined += f"""
## {agent_type.replace('_', ' ').title()} Perspective

{analysis}

---
"""

    combined += """
## Synthesis and Next Steps

Based on the parallel exploration above, the following synthesis emerges:

### Recommended Approach
- Combine architectural rigor with practical implementation considerations
- Start with MVP approach but design for extensibility
- Implement comprehensive testing from the beginning
- Focus on integration with existing patterns

### Key Decision Points
1. **Architecture**: Modular vs. Extension vs. Service Layer
2. **Implementation Speed**: MVP vs. Full Implementation
3. **Testing Strategy**: Test coverage vs. delivery speed
4. **Integration**: New patterns vs. existing conventions

### Next Phase
Proceed to architect synthesis to resolve decision points and create unified design approach.
"""

    return combined


# Node Definition
parallel_design_exploration_node = NodeDefinition(
    config=parallel_design_exploration_config,
    handler=parallel_design_exploration_handler,
    description="Runs multiple agents in parallel to explore diverse design approaches for the feature",
)
