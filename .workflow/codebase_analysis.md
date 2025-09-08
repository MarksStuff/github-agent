# Codebase Analysis

## Overview
This is an MCP (Model Context Protocol) server implementation that provides GitHub and codebase tools for AI agents. The system uses a master-worker architecture where each repository is handled by a dedicated worker process.

## Core Architecture

### Master-Worker Pattern
- **MCP Master** (`mcp_master.py`): Orchestrates multiple worker processes
- **MCP Worker** (`mcp_worker.py`): Handles a single repository on dedicated port
- Each worker provides both GitHub PR tools and codebase analysis tools

### Key Components

#### 1. Symbol Storage System (`symbol_storage.py`)
- **Abstract Base**: `AbstractSymbolStorage` defines interface
- **SQLite Implementation**: `SQLiteSymbolStorage` with retry logic and corruption recovery
- **Production Storage**: `ProductionSymbolStorage` uses standard data directory
- **Symbol Model**: `Symbol` dataclass with name, kind, file_path, line/column numbers
- **Database Schema**: Symbols table with indexes for efficient queries

#### 2. Symbol Extraction (`python_symbol_extractor.py`)
- **AST-based extraction**: Uses Python's AST module
- **Symbol Types**: Classes, functions, methods, properties, variables
- **Hierarchical Tracking**: Maintains scope stack for nested symbols
- **Error Recovery**: Handles multiple encodings, syntax errors

#### 3. Repository Indexing (`repository_indexer.py`)
- **Batch Processing**: Indexes entire repositories
- **File Filtering**: Excludes __pycache__, .git, venv, etc.
- **Size Limits**: Skips files > 10MB by default
- **Result Tracking**: `IndexingResult` tracks success/failure metrics

#### 4. LSP Integration
- **Simple LSP Client** (`simple_lsp_client.py`): Subprocess-based, no persistent connections
- **LSP Methods**: definition, references, hover
- **LSP Constants** (`lsp_constants.py`): Method names, capabilities, error codes
- **Server Support**: PyLSP and Pyright managers

#### 5. Codebase Tools (`codebase_tools.py`)
- **Tool Registry**: Maps tool names to handler methods
- **Available Tools**:
  - `search_symbols`: Search symbols by name/kind
  - `find_definition`: Get symbol definition via LSP
  - `find_references`: Find all references via LSP
  - `find_hover`: Get hover info via LSP
  - `codebase_health_check`: Verify system health

#### 6. GitHub Integration (`github_tools.py`)
- PR comment management
- Build status checking
- Branch/commit operations
- CI error analysis

## Design Patterns

### 1. Abstract Factory Pattern
- Abstract base classes for all major components
- Concrete implementations injected via dependency injection
- Examples: `AbstractSymbolStorage`, `AbstractSymbolExtractor`, `AbstractRepositoryIndexer`

### 2. Repository Pattern
- `SQLiteSymbolStorage` encapsulates all database operations
- Clean separation between data access and business logic

### 3. Strategy Pattern
- Different LSP server implementations (PyLSP, Pyright)
- Selected based on configuration

### 4. Template Method Pattern
- Base retry logic in `_execute_with_retry`
- Specialized operations passed as functions

## Data Flow

1. **Indexing Flow**:
   - Repository path → File discovery → Symbol extraction → Database storage
   
2. **Query Flow**:
   - Tool request → CodebaseTools → Symbol storage/LSP → Response
   
3. **LSP Flow**:
   - Create subprocess → Initialize → Send request → Read response → Cleanup

## Storage Architecture

### SQLite Database
- **Location**: `~/.local/share/github-agent/symbols.db`
- **Tables**:
  - `symbols`: Main symbol storage
  - `comment_replies`: GitHub comment tracking
- **Indexes**: Optimized for name, repository_id, file_path queries
- **Features**: WAL mode, retry logic, corruption recovery

## Error Handling

### Resilience Patterns
- **Retry Logic**: 3 attempts with exponential backoff
- **Corruption Recovery**: Backup corrupt DB, recreate schema
- **Encoding Fallback**: Try UTF-8, UTF-8-sig, Latin-1, CP1252
- **Process Cleanup**: Graceful termination, force kill if needed

## Configuration

### Repository Configuration (`RepositoryConfig`)
- name, workspace path, port, language, python_path
- Loaded from `repositories.json`

### Environment Variables
- `GITHUB_TOKEN`: For GitHub API access
- Loaded from `~/.local/share/github-agent/.env`

## Logging

### Microsecond Precision Logging
- Custom formatter with microsecond timestamps
- Separate log files per worker
- Location: `~/.local/share/github-agent/logs/`

## Testing Infrastructure

### Mock Implementations
- `MockSymbolStorage`: In-memory symbol storage
- `MockSymbolExtractor`: Returns predefined symbols
- `MockGitHubAPIContext`: Simulates GitHub API

### Test Coverage
- Unit tests for all major components
- Integration tests for indexing workflow
- Error condition testing