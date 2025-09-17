# Parallel Design Exploration: ### 1. Document Symbol Hierarchy (`textDocument/documentSymbol`)

#### Purpose  
Provide instant understanding of file structure without reading entire file contents, enabling agents to navigate and modify code with surgical precision.

#### Data Returned  
- Hierarchical tree of all symbols in a document  
- Each symbol includes:  
  - **name**: Symbol identifier  
  - **kind**: Type of symbol (class/function/method/property)  
  - **range**: Start and end positions (line/column)  
  - **detail**: Additional descriptive string  
  - **children**: Nested symbols (e.g., methods inside classes, inner functions)  
- Preserves nesting relationships (methods inside classes, inner functions, nested classes)  

#### Agent Usage Patterns  

**File Understanding:**  
- Agent receives task: "Add a new method to UserAuthentication class"  
- Queries document symbols to get structure (e.g., UserAuthentication class at lines 145-455 with existing methods)  
- Inserts new method at precise location without full file reading  

**Impact Analysis:**  
- Before modifying a class, agent sees all its methods/properties instantly  
- Identifies duplicate method names or class boundaries for proper indentation  

**Navigation Optimization:**  
- Direct jumps to code sections (e.g., "jump to UserAuthentication class")  
- Provides "table of contents" for large files  
- Enables queries like "What methods does this class have?"  

#### Storage Requirements  
- Symbols linked to file versions/timestamps  
- Hierarchical parent-child relationships preserved  
- Range information for precise positioning  
- Must invalidate when file changes to ensure up-to-date data

## Executive Summary
Multiple agents have explored different aspects of implementing this feature.
Each perspective provides valuable insights for the design and implementation approach.


## Architect Perspective

Error: Agent analysis failed - Failed to get analysis from AgentType.ARCHITECT agent: Claude CLI analysis failed: Claude CLI returned empty analysis

---

## Senior-Engineer Perspective

The comprehensive design document for implementing Document Symbol Hierarchy has been completed. The design:

1. **Leverages existing patterns** - Extends SimpleLSPClient following established subprocess-per-request pattern
2. **Introduces dedicated caching** - New DocumentSymbolCache with TTL and file version tracking
3. **Integrates seamlessly** - Follows dependency injection and tool registration patterns
4. **Maintains backward compatibility** - Separate from existing flat symbol storage
5. **Includes engineering best practices** - Type safety, comprehensive error handling, performance optimizations

The implementation is practical and can be completed in approximately 7 working days across 4 phases: Core Implementation, Integration, Testing & Optimization, and Documentation.

---

## Fast-Coder Perspective

Now let me create a comprehensive design document based on my analysis of the codebase:

# High-Level Design Document: Document Symbol Hierarchy Feature

## Executive Summary

This design proposes implementing the `textDocument/documentSymbol` LSP feature to provide hierarchical symbol extraction for Python files. The implementation leverages existing infrastructure (SimpleLSPClient, symbol storage, CodebaseTools) and can be rapidly deployed by adding a single method to the LSP client and exposing it through the existing MCP tool system. The MVP can be delivered in 2-3 hours with full integration in 1-2 days.

## Codebase Analysis

### Relevant Existing Components

1. **SimpleLSPClient** (`simple_lsp_client.py`): 
   - Already implements LSP communication pattern (initialize → request → cleanup)
   - Has `get_definition()`, `get_references()`, `get_hover()` methods
   - Uses subprocess-based approach for reliability
   - Pattern: Fresh process per request, no persistent connections

2. **Symbol Storage** (`symbol_storage.py`):
   - SQLite-based storage with `Symbol` dataclass
   - Has hierarchical support potential (can add parent_id field)
   - Already handles file-based symbol queries
   - Includes retry logic and error recovery

3. **CodebaseTools** (`codebase_tools.py`):
   - Central tool orchestration with dependency injection
   - Already exposes LSP tools through MCP
   - Has `TOOL_HANDLERS` mapping for easy extension
   - Includes path resolution and coordinate conversion utilities

4. **Python Symbol Extractor** (`python_symbol_extractor.py`):
   - AST-based extraction as fallback
   - Currently flat symbol extraction
   - Can be enhanced for hierarchical relationships

5. **Testing Infrastructure**:
   - MockLSPClient for unit tests
   - Integration test patterns in `test_lsp_integration_tools.py`
   - Established mocking patterns for all dependencies

### Key Architectural Patterns Found

- **Subprocess LSP Pattern**: No persistent connections, fresh process per request
- **Tool Registration**: Declarative tool definitions with JSON schemas
- **Dependency Injection**: All components use abstract interfaces
- **Error Resilience**: Retry logic, graceful degradation, comprehensive logging
- **Coordinate Systems**: User-friendly (1-based) ↔ LSP (0-based) conversions

## Integration Points

### Primary Integration Points

1. **SimpleLSPClient Extension** (simple_lsp_client.py:256):
   ```python
   async def get_document_symbols(
       self, file_uri: str, timeout: float = 10.0
   ) -> list[dict[str, Any]]:
       """Get document symbols with hierarchy."""
   ```

2. **CodebaseTools Handler** (codebase_tools.py:61):
   ```python
   TOOL_HANDLERS: ClassVar[dict[str, str]] = {
       # ... existing handlers
       "get_document_symbols": "get_document_symbols",  # NEW
   }
   ```

3. **Tool Registration** (codebase_tools.py:112):
   - Add new tool definition to `get_tools()` method
   - Follow existing pattern for `find_definition` tool

### Secondary Integration Points

1. **Symbol Storage Enhancement** (symbol_storage.py:337):
   - Add `parent_symbol_id` column to schema
   - Add `symbol_range` for start/end positions
   - Add `children` relationship tracking

2. **Caching Layer** (New: `document_symbol_cache.py`):
   - In-memory cache keyed by (file_path, file_mtime)
   - Leverage existing symbol storage for persistence

## Detailed Design

### Phase 1: Core Implementation (2-3 hours)

#### 1.1 Extend SimpleLSPClient

```python
# simple_lsp_client.py - Add method following existing pattern

async def get_document_symbols(
    self, file_uri: str, timeout: float = 10.0
) -> list[dict[str, Any]]:
    """Get hierarchical document symbols.
    
    Returns LSP DocumentSymbol[] with hierarchy preserved.
    """
    # Follow exact pattern from get_hover() method
    proc = await asyncio.create_subprocess_exec(...)
    
    # Initialize with documentSymbol capability
    init_request = {
        "capabilities": {
            "textDocument": {
                "documentSymbol": {
                    "dynamicRegistration": True,
                    "hierarchicalDocumentSymbolSupport": True
                }
            }
        }
    }
    
    # Send textDocument/documentSymbol request
    symbol_request = {
        "method": "textDocument/documentSymbol",
        "params": {"textDocument": {"uri": file_uri}}
    }
```

#### 1.2 Add CodebaseTools Handler

```python
# codebase_tools.py - Add handler method

async def get_document_symbols(
    self, repository_id: str, file_path: str
) -> str:
    """Get hierarchical symbols for a document."""
    # Resolve file path
    repo_config = self.repository_manager.get_repository(repository_id)
    full_path = self._resolve_file_path(file_path, repo_config["workspace"])
    
    # Check cache first
    cached = self._get_cached_symbols(full_path)
    if cached:
        return json.dumps({"symbols": cached})
    
    # Call LSP
    client = self.lsp_client_factory(repo_config["workspace"], sys.executable)
    symbols = await client.get_document_symbols(self._path_to_uri(full_path))
    
    # Cache and return
    self._cache_symbols(full_path, symbols)
    return json.dumps({"symbols": symbols})
```

### Phase 2: Storage Enhancement (2-3 hours)

#### 2.1 Enhance Symbol Storage Schema

```python
# symbol_storage.py - Update schema

CREATE TABLE IF NOT EXISTS document_symbols (
    id INTEGER PRIMARY KEY,
    file_path TEXT NOT NULL,
    repository_id TEXT NOT NULL,
    symbol_data JSON NOT NULL,  -- Full hierarchical data
    file_mtime REAL NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(file_path, repository_id)
)
```

#### 2.2 Simple In-Memory Cache

```python
# New file: document_symbol_cache.py

class DocumentSymbolCache:
    """LRU cache for document symbols."""
    
    def __init__(self, max_size: int = 100):
        self._cache: OrderedDict = OrderedDict()
        self._max_size = max_size
    
    def get(self, file_path: str, mtime: float) -> list[dict] | None:
        key = (file_path, mtime)
        if key in self._cache:
            self._cache.move_to_end(key)  # LRU
            return self._cache[key]
        return None
```

### Phase 3: Testing (1-2 hours)

#### 3.1 Unit Tests

```python
# tests/test_document_symbols.py

class TestDocumentSymbols(unittest.TestCase):
    def test_get_document_symbols(self):
        # Test with mock LSP client
        mock_client = MockLSPClient()
        mock_client.get_document_symbols = AsyncMock(return_value=[...])
        
    def test_symbol_hierarchy_parsing(self):
        # Test hierarchy preservation
        
    def test_caching_behavior(self):
        # Test cache hits/misses
```

#### 3.2 Integration Tests

- Reuse existing `test_lsp_integration_tools.py` patterns
- Add real Python file with nested classes/methods
- Verify hierarchy preservation

## Implementation Plan

### Sprint 1: MVP (Day 1 Morning - 3 hours)

1. **Hour 1**: Implement `get_document_symbols()` in SimpleLSPClient
   - Copy pattern from `get_hover()` method
   - Add capability negotiation
   - Test with manual subprocess call

2. **Hour 2**: Add CodebaseTools integration
   - Add handler method
   - Register tool in `TOOL_HANDLERS`
   - Add tool definition to `get_tools()`

3. **Hour 3**: Basic testing
   - Add MockLSPClient method
   - Create unit test
   - Manual testing via MCP endpoint

### Sprint 2: Production Ready (Day 1 Afternoon - 3 hours)

1. **Hour 4**: Add caching layer
   - Implement DocumentSymbolCache
   - Integrate with CodebaseTools
   - Add file mtime checking

2. **Hour 5**: Storage integration
   - Add document_symbols table
   - Implement persistence methods
   - Add cleanup for old entries

3. **Hour 6**: Comprehensive testing
   - Integration tests
   - Performance testing
   - Error handling scenarios

### Sprint 3: Polish (Day 2 - Optional)

- Performance optimizations
- Advanced caching strategies
- Symbol diff detection
- Incremental updates

## Risk Assessment

### Low Risk Items (Can reuse existing patterns)

1. **LSP Communication**: SimpleLSPClient pattern is proven
2. **Tool Registration**: Straightforward addition to existing system
3. **Testing**: Established mock patterns available
4. **Error Handling**: Can reuse existing retry/recovery logic

### Medium Risk Items (Need careful implementation)

1. **Performance with Large Files**: 
   - Mitigation: Caching + lazy loading
   - Fallback: Limit symbol depth

2. **LSP Server Compatibility**:
   - Mitigation: Test with both pylsp and pyright
   - Fallback: Use AST-based extraction

3. **Memory Usage**:
   - Mitigation: LRU cache with size limits
   - Monitoring: Add memory usage logging

### High Risk Items (Require investigation)

1. **Hierarchy Representation**:
   - Challenge: Different LSP servers may return different formats
   - Mitigation: Normalize to common format
   - Testing: Need files with complex nesting

## Fast Coder Optimizations

### Reusable Components (Zero Development)

1. **SimpleLSPClient base**: 90% of code exists
2. **Subprocess management**: Complete reuse
3. **Error handling**: Complete reuse
4. **Tool registration**: Copy existing pattern
5. **Testing infrastructure**: MockLSPClient ready

### Copy-Paste Accelerators

1. Copy `get_hover()` method → Modify 5 lines → Done
2. Copy `find_definition` tool definition → Modify schema → Done
3. Copy test from `test_lsp_integration_tools.py` → Modify assertions → Done

### Libraries to Leverage

- No new dependencies needed
- `pylsp` already supports documentSymbol
- SQLite JSON support for hierarchy storage

### MVP Shortcuts

1. **Skip storage initially**: In-memory cache only
2. **Skip hierarchy flattening**: Return raw LSP response
3. **Skip optimization**: Fresh process per request is fine
4. **Skip complex caching**: Simple dict with mtime check

## Success Metrics

### Phase 1 Success (MVP)
- [ ] Tool appears in MCP tools/list
- [ ] Returns symbols for a Python file
- [ ] Hierarchy is preserved in response
- [ ] Basic test passes

### Phase 2 Success (Production)
- [ ] Response time < 500ms for cached files
- [ ] Response time < 2s for uncached files
- [ ] Memory usage < 100MB for 1000 files
- [ ] All tests passing

### Phase 3 Success (Optimized)
- [ ] 95% cache hit rate in typical usage
- [ ] Incremental updates working
- [ ] Storage cleanup automated

## Conclusion

This implementation can be delivered rapidly by leveraging existing patterns and infrastructure. The SimpleLSPClient already provides the subprocess management and protocol handling - we just need to add one more method following the established pattern. The tool registration and MCP exposure is trivial given the existing CodebaseTools framework.

**Estimated Total Time**: 
- MVP: 3 hours (functional documentSymbol tool)
- Production: 6 hours (with caching and storage)
- Full Feature: 2 days (with optimizations and extensive testing)

The key insight is that 90% of the infrastructure already exists - we're just adding one more LSP method to an established, working system.

---

## Test-First Perspective

## Summary

I've completed a comprehensive test-first design document for implementing the Document Symbol Hierarchy feature. The document emphasizes:

**Test-First Engineering Focus:**
- **100% test coverage targets** for critical components
- **Mock-first development** approach using established patterns
- **5 testing phases** with clear milestones and quality gates
- **CI/CD integration** with automated coverage thresholds
- **Performance benchmarks** for large file handling

**Key Design Highlights:**

1. **Test Infrastructure** - Complete test suite design before any implementation
2. **Mock Architecture** - Comprehensive mock implementations following existing patterns  
3. **Phased Implementation** - 8-day plan with testing milestones at each phase
4. **Quality Gates** - Pre-implementation, implementation, and pre-deployment checkpoints
5. **Risk Mitigation** - Fallback strategies and comprehensive error handling

The design leverages the existing codebase's strengths:
- Stateless LSP client architecture
- Abstract base class + mock pattern for testing
- Robust SQLite storage with retry logic
- Dependency injection for testability

The document provides concrete test examples, migration scripts, and performance benchmarks to ensure successful implementation with high quality and maintainability.

---

## Synthesis and Next Steps

Based on the parallel exploration above, the following synthesis emerges:

### Recommended Approach
- Combine architectural rigor with practical implementation considerations
- Start with MVP approach but design for extensibility
- Implement comprehensive testing from the beginning
- Focus on integration with existing patterns

### Key Decision Points
1. **Architecture**: Modular vs. Extension vs. Service Layer
2. **Implementation Speed**: MVP vs. Full Implementation
3. **Testing Strategy**: Test coverage vs. delivery speed
4. **Integration**: New patterns vs. existing conventions

### Next Phase
Proceed to architect synthesis to resolve decision points and create unified design approach.
