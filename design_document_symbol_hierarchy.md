# Document Symbol Hierarchy Feature - Implementation Design Document

## Executive Summary

This design document outlines the implementation of the Document Symbol Hierarchy feature (`textDocument/documentSymbol`) for the GitHub Agent MCP Server. The feature will provide hierarchical, tree-structured symbol information for Python files, enabling AI coding agents to understand file structure without reading entire files. This capability significantly improves agent efficiency by allowing precise navigation and targeted code modifications.

**Key Benefits:**
- **Reduced Token Consumption**: Agents get file structure without full file reads (10x-100x reduction)
- **Surgical Code Modification**: Precise location awareness for inserting methods/properties
- **Improved Navigation**: Jump directly to relevant code sections
- **Better Context Understanding**: Hierarchical relationships between symbols

## Codebase Analysis

### Current Architecture Strengths

The existing codebase provides an excellent foundation for this feature:

1. **LSP Integration (simple_lsp_client.py)**
   - Stateless, subprocess-based LSP client with proven reliability
   - Clean JSON-RPC protocol implementation
   - Existing patterns for definition, references, and hover
   - Factory function pattern for dependency injection

2. **Symbol Storage (symbol_storage.py)**
   - Robust SQLite storage with WAL mode for concurrency
   - Abstract base class pattern for testability
   - Comprehensive retry logic and error recovery
   - Existing symbol search and indexing infrastructure

3. **Code Analysis Tools (codebase_tools.py)**
   - Well-structured MCP tool registration system
   - Dependency injection for all components
   - Consistent error handling and logging patterns
   - Clear separation of concerns

4. **Testing Infrastructure**
   - No use of `unittest.mock` - concrete mock implementations instead
   - Abstract base classes with mock implementations
   - Comprehensive test coverage patterns
   - Integration test examples available

### Identified Gaps

1. **LSP Client**: Missing `textDocument/documentSymbol` method implementation
2. **Storage Schema**: No hierarchy support (parent-child relationships)
3. **Symbol Model**: Flat structure without range information
4. **Tool Exposure**: No MCP tool for document symbols

## Integration Points

### Files to Modify

| File | Modifications | Rationale |
|------|--------------|-----------|
| `simple_lsp_client.py` | Add `get_document_symbols()` method | Core LSP protocol implementation following existing patterns |
| `symbol_storage.py` | Extend Symbol dataclass with hierarchy fields<br>Add hierarchy-aware storage methods | Enable parent-child relationships and range data |
| `codebase_tools.py` | Add `get_document_symbols` tool definition<br>Implement `find_document_symbols()` method | Expose feature through MCP protocol |
| `repository_indexer.py` | Update to extract and store hierarchy | Populate hierarchy data during indexing |
| `python_symbol_extractor.py` | Track parent symbols during AST traversal | Build hierarchy during extraction |

### New Files to Create

| File | Purpose | Content |
|------|---------|---------|
| `document_symbol_types.py` | Domain models | DocumentSymbol, SymbolRange, HierarchicalSymbol classes |
| `tests/test_document_symbols.py` | Comprehensive test suite | Unit and integration tests |
| `tests/mocks/mock_lsp_document_symbols.py` | Test infrastructure | Mock LSP responses for testing |

### Database Schema Evolution

```sql
-- Migration approach: Add columns without breaking existing functionality
ALTER TABLE symbols ADD COLUMN parent_symbol_id INTEGER REFERENCES symbols(id);
ALTER TABLE symbols ADD COLUMN detail TEXT;
ALTER TABLE symbols ADD COLUMN range_start_line INTEGER;
ALTER TABLE symbols ADD COLUMN range_start_character INTEGER;
ALTER TABLE symbols ADD COLUMN range_end_line INTEGER;
ALTER TABLE symbols ADD COLUMN range_end_character INTEGER;
ALTER TABLE symbols ADD COLUMN selection_start_line INTEGER;
ALTER TABLE symbols ADD COLUMN selection_start_character INTEGER;
ALTER TABLE symbols ADD COLUMN selection_end_line INTEGER;
ALTER TABLE symbols ADD COLUMN selection_end_character INTEGER;

-- Performance indexes for hierarchy queries
CREATE INDEX idx_symbols_parent ON symbols(parent_symbol_id);
CREATE INDEX idx_symbols_file_hierarchy ON symbols(file_path, parent_symbol_id);
```

## Detailed Design

### Component Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    MCP Worker Process                    │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌──────────────┐    ┌─────────────────────────────┐   │
│  │ CodebaseTools│───▶│ find_document_symbols()      │   │
│  └──────────────┘    └─────────────────────────────┘   │
│         │                        │                       │
│         ▼                        ▼                       │
│  ┌──────────────────────────────────────────────────┐   │
│  │            SimpleLSPClient                       │   │
│  │  ┌────────────────────────────────────────────┐ │   │
│  │  │ get_document_symbols(file_uri) -> hierarchy│ │   │
│  │  └────────────────────────────────────────────┘ │   │
│  └──────────────────────────────────────────────────┘   │
│         │                        │                       │
│         ▼                        ▼                       │
│  ┌──────────────┐    ┌─────────────────────────────┐   │
│  │ pylsp process│    │ SQLiteSymbolStorage         │   │
│  └──────────────┘    │ - store_document_symbols()  │   │
│                      │ - get_document_symbols()     │   │
│                      └─────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

### Data Flow

1. **Request Phase**
   ```
   AI Agent → MCP Request → CodebaseTools.find_document_symbols()
   ```

2. **LSP Communication**
   ```
   CodebaseTools → SimpleLSPClient.get_document_symbols()
   → Spawn pylsp process → Send textDocument/documentSymbol
   → Receive hierarchical response → Parse and return
   ```

3. **Storage Phase**
   ```
   Repository Indexer → Extract symbols with hierarchy
   → Store in SQLite with parent relationships
   ```

4. **Response Phase**
   ```
   Build hierarchical tree → Format as JSON → Return to agent
   ```

### Implementation Classes

#### 1. DocumentSymbol Domain Model

```python
@dataclass
class SymbolRange:
    """LSP-compatible range information."""
    start_line: int
    start_character: int
    end_line: int
    end_character: int

@dataclass
class DocumentSymbol:
    """Hierarchical symbol information."""
    name: str
    detail: str | None
    kind: SymbolKind
    range: SymbolRange
    selection_range: SymbolRange
    children: list['DocumentSymbol']
    parent_id: int | None = None

    def to_dict(self) -> dict:
        """Convert to LSP-compatible dictionary."""
        return {
            "name": self.name,
            "detail": self.detail,
            "kind": self.kind.value,
            "range": {
                "start": {"line": self.range.start_line,
                         "character": self.range.start_character},
                "end": {"line": self.range.end_line,
                       "character": self.range.end_character}
            },
            "selectionRange": {
                "start": {"line": self.selection_range.start_line,
                         "character": self.selection_range.start_character},
                "end": {"line": self.selection_range.end_line,
                       "character": self.selection_range.end_character}
            },
            "children": [child.to_dict() for child in self.children]
        }
```

#### 2. SimpleLSPClient Extension

```python
async def get_document_symbols(
    self, file_uri: str, timeout: float = 10.0
) -> list[dict[str, Any]]:
    """Get document symbols with hierarchy.

    Returns LSP DocumentSymbol[] response with full hierarchy.
    """
    # Following existing pattern from get_definition()
    proc = await self._spawn_lsp_process()
    await self._initialize_lsp(proc)

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

#### 3. CodebaseTools Integration

```python
def get_tools(self, repo_name: str, repository_workspace: str) -> list[dict]:
    """Extended with document symbols tool."""
    return existing_tools + [
        {
            "name": "get_document_symbols",
            "description": f"Get hierarchical symbol tree for a file in {repo_name}",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "repository_id": {"type": "string"},
                    "file_path": {"type": "string"}
                },
                "required": ["repository_id", "file_path"]
            }
        }
    ]

async def find_document_symbols(
    self, repository_id: str, file_path: str
) -> str:
    """Get document symbols for a file."""
    # Resolve file path
    # Create LSP client
    # Call get_document_symbols
    # Format and return hierarchy
```

## Implementation Plan

### Phase 1: Foundation (2-3 days)
**Goal**: Establish core infrastructure without breaking existing functionality

1. **Create Domain Models**
   - Implement `document_symbol_types.py` with DocumentSymbol classes
   - Add hierarchy fields to Symbol dataclass (backward compatible)
   - Write comprehensive unit tests

2. **Extend SimpleLSPClient**
   - Implement `get_document_symbols()` method
   - Follow existing patterns from `get_definition()`
   - Add proper error handling and logging

3. **Database Migration**
   - Create migration script for schema changes
   - Ensure backward compatibility
   - Test with existing data

### Phase 2: Integration (2-3 days)
**Goal**: Connect components and expose through MCP

1. **Symbol Storage Updates**
   - Add methods for storing/retrieving hierarchical symbols
   - Implement parent-child relationship queries
   - Add range information support

2. **CodebaseTools Integration**
   - Add `get_document_symbols` tool definition
   - Implement `find_document_symbols()` method
   - Wire up with SimpleLSPClient

3. **Testing Infrastructure**
   - Create mock LSP responses
   - Write integration tests
   - Test with real Python files

### Phase 3: Indexing Enhancement (1-2 days)
**Goal**: Populate hierarchy data during repository indexing

1. **Update PythonSymbolExtractor**
   - Track parent symbols during AST traversal
   - Extract range information
   - Build parent-child relationships

2. **Modify RepositoryIndexer**
   - Store hierarchy information
   - Handle nested symbols correctly
   - Maintain performance

### Phase 4: Optimization & Polish (1-2 days)
**Goal**: Performance tuning and production readiness

1. **Performance Optimization**
   - Add caching for frequently accessed files
   - Optimize hierarchy queries
   - Implement batch operations

2. **Error Handling**
   - Graceful degradation for unsupported files
   - Comprehensive error messages
   - Retry logic for LSP failures

3. **Documentation**
   - Update API documentation
   - Add usage examples
   - Document performance characteristics

## Risk Assessment

### Technical Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| LSP server compatibility | High | Test with both pylsp and pyright, implement fallbacks |
| Database migration failures | Medium | Comprehensive backup strategy, reversible migrations |
| Performance degradation | Medium | Benchmark before/after, implement caching |
| Memory usage for large files | Low | Implement streaming/pagination for large hierarchies |

### Implementation Challenges

1. **Hierarchy Reconstruction**
   - Challenge: Building tree from flat database records
   - Solution: Recursive query with proper ordering, in-memory tree building

2. **Range Accuracy**
   - Challenge: Ensuring accurate line/column positions
   - Solution: Validate against source files, comprehensive testing

3. **Backward Compatibility**
   - Challenge: Not breaking existing symbol operations
   - Solution: Additive changes only, extensive regression testing

## Engineering Best Practices

### Code Quality Standards

1. **Type Safety**
   - Use modern Python type hints throughout
   - `| None` instead of `Optional[T]`
   - Proper generic types for collections

2. **Error Handling**
   - Explicit error types and messages
   - Graceful degradation
   - Comprehensive logging at appropriate levels

3. **Testing Coverage**
   - Unit tests for all new methods
   - Integration tests for end-to-end flows
   - Mock implementations following existing patterns
   - No `unittest.mock` usage

4. **Performance Considerations**
   - Lazy loading where appropriate
   - Connection pooling for database
   - Subprocess reuse investigation for LSP

### Operational Considerations

1. **Monitoring**
   - Log symbol extraction statistics
   - Track LSP request latencies
   - Monitor database query performance

2. **Deployment**
   - Feature flag for gradual rollout
   - Database migration automation
   - Rollback procedures documented

3. **Documentation**
   - Inline code documentation
   - API documentation updates
   - Architecture decision records

## Success Metrics

1. **Performance Metrics**
   - Document symbol retrieval < 500ms for average file
   - Memory usage increase < 20% for symbol storage
   - LSP request success rate > 99%

2. **Functionality Metrics**
   - Accurate hierarchy for 100% of well-formed Python files
   - Graceful handling of malformed files
   - Complete symbol coverage (classes, methods, functions, variables)

3. **User Experience Metrics**
   - 10x-100x reduction in tokens for file understanding
   - Precise navigation to symbol definitions
   - Accurate insertion point identification for new code

## Technical Debt Considerations

### Opportunities for Improvement

1. **LSP Client Architecture**
   - Current: Subprocess per request
   - Future: Connection pooling or persistent processes
   - Benefit: Reduced latency, better resource usage

2. **Symbol Storage Optimization**
   - Current: Flat table with parent references
   - Future: Materialized path or nested set model
   - Benefit: Faster hierarchy queries

3. **Caching Strategy**
   - Current: No caching
   - Future: Redis or in-memory cache for hot files
   - Benefit: Improved response times for frequently accessed files

### Refactoring Opportunities

1. **Abstract Symbol Hierarchy Interface**
   - Create interface for different hierarchy providers
   - Enable multiple implementation strategies

2. **Unified Symbol Model**
   - Consolidate flat and hierarchical symbol representations
   - Reduce code duplication

## Conclusion

The Document Symbol Hierarchy feature represents a significant enhancement to the GitHub Agent MCP Server's code analysis capabilities. By leveraging the existing robust architecture and following established patterns, we can implement this feature with minimal risk and maximum benefit.

The phased implementation approach ensures continuous value delivery while maintaining system stability. The focus on engineering excellence, comprehensive testing, and backward compatibility aligns with the codebase's existing high standards.

This feature will dramatically improve AI agent efficiency in code navigation and modification tasks, reducing token consumption by orders of magnitude while increasing precision in code operations.

## Appendix: Example Usage

### MCP Request
```json
{
  "method": "get_document_symbols",
  "params": {
    "repository_id": "github-agent",
    "file_path": "codebase_tools.py"
  }
}
```

### Expected Response
```json
{
  "symbols": [
    {
      "name": "CodebaseTools",
      "kind": "class",
      "detail": "class CodebaseTools",
      "range": {"start": {"line": 57, "character": 0},
                "end": {"line": 900, "character": 0}},
      "children": [
        {
          "name": "__init__",
          "kind": "method",
          "detail": "def __init__(self, ...)",
          "range": {"start": {"line": 69, "character": 4},
                    "end": {"line": 88, "character": 0}},
          "children": []
        },
        {
          "name": "get_tools",
          "kind": "method",
          "detail": "def get_tools(self, ...)",
          "range": {"start": {"line": 112, "character": 4},
                    "end": {"line": 276, "character": 0}},
          "children": []
        }
      ]
    }
  ]
}
```

This design provides a practical, implementable approach that leverages the existing codebase's strengths while adding powerful new capabilities for AI-assisted code navigation and modification.