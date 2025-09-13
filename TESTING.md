# Testing Guide

## Test Configuration

The pytest configuration has been updated to support flexible test execution modes.

## Running Tests

### 1. All Tests (Default)
Run all tests including integration tests that hit your RTX 5070:
```bash
pytest
```
This runs both unit tests (fast, with mocks) and integration tests (slower, real Ollama calls).

### 2. Unit Tests Only
Run only unit tests (fast, no GPU usage):
```bash
pytest -m "not integration"
```
This excludes integration tests and runs only mocked tests.

### 3. Integration Tests Only
Run only integration tests (will use your RTX 5070):
```bash
pytest -m integration
```
This runs only the tests that make real calls to Ollama.

### 4. Specific Test Categories
Run tests with specific markers:
```bash
pytest -m slow          # Run slow tests
pytest -m github        # Run GitHub API tests
pytest -m "integration and slow"  # Run slow integration tests
```

## Environment Configuration

Integration tests automatically read configuration from `pytest.ini`:
- `OLLAMA_BASE_URL = http://marks-pc:11434`

No need to set environment variables manually when using pytest.

## Test Markers

- `@pytest.mark.integration`: Tests that use real external services (Ollama, GitHub)
- `@pytest.mark.slow`: Tests that take significant time to complete
- `@pytest.mark.github`: Tests requiring GitHub API access
- `@pytest.mark.unit`: Fast unit tests using mocks (default)

## GPU Activity

Integration tests will show GPU activity on your RTX 5070. You can monitor this with:
```bash
nvidia-smi
```

Unit tests use mocks and will show no GPU activity.