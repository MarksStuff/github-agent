"""Real implementation of CodebaseAnalyzer using MCP tools."""

from pathlib import Path
from typing import Any

from .interfaces import CodebaseAnalyzerInterface


class RealCodebaseAnalyzer(CodebaseAnalyzerInterface):
    """Real codebase analyzer that uses MCP tools to analyze the repository."""

    def __init__(self, repo_path: str):
        """Initialize analyzer with repository path.

        Args:
            repo_path: Path to the repository to analyze
        """
        self._repo_path = Path(repo_path)
        if not self._repo_path.exists():
            raise ValueError(f"Repository path does not exist: {repo_path}")

    @property
    def repo_path(self) -> Path:
        """Get the repository path being analyzed."""
        return self._repo_path

    def analyze(self) -> dict[str, Any]:
        """Analyze the codebase and return structured information.

        Returns:
            Analysis results with architecture, patterns, etc.
        """
        # Get basic file structure
        languages = self._detect_languages()
        frameworks = self._detect_frameworks()
        databases = self._detect_databases()
        key_files = self._find_key_files()

        # Analyze architecture patterns
        architecture = self._analyze_architecture()
        patterns = self._detect_patterns()
        conventions = self._detect_conventions()
        interfaces = self._find_interfaces()
        services = self._find_services()
        testing = self._analyze_testing()
        recent_changes = self._get_recent_changes()

        return {
            "architecture": architecture,
            "languages": languages,
            "frameworks": frameworks,
            "databases": databases,
            "patterns": patterns,
            "conventions": conventions,
            "interfaces": interfaces,
            "services": services,
            "testing": testing,
            "recent_changes": recent_changes,
            "key_files": key_files[:10],  # Limit to top 10
        }

    def analyze_feature_impact(self, feature_description: str) -> dict[str, Any]:
        """Analyze the impact of a proposed feature.

        Args:
            feature_description: Description of the feature to analyze

        Returns:
            Impact analysis including affected files, complexity, etc.
        """
        # This is a simplified implementation
        # In a full version, this would use Claude or other analysis tools

        affected_files = []
        complexity = "medium"
        estimated_effort = "2-4 days"
        dependencies = []
        risks = []

        # Basic pattern matching for common features
        feature_lower = feature_description.lower()

        if "auth" in feature_lower or "login" in feature_lower:
            affected_files = self._find_auth_related_files()
            dependencies = ["Authentication library", "JWT tokens", "Password hashing"]
            risks = ["Security vulnerabilities", "Session management"]

        elif "api" in feature_lower or "endpoint" in feature_lower:
            affected_files = self._find_api_related_files()
            dependencies = ["API framework", "Request validation"]
            risks = ["API versioning", "Rate limiting"]

        elif "database" in feature_lower or "model" in feature_lower:
            affected_files = self._find_database_related_files()
            dependencies = ["Database migrations", "ORM updates"]
            risks = ["Data migration", "Schema changes"]

        else:
            # Default analysis
            affected_files = [str(f) for f in self._find_key_files()[:5]]

        return {
            "affected_files": affected_files,
            "complexity": complexity,
            "estimated_effort": estimated_effort,
            "dependencies": dependencies,
            "risks": risks,
        }

    def _detect_languages(self) -> list[str]:
        """Detect programming languages used in the repository."""
        languages = []

        # Directories to exclude from language detection (dependencies, not source code)
        excluded_dirs = {
            ".venv",
            "venv",
            "env",
            ".env",  # Python virtual environments
            "node_modules",
            ".npm",  # Node.js dependencies
            "__pycache__",
            ".pytest_cache",  # Python cache directories
            ".git",
            ".gitignore",  # Git metadata
            "site-packages",  # Python packages
            "dist",
            "build",
            ".tox",  # Build artifacts
            "coverage",
            ".coverage",
            "htmlcov",  # Coverage files and HTML reports
            ".mypy_cache",
            ".ruff_cache",  # Linting cache
            "artifacts",
            "tmp",
            "temp",  # Temporary directories
            "logs",
            "log",  # Log directories
        }

        # Check for common language file extensions
        language_patterns = {
            "Python": ["*.py"],
            "JavaScript": ["*.js", "*.jsx"],
            "TypeScript": ["*.ts", "*.tsx"],
            "Java": ["*.java"],
            "C++": ["*.cpp", "*.cc", "*.cxx"],
            "C": ["*.c"],
            "Go": ["*.go"],
            "Rust": ["*.rs"],
            "Ruby": ["*.rb"],
            "PHP": ["*.php"],
            "SQL": ["*.sql"],
            "Shell": ["*.sh", "*.bash"],
            "YAML": ["*.yml", "*.yaml"],
            "JSON": ["*.json"],
        }

        for language, patterns in language_patterns.items():
            for pattern in patterns:
                # Find all matching files but exclude dependency directories
                matching_files = []
                for file_path in self._repo_path.rglob(pattern):
                    # Check if file is in an excluded directory
                    path_parts = file_path.relative_to(self._repo_path).parts
                    if not any(
                        excluded_dir in path_parts for excluded_dir in excluded_dirs
                    ):
                        matching_files.append(file_path)

                if matching_files:
                    languages.append(language)
                    break

        return languages

    def _detect_frameworks(self) -> list[str]:
        """Detect frameworks used in the repository."""
        frameworks = []

        # Check for common framework indicators
        if (self._repo_path / "package.json").exists():
            try:
                import json

                with open(self._repo_path / "package.json") as f:
                    package_data = json.load(f)
                    deps = {
                        **package_data.get("dependencies", {}),
                        **package_data.get("devDependencies", {}),
                    }

                    if "react" in deps:
                        frameworks.append("React")
                    if "vue" in deps:
                        frameworks.append("Vue")
                    if "angular" in deps:
                        frameworks.append("Angular")
                    if "express" in deps:
                        frameworks.append("Express")
                    if "next" in deps:
                        frameworks.append("Next.js")
            except Exception:
                pass

        if (self._repo_path / "requirements.txt").exists():
            try:
                with open(self._repo_path / "requirements.txt") as f:
                    requirements = f.read().lower()

                    if "fastapi" in requirements:
                        frameworks.append("FastAPI")
                    if "django" in requirements:
                        frameworks.append("Django")
                    if "flask" in requirements:
                        frameworks.append("Flask")
                    if "langchain" in requirements:
                        frameworks.append("LangChain")
                    if "langgraph" in requirements:
                        frameworks.append("LangGraph")
                    if "sqlalchemy" in requirements:
                        frameworks.append("SQLAlchemy")
            except Exception:
                pass

        return frameworks

    def _detect_databases(self) -> list[str]:
        """Detect databases used in the repository."""
        databases = []

        # Check for database configuration files and patterns
        db_indicators = {
            "PostgreSQL": ["postgres", "psycopg", "postgresql"],
            "MySQL": ["mysql", "pymysql"],
            "SQLite": ["sqlite", ".db", ".sqlite"],
            "Redis": ["redis"],
            "MongoDB": ["mongo", "pymongo"],
        }

        # Check requirements.txt
        try:
            if (self._repo_path / "requirements.txt").exists():
                with open(self._repo_path / "requirements.txt") as f:
                    requirements = f.read().lower()

                    for db, indicators in db_indicators.items():
                        if any(ind in requirements for ind in indicators):
                            databases.append(db)
        except Exception:
            pass

        # Check for database files
        if list(self._repo_path.rglob("*.db")) or list(
            self._repo_path.rglob("*.sqlite")
        ):
            if "SQLite" not in databases:
                databases.append("SQLite")

        return databases

    def _find_key_files(self) -> list[str]:
        """Find key files in the repository."""
        key_files = []

        # Common important files
        important_files = [
            "README.md",
            "requirements.txt",
            "package.json",
            "setup.py",
            "pyproject.toml",
            "Cargo.toml",
            "go.mod",
            "main.py",
            "app.py",
            "index.js",
            "main.js",
            "Dockerfile",
            "docker-compose.yml",
            ".env.example",
            "config.py",
            "settings.py",
        ]

        for filename in important_files:
            file_path = self._repo_path / filename
            if file_path.exists():
                key_files.append(f"{filename} - {self._get_file_description(filename)}")

        # Add some directory-based files
        common_dirs = ["src", "lib", "app", "api", "models", "services", "components"]
        for dir_name in common_dirs:
            dir_path = self._repo_path / dir_name
            if dir_path.exists() and dir_path.is_dir():
                key_files.append(f"{dir_name}/ - {self._get_dir_description(dir_name)}")

        return key_files

    def _get_file_description(self, filename: str) -> str:
        """Get a description for a common file."""
        descriptions = {
            "README.md": "Project documentation",
            "requirements.txt": "Python dependencies",
            "package.json": "Node.js dependencies",
            "setup.py": "Python package setup",
            "main.py": "Application entry point",
            "app.py": "Application entry point",
            "index.js": "JavaScript entry point",
            "Dockerfile": "Container configuration",
            "docker-compose.yml": "Multi-container setup",
            "config.py": "Application configuration",
            "settings.py": "Application settings",
        }
        return descriptions.get(filename, "Configuration file")

    def _get_dir_description(self, dirname: str) -> str:
        """Get a description for a common directory."""
        descriptions = {
            "src": "Source code",
            "lib": "Library code",
            "app": "Application code",
            "api": "API endpoints",
            "models": "Data models",
            "services": "Business services",
            "components": "UI components",
            "tests": "Test suite",
            "docs": "Documentation",
        }
        return descriptions.get(dirname, "Code directory")

    def _analyze_architecture(self) -> str:
        """Analyze the overall architecture."""
        # This is a simplified analysis
        # In a full implementation, this would analyze imports, dependencies, etc.

        has_api = bool(list(self._repo_path.rglob("*api*")))
        has_models = bool(list(self._repo_path.rglob("*model*")))
        has_services = bool(list(self._repo_path.rglob("*service*")))
        has_tests = bool(list(self._repo_path.rglob("test*")))

        if has_api and has_models and has_services:
            return "Layered architecture with API, service, and data layers"
        elif has_api and has_models:
            return "API-based architecture with data models"
        elif has_tests:
            return "Well-structured codebase with testing"
        else:
            return "Standard project structure"

    def _detect_patterns(self) -> str:
        """Detect design patterns used."""
        patterns = set()  # Use set to avoid duplicates

        # Look for common pattern indicators
        py_files = list(self._repo_path.rglob("*.py"))

        for file_path in py_files[:20]:  # Limit search
            try:
                content = file_path.read_text(encoding="utf-8")

                if "Factory" in content and "class" in content:
                    patterns.add("Factory pattern")
                if "from abc import" in content:
                    patterns.add("Abstract base classes")
                if "def __enter__" in content and "def __exit__" in content:
                    patterns.add("Context manager pattern")
                if "@property" in content:
                    patterns.add("Property pattern")
                if "Observer" in content or "observer" in content:
                    patterns.add("Observer pattern")
                if "Singleton" in content:
                    patterns.add("Singleton pattern")
                if "Strategy" in content:
                    patterns.add("Strategy pattern")
                if "Builder" in content:
                    patterns.add("Builder pattern")
            except Exception:
                continue

        return ", ".join(sorted(patterns)) if patterns else "Standard OOP patterns"

    def _detect_conventions(self) -> str:
        """Detect coding conventions used."""
        conventions = []

        # Check for common convention files
        if (self._repo_path / ".flake8").exists() or (
            self._repo_path / "setup.cfg"
        ).exists():
            conventions.append("PEP 8 (Python)")

        if (self._repo_path / ".eslintrc").exists() or (
            self._repo_path / ".eslintrc.json"
        ).exists():
            conventions.append("ESLint (JavaScript/TypeScript)")

        if (self._repo_path / ".editorconfig").exists():
            conventions.append("EditorConfig")

        if (self._repo_path / ".pre-commit-config.yaml").exists():
            conventions.append("Pre-commit hooks")

        return ", ".join(conventions) if conventions else "Standard conventions"

    def _find_interfaces(self) -> str:
        """Find interface definitions."""
        interfaces = []

        # Look for Python abstract base classes
        py_files = list(self._repo_path.rglob("*interface*.py"))
        py_files.extend(list(self._repo_path.rglob("*abc*.py")))

        if py_files:
            interfaces.append("Python abstract interfaces")

        # Look for TypeScript interfaces
        ts_files = list(self._repo_path.rglob("*.ts"))
        for file_path in ts_files[:10]:
            try:
                content = file_path.read_text()
                if "interface " in content:
                    interfaces.append("TypeScript interfaces")
                    break
            except Exception:
                continue

        return ", ".join(interfaces) if interfaces else "Implicit interfaces"

    def _find_services(self) -> str:
        """Find service definitions."""
        services = []

        if list(self._repo_path.rglob("*service*.py")):
            services.append("Python services")

        if list(self._repo_path.rglob("*api*.py")):
            services.append("API endpoints")

        if (self._repo_path / "docker-compose.yml").exists():
            services.append("Containerized services")

        return ", ".join(services) if services else "Monolithic structure"

    def _analyze_testing(self) -> str:
        """Analyze testing approach."""
        testing = []

        if list(self._repo_path.rglob("test_*.py")) or list(
            self._repo_path.rglob("*_test.py")
        ):
            testing.append("pytest")

        if list(self._repo_path.rglob("*.test.js")) or list(
            self._repo_path.rglob("*.spec.js")
        ):
            testing.append("JavaScript tests")

        if (self._repo_path / "pytest.ini").exists():
            testing.append("pytest configuration")

        return ", ".join(testing) if testing else "Testing setup to be determined"

    def _get_recent_changes(self) -> str:
        """Get information about recent changes."""
        # This is a simplified implementation
        # In a full version, this would analyze git history

        if (self._repo_path / ".git").exists():
            return "Git repository - recent changes can be analyzed from commit history"
        else:
            return "No version control detected"

    def _find_auth_related_files(self) -> list[str]:
        """Find authentication-related files."""
        auth_files = []
        patterns = ["*auth*", "*login*", "*user*", "*session*", "*jwt*"]

        for pattern in patterns:
            files = list(self._repo_path.rglob(pattern))
            auth_files.extend([str(f.relative_to(self._repo_path)) for f in files[:3]])

        return auth_files[:10]

    def _find_api_related_files(self) -> list[str]:
        """Find API-related files."""
        api_files = []
        patterns = ["*api*", "*endpoint*", "*router*", "*handler*"]

        for pattern in patterns:
            files = list(self._repo_path.rglob(pattern))
            api_files.extend([str(f.relative_to(self._repo_path)) for f in files[:3]])

        return api_files[:10]

    def _find_database_related_files(self) -> list[str]:
        """Find database-related files."""
        db_files = []
        patterns = ["*model*", "*migration*", "*schema*", "*.sql", "*database*"]

        for pattern in patterns:
            files = list(self._repo_path.rglob(pattern))
            db_files.extend([str(f.relative_to(self._repo_path)) for f in files[:3]])

        return db_files[:10]
