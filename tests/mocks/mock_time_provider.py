"""Mock time provider for testing."""

import threading


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
