# LangGraph Workflow Tests

Comprehensive test suite for the LangGraph-based multi-agent workflow implementation.

## Test Structure

```
tests/
├── __init__.py                 # Test package init
├── conftest.py                # Pytest fixtures and configuration
├── test_runner.py             # Custom test runner with coverage
├── test_workflow_phases.py    # Unit tests for workflow phases
├── test_github_integration.py # GitHub operations tests
├── test_agent_personas.py     # Agent behavior tests
├── test_config.py             # Configuration and routing tests
├── test_cli.py                # CLI and interactive mode tests
├── test_integration.py        # End-to-end integration tests
└── README.md                  # This file
```

## Test Categories

### Unit Tests
- **test_workflow_phases.py**: Tests individual workflow phases (Phase 0-3)
- **test_agent_personas.py**: Tests agent implementations and behaviors
- **test_config.py**: Tests configuration management and routing logic
- **test_cli.py**: Tests command-line interface and argument parsing

### Integration Tests
- **test_github_integration.py**: Tests GitHub API integration and PR workflows
- **test_integration.py**: End-to-end workflow testing with mocked dependencies

## Design Principles

### Dependency Injection Pattern
Following CLAUDE.md guidelines, we use **abstract base classes** with mock implementations rather than unittest.mock for our own objects:

```python
# interfaces.py - Abstract base classes
class GitHubInterface(ABC):
    @abstractmethod
    async def create_pull_request(self, title: str, body: str) -> int:
        pass

# mocks.py - Mock implementations  
class MockGitHub(GitHubInterface):
    async def create_pull_request(self, title: str, body: str) -> int:
        # Mock implementation
        return 123

# Test usage
workflow = MultiAgentWorkflow(github=MockGitHub())
```

### Mock Usage Guidelines
- **unittest.mock**: Only for external dependencies (file system, HTTP requests)
- **Custom mocks**: For our own classes using dependency injection
- **Real objects**: Used in integration tests where beneficial

## Running Tests

### Basic Test Execution

```bash
# Run all tests
python -m pytest

# Run specific test file
python -m pytest tests/test_workflow_phases.py

# Run specific test method
python -m pytest tests/test_workflow_phases.py::TestWorkflowPhases::test_phase_0_code_context_extraction

# Run with verbose output
python -m pytest -v

# Run tests matching pattern
python -m pytest -k "test_workflow"
```

### Using Custom Test Runner

```bash
# Run all tests with coverage
python tests/test_runner.py

# Run specific module
python tests/test_runner.py --module workflow_phases

# Show test summary
python tests/test_runner.py --summary

# Run with coverage reporting
python tests/test_runner.py --coverage
```

### Test Categories

```bash
# Run only unit tests (fast)
python -m pytest -m "not integration and not slow"

# Run integration tests
python -m pytest -m integration

# Run all except slow tests
python -m pytest -m "not slow"

# Run GitHub-dependent tests
python -m pytest -m github
```

## Coverage Requirements

- **Minimum Coverage**: 80% (configured in pytest.ini)
- **Target Coverage**: 95%+ for core workflow logic
- **Coverage Reports**: Generated in `htmlcov/` directory

```bash
# Generate coverage report
python -m pytest --cov=langgraph_workflow --cov-report=html

# View coverage
open htmlcov/index.html
```

## Test Data and Fixtures

### Common Fixtures (conftest.py)
- `temp_directory`: Temporary directory for file operations
- `repo_path`: Mock repository path
- `thread_id`: Standard test thread ID
- `mock_dependencies`: Complete set of mocked dependencies
- `sample_feature_description`: Standard test feature
- `sample_prd_content`: Sample PRD for feature extraction tests

### Mock Dependencies
- **MockModel**: Language model responses
- **MockGitHub**: GitHub API operations
- **MockAgent**: Agent analysis and review
- **MockCodebaseAnalyzer**: Repository analysis
- **MockFileSystem**: File operations
- **MockGit**: Git operations
- **MockTestRunner**: Test execution
- **MockArtifactManager**: Artifact storage

## Writing New Tests

### Test Structure Template

```python
import unittest
from unittest.mock import patch
from ..mocks import create_mock_dependencies
from ..workflow import MultiAgentWorkflow

class TestNewFeature(unittest.IsolatedAsyncioTestCase):
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_deps = create_mock_dependencies("test-thread")
        self.workflow = MultiAgentWorkflow("/tmp/repo", "test-thread")
    
    async def test_new_functionality(self):
        """Test description."""
        # Arrange
        # ... setup test data
        
        # Act
        result = await self.workflow.new_method()
        
        # Assert
        self.assertEqual(result["status"], "success")
```

### Testing Async Code

```python
class TestAsyncFeature(unittest.IsolatedAsyncioTestCase):
    
    async def test_async_method(self):
        """Test async functionality."""
        result = await async_function()
        self.assertIsNotNone(result)
```

### Testing Error Handling

```python
async def test_error_handling(self):
    """Test error scenarios."""
    with self.assertRaises(ValueError) as context:
        await function_that_should_fail()
    
    self.assertIn("expected error message", str(context.exception))
```

## Test Best Practices

### 1. Test Independence
- Each test should be independent and not rely on other tests
- Use `setUp()` and `tearDown()` for test isolation
- Clean up temporary files and resources

### 2. Descriptive Test Names
```python
# Good
def test_phase_0_extracts_code_context_with_claude_model(self):

# Bad  
def test_phase_0(self):
```

### 3. Arrange-Act-Assert Pattern
```python
async def test_feature(self):
    # Arrange - Set up test data
    workflow = MultiAgentWorkflow(repo_path, thread_id)
    state = create_initial_state()
    
    # Act - Execute the functionality
    result = await workflow.execute_phase(state)
    
    # Assert - Verify results
    self.assertEqual(result["status"], "success")
```

### 4. Mock External Dependencies
```python
@patch('requests.get')
async def test_api_call(self, mock_get):
    mock_get.return_value.json.return_value = {"result": "success"}
    # ... test code
```

### 5. Test Edge Cases
- Empty inputs
- Large inputs  
- Network failures
- Timeout scenarios
- Invalid configurations

## Debugging Tests

### Running with Debug Output
```bash
# Show print statements
python -m pytest -s

# Show detailed failure info
python -m pytest --tb=long

# Stop on first failure
python -m pytest -x

# Start debugger on failure
python -m pytest --pdb
```

### Logging in Tests
```python
import logging
logging.basicConfig(level=logging.DEBUG)

async def test_with_logging(self):
    logger = logging.getLogger(__name__)
    logger.info("Test starting")
    # ... test code
```

## Continuous Integration

### GitHub Actions Integration
Tests are designed to run in CI environments:

```yaml
# .github/workflows/test.yml
- name: Run tests
  run: |
    python -m pytest --cov=langgraph_workflow
    python tests/test_runner.py --coverage
```

### Environment Variables for CI
```bash
# Required for GitHub integration tests
export GITHUB_TOKEN=dummy_token_for_tests

# Optional for model tests
export ANTHROPIC_API_KEY=dummy_key_for_tests
export OLLAMA_BASE_URL=http://mock-ollama:11434
```

## Performance Testing

### Benchmarking
```python
async def test_performance_benchmark(self):
    """Test execution time stays within bounds."""
    import time
    
    start = time.time()
    result = await expensive_operation()
    duration = time.time() - start
    
    self.assertLess(duration, 5.0, "Operation took too long")
```

### Memory Usage
```python
async def test_memory_usage(self):
    """Test memory consumption."""
    import sys
    
    state = create_large_state()
    size = sys.getsizeof(state)
    
    self.assertLess(size, 1024*1024, "State too large (>1MB)")
```

## Test Data Management

### Fixture Files
Store test data in `tests/fixtures/`:
```
tests/fixtures/
├── sample_prd.md
├── sample_code_context.md
├── sample_synthesis.md
└── sample_responses.json
```

### Factory Pattern
```python
# tests/factories.py
def create_workflow_state(**overrides):
    """Factory for creating test workflow states."""
    defaults = {
        "thread_id": "test-thread",
        "feature_description": "Test feature",
        "current_phase": WorkflowPhase.PHASE_0_CODE_CONTEXT,
        # ... other defaults
    }
    defaults.update(overrides)
    return WorkflowState(**defaults)
```

## Troubleshooting

### Common Issues

1. **Import Errors**: Ensure `PYTHONPATH` includes parent directory
2. **Async Test Failures**: Use `unittest.IsolatedAsyncioTestCase`
3. **Mock Conflicts**: Reset mocks between tests
4. **Temp File Cleanup**: Use context managers for temporary resources

### Debug Commands
```bash
# List all tests
python -m pytest --collect-only

# Run tests with profiling
python -m pytest --profile-svg

# Run specific failed tests
python -m pytest --lf

# Show slowest tests
python -m pytest --durations=10
```

## Contributing

When adding new tests:
1. Follow the existing patterns and naming conventions
2. Add appropriate markers (`@pytest.mark.integration`, etc.)
3. Update this documentation if adding new test categories
4. Ensure new tests pass in isolation and with the full suite
5. Maintain or improve overall test coverage