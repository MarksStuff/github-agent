"""Pytest configuration for LangGraph workflow tests."""

import asyncio
import sys
from pathlib import Path

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import all fixtures to make them available
from .fixtures import *  # noqa: F403, E402


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# Pytest configuration
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "integration: mark test as integration test")
    config.addinivalue_line("markers", "slow: mark test as slow running")
    config.addinivalue_line("markers", "github: mark test as requiring GitHub API")


def pytest_collection_modifyitems(config, items):
    """Automatically mark tests based on their location/name."""
    for item in items:
        # Mark integration tests
        if "integration" in item.nodeid:
            item.add_marker(pytest.mark.integration)

        # Mark slow tests
        if "performance" in item.nodeid or "slow" in item.name:
            item.add_marker(pytest.mark.slow)

        # Mark GitHub tests
        if "github" in item.nodeid:
            item.add_marker(pytest.mark.github)
