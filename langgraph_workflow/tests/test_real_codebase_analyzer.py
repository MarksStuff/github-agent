"""Tests for the real codebase analyzer implementation."""

import tempfile
from pathlib import Path

import pytest

from langgraph_workflow.real_codebase_analyzer import RealCodebaseAnalyzer


class TestRealCodebaseAnalyzer:
    """Test real codebase analyzer functionality."""

    def test_init_with_valid_path(self):
        """Test initializing with a valid repository path."""
        with tempfile.TemporaryDirectory() as temp_dir:
            analyzer = RealCodebaseAnalyzer(temp_dir)
            assert analyzer.repo_path == Path(temp_dir)

    def test_init_with_invalid_path(self):
        """Test initializing with an invalid repository path."""
        with pytest.raises(ValueError, match="Repository path does not exist"):
            RealCodebaseAnalyzer("/nonexistent/path")

    def test_detect_languages_python(self):
        """Test language detection for Python files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create some Python files
            (temp_path / "main.py").write_text("print('hello')")
            (temp_path / "test.py").write_text("import unittest")

            analyzer = RealCodebaseAnalyzer(temp_dir)
            languages = analyzer._detect_languages()

            assert "Python" in languages

    def test_detect_languages_multiple(self):
        """Test detection of multiple languages."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create files for different languages
            (temp_path / "main.py").write_text("print('hello')")
            (temp_path / "app.js").write_text("console.log('hello')")
            (temp_path / "schema.sql").write_text("CREATE TABLE test;")

            analyzer = RealCodebaseAnalyzer(temp_dir)
            languages = analyzer._detect_languages()

            assert "Python" in languages
            assert "JavaScript" in languages
            assert "SQL" in languages

    def test_detect_frameworks_python(self):
        """Test framework detection from requirements.txt."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create requirements.txt with frameworks
            requirements = """
fastapi>=0.68.0
langchain>=0.1.0
sqlalchemy>=1.4.0
django>=4.0.0
            """.strip()
            (temp_path / "requirements.txt").write_text(requirements)

            analyzer = RealCodebaseAnalyzer(temp_dir)
            frameworks = analyzer._detect_frameworks()

            assert "FastAPI" in frameworks
            assert "LangChain" in frameworks
            assert "SQLAlchemy" in frameworks
            assert "Django" in frameworks

    def test_detect_frameworks_nodejs(self):
        """Test framework detection from package.json."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create package.json with frameworks
            package_json = {
                "dependencies": {"react": "^18.0.0", "express": "^4.18.0"},
                "devDependencies": {"vue": "^3.0.0"},
            }

            import json

            (temp_path / "package.json").write_text(json.dumps(package_json))

            analyzer = RealCodebaseAnalyzer(temp_dir)
            frameworks = analyzer._detect_frameworks()

            assert "React" in frameworks
            assert "Express" in frameworks
            assert "Vue" in frameworks

    def test_detect_databases(self):
        """Test database detection."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create requirements.txt with database libs
            requirements = """
psycopg2-binary>=2.9.0
redis>=4.0.0
sqlite3
            """.strip()
            (temp_path / "requirements.txt").write_text(requirements)

            # Create a SQLite database file
            (temp_path / "app.db").write_text("")

            analyzer = RealCodebaseAnalyzer(temp_dir)
            databases = analyzer._detect_databases()

            assert "PostgreSQL" in databases
            assert "Redis" in databases
            assert "SQLite" in databases

    def test_find_key_files(self):
        """Test finding key files in repository."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create common important files
            (temp_path / "README.md").write_text("# Test Project")
            (temp_path / "requirements.txt").write_text("fastapi>=0.68.0")
            (temp_path / "main.py").write_text("print('hello')")
            (temp_path / "Dockerfile").write_text("FROM python:3.9")

            # Create directories
            (temp_path / "src").mkdir()
            (temp_path / "tests").mkdir()

            analyzer = RealCodebaseAnalyzer(temp_dir)
            key_files = analyzer._find_key_files()

            # Check that important files are detected
            assert any("README.md" in kf for kf in key_files)
            assert any("requirements.txt" in kf for kf in key_files)
            assert any("main.py" in kf for kf in key_files)
            assert any("Dockerfile" in kf for kf in key_files)
            assert any("src/" in kf for kf in key_files)

    def test_analyze_architecture(self):
        """Test architecture analysis."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create structure that suggests layered architecture
            (temp_path / "api").mkdir()
            (temp_path / "api" / "endpoints.py").write_text("# API code")
            (temp_path / "models").mkdir()
            (temp_path / "models" / "user.py").write_text("# Model code")
            (temp_path / "services").mkdir()
            (temp_path / "services" / "auth.py").write_text("# Service code")

            analyzer = RealCodebaseAnalyzer(temp_dir)
            architecture = analyzer._analyze_architecture()

            assert "Layered architecture" in architecture

    def test_detect_patterns(self):
        """Test design pattern detection."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create Python file with patterns
            python_code = """
from abc import ABC, abstractmethod

class UserFactory:
    def create_user(self):
        pass

class BaseModel(ABC):
    @abstractmethod
    def save(self):
        pass

class DataManager:
    @property
    def connection(self):
        return self._connection

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass
            """.strip()

            (temp_path / "patterns.py").write_text(python_code)

            analyzer = RealCodebaseAnalyzer(temp_dir)
            patterns = analyzer._detect_patterns()

            assert "Factory pattern" in patterns
            assert "Abstract base classes" in patterns
            assert "Property pattern" in patterns
            assert "Context manager pattern" in patterns

    def test_analyze_feature_impact_auth(self):
        """Test feature impact analysis for authentication."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create some auth-related files
            (temp_path / "auth.py").write_text("# Auth code")
            (temp_path / "user_model.py").write_text("# User model")

            analyzer = RealCodebaseAnalyzer(temp_dir)
            impact = analyzer.analyze_feature_impact("Add user authentication system")

            assert impact["complexity"] == "medium"
            assert "Authentication library" in impact["dependencies"]
            assert "Security vulnerabilities" in impact["risks"]
            assert len(impact["affected_files"]) > 0

    def test_analyze_feature_impact_api(self):
        """Test feature impact analysis for API features."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create API-related files
            (temp_path / "api.py").write_text("# API code")
            (temp_path / "endpoints.py").write_text("# Endpoints")

            analyzer = RealCodebaseAnalyzer(temp_dir)
            impact = analyzer.analyze_feature_impact("Add new API endpoint")

            assert "API framework" in impact["dependencies"]
            assert "Rate limiting" in impact["risks"]

    def test_full_analyze(self):
        """Test complete codebase analysis."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create a realistic project structure
            (temp_path / "README.md").write_text("# Test Project")
            (temp_path / "requirements.txt").write_text(
                "fastapi>=0.68.0\nlangchain>=0.1.0"
            )
            (temp_path / "main.py").write_text("from fastapi import FastAPI")

            # Create source structure
            (temp_path / "src").mkdir()
            (temp_path / "src" / "api").mkdir()
            (temp_path / "src" / "models").mkdir()
            (temp_path / "tests").mkdir()

            analyzer = RealCodebaseAnalyzer(temp_dir)
            analysis = analyzer.analyze()

            # Verify all expected keys are present
            expected_keys = [
                "architecture",
                "languages",
                "frameworks",
                "databases",
                "patterns",
                "conventions",
                "interfaces",
                "services",
                "testing",
                "recent_changes",
                "key_files",
            ]

            for key in expected_keys:
                assert key in analysis

            # Verify some expected content
            assert "Python" in analysis["languages"]
            assert "FastAPI" in analysis["frameworks"]
            assert "LangChain" in analysis["frameworks"]
            assert len(analysis["key_files"]) > 0
