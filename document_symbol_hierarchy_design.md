# Document Symbol Hierarchy Feature - Test-First Design Document

## 1. Executive Summary

This design document proposes a test-driven implementation of the Document Symbol Hierarchy feature (`textDocument/documentSymbol`) for the GitHub Agent MCP Server. The feature will provide hierarchical symbol information for documents, enabling AI agents to navigate and modify code with surgical precision without reading entire files.

**Key Design Decisions:**
- **Test-First Development**: Write comprehensive test suites before implementation
- **Hierarchical Storage**: Extend SQLite schema to support parent-child symbol relationships
- **LSP Integration**: Leverage existing SimpleLSPClient with new documentSymbol method
- **Mock-First Testing**: Create comprehensive mock implementations following existing patterns
- **Backward Compatibility**: Maintain existing symbol storage while adding hierarchy support

## 2. Codebase Analysis

### 2.1 Current LSP Architecture

The system uses a **stateless LSP client** approach:

```python
# simple_lsp_client.py - Current pattern
class SimpleLSPClient:
    async def get_definition(...) -> list[dict] | None
    async def get_references(...) -> list[dict] | None
    async def get_hover(...) -> dict | None
    # Missing: get_document_symbols()
```

**Key Findings:**
- Each LSP request spawns a fresh `pylsp` subprocess
- Proper JSON-RPC protocol implementation exists
- LSP constants already define `DOCUMENT_SYMBOLS = "textDocument/documentSymbol"`
- PyRight LSP manager confirms `documentSymbolProvider: True` capability

### 2.2 Symbol Storage Architecture

Current schema stores flat symbols without hierarchy:

```sql
CREATE TABLE symbols (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    kind TEXT NOT NULL,
    file_path TEXT NOT NULL,
    line_number INTEGER NOT NULL,
    column_number INTEGER NOT NULL,
    repository_id TEXT NOT NULL,
    docstring TEXT
)
```

**Storage Patterns:**
- Abstract base class `AbstractSymbolStorage` with SQLite implementation
- Robust retry logic and WAL mode for concurrency
- Comprehensive indexing for performance

### 2.3 Testing Infrastructure

**Established Patterns:**
- **Abstract + Mock Pattern**: No `unittest.mock`, uses concrete mock implementations
- **Dependency Injection**: All dependencies injected via constructor
- **State Tracking**: Mocks track calls for verification

Example mock pattern:
```python
class MockSymbolStorage(AbstractSymbolStorage):
    def __init__(self):
        self.symbols: list[Symbol] = []
        # In-memory implementation
```

## 3. Integration Points

### 3.1 Files to Modify

| File | Modification | Purpose |
|------|-------------|---------|
| `simple_lsp_client.py` | Add `get_document_symbols()` method | LSP protocol implementation |
| `symbol_storage.py` | Extend schema with hierarchy columns | Parent-child relationships |
| `codebase_tools.py` | Add `find_document_symbols()` tool | MCP tool exposure |
| `python_symbol_extractor.py` | Add hierarchy extraction logic | AST traversal updates |
| `lsp_constants.py` | Add DocumentSymbol type definitions | Type safety |

### 3.2 New Files to Create

| File | Purpose |
|------|---------|
| `tests/test_document_symbols.py` | Comprehensive test suite |
| `tests/mocks/mock_document_symbols.py` | Mock hierarchy structures |
| `document_symbol_types.py` | Domain models for hierarchical symbols |

### 3.3 Database Migration

```sql
-- Add hierarchy support to symbols table
ALTER TABLE symbols ADD COLUMN parent_id INTEGER REFERENCES symbols(id);
ALTER TABLE symbols ADD COLUMN detail TEXT;
ALTER TABLE symbols ADD COLUMN start_line INTEGER;
ALTER TABLE symbols ADD COLUMN start_character INTEGER;
ALTER TABLE symbols ADD COLUMN end_line INTEGER;
ALTER TABLE symbols ADD COLUMN end_character INTEGER;

-- Index for hierarchy queries
CREATE INDEX idx_symbols_parent_id ON symbols(parent_id);
CREATE INDEX idx_symbols_file_hierarchy ON symbols(file_path, parent_id);
```

## 4. Detailed Design

### 4.1 Domain Model

```python
# document_symbol_types.py
from dataclasses import dataclass
from enum import IntEnum
from typing import Any

class SymbolKindLSP(IntEnum):
    """LSP Protocol SymbolKind values"""
    File = 1
    Module = 2
    Namespace = 3
    Package = 4
    Class = 5
    Method = 6
    Property = 7
    Field = 8
    Constructor = 9
    Enum = 10
    Interface = 11
    Function = 12
    Variable = 13
    Constant = 14
    String = 15
    Number = 16
    Boolean = 17
    Array = 18
    Object = 19
    Key = 20
    Null = 21
    EnumMember = 22
    Struct = 23
    Event = 24
    Operator = 25
    TypeParameter = 26

@dataclass
class Range:
    """LSP Range type"""
    start_line: int
    start_character: int
    end_line: int
    end_character: int

    def to_lsp_dict(self) -> dict[str, Any]:
        """Convert to LSP protocol format (0-based)"""
        return {
            "start": {"line": self.start_line, "character": self.start_character},
            "end": {"line": self.end_line, "character": self.end_character}
        }

@dataclass
class DocumentSymbol:
    """Hierarchical document symbol"""
    name: str
    kind: SymbolKindLSP
    range: Range
    selection_range: Range
    detail: str | None = None
    children: list["DocumentSymbol"] | None = None

    def to_lsp_dict(self) -> dict[str, Any]:
        """Convert to LSP protocol format"""
        result = {
            "name": self.name,
            "kind": int(self.kind),
            "range": self.range.to_lsp_dict(),
            "selectionRange": self.selection_range.to_lsp_dict(),
        }
        if self.detail:
            result["detail"] = self.detail
        if self.children:
            result["children"] = [child.to_lsp_dict() for child in self.children]
        return result
```

### 4.2 LSP Client Extension

```python
# simple_lsp_client.py - Addition
async def get_document_symbols(self, file_uri: str) -> list[dict] | None:
    """
    Get document symbols for a file.

    Args:
        file_uri: File URI (file:///path/to/file.py)

    Returns:
        List of DocumentSymbol dictionaries or None if failed
    """
    request = {
        "jsonrpc": "2.0",
        "id": self._get_next_id(),
        "method": "textDocument/documentSymbol",
        "params": {
            "textDocument": {"uri": file_uri}
        }
    }

    try:
        response = await self._send_request(request)
        return response.get("result")
    except Exception as e:
        self.logger.error(f"Document symbols request failed: {e}")
        return None
```

### 4.3 Storage Layer Updates

```python
# symbol_storage.py - AbstractSymbolStorage additions
@abstractmethod
def insert_document_symbols(
    self,
    file_path: str,
    repository_id: str,
    symbols: list[DocumentSymbol]
) -> None:
    """Insert hierarchical document symbols."""
    pass

@abstractmethod
def get_document_symbols(
    self,
    file_path: str,
    repository_id: str
) -> list[DocumentSymbol]:
    """Get hierarchical symbols for a document."""
    pass

# SQLiteSymbolStorage implementation
def _insert_symbol_hierarchy(
    self,
    symbol: DocumentSymbol,
    file_path: str,
    repository_id: str,
    parent_id: int | None = None
) -> int:
    """Recursively insert symbol and its children."""
    cursor = self._get_connection().cursor()

    cursor.execute("""
        INSERT INTO symbols (
            name, kind, file_path, repository_id,
            start_line, start_character, end_line, end_character,
            detail, parent_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        symbol.name,
        symbol.kind.name,
        file_path,
        repository_id,
        symbol.range.start_line,
        symbol.range.start_character,
        symbol.range.end_line,
        symbol.range.end_character,
        symbol.detail,
        parent_id
    ))

    symbol_id = cursor.lastrowid

    # Insert children recursively
    if symbol.children:
        for child in symbol.children:
            self._insert_symbol_hierarchy(
                child, file_path, repository_id, symbol_id
            )

    return symbol_id
```

### 4.4 CodebaseTools Integration

```python
# codebase_tools.py - New tool handler
TOOL_HANDLERS["find_document_symbols"] = "find_document_symbols"

async def find_document_symbols(
    self,
    repository_id: str,
    file_path: str,
    use_cache: bool = True
) -> str:
    """
    Get hierarchical document symbols for a file.

    Args:
        repository_id: Repository identifier
        file_path: Path to file relative to repository root
        use_cache: Whether to use cached symbols or fetch fresh from LSP

    Returns:
        JSON string with document symbols
    """
    repo_config = self.repository_manager.get_repository(repository_id)
    if not repo_config:
        return json.dumps({
            "error": f"Repository '{repository_id}' not found",
            "file_path": file_path
        })

    # Check cache first if requested
    if use_cache:
        cached_symbols = self.symbol_storage.get_document_symbols(
            file_path, repository_id
        )
        if cached_symbols:
            return json.dumps({
                "repository_id": repository_id,
                "file_path": file_path,
                "symbols": [s.to_lsp_dict() for s in cached_symbols],
                "source": "cache"
            })

    # Fetch fresh from LSP
    file_uri = self._path_to_uri(repo_config.workspace, file_path)
    lsp_client = self.lsp_client_factory(
        repo_config.workspace,
        repo_config.python_path
    )

    symbols = await lsp_client.get_document_symbols(file_uri)

    if symbols:
        # Convert and cache
        doc_symbols = self._parse_lsp_symbols(symbols)
        self.symbol_storage.insert_document_symbols(
            file_path, repository_id, doc_symbols
        )

        return json.dumps({
            "repository_id": repository_id,
            "file_path": file_path,
            "symbols": symbols,
            "source": "lsp"
        })

    return json.dumps({
        "repository_id": repository_id,
        "file_path": file_path,
        "symbols": [],
        "source": "lsp"
    })
```

## 5. Test-First Implementation Plan

### 5.1 Testing Phases

#### Phase 1: Unit Test Development (Days 1-2)
**Files to create first:**

1. **`tests/test_document_symbol_types.py`**
   ```python
   def test_symbol_kind_values():
       """Verify LSP SymbolKind enum values match protocol."""
       assert SymbolKindLSP.Class == 5
       assert SymbolKindLSP.Method == 6

   def test_range_to_lsp_dict():
       """Test Range serialization to LSP format."""
       range = Range(10, 5, 15, 20)
       lsp_dict = range.to_lsp_dict()
       assert lsp_dict == {
           "start": {"line": 10, "character": 5},
           "end": {"line": 15, "character": 20}
       }

   def test_document_symbol_hierarchy():
       """Test DocumentSymbol with nested children."""
       # Create class with methods
       class_symbol = DocumentSymbol(
           name="MyClass",
           kind=SymbolKindLSP.Class,
           range=Range(0, 0, 10, 0),
           selection_range=Range(0, 6, 0, 13),
           children=[
               DocumentSymbol(
                   name="__init__",
                   kind=SymbolKindLSP.Method,
                   range=Range(1, 4, 3, 0),
                   selection_range=Range(1, 8, 1, 16)
               )
           ]
       )
       lsp_dict = class_symbol.to_lsp_dict()
       assert len(lsp_dict["children"]) == 1
   ```

2. **`tests/test_lsp_document_symbols.py`**
   ```python
   @pytest.mark.asyncio
   async def test_get_document_symbols_success():
       """Test successful document symbol retrieval."""
       mock_response = {
           "jsonrpc": "2.0",
           "id": 1,
           "result": [{
               "name": "TestClass",
               "kind": 5,
               "range": {...},
               "children": [...]
           }]
       }
       # Test LSP client method

   @pytest.mark.asyncio
   async def test_get_document_symbols_empty_file():
       """Test document symbols for empty file."""
       # Should return empty list

   @pytest.mark.asyncio
   async def test_get_document_symbols_timeout():
       """Test timeout handling."""
       # Should handle gracefully
   ```

3. **`tests/test_symbol_storage_hierarchy.py`**
   ```python
   def test_insert_document_symbols_flat():
       """Test inserting symbols without children."""

   def test_insert_document_symbols_nested():
       """Test inserting deeply nested symbols."""

   def test_get_document_symbols_preserves_hierarchy():
       """Test that hierarchy is preserved on retrieval."""

   def test_update_document_symbols_replaces_old():
       """Test that updating symbols replaces old ones."""
   ```

#### Phase 2: Mock Implementation (Day 3)

**`tests/mocks/mock_document_symbols.py`**
```python
class MockDocumentSymbolStorage:
    """Mock storage with hierarchy support."""

    def __init__(self):
        self._symbols: dict[tuple[str, str], list[DocumentSymbol]] = {}

    def insert_document_symbols(
        self,
        file_path: str,
        repository_id: str,
        symbols: list[DocumentSymbol]
    ) -> None:
        """Store symbols in memory."""
        key = (file_path, repository_id)
        self._symbols[key] = symbols

    def get_document_symbols(
        self,
        file_path: str,
        repository_id: str
    ) -> list[DocumentSymbol]:
        """Retrieve symbols from memory."""
        key = (file_path, repository_id)
        return self._symbols.get(key, [])

class MockLSPClientWithSymbols(MockLSPClient):
    """Extended mock with document symbol support."""

    def __init__(self, workspace_root: str = "/test"):
        super().__init__(workspace_root)
        self._document_symbols: dict[str, list[dict]] = {}

    async def get_document_symbols(self, uri: str) -> list[dict] | None:
        """Return mocked document symbols."""
        return self._document_symbols.get(uri)

    def set_document_symbols(self, uri: str, symbols: list[dict]) -> None:
        """Set symbols for testing."""
        self._document_symbols[uri] = symbols
```

#### Phase 3: Integration Tests (Day 4)

**`tests/test_codebase_tools_document_symbols.py`**
```python
@pytest.mark.asyncio
async def test_find_document_symbols_from_cache():
    """Test retrieving symbols from cache."""
    # Setup mock storage with cached symbols
    # Verify cache is used when use_cache=True

@pytest.mark.asyncio
async def test_find_document_symbols_from_lsp():
    """Test fetching fresh symbols from LSP."""
    # Setup mock LSP client with symbols
    # Verify LSP is called when use_cache=False

@pytest.mark.asyncio
async def test_find_document_symbols_caches_lsp_result():
    """Test that LSP results are cached."""
    # Fetch from LSP
    # Verify symbols are stored in cache

@pytest.mark.asyncio
async def test_find_document_symbols_handles_errors():
    """Test error handling in document symbols."""
    # Test repository not found
    # Test LSP failure
    # Test invalid file path
```

#### Phase 4: Implementation (Days 5-7)

1. **Day 5**: Implement core types and LSP client method
   - Create `document_symbol_types.py`
   - Extend `simple_lsp_client.py`
   - Run unit tests, ensure all pass

2. **Day 6**: Implement storage layer
   - Extend database schema
   - Implement hierarchy storage methods
   - Run storage tests, ensure all pass

3. **Day 7**: Implement CodebaseTools integration
   - Add tool handler
   - Wire up to MCP endpoint
   - Run integration tests, ensure all pass

#### Phase 5: End-to-End Testing (Day 8)

**`tests/test_document_symbols_e2e.py`**
```python
@pytest.mark.integration
async def test_document_symbols_full_workflow():
    """Test complete workflow from MCP request to response."""
    # 1. Create test repository with Python files
    # 2. Start MCP worker
    # 3. Send document symbol request via MCP
    # 4. Verify hierarchical response
    # 5. Verify symbols are cached
    # 6. Test cache invalidation on file change
```

### 5.2 Test Coverage Strategy

| Component | Target Coverage | Test Types |
|-----------|----------------|------------|
| `document_symbol_types.py` | 100% | Unit |
| `simple_lsp_client.get_document_symbols()` | 95% | Unit + Integration |
| `symbol_storage` hierarchy methods | 95% | Unit + Integration |
| `codebase_tools.find_document_symbols()` | 90% | Integration |
| Mock implementations | 100% | Unit |
| E2E workflow | 80% | Integration |

### 5.3 CI/CD Integration

```yaml
# .github/workflows/test-document-symbols.yml
name: Document Symbol Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      - run: pip install -r requirements.txt
      - run: pip install pytest-cov
      - run: |
          pytest tests/test_document_symbol*.py \
            --cov=document_symbol_types \
            --cov=simple_lsp_client \
            --cov=symbol_storage \
            --cov=codebase_tools \
            --cov-report=term-missing \
            --cov-fail-under=90
```

## 6. Risk Assessment

### 6.1 Technical Risks

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| **LSP Server Compatibility** | High | Medium | Test with both pylsp and pyright; implement fallbacks |
| **Database Migration Failure** | High | Low | Backup before migration; provide rollback script |
| **Performance Degradation** | Medium | Medium | Index parent_id; implement pagination for large files |
| **Memory Issues with Large Files** | Medium | Low | Maintain 10MB file size limit; stream processing |
| **Concurrent Access Issues** | Low | Low | SQLite WAL mode already enabled |

### 6.2 Testing Risks

| Risk | Mitigation |
|------|------------|
| **Incomplete Test Coverage** | Mandatory 90% coverage threshold |
| **Mock Drift** | Regular validation against real LSP servers |
| **Integration Test Flakiness** | Proper cleanup; isolated test environments |
| **Performance Test Gaps** | Add benchmarks for files with 1000+ symbols |

### 6.3 Mitigation Strategies

1. **Backward Compatibility**
   - Keep existing flat symbol methods
   - Add feature flag for hierarchy support
   - Gradual migration path

2. **Performance Optimization**
   ```python
   # Lazy loading for children
   class DocumentSymbol:
       @property
       def children(self):
           if self._children is None:
               self._children = self._load_children()
           return self._children
   ```

3. **Error Recovery**
   ```python
   # Fallback to flat symbols if hierarchy fails
   try:
       symbols = await lsp_client.get_document_symbols(uri)
   except Exception:
       # Fall back to existing symbol extraction
       flat_symbols = await self._extract_flat_symbols(file_path)
       return self._convert_flat_to_hierarchy(flat_symbols)
   ```

## 7. Testing Milestones and Quality Gates

### 7.1 Milestone Schedule

| Milestone | Completion Criteria | Due |
|-----------|-------------------|-----|
| **M1: Test Infrastructure** | All test files created, mocks implemented | Day 3 |
| **M2: Unit Tests Pass** | 100% of unit tests passing | Day 5 |
| **M3: Integration Tests Pass** | 100% of integration tests passing | Day 7 |
| **M4: Coverage Target Met** | ≥90% code coverage achieved | Day 8 |
| **M5: Performance Validated** | <100ms for 1000-symbol file | Day 9 |
| **M6: Documentation Complete** | API docs, test docs, user guide | Day 10 |

### 7.2 Quality Gates

**Gate 1: Pre-Implementation Review**
- [ ] All test cases documented
- [ ] Mock implementations reviewed
- [ ] Database migration tested on copy

**Gate 2: Implementation Complete**
- [ ] All tests passing (0 failures)
- [ ] No Python warnings
- [ ] Ruff/mypy checks pass

**Gate 3: Pre-Deployment**
- [ ] Load testing completed
- [ ] Security review passed
- [ ] Rollback procedure tested

### 7.3 Test Metrics Dashboard

```python
# tests/metrics/test_metrics.py
def generate_test_report():
    """Generate comprehensive test metrics."""
    return {
        "unit_tests": {
            "total": 45,
            "passed": 45,
            "coverage": 98.5
        },
        "integration_tests": {
            "total": 20,
            "passed": 20,
            "avg_duration": 1.2
        },
        "mocks": {
            "total_calls": 1250,
            "verification_passed": 1250
        },
        "performance": {
            "avg_response_time": 85,  # ms
            "p99_response_time": 120,
            "max_symbols_tested": 2500
        }
    }
```

## 8. Conclusion

This test-first design ensures robust implementation of the Document Symbol Hierarchy feature through:

1. **Comprehensive Test Coverage**: Every component tested before implementation
2. **Mock-First Development**: Complete mock infrastructure for isolated testing
3. **Incremental Implementation**: Phased approach with validation gates
4. **Performance Validation**: Benchmarks and load testing built-in
5. **Risk Mitigation**: Fallback strategies and error recovery

The design leverages existing patterns in the codebase while introducing minimal changes to the architecture. By following the test-first approach, we ensure high quality, maintainability, and confidence in the implementation.

## Appendices

### A. Sample Test Data

```python
# tests/fixtures/document_symbols.py
SAMPLE_PYTHON_FILE = '''
class Calculator:
    """A simple calculator class."""

    def __init__(self):
        self.result = 0

    def add(self, x: int, y: int) -> int:
        """Add two numbers."""
        return x + y

    class InnerClass:
        def inner_method(self):
            pass

def standalone_function():
    """A standalone function."""
    pass

CONSTANT = 42
'''

EXPECTED_SYMBOLS = [
    DocumentSymbol(
        name="Calculator",
        kind=SymbolKindLSP.Class,
        range=Range(1, 0, 13, 0),
        selection_range=Range(1, 6, 1, 16),
        detail="class",
        children=[
            DocumentSymbol(
                name="__init__",
                kind=SymbolKindLSP.Method,
                range=Range(4, 4, 5, 20),
                selection_range=Range(4, 8, 4, 16)
            ),
            # ... more methods
        ]
    ),
    # ... more symbols
]
```

### B. Migration Script

```sql
-- migration/001_add_document_symbols.sql
BEGIN TRANSACTION;

-- Add new columns for hierarchy support
ALTER TABLE symbols ADD COLUMN parent_id INTEGER REFERENCES symbols(id);
ALTER TABLE symbols ADD COLUMN detail TEXT;
ALTER TABLE symbols ADD COLUMN start_line INTEGER;
ALTER TABLE symbols ADD COLUMN start_character INTEGER;
ALTER TABLE symbols ADD COLUMN end_line INTEGER;
ALTER TABLE symbols ADD COLUMN end_character INTEGER;

-- Migrate existing data
UPDATE symbols SET
    start_line = line_number,
    start_character = column_number,
    end_line = line_number,
    end_character = column_number + LENGTH(name)
WHERE start_line IS NULL;

-- Create indexes
CREATE INDEX idx_symbols_parent_id ON symbols(parent_id);
CREATE INDEX idx_symbols_file_hierarchy ON symbols(file_path, parent_id);

COMMIT;
```

### C. Performance Benchmarks

```python
# tests/benchmarks/test_symbol_performance.py
import time
import pytest

@pytest.mark.benchmark
def test_large_file_performance(benchmark_fixture):
    """Benchmark symbol extraction for large files."""
    # Generate file with 1000+ symbols
    large_file = generate_large_python_file(
        classes=50,
        methods_per_class=20
    )

    start = time.time()
    symbols = extract_document_symbols(large_file)
    duration = time.time() - start

    assert len(symbols) > 1000
    assert duration < 0.1  # 100ms threshold
```