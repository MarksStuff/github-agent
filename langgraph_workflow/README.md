# LangGraph Multi-Agent Workflow

This directory contains the LangGraph-based implementation of the multi-agent development workflow as specified in `improvements/multiagent-workflow.md`.

## Overview

The workflow orchestrates four specialized AI agents to collaboratively develop features:

1. **Test-first**: Focuses on testable code and comprehensive test coverage
2. **Fast-coder**: Prioritizes rapid implementation and iteration  
3. **Senior Engineer**: Emphasizes simplicity, design patterns, and removing duplication
4. **Architect**: Focuses on overall system architecture and scalability

## Key Features

- **Stateful workflow** with SQLite persistence via LangGraph checkpointing
- **Hybrid model routing**: Ollama for free tasks, Claude Code for complex reasoning
- **GitHub PR-based human arbitration**: All conflicts resolved via PR comments
- **Parallel development**: Tests and implementation written simultaneously
- **Git-based rollback**: Every change committed with SHA tracking
- **Minimal context windows**: Smart summarization keeps prompts small

## Installation

```bash
# Install LangGraph dependencies
pip install -r langgraph_workflow/requirements.txt

# Create a .env file with your configuration
cat > .env << EOF
GITHUB_TOKEN=your_github_token
ANTHROPIC_API_KEY=your_anthropic_key
OLLAMA_BASE_URL=http://localhost:11434
EOF

# Start Ollama (for local models)
ollama serve
ollama pull qwen2.5-coder:7b
ollama pull llama3.1
```

## Workflow Phases

### Phase 0: Code Context Extraction
- Senior engineer analyzes existing codebase (Claude Code)
- Creates comprehensive Code Context Document
- Identifies patterns, conventions, infrastructure

### Phase 1: Parallel Design Exploration + Synthesis
1. **Parallel Analysis** (Ollama): All 4 agents analyze feature in isolation
2. **Architect Synthesis** (Ollama): Documents common themes and conflicts
3. **Code Investigation** (Claude Code): Targeted investigation if needed
4. **Human Review**: Via GitHub PR for conflict resolution

### Phase 2: Collaborative Design Document
- Agents iteratively build design document (Ollama)
- Random order to avoid bias
- Human arbitrates disagreements via PR comments
- Complete when all agents agree

### Phase 3: Implementation with Parallel Development
1. **Skeleton Creation**: Senior engineer creates structure (Claude Code)
2. **Parallel Development**: Tests and implementation written blindly
3. **Reconciliation**: Resolve mismatches between tests/code
4. **Component Tests**: Higher-level testing
5. **Integration Tests**: Full system validation
6. **Refinement**: Final quality improvements

## LangGraph Studio Integration

### Running with LangGraph Studio UI

The workflow is fully integrated with LangGraph Studio for visual monitoring and debugging:

```bash
# Install LangGraph CLI if not already installed
pip install langgraph-cli

# Start LangGraph Studio (from langgraph_workflow directory)
cd langgraph_workflow
langgraph up

# The UI will be available at http://localhost:8123
```

The Studio UI provides:
- **Visual graph representation** of the workflow
- **Real-time state inspection** as the workflow executes
- **Step-by-step debugging** capabilities
- **Message history** and artifact viewing
- **Interactive input** for human review steps

### Running as API Server

For programmatic access, run the FastAPI server:

```bash
# Start the API server
python -m langgraph_workflow.server

# API will be available at http://localhost:8000
# API docs at http://localhost:8000/docs
```

API endpoints:
- `POST /workflows` - Start a new workflow
- `GET /workflows/{thread_id}` - Get workflow status
- `POST /workflows/{thread_id}/step` - Execute a single step
- `GET /steps` - List available workflow steps

## Usage

### Basic Usage

```python
from langgraph_workflow import MultiAgentWorkflow

# Initialize workflow
workflow = MultiAgentWorkflow(
    repo_path="/path/to/repo",
    thread_id="pr-1234"  # Use PR/issue number for persistence
)

# Create initial state
initial_state = {
    "feature_description": "Add user authentication with JWT tokens",
    "thread_id": "pr-1234",
    # ... other state fields initialized
}

# Run workflow
config = {"configurable": {"thread_id": "pr-1234"}}
result = await workflow.app.ainvoke(initial_state, config)
```

### Command Line

```bash
python -m langgraph_workflow.run \
    --repo-path /path/to/repo \
    --feature "Add user authentication" \
    --thread-id pr-1234
```

### Resuming from Checkpoint

```python
# Resume a previous workflow
workflow = MultiAgentWorkflow(
    repo_path="/path/to/repo",
    thread_id="pr-1234"  # Same thread ID to resume
)

# Will automatically load from SQLite checkpoint
result = await workflow.app.ainvoke(None, config)
```

## State Management

The workflow maintains durable state in SQLite:

```python
WorkflowState = {
    # Core info
    "thread_id": str,              # PR/issue identifier
    "feature_description": str,    # What to build
    "current_phase": WorkflowPhase,
    
    # Compact messaging
    "messages_window": [Message],  # Last 10 messages only
    "summary_log": str,            # Rolling summary
    
    # Artifacts (paths, not content)
    "artifacts_index": {           # key -> path mapping
        "code_context": "path/to/context.md",
        "design_document": "path/to/design.md",
        "skeleton": "path/to/skeleton.py"
    },
    
    # Git integration
    "git_branch": str,
    "last_commit_sha": str,
    "pr_number": int,
    
    # Quality tracking
    "test_report": dict,
    "ci_status": dict,
    "quality": "draft|ok|fail"
}
```

## GitHub Integration

### Automatic PR Creation

The workflow automatically creates PRs for:
- Design review (Phase 1)
- Implementation review (Phase 3)

### Human Arbitration Flow

1. Agents disagree → Create "Request Changes" on PR
2. Human comments on PR with decision
3. Next agent copies decision verbatim into document
4. Decision logged in arbitration history (no re-litigation)

### CI/CD Integration

```python
# Workflow waits for CI after push
status = await workflow.wait_for_ci(pr_number)

if status["status"] == "failure":
    # Automatic fix attempts with Ollama
    # Escalate to Claude Code if needed
```

## Model Routing Policy

### Use Ollama (Free) For:
- Initial design exploration
- Design document creation
- Quick fixes and iterations
- Test writing
- Basic refactoring

### Use Claude Code (Paid) For:
- Code context extraction
- Targeted code investigation
- Skeleton creation
- Complex reconciliation
- Final refinement
- Stubborn bug fixes

### Escalation Triggers:
- Diff size > 300 lines → Claude Code
- Files touched > 10 → Claude Code
- 2+ consecutive test failures → Claude Code
- Complex architectural decisions → Claude Code

## Artifacts Directory Structure

```
agents/artifacts/<thread_id>/
├── code_context.md           # Phase 0 output
├── analysis_<agent>.md       # Phase 1 analyses
├── synthesis.md              # Architect synthesis
├── design_document.md        # Phase 2 output
├── skeleton.py              # Phase 3 skeleton
├── tests_initial.py         # Parallel test development
├── implementation_initial.py # Parallel implementation
├── patches/                 # Incremental changes
│   └── <timestamp>.patch
├── reports/                 # Test/lint reports
│   └── pytest_<timestamp>.txt
└── logs/                    # CI/CD logs
    └── ci_<check_id>.txt
```

## Configuration

### Environment Variables

```bash
# Required
GITHUB_TOKEN=ghp_xxxx
ANTHROPIC_API_KEY=sk-ant-xxxx

# Optional
OLLAMA_BASE_URL=http://localhost:11434
MCP_SERVER_URL=http://localhost:8080
AGENT_DB=agent_state.db
```

### Workflow Configuration

```python
# In langgraph_workflow/config.py
WORKFLOW_CONFIG = {
    "escalation_thresholds": {
        "diff_size_lines": 300,
        "files_touched": 10,
        "consecutive_failures": 2
    },
    "context_limits": {
        "messages_window": 10,
        "summary_max_tokens": 1000
    },
    "timeouts": {
        "ci_wait": 1800,  # 30 minutes
        "poll_interval": 30
    }
}
```

## Monitoring and Debugging

### LangGraph Studio

1. Start local server with Studio support
2. Connect Studio to visualize workflow
3. Use time-travel to debug issues
4. Branch from checkpoints for A/B testing

### Logging

```python
import logging

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)

# Workflow logs to:
# - Console: INFO and above
# - File: agents/artifacts/<thread_id>/logs/workflow.log
```

### Metrics

The workflow tracks:
- Time per phase
- Model calls (Ollama vs Claude)
- Arbitrations required
- Test pass/fail rates
- CI success rates

## Troubleshooting

### Common Issues

**Agents keep disagreeing**
- Check arbitration log is being consulted
- Make human decisions more explicit
- Add detail to feature description

**Tests and implementation incompatible**
- Ensure skeleton is detailed enough
- Add interface documentation
- Improve design document clarity

**Claude Code costs too high**
- Batch more tasks in design phase
- Improve Code Context Document
- Use Ollama for more iterations

**CI keeps failing**
- Check lint/format rules are clear
- Ensure test environment matches CI
- Add pre-commit hooks locally

## Examples

### Example: Adding Authentication

```python
# Initialize for authentication feature
workflow = MultiAgentWorkflow(
    repo_path="/Users/dev/myapp",
    thread_id="pr-auth-feature"
)

state = {
    "feature_description": """
    Add JWT-based authentication:
    - User login/logout endpoints
    - Token refresh mechanism
    - Role-based access control
    - Session management
    """,
    "thread_id": "pr-auth-feature"
}

# Run workflow
result = await workflow.app.ainvoke(state, config)

# Results in:
# - PR #1234 with design for review
# - Implementation with full test coverage
# - Automatic CI fixes
# - Refined, production-ready code
```

### Example: Resuming After Human Feedback

```python
# After reviewing PR and adding comments...

# Resume workflow
workflow = MultiAgentWorkflow(
    repo_path="/Users/dev/myapp",
    thread_id="pr-auth-feature"  # Same thread
)

# Workflow automatically:
# 1. Fetches PR comments
# 2. Incorporates feedback
# 3. Continues from last checkpoint
# 4. Updates PR with changes
```

## Contributing

To modify the workflow:

1. Edit phase implementations in `langgraph_workflow.py`
2. Adjust agent behaviors in `agent_personas.py`
3. Modify GitHub integration in `github_integration.py`
4. Update routing policies in configuration
5. Test with example features

## License

Same as parent repository