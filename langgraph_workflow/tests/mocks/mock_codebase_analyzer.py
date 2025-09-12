"""Mock implementation of CodebaseAnalyzer for testing."""

from typing import Any


class MockCodebaseAnalyzer:
    """Mock codebase analyzer that returns predictable analysis results."""

    def __init__(self, repo_path: str | None = None):
        """Initialize mock analyzer.
        
        Args:
            repo_path: Repository path (ignored in mock)
        """
        self.repo_path = repo_path
        self.custom_analysis = {}

    def set_analysis_result(self, analysis: dict[str, Any]):
        """Set custom analysis result for testing specific scenarios.
        
        Args:
            analysis: Custom analysis dictionary to return
        """
        self.custom_analysis = analysis

    async def analyze(self) -> dict[str, Any]:
        """Analyze the codebase and return structured information.
        
        Returns:
            Analysis results with architecture, patterns, etc.
        """
        # Return custom analysis if set, otherwise default test analysis
        if self.custom_analysis:
            return self.custom_analysis
            
        return {
            "architecture": "Test microservices architecture with clean separation of concerns",
            "languages": ["Python", "TypeScript", "SQL"],
            "frameworks": ["FastAPI", "React", "LangGraph", "SQLAlchemy"],
            "databases": ["PostgreSQL", "Redis"],
            "patterns": "Repository pattern, dependency injection, observer pattern, factory pattern",
            "conventions": "PEP 8 for Python, ESLint for TypeScript, conventional commits",
            "interfaces": "Abstract base classes for repositories, services, and agents",
            "services": "REST API services, background task queues, caching layer",
            "testing": "pytest with fixtures, unittest.mock only for external dependencies",
            "recent_changes": "Added LangGraph workflow system, improved test architecture",
            "key_files": [
                "src/main.py - Application entry point",
                "src/models/ - Database models",
                "src/services/ - Business logic services", 
                "src/api/ - REST API endpoints",
                "tests/ - Comprehensive test suite"
            ],
            "complexity_score": 0.6,  # Medium complexity
            "technical_debt": 0.2,    # Low technical debt
            "test_coverage": 0.85,    # Good test coverage
        }

    def analyze_feature_impact(self, feature_description: str) -> dict[str, Any]:
        """Analyze the impact of a proposed feature.
        
        Args:
            feature_description: Description of the feature to analyze
            
        Returns:
            Impact analysis including affected files, complexity, etc.
        """
        feature_lower = feature_description.lower()
        
        # Pattern-based analysis
        if "auth" in feature_lower or "login" in feature_lower:
            return {
                "affected_files": [
                    "src/auth/", "src/models/user.py", "src/api/auth.py",
                    "tests/test_auth.py", "src/middleware/auth.py"
                ],
                "complexity": "medium",
                "estimated_effort": "3-5 days",
                "dependencies": ["JWT library", "password hashing", "session storage"],
                "risks": ["Security vulnerabilities", "session management complexity"]
            }
        elif "dashboard" in feature_lower or "ui" in feature_lower:
            return {
                "affected_files": [
                    "frontend/src/components/", "src/api/dashboard.py",
                    "frontend/src/pages/", "tests/test_dashboard.py"
                ],
                "complexity": "medium",
                "estimated_effort": "4-6 days", 
                "dependencies": ["Chart library", "data visualization", "responsive design"],
                "risks": ["Performance with large datasets", "browser compatibility"]
            }
        else:
            return {
                "affected_files": ["src/", "tests/"],
                "complexity": "unknown",
                "estimated_effort": "2-4 days",
                "dependencies": [],
                "risks": ["Unclear requirements"]
            }