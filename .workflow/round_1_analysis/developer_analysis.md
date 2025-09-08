# Developer Analysis

**Feature**: # Feature: 1. Document Symbol Hierarchy
**Date**: 2025-09-07T17:48:59.032331
**Agent**: developer

## Analysis

## Implementation Analysis: Document Symbol Hierarchy Feature

### 1. Implementation Strategy Analysis

**Architecture Fit:**
- The feature aligns perfectly with existing patterns - we already have `Symbol` dataclass and AST-based extraction
- Current flow: File → AST → Flat symbols → Storage
- New flow: File → LSP documentSymbol → Hierarchical symbols → Storage

**File Organization:**
- New module: `document_symbol_provider.py` - handles LSP documentSymbol requests and caching
- Extend `Symbol` dataclass in `symbol_storage.py` to include hierarchy fields
- Extend `CodebaseTools` to add `get_document_symbols` method
- Update `lsp_constants.py` (already has DOCUMENT_SYMBOLS constant)

**Class Design:**
- `DocumentSymbolProvider` - orchestrates symbol extraction via LSP or fallback to AST
- Enhanced `Symbol` with optional `parent_symbol_id`, `children`, `range_end_line`, `range_end_column`
- `DocumentSymbolCache` - version-aware caching layer

**Integration Points:**
- Hooks into `CodebaseTools.get_tools()` as new MCP tool
- Reuses existing `SimpleLSPClient` for LSP calls
- Falls back to enhanced `PythonSymbolExtractor` when LSP unavailable

### 2. Existing Code Leverage Analysis

**Reusable Components:**
- `SimpleLSPClient` - already has pattern for LSP requests, just add `get_document_symbols()` method
- `Symbol` dataclass - extend with hierarchy fields rather than creating new class
- `SQLiteSymbolStorage` - add columns for hierarchy data
- `PythonSymbolExtractor` - enhance to track AST node ranges and parent-child relationships

**Utility Functions:**
- `_path_to_uri()` and `_uri_to_path()` from CodebaseTools
- `_execute_with_retry()` pattern from SQLiteSymbolStorage
- Encoding fallback logic from PythonSymbolExtractor

**Patterns to Follow:**
- Abstract base class pattern (create `AbstractDocumentSymbolProvider`)
- Dependency injection for LSP client and storage
- Tool registration pattern in CodebaseTools

### 3. Implementation Complexity Assessment

**Core vs. Optional:**
- **Core MVP**: LSP documentSymbol call → return hierarchical structure
- **Optional enhancements**: Caching, AST fallback, incremental updates

**Complexity Ranking:**
1. **Straightforward**: Adding LSP method to SimpleLSPClient (follow existing pattern)
2. **Moderate**: Schema migration for hierarchy fields in SQLite
3. **Moderate**: Converting LSP response to Symbol hierarchy
4. **Complex**: AST-based hierarchy extraction with accurate ranges

**Risk Areas:**
- LSP server compatibility (pylsp vs pyright response formats)
- Performance with large files (1000+ symbols)
- Cache invalidation on file changes

### 4. Technical Decision Analysis

**Data Flow:**
```
Request → CodebaseTools.get_document_symbols()
    → DocumentSymbolProvider.get_symbols()
        → Check cache (file hash/timestamp)
        → If miss: SimpleLSPClient.get_document_symbols()
        → If LSP fails: PythonSymbolExtractor (enhanced)
        → Convert to Symbol hierarchy
        → Store in cache
    → Return hierarchical Symbol list
```

**Error Handling:**
- LSP timeout → fall back to AST extraction
- AST parse error → return empty list with error message
- Invalid file path → clear error response

**Performance:**
- Cache symbols with file hash/timestamp
- Lazy-load children for deep hierarchies
- Batch database inserts for initial indexing

**Configuration:**
- `use_document_symbols`: Enable/disable feature
- `document_symbol_cache_ttl`: Cache expiration (default: 300s)
- `max_symbol_depth`: Limit nesting depth (default: 10)

### 5. Development Approach Recommendation

**Implementation Order:**
1. **Extend LSP constants and SimpleLSPClient** (low risk, quick win)
   - Add `get_document_symbols()` method following existing pattern
   - Test with simple Python file

2. **Create minimal DocumentSymbolProvider** 
   - Just LSP call, no caching or fallback
   - Convert LSP response to flat Symbol list initially
   - Wire into CodebaseTools as new tool

3. **Add hierarchy support to Symbol**
   - Extend dataclass with parent/children fields
   - Update Symbol.to_dict() for hierarchy
   - No database changes yet

4. **Implement hierarchy conversion**
   - Parse LSP response into parent-child relationships
   - Preserve ranges and detail strings
   - Test with nested classes/methods

5. **Add caching layer**
   - File timestamp/hash checking
   - In-memory cache initially
   - Add SQLite persistence later

**Testing Strategy:**
- Unit test LSP response parsing with mock data
- Integration test with real pylsp server
- Test fallback when LSP unavailable
- Verify hierarchy preservation with complex files

**MVP Definition:**
- Can call textDocument/documentSymbol via LSP
- Returns hierarchical symbol structure
- Integrated as MCP tool
- Works with at least pylsp server
- No caching required for MVP

The approach leverages existing infrastructure heavily - we're essentially adding one more LSP method and enhancing our Symbol model to support hierarchy. The riskiest part is ensuring compatibility across different LSP servers, so starting with pylsp-only support makes sense.

---
*This analysis was generated by the developer agent as part of the multi-agent workflow.*
