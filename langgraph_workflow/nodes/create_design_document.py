"""Create Design Document Node Definition.

This node creates a comprehensive design document that will be reviewed via PR comments.
Integrates PR feedback workflow to incorporate review comments.
"""

import logging
from datetime import datetime

from ..enums import AgentType, ArtifactName, ModelRouter
from ..node_config import NodeConfig, NodeDefinition, OutputLocation

logger = logging.getLogger(__name__)

# Node Configuration
create_design_document_config = NodeConfig(
    # Model selection - no code access needed for design doc creation
    needs_code_access=False,
    model_preference=ModelRouter.OLLAMA,
    # Single agent for coherent document creation
    agents=[AgentType.ARCHITECT],
    # Prompt template
    prompt_template="""You are creating a comprehensive Design Document for a feature implementation.

## Context
**Feature to Implement:** {feature_description}

**Code Context:**
{code_context}

**Design Exploration Results:**
{design_exploration}

## Your Task
Create a detailed, implementable design document that synthesizes the exploration results into a concrete plan.

## Design Document Structure

### 1. FEATURE OVERVIEW
- Clear description of what will be implemented
- User value and business justification
- Success criteria and acceptance criteria

### 2. TECHNICAL APPROACH
- Chosen architectural approach (with rationale)
- Key components and their responsibilities
- Data flow and interaction patterns
- Integration points with existing code

### 3. IMPLEMENTATION PLAN
- Development phases and milestones
- Key tasks and estimated effort
- Dependencies and prerequisites
- Risk mitigation strategies

### 4. API/INTERFACE DESIGN
- External interfaces (REST endpoints, CLI commands, etc.)
- Internal interfaces between components
- Data models and schemas
- Error handling approach

### 5. DATA CONSIDERATIONS
- Data requirements and storage needs
- Migration considerations (if applicable)
- Performance and scalability requirements
- Security and privacy implications

### 6. TESTING STRATEGY
- Unit testing approach and coverage
- Integration testing requirements
- End-to-end testing scenarios
- Performance and load testing needs

### 7. DEPLOYMENT AND OPERATIONS
- Deployment strategy and rollout plan
- Configuration management
- Monitoring and observability
- Maintenance and support considerations

## Requirements
- Be specific and actionable
- Include concrete examples where helpful
- Consider edge cases and error scenarios
- Align with existing codebase patterns
- Provide clear implementation guidance""",
    # Agent customizations
    agent_prompt_customizations={
        AgentType.ARCHITECT: """
As an Architect, ensure the design document:
- Follows established architectural principles
- Maintains system cohesion and consistency
- Considers long-term maintainability and evolution
- Addresses scalability and performance requirements
- Includes proper abstractions and interfaces
- Aligns with existing system architecture patterns"""
    },
    # Output configuration - goes to repository for review
    output_location=OutputLocation.REPOSITORY,
    artifact_names=[ArtifactName.DESIGN_DOCUMENT],
    artifact_path_template="{base_path}/pr-{pr_number}/design/{artifact_name}.md",
    # Standard workflows - no code changes but needs PR feedback
    requires_code_changes=False,
    requires_pr_feedback=True,
    # PR feedback configuration
    pr_feedback_prompt="""Review and incorporate the following PR comments into the design document:

{comments}

Update the design document to address the feedback while maintaining coherence and completeness.
Focus on:
- Clarifying ambiguous sections
- Adding missing details or considerations
- Adjusting technical approach based on review input
- Improving implementation guidance
- Resolving any identified issues or concerns""",
    pr_reply_template="""✅ Design document updated based on feedback.

**Changes made:** {outcome}

**Updated at:** {timestamp}

The design document has been revised to incorporate your suggestions. Please review the updated version and let me know if additional changes are needed.""",
)


async def create_design_document_handler(state: dict) -> dict:
    """Create a comprehensive design document.

    This handler synthesizes the design exploration results into a concrete,
    implementable design document.
    """
    from ..enums import WorkflowPhase

    logger.info("📋 Phase 2: Creating design document")

    # Update phase
    state["current_phase"] = WorkflowPhase.PHASE_2_DESIGN_DOCUMENT

    # Get required context
    feature_description = state.get("feature_description", "")
    code_context = state.get("code_context_document", "")
    agent_analyses = state.get("agent_analyses", {})

    # Combine agent analyses into design exploration summary
    design_exploration = _summarize_design_exploration(agent_analyses)

    if not design_exploration:
        logger.warning(
            "No design exploration available - creating basic design document"
        )
        design_exploration = "Design exploration results not available"

    # Create the design document
    design_document = await _create_design_document(
        feature_description, code_context, design_exploration
    )

    # Store design document
    state["design_document"] = design_document

    # Save artifact
    from pathlib import Path

    repo_path = Path(state.get("repo_path", "."))

    pr_number = state.get("pr_number")
    if pr_number:
        artifact_path = repo_path / f"pr-{pr_number}" / "design" / "design_document.md"
    else:
        artifact_path = repo_path / ".local" / "artifacts" / "design_document.md"

    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(design_document)

    # Update artifacts index
    if "artifacts_index" not in state:
        state["artifacts_index"] = {}
    state["artifacts_index"]["design_document"] = str(artifact_path)

    logger.info(f"📄 Design document created: {artifact_path}")

    # Mark as ready for review if in repository
    if pr_number:
        state["design_document_ready_for_review"] = True
        logger.info(f"📝 Design document ready for PR #{pr_number} review")

    return state


def _summarize_design_exploration(agent_analyses: dict) -> str:
    """Summarize the design exploration results for the design document."""
    if not agent_analyses:
        return ""

    summary = "## Design Exploration Summary\n\n"

    for agent_type, analysis in agent_analyses.items():
        # Extract key points from each analysis (simplified extraction)
        summary += f"### {agent_type.replace('_', ' ').title()} Insights\n"

        # Extract first few bullet points or sentences
        lines = analysis.split("\n")
        key_points = []
        for line in lines:
            if line.strip().startswith("-") or line.strip().startswith("*"):
                key_points.append(line.strip())
                if len(key_points) >= 3:
                    break

        if key_points:
            summary += "\n".join(key_points) + "\n\n"
        else:
            # Fallback: use first paragraph
            paragraphs = analysis.split("\n\n")
            if len(paragraphs) > 1:
                summary += paragraphs[1][:200] + "...\n\n"

    return summary


async def _create_design_document(
    feature_description: str, code_context: str, design_exploration: str
) -> str:
    """Create the actual design document content."""

    # For now, create a structured design document template
    # In real implementation, this would call the configured agent

    document = f"""# Design Document: {feature_description}

**Created:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Status:** Draft - Pending Review

## 1. FEATURE OVERVIEW

### Description
{feature_description}

### User Value
This feature will provide significant value by enabling users to {feature_description.lower()}.

### Success Criteria
- Feature is successfully implemented and integrated
- All existing functionality continues to work
- Performance impact is minimal
- Code quality standards are maintained

### Acceptance Criteria
- [ ] Core functionality is implemented
- [ ] Integration tests pass
- [ ] Documentation is updated
- [ ] Performance benchmarks are met

## 2. TECHNICAL APPROACH

### Architectural Approach
Based on the design exploration, we will implement a modular component architecture that:
- Maintains separation of concerns
- Integrates cleanly with existing patterns
- Provides clear interfaces for testing
- Allows for future extensibility

### Key Components
1. **Core Logic Module**: Implements the main feature functionality
2. **Integration Layer**: Handles interaction with existing system components
3. **Configuration Module**: Manages feature-specific settings
4. **Validation Module**: Ensures input/output correctness

### Data Flow
```
Input → Validation → Core Logic → Integration Layer → Output
```

### Integration Points
- Existing API endpoints (if applicable)
- Database schema extensions (if needed)
- Configuration system integration
- Logging and monitoring hooks

## 3. IMPLEMENTATION PLAN

### Phase 1: Foundation (Week 1)
- Set up basic module structure
- Implement core data models
- Create basic configuration support
- Set up initial tests

### Phase 2: Core Implementation (Week 2-3)
- Implement main feature logic
- Add integration with existing components
- Expand test coverage
- Initial performance optimization

### Phase 3: Polish and Integration (Week 4)
- Complete integration testing
- Performance tuning
- Documentation updates
- Final code review and cleanup

### Dependencies
- Existing codebase patterns and utilities
- Current development environment setup
- Access to testing environments

### Risk Mitigation
- Implement feature flags for safe rollout
- Maintain backward compatibility
- Create rollback procedures
- Monitor performance impact

## 4. API/INTERFACE DESIGN

### External Interfaces
(To be defined based on specific feature requirements)

### Internal Interfaces
```python
class FeatureInterface:
    def execute(self, input_data: InputModel) -> OutputModel:
        \"\"\"Main feature execution interface.\"\"\"
        pass

    def validate_input(self, data: Any) -> bool:
        \"\"\"Validate input data.\"\"\"
        pass

    def configure(self, config: ConfigModel) -> None:
        \"\"\"Configure feature behavior.\"\"\"
        pass
```

### Data Models
```python
class InputModel:
    # Input data structure
    pass

class OutputModel:
    # Output data structure
    pass

class ConfigModel:
    # Configuration structure
    pass
```

### Error Handling
- Use existing exception hierarchy
- Provide clear error messages
- Implement proper logging
- Graceful degradation strategies

## 5. DATA CONSIDERATIONS

### Data Requirements
- Identify any new data storage needs
- Consider data migration requirements
- Plan for data backup and recovery

### Performance Requirements
- Response time targets: < 500ms for typical operations
- Throughput targets: Support existing load + 20%
- Memory usage: Minimal impact on current usage

### Security Considerations
- Input validation and sanitization
- Access control integration
- Audit logging for sensitive operations
- Data encryption if handling sensitive data

## 6. TESTING STRATEGY

### Unit Testing
- Test coverage target: 90%+ for core logic
- Use existing testing frameworks and patterns
- Mock external dependencies
- Test edge cases and error conditions

### Integration Testing
- Test all integration points
- Verify backward compatibility
- Test configuration scenarios
- Performance regression testing

### End-to-End Testing
- Complete workflow validation
- User scenario testing
- Cross-browser testing (if applicable)
- Load testing for performance validation

## 7. DEPLOYMENT AND OPERATIONS

### Deployment Strategy
- Gradual rollout using feature flags
- Monitor key metrics during deployment
- Rollback procedures if issues detected
- Communication plan for stakeholders

### Configuration Management
- Environment-specific configuration
- Runtime configuration updates (if needed)
- Configuration validation
- Default value management

### Monitoring and Observability
- Key performance indicators (KPIs)
- Error rate monitoring
- Usage analytics
- System health checks

### Maintenance and Support
- Documentation for operations team
- Troubleshooting guides
- Support procedures
- Update and patching strategy

## 8. OPEN QUESTIONS AND DECISIONS

### Questions Requiring Input
- [ ] Specific performance requirements?
- [ ] User interface requirements (if applicable)?
- [ ] Integration timeline constraints?
- [ ] Resource allocation and team assignments?

### Decisions Made
- Architecture: Modular component approach
- Testing: Comprehensive test coverage strategy
- Deployment: Feature flag-based gradual rollout

### Decisions Pending
- Specific API design details
- Performance optimization priorities
- Documentation format and location

---

## NEXT STEPS

1. **Review and Approval**: Stakeholder review of this design document
2. **Implementation Planning**: Detailed task breakdown and assignment
3. **Environment Setup**: Prepare development and testing environments
4. **Implementation Start**: Begin Phase 1 development

**Note**: This design document is living and will be updated based on feedback and implementation discoveries.
"""

    return document


# Node Definition
create_design_document_node = NodeDefinition(
    config=create_design_document_config,
    handler=create_design_document_handler,
    description="Creates a comprehensive design document that synthesizes exploration results into an implementable plan",
)
