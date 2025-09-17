# Document Symbol Hierarchy - Rapid Implementation Design

## Executive Summary

This design document outlines a **fast, pragmatic implementation** of the Document Symbol Hierarchy (`textDocument/documentSymbol`) feature for the GitHub Agent MCP Server. By leveraging existing AST-based symbol extraction and LSP infrastructure, we can deliver this feature **in under 2 days** with minimal code changes. The implementation reuses 80% of existing code and focuses on essential functionality first.

**Key Approach:** Extend existing `PythonSymbolExtractor` to capture hierarchy, add a new LSP method to `SimpleLSPClient`, and create a simple caching layer in the existing SQLite database.

## 1. Codebase Analysis

### Existing Components We Can Leverage

#### 1.1 Symbol Extraction Infrastructure
- **`python_symbol_extractor.py`**: Already parses Python AST and extracts symbols
- **`repository_indexer.py`**: Batch processes entire repositories
- **Current capability**: Extracts flat list of symbols with line/column positions
- **Quick win**: Add parent tracking with ~50 lines of code

#### 1.2 LSP Infrastructure
- **`simple_lsp_client.py`**: Clean subprocess-based LSP client
- **Already supports**: `get_definition()`, `get_references()`, `get_hover()`
- **Pattern established**: Add `get_document_symbols()` following same pattern
- **Estimated effort**: 30 lines of code

#### 1.3 Storage Layer
- **`symbol_storage.py`**: SQLite database with Symbol model
- **Current schema**: Stores symbols with file path, line, column
- **Quick enhancement**: Add `parent_id` column for hierarchy
- **Migration**: Simple ALTER TABLE statement

#### 1.4 Tool Integration
- **`codebase_tools.py`**: MCP tool definitions and handlers
- **Pattern**: Add new tool following existing pattern
- **Registration**: Single entry in `TOOL_HANDLERS` dict

### Reusable Patterns Identified

1. **LSP Method Pattern** (simple_lsp_client.py:28-148):
   - Initialize LSP server subprocess
   - Send request with proper JSON-RPC format
   - Handle response with timeout
   - Clean shutdown with process termination

2. **Tool Registration Pattern** (codebase_tools.py:61-67):
   - Define tool in `get_tools()` method
   - Add handler method
   - Map in `TOOL_HANDLERS` dict

3. **AST Visitor Pattern** (python_symbol_extractor.py:136-200):
   - Track scope stack for nesting
   - Visit nodes recursively
   - Extract symbol metadata

## 2. Integration Points

### Minimal File Modifications Required

1. **`python_symbol_extractor.py`** (~50 lines):
   - Add parent tracking to AST visitor
   - Maintain hierarchy stack during traversal
   - Return hierarchical structure

2. **`simple_lsp_client.py`** (~40 lines):
   - Add `get_document_symbols()` method
   - Reuse existing request/response pattern

3. **`symbol_storage.py`** (~20 lines):
   - Add `parent_id` field to Symbol dataclass
   - Update schema with parent relationship
   - Add query method for hierarchical retrieval

4. **`codebase_tools.py`** (~60 lines):
   - Add `document_symbols` tool definition
   - Implement handler that calls LSP or falls back to AST

5. **`mcp_worker.py`** (5 lines):
   - Register new tool in available tools list

## 3. Detailed Design - MVP Implementation

### Phase 1: Core Functionality (4 hours)

#### 3.1 Enhanced Symbol Model
```python
# symbol_storage.py - Add to existing Symbol dataclass
@dataclass
class Symbol:
    # ... existing fields ...
    parent_id: int | None = None  # NEW: Reference to parent symbol
    children: list['Symbol'] | None = None  # NEW: Transient field for hierarchy
    end_line: int | None = None  # NEW: For range calculation
    detail: str | None = None  # NEW: Additional symbol details
```

#### 3.2 Quick LSP Integration
```python
# simple_lsp_client.py - Add single method
async def get_document_symbols(
    self, file_uri: str, timeout: float = 10.0
) -> list[dict[str, Any]]:
    """Get document symbols with hierarchy."""
    # Reuse existing pattern from get_definition
    proc = await self._start_lsp_process()
    await self._initialize(proc)

    request = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "textDocument/documentSymbol",
        "params": {"textDocument": {"uri": file_uri}}
    }

    await self._send_message(proc, request)
    response = await self._read_response(proc)
    return response.get("result", [])
```

#### 3.3 Fallback AST Extraction
```python
# python_symbol_extractor.py - Enhance existing visitor
class PythonSymbolExtractor(AbstractSymbolExtractor):
    def __init__(self):
        # ... existing ...
        self.parent_stack: list[int] = []  # NEW: Track parent IDs

    def visit_ClassDef(self, node):
        # Create symbol with parent reference
        parent_id = self.parent_stack[-1] if self.parent_stack else None
        symbol = Symbol(
            name=node.name,
            parent_id=parent_id,  # NEW
            end_line=node.end_lineno,  # NEW
            # ... existing fields ...
        )
        self.symbols.append(symbol)

        # Track as parent for nested symbols
        self.parent_stack.append(len(self.symbols) - 1)
        self.generic_visit(node)
        self.parent_stack.pop()
```

### Phase 2: Tool Integration (2 hours)

#### 3.4 MCP Tool Definition
```python
# codebase_tools.py - Add to get_tools()
{
    "name": "document_symbols",
    "description": f"Get hierarchical symbol tree for a file in {repo_name}",
    "inputSchema": {
        "type": "object",
        "properties": {
            "repository_id": {"type": "string"},
            "file_path": {"type": "string"},
            "use_cache": {
                "type": "boolean",
                "default": True,
                "description": "Use cached symbols if available"
            }
        },
        "required": ["repository_id", "file_path"]
    }
}
```

#### 3.5 Handler Implementation
```python
# codebase_tools.py - Add handler method
async def document_symbols(
    self, repository_id: str, file_path: str, use_cache: bool = True
) -> str:
    """Get document symbols with hierarchy."""

    # Try LSP first (most accurate)
    try:
        client = self.lsp_client_factory(repo.workspace, repo.python_path)
        symbols = await client.get_document_symbols(file_uri)
        if symbols:
            return json.dumps({"source": "lsp", "symbols": symbols})
    except Exception as e:
        logger.debug(f"LSP failed, falling back to AST: {e}")

    # Fallback to AST extraction
    if use_cache:
        symbols = self.symbol_storage.get_symbols_by_file(file_path, repository_id)
        if symbols:
            hierarchy = self._build_hierarchy(symbols)
            return json.dumps({"source": "cache", "symbols": hierarchy})

    # Extract fresh from AST
    extractor = PythonSymbolExtractor()
    symbols = extractor.extract_from_file(file_path, repository_id)
    hierarchy = self._build_hierarchy(symbols)

    # Cache for next time
    self.symbol_storage.insert_symbols(symbols)

    return json.dumps({"source": "ast", "symbols": hierarchy})

def _build_hierarchy(self, flat_symbols: list[Symbol]) -> list[dict]:
    """Convert flat symbol list to hierarchy."""
    # Simple parent-child relationship building
    # 20 lines of straightforward code
```

### Phase 3: Optimization & Caching (2 hours)

#### 3.6 Simple File-Based Cache
```python
# Add to symbol_storage.py
def get_file_modification_time(self, file_path: str, repository_id: str) -> float | None:
    """Check when file symbols were last indexed."""
    # Simple query to symbols table

def should_reindex(self, file_path: str, repository_id: str) -> bool:
    """Check if file has changed since last index."""
    # Compare file mtime with database timestamp
```

## 4. Implementation Plan

### Day 1 - Core Development (6 hours)

**Morning (3 hours):**
1. **Hour 1:** Extend Symbol model with hierarchy fields
2. **Hour 2:** Add `get_document_symbols()` to LSP client
3. **Hour 3:** Enhance AST extractor with parent tracking

**Afternoon (3 hours):**
4. **Hour 4:** Create MCP tool definition and handler
5. **Hour 5:** Build hierarchy construction helper
6. **Hour 6:** Basic testing with real Python files

### Day 2 - Integration & Testing (4 hours)

**Morning (2 hours):**
1. **Hour 1:** Add caching logic with timestamp checks
2. **Hour 2:** Integration testing with MCP worker

**Afternoon (2 hours):**
3. **Hour 3:** Test with multiple repositories
4. **Hour 4:** Documentation and example usage

### Incremental Delivery Milestones

1. **MVP (4 hours):** Basic hierarchy via AST - usable immediately
2. **Enhanced (6 hours):** LSP integration for accuracy
3. **Optimized (8 hours):** Caching and performance tuning
4. **Complete (10 hours):** Full testing and documentation

## 5. Risk Assessment

### Low-Risk Approach

**Minimal Risks:**
1. **Schema Change**: Simple ALTER TABLE, backward compatible
2. **LSP Compatibility**: Fallback to AST ensures 100% coverage
3. **Performance**: Caching prevents repeated parsing
4. **Integration**: Follows existing patterns exactly

**Mitigation Strategies:**
1. **Feature Flag**: Add `ENABLE_DOCUMENT_SYMBOLS` constant
2. **Graceful Degradation**: Always fallback to flat list
3. **Incremental Rollout**: Test with single repository first
4. **Monitoring**: Log usage and performance metrics

### What We're NOT Doing (Saves Time)

1. **Not building custom parser** - Use existing AST
2. **Not creating new storage** - Extend existing SQLite
3. **Not changing architecture** - Fits current patterns
4. **Not perfect on day 1** - MVP first, enhance later
5. **Not supporting all languages** - Python only initially

## 6. Quick Wins & Shortcuts

### Immediate Value Delivery

1. **Reuse LSP subprocess pattern** - Copy-paste-modify approach
2. **Extend existing Symbol class** - No new models needed
3. **Piggyback on indexer** - Symbols extracted during normal indexing
4. **Simple parent_id relationship** - No complex tree structures
5. **JSON response format** - Direct serialization

### Libraries We Can Leverage

- **ast module**: Already used, handles all Python parsing
- **pylsp**: Already integrated, supports documentSymbol
- **sqlite3**: Already used, simple schema migration
- **dataclasses**: Already used for Symbol model

### Code We Can Copy

1. **LSP method pattern** from `get_definition()` - 90% reusable
2. **Tool registration** from `search_symbols` - 100% same pattern
3. **AST visitor** from symbol extractor - Add 10 lines
4. **Caching logic** from symbol storage - Reuse retry mechanism

## 7. Success Metrics

### Definition of Done (MVP)

- [ ] API returns hierarchical symbols for any Python file
- [ ] Falls back gracefully when LSP unavailable
- [ ] Caches results to avoid re-parsing
- [ ] Integrates with existing MCP tools
- [ ] Handles files up to 10MB without issues

### Performance Targets

- First call: < 500ms for average file (using LSP)
- Cached call: < 50ms (database query only)
- Large file (10MB): < 2 seconds
- Memory usage: < 100MB additional

## Appendix: Code Templates

### Template 1: LSP Method Addition
```python
# Copy this pattern from existing methods
async def get_document_symbols(self, file_uri: str, timeout: float = 10.0):
    # 95% identical to get_definition
    # Change: method name and params only
```

### Template 2: Tool Handler
```python
async def document_symbols(self, **kwargs):
    # Copy pattern from search_symbols
    # Main logic: Try LSP → Try Cache → Extract Fresh
```

### Template 3: Hierarchy Builder
```python
def _build_hierarchy(symbols: list[Symbol]) -> list[dict]:
    id_map = {i: s for i, s in enumerate(symbols)}
    roots = []

    for idx, symbol in enumerate(symbols):
        if symbol.parent_id is None:
            roots.append(symbol)
        else:
            parent = id_map[symbol.parent_id]
            if parent.children is None:
                parent.children = []
            parent.children.append(symbol)

    return [_symbol_to_dict(s) for s in roots]
```

## Conclusion

This rapid implementation leverages **80% existing code** and can be **delivered in 2 days**. By focusing on the MVP and using established patterns, we minimize risk and maximize speed to market. The implementation is designed to be enhanced incrementally without breaking changes.

**Total New Code: ~200 lines**
**Total Time: 10 hours**
**Risk Level: Low**
**Reuse Factor: 80%**