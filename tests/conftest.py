"""
Pytest configuration and shared fixtures for shutdown system tests.
"""

import logging
import os
import socket
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

import pytest

import codebase_tools
import mcp_master
# async_lsp_client imports removed - using SimpleLSPClient directly
from lsp_constants import LSPServerType
from python_symbol_extractor import AbstractSymbolExtractor, PythonSymbolExtractor
from repository_indexer import (
    AbstractRepositoryIndexer,
    IndexingResult,
    PythonRepositoryIndexer,
)
from repository_manager import RepositoryManager
from shutdown_simple import SimpleHealthMonitor, SimpleShutdownCoordinator
from startup_orchestrator import CodebaseStartupOrchestrator
from symbol_storage import (
    AbstractSymbolStorage,
    ProductionSymbolStorage,
    SQLiteSymbolStorage,
    Symbol,
    SymbolKind,
)
from tests.test_fixtures import MockRepositoryManager


def find_free_port(start_port: int = 8081, max_attempts: int = 100) -> int:
    """
    Find a free port starting from start_port.

    Args:
        start_port: Port to start searching from
        max_attempts: Maximum number of ports to try

    Returns:
        Free port number

    Raises:
        RuntimeError: If no free port found within max_attempts
    """
    for port in range(start_port, start_port + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind(("localhost", port))
                return port
            except OSError:
                continue

    raise RuntimeError(
        f"No free port found in range {start_port}-{start_port + max_attempts}"
    )


# Minimal MockLSPClient for test compatibility
class MockLSPClient:
    """Minimal mock LSP client for testing compatibility."""
    
    def __init__(self, workspace_root: str = "/test"):
        self.workspace_root = workspace_root
        self.logger = logging.getLogger(__name__)
        
    async def get_definition(self, uri: str, line: int, character: int) -> list[dict] | None:
        """Mock get_definition method."""
        return []
        
    async def get_references(self, uri: str, line: int, character: int, include_declaration: bool = True) -> list[dict] | None:
        """Mock get_references method."""
        return []
        
    async def get_hover(self, uri: str, line: int, character: int) -> dict | None:
        """Mock get_hover method."""
        return None


@pytest.fixture(scope="session")
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def mock_repository_manager():
    """Create a fresh mock repository manager for each test."""
    return MockRepositoryManager()


# LSP client provider functions removed - SimpleLSPClient used directly


@pytest.fixture
def mock_repository_manager_with_lsp():
    """Create a mock repository manager that returns mock LSP clients."""
    return MockRepositoryManager()


@pytest.fixture
def temp_health_file(temp_dir):
    """Create a temporary health file path."""
    health_file = temp_dir / "health.json"
    yield str(health_file)
    # Cleanup is automatic with temp_dir


@pytest.fixture
def timeout_protection():
    """Provide timeout protection for tests that might hang."""
    timeout_seconds = 30  # Default test timeout

    def run_with_timeout(func, *args, **kwargs):
        """Run a function with timeout protection."""
        result: list[Any] = [None]
        exception: list[Exception | None] = [None]

        def target():
            try:
                result[0] = func(*args, **kwargs)
            except Exception as e:
                exception[0] = e

        thread = threading.Thread(target=target)
        thread.daemon = True  # Dies with main thread
        thread.start()
        thread.join(timeout=timeout_seconds)

        if thread.is_alive():
            raise TimeoutError(
                f"Function {func.__name__} timed out after {timeout_seconds}s"
            )

        if exception[0]:
            raise exception[0]

        return result[0]

    return run_with_timeout


@pytest.fixture(autouse=True)
def cleanup_threads():
    """Automatically cleanup any daemon threads after each test."""
    # Record initial thread count
    initial_threads = set(threading.enumerate())

    yield

    # Wait for test threads to finish
    max_wait = 5.0  # seconds
    start_time = time.time()

    while time.time() - start_time < max_wait:
        current_threads = set(threading.enumerate())
        test_threads = current_threads - initial_threads

        # Filter out daemon threads and threads that are finishing
        active_test_threads = [
            t
            for t in test_threads
            if t.is_alive() and not t.daemon and t != threading.current_thread()
        ]

        if not active_test_threads:
            break

        time.sleep(0.1)

    # Force cleanup any remaining threads
    current_threads = set(threading.enumerate())
    remaining_threads = current_threads - initial_threads
    for thread in remaining_threads:
        if (
            thread.is_alive()
            and not thread.daemon
            and thread != threading.current_thread()
        ):
            try:
                # Try to join with short timeout
                thread.join(timeout=0.1)
            except Exception:
                pass  # Best effort cleanup


class MockTimeProvider:
    """Mock time provider for testing time-dependent behavior."""

    def __init__(self):
        self.current_time = 0.0
        self._lock = threading.Lock()

    def time(self):
        """Get current mock time."""
        with self._lock:
            return self.current_time

    def advance(self, seconds):
        """Advance mock time by specified seconds."""
        with self._lock:
            self.current_time += seconds

    def sleep(self, seconds):
        """Mock sleep that advances time instead of waiting."""
        self.advance(seconds)


@pytest.fixture
def mock_time():
    """Provide mock time for testing time-dependent behavior."""
    mock_time_provider = MockTimeProvider()

    # Patch time.time and time.sleep
    import time

    original_time = time.time
    original_sleep = time.sleep

    time.time = mock_time_provider.time
    time.sleep = mock_time_provider.sleep

    yield mock_time_provider

    # Restore original functions
    time.time = original_time
    time.sleep = original_sleep


@pytest.fixture
def captured_signals():
    """Capture signals sent during test for verification."""
    captured = []

    import signal

    original_signal = signal.signal

    def mock_signal(sig, handler):
        captured.append(("register", sig, handler))
        return original_signal(sig, handler)

    signal.signal = mock_signal

    yield captured

    # Restore
    signal.signal = original_signal


# Custom assertions for shutdown testing
def assert_clean_shutdown(shutdown_result, exit_code_manager, expected_exit_code=None):
    """Assert that a shutdown completed cleanly."""
    assert shutdown_result is True, "Shutdown should have succeeded"

    if expected_exit_code:
        actual_exit_code = exit_code_manager.determine_exit_code("test")
        assert (
            actual_exit_code == expected_exit_code
        ), f"Expected exit code {expected_exit_code}, got {actual_exit_code}"

    summary = exit_code_manager.get_exit_summary()
    assert (
        summary["total_problems"] == 0
    ), f"Expected clean shutdown but found problems: {summary}"


def assert_shutdown_with_issues(
    shutdown_result, exit_code_manager, expected_problems=None
):
    """Assert that a shutdown completed but had issues."""
    # Shutdown might succeed or fail depending on severity
    if shutdown_result is False:
        # Failed shutdown should have critical issues
        summary = exit_code_manager.get_exit_summary()
        assert (
            summary["total_problems"] > 0
        ), "Failed shutdown should have reported problems"

    if expected_problems:
        summary = exit_code_manager.get_exit_summary()
        assert (
            summary["total_problems"] >= expected_problems
        ), f"Expected at least {expected_problems} problems, got {summary['total_problems']}"


# Add to pytest namespace for easy import
pytest.assert_clean_shutdown = assert_clean_shutdown  # type: ignore[attr-defined]
pytest.assert_shutdown_with_issues = assert_shutdown_with_issues  # type: ignore[attr-defined]


# Mock classes for testing symbol extraction and indexing
class MockSymbolStorage(AbstractSymbolStorage):
    """Mock symbol storage for testing."""

    def __init__(self):
        """Initialize mock storage."""
        self.symbols: list[Symbol] = []
        self.deleted_repositories: list[str] = []
        self._health_check_result: bool = True

    def create_schema(self) -> None:
        """Create schema (no-op for mock)."""
        pass

    def insert_symbol(self, symbol: Symbol) -> None:
        """Insert a symbol into mock storage."""
        self.symbols.append(symbol)

    def insert_symbols(self, symbols: list[Symbol]) -> None:
        """Insert symbols into mock storage."""
        self.symbols.extend(symbols)

    def update_symbol(self, symbol: Symbol) -> None:
        """Update symbol in mock storage (no-op for mock)."""
        pass

    def delete_symbol(self, symbol_id: int) -> None:
        """Delete symbol by ID (no-op for mock)."""
        pass

    def delete_symbols_by_repository(self, repository_id: str) -> None:
        """Delete symbols by repository in mock storage."""
        self.deleted_repositories.append(repository_id)
        self.symbols = [s for s in self.symbols if s.repository_id != repository_id]

    def search_symbols(
        self,
        query: str,
        repository_id: str | None = None,
        symbol_kind: str | None = None,
        limit: int = 50,
    ) -> list[Symbol]:
        """Search symbols in mock storage."""
        results = self.symbols.copy()

        if query:
            results = [s for s in results if query.lower() in s.name.lower()]
        if repository_id:
            results = [s for s in results if s.repository_id == repository_id]
        if symbol_kind:
            results = [s for s in results if s.kind.value == symbol_kind]

        return results[:limit]

    def get_symbol_by_id(self, symbol_id: int) -> Symbol | None:
        """Get symbol by ID in mock storage (not implemented for mock)."""
        return None

    def get_symbols_by_file(self, file_path: str, repository_id: str) -> list[Symbol]:
        """Get symbols by file path in mock storage."""
        return [
            s
            for s in self.symbols
            if s.file_path == file_path and s.repository_id == repository_id
        ]

    def health_check(self) -> bool:
        """Mock health check returns configurable result."""
        return self._health_check_result

    def set_health_check_result(self, result: bool) -> None:
        """Set the health check result for testing."""
        self._health_check_result = result


class MockSymbolExtractor(AbstractSymbolExtractor):
    """Mock symbol extractor for testing."""

    def __init__(self):
        """Initialize empty mock extractor."""
        self.symbols: list[Symbol] = []

    def extract_from_file(self, file_path: str, repository_id: str) -> list[Symbol]:
        """Return predefined symbols."""
        return self.symbols.copy()

    def extract_from_source(
        self, source: str, file_path: str, repository_id: str
    ) -> list[Symbol]:
        """Return predefined symbols."""
        return self.symbols.copy()


class MockRepositoryIndexer(AbstractRepositoryIndexer):
    """Mock repository indexer for testing."""

    def __init__(self):
        """Initialize empty mock indexer."""
        self.predefined_result = IndexingResult()
        self.last_repository_path = ""
        self.last_repository_id = ""
        self.clear_calls: list[str] = []

    def index_repository(
        self, repository_path: str, repository_id: str
    ) -> IndexingResult:
        """Return predefined result and track call parameters."""
        self.last_repository_path = repository_path
        self.last_repository_id = repository_id
        return self.predefined_result

    def clear_repository_index(self, repository_id: str) -> None:
        """Track clear repository calls."""
        self.clear_calls.append(repository_id)


# Test fixtures for mock objects
@pytest.fixture
def mock_symbol_storage():
    """Create a mock symbol storage for testing."""
    return MockSymbolStorage()


@pytest.fixture
def in_memory_symbol_storage():
    """Create an in-memory SQLite symbol storage for integration testing."""
    storage = SQLiteSymbolStorage(":memory:")
    yield storage
    storage.close()


@pytest.fixture
def temp_symbol_storage(tmp_path):
    """Create a temporary file-based SQLite symbol storage for testing."""
    db_path = tmp_path / "test_symbols.db"
    storage = SQLiteSymbolStorage(str(db_path))
    yield storage
    storage.close()


class SymbolStorageCloser:
    """Context manager to ensure SQLiteSymbolStorage is properly closed."""

    def __init__(self, db_path):
        self.db_path = db_path
        self.storage = None

    def __enter__(self):
        self.storage = SQLiteSymbolStorage(str(self.db_path))
        return self.storage

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.storage:
            self.storage.close()


@pytest.fixture
def mock_symbol_extractor():
    """Create an empty mock symbol extractor."""
    return MockSymbolExtractor()


@pytest.fixture
def mock_repository_indexer():
    """Create a mock repository indexer for testing."""
    return MockRepositoryIndexer()


@pytest.fixture
def temp_database():
    """Create a temporary SQLite database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_file:
        db_path = temp_file.name

    storage = SQLiteSymbolStorage(db_path)
    yield storage

    # Cleanup
    storage.close()
    try:
        os.unlink(db_path)
    except OSError:
        pass


# Consolidated fixtures for common test needs


@pytest.fixture
def test_logger():
    """Create a real logger for testing."""
    logger = logging.getLogger(f"test_logger_{id(object())}")
    logger.setLevel(logging.DEBUG)

    # Add console handler if not already present
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        )
        logger.addHandler(handler)

    return logger


@pytest.fixture
def temp_git_repo():
    """Create a temporary git repository for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        repo_path = Path(temp_dir)

        # Initialize as a real git repository
        subprocess.run(["git", "init"], cwd=repo_path, capture_output=True, check=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=repo_path,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=repo_path,
            capture_output=True,
            check=True,
        )

        # Create test files
        (repo_path / "README.md").write_text("# Test Repository")
        (repo_path / "main.py").write_text("# Main application file")

        # Initial commit
        subprocess.run(
            ["git", "add", "."], cwd=repo_path, capture_output=True, check=True
        )
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            cwd=repo_path,
            capture_output=True,
            check=True,
        )

        yield str(repo_path)


@pytest.fixture
def temp_repo_path():
    """Create a temporary repository path for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield str(temp_dir)


@pytest.fixture
def python_symbol_extractor():
    """Create a PythonSymbolExtractor for testing."""
    return PythonSymbolExtractor()


@pytest.fixture
def sample_symbols():
    """Create sample symbols for testing."""
    return [
        Symbol(
            name="TestClass",
            kind=SymbolKind.CLASS,
            file_path="test.py",
            line_number=1,
            column_number=0,
            repository_id="test-repo",
            docstring="A test class.",
        ),
        Symbol(
            name="test_function",
            kind=SymbolKind.FUNCTION,
            file_path="test.py",
            line_number=10,
            column_number=0,
            repository_id="test-repo",
        ),
        Symbol(
            name="test_method",
            kind=SymbolKind.METHOD,
            file_path="test.py",
            line_number=15,
            column_number=4,
            repository_id="test-repo",
        ),
        Symbol(
            name="TEST_CONSTANT",
            kind=SymbolKind.CONSTANT,
            file_path="constants.py",
            line_number=1,
            column_number=0,
            repository_id="test-repo",
        ),
        Symbol(
            name="helper_function",
            kind=SymbolKind.FUNCTION,
            file_path="utils.py",
            line_number=5,
            column_number=0,
            repository_id="other-repo",
        ),
    ]


@pytest.fixture
def mcp_master_factory():
    """
    Factory fixture for creating MCPMaster instances with all required dependencies.

    This fixture returns a function that creates MCPMaster instances with proper
    dependency injection, using the same pattern as the main() function.
    """

    def create_mcp_master(config_file_path: str) -> mcp_master.MCPMaster:
        # Create repository manager from configuration
        repository_manager = RepositoryManager.create_from_config(config_file_path)

        # Create worker managers (empty for testing)
        workers: dict[str, mcp_master.WorkerProcess] = {}

        # Create startup orchestrator components
        symbol_storage = ProductionSymbolStorage.create_with_schema()
        symbol_extractor = PythonSymbolExtractor()
        indexer = PythonRepositoryIndexer(symbol_extractor, symbol_storage)

        startup_orchestrator = CodebaseStartupOrchestrator(
            symbol_storage=symbol_storage,
            symbol_extractor=symbol_extractor,
            indexer=indexer,
        )

        # Create shutdown and health monitoring components
        import logging

        test_logger = logging.getLogger("test_mcp_master")
        shutdown_coordinator = SimpleShutdownCoordinator(test_logger)
        health_monitor = SimpleHealthMonitor(test_logger)

        # Create CodebaseTools instance
        from codebase_tools import CodebaseTools, create_simple_lsp_client

        codebase_tools = CodebaseTools(
            repository_manager=repository_manager,
            symbol_storage=symbol_storage,
            lsp_client_factory=create_simple_lsp_client,
        )

        return mcp_master.MCPMaster(
            repository_manager=repository_manager,
            workers=workers,
            startup_orchestrator=startup_orchestrator,
            symbol_storage=symbol_storage,
            shutdown_coordinator=shutdown_coordinator,
            health_monitor=health_monitor,
            codebase_tools=codebase_tools,
        )

    return create_mcp_master


# Factory fixtures for dependency injection with automatic cleanup
@pytest.fixture
def repository_manager_factory():
    """Factory for creating repository manager instances."""

    def _create(mock=True):
        if mock:
            return MockRepositoryManager()
        else:
            # Use real RepositoryManager for testing
            from repository_manager import RepositoryManager

            return RepositoryManager()

    return _create


@pytest.fixture
def symbol_storage_factory():
    """Factory for creating symbol storage instances with automatic cleanup."""
    created_objects = []

    def _create(mock=True):
        if mock:
            return MockSymbolStorage()
        else:
            # Use real SQLiteSymbolStorage with in-memory database
            from symbol_storage import SQLiteSymbolStorage

            storage = SQLiteSymbolStorage(db_path=":memory:")
            created_objects.append(storage)
            return storage

    yield _create

    # Cleanup all created real objects
    for obj in created_objects:
        obj.close()


@pytest.fixture
def lsp_client_factory_factory():
    """Factory for creating LSP client factory functions."""

    def _create(mock=True):
        # SimpleLSPClient doesn't need mocking - it's simple and reliable
        from codebase_tools import create_simple_lsp_client
        return create_simple_lsp_client

    return _create


@pytest.fixture
def codebase_tools_factory(
    repository_manager_factory, symbol_storage_factory, lsp_client_factory_factory
):
    """Factory for creating CodebaseTools instances with automatic cleanup."""

    def _create(
        repositories: dict | None = None,
        use_real_repository_manager: bool = False,
        use_real_symbol_storage: bool = False,
        use_real_lsp_client_factory: bool = False,
    ) -> codebase_tools.CodebaseTools:
        if repositories is None:
            repositories = {}
        # Create repository manager
        repository_manager = repository_manager_factory(
            mock=not use_real_repository_manager
        )
        for name, config in repositories.items():
            repository_manager.add_repository(name, config)

        # Create symbol storage
        symbol_storage = symbol_storage_factory(mock=not use_real_symbol_storage)

        # Create LSP client factory
        lsp_client_factory = lsp_client_factory_factory(
            mock=not use_real_lsp_client_factory
        )

        return codebase_tools.CodebaseTools(
            repository_manager=repository_manager,
            symbol_storage=symbol_storage,
            lsp_client_factory=lsp_client_factory,
        )

    return _create
