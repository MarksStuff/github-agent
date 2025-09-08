# Consolidated Design Document

## 1. Introduction

This design document specifies the architecture for adding Document Symbol Hierarchy support to the github-agent codebase. The feature will expose hierarchical symbol information (classes, methods, functions with parent-child relationships) through the MCP protocol, enabling coding agents to better understand code structure. The implementation leverages existing LSP infrastructure while maintaining backward compatibility with the current flat symbol storage system.

## 2. Goals / Non-Goals

### Goals
- Expose textDocument/documentSymbol LSP capability through MCP tools
- Preserve parent-child relationships between symbols (e.g., methods within classes)
- Provide accurate symbol ranges (start and end positions)
- Cache symbol hierarchies to reduce LSP server calls
- Support fallback to AST-based extraction when LSP is unavailable
- Maintain backward compatibility with existing flat symbol queries

### Non-Goals
- Cross-file symbol relationship tracking
- Real-time file watching for cache invalidation
- Support for non-Python languages initially
- Incremental symbol updates on partial file changes
- Complex caching strategies beyond simple TTL
- Modification of existing Symbol class core functionality

## 3. Proposed Architecture

The architecture extends the existing LSP and symbol storage infrastructure through a layered approach:

1. **LSP Layer**: Extends `SimpleLSPClient` with documentSymbol support
2. **Provider Layer**: New `DocumentSymbolProvider` orchestrates symbol extraction
3. **Storage Layer**: Extends existing `Symbol` dataclass with optional hierarchy fields
4. **Cache Layer**: Simple JSON-based file cache with TTL validation
5. **MCP Layer**: Exposes functionality through `CodebaseTools` integration

Data flows from MCP request → CodebaseTools → DocumentSymbolProvider → LSP Client → Cache → Response. The design maintains separation of concerns with each layer having a single responsibility.

## 4. Detailed Design

### Class Specifications

```python
# document_symbol_provider.py
class DocumentSymbolProvider:
    """Orchestrates document symbol extraction from LSP or AST fallback"""
    
    def __init__(self, 
                 lsp_client: SimpleLSPClient,
                 symbol_extractor: AbstractSymbolExtractor,
                 cache_dir: Path | None = None):
        """Initialize with LSP client, fallback extractor, and optional cache"""
    
    async def get_document_symbols(self, file_path: str) -> list[Symbol]:
        """Get hierarchical symbols for a file"""
    
    def _check_cache(self, file_path: str) -> list[Symbol] | None:
        """Check JSON cache for valid symbols"""
    
    def _save_to_cache(self, file_path: str, symbols: list[Symbol]) -> None:
        """Save symbols to JSON cache"""
    
    def _convert_lsp_response(self, lsp_symbols: list[dict]) -> list[Symbol]:
        """Convert LSP response to Symbol hierarchy"""
    
    def _build_hierarchy(self, symbols: list[Symbol]) -> list[Symbol]:
        """Build parent-child relationships"""
```

### Extended Data Structures

```python
# symbol_storage.py - Extend existing Symbol dataclass
@dataclass
class Symbol:
    # ... existing fields ...
    parent_id: str | None = None
    children: list['Symbol'] = field(default_factory=list)
    end_line: int | None = None
    end_column: int | None = None
    
    def to_hierarchical_dict(self) -> dict[str, Any]:
        """Serialize with hierarchy information"""
    
    def validate_hierarchy(self) -> bool:
        """Validate parent-child relationships and ranges"""
```

### LSP Client Extension

```python
# simple_lsp_client.py - Add to SimpleLSPClient class
async def get_document_symbols(self, 
                              file_uri: str, 
                              timeout: float = 30.0) -> list[dict] | None:
    """Send textDocument/documentSymbol request to LSP server"""
```

### MCP Integration

```python
# codebase_tools.py - Add to CodebaseTools class
async def get_document_symbols(self, file_path: str) -> list[dict]:
    """MCP tool handler for document symbols"""

# Add to TOOL_HANDLERS mapping at line 61:
"get_document_symbols": "get_document_symbols"
```

### Cache Specification

```python
# Cache file structure (JSON)
{
    "file_path": "/path/to/file.py",
    "file_hash": "sha256:...",
    "timestamp": 1234567890.0,
    "symbols": [
        {
            "name": "MyClass",
            "kind": "CLASS",
            "line": 1,
            "column": 0,
            "end_line": 50,
            "end_column": 0,
            "children": [...]
        }
    ]
}
```

### Database Design

```sql
-- Create new schema (no migrations, full rebuild)
DROP TABLE IF EXISTS symbols;

CREATE TABLE symbols (
    symbol_id TEXT PRIMARY KEY,
    file_path TEXT NOT NULL,
    name TEXT NOT NULL,
    kind TEXT NOT NULL,
    line INTEGER NOT NULL,
    column INTEGER NOT NULL,
    parent_symbol_id TEXT,
    end_line INTEGER,
    end_column INTEGER,
    created_at INTEGER DEFAULT (strftime('%s', 'now')),
    FOREIGN KEY (parent_symbol_id) REFERENCES symbols(symbol_id)
);

CREATE INDEX idx_symbols_file_path ON symbols(file_path);
CREATE INDEX idx_symbols_name ON symbols(name);
CREATE INDEX idx_symbol_parent ON symbols(parent_symbol_id);
```

## 5. Alternatives Considered

**Separate Document Symbols Table**: Creating a new `document_symbols` table was considered but rejected due to unnecessary complexity and duplication of data. Extending the existing Symbol class is simpler.

**Complex Caching with WAL Mode**: Implementing SQLite-based caching with WAL mode was considered but deemed over-engineering for MVP. JSON file cache is sufficient initially.

**Abstract Base Classes**: Creating `AbstractDocumentSymbolProvider` and `AbstractDocumentSymbolCache` was considered but rejected to avoid abstraction bloat without multiple implementations.

**Real-time File Watching**: Implementing file watchers for cache invalidation was considered but deferred as the simple TTL approach is adequate for initial release.

## 6. Testing / Validation

### Test Classes

```python
# tests/test_document_symbols.py
class TestDocumentSymbolProvider(unittest.TestCase):
    """Test document symbol extraction and hierarchy building"""
    
    def test_lsp_symbol_extraction(self):
        """Test successful LSP documentSymbol request"""
    
    def test_fallback_to_ast_extraction(self):
        """Test AST fallback when LSP unavailable"""
    
    def test_cache_hit_and_miss(self):
        """Test cache behavior with TTL"""
    
    def test_hierarchy_building(self):
        """Test parent-child relationship construction"""
    
    def test_circular_reference_detection(self):
        """Test prevention of circular parent references"""
    
    def test_range_validation(self):
        """Test symbol range consistency"""

# tests/test_lsp_document_symbol_integration.py
class TestLSPDocumentSymbolIntegration(unittest.TestCase):
    """Integration tests with real LSP server"""
    
    def test_pylsp_response_parsing(self):
        """Test with pylsp server response format"""
    
    def test_large_file_performance(self):
        """Test performance with 1000+ symbols"""
```

### Mock Specifications

```python
# tests/mocks/mock_lsp_client.py - Extend existing
class MockLSPClient:
    def set_document_symbols_response(self, uri: str, symbols: list[dict]):
        """Set mock response for document symbols"""
    
    async def get_document_symbols(self, uri: str) -> list[dict] | None:
        """Return mock document symbols"""
```

### Test Scenarios
- Empty file handling
- Syntax error recovery
- Deeply nested symbols (5+ levels)
- Unicode symbol names
- Overlapping or malformed ranges
- File modification during extraction
- LSP timeout scenarios
- Cache corruption recovery

## 7. Migration / Deployment & Rollout

### Deployment Steps

1. **Phase 1 - LSP Integration** (No schema changes)
   - Deploy `SimpleLSPClient.get_document_symbols()` method
   - Add MCP tool handler to `CodebaseTools`
   - Return flat symbol list initially

2. **Phase 2 - Database Rebuild** (Full refresh)
   - Drop existing symbols table completely
   - Create new symbols table with hierarchy fields
   - Run full codebase analysis to repopulate all symbols
   - No migration scripts needed - clean slate approach

3. **Phase 3 - Hierarchy Activation**
   - Deploy `DocumentSymbolProvider` with cache
   - Enable hierarchy building from LSP response
   - Activate MCP tool to return hierarchical data

### Database Rebuild Process

```python
# rebuild_database.py
async def rebuild_symbol_database(repo_path: Path):
    """Complete database rebuild for schema changes"""
    
    # 1. Drop existing tables
    await db.execute("DROP TABLE IF EXISTS symbols")
    
    # 2. Create new schema
    await db.execute(CREATE_SYMBOLS_TABLE_SQL)
    
    # 3. Re-analyze entire codebase
    indexer = RepositoryIndexer(repo_path)
    await indexer.index_repository(force_rebuild=True)
    
    # 4. Verify integrity
    await verify_symbol_hierarchy()
```

### Configuration Parameters

```python
# Repository configuration
{
    "use_document_symbols": true,  # Feature flag
    "document_symbol_cache_ttl": 300,  # 5 minutes
    "lsp_document_symbol_timeout": 30.0,  # seconds
    "rebuild_on_schema_change": true  # Auto-rebuild database
}
```

### Rollback Strategy
- Feature flag `use_document_symbols` disables entire feature
- Database rebuild is idempotent - can re-run anytime
- Previous database backup retained until new analysis completes
- Cache can be cleared without affecting core functionality

## Appendix

### Conflict Resolutions

**Schema Modification vs New Table**: Resolved to extend existing Symbol class with optional fields rather than creating separate tables. This maintains backward compatibility while avoiding data duplication.

**Abstract Base Classes**: Decided against new abstractions initially. Will add only if multiple implementations emerge.

**Cache Implementation**: JSON file cache chosen over SQLite for MVP. Database integration deferred to Phase 3.

**Test Coverage**: Minimum 80% coverage for MVP, comprehensive integration tests with real LSP servers required before production.

**Migration Strategy**: Resolved to use clean rebuild approach instead of migrations. Drop and recreate tables, then re-analyze entire codebase for consistency.

### Technical Implementation Notes

**LSP Response Normalization**: Different LSP servers return varying response formats. Implementation must handle both flat lists (older servers) and nested structures (modern servers).

**Symbol Kind Mapping**: LSP servers may use numeric or string constants for symbol kinds. Requires mapping layer to normalize to internal SymbolKind enum.

**Performance Constraints**: Target response time <100ms for files under 1000 lines, <1s for files up to 10,000 lines.

**Error Recovery**: LSP failures should fall back to AST extraction. Cache corruption should trigger rebuild rather than error propagation.

**Database Rebuild Triggers**: Schema version stored in metadata table. On version mismatch, automatic rebuild initiated. User prompted for confirmation in interactive mode.