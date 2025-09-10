# LangGraph Multi-Agent Workflow

A stateful multi-agent workflow system using LangGraph for software development tasks. This system replaces the custom orchestration in `multi_agent_workflow/` with a modern, checkpointable, and observable workflow.

## Features

- **Stateful Execution**: SQLite-backed checkpointing for pause/resume
- **Multi-Agent Coordination**: Architect, Developer, Senior Engineer, Tester agents
- **Hybrid Model Routing**: Local Ollama + Remote Claude escalation
- **GitHub Integration**: PR creation, comment handling, CI/CD monitoring
- **Time-Travel Debugging**: LangGraph Studio integration
- **Artifact Management**: Structured storage of designs, code, tests
- **Quality Gates**: Automated testing and validation checkpoints

## Quick Start

### 1. Setup

```bash
# Run the setup script to install dependencies
./setup/setup_system.sh

# Or install manually
pip install langgraph langgraph-checkpoint-sqlite langchain-ollama langchain-anthropic

# Configure environment
cp .env.langgraph.example .env
# Edit .env with your configuration
```

### 2. Start Server

```bash
# Start the LangGraph server
cd langgraph_workflow
python server.py

# Or use the CLI directly
python cli.py --help
```

### 3. Run Workflow

```bash
# Start a new workflow
python cli.py start "Add authentication" --task-file task.md

# Check status
python cli.py status workflow-20250109-143022

# Resume paused workflow
python cli.py resume workflow-20250109-143022
```

## Architecture

### State Management

The workflow uses a comprehensive state schema with enums for type safety:

```python
class WorkflowState(TypedDict):
    thread_id: str
    current_phase: WorkflowPhase  # ANALYSIS, DESIGN, FINALIZATION, IMPLEMENTATION
    task_spec: str
    feature_name: str
    repo_name: str
    repo_path: str
    # ... and many more fields
```

### Workflow Phases

1. **Analysis Phase**
   - Codebase analysis by Senior Engineer
   - Parallel feature analysis by all agents
   - Artifact generation and storage

2. **Design Phase**  
   - Conflict identification and resolution
   - Design consolidation
   - PR creation for review

3. **Finalization Phase**
   - GitHub PR feedback processing
   - Design updates based on feedback
   - Response generation

4. **Implementation Phase**
   - Architecture skeleton creation
   - Test-driven development
   - Code implementation and validation

### Model Routing

The system uses hybrid model routing for cost optimization:

- **Local Ollama** (`qwen2.5-coder:7b`): Routine tasks, drafts, simple fixes
- **Claude Opus**: Complex reasoning, escalations, final reviews

Escalation triggers:
- Retry count ≥ 2
- Complex design conflicts (>5)
- Finalization phase
- Explicit escalation request

### Artifact Management

Structured artifact storage under `.workflow/artifacts/`:

```
artifacts/
└── <thread_id>/
    ├── analysis/
    │   ├── codebase_analysis.md
    │   ├── architect_analysis.md
    │   └── ...
    ├── design/
    │   ├── consolidated_design.md
    │   └── finalized_design.md
    ├── code/
    │   ├── skeleton.py
    │   └── implementation.py
    └── tests/
        └── test_suite.py
```

## Configuration

### Environment Variables

```bash
# Repository Configuration
REPO_NAME=owner/repo
REPO_PATH=/path/to/repo

# Model Configuration  
ANTHROPIC_API_KEY=your-key
OLLAMA_BASE_URL=http://remote-machine:11434

# LangGraph Configuration
LANGGRAPH_DB_PATH=.langgraph_checkpoints/agent_state.db
LANGGRAPH_SERVER_PORT=8123

# Model Routing
MODEL_ROUTER_ESCALATION_THRESHOLD=2
MODEL_ROUTER_DIFF_SIZE_LIMIT=300
MODEL_ROUTER_FILES_LIMIT=10
```

### Remote Ollama Setup

For remote Ollama (e.g., Windows machine):

```bash
# On Windows machine
ollama serve --host 0.0.0.0

# In your .env
OLLAMA_BASE_URL=http://windows-machine-ip:11434
```

## API Reference

### Server Endpoints

- `POST /workflow/start` - Start new workflow
- `POST /workflow/resume` - Resume paused workflow  
- `GET /workflow/status/{thread_id}` - Get workflow status
- `GET /workflow/threads` - List all workflows
- `GET /models/status` - Check model connections
- `GET /health` - Health check

### CLI Commands

```bash
# Workflow Management
python cli.py start "feature-name" --task-file task.md
python cli.py resume thread-id
python cli.py status thread-id
python cli.py list

# Validation and Debugging
python cli.py validate thread-id --verbose
python cli.py artifacts list --thread-id thread-id
python cli.py models test

# Artifact Management
python cli.py artifacts export --thread-id thread-id
python cli.py artifacts cleanup --thread-id thread-id --keep-final
python cli.py artifacts stats
```

## Integration with Existing System

### Compatibility Layer

The LangGraph workflow integrates with existing components:

- **Agent Interfaces**: Wraps existing `ArchitectAgent`, `DeveloperAgent`, etc.
- **GitHub Tools**: Uses existing `github_tools.py` MCP integration
- **Repository Manager**: Leverages existing repository setup
- **Task Context**: Converts to/from existing JSON context format

### Migration Path

1. **Phase 1**: Run both systems in parallel
2. **Phase 2**: Gradually migrate workflows to LangGraph  
3. **Phase 3**: Deprecate custom orchestration
4. **Phase 4**: Full LangGraph adoption

### Backward Compatibility

```python
# Convert existing context to LangGraph state
from langgraph_workflow.state import initialize_state
from multi_agent_workflow.task_context import TaskContext

# Load existing context
old_context = TaskContext.load_from_file("context.json")

# Convert to LangGraph state
new_state = initialize_state(thread_id, repo_name, repo_path)
new_state.update({
    "task_spec": old_context.task_spec,
    "feature_name": old_context.feature_spec.name,
    # ... migrate other fields
})
```

## Development

### Adding New Nodes

1. Create node function in appropriate module:

```python
# langgraph_workflow/nodes/custom_nodes.py
async def my_custom_node(state: WorkflowState) -> dict:
    # Node implementation
    return state
```

2. Add to graph in `graph.py`:

```python
graph.add_node("my_custom_node", CustomNodes.my_custom_node)
graph.add_edge("previous_node", "my_custom_node")
```

### Adding New State Fields

1. Update `WorkflowState` in `state.py`
2. Update validation in `validators.py`
3. Handle migration in existing workflows

### Testing

```bash
# Run tests
python -m pytest langgraph_workflow/tests/

# Integration tests
python -m pytest langgraph_workflow/tests/test_integration.py

# Test model connections
python cli.py models test
```

## Monitoring and Observability

### LangGraph Studio

1. Start the server: `python server.py`
2. Open LangGraph Studio
3. Connect to `http://localhost:8123`
4. View workflow graphs, state, and execution

### Logging

Structured logging with multiple levels:

```python
import logging
logger = logging.getLogger(__name__)

# Info: Normal workflow progress
logger.info("Starting phase: analysis")

# Warning: Recoverable issues  
logger.warning("Ollama connection failed, falling back to Claude")

# Error: Serious problems
logger.error("Workflow execution failed", exc_info=True)
```

Log files: `langgraph_workflow.log`

### Metrics

Key metrics to monitor:

- Workflow completion rate
- Average execution time per phase  
- Model usage (Ollama vs Claude)
- Retry and escalation rates
- Artifact storage growth

## Troubleshooting

### Common Issues

**"Workflow not found"**
- Check thread ID spelling
- Verify SQLite database exists
- Check file permissions

**"Model connection failed"**  
- Verify API keys in environment
- Test Ollama connectivity: `curl http://ollama-host:11434/api/tags`
- Check network connectivity

**"Checkpoint corruption"**
- Delete SQLite file to start fresh
- Check disk space
- Verify write permissions

**"Agent execution timeout"**
- Increase timeout in model router
- Check model availability
- Review system resources

### Debug Mode

Enable verbose logging:

```bash
export LANGGRAPH_LOG_LEVEL=debug
python cli.py --verbose status thread-id
```

### Recovery Procedures

**Corrupted Workflow State**:
```bash
# Validate state
python cli.py validate thread-id --verbose

# Export artifacts before cleanup  
python cli.py artifacts export --thread-id thread-id

# Reset workflow (creates new thread)
python cli.py start "feature-name" --task-file task.md
```

## Contributing

1. Follow existing code patterns and type hints
2. Add comprehensive tests for new functionality  
3. Update documentation for API changes
4. Test with both Ollama and Claude models
5. Validate state schema changes

## License

Same as parent project.