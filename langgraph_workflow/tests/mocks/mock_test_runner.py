"""Mock test runner for testing."""

from typing import Any

from ...interfaces import TestRunnerInterface


class MockTestRunner(TestRunnerInterface):
    """Mock test runner for testing."""

    def __init__(
        self,
        test_results: dict[str, Any] | None = None,
        lint_results: dict[str, Any] | None = None,
    ):
        """Initialize with mock results."""
        self.test_results = test_results or {
            "passed": 10,
            "failed": 0,
            "errors": 0,
            "total": 10,
            "failed_tests": [],
        }
        self.lint_results = lint_results or {"errors": 0, "warnings": 0, "issues": []}
        self.runs = []

    async def run_tests(self, test_path: str | None = None) -> dict[str, Any]:
        """Mock run tests."""
        self.runs.append(("tests", test_path))
        return self.test_results.copy()

    async def run_lint(self) -> dict[str, Any]:
        """Mock run lint."""
        self.runs.append(("lint", None))
        return self.lint_results.copy()

    def set_test_results(self, results: dict[str, Any]) -> None:
        """Helper to set test results."""
        self.test_results = results

    def set_lint_results(self, results: dict[str, Any]) -> None:
        """Helper to set lint results."""
        self.lint_results = results