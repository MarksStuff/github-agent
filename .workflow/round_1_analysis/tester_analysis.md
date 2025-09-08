# Tester Analysis

**Feature**: # Feature: 1. Document Symbol Hierarchy
**Date**: 2025-09-07T17:48:59.032883
**Agent**: tester

## Analysis

Now, based on my analysis of the codebase testing patterns, here's the comprehensive testing specification for the Document Symbol Hierarchy feature:

## TESTING SPECIFICATION: Document Symbol Hierarchy

### 1. TEST STRATEGY ANALYSIS

**Testing Approach**: Following existing abstract base + mock implementation pattern
- Abstract base class for symbol hierarchy provider
- Mock implementation for unit tests
- Integration tests with real LSP client
- Storage persistence tests for cached symbols

**Test Categories**:
- **Unit tests**: Symbol extraction, hierarchy building, cache invalidation
- **Integration tests**: LSP documentSymbol interaction, storage integration
- **End-to-end tests**: Complete workflow from file change to symbol retrieval

**Mock Strategy**: Create mock classes inheriting from abstract bases (pattern from `tests/mocks/`)
- `MockDocumentSymbolProvider` - Returns predefined symbol hierarchies
- `MockHierarchicalSymbolStorage` - In-memory storage with parent-child relationships
- Reuse existing: `MockLSPClient`, `MockSymbolStorage`, `MockSymbolExtractor`

**Test Organization**:
- `tests/test_document_symbol_hierarchy.py` - Core unit tests
- `tests/test_lsp_document_symbol_integration.py` - LSP integration tests
- `tests/mocks/mock_document_symbol_provider.py` - Mock implementation

### 2. REQUIRED TEST FILES

**Unit Test Files**:
- `tests/test_document_symbol_hierarchy.py`
- `tests/test_hierarchical_symbol_storage.py`

**Integration Test Files**:
- `tests/test_lsp_document_symbol_integration.py`
- `tests/test_symbol_hierarchy_caching.py`

**Mock Files**:
- `tests/mocks/mock_document_symbol_provider.py`
- `tests/mocks/mock_hierarchical_symbol_storage.py`

**Test Dependencies**: Reuse from existing infrastructure:
- `tests/fixtures.py` - extractor, storage, temp_repo_path fixtures
- `tests/conftest.py` - SymbolStorageCloser context manager
- `tests/mocks/mock_lsp_client.py` - Extend with documentSymbol method

### 3. SPECIFIC TEST SCENARIOS

**Happy Path Tests**:
```python
def test_extract_class_hierarchy()  # Class with methods and properties
def test_extract_nested_classes()   # Inner classes with their methods
def test_extract_module_functions() # Module-level functions and variables
def test_preserve_line_ranges()     # Accurate start/end positions
def test_symbol_detail_strings()    # Signatures and type hints preserved
```

**Error Handling Tests**:
```python
def test_invalid_file_path()        # Non-existent file
def test_syntax_error_recovery()    # File with syntax errors
def test_empty_file_handling()      # Empty or whitespace-only files
def test_lsp_timeout_handling()     # LSP server timeout
def test_cache_corruption_recovery()# Corrupted cache data
```

**Edge Cases**:
```python
def test_deeply_nested_symbols()    # 5+ levels of nesting
def test_large_file_performance()   # 10000+ line files
def test_unicode_symbol_names()     # Non-ASCII identifiers
def test_overlapping_ranges()       # Malformed symbol ranges
def test_concurrent_cache_updates() # Race conditions
```

**Integration Scenarios**:
```python
def test_file_modification_invalidates_cache()
def test_symbol_hierarchy_with_references()
def test_cross_file_symbol_relationships()
def test_workspace_symbol_aggregation()
```

### 4. MOCK SPECIFICATIONS

**MockDocumentSymbolProvider**:
```python
class MockDocumentSymbolProvider(AbstractDocumentSymbolProvider):
    def __init__(self):
        self.symbol_trees = {}  # file_path -> symbol hierarchy
        self.call_count = 0
        
    def get_document_symbols(self, file_path: str) -> list[DocumentSymbol]:
        self.call_count += 1
        return self.symbol_trees.get(file_path, [])
        
    def set_mock_symbols(self, file_path: str, symbols: list[DocumentSymbol]):
        self.symbol_trees[file_path] = symbols
```

**MockHierarchicalSymbolStorage** (extends MockSymbolStorage):
```python
class MockHierarchicalSymbolStorage(MockSymbolStorage):
    def __init__(self):
        super().__init__()
        self.symbol_hierarchies = {}  # file_path -> tree structure
        self.invalidation_log = []
        
    def store_symbol_hierarchy(self, file_path: str, symbols: list[DocumentSymbol]):
        self.symbol_hierarchies[file_path] = symbols
        
    def invalidate_file_symbols(self, file_path: str):
        self.invalidation_log.append(file_path)
        if file_path in self.symbol_hierarchies:
            del self.symbol_hierarchies[file_path]
```

**Extended MockLSPClient**:
```python
# In mock_lsp_client.py, add:
async def get_document_symbols(self, uri: str) -> list[dict] | None:
    """Mock documentSymbol method."""
    return self.mock_document_symbols.get(uri, [])
```

### 5. TEST IMPLEMENTATION DETAILS

**Test Method Names** (following existing patterns):
```python
# Unit tests
test_document_symbol_creation()
test_symbol_kind_mapping()
test_range_calculation()
test_hierarchy_building()
test_children_relationship()

# Integration tests
test_lsp_document_symbol_request()
test_symbol_cache_hit_ratio()
test_invalidation_on_file_change()
test_batch_symbol_extraction()

# Error tests
test_malformed_lsp_response()
test_connection_failure_fallback()
test_partial_symbol_extraction()
```

**Test Data Examples**:
```python
SAMPLE_PYTHON_FILE = """
class UserAuthentication:
    '''Handles user authentication.'''
    
    def __init__(self):
        self.users = {}
        
    def login(self, username: str, password: str) -> bool:
        '''Authenticate user.'''
        return self._verify(username, password)
        
    def _verify(self, user: str, pwd: str) -> bool:
        return user in self.users
        
    class Session:
        '''Nested session handler.'''
        def __init__(self, token: str):
            self.token = token
"""

EXPECTED_HIERARCHY = [
    DocumentSymbol(
        name="UserAuthentication",
        kind=SymbolKind.CLASS,
        range=Range(start=(1, 0), end=(15, 0)),
        children=[
            DocumentSymbol(name="__init__", kind=SymbolKind.METHOD, ...),
            DocumentSymbol(name="login", kind=SymbolKind.METHOD, ...),
            DocumentSymbol(name="_verify", kind=SymbolKind.METHOD, ...),
            DocumentSymbol(
                name="Session",
                kind=SymbolKind.CLASS,
                children=[
                    DocumentSymbol(name="__init__", kind=SymbolKind.METHOD, ...)
                ]
            )
        ]
    )
]
```

**Assertions**:
```python
# Hierarchy structure
assert len(symbols) == 1
assert symbols[0].name == "UserAuthentication"
assert len(symbols[0].children) == 4

# Range accuracy
assert symbols[0].range.start.line == 1
assert symbols[0].range.end.line == 15

# Cache behavior
assert storage.get_cache_hits() == expected_hits
assert provider.call_count == expected_calls

# Performance
assert extraction_time < 0.1  # 100ms for 1000-line file
```

**Coverage Goals**:
- Line coverage: 95%+ for new code
- Branch coverage: 90%+ for error paths
- Integration coverage: All LSP methods tested
- Mock coverage: 100% of abstract methods implemented

This testing strategy follows the established patterns in the codebase, emphasizing:
1. Abstract base classes with mock implementations
2. Comprehensive error handling tests
3. Integration with existing infrastructure
4. Performance validation for large files

---
*This analysis was generated by the tester agent as part of the multi-agent workflow.*
