# Codebase Analysis

# Comprehensive Codebase Design Investigation

## 1. Directory Structure

**Root Directory**: `/Users/mstriebeck/Code/github-agent`

### Main Directories:
- [`tests/`](file:///Users/mstriebeck/Code/github-agent/tests) - Comprehensive test suite with mocks and fixtures
- [`scripts/`](file:///Users/mstriebeck/Code/github-agent/scripts) - Development automation scripts
- [`config/`](file:///Users/mstriebeck/Code/github-agent/config) - Configuration templates and examples
- [`systemd/`](file:///Users/mstriebeck/Code/github-agent/systemd) - System service configuration

### Entry Points:
- [`mcp_master.py`](file:///Users/mstriebeck/Code/github-agent/mcp_master.py) - Main master process spawning workers
- [`mcp_worker.py`](file:///Users/mstriebeck/Code/github-agent/mcp_worker.py) - Individual repository worker processes
- [`github_agent_mcp.py`](file:///Users/mstriebeck/Code/github-agent/github_agent_mcp.py) - Legacy single-port server
- [`codebase_cli.py`](file:///Users/mstriebeck/Code/github-agent/codebase_cli.py) - CLI interface

## 2. Key Classes and Modules

### Core Architecture Classes:
- **[`RepositoryManager`](file:///Users/mstriebeck/Code/github-agent/repository_manager.py#L158)** - Manages multiple repository configurations with validation
- **[`CodebaseTools`](file:///Users/mstriebeck/Code/github-agent/codebase_tools.py#L57)** - Object-oriented codebase analysis tools
- **[`SimpleLSPClient`](file:///Users/mstriebeck/Code/github-agent/simple_lsp_client.py#L14)** - Direct subprocess LSP client implementation
- **[`SQLiteSymbolStorage`](file:///Users/mstriebeck/Code/github-agent/symbol_storage.py)** - Symbol database management
- **[`ExitCodeManager`](file:///Users/mstriebeck/Code/github-agent/exit_codes.py#L68)** - Standardized exit code handling

### Key Abstractions:
- **[`AbstractRepositoryManager`](file:///Users/mstriebeck/Code/github-agent/repository_manager.py#L41)** - Repository management interface
- **[`AbstractSymbolStorage`](file:///Users/mstriebeck/Code/github-agent/symbol_storage.py#L64)** - Symbol storage interface
- **[`AbstractGitHubAPIContext`](file:///Users/mstriebeck/Code/github-agent/github_tools.py)** - GitHub API abstraction

### Core Data Classes:
- **[`RepositoryConfig`](file:///Users/mstriebeck/Code/github-agent/repository_manager.py#L70)** - Repository configuration with validation
- **[`Symbol`](file:///Users/mstriebeck/Code/github-agent/symbol_storage.py#L39)** - Python symbol representation

## 3. Design Patterns Used

### **Master-Worker Architecture**
- **Location**: [`mcp_master.py`](file:///Users/mstriebeck/Code/github-agent/mcp_master.py#L4) spawns workers
- **Pattern**: Master process manages multiple worker processes per repository
- **Implementation**: Each repository gets dedicated port and isolated process

### **Dependency Injection Pattern**
- **Location**: [`CodebaseTools.__init__`](file:///Users/mstriebeck/Code/github-agent/codebase_tools.py#L69)
- **Usage**: Constructor injection for repository manager, symbol storage, LSP client factory
- **Example**: 
```python
def __init__(self, repository_manager: AbstractRepositoryManager, 
             symbol_storage: AbstractSymbolStorage, 
             lsp_client_factory: LSPClientFactory)
```

### **Abstract Base Classes for Testing**
- **Location**: [`tests/mocks/`](file:///Users/mstriebeck/Code/github-agent/tests/mocks) directory
- **Pattern**: Mock implementations extending abstract interfaces
- **Example**: [`MockRepositoryManager`](file:///Users/mstriebeck/Code/github-agent/tests/mocks/mock_repository_manager.py#L8) extends [`AbstractRepositoryManager`](file:///Users/mstriebeck/Code/github-agent/repository_manager.py#L41)

### **Factory Pattern**
- **Location**: [`create_simple_lsp_client`](file:///Users/mstriebeck/Code/github-agent/codebase_tools.py#L49)
- **Usage**: LSP client creation with type safety

### **Strategy Pattern** 
- **Location**: [`Language` enum](file:///Users/mstriebeck/Code/github-agent/constants.py#L19) with different LSP servers
- **Implementation**: Different LSP server types for different languages

## 4. Technology Stack

- **Python Version**: 3.12+ (configured in [`pyproject.toml`](file:///Users/mstriebeck/Code/github-agent/pyproject.toml#L17))
- **Web Framework**: FastAPI with uvicorn
- **Testing**: pytest with async support
- **Code Quality**: ruff (linting/formatting), mypy (type checking), bandit (security)
- **Git Integration**: GitPython
- **GitHub API**: PyGithub
- **LSP**: python-lsp-server, pyright
- **Database**: SQLite for symbol storage
- **HTTP Clients**: aiohttp, httpx, requests

## 5. Naming Conventions

### **Variables and Functions**: `snake_case`
- Examples: `repository_manager`, `get_definition`, `workspace_root`

### **Classes**: `PascalCase`
- Examples: `RepositoryManager`, `CodebaseTools`, `SimpleLSPClient`

### **Constants**: `SCREAMING_SNAKE_CASE`
- Examples: `MCP_PORT_RANGE_START`, `MINIMUM_PYTHON_VERSION`

### **Files and Modules**: `snake_case.py`
- Examples: `repository_manager.py`, `simple_lsp_client.py`

### **Type Annotations**: Modern Python syntax
- ✅ `dict[str, int]` instead of `Dict[str, int]`
- ✅ `list[str] | None` instead of `Optional[List[str]]`

## 6. Testing Approach

### **Test Structure**:
- Tests located in [`tests/`](file:///Users/mstriebeck/Code/github-agent/tests) directory
- Mock implementations in [`tests/mocks/`](file:///Users/mstriebeck/Code/github-agent/tests/mocks)
- Shared fixtures in [`tests/fixtures.py`](file:///Users/mstriebeck/Code/github-agent/tests/fixtures.py)

### **Testing Framework**: pytest with these features:
- **Coverage**: Configured for XML, LCOV, HTML, and terminal reports
- **Async support**: `pytest-asyncio>=0.23.0`
- **Markers**: `slow`, `integration`, `asyncio`

### **Mock Strategy**: 
- **NO `unittest.mock`** patches for internal objects
- **Abstract base classes** with concrete mock implementations
- **Dependency injection** to pass real vs mock objects
- **Example**: [`MockRepositoryManager`](file:///Users/mstriebeck/Code/github-agent/tests/mocks/mock_repository_manager.py) implements [`AbstractRepositoryManager`](file:///Users/mstriebeck/Code/github-agent/repository_manager.py#L41)

### **Test Naming**: `test_*.py` files with `test_*` functions

## 7. Error Handling Patterns

### **Structured Exit Codes**:
- **Location**: [`exit_codes.py`](file:///Users/mstriebeck/Code/github-agent/exit_codes.py)
- **Pattern**: Enum-based exit codes for different failure scenarios
- **Categories**: Success (0-9), Timeouts (10-19), Force shutdowns (20-29), Critical failures (30-39)

### **Logging Strategy**:
- Microsecond precision logging
- Structured log storage in `~/.local/share/github-agent/logs`
- Component-specific loggers

### **Exception Hierarchy**:
- Custom exceptions for domain-specific errors
- Proper error propagation through abstract interfaces

## 8. Configuration and Settings

### **Configuration Files**:
- [`repositories.json`](file:///Users/mstriebeck/Code/github-agent/config/repositories.example.json) - Multi-repository configuration
- [`.env`](file:///Users/mstriebeck/Code/github-agent/.env) - Environment variables (GITHUB_TOKEN)
- [`pyproject.toml`](file:///Users/mstriebeck/Code/github-agent/pyproject.toml) - Python project configuration

### **Environment Variables**:
- `GITHUB_TOKEN` - Required for GitHub API access
- `GITHUB_AGENT_REPO_CONFIG` - Custom config file location
- `SERVER_HOST` - Host binding (default: localhost)
- `GITHUB_AGENT_DEV_MODE` - Development mode toggle

### **Port Management**:
- Range: 8080-8200 ([`constants.py`](file:///Users/mstriebeck/Code/github-agent/constants.py#L28-30))
- Dedicated ports per repository for process isolation

## 9. Design Summary for Future Development

### **Recommended Patterns**:

1. **Dependency Injection**: Always accept dependencies through constructor parameters
2. **Abstract Base Classes**: Create abstract interfaces for testability
3. **Factory Functions**: Use factory patterns for complex object creation
4. **Modern Type Hints**: Use `dict[str, int]` syntax, `| None` for optionals

### **Quality Standards**:

1. **100% Test Coverage**: Every function must have corresponding tests
2. **No `unittest.mock` for Internal Objects**: Use abstract base classes and dependency injection
3. **Type Safety**: Full mypy compliance with strict settings
4. **Code Quality**: Pass ruff linting and formatting checks

### **Integration Guidelines**:

1. **Repository-Aware**: All tools should accept repository context
2. **Process Isolation**: Each repository runs in dedicated worker process
3. **Clean Shutdown**: Implement proper cleanup and exit code reporting
4. **LSP Integration**: Use SimpleLSPClient pattern for language server communication

### **Architectural Principles**:

1. **Single Responsibility**: Classes have focused, clear purposes
2. **Open/Closed**: Use composition and dependency injection for extensibility
3. **Interface Segregation**: Small, focused abstract base classes
4. **Dependency Inversion**: Depend on abstractions, not concrete implementations
5. **Process Isolation**: Multi-port architecture prevents cascading failures
6. **Graceful Degradation**: Robust error handling and recovery mechanisms