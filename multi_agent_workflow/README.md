# Multi-Agent Workflow System

This is a comprehensive multi-agent collaboration system for code development with enhanced implementation capabilities.

## Overview

The system implements a complete development workflow where four AI agents with different personas collaborate through multiple phases:

- **Architect**: Focuses on system design and architecture
- **Developer**: Emphasizes rapid implementation and iteration  
- **Senior Engineer**: Prioritizes code quality and maintainability
- **Tester**: Concentrates on comprehensive testing strategy

## Setup

### Prerequisites

1. Python 3.12+
2. AmpCLI installed and configured
3. GitHub token with repo access (set as `GITHUB_TOKEN` environment variable)
4. Access to the parent directory's MCP server

### Installation

```bash
# From the parent directory (github-agent)
cd multi-agent-workflow

# Install dependencies (uses parent's requirements)
pip install -r ../requirements.txt
```

## Workflow Steps

The complete workflow consists of 4 main steps:

### Step 1: Analysis
Multi-agent analysis of feature requirements
```bash
python step1_analysis.py <task_file>
python step1_analysis.py  # Interactive mode
```

### Step 2: Design Creation  
Create consolidated design document from agent analyses
```bash
python step2_create_design_document.py --pr <PR_NUMBER>
```

### Step 3: Design Finalization
Finalize design incorporating human feedback
```bash  
python step3_finalize_design_document.py --pr <PR_NUMBER>
```

### Step 4: Enhanced Implementation (NEW!)
Comprehensive skeleton-first, test-driven implementation with PR review cycles
```bash
# Start new enhanced workflow
python step4_implementation.py --pr <PR_NUMBER>

# Resume after PR review
python step4_implementation.py --pr <PR_NUMBER> --resume
```

## Enhanced Implementation Process

Step 4 now implements a sophisticated 20-step workflow:

### Phase 1: Architecture Skeleton Creation (Steps 1-2)
1. **Architect creates skeleton** - Complete class/method signatures (NO implementation)
2. **All agents review skeleton** - Comprehensive peer review and feedback
3. **Senior engineer finalizes** - Incorporates all feedback into definitive skeleton

### Phase 2: Test Creation and Review (Steps 3-5)
4. **Testing agent creates tests** - Comprehensive test suite against skeleton using dependency injection
5. **All agents review tests** - Coverage, quality, edge cases analysis
6. **Senior engineer finalizes tests** - Addresses all feedback, creates final test suite

### Phase 3: Implementation and Test Validation (Steps 6-12)
7. **Developer implements code blind** - Complete implementation WITHOUT seeing tests
8. **Run tests and capture failures** - Detailed failure analysis
9. **All agents analyze failures** - Each provides specific fix recommendations
10. **Senior engineer creates fix plan** - Comprehensive strategy addressing all analyses
11. **Apply fixes and repeat** - Up to 5 iterations until all tests pass
12. **Commit and create PR** - Push changes, create PR, **PAUSE for human review**

### Phase 4: PR Review and Response Cycles (Steps 13-20)
13. **Resume workflow** - Human resumes after adding PR comments
14. **Fetch new PR comments** - Using MCP GitHub tools
15. **All agents analyze comments** - Categorize, assess, suggest responses
16. **Senior engineer creates response plan** - Comprehensive plan for all feedback  
17. **Implement changes and post replies** - Make code changes, reply to comments
18. **Commit response changes** - Push updated code with meaningful messages
19. **Pause again** - Wait for next review cycle
20. **Repeat until no new comments** - Complete when no more feedback

## Key Features

### Pause/Resume Functionality
- Workflow pauses without exiting at review points
- Persistent state management in `.workflow/enhanced_workflow_state.json` 
- Resume with `--resume` flag maintains exact phase and context
- Multiple pause/resume cycles for iterative PR reviews

### Test-Driven Architecture
- Tests created BEFORE implementation using only the skeleton
- Implementation done completely blind to test files
- Ensures true test-driven development approach
- Mock objects using inheritance/dependency injection (no frameworks)

### Automated PR Management  
- Integration with MCP GitHub tools for comment handling
- Automated analysis of all PR feedback by all agents
- Intelligent response planning and implementation
- Multiple review cycles until completion

### Complete Documentation
- All agent analyses, reviews, and decisions saved as markdown
- Comprehensive traceability of entire development process
- State management with full audit trail

## Usage

### Environment Setup

```bash
# Set environment variables
export GITHUB_REPO="myorg/myrepo" 
export REPO_PATH="/path/to/your/repo"
export GITHUB_TOKEN="your-github-token"
```

### Example Tasks

The script includes three built-in example tasks:
- **Request Logging**: Add logging to API endpoints
- **Input Validation**: Implement user input validation
- **Redis Caching**: Add caching to user profile service

You can also find a more comprehensive example in:
- `example_task_specs/user-auth-v2.md` - Full user authentication system specification

To use the example file:
```bash
python run_phase1_analysis.py example_task_specs/user-auth-v2.md
```

### Output Structure

```
.workflow/
├── round_1_analysis/          # Step 1 outputs
│   ├── architect_analysis.md
│   ├── developer_analysis.md  
│   ├── senior_engineer_analysis.md
│   ├── tester_analysis.md
│   └── analysis_summary.md
├── round_2_design/           # Step 2 outputs
│   └── consolidated_design.md
├── round_3_design/           # Step 3 outputs  
│   └── finalized_design.md
├── enhanced_implementation/  # Step 4 outputs (NEW!)
│   ├── architecture_skeleton.md
│   ├── skeleton_review_*.md
│   ├── final_skeleton.md
│   ├── test_suite.md
│   ├── test_review_*.md
│   ├── final_tests.md
│   ├── implementation.md
│   ├── test_results.json
│   ├── failure_analysis_*.md
│   ├── fix_plan.md
│   ├── updated_implementation.md
│   ├── comment_analysis_*.md
│   └── response_plan.md
└── enhanced_workflow_state.json  # State for pause/resume
```

### GitHub Integration

After analysis completes:

1. Create a GitHub PR for your feature branch (if not already created)
2. Commit and push the `.workflow` directory:
   ```bash
   git add .workflow
   git commit -m "Add multi-agent analysis for feature"
   git push
   ```
3. Review the analysis documents on GitHub
4. Add comments to specific sections for feedback
5. Agents will read and incorporate feedback in Phase 2

### Resuming Workflow

To check for new feedback on a PR:

```bash
python run_phase1_analysis.py resume <pr_number>
```

## Architecture

### Components

1. **AgentInterface**: Base class wrapping the AmpCLI personas
2. **WorkflowOrchestrator**: Coordinates the analysis workflow
3. **TaskContext**: Maintains shared state between agents
4. **CodebaseAnalyzer**: Analyzes repository structure and patterns

### Integration Points

- Uses `coding_personas.py` for the four agent personalities
- Calls `execute_tool()` from parent's `github_tools.py` for GitHub operations
- Each agent runs in an isolated AmpCLI environment

## Breaking Changes in Step 4

The enhanced Step 4 completely replaces the old 4-part cycle:

**OLD**: Interactive coding → Multi-agent review → Human break → PR integration  
**NEW**: Skeleton creation → Test creation → Implementation cycles → PR review cycles

### Migration Guide
- The new workflow is **not backward compatible** with old Step 4 state
- Start fresh with `python step4_implementation.py --pr <NUM>` (no --resume)
- Generated documents now saved in `enhanced_implementation/` directory
- New `--resume` flag required for continuing paused workflows

## Troubleshooting

### No PR Found

If the system can't find a PR, ensure:
1. You're on a feature branch (not main)
2. The branch has been pushed to GitHub
3. A PR has been created for the branch

### Agent Errors

Check the log file at:
```
~/.local/share/multi-agent-workflow/logs/phase1_analysis.log
```

### AmpCLI Issues

Ensure AmpCLI is properly installed:
```bash
amp --version
```

## Development

To extend or modify:

1. Add new agent types in `agent_interface.py`
2. Modify analysis prompts in agent classes
3. Extend `CodebaseAnalyzer` for deeper analysis
4. Add new workflow phases in `WorkflowOrchestrator`