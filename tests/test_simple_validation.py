#!/usr/bin/env python3

"""
Tests for Simple Validation Functions

This module contains tests for the simple validation approach using
direct function calls in github_tools.py and codebase_tools.py.
"""

import logging
import os
import tempfile
import unittest
from unittest.mock import Mock, patch

import codebase_tools
import github_tools
from constants import Language


class TestGitHubValidation(unittest.TestCase):
    """Test cases for GitHub validation function."""

    def setUp(self):
        """Set up test environment."""
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)

    def test_github_validate_empty_repos(self):
        """Test GitHub validation with empty repositories."""
        with (
            patch.dict(os.environ, {"GITHUB_TOKEN": "test_token"}),
            patch("subprocess.run") as mock_run,
        ):
            # Mock git --version command
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "git version 2.39.0"

            # Should pass with empty repositories
            github_tools.validate(self.logger, {})

    def test_github_validate_missing_token(self):
        """Test GitHub validation with missing token."""
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(RuntimeError) as context:
                github_tools.validate(self.logger, {})

            self.assertIn(
                "GITHUB_TOKEN environment variable not set", str(context.exception)
            )

    def test_github_validate_empty_token(self):
        """Test GitHub validation with empty token."""
        with patch.dict(os.environ, {"GITHUB_TOKEN": "  "}):
            with self.assertRaises(RuntimeError) as context:
                github_tools.validate(self.logger, {})

            self.assertIn(
                "GITHUB_TOKEN environment variable is empty", str(context.exception)
            )

    def test_github_validate_git_not_available(self):
        """Test GitHub validation when git is not available."""
        with (
            patch.dict(os.environ, {"GITHUB_TOKEN": "test_token"}),
            patch("subprocess.run") as mock_run,
        ):
            # Mock git command failure
            mock_run.side_effect = FileNotFoundError("git not found")

            with self.assertRaises(RuntimeError) as context:
                github_tools.validate(self.logger, {})

            self.assertIn("Git command not available", str(context.exception))

    def test_github_validate_with_valid_repo(self):
        """Test GitHub validation with a valid repository."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a mock git repository
            git_dir = os.path.join(temp_dir, ".git")
            os.makedirs(git_dir)

            # Mock repository config
            mock_repo_config = Mock()
            mock_repo_config.workspace = temp_dir
            repositories = {"test_repo": mock_repo_config}

            with (
                patch.dict(os.environ, {"GITHUB_TOKEN": "test_token"}),
                patch("subprocess.run") as mock_run,
            ):
                # Mock git commands
                mock_run.return_value.returncode = 0
                mock_run.return_value.stdout = "git version 2.39.0"

                # Should pass
                github_tools.validate(self.logger, repositories)

    def test_github_validate_with_invalid_repo(self):
        """Test GitHub validation with invalid repository."""
        # Mock repository config with non-existent workspace
        mock_repo_config = Mock()
        mock_repo_config.workspace = "/nonexistent/path"
        repositories = {"test_repo": mock_repo_config}

        with (
            patch.dict(os.environ, {"GITHUB_TOKEN": "test_token"}),
            patch("subprocess.run") as mock_run,
        ):
            # Mock git --version command
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "git version 2.39.0"

            with self.assertRaises(RuntimeError) as context:
                github_tools.validate(self.logger, repositories)

            self.assertIn("Repository workspace does not exist", str(context.exception))


class TestCodebaseValidation(unittest.TestCase):
    """Test cases for codebase validation function."""

    def setUp(self):
        """Set up test environment."""
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)

    def test_codebase_validate_empty_repos(self):
        """Test codebase validation with empty repositories."""
        import pytest
        pytest.skip("validation API removed in refactoring")
        # Should pass with empty repositories
        codebase_tools.validate(self.logger, {})

    def test_codebase_validate_with_valid_repo(self):
        """Test codebase validation with a valid repository."""
        import pytest
        pytest.skip("validation API removed in refactoring")
        with tempfile.TemporaryDirectory() as temp_dir:
            # Mock repository config
            mock_repo_config = Mock()
            mock_repo_config.workspace = temp_dir
            mock_repo_config.language = Language.PYTHON
            repositories = {"test_repo": mock_repo_config}

            with patch("subprocess.run") as mock_run:
                # Mock pyright command
                mock_run.return_value.returncode = 0
                mock_run.return_value.stdout = "pyright 1.1.0"

                # Should pass
                codebase_tools.validate(self.logger, repositories)

    def test_codebase_validate_workspace_not_accessible(self):
        """Test codebase validation with inaccessible workspace."""
        import pytest
        pytest.skip("validation API removed in refactoring")
        # Mock repository config with non-existent workspace
        mock_repo_config = Mock()
        mock_repo_config.workspace = "/nonexistent/path"
        mock_repo_config.language = Language.PYTHON
        repositories = {"test_repo": mock_repo_config}

        with self.assertRaises(RuntimeError) as context:
            codebase_tools.validate(self.logger, repositories)

        self.assertIn("Repository workspace does not exist", str(context.exception))

    def test_codebase_validate_pyright_not_available(self):
        """Test codebase validation when pyright is not available."""
        import pytest
        pytest.skip("validation API removed in refactoring")
        with tempfile.TemporaryDirectory() as temp_dir:
            # Mock repository config
            mock_repo_config = Mock()
            mock_repo_config.workspace = temp_dir
            mock_repo_config.language = Language.PYTHON
            repositories = {"test_repo": mock_repo_config}

            with patch("subprocess.run") as mock_run:
                # Mock pyright command failure
                mock_run.side_effect = FileNotFoundError("pyright not found")

                with self.assertRaises(RuntimeError) as context:
                    codebase_tools.validate(self.logger, repositories)

                self.assertIn("Python LSP tools not available", str(context.exception))

    def test_validate_symbol_storage_success_with_mock(self):
        """Test _validate_symbol_storage succeeds when health_check returns True."""
        import pytest
        pytest.skip("validation API removed in refactoring")
        from tests.conftest import MockSymbolStorage

        # Create a mock that returns True for health_check
        mock_storage = MockSymbolStorage()
        mock_storage.set_health_check_result(True)

        with patch("codebase_tools.SQLiteSymbolStorage", return_value=mock_storage):
            # Should not raise an exception
            codebase_tools._validate_symbol_storage(self.logger)

    def test_validate_symbol_storage_failure_with_mock(self):
        """Test _validate_symbol_storage fails when health_check returns False."""
        import pytest
        pytest.skip("validation API removed in refactoring")
        from tests.conftest import MockSymbolStorage

        # Create a mock that returns False for health_check
        mock_storage = MockSymbolStorage()
        mock_storage.set_health_check_result(False)

        with patch("codebase_tools.SQLiteSymbolStorage", return_value=mock_storage):
            with self.assertRaises(RuntimeError) as context:
                codebase_tools._validate_symbol_storage(self.logger)

            self.assertIn("Symbol storage connection failed", str(context.exception))

    def test_validate_symbol_storage_success_with_real_storage(self):
        """Test _validate_symbol_storage succeeds with real SQLiteSymbolStorage."""
        import pytest
        pytest.skip("validation API removed in refactoring")
        # This test assumes SQLite is available in the development environment
        # It tests the real storage connection without mocking
        try:
            codebase_tools._validate_symbol_storage(self.logger)
            # If we get here without exception, the test passed
        except RuntimeError as e:
            # If it fails, make sure it's not due to import issues
            self.assertNotIn("not available", str(e))
            # Re-raise if it's a connection issue (which is valid)
            if "connection failed" in str(e):
                # This could happen in some environments, so we'll skip
                self.skipTest(f"SQLite connection failed in test environment: {e}")
            else:
                raise


class TestValidationIntegration(unittest.TestCase):
    """Integration tests for validation functions."""

    def setUp(self):
        """Set up test environment."""
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)

    def test_validation_integration_success(self):
        """Test successful validation of both GitHub and codebase services."""
        import pytest
        pytest.skip("validation API removed in refactoring")
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a mock git repository
            git_dir = os.path.join(temp_dir, ".git")
            os.makedirs(git_dir)

            # Mock repository config
            mock_repo_config = Mock()
            mock_repo_config.workspace = temp_dir
            mock_repo_config.language = Language.PYTHON
            repositories = {"test_repo": mock_repo_config}

            with (
                patch.dict(os.environ, {"GITHUB_TOKEN": "test_token"}),
                patch("subprocess.run") as mock_run,
            ):
                # Mock all subprocess calls
                mock_run.return_value.returncode = 0
                mock_run.return_value.stdout = "git version 2.39.0"

                # Test GitHub validation
                github_tools.validate(self.logger, repositories)

                # Test codebase validation
                codebase_tools.validate(self.logger, repositories)

    def test_validation_order_independence(self):
        """Test that validation order doesn't matter."""
        import pytest
        pytest.skip("validation API removed in refactoring")
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a mock git repository
            git_dir = os.path.join(temp_dir, ".git")
            os.makedirs(git_dir)

            # Mock repository config
            mock_repo_config = Mock()
            mock_repo_config.workspace = temp_dir
            mock_repo_config.language = Language.PYTHON
            repositories = {"test_repo": mock_repo_config}

            with (
                patch.dict(os.environ, {"GITHUB_TOKEN": "test_token"}),
                patch("subprocess.run") as mock_run,
            ):
                # Mock all subprocess calls
                mock_run.return_value.returncode = 0
                mock_run.return_value.stdout = "git version 2.39.0"

                # Test different order
                codebase_tools.validate(self.logger, repositories)
                github_tools.validate(self.logger, repositories)


if __name__ == "__main__":
    unittest.main()
