# Enhanced Multi-Agent Workflow

A comprehensive two-phase development workflow that orchestrates 4 AI agents to design, implement, and maintain high-quality code through skeleton-first architecture and test-driven development.

## Overview

This enhanced workflow implements a sophisticated development process:

1. **Skeleton-First Design**: Architecture skeleton created before any implementation
2. **Test-First Development**: Comprehensive tests written against the skeleton  
3. **Blind Implementation**: Code implemented without seeing tests
4. **Iterative Validation**: Test failures analyzed and fixed systematically
5. **Automated PR Management**: GitHub PR creation, review, and response cycles

## Workflow Phases

### Phase 1: Design Analysis & Architecture Skeleton

1. **Design Analysis**: All 4 agents analyze the feature requirements
2. **Skeleton Creation**: Architect creates complete class/method signatures  
3. **Skeleton Review**: All agents review the architecture skeleton
4. **Finalization**: Senior engineer incorporates feedback and finalizes skeleton

### Phase 2: Test Creation & Review

1. **Test Creation**: Testing agent creates comprehensive test suite against skeleton
2. **Test Review**: All agents review tests for coverage and quality
3. **Test Finalization**: Senior engineer addresses feedback and finalizes tests

### Phase 3: Implementation & Test Validation

1. **Blind Implementation**: Developer implements all methods without seeing tests
2. **Test Execution**: Run all tests and capture detailed failure information
3. **Failure Analysis**: Each agent analyzes failures and suggests fixes
4. **Fix Planning**: Senior engineer creates comprehensive fix plan
5. **Fix Application**: Apply fixes and re-run tests
6. **Iteration**: Repeat until all tests pass (max 5 iterations)
7. **Git Operations**: Commit all changes and push to repository
8. **PR Creation**: Create GitHub Pull Request
9. **Workflow Pause**: Wait for human review

### Phase 4: PR Review & Response Cycles

1. **Resume Signal**: Human resumes workflow after PR review
2. **Comment Fetching**: Retrieve new PR comments via MCP GitHub tools
3. **Comment Analysis**: All agents analyze comments and suggest responses
4. **Response Planning**: Senior engineer creates response plan
5. **Implementation**: Make code changes and post PR replies
6. **Commit Changes**: Commit response changes with summary
7. **Pause & Repeat**: Pause for next review cycle

## Agent Roles

### 🏗️ Architect Agent
- **Focus**: System design and architectural integrity
- **Responsibilities**: Create skeleton, ensure design patterns, maintain architectural consistency
- **Persona**: Software architect focused on scalability and design patterns

### 🚀 Developer Agent  
- **Focus**: Fast implementation and practical solutions
- **Responsibilities**: Implement functionality, suggest pragmatic approaches
- **Persona**: Fast coder prioritizing working software and iteration

### 🧪 Testing Agent
- **Focus**: Comprehensive testing and quality assurance  
- **Responsibilities**: Create test suites, ensure coverage, identify edge cases
- **Persona**: Test-focused developer believing in TDD and thorough testing

### 👨‍💼 Senior Engineer Agent
- **Focus**: Code quality and maintainability
- **Responsibilities**: Resolve conflicts, make final decisions, ensure quality
- **Persona**: Senior engineer prioritizing long-term maintainability

## Usage

### Starting a New Workflow

```bash
# Basic usage
python run_enhanced_workflow.py my-org/my-repo . "Feature Name" "Detailed description"

# Example
python run_enhanced_workflow.py github-org/my-app . "User Authentication" "Add JWT-based authentication with login/logout endpoints"
```

### Resuming After PR Review

```bash
# Resume paused workflow
python run_enhanced_workflow.py my-org/my-repo . --resume
```

### Checking Workflow Status

```bash
# View current status
python run_enhanced_workflow.py my-org/my-repo . --status
```

## Workflow States

The workflow maintains persistent state in `.workflow/workflow_state.json`:

- **design**: Phase 1 - Creating architecture skeleton
- **tests**: Phase 2 - Creating and reviewing test suite  
- **implementation**: Phase 3 - Implementation and test validation
- **pr_review**: Phase 4 - PR review and response cycles
- **completed**: Workflow finished successfully

## Generated Artifacts

### Documents Directory (`.workflow/documents/`)

- `design_analysis_*.md`: Individual agent design analyses
- `architecture_skeleton.md`: Initial skeleton from architect
- `skeleton_review_*.md`: Individual skeleton reviews  
- `final_architecture_skeleton.md`: Final approved skeleton
- `comprehensive_test_suite.md`: Initial test suite
- `test_review_*.md`: Individual test reviews
- `final_test_suite.md`: Final approved test suite
- `initial_implementation.md`: First implementation attempt
- `test_results.json`: Detailed test execution results
- `failure_analysis_*.md`: Individual failure analyses
- `fix_plan.md`: Comprehensive fix strategy
- `updated_implementation.md`: Implementation with fixes applied
- `pr_comment_analysis_*.md`: PR comment analyses
- `pr_response_plan.md`: Response strategy for PR feedback

### Workflow State

- `workflow_state.json`: Current phase, data, and pause state
- `workflow.log`: Detailed execution log

## Key Features

### 🔄 Pause & Resume
- Workflow pauses automatically after PR creation
- Human reviews code and adds PR comments
- Workflow resumes to address all feedback
- Continues until no new comments

### 🤖 Multi-Agent Intelligence
- 4 specialized agents with distinct perspectives
- Comprehensive review at each phase
- Conflict resolution by senior engineer
- Maintains consistency across all decisions

### 🧪 Test-Driven Architecture
- Tests created before implementation
- Implementation done "blind" to tests
- Ensures true test-driven development
- Comprehensive failure analysis and fixes

### 📝 Complete Documentation
- Every decision documented and saved
- Full traceability of workflow steps
- Individual agent perspectives preserved
- Comprehensive fix strategies recorded

### 🔧 GitHub Integration
- Automated PR creation with detailed descriptions
- PR comment fetching via MCP GitHub tools
- Automated responses to reviewer feedback
- Git operations with meaningful commit messages

## Prerequisites

1. **GitHub CLI**: `gh` command available and authenticated
2. **MCP GitHub Tools**: GitHub agent MCP server configured
3. **Python Environment**: Python 3.8+ with required dependencies
4. **Git Repository**: Working Git repository with remote configured
5. **Environment Variables**: `GITHUB_TOKEN` for API access

## Configuration

### Environment Variables

```bash
export GITHUB_TOKEN="your_github_personal_access_token"
```

### MCP Server Setup

Ensure the GitHub agent MCP server is configured for:
- `mcp__github-agent__github_get_pr_comments`
- `mcp__github-agent__github_post_pr_reply`
- Other GitHub API operations

## Error Handling

### Test Failures
- Maximum 5 iteration attempts to fix failures
- Each failure analyzed by all agents
- Comprehensive fix plans created
- Graceful handling of persistent failures

### Git Operations
- Automatic retry on common Git failures
- Meaningful error messages
- State preservation on failures
- Manual intervention points identified

### GitHub API
- Retry logic for API rate limits
- Fallback behaviors for API failures
- Detailed error logging
- Graceful degradation when possible

## Best Practices

### Feature Specifications
- Provide clear, detailed descriptions
- Include acceptance criteria
- Specify integration requirements
- Consider edge cases and error conditions

### Code Review
- Review skeleton before implementation begins
- Examine test coverage and quality
- Provide specific, actionable feedback
- Consider long-term maintainability

### PR Comments
- Be specific about requested changes
- Reference exact lines and files
- Explain reasoning behind suggestions
- Consider architectural implications

## Troubleshooting

### Workflow Stuck
```bash
# Check current status
python run_enhanced_workflow.py repo . --status

# Review workflow logs
tail -f .workflow/workflow.log

# Examine state file
cat .workflow/workflow_state.json
```

### Test Failures
```bash
# Review test results
cat .workflow/documents/test_results.json

# Check failure analyses
ls .workflow/documents/failure_analysis_*.md
```

### GitHub Issues
```bash
# Verify GitHub CLI auth
gh auth status

# Test MCP GitHub tools
# (depends on your MCP setup)
```

## Advanced Usage

### Custom Agent Behavior
Modify agent personas in `coding_personas.py` to adjust behavior:
- Development philosophy
- Code quality standards  
- Testing strategies
- Review criteria

### Workflow Customization
Extend `EnhancedWorkflowOrchestrator` for:
- Additional phases
- Custom validation steps
- Integration with other tools
- Modified review processes

### Integration Points
The workflow can be integrated with:
- CI/CD pipelines
- Code quality tools
- Project management systems
- Custom development workflows

## Contributing

1. Follow existing agent interface patterns
2. Maintain comprehensive documentation
3. Add appropriate error handling
4. Include logging for debugging
5. Test with various feature types

## License

This enhanced workflow is part of the github-agent project and follows the same licensing terms.