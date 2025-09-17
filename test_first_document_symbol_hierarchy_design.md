# Test-Driven Design Document: Document Symbol Hierarchy Feature

## Executive Summary

This design proposes implementing the `textDocument/documentSymbol` LSP feature through a **test-first approach** that leverages the existing codebase's abstract interfaces and dependency injection patterns. The implementation will extend the current symbol extraction capabilities to maintain hierarchical relationships while ensuring comprehensive test coverage at every layer.

Key approach: Build from the test layer up, using mock-driven development to ensure every component is independently testable before integration, minimizing risk and maximizing code quality.

## Codebase Analysis

### Existing Testing Infrastructure

The codebase demonstrates mature testing patterns:

1. **Abstract Interface Pattern** (`symbol_storage.py:88-201`, `repository_manager.py:41-68`)
   - All major components have abstract base classes
   - Enables easy mock creation for testing

2. **Mock Implementation Strategy** (`tests/mocks/`)
   - Dedicated mock implementations for all core components
   - MockSymbolStorage, MockLSPClient, MockSymbolExtractor already exist
   - No use of unittest.mock for internal components (good practice)

3. **Test Organization**
   - Unit tests for individual components
   - Integration tests for complex interactions
   - Comprehensive fixture support via conftest.py

4. **Dependency Injection** (`codebase_tools.py:69-86`)
   ```python
   def __init__(self, repository_manager: AbstractRepositoryManager,
                symbol_storage: AbstractSymbolStorage,
                lsp_client_factory: LSPClientFactory)
   ```

### Relevant Components for Extension

1. **Symbol Model** (`symbol_storage.py:41-62`)
   - Current Symbol dataclass lacks hierarchy support
   - Need to add parent_id and children fields

2. **PythonSymbolExtractor** (`python_symbol_extractor.py:33-200`)
   - Already tracks scope_stack for context
   - Can be extended to build hierarchy

3. **SimpleLSPClient** (`simple_lsp_client.py:14-300`)
   - Subprocess-based LSP communication
   - Need to add document_symbols method

4. **CodebaseTools** (`codebase_tools.py:57-452`)
   - Central integration point for MCP tools
   - Will expose new document_symbols tool

## Integration Points

### Primary Integration Points

1. **LSP Protocol Layer** (`lsp_constants.py:63`)
   - DOCUMENT_SYMBOLS constant already defined
   - Need to implement handler in SimpleLSPClient

2. **Symbol Storage Layer** (`symbol_storage.py`)
   - Extend AbstractSymbolStorage with hierarchy methods
   - Update SQLiteSymbolStorage implementation
   - Maintain backward compatibility

3. **MCP Tool Registration** (`mcp_worker.py:465-478`)
   - Register new document_symbols tool
   - Integrate with CodebaseTools.get_tools()

4. **Symbol Extraction** (`repository_indexer.py:124-200`)
   - Enhance extraction to preserve parent-child relationships
   - Store hierarchy in database

## Detailed Design

### Test-First Implementation Strategy

#### Phase 1: Test Infrastructure Setup

**1.1 Create Mock Hierarchy Components**
```python
# tests/mocks/mock_hierarchical_symbol_storage.py
class MockHierarchicalSymbolStorage(AbstractSymbolStorage):
    def get_document_symbols(self, file_path: str, repository_id: str) -> list[HierarchicalSymbol]:
        """Return mock hierarchical symbols for testing."""
        pass
```

**1.2 Define Test Fixtures**
```python
# tests/conftest.py additions
@pytest.fixture
def hierarchical_symbols():
    """Fixture providing sample hierarchical symbol structure."""
    return [
        HierarchicalSymbol(
            name="TestClass",
            kind=SymbolKind.CLASS,
            range=Range(start=Position(10, 0), end=Position(50, 0)),
            children=[
                HierarchicalSymbol(
                    name="__init__",
                    kind=SymbolKind.METHOD,
                    range=Range(start=Position(11, 4), end=Position(15, 4))
                )
            ]
        )
    ]
```

#### Phase 2: Model Layer with Tests

**2.1 Enhanced Symbol Model**
```python
# symbol_storage.py additions
@dataclass
class HierarchicalSymbol:
    """Symbol with hierarchical structure for document symbols."""
    name: str
    kind: SymbolKind
    range: Range
    selection_range: Range | None = None
    detail: str | None = None
    children: list['HierarchicalSymbol'] = field(default_factory=list)

    def to_lsp_format(self) -> dict[str, Any]:
        """Convert to LSP DocumentSymbol format."""
        pass
```

**2.2 Test Coverage for Model**
```python
# tests/test_hierarchical_symbol.py
class TestHierarchicalSymbol:
    def test_creation(self):
        """Test creating hierarchical symbol."""

    def test_nested_children(self):
        """Test multi-level nesting."""

    def test_lsp_format_conversion(self):
        """Test conversion to LSP format."""

    def test_serialization(self):
        """Test JSON serialization."""
```

#### Phase 3: Storage Layer with Tests

**3.1 Abstract Interface Extension**
```python
# symbol_storage.py
class AbstractSymbolStorage(ABC):
    # ... existing methods ...

    @abstractmethod
    def get_document_symbols(self, file_path: str, repository_id: str) -> list[HierarchicalSymbol]:
        """Get hierarchical symbols for a document."""
        pass

    @abstractmethod
    def store_document_symbols(self, file_path: str, repository_id: str,
                             symbols: list[HierarchicalSymbol]) -> None:
        """Store hierarchical symbols for a document."""
        pass
```

**3.2 Storage Tests First**
```python
# tests/test_hierarchical_symbol_storage.py
class TestHierarchicalSymbolStorage:
    def test_store_and_retrieve_hierarchy(self, storage):
        """Test storing and retrieving symbol hierarchy."""

    def test_update_document_symbols(self, storage):
        """Test updating existing document symbols."""

    def test_delete_document_symbols(self, storage):
        """Test deleting document symbols."""

    def test_complex_nested_hierarchy(self, storage):
        """Test deeply nested class/function structures."""
```

#### Phase 4: Extraction Layer with Tests

**4.1 Test-Driven Extractor Enhancement**
```python
# tests/test_hierarchical_extractor.py
class TestHierarchicalExtraction:
    def test_extract_class_hierarchy(self):
        """Test extracting class with methods."""
        source = '''
        class MyClass:
            def method1(self):
                pass
            def method2(self):
                pass
        '''
        symbols = extractor.extract_hierarchical(source)
        assert len(symbols) == 1
        assert len(symbols[0].children) == 2

    def test_extract_nested_functions(self):
        """Test nested function extraction."""

    def test_extract_nested_classes(self):
        """Test nested class extraction."""
```

**4.2 Implementation After Tests**
```python
# python_symbol_extractor.py enhancement
class PythonSymbolExtractor:
    def extract_hierarchical(self, source: str, file_path: str,
                           repository_id: str) -> list[HierarchicalSymbol]:
        """Extract symbols with hierarchy preserved."""
        # Implementation guided by tests
```

#### Phase 5: LSP Integration with Tests

**5.1 LSP Client Tests**
```python
# tests/test_lsp_document_symbols.py
class TestLSPDocumentSymbols:
    @pytest.mark.asyncio
    async def test_get_document_symbols(self, mock_lsp_client):
        """Test getting document symbols via LSP."""

    @pytest.mark.asyncio
    async def test_handle_empty_document(self, mock_lsp_client):
        """Test handling empty documents."""

    @pytest.mark.asyncio
    async def test_handle_syntax_errors(self, mock_lsp_client):
        """Test handling files with syntax errors."""
```

**5.2 SimpleLSPClient Extension**
```python
# simple_lsp_client.py
async def get_document_symbols(self, file_uri: str,
                              timeout: float = 10.0) -> list[dict[str, Any]]:
    """Get document symbols for a file."""
    # Implementation with proper subprocess handling
```

#### Phase 6: Integration Tests

**6.1 End-to-End Test Suite**
```python
# tests/test_document_symbols_integration.py
class TestDocumentSymbolsIntegration:
    @pytest.mark.integration
    def test_full_workflow(self, temp_repository):
        """Test complete document symbols workflow."""
        # 1. Create test Python file
        # 2. Index repository
        # 3. Request document symbols
        # 4. Verify hierarchy

    def test_performance_large_file(self):
        """Test performance with large files."""

    def test_concurrent_requests(self):
        """Test handling concurrent symbol requests."""
```

### Database Schema Updates

```sql
-- New table for hierarchical symbols
CREATE TABLE IF NOT EXISTS document_symbols (
    id INTEGER PRIMARY KEY,
    file_path TEXT NOT NULL,
    repository_id TEXT NOT NULL,
    symbol_data JSON NOT NULL,  -- Stores hierarchical structure
    file_hash TEXT NOT NULL,     -- For cache invalidation
    indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(file_path, repository_id)
);

CREATE INDEX idx_document_symbols_repo ON document_symbols(repository_id);
CREATE INDEX idx_document_symbols_file ON document_symbols(file_path);
```

### Error Handling and Edge Cases

**Test-Driven Error Scenarios:**

1. **Syntax Errors**
   - Test: `test_handle_syntax_error_gracefully()`
   - Implementation: Return partial symbols if possible

2. **Large Files**
   - Test: `test_handle_large_file_timeout()`
   - Implementation: Streaming symbol extraction

3. **Circular Dependencies**
   - Test: `test_handle_circular_imports()`
   - Implementation: Cycle detection in hierarchy

4. **Unicode and Encoding**
   - Test: `test_handle_various_encodings()`
   - Implementation: Robust encoding detection

## Implementation Plan

### Phase 1: Test Infrastructure (Week 1)
- [ ] Create comprehensive test fixtures
- [ ] Set up mock hierarchical storage
- [ ] Define test scenarios and edge cases
- [ ] Create performance benchmarks

### Phase 2: Core Models (Week 1)
- [ ] Write HierarchicalSymbol tests
- [ ] Implement HierarchicalSymbol model
- [ ] Write Range/Position tests
- [ ] Implement Range/Position models

### Phase 3: Storage Layer (Week 2)
- [ ] Write storage interface tests
- [ ] Implement mock storage
- [ ] Write SQLite storage tests
- [ ] Implement SQLite storage
- [ ] Add migration scripts with tests

### Phase 4: Extraction (Week 2)
- [ ] Write extraction tests for all Python constructs
- [ ] Implement hierarchical extraction
- [ ] Test edge cases (decorators, metaclasses)
- [ ] Performance optimization with tests

### Phase 5: LSP Integration (Week 3)
- [ ] Write LSP client tests
- [ ] Implement document symbols in SimpleLSPClient
- [ ] Test timeout and error handling
- [ ] Integration tests with real pylsp

### Phase 6: MCP Tool Integration (Week 3)
- [ ] Write MCP tool tests
- [ ] Implement document_symbols tool
- [ ] End-to-end integration tests
- [ ] Performance and load tests

### Phase 7: CI/CD Integration (Week 4)
- [ ] Set up test coverage requirements (>90%)
- [ ] Add performance regression tests
- [ ] Configure automated test runs
- [ ] Add mutation testing

## Testing Strategy

### Test Coverage Goals
- **Unit Tests**: 95% coverage for new code
- **Integration Tests**: Cover all major workflows
- **Performance Tests**: Sub-100ms response for files <1000 lines
- **Mutation Testing**: 80% mutation score

### Test Pyramid
```
         /\
        /  \  E2E Tests (10%)
       /    \
      /------\ Integration Tests (20%)
     /        \
    /----------\ Unit Tests (70%)
```

### Quality Gates
1. **Pre-commit**: All unit tests pass
2. **PR Checks**:
   - All tests pass
   - Coverage > 90%
   - No performance regressions
3. **Deployment**:
   - Integration tests pass
   - Load tests pass

### Mock Strategy

**Use Existing Patterns:**
```python
# Good - follows codebase pattern
class MockHierarchicalStorage(AbstractSymbolStorage):
    def __init__(self):
        self._symbols = {}

# Avoid - codebase doesn't use unittest.mock for internal components
@patch('symbol_storage.SQLiteSymbolStorage')
def test_something(mock_storage):
    pass
```

## Risk Assessment

### Technical Risks

1. **Risk**: Performance degradation with deep hierarchies
   - **Mitigation**: Test-driven performance benchmarks
   - **Tests**: `test_performance_deep_nesting()`

2. **Risk**: Memory issues with large files
   - **Mitigation**: Streaming extraction with tests
   - **Tests**: `test_memory_usage_large_files()`

3. **Risk**: LSP server compatibility issues
   - **Mitigation**: Test against multiple LSP servers
   - **Tests**: `test_pylsp_compatibility()`, `test_pyright_compatibility()`

### Testing Risks

1. **Risk**: Incomplete test coverage leading to bugs
   - **Mitigation**: Mutation testing to verify test quality
   - **Validation**: Achieve 80% mutation score

2. **Risk**: Flaky integration tests
   - **Mitigation**: Proper test isolation and cleanup
   - **Validation**: Run tests 100x to ensure stability

## Success Criteria

### Functional Requirements
- [ ] Document symbols returned within 100ms for average files
- [ ] Correct hierarchy for all Python constructs
- [ ] Graceful handling of syntax errors
- [ ] Cache invalidation on file changes

### Quality Requirements
- [ ] 95% unit test coverage
- [ ] 90% integration test coverage
- [ ] All tests pass in CI/CD
- [ ] No memory leaks in 24-hour stress test
- [ ] Documentation with test examples

### Performance Benchmarks
```python
# tests/benchmarks/test_document_symbols_performance.py
def test_performance_small_file():
    """<100 lines should complete in <50ms"""

def test_performance_medium_file():
    """<1000 lines should complete in <100ms"""

def test_performance_large_file():
    """<10000 lines should complete in <500ms"""
```

## Conclusion

This test-first design ensures high-quality implementation of the document symbols feature by:

1. **Starting with tests** - Every component has tests before implementation
2. **Using existing patterns** - Leveraging abstract interfaces and DI
3. **Ensuring testability** - All components independently testable
4. **Maintaining quality** - Comprehensive coverage and performance tests
5. **Minimizing risk** - Issues caught early through TDD

The approach aligns with the codebase's existing testing philosophy while adding a critical LSP feature for enhanced code navigation.