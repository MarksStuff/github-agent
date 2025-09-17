# Design Document: Document Symbol Hierarchy Implementation (Fast Coder Approach)

## Executive Summary

This design proposes a **rapid implementation strategy** for the `textDocument/documentSymbol` LSP feature. By **leveraging existing LSP infrastructure** (SimpleLSPClient), **reusing current storage patterns** (SQLiteSymbolStorage), and **minimizing custom development**, we can deliver a working feature in **2-3 days**. The approach maximizes code reuse, builds on proven patterns, and delivers immediate value with minimal risk.

**Key Insight**: The pylsp server **already supports** `textDocument/documentSymbol`. We just need to expose it through our MCP interface - no custom AST parsing required!

## 1. Codebase Analysis

### 1.1 Existing LSP Infrastructure ✅ READY TO USE
- **SimpleLSPClient** (`simple_lsp_client.py`): Already handles LSP communication
- **Pattern**: Subprocess-based, stateless, reliable
- **Current methods**: `get_definition()`, `get_references()`, `get_hover()`
- **Time to extend**: **< 1 hour** to add `get_document_symbols()`

### 1.2 Storage Layer ✅ READY TO USE
- **SQLiteSymbolStorage** (`symbol_storage.py`): Robust storage with retry logic
- **Current schema**: Supports symbols with hierarchy metadata
- **Pattern**: Abstract base class with concrete SQLite implementation
- **Time to extend**: **< 2 hours** to add parent_id column for hierarchy

### 1.3 Tool Integration ✅ READY TO USE
- **CodebaseTools** (`codebase_tools.py`): Already exposes MCP tools
- **Pattern**: Tool registration and execution framework
- **Current tools**: `search_symbols`, `find_definition`, `find_references`
- **Time to add**: **< 1 hour** to add `get_document_symbols` tool

### 1.4 LSP Constants ✅ ALREADY DEFINED
- **LSPMethod.DOCUMENT_SYMBOLS** already defined in `lsp_constants.py:63`
- **Client capabilities** already include documentSymbol support (`lsp_constants.py:111-116`)

## 2. Integration Strategy

### 2.1 Minimal Changes Required

**File 1: SimpleLSPClient** (30 minutes)
```python
# Add one method to simple_lsp_client.py
async def get_document_symbols(self, file_uri: str, timeout: float = 10.0) -> list[dict[str, Any]]:
    """Get document symbols - reuses existing pattern"""
    # 99% copy of get_hover() method, just change the LSP method name
```

**File 2: CodebaseTools** (30 minutes)
```python
# Add to TOOL_HANDLERS dict
"get_document_symbols": "get_document_symbols"

# Add tool definition in get_tools()
# Add handler method - calls SimpleLSPClient
```

**File 3: SQLiteSymbolStorage** (1 hour - optional for caching)
```python
# Add parent_id column for hierarchy (migration)
# Add methods: store_document_symbols(), get_cached_document_symbols()
```

### 2.2 Data Flow (Reusing Existing Patterns)

1. **Request**: MCP client → `get_document_symbols` tool
2. **Routing**: MCPWorker → CodebaseTools (existing)
3. **LSP Call**: SimpleLSPClient → pylsp subprocess (proven pattern)
4. **Response**: Format and return (existing patterns)
5. **Optional Cache**: Store in SQLite for faster retrieval

## 3. Detailed Design

### 3.1 SimpleLSPClient Extension

```python
async def get_document_symbols(
    self, file_uri: str, timeout: float = 10.0
) -> list[dict[str, Any]]:
    """Get document symbols with hierarchy.

    Returns LSP DocumentSymbol[] with:
    - name, kind, range, selectionRange
    - children[] for nested symbols
    """
    # Implementation: 90% copy from get_hover()
    # Changes: method name, no position params needed
```

### 3.2 MCP Tool Definition

```python
{
    "name": "get_document_symbols",
    "description": "Get hierarchical symbol tree for a document",
    "inputSchema": {
        "type": "object",
        "properties": {
            "repository_id": {"type": "string"},
            "file_path": {"type": "string"}
        },
        "required": ["repository_id", "file_path"]
    }
}
```

### 3.3 Storage Schema Update (Optional - Phase 2)

```sql
-- Add to existing symbols table
ALTER TABLE symbols ADD COLUMN parent_symbol_id INTEGER REFERENCES symbols(id);
ALTER TABLE symbols ADD COLUMN file_version TEXT;  -- timestamp or hash
CREATE INDEX idx_symbols_parent ON symbols(parent_symbol_id);
```

## 4. Implementation Plan

### Phase 1: MVP (Day 1) ✅
**Goal**: Working `textDocument/documentSymbol` via MCP

1. **Hour 1**: Extend SimpleLSPClient
   - Copy `get_hover()` method
   - Change to `textDocument/documentSymbol`
   - Test with manual script

2. **Hour 2**: Add MCP tool
   - Add tool definition to CodebaseTools
   - Add handler method
   - Wire up to SimpleLSPClient

3. **Hour 3**: Test & Debug
   - Test via MCP interface
   - Verify hierarchy preservation
   - Handle edge cases

**Deliverable**: Working documentSymbol feature

### Phase 2: Caching (Day 2) 🔄
**Goal**: Add caching for performance

1. **Hour 1-2**: Schema migration
   - Add parent_symbol_id column
   - Add file_version tracking

2. **Hour 3-4**: Cache logic
   - Store symbols after LSP call
   - Check cache before LSP
   - Invalidate on file change

**Deliverable**: Cached document symbols

### Phase 3: Optimizations (Day 3) ⚡
**Goal**: Performance and reliability

1. **Hour 1-2**: Batch operations
   - Multiple file symbols in one call
   - Parallel LSP requests

2. **Hour 3-4**: Error handling
   - Graceful degradation
   - Fallback strategies

**Deliverable**: Production-ready feature

## 5. Risk Assessment & Mitigation

### Low Risks ✅
- **LSP Support**: pylsp already supports documentSymbol
- **Infrastructure**: All components proven in production
- **Complexity**: Mostly copy-paste from existing patterns

### Mitigation Strategies
- **Fallback**: If pylsp fails, fall back to cached symbols from repository_indexer
- **Incremental**: Deploy Phase 1 immediately, add caching later
- **Testing**: Use existing test patterns from other LSP methods

## 6. Quick Wins & Shortcuts

### Immediate Wins (Day 1)
1. **Copy-paste development**: Reuse 90% of existing code
2. **No custom parsing**: Let pylsp do the heavy lifting
3. **Skip caching initially**: Direct LSP calls work fine

### Smart Shortcuts
1. **Use existing retry logic** from SimpleLSPClient
2. **Leverage existing error handling** patterns
3. **Reuse test infrastructure** from other tools

### Future Enhancements (Post-MVP)
- WebSocket support for real-time updates
- Cross-file symbol relationships
- Incremental symbol updates
- Symbol search with hierarchy context

## 7. Code Reuse Inventory

### What We're Reusing
- ✅ SimpleLSPClient communication pattern (100%)
- ✅ MCP tool registration system (100%)
- ✅ SQLite storage with retry logic (100%)
- ✅ Error handling patterns (100%)
- ✅ Logging infrastructure (100%)
- ✅ Test patterns and mocks (100%)

### What's New (Minimal)
- ❌ One new LSP method (~50 lines)
- ❌ One new MCP tool handler (~30 lines)
- ❌ Optional: cache storage (~100 lines)

**Total new code: < 200 lines for MVP**

## 8. Success Metrics

### Day 1 Success
- [ ] documentSymbol working via MCP
- [ ] Returns hierarchical structure
- [ ] Handles Python files correctly

### Day 2 Success
- [ ] Symbols cached in SQLite
- [ ] Cache invalidation working
- [ ] Performance < 500ms for cached

### Day 3 Success
- [ ] Production deployment ready
- [ ] Error handling comprehensive
- [ ] Documentation complete

## 9. Alternative Approaches (Rejected)

### Why NOT These Approaches:

1. **Custom AST Parser**: Too complex, pylsp already does this
2. **Persistent LSP Connection**: SimpleLSPClient pattern works better
3. **New Storage System**: SQLite is proven and sufficient
4. **GraphQL API**: Overkill for this use case

## 10. Rapid Development Timeline

### Day 1 (4 hours)
- **9:00 AM**: Start coding SimpleLSPClient extension
- **10:00 AM**: Add MCP tool definition
- **11:00 AM**: Integration testing
- **12:00 PM**: Deploy Phase 1 MVP ✅

### Day 2 (4 hours)
- **Morning**: Add caching layer
- **Afternoon**: Test and optimize

### Day 3 (4 hours)
- **Morning**: Production hardening
- **Afternoon**: Documentation and deployment

**Total Time to Production: 12 hours**

## Conclusion

This Fast Coder approach delivers a **working documentSymbol feature in under 4 hours** by maximizing code reuse and leveraging existing infrastructure. The pylsp server already provides the functionality - we just need to expose it through our MCP interface.

**Key Success Factors:**
- 90% code reuse from existing patterns
- No custom symbol extraction needed
- Proven infrastructure components
- Incremental delivery approach
- Minimal risk, maximum speed

The implementation is so straightforward that most of the code can be copy-pasted from existing methods with minor modifications. This is the optimal approach for rapid delivery while maintaining code quality and reliability.