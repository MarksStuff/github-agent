# Peer Review Results

Generated: 2025-09-07T19:19:36.670417

## Architect Peer Review

**Status**: success

## ARCHITECTURAL REVIEW: Document Symbol Hierarchy Feature

### 1. ARCHITECTURAL ALIGNMENT ✅

**Pattern Compliance:**
- ✅ **Abstract Base Pattern**: Correctly identifies need for `AbstractDocumentSymbolProvider` following `AbstractSymbolStorage` (symbol_storage.py:88-202)
- ✅ **Repository Pattern**: Properly extends `SQLiteSymbolStorage` rather than creating new storage
- ✅ **Visitor Pattern**: Leverages existing `PythonSymbolExtractor.visit_node` (python_symbol_extractor.py:155)

**Architectural Conflicts:**
- ❌ **Schema Breaking Change**: Adding `parent_id` to existing `Symbol` dataclass breaks backward compatibility
  - **Fix**: Create `HierarchicalSymbol(Symbol)` subclass instead
- ❌ **Mutable State Anti-pattern**: Developer mentions reusing `PythonSymbolExtractor.symbols` list (line 38) which is mutable class state
  - **Fix**: Return hierarchical structure, don't mutate shared state

### 2. SYSTEM INTEGRATION GAPS

**Missing Interface Definitions:**
```python
# Required but not specified:
class AbstractDocumentSymbolProvider(ABC):
    @abstractmethod
    async def get_document_symbols(self, file_path: str) -> list[Symbol]:
        pass
```

**Incomplete LSP Integration:**
- ✅ Correctly extends `SimpleLSPClient` 
- ❌ Missing versioning for LSP response compatibility (pylsp vs pyright)
  - **Add**: Response adapter pattern like `_adapt_lsp_response()` 

**Database Migration Missing:**
```sql
-- Required migration not addressed:
ALTER TABLE symbols ADD COLUMN parent_symbol_id TEXT;
ALTER TABLE symbols ADD COLUMN range_end_line INTEGER;
ALTER TABLE symbols ADD COLUMN range_end_column INTEGER;
CREATE INDEX idx_parent_symbol ON symbols(parent_symbol_id);
```

### 3. PATTERN CONSISTENCY ISSUES

**Naming Convention Violations:**
- ❌ `DocumentSymbolProvider` should be `AbstractDocumentSymbolProvider` for base class
- ❌ `DocumentSymbolCache` doesn't follow existing cache pattern in `CodebaseTools._lsp_clients` (dict-based)
- ✅ Correctly uses underscore prefix for private methods

**Error Handling Mismatch:**
- ✅ Follows `_execute_with_retry` pattern from SQLiteSymbolStorage
- ❌ Missing corruption recovery like `_recover_from_corruption` (symbol_storage.py:306-328)
- ❌ No mention of logging pattern: `logger = logging.getLogger(__name__)`

**Testing Pattern Deviation:**
- ✅ Correctly identifies mock pattern from `tests/mocks/`
- ❌ Tester suggests `MockHierarchicalSymbolStorage` when should extend existing `MockSymbolStorage`
- ❌ Test file naming: should be `test_document_symbols.py` not `test_document_symbol_hierarchy.py` (follows `test_lsp_client.py` pattern)

### 4. SPECIFIC ARCHITECTURAL IMPROVEMENTS

**Required Class Modifications:**
```python
# symbol_storage.py - DON'T modify Symbol, extend it:
@dataclass
class HierarchicalSymbol(Symbol):
    parent_symbol_id: str | None = None
    children: list['HierarchicalSymbol'] = field(default_factory=list)
    range_end_line: int | None = None
    range_end_column: int | None = None
```

**File Creation Order (Corrected):**
1. `abstract_document_symbol_provider.py` - Interface definition
2. `lsp_document_symbol_provider.py` - LSP implementation  
3. `ast_document_symbol_provider.py` - AST fallback implementation
4. Update `simple_lsp_client.py` - Add `get_document_symbols()` method
5. Extend `tests/mocks/mock_symbol_storage.py` - NOT create new mock

**Integration Points (Specific):**
```python
# codebase_tools.py:224 - Add to TOOL_HANDLERS:
"get_document_symbols": self._handle_get_document_symbols,

# simple_lsp_client.py - Add method following existing pattern:
async def get_document_symbols(self, file_path: str) -> dict | None:
    # Follow get_references() pattern at line 312-351
```

### 5. SCALABILITY CONCERNS

**Performance Risks:**
- ⚠️ No mention of connection pooling for concurrent requests (SQLiteSymbolStorage uses single connection)
- ⚠️ Cache invalidation strategy unclear - file watching not addressed
- ✅ Correctly identifies need for lazy loading deep hierarchies

**Realistic Scale Requirements:**
- Python files rarely exceed 5000 lines (Linux kernel drivers ~3000 lines)
- Symbol depth rarely exceeds 4 levels (class → method → inner class → method)
- **Recommendation**: Skip complex caching initially, use simple TTL like `_lsp_clients` dict

### 6. CRITICAL CORRECTIONS

**Database Schema Approach:**
```python
# DON'T alter existing schema, create supplementary table:
CREATE TABLE symbol_hierarchy (
    symbol_id TEXT PRIMARY KEY,
    parent_symbol_id TEXT,
    range_end_line INTEGER,
    range_end_column INTEGER,
    FOREIGN KEY (symbol_id) REFERENCES symbols(id),
    FOREIGN KEY (parent_symbol_id) REFERENCES symbols(id)
);
```

**Correct Implementation Order:**
1. Extend `SimpleLSPClient.get_document_symbols()` - test with real pylsp
2. Create adapter for LSP response → `HierarchicalSymbol` 
3. Add MCP tool to `CodebaseTools` returning flat list initially
4. Add hierarchy in phase 2 after validating LSP compatibility

**Remove Over-engineering:**
- ❌ Skip `DocumentSymbolCache` - use existing `_lsp_clients` pattern
- ❌ Skip `max_symbol_depth` config - unnecessary complexity
- ❌ Skip incremental updates - not in requirements

The proposals are architecturally sound but need adjustments to match existing patterns exactly. Focus on extending current abstractions rather than modifying core classes.

---

## Developer Peer Review

**Status**: success

## Fast Coder Review: Document Symbol Hierarchy Feature

### Quick Implementation Path

**Fastest MVP - Reuse Existing Infrastructure:**
```python
# 1. Extend simple_lsp_client.py (+30 lines)
async def get_document_symbols(self, file_uri: str) -> list[dict]:
    # Copy pattern from get_references() at line 165
    return await self._send_request("textDocument/documentSymbol", {
        "textDocument": {"uri": file_uri}
    })

# 2. Add to codebase_tools.py (+15 lines)
async def get_document_symbols(self, file_path: str) -> list[dict]:
    # Reuse existing LSP client caching
    symbols = await self.lsp_client.get_document_symbols(f"file://{file_path}")
    return symbols or []
```

**Skip the Over-Engineering:**
- ❌ Architect's SQL schema is overkill - start with in-memory cache
- ❌ Senior's HierarchicalSymbol subclass - use existing Symbol with parent_id field
- ❌ Tester's 5+ test files - start with one integration test

### Practical Simplifications

**Instead of Complex Caching:**
```python
# Just use a dict for now
self._symbol_cache: dict[str, tuple[float, list]] = {}  # path -> (mtime, symbols)

def get_cached_or_fetch(self, path: str) -> list:
    mtime = os.path.getmtime(path)
    if path in self._symbol_cache:
        cached_time, symbols = self._symbol_cache[path]
        if cached_time == mtime:
            return symbols
    # Fetch and cache
```

**Instead of New Tables:**
- Add `parent_id`, `end_line`, `end_column` to existing Symbol dataclass
- Use existing `symbols` table - no new schema migration needed
- Store hierarchy as JSON in existing `detail` field temporarily

### Iterative Build Plan

**Phase 1 (2 hours):**
1. Add LSP method to `simple_lsp_client.py`
2. Wire up in `codebase_tools.py`
3. Write one integration test
4. Deploy and test with real LSP server

**Phase 2 (1 hour):**
1. Add simple in-memory cache
2. Test cache invalidation on file change

**Phase 3 (if needed):**
1. Persist to existing SQLite table
2. Add parent_id column migration

### Disagreements with Analyses

**Architect Over-Complicates:**
- New `document_symbols` table unnecessary - reuse existing
- Abstract Factory for caching is premature
- WAL mode configuration - already enabled

**Senior's Refactoring Too Aggressive:**
- Don't refactor PythonSymbolExtractor now - it works
- Skip Builder/Composite patterns - YAGNI
- `_execute_with_retry` already handles what we need

**Tester's Coverage Unrealistic:**
- 95% coverage target blocks shipping
- 4 new test files is excessive
- Mock implementations can come later

### Real Implementation Issues

**Actual Problems to Solve:**
```python
# 1. LSP response varies by server
# pylsp returns flat list, rust-analyzer returns nested
if isinstance(symbols[0], dict) and 'children' in symbols[0]:
    # Handle nested format
else:
    # Handle flat format

# 2. Symbol kinds differ between servers
kind_mapping = {
    "Class": SymbolKind.CLASS,
    5: SymbolKind.CLASS,  # Some servers use numbers
    # ...
}
```

**What Will Actually Break:**
- Large files (>10k lines) will timeout - increase to 30s
- Concurrent requests to same file - use asyncio.Lock
- LSP server not running - return empty list, don't fail

### Minimum Viable Implementation

```python
# codebase_tools.py - 20 lines total
async def get_document_symbols(self, file_path: str) -> list[dict]:
    """Get symbol hierarchy for a file."""
    try:
        abs_path = os.path.abspath(file_path)
        uri = f"file://{abs_path}"
        
        # Check simple cache
        if hasattr(self, '_symbol_cache'):
            if uri in self._symbol_cache:
                return self._symbol_cache[uri]
        
        # Get from LSP
        symbols = await self.lsp_client.get_document_symbols(uri)
        
        # Cache for this session
        if not hasattr(self, '_symbol_cache'):
            self._symbol_cache = {}
        self._symbol_cache[uri] = symbols
        
        return symbols or []
    except Exception as e:
        logger.warning(f"Failed to get symbols for {file_path}: {e}")
        return []
```

**That's it. Ship it, iterate based on usage.**

---

## Senior Engineer Peer Review

**Status**: success

## Senior Engineer Review: Document Symbol Hierarchy Feature

### Code Quality Assessment

**Architect's Approach - Strengths:**
- Reuses existing `_execute_with_retry` pattern from `symbol_storage.py:281-304`
- Properly extends `Symbol` dataclass rather than creating parallel structures
- Clean separation with `document_symbol_cache.py` module

**Architect's Approach - Concerns:**
```python
# Overly complex schema with redundant fields
CREATE TABLE document_symbols (
    file_version TEXT NOT NULL,  # This couples storage to git
    extracted_at TIMESTAMP,      # Unnecessary for symbols
    ...
)
```
Better: Store only essential fields. Version tracking belongs in a separate cache metadata table.

**Developer's Approach - Strengths:**
- Incremental implementation plan reduces risk
- Fallback pattern (LSP → AST) is pragmatic
- Reuses existing `SimpleLSPClient` patterns

**Developer's Approach - Concerns:**
- "Lazy-load children for deep hierarchies" adds unnecessary complexity
- Mixed responsibilities in `DocumentSymbolProvider` (orchestration + caching + fallback)

### Long-term Maintainability Issues

**Schema Design Problem:**
```python
# From Architect's plan
parent_id INTEGER,
FOREIGN KEY (parent_id) REFERENCES document_symbols(id)
```
Self-referential foreign keys in SQLite make bulk operations painful. Better approach:
```python
# Store hierarchy as JSON in single column
symbols_json TEXT,  -- Full hierarchy serialized
file_hash TEXT,     -- Simple cache key
```

**Abstraction Overengineering:**
Both analyses suggest `AbstractDocumentSymbolProvider` and `AbstractDocumentSymbolCache`. This codebase already has:
- `AbstractSymbolStorage` at `symbol_storage.py:88-202`
- `AbstractSymbolExtractor` at `symbol_extractor.py:62-97`

Adding more abstractions without concrete implementations creates maintenance burden.

### Recommended Simplifications

**1. Single Responsibility Classes:**
```python
# Instead of DocumentSymbolProvider doing everything:
class LSPSymbolHierarchy:
    """Only handles LSP documentSymbol calls"""
    def get_symbols(self, file_path: str) -> list[DocumentSymbol]

class SymbolHierarchyCache:
    """Only handles caching logic"""
    def get_or_fetch(self, file_path: str, fetcher: Callable)
```

**2. Extend Existing Symbol Class Minimally:**
```python
@dataclass
class Symbol:
    # ... existing fields ...
    children: list['Symbol'] | None = None  # Only add this
    # Don't add parent_id, end_line, end_column yet
```

**3. Reuse Existing Patterns:**
The codebase already has subprocess management in `simple_lsp_client.py:165-254`. Don't create new patterns:
```python
# Good - follows existing pattern
async def get_document_symbols(self, file_uri: str, timeout: float = 10.0):
    return await self._send_request(
        "textDocument/documentSymbol",
        {"textDocument": {"uri": file_uri}},
        timeout
    )
```

### Testing Strategy Critique

**Tester's Over-specification:**
```python
# Too many mock classes proposed
MockDocumentSymbolProvider
MockHierarchicalSymbolStorage
MockLSPClient (extended)
```

The codebase pattern at `tests/mocks/` shows minimal mocking. Follow that:
```python
# Better - single mock for testing
class MockLSPClient(SimpleLSPClient):
    def __init__(self):
        self.document_symbols_response = {}
    
    async def get_document_symbols(self, uri: str):
        return self.document_symbols_response.get(uri, [])
```

### Implementation Priority

**MVP (What Actually Matters):**
1. Add `get_document_symbols()` to `SimpleLSPClient`
2. Add handler in `codebase_tools.py:61-67`
3. Return raw LSP response formatted as hierarchy
4. One integration test with real pylsp

**Defer These Complexities:**
- Database schema changes
- Caching layer
- AST fallback
- Abstract base classes
- File version tracking

### Code Health Recommendations

**1. Naming Consistency:**
```python
# Match existing patterns in codebase
get_document_symbols()  # Not getDocumentSymbols()
symbol_kind            # Not symbolKind
```

**2. Error Handling Pattern:**
```python
# Follow existing pattern from symbol_storage.py:233-258
try:
    symbols = await self.get_document_symbols(uri)
except (TimeoutError, ProcessError) as e:
    logger.warning(f"LSP symbol fetch failed: {e}")
    return []  # Empty list, not None
```

**3. Configuration Simplicity:**
```python
# Not needed in MVP:
# enable_document_symbol_cache
# document_symbol_cache_ttl
# max_symbol_depth

# Only need:
use_document_symbols: bool = True  # Feature flag
```

### Final Verdict

Both analyses over-engineer the solution. The feature can be implemented in ~100 lines by:
1. Adding one method to `SimpleLSPClient`
2. Adding one handler to `CodebaseTools`
3. Formatting the LSP response

Start simple. Add complexity only when real usage demonstrates the need.

---

## Tester Peer Review

**Status**: success

## Test-Focused Review of Document Symbol Hierarchy Analyses

### 1. Testing Coverage Assessment

**Critical Testing Gaps Identified:**

The analyses miss several testability concerns:

- **No mock for `SimpleLSPClient`** - Existing tests use `MockLSPClient` (tests/mocks/mock_lsp_client.py), but adding `get_document_symbols()` needs corresponding mock implementation
- **Missing hierarchy validation tests** - Need tests for circular parent references, orphaned children, invalid ranges
- **No integration test plan** - Should test full flow: `CodebaseTools` → `DocumentSymbolProvider` → `SimpleLSPClient` → Storage

**Edge Cases Not Addressed:**

```python
# tests/test_document_symbols.py - Missing test scenarios
def test_circular_parent_reference():
    """Symbols can't be their own parent/grandparent"""
    
def test_overlapping_symbol_ranges():
    """Child range must be within parent range"""
    
def test_symbol_without_end_position():
    """LSP servers may omit end positions"""
```

### 2. Quality Assurance Issues

**Testability Problems in Proposed Design:**

1. **Architect's SQL schema lacks testability**:
   - Direct foreign key `parent_id` makes testing hierarchies difficult
   - Should use `MockSymbolStorage` pattern from tests/mocks/mock_symbol_storage.py:15-89

2. **Developer's fallback chain is hard to test**:
   ```python
   # Proposed but untestable:
   LSP → Cache → AST fallback
   
   # Testable approach using dependency injection:
   class DocumentSymbolProvider:
       def __init__(self, lsp_client: AbstractLSPClient,
                   cache: AbstractSymbolCache,
                   extractor: AbstractSymbolExtractor):
           # Now we can inject mocks for each layer
   ```

3. **Senior's `HierarchicalSymbol` subclass breaks existing tests**:
   - Changing `Symbol` dataclass will break tests/test_symbol_storage.py:89-156
   - Better: Add optional fields to existing `Symbol` class

### 3. Testing Strategy Improvements

**Required Test Structure Following Existing Patterns:**

```python
# tests/test_document_symbol_provider.py
class TestDocumentSymbolProvider(unittest.TestCase):
    def setUp(self):
        # Follow pattern from test_codebase_tools.py:50-80
        self.mock_lsp_client = MockLSPClient()
        self.mock_storage = MockSymbolStorage()
        self.provider = DocumentSymbolProvider(
            lsp_client=self.mock_lsp_client,
            storage=self.mock_storage
        )
    
    def test_get_symbols_with_hierarchy(self):
        # Test happy path with mock LSP response
        
    def test_fallback_to_ast_extractor(self):
        # Test when LSP fails
        
    def test_cache_invalidation_on_file_change(self):
        # Test version-based caching
```

**Missing Test Doubles:**

```python
# tests/mocks/mock_document_symbol_cache.py
class MockDocumentSymbolCache(AbstractDocumentSymbolCache):
    """Following pattern from mock_symbol_storage.py"""
    def __init__(self):
        self.symbols: dict[str, list[Symbol]] = {}
        self.versions: dict[str, str] = {}
```

### 4. Risk Assessment & Priority Testing

**Highest Quality Risks:**

1. **Database Migration** - Changing schema needs rollback tests:
   ```python
   def test_schema_migration_rollback():
       """Ensure we can rollback if migration fails"""
   ```

2. **LSP Server Compatibility** - Different servers return different formats:
   ```python
   def test_pylsp_response_format():
       """Test with actual pylsp response structure"""
   
   def test_pyright_response_format():
       """Test with pyright's different structure"""
   ```

3. **Performance with Large Files** - Need load tests:
   ```python
   def test_performance_with_1000_symbols():
       """Ensure < 1s response time"""
   ```

**Testing Priority Order:**

1. **First**: Unit tests for Symbol hierarchy validation
2. **Second**: Integration tests with MockLSPClient
3. **Third**: Schema migration tests with rollback
4. **Fourth**: Performance tests with large files
5. **Last**: End-to-end tests with real LSP servers

### 5. Test-Driven Implementation Approach

**Start with Failing Tests:**

```python
# Write these tests FIRST, then implement to make them pass

def test_symbol_hierarchy_construction():
    """TDD: Define expected hierarchy structure"""
    parent = Symbol(name="MyClass", kind=SymbolKind.CLASS,
                   file_path="test.py", line=1, column=0)
    child = Symbol(name="my_method", kind=SymbolKind.METHOD,
                  file_path="test.py", line=2, column=4,
                  parent_id=parent.id)
    
    hierarchy = build_hierarchy([parent, child])
    assert hierarchy[0].children[0].name == "my_method"

def test_lsp_response_parsing():
    """TDD: Define LSP response transformation"""
    lsp_response = {
        "name": "MyClass",
        "kind": 5,  # Class
        "children": [{
            "name": "my_method",
            "kind": 6  # Method
        }]
    }
    
    symbols = parse_lsp_response(lsp_response)
    assert len(symbols) == 2
    assert symbols[1].parent_id == symbols[0].id
```

**Refactoring for Testability:**

Instead of Senior's suggestion to create `HierarchicalSymbol`, make `Symbol` testable:

```python
# symbol_storage.py:40 - Add optional fields
@dataclass
class Symbol:
    # ... existing fields ...
    parent_id: int | None = None
    end_line: int | None = None
    end_column: int | None = None
    
    def validate_hierarchy(self) -> bool:
        """Testable validation method"""
        if self.parent_id == self.id:
            return False  # Can't be own parent
        if self.end_line and self.end_line < self.line:
            return False  # Invalid range
        return True
```

**Key Testing Requirements Missing from All Analyses:**

1. **Regression tests** for existing `get_symbols_by_file()` functionality
2. **Mock data fixtures** for complex hierarchies (nested classes, decorators, async methods)
3. **Property-based testing** for hierarchy invariants
4. **Mutation testing** to verify test effectiveness

---

