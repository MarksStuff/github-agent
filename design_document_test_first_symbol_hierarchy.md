# Test-First Design Document: Document Symbol Hierarchy Feature

## Executive Summary

This document presents a **test-first engineering approach** to implementing the Document Symbol Hierarchy (`textDocument/documentSymbol`) feature for the GitHub Agent MCP Server. The implementation will enable AI coding agents to instantly understand file structure without reading entire files, reducing token consumption by 10-100x while maintaining precise code navigation capabilities.

**Core Testing Philosophy:**
- **Test-Driven Development (TDD)**: Write tests before implementation
- **100% Test Coverage**: Every line of production code must be tested
- **Isolated Testing**: Use dependency injection and abstract interfaces for testability
- **No Mocking Libraries for Internal Code**: Create abstract base classes with test implementations
- **Automated Quality Gates**: CI/CD integration with strict test requirements

## Codebase Analysis

### Current LSP Architecture
The system uses a **subprocess-based LSP client** (`simple_lsp_client.py`) that spawns fresh `pylsp` processes for each request:

```python
# Current pattern - lines 46-53 of simple_lsp_client.py
proc = await asyncio.create_subprocess_exec(
    self.python_path, "-m", "pylsp",
    stdin=asyncio.subprocess.PIPE,
    stdout=asyncio.subprocess.PIPE,
    stderr=asyncio.subprocess.PIPE,
    cwd=self.workspace_root
)
```

**Key Findings:**
1. **Stateless Design**: Each LSP request creates a new process (no persistent connections)
2. **Protocol Implementation**: Full JSON-RPC 2.0 with proper header handling
3. **Error Handling**: Comprehensive cleanup with graceful/forced termination
4. **Factory Pattern**: `LSPClientFactory` type alias for dependency injection

### Testing Infrastructure Analysis

**Current Testing Patterns:**

1. **Abstract Interfaces Everywhere**:
   - `AbstractRepositoryManager` (repository_manager.py:41-68)
   - `AbstractSymbolStorage` (symbol_storage.py:88-100)
   - `AbstractSymbolExtractor` (python_symbol_extractor.py)
   - `AbstractRepositoryIndexer` (repository_indexer.py:61-75)

2. **Mock Implementations**:
   - `MockLSPClient` (tests/mocks/mock_lsp_client.py)
   - `MockSymbolExtractor` (tests/mocks/)
   - No use of `unittest.mock` for internal code

3. **Fixture Patterns** (tests/fixtures.py):
   - Factory fixtures for component creation
   - Temporary directories for isolation
   - Environment variable mocking for external resources

4. **Test Organization**:
   - Unit tests: `test_*.py`
   - Integration tests: `test_*_integration.py`
   - Real system tests: `test_real_lsp_integration.py`

### Symbol Storage Architecture

Current `Symbol` dataclass (symbol_storage.py:41-62):
```python
@dataclass
class Symbol:
    name: str
    kind: SymbolKind
    file_path: str
    line_number: int
    column_number: int
    repository_id: str
    docstring: str | None = None
```

**Gaps for Hierarchy Support:**
- No parent-child relationships
- No range information (start/end positions)
- No detail/signature information
- Flat structure only

## Integration Points

### Files Requiring Modification

| File | Changes | Test Strategy |
|------|---------|---------------|
| `simple_lsp_client.py` | Add `get_document_symbols()` method | Mock subprocess, test protocol handling |
| `symbol_storage.py` | Extend Symbol with hierarchy fields | Test backward compatibility |
| `codebase_tools.py` | Add `find_document_symbols()` method | Mock LSP client, test integration |
| `repository_indexer.py` | Track parent symbols during traversal | Test hierarchy extraction |
| Database Schema | Add hierarchy tables | Test migration and queries |

### New Files to Create

| File | Purpose | Test Coverage |
|------|---------|---------------|
| `document_symbol_types.py` | Domain models | 100% unit tests |
| `tests/test_document_symbols.py` | Comprehensive test suite | Self-testing |
| `tests/mocks/mock_document_symbol_lsp.py` | Test infrastructure | Used by other tests |
| `tests/fixtures/document_symbol_fixtures.py` | Test data | Reusable test scenarios |

## Detailed Design - Test-First Approach

### Phase 1: Test Infrastructure (Write Tests First)

#### 1.1 Domain Model Tests
```python
# tests/test_document_symbol_types.py
class TestDocumentSymbol:
    def test_create_symbol_with_all_fields(self):
        """Test creating a DocumentSymbol with complete data."""

    def test_create_nested_hierarchy(self):
        """Test parent-child relationships."""

    def test_convert_to_lsp_format(self):
        """Test serialization to LSP protocol format."""

    def test_convert_from_lsp_format(self):
        """Test deserialization from LSP response."""

    def test_range_validation(self):
        """Test that ranges are properly validated."""

    def test_backward_compatibility(self):
        """Test that new fields don't break existing Symbol usage."""
```

#### 1.2 Mock LSP Client for Document Symbols
```python
# tests/mocks/mock_document_symbol_lsp.py
class MockDocumentSymbolLSPClient:
    """Mock LSP client that returns predictable symbol hierarchies."""

    def __init__(self, test_responses: dict[str, list]):
        self.test_responses = test_responses
        self.call_history = []

    async def get_document_symbols(self, uri: str) -> list[dict]:
        self.call_history.append(('get_document_symbols', uri))
        return self.test_responses.get(uri, [])
```

#### 1.3 Integration Test Scenarios
```python
# tests/test_document_symbols_integration.py
class TestDocumentSymbolsIntegration:
    @pytest.fixture
    def sample_python_file(self, tmp_path):
        """Create a realistic Python file for testing."""
        file_content = '''
class UserAuthentication:
    """Handles user authentication."""

    def __init__(self):
        self.users = {}

    def login(self, username: str, password: str) -> bool:
        """Authenticate a user."""
        return self._validate_credentials(username, password)

    def _validate_credentials(self, user: str, pwd: str) -> bool:
        """Private method to validate."""
        return user in self.users

def standalone_function():
    """Module-level function."""
    pass
'''
        test_file = tmp_path / "auth.py"
        test_file.write_text(file_content)
        return test_file

    async def test_extract_complete_hierarchy(self, sample_python_file):
        """Test extracting full symbol hierarchy from real file."""

    async def test_cache_invalidation_on_file_change(self):
        """Test that cached symbols update when file changes."""

    async def test_performance_large_file(self):
        """Test performance with 1000+ line file."""
```

### Phase 2: Implementation with Continuous Testing

#### 2.1 Domain Models (Implement After Tests Pass)
```python
# document_symbol_types.py
from dataclasses import dataclass, field
from typing import Any

@dataclass
class SymbolRange:
    """Position range in a document."""
    start_line: int
    start_character: int
    end_line: int
    end_character: int

    def contains(self, line: int, character: int) -> bool:
        """Check if position is within this range."""
        # Implementation driven by tests

@dataclass
class DocumentSymbol:
    """Hierarchical symbol with LSP compatibility."""
    name: str
    detail: str | None
    kind: str  # SymbolKind value
    range: SymbolRange
    selection_range: SymbolRange
    children: list['DocumentSymbol'] = field(default_factory=list)
    parent_id: str | None = None

    @classmethod
    def from_lsp_response(cls, data: dict) -> 'DocumentSymbol':
        """Create from LSP protocol response."""
        # Implementation driven by test requirements

    def to_lsp_format(self) -> dict[str, Any]:
        """Convert to LSP protocol format."""
        # Implementation driven by test expectations
```

#### 2.2 LSP Client Extension (Test-Driven)
```python
# Addition to simple_lsp_client.py
async def get_document_symbols(
    self, file_uri: str, timeout: float = 10.0
) -> list[dict[str, Any]]:
    """Get document symbols with hierarchy.

    Test coverage requirements:
    - Valid file returns symbols
    - Non-existent file returns empty list
    - Syntax error file returns partial symbols
    - Timeout handling
    - Process cleanup verification
    """
    # Implementation guided by test failures
```

### Phase 3: Storage and Caching with Test Coverage

#### 3.1 Storage Schema Tests First
```python
# tests/test_symbol_storage_hierarchy.py
class TestHierarchicalSymbolStorage:
    def test_store_flat_symbols(self):
        """Test storing symbols without hierarchy."""

    def test_store_nested_symbols(self):
        """Test storing parent-child relationships."""

    def test_retrieve_by_parent(self):
        """Test querying children of a symbol."""

    def test_retrieve_document_structure(self):
        """Test reconstructing full document hierarchy."""

    def test_concurrent_access(self):
        """Test thread-safe operations."""
```

#### 3.2 Schema Implementation
```sql
-- New tables for hierarchy support
CREATE TABLE IF NOT EXISTS symbol_hierarchy (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol_id INTEGER NOT NULL,
    parent_id INTEGER,
    depth INTEGER NOT NULL,
    path TEXT NOT NULL,  -- Materialized path for efficient queries
    FOREIGN KEY (symbol_id) REFERENCES symbols(id),
    FOREIGN KEY (parent_id) REFERENCES symbols(id)
);

CREATE TABLE IF NOT EXISTS symbol_ranges (
    symbol_id INTEGER PRIMARY KEY,
    start_line INTEGER NOT NULL,
    start_character INTEGER NOT NULL,
    end_line INTEGER NOT NULL,
    end_character INTEGER NOT NULL,
    FOREIGN KEY (symbol_id) REFERENCES symbols(id)
);
```

### Phase 4: Integration Testing

#### 4.1 End-to-End Test Suite
```python
# tests/test_e2e_document_symbols.py
class TestEndToEndDocumentSymbols:
    async def test_mcp_request_to_response(self):
        """Test complete flow from MCP request to response."""
        # 1. Create test repository
        # 2. Add Python files with known structure
        # 3. Make MCP request for document symbols
        # 4. Verify response structure and content
        # 5. Verify caching behavior

    async def test_real_pylsp_integration(self):
        """Test with actual pylsp server."""
        # Skip if SKIP_REAL_LSP_TESTS is set
        # Use real pylsp to verify protocol compatibility
```

## Implementation Plan - Test-First Milestones

### Sprint 1: Foundation (Days 1-3)
**Testing Focus: 100% coverage before moving forward**

1. **Day 1: Test Infrastructure**
   - [ ] Write all domain model tests
   - [ ] Create mock LSP client for testing
   - [ ] Set up test fixtures and data
   - [ ] **Quality Gate**: All tests written, currently failing

2. **Day 2: Domain Implementation**
   - [ ] Implement DocumentSymbol classes
   - [ ] Make domain model tests pass
   - [ ] Add property-based testing with hypothesis
   - [ ] **Quality Gate**: Domain tests 100% passing

3. **Day 3: LSP Client Tests & Implementation**
   - [ ] Write LSP client method tests
   - [ ] Implement get_document_symbols()
   - [ ] Test error handling paths
   - [ ] **Quality Gate**: LSP tests passing, no uncovered lines

### Sprint 2: Integration (Days 4-6)
**Testing Focus: Component integration with mocked dependencies**

4. **Day 4: Storage Tests & Implementation**
   - [ ] Write storage hierarchy tests
   - [ ] Implement schema changes
   - [ ] Test migrations
   - [ ] **Quality Gate**: Storage tests passing

5. **Day 5: CodebaseTools Integration**
   - [ ] Write tool integration tests
   - [ ] Implement find_document_symbols()
   - [ ] Test MCP protocol handling
   - [ ] **Quality Gate**: Integration tests passing

6. **Day 6: End-to-End Testing**
   - [ ] Write E2E test scenarios
   - [ ] Test with real pylsp (optional)
   - [ ] Performance testing
   - [ ] **Quality Gate**: All tests green, >95% coverage

### Sprint 3: Hardening (Days 7-8)
**Testing Focus: Edge cases and production readiness**

7. **Day 7: Edge Cases & Error Scenarios**
   - [ ] Malformed Python files
   - [ ] Huge files (>10MB)
   - [ ] Concurrent requests
   - [ ] Process failures
   - [ ] **Quality Gate**: All edge cases handled

8. **Day 8: Production Validation**
   - [ ] Load testing
   - [ ] Memory leak testing
   - [ ] CI/CD pipeline integration
   - [ ] Documentation tests
   - [ ] **Quality Gate**: Production ready

## Risk Assessment - Testing Perspective

### Technical Risks

| Risk | Impact | Mitigation | Test Strategy |
|------|--------|------------|---------------|
| LSP protocol incompatibility | High | Test with multiple pylsp versions | Version matrix testing |
| Performance degradation | Medium | Benchmark tests in CI | Automated performance regression tests |
| Memory leaks in subprocess | Medium | Process cleanup tests | Resource monitoring in tests |
| Schema migration failures | High | Rollback tests | Test both upgrade and downgrade paths |
| Concurrent access issues | Medium | Thread safety tests | Stress testing with multiple workers |

### Quality Assurance Risks

| Risk | Mitigation |
|------|------------|
| Insufficient test coverage | Enforce 95% minimum coverage in CI |
| Test brittleness | Use test fixtures and factories |
| Slow test execution | Parallel test execution, mock heavy operations |
| Testing blind spots | Code review focus on test quality |

## Testing Metrics & Quality Gates

### Required Metrics
- **Code Coverage**: ≥95% (lines, branches, statements)
- **Test Execution Time**: <30 seconds for unit tests
- **Test Reliability**: 0% flakiness tolerance
- **Mutation Testing**: ≥80% mutant kill rate

### CI/CD Integration
```yaml
# .github/workflows/test-symbol-hierarchy.yml
name: Document Symbol Tests
on: [push, pull_request]

jobs:
  test:
    steps:
      - name: Run unit tests
        run: pytest tests/test_document_symbols*.py -v --cov=document_symbol_types --cov-report=term-missing

      - name: Run integration tests
        run: pytest tests/test_*integration*.py -v

      - name: Check coverage
        run: |
          coverage report --fail-under=95

      - name: Run mutation tests
        run: mutmut run --paths document_symbol_types.py
```

## Test Data Management

### Fixture Categories
1. **Minimal**: Single function/class
2. **Typical**: Standard module with 5-10 symbols
3. **Complex**: Nested classes, decorators, metaclasses
4. **Edge Cases**: Unicode, very long names, deep nesting
5. **Performance**: 1000+ symbols

### Test Data Generation
```python
# tests/fixtures/document_symbol_fixtures.py
@pytest.fixture
def symbol_hierarchy_factory():
    """Factory for creating test symbol hierarchies."""
    def create_hierarchy(depth=3, width=3):
        # Programmatically generate test hierarchies
        pass
    return create_hierarchy
```

## Monitoring & Observability

### Test Observability
- Test execution metrics in CI
- Coverage trends over time
- Performance regression detection
- Flaky test detection and reporting

### Production Monitoring
- Symbol extraction success rates
- LSP request latencies
- Cache hit ratios
- Memory usage patterns

## Success Criteria

### Testing Success Metrics
1. **Coverage**: ≥95% across all new code
2. **Performance**: <100ms for typical files
3. **Reliability**: Zero test failures in 100 consecutive runs
4. **Maintainability**: Test-to-code ratio ≥ 2:1

### Feature Success Metrics
1. **Token Reduction**: 90% fewer tokens for file understanding
2. **Agent Efficiency**: 50% reduction in file read operations
3. **Accuracy**: 100% symbol extraction accuracy
4. **Compatibility**: Works with all Python 3.8+ code

## Conclusion

This test-first design ensures that the Document Symbol Hierarchy feature will be:
- **Robust**: Comprehensive test coverage prevents regressions
- **Maintainable**: Clear test specifications document behavior
- **Performant**: Performance tests prevent degradation
- **Reliable**: Extensive error handling validated by tests

The implementation follows TDD principles, ensuring that every line of code has a purpose defined by a failing test, resulting in a lean, well-tested feature that integrates seamlessly with the existing codebase.