# Code Context Document - GitHub Agent MCP Server

## 1. SYSTEM IDENTITY

**What This System Actually Does:**
- **Primary purpose**: Multi-repository GitHub integration server that provides MCP (Model Context Protocol) tools for AI coding agents to interact with GitHub PRs, CI/CD pipelines, and codebases
- **Problem domain**: Automated code review, CI/CD monitoring, repository indexing, and LSP-based code analysis for AI-assisted development
- **System type**: Distributed MCP API server with master-worker architecture providing REST/JSON-RPC endpoints

*Evidence: Core functionality found in:*
- `github_agent_mcp.py:4-5`: "GitHub Agent MCP Server Entry Point"
- `mcp_master.py:4-11`: Master process that spawns workers for each repository
- `mcp_worker.py:4-11`: Worker process handling MCP protocol for single repository
- `github_tools.py`: GitHub API integration tools (PR management, CI/CD checks)
- `codebase_tools.py`: LSP-based code analysis tools

## 2. ARCHITECTURE REALITY CHECK

**Actual Architecture Pattern: Master-Worker with MCP Protocol**

The system implements a **distributed master-worker architecture** with dedicated port isolation:

- **Master Process** (`mcp_master.py`): Orchestrates worker lifecycle
  - Reads repository configurations from `repositories.json`
  - Spawns dedicated worker processes per repository
  - Monitors worker health and handles restarts
  - Manages graceful shutdown coordination

- **Worker Processes** (`mcp_worker.py`): Handle individual repositories
  - Each worker runs FastAPI server on dedicated port
  - Provides MCP protocol endpoints (`/mcp/`)
  - Integrates GitHub tools and codebase analysis tools
  - Isolated process prevents cross-repository failures

*Evidence: Master-worker implementation in:*
- `mcp_master.py:106-140`: WorkerProcess dataclass defining worker structure
- `mcp_master.py:293-346`: spawn_worker() method creating subprocess
- `mcp_worker.py:57-75`: MCPWorker class initialization

**Real Design Patterns Found:**

1. **Abstract Factory Pattern**
   - Location: `codebase_tools.py:46-52`, `simple_lsp_client.py`
   - Implementation: LSPClientFactory for creating LSP client instances
   ```python
   def create_simple_lsp_client(workspace_root: str, python_path: str) -> SimpleLSPClient:
       """Factory function to create SimpleLSPClient instances."""
       return SimpleLSPClient(workspace_root, python_path)
   ```

2. **Strategy Pattern**
   - Location: `repository_manager.py:41-68` (AbstractRepositoryManager)
   - Implementation: Abstract base class with concrete implementations
   ```python
   class AbstractRepositoryManager(abc.ABC):
       @abc.abstractmethod
       def get_repository(self, name: str) -> Any | None: pass
   ```

3. **Dependency Injection**
   - Location: `codebase_tools.py:69-86`
   - Implementation: CodebaseTools accepts dependencies via constructor
   ```python
   def __init__(self, repository_manager: AbstractRepositoryManager,
                symbol_storage: AbstractSymbolStorage,
                lsp_client_factory: LSPClientFactory)
   ```
   - `repository_manager.py:41-68` - `AbstractRepositoryManager`
   - `github_tools.py:155-177` - `AbstractGitHubAPIContext`
   - `repository_indexer.py:61-75` - `AbstractRepositoryIndexer`

3. **Dependency Injection** - `codebase_tools.py:69-86`
   ```python
   def __init__(self, repository_manager: AbstractRepositoryManager,
                symbol_storage: AbstractSymbolStorage,
                lsp_client_factory: LSPClientFactory)
   ```

4. **State Machine Pattern** - `langgraph_workflow/enhanced_workflow.py:81-129`
   Using LangGraph's StateGraph for workflow orchestration

## 3. TECHNOLOGY STACK - VERIFIED USAGE

**Primary Language(s):**
- **Language**: Python 3.12+
- **Actual usage**:
  - Core server: `mcp_master.py`, `mcp_worker.py`, `github_agent_mcp.py`
  - GitHub integration: `github_tools.py`
  - Code analysis: `codebase_tools.py`, `repository_indexer.py`, `simple_lsp_client.py`
- **Purpose**: Entire backend system, MCP protocol implementation, GitHub API integration

**Frameworks ACTUALLY IN USE:**

1. **FastAPI** (Web Framework)
   - Initialization: `mcp_worker.py:396-404`
   - Usage: MCP endpoint handling
   ```python
   app = FastAPI(title=f"GitHub MCP Server - {self.repo_name}")
   app.add_middleware(CORSMiddleware, ...)
   ```

2. **LangGraph** (AI Workflow Orchestration)
   - Initialization: `langgraph_workflow/enhanced_workflow.py:74`
   - Usage: Multi-agent workflow state management
   ```python
   self.graph = self._build_enhanced_graph()
   ```

3. **PyGithub** (GitHub API)
   - Import: `github_tools.py:20-21`
   - Usage: GitHub PR operations
   ```python
   from github import Github
   from github.Repository import Repository
   ```

4. **Python LSP Server** (Code Analysis)
   - Usage: `simple_lsp_client.py:46-53`
   ```python
   proc = await asyncio.create_subprocess_exec(
       self.python_path, "-m", "pylsp", ...)
   ```

5. **SQLite** (Symbol Storage)
   - Implementation: `symbol_storage.py` (referenced in multiple files)
   - Usage: Caching extracted code symbols

**Database/Storage:**
- **Type**: SQLite
- **Access**: Direct SQL via `symbol_storage.py`
- **Location**: Configured via `SYMBOLS_DB_PATH` in `constants.py:34`

## 4. CODE ORGANIZATION ANALYSIS

**Directory Structure Meaning:**
```
.
├── github_agent_mcp.py      # Main entry point for MCP server
├── mcp_master.py            # Master process orchestrator
├── mcp_worker.py            # Worker process implementation
├── github_tools.py          # GitHub PR/CI integration tools
├── codebase_tools.py        # Code analysis and LSP tools
├── repository_manager.py    # Repository configuration management
├── repository_indexer.py    # Code symbol extraction engine
├── simple_lsp_client.py     # LSP client for code navigation
├── symbol_storage.py        # SQLite storage for symbols
├── constants.py             # System-wide constants
├── langgraph_workflow/      # Multi-agent AI workflow system
│   ├── enhanced_workflow.py # Main workflow orchestration
│   ├── nodes/              # Workflow node implementations
│   ├── agent_personas.py   # AI agent definitions
│   └── run.py              # Workflow execution CLI
├── tests/                   # Comprehensive test suite
│   └── mocks/              # Mock implementations for testing
├── scripts/                 # Deployment and maintenance scripts
└── setup/                   # System setup scripts
```

**Module Communication Patterns:**
- **Hierarchical**: Master → Worker processes via subprocess spawning
- **Protocol-based**: Workers expose MCP endpoints via FastAPI
- **Dependency Injection**: Core components use abstract interfaces
- **No circular dependencies** detected in imports

## 5. KEY COMPONENTS AND THEIR ROLES

**Component**: MCPMaster
- **Location**: `mcp_master.py:189-691`
- **Responsibility**: Process lifecycle management, health monitoring, graceful shutdown
- **Dependencies**: RepositoryManager, CodebaseTools, SimpleShutdownCoordinator
- **Dependents**: Main entry point (`github_agent_mcp.py`)

**Component**: MCPWorker
- **Location**: `mcp_worker.py:57-602`
- **Responsibility**: Handle MCP protocol for single repository, expose GitHub/codebase tools
- **Dependencies**: GitHubAPIContext, CodebaseTools, FastAPI
- **Dependents**: MCPMaster (spawns workers)

**Component**: CodebaseTools
- **Location**: `codebase_tools.py:57-452`
- **Responsibility**: Code analysis, symbol search, LSP operations
- **Dependencies**: SimpleLSPClient, AbstractSymbolStorage, AbstractRepositoryManager
- **Dependents**: MCPWorker, MCPMaster

**Component**: GitHubTools
- **Location**: `github_tools.py:35-1052`
- **Responsibility**: GitHub PR operations, CI/CD status, comment management
- **Dependencies**: PyGithub, GitHubAPIContext
- **Dependents**: MCPWorker

**Component**: EnhancedMultiAgentWorkflow
- **Location**: `langgraph_workflow/enhanced_workflow.py:31-366`
- **Responsibility**: Orchestrate multi-agent AI workflows for feature development
- **Dependencies**: LangGraph, agent implementations
- **Dependents**: Workflow CLI (`langgraph_workflow/run.py`)

## 6. INTEGRATION POINTS - VERIFIED

**External Systems:**
- **GitHub API**: Via PyGithub in `github_tools.py:179-223`
  ```python
  self.github = Github(github_token)
  self.repo = self.github.get_repo(f"{owner}/{repo}")
  ```
- **Python LSP Server**: Via subprocess in `simple_lsp_client.py:46-53`
- **Ollama/Claude CLI**: In `langgraph_workflow/run.py:83-151` for LLM operations

**Exposed Interfaces:**
- **MCP Endpoints**: `mcp_worker.py:439-468`
  - POST `/mcp/` - Main MCP protocol handler
  - GET `/health` - Health check endpoint
- **Repository Management CLI**: Referenced in `README.md:93-101`

## 7. DATA FLOW ANALYSIS

Typical MCP tool invocation flow:
1. **Entry**: FastAPI endpoint `mcp_worker.py:439` receives POST to `/mcp/`
2. **Routing**: `_handle_tool_call()` at `mcp_worker.py:482-539`
3. **GitHub Tool Path**:
   - Dispatch to `github_tools.py` functions
   - API call via PyGithub
   - Response formatting
4. **Codebase Tool Path**:
   - Dispatch to `codebase_tools.py:299-452`
   - LSP client invocation or symbol storage query
   - Response formatting
5. **Response**: JSON-RPC formatted response via FastAPI

## 8. TESTING REALITY

**Test Coverage:**
- **Test Location**: `tests/` directory with 40+ test files
- **Testing Framework**: pytest (configured in `pyproject.toml:51-69`)
- **Test Types Found**:
  - Unit tests: `test_*.py` files testing individual components
  - Integration tests: `test_*_integration.py` files
  - Mock implementations: `tests/mocks/` directory

**Key Test Examples:**
- `tests/test_mcp_worker.py` - Worker process testing
- `tests/test_repository_indexer.py` - Symbol extraction testing
- `tests/test_github_tools.py` - GitHub integration testing

## 9. DEVELOPMENT PRACTICES - OBSERVED

**Code Style**:
- Modern Python with type hints throughout
- Consistent async/await patterns
- Comprehensive logging with microsecond precision

**Error Handling**:
```python
# mcp_worker.py:164-174
try:
    self.github_context = GitHubAPIContext(self.repo_config)
except Exception as e:
    self.logger.error(f"Failed to setup GitHub context: {e}")
    raise
```

**Logging**:
- Custom `MicrosecondFormatter` in `system_utils.py`
- Hierarchical logger names
- Separate log files per worker

**Configuration**:
- Environment variables via `.env` file
- Repository configuration in `repositories.json`
- System constants in `constants.py`

## 10. CRITICAL FINDINGS

**Code Smells/Issues Found:**

1. **Potential Memory Issue**: Large file handling in `repository_indexer.py:95-96`
   - Max file size limit of 10MB to prevent AST parsing issues
   - Could be problematic for large generated files

2. **Process Management Complexity**: `mcp_master.py:361-433`
   - Complex shutdown coordination across multiple processes
   - Potential for zombie processes if shutdown fails

**Inconsistencies:**

1. **Mixed Paradigms**:
   - Core system uses master-worker architecture
   - Optional LangGraph workflow uses different state management
   - Two separate systems not fully integrated

2. **Testing Approach**:
   - Mock objects for testing (`tests/mocks/`)
   - But production code uses dependency injection
   - Could use same abstractions for both

## VALIDATION CHECKLIST

- [x] Every framework listed is actually imported and used in source code
- [x] Every pattern claimed has a concrete code example
- [x] Every component described exists in the repository
- [x] Architecture description matches actual code structure
- [x] No languages listed that only appear in config/data files
- [x] Integration points have actual code implementing them

## IMPORTANT NOTES:

1. **System Boundary**: The core MCP server (master-worker) is separate from the LangGraph workflow system - they can operate independently
2. **Production Ready**: Extensive error handling, logging, and process management indicate production use
3. **Multi-Repository Design**: Each repository gets its own port and worker process for isolation
4. **AI Integration**: Optional but sophisticated multi-agent workflow system using LangGraph
5. **Active Development**: Recent commits show ongoing work on the LangGraph workflow components