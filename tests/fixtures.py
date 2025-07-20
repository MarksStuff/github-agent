"""Additional reusable fixtures for testing."""

import logging
import os
import tempfile
from unittest.mock import patch

import pytest

from constants import Language
from exit_codes import ExitCodeManager
from health_monitor import HealthMonitor
from python_symbol_extractor import PythonSymbolExtractor
from repository_indexer import PythonRepositoryIndexer
from repository_manager import RepositoryConfig
from symbol_storage import SQLiteSymbolStorage


@pytest.fixture
def exit_code_manager(test_logger):
    """Create an ExitCodeManager instance for testing."""
    return ExitCodeManager(test_logger)


@pytest.fixture
def debug_logger():
    """Create a debug logger for testing."""
    logger = logging.getLogger(f"test_debug_{id(object())}")
    logger.setLevel(logging.DEBUG)

    # Add console handler if not already present
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        )
        logger.addHandler(handler)

    return logger


# From test_exit_codes.py
@pytest.fixture
def manager(test_logger):
    """Create an ExitCodeManager instance."""
    return ExitCodeManager(test_logger)


# Note: temp_repo is replaced by temp_git_repo which is defined in conftest.py
# The mcp_worker tests should use temp_git_repo instead


@pytest.fixture
def mock_github_token():
    """Mock GitHub token environment variable"""
    with patch.dict(os.environ, {"GITHUB_TOKEN": "test_token_123"}):
        yield


@pytest.fixture
def mock_subprocess():
    """Mock subprocess calls for git operations"""
    with patch("subprocess.check_output") as mock_check_output:
        mock_check_output.return_value = b"mock output"
        yield mock_check_output


@pytest.fixture
def mcp_worker_factory(temp_git_repo, mock_github_token, mock_subprocess):
    """Factory for creating MCPWorker instances with automatic cleanup"""
    workers = []

    def create_worker(repository_path=None, port=0):
        if repository_path is None:
            repository_path = temp_git_repo
        from mcp_worker import MCPWorker

        worker = MCPWorker(repository_path, port)
        workers.append(worker)
        return worker

    yield create_worker

    # Cleanup any created workers
    for worker in workers:
        if hasattr(worker, "cleanup"):
            try:
                worker.cleanup()
            except Exception:
                pass


# From test_health_monitor.py
@pytest.fixture
def monitor(test_logger, temp_health_file):
    """Create a HealthMonitor instance."""
    return HealthMonitor(test_logger, temp_health_file)


# From test_mcp_search_symbols_integration.py
@pytest.fixture
def mock_repo_config(temp_repo_path):
    """Create a mock repository configuration for testing"""
    from constants import Language

    return RepositoryConfig(
        name="test-repo",
        workspace=temp_repo_path,
        port=9999,
        description="Test repository for search_symbols integration tests",
        language=Language.PYTHON,
        python_path="/usr/bin/python3",
        github_owner="test-owner",
        github_repo="test-repo",
    )


# From test_mcp_integration.py
@pytest.fixture
def test_config_with_dynamic_port(temp_git_repo):
    """
    Create a test repository configuration with dynamically allocated port.
    This fixture ensures each test gets a unique port to avoid conflicts.
    """
    import socket

    def find_free_port():
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("", 0))
            return s.getsockname()[1]

    port = find_free_port()

    return {
        "test_repository": {
            "repository_id": "test-repo",
            "name": "Test Repository",
            "path": temp_git_repo,
            "language": "python",
            "port": port,
            "pyright_path": "pyright",
            "python_path": "python",
        }
    }


# From test_python_symbol_extractor.py
@pytest.fixture
def extractor():
    """Create a PythonSymbolExtractor for testing."""
    return PythonSymbolExtractor()


# From test_repository_indexer.py
@pytest.fixture
def indexer(mock_symbol_extractor, mock_symbol_storage):
    """Create a repository indexer."""
    return PythonRepositoryIndexer(mock_symbol_extractor, mock_symbol_storage)


# From test_edge_cases.py
@pytest.fixture
def monitor_simple(test_logger):
    """Create a SimpleHealthMonitor."""
    from shutdown_simple import SimpleHealthMonitor

    return SimpleHealthMonitor(test_logger)


@pytest.fixture
def logger():
    """Create a real logger for testing."""
    logger = logging.getLogger(f"test_exit_codes_{id(object())}")
    logger.setLevel(logging.DEBUG)

    # Add console handler if not already present
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        )
        logger.addHandler(handler)

    # Capture logs for assertions
    captured_logs: list = []

    class TestHandler(logging.Handler):
        def emit(self, record):
            captured_logs.append(record)

    test_handler = TestHandler()
    logger.addHandler(test_handler)

    # Type ignore for dynamic attribute assignment in test fixture
    logger.captured_logs = captured_logs  # type: ignore[attr-defined]
    return logger


# From test_symbol_storage.py
@pytest.fixture
def storage():
    """Create a temporary SQLite storage for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = os.path.join(temp_dir, "test_symbols.db")
        storage = SQLiteSymbolStorage(db_path)
        yield storage
        storage.close()


# =================== FIXTURES FROM conftest.py ===================


@pytest.fixture(scope="session")
def temp_dir():
    """Create a temporary directory for test files."""
    from pathlib import Path

    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def mock_repository_manager():
    """Create a fresh mock repository manager for each test."""
    from tests.mocks import MockRepositoryManager

    return MockRepositoryManager()


@pytest.fixture
def mock_repository_manager_with_lsp():
    """Create a mock repository manager that returns mock LSP clients."""
    from tests.mocks import MockRepositoryManager

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
    import threading
    from typing import Any

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
    import threading
    import time

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


@pytest.fixture
def mock_time():
    """Provide mock time for testing time-dependent behavior."""
    from tests.mocks import MockTimeProvider

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


@pytest.fixture
def mock_symbol_storage():
    """Create a mock symbol storage for testing."""
    from tests.mocks import MockSymbolStorage

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


@pytest.fixture
def mock_symbol_extractor():
    """Create an empty mock symbol extractor."""
    from tests.mocks import MockSymbolExtractor

    return MockSymbolExtractor()


@pytest.fixture
def mock_repository_indexer():
    """Create a mock repository indexer for testing."""
    from tests.mocks import MockRepositoryIndexer

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
    import subprocess
    from pathlib import Path

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
    from symbol_storage import Symbol, SymbolKind

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
    import mcp_master
    from repository_manager import RepositoryManager
    from shutdown_simple import SimpleHealthMonitor, SimpleShutdownCoordinator
    from startup_orchestrator import CodebaseStartupOrchestrator
    from symbol_storage import ProductionSymbolStorage

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
    from tests.mocks import MockRepositoryManager

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
    from tests.mocks import MockSymbolStorage

    created_objects = []

    def _create(mock=True):
        if mock:
            return MockSymbolStorage()
        else:
            # Use real SQLiteSymbolStorage with in-memory database
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
    import codebase_tools

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


# From test_mcp_integration.py - Note: This returns a tuple (config, port) unlike the one in fixtures.py
@pytest.fixture
def test_config_with_dynamic_port_tuple(temp_git_repo):
    """
    Create a test repository configuration with dynamically allocated port.

    This configuration includes all required fields from the repository
    schema validation (port, path, language, python_path) and uses
    a dynamically allocated port to avoid conflicts.

    Args:
        temp_git_repo: Path to the temporary git repository

    Returns:
        tuple: (config_dict, allocated_port)
    """
    import socket

    # Get a free port - this is critical to avoid conflicts with production
    def find_free_port() -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("localhost", 0))  # Bind to any available port
            return s.getsockname()[1]  # Return the allocated port

    test_port = find_free_port()

    # Create a complete repository configuration that matches production format
    # All these fields are required by the master's configuration validation
    config = {
        "repositories": {
            "integration-test-repo": {
                "port": test_port,
                "workspace": temp_git_repo,
                "language": Language.PYTHON.value,  # Required field
                "python_path": "/usr/bin/python3",  # Required field for US001-12
                "description": "Integration test repository",
                "github_owner": "test-owner",  # Optional but realistic
                "github_repo": "integration-test",  # Optional but realistic
            }
        }
    }

    return config, test_port


# From test_mcp_worker.py - Custom override with GitHub context injection
@pytest.fixture
def mcp_worker_factory_with_github(temp_git_repo, mock_github_token, mock_subprocess):
    """Factory for creating MCPWorker instances with automatic cleanup"""
    from mcp_worker import MCPWorker
    from tests.mocks import MockGitHubAPIContext

    workers = []

    def _create(repo_config):
        # Create mock GitHub context for dependency injection
        mock_github_context = MockGitHubAPIContext(
            repo_name="test/test-repo", github_token="fake_token_for_testing"
        )

        # Use dependency injection instead of patching
        worker = MCPWorker(repo_config, github_context=mock_github_context)
        workers.append(worker)
        return worker

    yield _create

    # Cleanup
    for worker in workers:
        if hasattr(worker, "cleanup") and callable(worker.cleanup):
            try:
                worker.cleanup()
            except Exception:
                pass
