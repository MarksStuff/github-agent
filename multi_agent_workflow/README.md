# Multi-Agent Workflow System - Phase 1

This is the Phase 1 implementation of the multi-agent collaboration system for code development.

## Overview

Phase 1 implements the analysis-only workflow where four AI agents with different personas analyze a feature request in parallel:

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

## Usage

### Running Analysis

```bash
# Set environment variables
export GITHUB_REPO="myorg/myrepo"
export REPO_PATH="/path/to/your/repo"
export GITHUB_TOKEN="your-github-token"

# Interactive mode - select from examples or enter custom task
python run_phase1_analysis.py

# Read task specification from a file
python run_phase1_analysis.py path/to/task_spec.md

# Show help
python run_phase1_analysis.py --help
```

The script will:
1. Load task specification from file OR prompt you to select/enter one
2. Analyze your codebase to understand context
3. Run all four agents in parallel to analyze the task
4. Create analysis documents in `.workflow/round_1_analysis/`
5. Save workflow state for later resumption

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
└── round_1_analysis/
    ├── architect_analysis.md
    ├── developer_analysis.md
    ├── senior_engineer_analysis.md
    ├── tester_analysis.md
    └── analysis_summary.md
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

## Next Steps (Phase 2)

Phase 2 will add:
- Processing of human feedback from GitHub comments
- Agent collaboration and conflict resolution
- Consolidated design document generation
- Design approval workflow

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