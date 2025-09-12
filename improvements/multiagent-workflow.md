# Multi-Agent Development Workflow

## Overview

This document describes a collaborative workflow for feature development using four specialized AI agents, designed to minimize bias, maximize collaboration, and efficiently use available resources (Ollama for free tasks, Claude Code for code access tasks).

## The Four Agents

1. **Test-first**: Focuses on testable code and comprehensive test coverage
2. **Fast-coder**: Prioritizes rapid implementation and iteration
3. **Senior Engineer**: Emphasizes simplicity, design patterns, and removing duplication
4. **Architect**: Focuses on overall system architecture and scalability

## Complete End-to-End Workflow

## Phase 0: Code Context Extraction

### Step 1: Code Analysis
**[CLAUDE CODE - Needs code access]**
- Senior engineer analyzes existing codebase and creates **Code Context Document** containing:
  - Current architecture overview
  - Existing patterns and conventions
  - Available infrastructure/libraries
  - Key interfaces and contracts
  - Technical constraints
  - Areas marked as "legacy" or "refactor-friendly"
  - Database schemas and data models
  - Authentication/authorization approach
  - Error handling patterns
  - Testing conventions

## Phase 1: Parallel Design Exploration + Synthesis

### Step 1: Parallel Initial Analysis
**[OLLAMA - No code access needed]**
- All 4 agents receive simultaneously:
  - Feature description
  - Code Context Document
- Each agent produces their perspective in isolation:
  - **Test-first**: Acceptance criteria and test scenarios (considering existing test patterns)
  - **Fast-coder**: Quick implementation sketch/pseudocode (using existing infrastructure)
  - **Senior engineer**: Key abstractions and patterns to consider (aligned with current patterns)
  - **Architect**: System integration points and scalability concerns (within current architecture)

### Step 2: Architect-Led Synthesis
**[OLLAMA - No code access needed]**
- Architect creates a Design Synthesis document containing:
  - **Common Themes**: Areas where 2+ agents align
  - **Conflicts**: Explicit disagreements or tension points
  - **Trade-offs**: What each approach optimizes for
  - **Questions Requiring Code Investigation**: Specific unknowns about existing code
- Architect remains neutral, documenting rather than judging

### Step 3: Targeted Code Investigation (if needed)
**[CLAUDE CODE - Needs code access]**
- Only if critical questions identified in synthesis
- Architect investigates specific code areas to answer questions
- Updates synthesis with findings
- Minimal code access, targeted queries only

### Step 4: Human Review & Decision
**[HUMAN - No AI needed]**
- You receive the synthesis via GitHub PR and:
  - Comment on common themes (approve or refine)
  - Decide on conflicts via PR comments
  - Add missing considerations in "Additional Considerations" empty section
  - Output: **Design Constraints Document**

## Phase 2: Collaborative Design Document

### Setup
**[OLLAMA - No code access needed]**
- Create GitHub PR with template document including:
  ```markdown
  ## Design Document
  
  ### Core Design
  [Agent content here]
  
  ### Human Additions
  <!-- Empty section for human to comment -->
  
  ### Arbitration History
  <!-- Auto-populated from PR comments -->
  
  ### Unresolved Questions
  <!-- Agents add items needing human input -->
  ```

### Iterative Document Building
**[OLLAMA - No code access needed]**
1. Random agent adds/modifies a section (commits to PR)
2. All other agents immediately review the addition
3. If any agent objects → Creates "Request Changes" on PR
4. Human arbitrates via PR comment → Decision logged in **Arbitration Log**
5. First agent action after human comment: Copy comment verbatim into document
6. Continue with another random agent

### Completion Criteria
**[OLLAMA - No code access needed]**
Document is complete when all 4 agents agree:
- Everything necessary is covered
- No new disagreements exist
- All concerns have been addressed or arbitrated
- Document aligns with Code Context Document

### Output
- **Complete Design Document** with acceptance tests
- **Arbitration Log** (prevents re-litigation of decisions)

## Phase 3: Implementation with Parallel Development

### Round 1: Structure & Test Setup

#### Step 1: Skeleton Creation
**[CLAUDE CODE - Needs code access]**
- Senior engineer writes skeleton of all classes and methods (signatures only, no implementation)
- Creates PR with skeleton
- Architect reviews skeleton for system consistency and integration points
- If disagreement → Human arbitrates via PR comments

#### Step 2: Parallel Development
- Test-first writes comprehensive unit tests using the skeleton **[CLAUDE CODE - Needs code access]**
  - Creates `tests-initial` branch
  - Writes tests WITHOUT seeing implementation
- Fast-coder implements the classes/methods **[CLAUDE CODE - Needs code access]**
  - Creates `implementation-initial` branch  
  - Writes code WITHOUT seeing tests
- Both work until their parts are "complete" (tests executable, code compiles)

#### Step 3: Reconciliation
**[CLAUDE CODE - Needs code access]**
- Create reconciliation PR merging both branches
- Identify mismatches visible in GitHub:
  - Test doesn't compile (coder changed signatures)
  - Test fails (behavior mismatch)
  - Test assumptions wrong
  - Missing error cases
  - Incompatible approaches (sync vs async)
- Resolution process:
  - Fast-coder and Test-first each argue their case via PR comments
  - Senior engineer proposes solution
  - Architect weighs in on system impact
  - If no consensus → Human arbitrates via PR comment with architect's recommendation

### Round 2: Component Tests
**[CLAUDE CODE - Needs code access]**
- Test-first writes component tests (with unit tests now passing)
- Fast-coder refactors implementation if needed
- Senior engineer reviews for patterns and duplication
- Same reconciliation process for conflicts via PR

### Round 3: Integration Tests
**[CLAUDE CODE - Needs code access]**
- Test-first writes integration tests
- Architect ensures scalability concerns are tested
- Fast-coder optimizes implementation where needed
- Final reconciliation via PR

### Round 4: Refinement
**[CLAUDE CODE - Needs code access]**
- Senior engineer leads refactoring for simplicity and patterns
- All agents review final code via PR
- Human approval for deployment readiness

## Resource Usage Summary

### Ollama (Free) Usage
- Phase 1: Design exploration and synthesis (except targeted investigation)
- Phase 2: All design document creation
- **Total**: ~35-40% of agent work

### Claude Code (Paid) Usage
- Phase 0: Initial code context extraction
- Phase 1: Targeted investigation (if needed)
- Phase 3: All implementation work
- **Total**: ~60-65% of agent work

## Key Artifacts

1. **Code Context Document** (from Phase 0, periodically updated)
2. **Design Constraints Document** (from Phase 1)
3. **Arbitration Log** (accumulated from Phase 2 onward)
4. **Design Document with Acceptance Tests** (from Phase 2)
5. **Working Code with Full Test Coverage** (from Phase 3)

## Human Touch Points

### When You Are Involved
- **Phase 1**: Reviewing synthesis, deciding conflicts, adding considerations (via PR)
- **Phase 2**: Arbitrating any disagreement during document building (via PR)
- **Phase 3**: 
  - Skeleton disagreements (via PR)
  - Test/implementation reconciliation conflicts (via PR)
  - Final approval (via PR)

### When You Are NOT Involved
- Code Context Document creation (Phase 0)
- Agents work in parallel (Phase 1 initial, Phase 3 development)
- Agents agree on additions (Phase 2)
- Reconciliation reaches consensus (Phase 3)

## GitHub Integration Strategy

### PR Structure
- **All human decisions**: Via PR comments
- **All conflicts**: Raised as "Request Changes" on PR
- **All arbitrations**: Logged as resolved PR threads
- **Human additions**: Comments on empty sections, then copied verbatim
- **Branch strategy**:
  - `design-doc` branch for Phases 1-2
  - `skeleton` branch for Phase 3 skeleton
  - `tests-initial` and `implementation-initial` for parallel development
  - `main` for final merged code

### GitHub Labels
- `needs-human`: Requires human decision
- `conflict`: Agents disagree
- `arbitrated`: Human has made decision
- `ollama-task`: Can be done with Ollama
- `claude-code-task`: Requires Claude Code

### Comment-to-Document Flow
1. Human adds comment on empty section or inline
2. Next agent's first action: Copy comment verbatim into document
3. Agents respond/incorporate the feedback
4. Original comment gets marked as "Resolved"

## Key Design Principles

### Avoiding Order Bias
- Parallel initial exploration (all agents work simultaneously)
- Random order for sequential contributions
- Blind parallel development (tests and code written separately)
- Arbitration log prevents re-litigation of settled issues

### Efficient Escalation
- Immediate stop on disagreement
- Clear escalation to human via PR
- Logged decisions prevent circular debates
- Consensus-based completion criteria

### Resource Optimization
- Maximum use of free Ollama for design work
- Claude Code only when code access is essential
- Batching of code-related tasks when possible
- Code Context Document enables informed design without constant code access

## Example Workflows

### Example: Adding User Authentication Feature

1. **Phase 0**: Senior engineer analyzes existing auth infrastructure, creates context document
2. **Phase 1**: All agents design authentication approach based on context
3. **Phase 2**: Collaborative creation of detailed design with JWT tokens, refresh strategy
4. **Phase 3**: 
   - Skeleton includes `AuthService`, `TokenManager`, middleware interfaces
   - Tests written for login, logout, token refresh scenarios
   - Implementation includes JWT generation, validation logic
   - Reconciliation resolves token storage approach (cookies vs headers)

### Example: Conflict Resolution via GitHub

1. Fast-coder commits: "Use in-memory cache for sessions"
2. Architect requests changes: "This won't scale beyond single instance"
3. Human comments: "Use Redis for session storage, but make it configurable for local development"
4. Agent copies human comment verbatim into design document
5. Arbitration logged, Redis decision is final

## Best Practices

### For Humans
- Keep arbitration decisions concise and clear
- Provide rationale for decisions to prevent future similar conflicts
- Use GitHub's suggestion feature for specific text changes
- Review the Arbitration Log before making decisions to ensure consistency

### For Agent Configuration
- Agents should cite the Code Context Document when referencing existing patterns
- Agents should explicitly state when they're unsure about existing code
- Agents should flag when design decisions might require significant refactoring
- Agents should respect previous arbitrations absolutely

## Optimization Tips

### Minimizing Claude Code Costs
1. **Thorough Phase 0**: Comprehensive Code Context Document reduces later investigations
2. **Extended design phases**: More design iteration in Ollama = less implementation iteration
3. **Batch code tasks**: Accumulate multiple code tasks before switching to Claude Code
4. **Documentation in Ollama**: Switch back to Ollama for documentation-only updates

### Maximizing Efficiency
1. **Clear feature descriptions**: Better input = less iteration
2. **Early conflict resolution**: Resolve design conflicts before implementation
3. **Parallel work**: Maximize parallel agent work to reduce total time
4. **Reusable artifacts**: Update Code Context Document after each feature

## Appendix: Document Templates

### Code Context Document Template
```markdown
# Code Context Document

## Architecture Overview
[High-level system architecture]

## Technology Stack
- Languages: 
- Frameworks:
- Databases:
- Infrastructure:

## Design Patterns
[List of patterns used consistently]

## Code Conventions
- Naming conventions:
- File structure:
- Error handling:
- Testing approach:

## Key Interfaces
[Important interfaces/contracts]

## Infrastructure Services
[Available services and how to use them]

## Legacy Areas
[Code that needs refactoring]

## Recent Changes
[Recent architectural decisions]
```

### Design Synthesis Template
```markdown
# Design Synthesis: [Feature Name]

## Common Themes
- [Theme 1 - which agents agreed]
- [Theme 2 - which agents agreed]

## Conflicts
### Conflict 1: [Name]
- Agent A position:
- Agent B position:
- Trade-offs:

## Questions for Code Investigation
- [ ] Question 1
- [ ] Question 2

## Additional Considerations
<!-- Human adds thoughts here -->
```

### Design Document Template
```markdown
# Design Document: [Feature Name]

## Overview
[Feature description and goals]

## Acceptance Criteria
[From Test-first agent]

## Technical Design
[Detailed technical approach]

## Implementation Plan
[Step-by-step implementation]

## Human Additions
<!-- Empty section for human to comment -->

## Arbitration History
<!-- Auto-populated from PR comments -->

## Unresolved Questions
<!-- Agents add items needing human input -->
```

## LangGraph Implementation Considerations

While this workflow is implementation-agnostic, here are key considerations for LangGraph:

### State Management
- Track which agent contributed what
- Maintain arbitration log
- Track completion status for each phase
- Store all artifacts (Code Context, Design Doc, etc.)

### Node Types
- **Parallel nodes**: Phase 1 initial analysis
- **Sequential nodes**: Phase 2 document building
- **Conditional edges**: Based on agreement/disagreement
- **Human-in-the-loop nodes**: All arbitration points

### Checkpointing
- Save state after each human decision
- Allow resumption from any point
- Maintain full history for audit trail

### Agent Prompts
Each agent needs clear instructions about:
- Their role and focus area
- When to object vs accept
- How to respect arbitration log
- How to build on others' work

## Metrics and Success Criteria

### Efficiency Metrics
- Time from feature request to deployed code
- Number of human interventions required
- Percentage of decisions reaching consensus without arbitration
- Claude Code usage vs Ollama usage ratio

### Quality Metrics
- Test coverage achieved
- Number of post-deployment bugs
- Code review feedback from human developers
- Adherence to existing patterns (from Code Context Document)

### Process Metrics
- Number of conflicts per feature
- Average time to resolve conflicts
- Number of re-litigated decisions (should be zero)
- Completeness of initial Code Context Document

## Troubleshooting Guide

### Common Issues and Solutions

#### Issue: Agents keep disagreeing on same topic
- **Solution**: Check arbitration log is being properly maintained and consulted
- **Solution**: Make human decision more explicit and detailed

#### Issue: Design doesn't match existing code
- **Solution**: Improve Code Context Document
- **Solution**: Add more targeted investigation in Phase 1

#### Issue: Too many human interventions
- **Solution**: Improve agent prompts to be more collaborative
- **Solution**: Add more detail to initial feature description

#### Issue: Tests and code are incompatible
- **Solution**: Ensure skeleton is detailed enough
- **Solution**: Add interface documentation to skeleton

#### Issue: Claude Code costs too high
- **Solution**: Batch more code tasks together
- **Solution**: Spend more time in design phases
- **Solution**: Cache Code Context Document for reuse

## Future Enhancements

### Potential Improvements
1. **Automated Code Context Updates**: After each feature, automatically update the Code Context Document
2. **Learning from Arbitrations**: Use arbitration history to improve agent behavior
3. **Parallel Feature Development**: Run multiple features through the pipeline simultaneously
4. **Automated Testing**: Add CI/CD integration for automatic test running
5. **Performance Monitoring**: Track which agent combinations work best together

### Advanced Workflows
1. **Bug Fix Workflow**: Simplified version for fixing bugs vs new features
2. **Refactoring Workflow**: Special workflow for pure refactoring tasks
3. **Emergency Hotfix**: Streamlined workflow for critical production issues
4. **Documentation Update**: Ollama-only workflow for documentation

## Conclusion

This workflow balances multiple competing concerns:
- **Quality vs Speed**: Parallel development with reconciliation
- **Innovation vs Consistency**: Code context grounding with fresh perspectives
- **Autonomy vs Control**: Agent collaboration with human arbitration
- **Cost vs Capability**: Strategic use of Ollama vs Claude Code

The key innovation is avoiding order bias through parallel work and random sequencing, while maintaining human control through GitHub's familiar PR interface. The workflow is designed to be practical, cost-effective, and integrate seamlessly with existing development practices.