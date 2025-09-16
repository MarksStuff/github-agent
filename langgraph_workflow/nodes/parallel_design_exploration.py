"""Parallel Design Exploration Node Definition.

This node runs multiple agents in parallel to explore different design approaches
for the feature. Uses Ollama for speed since no code access is needed.
"""

import asyncio
import logging

from ..enums import AgentType, ArtifactName, ModelRouter
from ..node_config import NodeConfig, NodeDefinition, OutputLocation

logger = logging.getLogger(__name__)

# Node Configuration
parallel_design_exploration_config = NodeConfig(
    # Model selection - no code access needed, prefer speed
    needs_code_access=False,
    model_preference=ModelRouter.OLLAMA,
    # Multiple agents for diverse perspectives
    agents=[
        AgentType.ARCHITECT,
        AgentType.SENIOR_ENGINEER,
        AgentType.FAST_CODER,
        AgentType.TEST_FIRST,
    ],
    # Base prompt template
    prompt_template="""You are conducting a design exploration for a new feature.

## Context
**Feature to Implement:** {feature_description}

**Code Context:**
{code_context}

## Your Task
Explore design approaches for implementing this feature. Consider:

1. **Architecture Options**: Different ways to structure the solution
2. **Integration Points**: How this fits with existing code
3. **Implementation Strategy**: High-level approach and key components
4. **Trade-offs**: Pros and cons of different approaches
5. **Risks and Considerations**: Potential challenges and mitigation strategies

## Deliverable
Provide a design exploration that covers:
- 2-3 viable architectural approaches
- Recommended integration points with existing code
- Key components and their responsibilities
- Implementation complexity assessment
- Risk factors and mitigation strategies

Focus on practical, implementable solutions that fit the existing codebase patterns.""",
    # Agent-specific customizations
    agent_prompt_customizations={
        AgentType.ARCHITECT: """
As an Architect, focus on:
- High-level system design and component architecture
- Scalability and maintainability considerations
- Design patterns that fit the existing system
- Integration with current architecture
- Future extensibility and evolution paths""",
        AgentType.SENIOR_ENGINEER: """
As a Senior Engineer, focus on:
- Practical implementation considerations
- Code organization and module structure
- Performance implications and optimizations
- Error handling and edge cases
- Code quality and maintainability aspects""",
        AgentType.FAST_CODER: """
As a Fast Coder, focus on:
- Quick implementation strategies
- Leveraging existing code and patterns
- Minimal viable implementation approach
- Rapid prototyping considerations
- Time-to-delivery optimization""",
        AgentType.TEST_FIRST: """
As a Test-First Engineer, focus on:
- Testability of different design approaches
- Test strategy and coverage considerations
- Mock/stub requirements for testing
- Test automation and CI/CD integration
- Quality assurance aspects of the design""",
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

    # Prepare context for agents
    agent_context = {
        "feature_description": feature_description,
        "code_context": code_context,
        "phase": "design_exploration",
    }

    # Run agents in parallel (mock implementation for now)
    logger.info("🚀 Running parallel design exploration with multiple agents")

    # Simulate parallel agent execution
    agent_analyses = {}

    # Mock agent responses (in real implementation, these would call actual agents)
    agent_analyses[AgentType.ARCHITECT] = await _mock_architect_analysis(agent_context)
    agent_analyses[AgentType.SENIOR_ENGINEER] = await _mock_senior_engineer_analysis(
        agent_context
    )
    agent_analyses[AgentType.FAST_CODER] = await _mock_fast_coder_analysis(
        agent_context
    )
    agent_analyses[AgentType.TEST_FIRST] = await _mock_test_first_analysis(
        agent_context
    )

    # Store agent analyses
    state["agent_analyses"] = agent_analyses

    # Create combined analysis artifact
    combined_analysis = _create_combined_analysis(agent_analyses, feature_description)

    # Save artifact
    from pathlib import Path

    artifacts_path = Path(state.get("repo_path", ".")) / ".local" / "artifacts"
    artifacts_path.mkdir(parents=True, exist_ok=True)

    pr_number = state.get("pr_number")
    if pr_number:
        artifact_path = (
            artifacts_path
            / f"pr-{pr_number}"
            / "design"
            / "explorations"
            / "parallel_design_exploration.md"
        )
    else:
        artifact_path = artifacts_path / "parallel_design_exploration.md"

    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(combined_analysis)

    # Update artifacts index
    if "artifacts_index" not in state:
        state["artifacts_index"] = {}
    state["artifacts_index"]["parallel_design_exploration"] = str(artifact_path)

    logger.info(f"✅ Parallel design exploration completed: {artifact_path}")
    logger.info(f"📊 Generated {len(agent_analyses)} agent perspectives")

    return state


async def _mock_architect_analysis(context: dict) -> str:
    """Mock architect analysis (replace with real agent call)."""
    await asyncio.sleep(0.1)  # Simulate processing time

    return f"""# Architect Analysis: {context['feature_description']}

## Architectural Approaches

### Approach 1: Modular Component Architecture
- Create dedicated module for the new feature
- Use dependency injection for integration
- Maintain separation of concerns
- **Pros**: Clean separation, testable, maintainable
- **Cons**: More initial setup, potential over-engineering

### Approach 2: Extension Pattern
- Extend existing components with new functionality
- Leverage current architecture patterns
- Minimal structural changes
- **Pros**: Quick integration, familiar patterns
- **Cons**: Potential coupling, harder to isolate

### Approach 3: Service Layer Addition
- Add new service layer for feature logic
- Use existing data and presentation layers
- Clear abstraction boundaries
- **Pros**: Good separation, scalable
- **Cons**: Additional complexity, more interfaces

## Recommendation
Approach 1 (Modular Component) for maintainability and future extensibility.

## Integration Points
- Hook into existing routing/middleware
- Leverage current data access patterns
- Extend configuration management
- Integrate with existing logging/monitoring

## Risk Factors
- Breaking existing functionality during integration
- Performance impact on current workflows
- Increased complexity for maintenance team"""


async def _mock_senior_engineer_analysis(context: dict) -> str:
    """Mock senior engineer analysis (replace with real agent call)."""
    await asyncio.sleep(0.1)  # Simulate processing time

    return f"""# Senior Engineer Analysis: {context['feature_description']}

## Implementation Strategy

### Code Organization
- Create feature-specific package/module
- Follow existing naming conventions
- Maintain consistent code style
- Use established error handling patterns

### Key Components
1. **Core Logic Module**: Business logic implementation
2. **Data Access Layer**: Integration with existing data sources
3. **API/Interface Layer**: External interaction points
4. **Configuration Module**: Feature-specific settings
5. **Validation Module**: Input/output validation

### Performance Considerations
- Minimize impact on existing operations
- Consider caching strategies for frequently accessed data
- Implement lazy loading where appropriate
- Monitor memory usage and optimization opportunities

### Error Handling
- Use existing exception hierarchy
- Implement proper logging at all levels
- Graceful degradation when feature unavailable
- Clear error messages for debugging

### Security Considerations
- Input validation and sanitization
- Authentication/authorization integration
- Secure data handling practices
- Audit logging for sensitive operations

## Implementation Complexity: Medium
- Estimated effort: 2-3 development cycles
- Key dependencies: Existing data access patterns
- Testing requirements: Unit + integration tests"""


async def _mock_fast_coder_analysis(context: dict) -> str:
    """Mock fast coder analysis (replace with real agent call)."""
    await asyncio.sleep(0.1)  # Simulate processing time

    return f"""# Fast Coder Analysis: {context['feature_description']}

## Rapid Implementation Strategy

### MVP Approach
- Start with minimal viable implementation
- Use existing patterns and libraries
- Focus on core functionality first
- Iterate and enhance based on feedback

### Quick Wins
- Leverage existing utilities and helpers
- Copy/adapt similar existing features
- Use proven libraries and frameworks
- Minimize custom implementations

### Implementation Steps
1. **Setup**: Create basic module structure (1 hour)
2. **Core Logic**: Implement main functionality (4-6 hours)
3. **Integration**: Hook into existing system (2-3 hours)
4. **Basic Testing**: Essential test cases (2 hours)
5. **Documentation**: Minimal docs and examples (1 hour)

### Time-Saving Strategies
- Reuse existing configuration patterns
- Copy test structures from similar features
- Use existing CI/CD pipeline without changes
- Leverage existing debugging and logging tools

### Technical Shortcuts (with future cleanup plan)
- Start with simple data structures
- Use existing validation where possible
- Implement basic error handling initially
- Plan for future refactoring and optimization

## Delivery Timeline: 1-2 weeks
- Quick prototype: 2-3 days
- Feature complete: 1 week
- Polished implementation: 2 weeks

## Risk Mitigation
- Keep changes minimal and isolated
- Use feature flags for safe rollout
- Implement basic monitoring from day one"""


async def _mock_test_first_analysis(context: dict) -> str:
    """Mock test-first analysis (replace with real agent call)."""
    await asyncio.sleep(0.1)  # Simulate processing time

    return f"""# Test-First Analysis: {context['feature_description']}

## Testing Strategy

### Test Structure
- Unit tests for core business logic
- Integration tests for system interactions
- End-to-end tests for complete workflows
- Performance tests for critical paths

### Test Categories
1. **Unit Tests**: Individual component behavior
2. **Integration Tests**: Component interactions
3. **API Tests**: External interface validation
4. **Data Tests**: Data consistency and validation
5. **Error Tests**: Exception handling and edge cases

### Testability Requirements

### Component Design for Testing
- Dependency injection for mockable dependencies
- Clear separation between pure logic and side effects
- Configurable external integrations
- Observable internal state for verification

### Mock/Stub Strategy
- Mock external services and APIs
- Stub database interactions for unit tests
- Use test doubles for complex dependencies
- Create test fixtures for common scenarios

### Test Data Management
- Use factories for test data creation
- Implement database seeding for integration tests
- Create realistic test scenarios
- Manage test data lifecycle properly

### CI/CD Integration
- Automated test execution on all commits
- Test coverage reporting and enforcement
- Performance regression detection
- Integration with existing quality gates

## Test Coverage Goals
- Unit tests: 90%+ for core logic
- Integration tests: All major workflows
- End-to-end tests: Critical user journeys
- Performance tests: Key performance indicators

## Quality Assurance
- Code review requirements
- Automated linting and formatting
- Security scan integration
- Documentation coverage verification"""


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
