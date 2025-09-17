# Document Symbol Hierarchy Feature - Senior Engineer Design Document

## Executive Summary

This design document outlines the implementation approach for adding LSP `textDocument/documentSymbol` functionality to the GitHub Agent MCP server. The feature will provide hierarchical symbol information for files, enabling AI agents to quickly understand file structure without reading entire content. The implementation leverages existing LSP infrastructure and extends the current symbol storage system to support hierarchical relationships.

**Key Technical Decisions:**
- Extend `SimpleLSPClient` with a new `get_document_symbols()` method following existing patterns
- Enhance SQLite schema with a `parent_symbol_id` column for hierarchy support
- Implement caching with file version tracking to minimize LSP calls
- Add new MCP tool `get_document_symbols` to expose functionality

## Codebase Analysis

### Current Architecture Findings

The codebase implements a **master-worker architecture** with strong separation of concerns:

1. **LSP Integration Layer** (`simple_lsp_client.py`)
   - Subprocess-based LSP client for reliability
   - No persistent connections - fresh process per request
   - Clean abstraction with factory pattern
   - Existing methods: `get_definition()`, `get_references()`, `get_hover()`

2. **Symbol Storage System** (`symbol_storage.py`, `repository_indexer.py`)
   - SQLite backend with WAL mode for concurrent access
   - Abstract base classes for dependency injection
   - Batch operations support for performance
   - Current schema stores flat symbols without hierarchy

3. **MCP Tool Registration** (`codebase_tools.py`)
   - Object-oriented design with dependency injection
   - Clear tool handler mapping pattern
   - Coordinate conversion utilities (LSP ↔ user-friendly)

4. **Error Handling Patterns**
   - Retry logic with exponential backoff
   - Graceful process cleanup
   - Database corruption recovery
   - Comprehensive logging with microsecond precision

### Performance Considerations

Current system characteristics:
- **File size limits**: 10MB max for AST parsing (prevents memory issues)
- **Process management**: Each LSP call spawns new process (overhead: ~100-200ms)
- **Database operations**: Batched inserts, WAL mode, connection pooling
- **Caching strategy**: Symbols cached indefinitely, no version tracking

## Integration Points

### Primary Integration Files

1. **`simple_lsp_client.py`** - Add document symbols method
   - Location: Lines 412-421 (factory function area)
   - Pattern: Follow existing `get_hover()` implementation (lines 256-360)
   - Process lifecycle management already handled

2. **`symbol_storage.py`** - Extend schema and data model
   - Location: Lines 40-63 (Symbol dataclass)
   - Add: `parent_symbol_id`, `symbol_range`, `detail`
   - Update: SQLite schema (lines 336-349)

3. **`codebase_tools.py`** - New MCP tool registration
   - Location: Lines 60-67 (TOOL_HANDLERS mapping)
   - Add: `"get_document_symbols": "get_document_symbols"`
   - Implement handler method following existing patterns

4. **`repository_indexer.py`** - Enhanced symbol extraction
   - Location: Lines 180-220 (extraction logic)
   - Modify: Store hierarchical relationships during indexing

### Secondary Integration Points

- **`lsp_constants.py`**: Already includes `DOCUMENT_SYMBOLS` constant (line 63)
- **`python_symbol_extractor.py`**: May need updates for hierarchical extraction
- **Database migrations**: New migration for schema changes

## Detailed Design

### 1. LSP Client Extension

```python
# simple_lsp_client.py - Add after line 360

async def get_document_symbols(
    self, file_uri: str, timeout: float = 10.0
) -> list[dict[str, Any]] | None:
    """Get document symbols for a file.

    Args:
        file_uri: URI of the file (file:///path/to/file.py)
        timeout: Request timeout in seconds

    Returns:
        Hierarchical list of document symbols
    """
    self.logger.info(f"Getting document symbols for {file_uri}")

    try:
        # Start fresh pylsp process
        proc = await asyncio.create_subprocess_exec(
            self.python_path,
            "-m",
            "pylsp",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=self.workspace_root,
        )

        # Initialize with document symbol capability
        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "processId": None,
                "rootUri": f"file://{self.workspace_root}",
                "capabilities": {
                    "textDocument": {
                        "documentSymbol": {
                            "dynamicRegistration": True,
                            "symbolKind": {"valueSet": list(range(1, 26))},
                            "hierarchicalDocumentSymbolSupport": True,
                        }
                    }
                },
            },
        }

        await self._send_message(proc, init_request)
        await asyncio.wait_for(self._read_response(proc), timeout=timeout / 2)

        # Send initialized notification
        await self._send_message(
            proc, {"jsonrpc": "2.0", "method": "initialized", "params": {}}
        )

        # Send document symbols request
        symbols_request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "textDocument/documentSymbol",
            "params": {"textDocument": {"uri": file_uri}},
        }

        await self._send_message(proc, symbols_request)
        response = await asyncio.wait_for(
            self._read_response(proc), timeout=timeout / 2
        )

        if "error" in response:
            raise Exception(f"Document symbols request failed: {response['error']}")

        result = response.get("result", [])
        self.logger.info(f"Got {len(result)} top-level symbol(s)")

        return result

    except asyncio.TimeoutError:
        self.logger.error(f"Document symbols request timed out after {timeout}s")
        raise
    except Exception as e:
        self.logger.error(f"Document symbols request failed: {e}")
        raise
    finally:
        # Enhanced cleanup (same as other methods)
        try:
            if "proc" in locals() and proc.returncode is None:
                self.logger.debug(f"Cleaning up pylsp process {proc.pid}")

                if proc.stdin and not proc.stdin.is_closing():
                    proc.stdin.close()

                proc.terminate()
                try:
                    await asyncio.wait_for(proc.wait(), timeout=1.0)
                    self.logger.debug(f"Process {proc.pid} terminated gracefully")
                except asyncio.TimeoutError:
                    self.logger.debug(f"Force killing process {proc.pid}")
                    proc.kill()
                    await proc.wait()

                self.logger.debug(f"Process {proc.pid} cleanup complete")
        except Exception as cleanup_error:
            self.logger.warning(f"Cleanup error: {cleanup_error}")
```

### 2. Enhanced Data Model

```python
# symbol_storage.py - Update Symbol dataclass

@dataclass
class HierarchicalSymbol:
    """Enhanced symbol with hierarchy and range information."""

    # Existing fields
    name: str
    kind: SymbolKind
    file_path: str
    line_number: int
    column_number: int
    repository_id: str
    docstring: str | None = None

    # New fields for hierarchy
    parent_symbol_id: int | None = None
    detail: str | None = None  # e.g., "(self, arg1: str) -> bool"
    range_start_line: int | None = None
    range_start_column: int | None = None
    range_end_line: int | None = None
    range_end_column: int | None = None
    file_version: str | None = None  # Git hash or mtime for cache invalidation
    children: list["HierarchicalSymbol"] | None = None  # For runtime hierarchy
```

### 3. Database Schema Changes

```sql
-- Add new columns to existing symbols table
ALTER TABLE symbols ADD COLUMN parent_symbol_id INTEGER REFERENCES symbols(id);
ALTER TABLE symbols ADD COLUMN detail TEXT;
ALTER TABLE symbols ADD COLUMN range_start_line INTEGER;
ALTER TABLE symbols ADD COLUMN range_start_column INTEGER;
ALTER TABLE symbols ADD COLUMN range_end_line INTEGER;
ALTER TABLE symbols ADD COLUMN range_end_column INTEGER;
ALTER TABLE symbols ADD COLUMN file_version TEXT;

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_symbols_parent ON symbols(parent_symbol_id);
CREATE INDEX IF NOT EXISTS idx_symbols_file_version ON symbols(file_path, file_version);
CREATE INDEX IF NOT EXISTS idx_symbols_hierarchy ON symbols(repository_id, file_path, parent_symbol_id);
```

### 4. MCP Tool Implementation

```python
# codebase_tools.py - Add to CodebaseTools class

async def get_document_symbols(
    self,
    repository_id: str,
    file_path: str,
    force_refresh: bool = False
) -> list[dict[str, Any]]:
    """Get hierarchical document symbols for a file.

    Args:
        repository_id: Repository identifier
        file_path: Path to the file relative to repository root
        force_refresh: Bypass cache and fetch fresh symbols

    Returns:
        Hierarchical list of symbols with ranges and details
    """
    repo = self.repository_manager.get_repository(repository_id)
    if not repo:
        raise ValueError(f"Repository not found: {repository_id}")

    full_path = Path(repo["workspace"]) / file_path
    if not full_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    # Check cache unless force refresh
    if not force_refresh:
        file_version = self._get_file_version(full_path)
        cached = self.symbol_storage.get_document_symbols_cached(
            repository_id, file_path, file_version
        )
        if cached:
            self.logger.debug(f"Using cached symbols for {file_path}")
            return cached

    # Fetch fresh symbols via LSP
    file_uri = self._path_to_uri(str(full_path))
    lsp_client = self.lsp_client_factory(
        repo["workspace"],
        repo.get("python_path", "python3")
    )

    try:
        symbols = await lsp_client.get_document_symbols(file_uri)

        if symbols:
            # Store in cache with hierarchy
            self._store_hierarchical_symbols(
                symbols, repository_id, file_path, file_version
            )

        return self._format_symbols_response(symbols)

    except Exception as e:
        self.logger.error(f"Failed to get document symbols: {e}")
        # Fall back to cached if available
        return self.symbol_storage.get_document_symbols_cached(
            repository_id, file_path, None
        ) or []

def _get_file_version(self, file_path: Path) -> str:
    """Get file version for cache invalidation."""
    # Try git hash first
    try:
        result = subprocess.run(
            ["git", "hash-object", str(file_path)],
            cwd=file_path.parent,
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass

    # Fall back to mtime
    return str(file_path.stat().st_mtime_ns)
```

## Implementation Plan

### Phase 1: Core Infrastructure (2-3 days)

**Tasks:**
1. Extend `SimpleLSPClient` with document symbols support
2. Update database schema with migration script
3. Enhance Symbol dataclass with hierarchical fields
4. Implement file version tracking utilities

**Testing:**
- Unit tests for LSP client method
- Integration tests with real Python files
- Database migration rollback tests

**Complexity:** Medium - Following established patterns

### Phase 2: Storage Layer (2 days)

**Tasks:**
1. Implement hierarchical symbol storage methods
2. Add caching with version-based invalidation
3. Create symbol tree builder utilities
4. Optimize queries with proper indexing

**Testing:**
- Storage CRUD operations with hierarchy
- Cache hit/miss scenarios
- Performance benchmarks with large files

**Complexity:** High - New hierarchical data structures

### Phase 3: MCP Tool Integration (1-2 days)

**Tasks:**
1. Add new tool to `codebase_tools.py`
2. Register tool in MCP handler mapping
3. Implement response formatting
4. Add tool documentation

**Testing:**
- End-to-end MCP tool invocation
- Error handling and fallbacks
- Response format validation

**Complexity:** Low - Well-defined integration points

### Phase 4: Optimization & Polish (1-2 days)

**Tasks:**
1. Implement batch symbol fetching
2. Add progress reporting for large files
3. Optimize database queries
4. Add performance metrics

**Testing:**
- Load testing with large repositories
- Concurrent access scenarios
- Memory profiling

**Complexity:** Medium - Performance tuning

### Phase 5: Documentation & Deployment (1 day)

**Tasks:**
1. Update API documentation
2. Add usage examples
3. Create migration guide
4. Deploy to staging environment

**Testing:**
- Documentation accuracy
- Migration procedures
- Rollback scenarios

## Risk Assessment

### Technical Risks

1. **LSP Server Compatibility**
   - **Risk**: Different LSP servers return different symbol formats
   - **Mitigation**: Normalize responses, test with both pylsp and pyright
   - **Impact**: Medium - May require adapter pattern

2. **Performance Degradation**
   - **Risk**: Large files cause timeout or memory issues
   - **Mitigation**: Implement streaming, increase timeouts, add file size limits
   - **Impact**: High - Core functionality affected

3. **Cache Invalidation Complexity**
   - **Risk**: Stale cache causes incorrect symbol information
   - **Mitigation**: Conservative invalidation, file watching, manual refresh option
   - **Impact**: Medium - User experience degraded

### Operational Risks

1. **Database Migration Failures**
   - **Risk**: Schema changes break existing deployments
   - **Mitigation**: Backward compatible changes, staged rollout, rollback plan
   - **Impact**: High - Service disruption

2. **Increased Process Overhead**
   - **Risk**: More LSP processes impact system resources
   - **Mitigation**: Process pooling, rate limiting, resource monitoring
   - **Impact**: Medium - Performance impact

### Mitigation Strategies

1. **Feature Flags**: Deploy behind feature flag for gradual rollout
2. **Monitoring**: Add metrics for LSP call latency, cache hit rates
3. **Fallback Logic**: Graceful degradation to flat symbol list
4. **Resource Limits**: Cap concurrent LSP processes
5. **Testing**: Comprehensive test suite covering edge cases

## Performance Optimizations

### Caching Strategy

```python
# Three-tier caching approach
class SymbolCache:
    def __init__(self):
        self.memory_cache = {}  # In-memory LRU cache
        self.disk_cache = {}    # SQLite cache
        self.lsp_cache = {}     # Short-lived LSP response cache
```

### Batch Operations

```python
# Fetch symbols for multiple files in single operation
async def get_document_symbols_batch(
    self, file_paths: list[str]
) -> dict[str, list[dict]]:
    """Fetch symbols for multiple files efficiently."""
    # Group by cache status
    cached, uncached = self._partition_by_cache_status(file_paths)

    # Fetch uncached in parallel with rate limiting
    async with asyncio.Semaphore(5):  # Max 5 concurrent LSP calls
        tasks = [self._fetch_symbols(path) for path in uncached]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    return {**cached, **dict(zip(uncached, results))}
```

### Resource Management

```python
# Process pool for LSP operations
class LSPProcessPool:
    def __init__(self, max_processes=10):
        self.semaphore = asyncio.Semaphore(max_processes)
        self.active_processes = set()

    async def execute(self, func, *args, **kwargs):
        async with self.semaphore:
            return await func(*args, **kwargs)
```

## Technical Debt Considerations

### Areas to Refactor

1. **SimpleLSPClient Duplication**
   - Current: Each method duplicates initialization logic
   - Solution: Extract common initialization into base method
   - Priority: Medium - Code maintainability

2. **Symbol Storage Abstraction**
   - Current: Tight coupling to SQLite
   - Solution: Better abstraction for alternative backends
   - Priority: Low - Works well currently

3. **Process Cleanup**
   - Current: Repeated cleanup code in finally blocks
   - Solution: Context manager for process lifecycle
   - Priority: Medium - Error handling improvement

### Future Enhancements

1. **WebSocket Support**: Persistent LSP connections for performance
2. **Incremental Updates**: Track file changes and update symbols incrementally
3. **Cross-File References**: Link symbols across file boundaries
4. **Language Expansion**: Support for TypeScript, JavaScript, Go

## Conclusion

This implementation leverages existing patterns and infrastructure while adding minimal complexity. The design prioritizes:

- **Reliability**: Following proven subprocess-based LSP approach
- **Performance**: Multi-tier caching with intelligent invalidation
- **Maintainability**: Clear separation of concerns, comprehensive testing
- **Scalability**: Resource limits and batch operations

The phased approach allows for incremental delivery with early value realization. Risk mitigation strategies ensure production stability throughout the rollout.

**Estimated Total Effort**: 7-10 engineering days
**Recommended Team Size**: 1-2 engineers
**Production Readiness**: 2 weeks from start