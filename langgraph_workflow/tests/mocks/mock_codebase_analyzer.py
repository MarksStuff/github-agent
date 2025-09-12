"""Mock codebase analyzer for testing."""

from typing import Any

from ...interfaces import CodebaseAnalyzerInterface


class MockCodebaseAnalyzer(CodebaseAnalyzerInterface):
    """Mock codebase analyzer for testing."""

    def __init__(self, analysis_result: dict[str, Any] | None = None):
        """Initialize with mock analysis result."""
        self.analysis_result = analysis_result or {
            "architecture": "Mock architecture",
            "languages": ["Python", "JavaScript"],
            "frameworks": ["FastAPI", "React"],
            "patterns": "Mock patterns",
            "conventions": "Mock conventions",
            "interfaces": "Mock interfaces",
            "services": "Mock services",
            "testing": "pytest",
            "recent_changes": "Mock recent changes",
        }

    async def analyze(self) -> dict[str, Any]:
        """Return mock analysis."""
        return self.analysis_result.copy()
