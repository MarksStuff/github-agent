"""
Pytest configuration and shared fixtures for shutdown system tests.
"""

import socket

import pytest

# async_lsp_client imports removed - using SimpleLSPClient directly
from symbol_storage import (
    SQLiteSymbolStorage,
)

# Import all fixtures from the centralized fixtures file
from tests.fixtures import *  # noqa: F403


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


# All fixtures have been moved to tests/fixtures.py


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


# Consolidated fixtures for common test needs are now in tests/fixtures.py
