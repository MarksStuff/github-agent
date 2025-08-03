"""Codebase analyzer for understanding existing code patterns and structure."""

import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class CodebaseAnalyzer:
    """Analyzes existing codebase to provide context for agents."""

    def __init__(self, repo_path: str):
        """Initialize analyzer with repository path.

        Args:
            repo_path: Path to the repository
        """
        self.repo_path = Path(repo_path)
        if not self.repo_path.exists():
            raise ValueError(f"Repository path does not exist: {repo_path}")

        self.analysis_results = {
            "structure": {},
            "patterns": [],
            "technologies": [],
            "test_frameworks": [],
            "dependencies": {},
        }

        logger.info(f"Initialized codebase analyzer for: {repo_path}")

    def analyze(self) -> dict[str, Any]:
        """Perform comprehensive codebase analysis.

        Returns:
            Analysis results dictionary
        """
        logger.info("Starting codebase analysis...")

        # Analyze directory structure
        self._analyze_structure()

        # Detect technologies and frameworks
        self._detect_technologies()

        # Analyze test setup
        self._analyze_test_setup()

        # Identify common patterns
        self._identify_patterns()

        # Get repository info
        self._analyze_git_info()

        logger.info("Codebase analysis complete")
        return self.analysis_results

    def _analyze_structure(self):
        """Analyze directory structure of the codebase."""
        structure = {
            "directories": [],
            "key_files": [],
            "file_count": 0,
            "languages": {},
        }

        # Count files by extension
        for root, dirs, files in os.walk(self.repo_path):
            # Skip hidden directories and common ignore patterns
            dirs[:] = [
                d
                for d in dirs
                if not d.startswith(".")
                and d not in ["node_modules", "__pycache__", "venv", ".venv"]
            ]

            rel_path = Path(root).relative_to(self.repo_path)
            if str(rel_path) != ".":
                structure["directories"].append(str(rel_path))

            for file in files:
                if file.startswith("."):
                    continue

                structure["file_count"] += 1
                ext = Path(file).suffix.lower()

                if ext:
                    structure["languages"][ext] = structure["languages"].get(ext, 0) + 1

                # Track key files
                if file in [
                    "README.md",
                    "setup.py",
                    "requirements.txt",
                    "package.json",
                    "Cargo.toml",
                    "go.mod",
                ]:
                    structure["key_files"].append(
                        str(rel_path / file) if str(rel_path) != "." else file
                    )

        self.analysis_results["structure"] = structure
        logger.info(
            f"Found {structure['file_count']} files across {len(structure['directories'])} directories"
        )

    def _detect_technologies(self):
        """Detect technologies and frameworks used."""
        technologies = []

        # Python detection
        if (self.repo_path / "requirements.txt").exists():
            technologies.append("Python")
            self._parse_requirements()
        elif (self.repo_path / "setup.py").exists():
            technologies.append("Python (setup.py)")
        elif (self.repo_path / "pyproject.toml").exists():
            technologies.append("Python (pyproject.toml)")

        # JavaScript/Node detection
        if (self.repo_path / "package.json").exists():
            technologies.append("JavaScript/Node.js")
            self._parse_package_json()

        # Other language detection
        if (self.repo_path / "Cargo.toml").exists():
            technologies.append("Rust")
        if (self.repo_path / "go.mod").exists():
            technologies.append("Go")
        if (self.repo_path / "pom.xml").exists():
            technologies.append("Java (Maven)")
        if (self.repo_path / "build.gradle").exists():
            technologies.append("Java (Gradle)")

        self.analysis_results["technologies"] = technologies
        logger.info(f"Detected technologies: {', '.join(technologies)}")

    def _analyze_test_setup(self):
        """Analyze testing setup and frameworks."""
        test_frameworks = []

        # Python test frameworks
        if self.analysis_results["technologies"] and "Python" in str(
            self.analysis_results["technologies"]
        ):
            test_dirs = ["tests", "test", "spec"]
            for test_dir in test_dirs:
                if (self.repo_path / test_dir).exists():
                    test_frameworks.append(f"Python tests in {test_dir}/")
                    break

            # Check for specific frameworks in dependencies
            deps = self.analysis_results.get("dependencies", {}).get("python", [])
            if any("pytest" in dep for dep in deps):
                test_frameworks.append("pytest")
            if any("unittest" in dep for dep in deps):
                test_frameworks.append("unittest")

        # JavaScript test frameworks
        if "JavaScript/Node.js" in self.analysis_results.get("technologies", []):
            deps = self.analysis_results.get("dependencies", {}).get("javascript", {})
            dev_deps = deps.get("devDependencies", {})

            if "jest" in dev_deps:
                test_frameworks.append("Jest")
            if "mocha" in dev_deps:
                test_frameworks.append("Mocha")
            if "vitest" in dev_deps:
                test_frameworks.append("Vitest")

        self.analysis_results["test_frameworks"] = test_frameworks
        logger.info(f"Found test frameworks: {', '.join(test_frameworks)}")

    def _identify_patterns(self):
        """Identify common design patterns and conventions."""
        patterns = []

        # Check for MVC/MVP structure
        if all(
            (self.repo_path / d).exists() for d in ["models", "views", "controllers"]
        ):
            patterns.append("MVC Pattern")
        elif all(
            (self.repo_path / d).exists()
            for d in ["src/models", "src/views", "src/controllers"]
        ):
            patterns.append("MVC Pattern (in src)")

        # Check for service layer
        if (self.repo_path / "services").exists() or (
            self.repo_path / "src/services"
        ).exists():
            patterns.append("Service Layer")

        # Check for dependency injection
        if (self.repo_path / "container.py").exists() or (
            self.repo_path / "src/container.py"
        ).exists():
            patterns.append("Dependency Injection")

        # Check for API structure
        if (self.repo_path / "api").exists() or (self.repo_path / "src/api").exists():
            patterns.append("API Layer")

        # Check for configuration management
        if (self.repo_path / "config").exists() or (
            self.repo_path / ".env.example"
        ).exists():
            patterns.append("Configuration Management")

        self.analysis_results["patterns"] = patterns
        logger.info(f"Identified patterns: {', '.join(patterns)}")

    def _parse_requirements(self):
        """Parse Python requirements.txt."""
        try:
            with open(self.repo_path / "requirements.txt") as f:
                requirements = [
                    line.strip()
                    for line in f
                    if line.strip() and not line.startswith("#")
                ]
                self.analysis_results["dependencies"]["python"] = requirements
                logger.info(f"Found {len(requirements)} Python dependencies")
        except Exception as e:
            logger.warning(f"Failed to parse requirements.txt: {e}")

    def _parse_package_json(self):
        """Parse package.json for JavaScript dependencies."""
        try:
            with open(self.repo_path / "package.json") as f:
                package_data = json.load(f)

                deps = {
                    "dependencies": list(package_data.get("dependencies", {}).keys()),
                    "devDependencies": list(
                        package_data.get("devDependencies", {}).keys()
                    ),
                }

                self.analysis_results["dependencies"]["javascript"] = deps
                total_deps = len(deps["dependencies"]) + len(deps["devDependencies"])
                logger.info(f"Found {total_deps} JavaScript dependencies")
        except Exception as e:
            logger.warning(f"Failed to parse package.json: {e}")

    def _analyze_git_info(self):
        """Get git repository information."""
        try:
            # Get current branch
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True,
            )
            self.analysis_results["git_branch"] = result.stdout.strip()

            # Get current commit
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True,
            )
            self.analysis_results["git_commit"] = result.stdout.strip()

            # Get repository name from remote
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True,
            )
            remote_url = result.stdout.strip()
            # Extract repo name from URL
            if "github.com" in remote_url:
                parts = remote_url.split("/")
                if len(parts) >= 2:
                    owner = parts[-2].split(":")[-1]
                    repo = parts[-1].replace(".git", "")
                    self.analysis_results["repository"] = f"{owner}/{repo}"

        except subprocess.CalledProcessError as e:
            logger.warning(f"Failed to get git info: {e}")

    def generate_summary(self) -> str:
        """Generate a human-readable summary of the analysis.

        Returns:
            Summary string
        """
        results = self.analysis_results
        structure = results.get("structure", {})

        summary_parts = [
            f"Repository: {results.get('repository', 'Unknown')}",
            f"Branch: {results.get('git_branch', 'Unknown')}",
            f"Total files: {structure.get('file_count', 0)}",
            f"Directories: {len(structure.get('directories', []))}",
            f"Technologies: {', '.join(results.get('technologies', []))}",
            f"Test frameworks: {', '.join(results.get('test_frameworks', []))}",
            f"Patterns: {', '.join(results.get('patterns', []))}",
        ]

        # Add language breakdown
        languages = structure.get("languages", {})
        if languages:
            lang_summary = ", ".join(
                [
                    f"{ext}: {count}"
                    for ext, count in sorted(
                        languages.items(), key=lambda x: x[1], reverse=True
                    )[:5]
                ]
            )
            summary_parts.append(f"Top languages: {lang_summary}")

        return "\n".join(summary_parts)
