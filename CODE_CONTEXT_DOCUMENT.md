# Code Context Document - GitHub Agent MCP Server

## 1. SYSTEM IDENTITY

**What This System Actually Does:**
- **Primary purpose**: A production-ready GitHub Pull Request management server implementing the Model Context Protocol (MCP) for AI coding agents
- **Problem domain**: Automated code review, PR feedback management, and repository analysis for AI agents
- **System type**: Multi-process server application with FastAPI/HTTP endpoints serving MCP protocol

*Evidence: Based on README.md:1-15, mcp_master.py:1-12, github_tools.py:1-6*

## 2. ARCHITECTURE REALITY CHECK

**Actual Architecture Pattern:**
This system implements a **Master-Worker Multi-Process Architecture** with the following structure:

- **Master Process** (`mcp_master.py`): Spawns and monitors worker processes for each repository
- **Worker Processes** (`mcp_worker.py`): Handle individual repositories on dedicated ports
- **Clean Process Isolation**: Each repository runs independently to prevent cascading failures

*Evidence: mcp_master.py:4-11 describes the master-worker pattern, mcp_worker.py:4-11 confirms single repository handling*

**Real Design Patterns Found:**

1. **Abstract Factory Pattern**
   - Location: `repository_manager.py:41-68` (AbstractRepositoryManager)
   - Implementation: Abstract base class defining interface for repository management
   - Code example: Abstract methods like `get_repository()`, `add_repository()`, `load_configuration()`

2. **Factory Method Pattern**
   - Location: `codebase_tools.py:49-51` (create_simple_lsp_client)
   - Implementation: Factory function for creating LSP client instances
   - Code example: `create_simple_lsp_client(workspace_root, python_path)`

3. **Strategy Pattern**
   - Location: `symbol_storage.py:88-150` (AbstractSymbolStorage)
   - Implementation: Different storage strategies (SQLite, Production) with common interface
   - Code example: SQLiteSymbolStorage and ProductionSymbolStorage implementing AbstractSymbolStorage

4. **Dependency Injection Pattern**
   - Location: `codebase_tools.py:69-85` (CodebaseTools.__init__)
   - Implementation: Dependencies injected via constructor
   - Code example: `__init__(self, repository_manager, symbol_storage, lsp_client_factory)`

5. **Protocol Pattern (Python's structural subtyping)**
   - Location: `codebase_tools.py:25-43` (LSPClientProtocol)
   - Implementation: Protocol defining LSP client interface for type checking

## 3. TECHNOLOGY STACK - VERIFIED USAGE

**Primary Language:**
- **Language**: Python 3.13
- **Actual usage**:
  - Core server files: `mcp_master.py`, `mcp_worker.py`, `github_tools.py`
  - Repository management: `repository_manager.py`, `repository_indexer.py`
  - Symbol extraction: `python_symbol_extractor.py`, `symbol_storage.py`
- **Purpose**: All server logic, API endpoints, process management, and GitHub integration

**Frameworks ACTUALLY IN USE:**

1. **FastAPI**
   - Initialization: `mcp_worker.py:28-30` imports FastAPI
   - Configuration: Worker creates FastAPI app instances for HTTP endpoints
   - Purpose: Serves MCP protocol over HTTP/REST endpoints

2. **LangGraph/LangChain**
   - Initialization: `langgraph_workflow/enhanced_workflow.py:11` imports StateGraph
   - Configuration: Workflow graphs built in `enhanced_workflow.py:81-100`
   - Purpose: Multi-agent workflow orchestration for complex PR tasks

3. **PyGithub**
   - Initialization: `github_tools.py:20-21` imports Github
   - Usage: GitHub API interactions for PR management
   - Purpose: Essential for PR comments, CI status checks, branch operations

4. **Python LSP (Language Server Protocol)**
   - Initialization: `simple_lsp_client.py:46-54` creates pylsp subprocess
   - Configuration: Direct subprocess approach for reliability
   - Purpose: Code navigation (definitions, references, hover info)

5. **SQLite (via sqlite3)**
   - Initialization: `symbol_storage.py:204-216` in SQLiteSymbolStorage
   - Usage: Symbol caching and comment tracking
   - Purpose: Persistent storage for extracted symbols and PR interactions

**Database/Storage:**
- **Type**: SQLite
- **Access method**: Direct sqlite3 module (symbol_storage.py:9)
- **Schema location**: `symbol_storage.py:232-276` (CREATE TABLE statements)
- **Databases used**:
  - Symbol storage: `SYMBOLS_DB_PATH`
  - Workflow state: `enhanced_workflow_state.db`
  - Agent state: `agent_state.db`

## 4. CODE ORGANIZATION ANALYSIS

**Directory Structure Meaning:**
```
src/
├── langgraph_workflow/ - LangGraph-based multi-agent workflow system
├── tests/             - Comprehensive test suite with mocks
├── scripts/           - Deployment and maintenance scripts
├── config/            - Configuration files and templates
├── agents/            - Agent persona definitions
├── artifacts/         - Generated artifacts storage
├── multi_agent_workflow/ - Legacy workflow implementation
```

**Module Communication Patterns:**
- **Dependency Direction**: Top-down from master → workers → tools
- **No Circular Dependencies**: Clean abstract interfaces prevent circular imports
- **Communication**: Workers use HTTP/FastAPI, internally use direct function calls

## 5. KEY COMPONENTS AND THEIR ROLES

**Component**: MCPMaster
- **Location**: `mcp_master.py:100-700`
- **Responsibility**: Process lifecycle management, health monitoring, graceful shutdown
- **Dependencies**: asyncio, subprocess, RepositoryManager
- **Dependents**: System entry point

**Component**: MCPWorker
- **Location**: `mcp_worker.py:57-800`
- **Responsibility**: Handle single repository, serve MCP endpoints, execute tools
- **Dependencies**: FastAPI, github_tools, codebase_tools
- **Dependents**: MCPMaster spawns workers

**Component**: CodebaseTools
- **Location**: `codebase_tools.py:57-800`
- **Responsibility**: Repository analysis, symbol search, LSP operations
- **Dependencies**: SimpleLSPClient, SymbolStorage, RepositoryManager
- **Dependents**: MCPWorker

**Component**: GitHubTools
- **Location**: `github_tools.py:35-2000`
- **Responsibility**: GitHub API operations, PR management, CI integration
- **Dependencies**: PyGithub, requests
- **Dependents**: MCPWorker

**Component**: SimpleLSPClient
- **Location**: `simple_lsp_client.py:14-500`
- **Responsibility**: Reliable LSP operations via subprocess
- **Dependencies**: asyncio, pylsp
- **Dependents**: CodebaseTools

## 6. INTEGRATION POINTS - VERIFIED

**External Systems:**
- **GitHub API**: PyGithub client in `github_tools.py:20-21`
- **Python LSP Server**: pylsp subprocess in `simple_lsp_client.py:46-54`

**Exposed Interfaces:**
- **MCP Endpoints**: `http://localhost:[port]/mcp/` (mcp_worker.py)
- **Tool Registration**: `/tools/list` endpoint
- **Tool Execution**: `/tools/call` endpoint

## 7. DATA FLOW ANALYSIS

Typical tool execution flow:
1. **Entry point**: `mcp_worker.py:handle_tool_call()` [file:function]
2. **Tool dispatch**: `mcp_worker.py:execute_tool()` [file:function]
3. **Business logic**: `github_tools.py:execute_*` or `codebase_tools.py` methods
4. **Data access**: `symbol_storage.py:SQLiteSymbolStorage` methods
5. **Response**: JSON response via FastAPI

## 8. TESTING REALITY

**Test Coverage:**
- **Test files location**: `tests/` directory
- **Testing framework**: pytest (requirements.txt:19)
- **Types of tests**:
  - Unit tests: `test_repository_indexer.py`, `test_symbol_storage.py`
  - Integration tests: `test_mcp_integration.py`, `test_worker_lsp_integration.py`
  - Mock implementations: `tests/mocks/` directory
- **Key patterns**: Abstract base classes for mocking, no unittest.mock for internal objects

## 9. DEVELOPMENT PRACTICES - OBSERVED

**Code Style**:
- Modern Python type hints throughout (`| None` instead of `Optional`)
- Consistent async/await patterns
- Dataclasses for data models

**Error Handling**:
- Comprehensive try/except blocks with specific exceptions
- Detailed logging at multiple levels
- Graceful degradation in worker processes

**Logging**:
- Custom MicrosecondFormatter for precise timing
- Separate log files per worker
- Structured logging with levels

**Configuration**:
- Environment variables via python-dotenv
- JSON configuration for repositories
- Factory pattern for flexible initialization

## 10. CRITICAL FINDINGS

**Code Smells/Issues Found:**
- **Multiple database files**: Three separate SQLite databases without clear separation of concerns
- **Legacy code**: `multi_agent_workflow/` directory appears to be replaced by `langgraph_workflow/`

**Inconsistencies:**
- Mixed async patterns: Some modules fully async, others use sync with async wrappers
- Testing approach varies: Some tests use abstract base classes, others use pytest fixtures

## VALIDATION CHECKLIST

- [x] Every framework listed is actually imported and used in source code
- [x] Every pattern claimed has a concrete code example
- [x] Every component described exists in the repository
- [x] Architecture description matches actual code structure
- [x] No languages listed that only appear in config/data files
- [x] Integration points have actual code implementing them

## SUMMARY

This is a production-ready MCP server implementing GitHub PR management tools for AI coding agents. It uses a robust master-worker architecture with process isolation, comprehensive error handling, and clean abstractions. The system combines GitHub API integration with local code analysis capabilities through LSP, providing a complete toolkit for automated code review and PR feedback workflows.