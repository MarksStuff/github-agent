"""Design Synthesis Node Definition.

This node analyzes the parallel design exploration results to identify:
- Design ideas that all agents agree on
- Design ideas that some agents propose without disagreement
- Design ideas where agents disagree
- Provides structured feedback section for human input
"""

import logging
from pathlib import Path

from ..enums import AgentType, ArtifactName, ModelRouter, WorkflowPhase
from ..node_config import NodeConfig, NodeDefinition, OutputLocation

logger = logging.getLogger(__name__)

# Node Configuration
design_synthesis_config = NodeConfig(
    # Model selection - Ollama for synthesis (no code access needed)
    needs_code_access=False,
    model_preference=ModelRouter.OLLAMA,
    # Single synthesis agent
    agents=[AgentType.SENIOR_ENGINEER],
    # Prompt template for consensus analysis
    prompt_template="""You are a senior engineer consolidating 4 design reviews from different agent perspectives. Your task is to create a structured synthesis focusing on agreements and disagreements between the agents.

## Feature to Implement:
{feature_description}

## Agent Design Documents:

### Architect Perspective:
{architect_design}

### Senior Engineer Perspective:
{senior_engineer_design}

### Fast Coder Perspective:
{fast_coder_design}

### Test-First Engineer Perspective:
{test_first_design}

## Your Task: Consolidation Analysis

Read all 4 design reviews and consolidate them focusing on:

1. **Everything where agents agree on, and nobody disagrees**
2. **Everything where 2 or more agents disagree on**

## Required Output Format:

# Design Synthesis: {feature_description}

## 1. Areas of Agreement
*Document all aspects where agents agree and no one disagrees*

### Architecture & Design Patterns
- **Consensus**: [What all agents agree on or propose similarly]
- **Supporting Agents**: [List which agents support this]
- **Details**: [Specific implementation details agreed upon]

### Technical Approach
- **Consensus**: [Agreed technical approaches]
- **Supporting Agents**: [List which agents support this]
- **Details**: [Implementation specifics]

### Implementation Strategy
- **Consensus**: [Agreed implementation strategies]
- **Supporting Agents**: [List which agents support this]
- **Details**: [Step-by-step approach agreed upon]

## 2. Areas of Disagreement
*Document all aspects where 2 or more agents disagree*

### [Disagreement Topic 1]
- **Conflicting Positions**:
  - **Agent 1 (e.g., Architect)**: [Their position/approach]
  - **Agent 2 (e.g., Senior Engineer)**: [Their different position/approach]
  - **Agent 3 (if applicable)**: [Their position if different]
- **Key Differences**: [What specifically they disagree on]
- **Impact**: [How this disagreement affects the implementation]

### [Disagreement Topic 2]
- **Conflicting Positions**:
  - **Agent A**: [Position]
  - **Agent B**: [Different position]
- **Key Differences**: [Specifics of disagreement]
- **Impact**: [Implementation impact]

## 3. Recommended Resolution
Based on the analysis above, provide recommendations for resolving disagreements and moving forward with implementation.

### Priority Decisions Needed
1. **[Disagreement 1]**: [Recommendation for resolution]
2. **[Disagreement 2]**: [Recommendation for resolution]

### Suggested Implementation Path
- **Phase 1**: [Based on agreements, what can be implemented immediately]
- **Phase 2**: [What requires decision resolution first]

---

**Analysis Instructions:**
- Be thorough in identifying both agreements and disagreements
- Quote specific text from agent documents to support your analysis
- Focus on practical implementation implications
- Clearly distinguish between areas of consensus vs. conflict""",
    # Agent customizations
    agent_prompt_customizations={
        AgentType.SENIOR_ENGINEER: """
As the consolidating senior engineer, focus on:
- Identifying practical engineering consensus and conflicts
- Analyzing implementation implications of agreements/disagreements
- Providing clear recommendations for resolving conflicts
- Highlighting areas where team discussion is needed
- Ensuring the synthesis is actionable for implementation
"""
    },
    # Output configuration
    output_location=OutputLocation.REPOSITORY,  # Store in repo for commit/push
    artifact_names=[ArtifactName.DESIGN_SYNTHESIS],
    artifact_path_template="design-synthesis-{feature_name}.md",
    # Standard workflows - will be committed to repository
    requires_code_changes=False,
    requires_pr_feedback=False,
)


async def design_synthesis_handler(state: dict) -> dict:
    """Analyze parallel design exploration results and create synthesis document.

    This handler creates a comprehensive analysis of agent consensus, conflicts,
    and provides structured areas for human feedback and decision-making.
    """
    logger.info("🔀 Phase 1.5: Design synthesis and consensus analysis")

    # Update phase
    state["current_phase"] = WorkflowPhase.PHASE_1_DESIGN_EXPLORATION

    # Get required context
    feature_description = state.get("feature_description", "")
    agent_analyses = state.get("agent_analyses", {})

    if not agent_analyses:
        error_msg = "No agent analyses available for synthesis"
        logger.error(f"❌ {error_msg}")
        raise RuntimeError(f"Design synthesis failed: {error_msg}")

    if len(agent_analyses) < 4:
        logger.warning(
            f"⚠️  Only {len(agent_analyses)} agent analyses available (expected 4)"
        )

    # Extract individual agent analyses
    architect_design = agent_analyses.get(AgentType.ARCHITECT, "Not available")
    senior_engineer_design = agent_analyses.get(
        AgentType.SENIOR_ENGINEER, "Not available"
    )
    fast_coder_design = agent_analyses.get(AgentType.FAST_CODER, "Not available")
    test_first_design = agent_analyses.get(AgentType.TEST_FIRST, "Not available")

    # Format the synthesis prompt
    prompt = design_synthesis_config.prompt_template.format(
        feature_description=feature_description,
        architect_design=architect_design,
        senior_engineer_design=senior_engineer_design,
        fast_coder_design=fast_coder_design,
        test_first_design=test_first_design,
    )

    logger.info(
        f"🧠 Calling synthesis agent with design analysis prompt ({len(prompt)} chars)"
    )

    # Call the synthesis agent using Ollama
    if design_synthesis_config.model_preference == ModelRouter.OLLAMA:
        # Use Ollama for design synthesis
        from langchain_core.messages import HumanMessage
        from langchain_ollama import ChatOllama

        from ..config import get_ollama_base_url, get_ollama_model

        # Create Ollama model instance
        model = ChatOllama(
            model=get_ollama_model("default"),
            base_url=get_ollama_base_url(),
            temperature=0.3,
        )

        logger.info("🔥 Calling Ollama for design synthesis...")

        # Call Ollama with the synthesis prompt
        response = await model.ainvoke([HumanMessage(content=prompt)])

        # Extract the synthesis document from the response
        if isinstance(response.content, str):
            synthesis_document = response.content
        else:
            synthesis_document = str(response.content)

        logger.info(f"✅ Ollama synthesis completed ({len(synthesis_document)} chars)")
    else:
        raise RuntimeError(
            "Design synthesis is configured to use Ollama for consolidation analysis."
        )

    # Validate synthesis quality
    min_synthesis_length = 3000  # Comprehensive synthesis should be substantial
    if not synthesis_document or len(synthesis_document) < min_synthesis_length:
        error_msg = (
            f"Design synthesis document too short ({len(synthesis_document) if synthesis_document else 0} chars, "
            f"minimum: {min_synthesis_length}). Synthesis requires detailed analysis of all agent perspectives."
        )
        logger.error(f"❌ {error_msg}")
        raise RuntimeError(f"Design synthesis failed: {error_msg}")

    # Store synthesis document
    state["synthesis_document"] = synthesis_document

    # Store synthesis document in repository for commit/push
    repo_path = Path(state.get("repo_path", "."))

    # Create a clean feature name for the filename
    feature_name = feature_description.strip()
    # Remove problematic characters and limit length
    feature_name = "".join(
        c for c in feature_name if c.isalnum() or c in (" ", "-", "_")
    ).strip()
    feature_name = feature_name.replace(" ", "-").lower()[:50]

    if not feature_name:
        feature_name = "unknown-feature"

    # Save synthesis document in repository root
    synthesis_filename = f"design-synthesis-{feature_name}.md"
    synthesis_path = repo_path / synthesis_filename

    synthesis_path.write_text(synthesis_document)
    logger.info(f"📄 Synthesis document saved to repository: {synthesis_path}")

    # Update artifacts index
    if "artifacts_index" not in state:
        state["artifacts_index"] = {}
    state["artifacts_index"]["design_synthesis"] = str(synthesis_path)

    logger.info(f"✅ Design synthesis completed: {synthesis_path}")
    logger.info(f"📊 Analyzed {len(agent_analyses)} agent perspectives")
    logger.info("📋 Document saved in repository, ready for commit and push")

    return state


# Node Definition
design_synthesis_node = NodeDefinition(
    config=design_synthesis_config,
    handler=design_synthesis_handler,
    description="Analyzes parallel design exploration results to identify consensus, conflicts, and areas needing human feedback",
)
