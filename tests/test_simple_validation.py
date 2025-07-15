#!/usr/bin/env python3

"""
Tests for Simple Validation Functions

This module contains tests for the simple validation approach using
direct function calls in github_tools.py and codebase_tools.py.
"""

import asyncio
import json
import logging
import os
import tempfile
import unittest
from unittest.mock import Mock, patch

import pytest

import codebase_tools
import github_tools
from constants import Language
from tests.conftest import MockLSPClient, MockSymbolStorage
from tests.test_fixtures import MockRepositoryManager


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


# Pytest-based tests for codebase validation functions
def test_codebase_validate_empty_repos(codebase_tools_factory):
    """Test codebase validation with empty repositories."""
    # Create CodebaseTools instance with no repositories
    codebase_tools = codebase_tools_factory()
    
    # Should return error when trying to check non-existent repository
    result = asyncio.run(codebase_tools.codebase_health_check("nonexistent"))
    result_data = json.loads(result)
    assert result_data["status"] == "error"
    assert "not found" in result_data["error"]

def test_codebase_validate_with_valid_repo(codebase_tools_factory):
    """Test codebase validation with a valid repository."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a git repository
        git_dir = os.path.join(temp_dir, ".git")
        os.makedirs(git_dir)
        
        # Mock repository config
        mock_repo_config = Mock()
        mock_repo_config.workspace = temp_dir
        mock_repo_config.language = Language.PYTHON
        repositories = {"test_repo": mock_repo_config}

        # Create CodebaseTools instance with valid repository
        codebase_tools = codebase_tools_factory(repositories=repositories)
        
        # Should pass health check for valid repository
        result = asyncio.run(codebase_tools.codebase_health_check("test_repo"))
        result_data = json.loads(result)
        assert result_data["status"] == "healthy"
        assert result_data["repository_id"] == "test_repo"

def test_codebase_validate_workspace_not_accessible(codebase_tools_factory):
    """Test codebase validation with inaccessible workspace."""
    # Mock repository config with non-existent workspace
    mock_repo_config = Mock()
    mock_repo_config.workspace = "/nonexistent/path"
    mock_repo_config.language = Language.PYTHON
    repositories = {"test_repo": mock_repo_config}

    # Create CodebaseTools instance with invalid repository
    codebase_tools = codebase_tools_factory(repositories=repositories)
    
    # Should return error for non-existent workspace
    result = asyncio.run(codebase_tools.codebase_health_check("test_repo"))
    result_data = json.loads(result)
    assert result_data["status"] == "error"
    assert "does not exist" in result_data["message"]

def test_codebase_validate_not_git_repo(codebase_tools_factory):
    """Test codebase validation when directory is not a git repository."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Mock repository config
        mock_repo_config = Mock()
        mock_repo_config.workspace = temp_dir
        mock_repo_config.language = Language.PYTHON
        repositories = {"test_repo": mock_repo_config}

        # Create CodebaseTools instance with non-git repository
        codebase_tools = codebase_tools_factory(repositories=repositories)
        
        # Should return warning for non-git repository
        result = asyncio.run(codebase_tools.codebase_health_check("test_repo"))
        result_data = json.loads(result)
        assert result_data["status"] == "warning"
        assert "not a Git repository" in result_data["message"]

def test_validate_symbol_storage_success_with_mock(codebase_tools_factory):
    """Test symbol storage health check succeeds when health_check returns True."""
    # Create CodebaseTools instance with mock symbol storage
    codebase_tools = codebase_tools_factory()
    
    # Set mock to return True for health_check
    codebase_tools.symbol_storage.set_health_check_result(True)
    
    # Health check should succeed
    assert codebase_tools.symbol_storage.health_check()

def test_validate_symbol_storage_failure_with_mock(codebase_tools_factory):
    """Test symbol storage health check fails when health_check returns False."""
    # Create CodebaseTools instance with mock symbol storage
    codebase_tools = codebase_tools_factory()
    
    # Set mock to return False for health_check
    codebase_tools.symbol_storage.set_health_check_result(False)
    
    # Health check should fail
    assert not codebase_tools.symbol_storage.health_check()

def test_validate_symbol_storage_success_with_real_storage(codebase_tools_factory):
    """Test symbol storage health check succeeds with real SQLiteSymbolStorage."""
    # This test assumes SQLite is available in the development environment
    # It tests the real storage connection without mocking
    try:
        # Create CodebaseTools instance with real SQLiteSymbolStorage (in-memory)
        codebase_tools = codebase_tools_factory(use_real_symbol_storage=True)
        
        # Health check should succeed
        assert codebase_tools.symbol_storage.health_check()
        
    except RuntimeError as e:
        # If it fails, make sure it's not due to import issues
        assert "not available" not in str(e)
        # Re-raise if it's a connection issue (which is valid)
        if "connection failed" in str(e):
            # This could happen in some environments, so we'll skip
            pytest.skip(f"SQLite connection failed in test environment: {e}")
        else:
            raise


# Integration tests for validation functions
def test_validation_integration_success(codebase_tools_factory):
    """Test successful validation of both GitHub and codebase services."""
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    
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
            github_tools.validate(logger, repositories)

            # Test codebase validation - create instance and run health check
            codebase_tools = codebase_tools_factory(repositories=repositories)
            
            result = asyncio.run(codebase_tools.codebase_health_check("test_repo"))
            result_data = json.loads(result)
            assert result_data["status"] == "healthy"

def test_validation_order_independence(codebase_tools_factory):
    """Test that validation order doesn't matter."""
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    
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
            codebase_tools = codebase_tools_factory(repositories=repositories)
            
            result = asyncio.run(codebase_tools.codebase_health_check("test_repo"))
            result_data = json.loads(result)
            assert result_data["status"] == "healthy"
            
            github_tools.validate(logger, repositories)


if __name__ == "__main__":
    unittest.main()
