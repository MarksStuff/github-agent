#!/usr/bin/env python3

"""
Tests for missing CodebaseTools methods
Tests for find_hover and shutdown methods that were not covered in other test files.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch

import pytest

from codebase_tools import CodebaseTools
from constants import Language
from tests.conftest import MockLSPClient


class TestCodebaseToolsMissingMethods:
    """Test cases for CodebaseTools methods that need additional coverage."""

    @pytest.mark.asyncio
    async def test_find_hover_success(self, codebase_tools_factory):
        """Test successful hover information retrieval."""
        # Create mock LSP client with hover response
        mock_lsp_client = Mock()
        mock_hover_response = {
            "contents": {
                "kind": "markdown",
                "value": "```python\ndef hello_world() -> str\n```\nA simple hello world function."
            },
            "range": {
                "start": {"line": 0, "character": 0},
                "end": {"line": 0, "character": 11}
            }
        }
        # Configure mock to return hover response
        mock_lsp_client.get_hover = AsyncMock(return_value=mock_hover_response)

        # Create temporary repository
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            
            # Create .git directory
            git_dir = repo_path / ".git"
            git_dir.mkdir()
            
            # Create test file
            test_file = repo_path / "test.py"
            test_file.write_text("def hello_world():\n    return 'Hello, World!'\n")

            # Create CodebaseTools instance
            from repository_manager import RepositoryConfig
            
            repo_config = RepositoryConfig.create_repository_config(
                name="test-repo",
                workspace=str(repo_path),
                description="Test repository",
                language=Language.PYTHON,
                port=8080,
                python_path="/usr/bin/python3",
            )
            repositories = {"test-repo": repo_config}
            
            tools = codebase_tools_factory(repositories=repositories)
            
            # Mock SimpleLSPClient constructor since find_hover creates it directly
            with patch('codebase_tools.SimpleLSPClient', return_value=mock_lsp_client):
                # Test hover request
                result_json = await tools.find_hover(
                    repository_id="test-repo",
                    file_path="test.py",
                    line=1,
                    character=5
                )
                result = json.loads(result_json)

                # Verify result
                assert "hover_info" in result
                assert result["file_path"] == "test.py"
                assert result["line"] == 1
                assert result["character"] == 5
                assert result["repository_id"] == "test-repo"
                assert result["hover_info"] == mock_hover_response

    @pytest.mark.asyncio
    async def test_find_hover_repo_not_found(self, codebase_tools_factory):
        """Test hover request for non-existent repository."""
        tools = codebase_tools_factory(repositories={})
        
        result_json = await tools.find_hover(
            repository_id="non-existent",
            file_path="test.py",
            line=1,
            character=5
        )
        result = json.loads(result_json)

        # Verify error response
        assert "error" in result
        assert "Repository 'non-existent' not found" in result["error"]
        assert result["file_path"] == "test.py"
        assert result["line"] == 1
        assert result["character"] == 5

    @pytest.mark.asyncio
    async def test_find_hover_no_hover_info(self, codebase_tools_factory):
        """Test hover request when no hover information is available."""
        # Create mock LSP client with no hover response
        mock_lsp_client = Mock()
        mock_lsp_client.get_hover = AsyncMock(return_value=None)

        # Create temporary repository
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            
            # Create .git directory
            git_dir = repo_path / ".git"
            git_dir.mkdir()
            
            # Create test file
            test_file = repo_path / "test.py"
            test_file.write_text("# Empty comment line\n")

            # Create CodebaseTools instance
            from repository_manager import RepositoryConfig
            
            repo_config = RepositoryConfig.create_repository_config(
                name="test-repo",
                workspace=str(repo_path),
                description="Test repository",
                language=Language.PYTHON,
                port=8080,
                python_path="/usr/bin/python3",
            )
            repositories = {"test-repo": repo_config}
            
            tools = codebase_tools_factory(repositories=repositories)
            
            # Mock SimpleLSPClient constructor since find_hover creates it directly
            with patch('codebase_tools.SimpleLSPClient', return_value=mock_lsp_client):
                # Test hover request
                result_json = await tools.find_hover(
                    repository_id="test-repo",
                    file_path="test.py",
                    line=1,
                    character=1
                )
                result = json.loads(result_json)

                # Verify result shows no hover info
                assert "message" in result
                assert "No hover information available" in result["message"]
                assert result["file_path"] == "test.py"
                assert result["line"] == 1
                assert result["character"] == 1

    @pytest.mark.asyncio
    async def test_find_hover_file_not_found(self, codebase_tools_factory):
        """Test hover request for non-existent file."""
        # Create temporary repository without the test file
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            
            # Create .git directory
            git_dir = repo_path / ".git"
            git_dir.mkdir()

            # Create CodebaseTools instance
            from repository_manager import RepositoryConfig
            
            repo_config = RepositoryConfig.create_repository_config(
                name="test-repo",
                workspace=str(repo_path),
                description="Test repository",
                language=Language.PYTHON,
                port=8080,
                python_path="/usr/bin/python3",
            )
            repositories = {"test-repo": repo_config}
            
            tools = codebase_tools_factory(repositories=repositories)

            # Test hover request for non-existent file
            result_json = await tools.find_hover(
                repository_id="test-repo",
                file_path="nonexistent.py",
                line=1,
                character=1
            )
            result = json.loads(result_json)

            # Verify error response
            assert "error" in result
            assert "Hover request failed" in result["error"]
            assert result["file_path"] == "nonexistent.py"
            assert result["line"] == 1
            assert result["character"] == 1

    @pytest.mark.asyncio
    async def test_find_hover_lsp_error(self, codebase_tools_factory):
        """Test hover request when LSP client raises an error."""
        # Create mock LSP client that raises an exception
        mock_lsp_client = Mock()
        mock_lsp_client.get_hover = AsyncMock(side_effect=Exception("LSP communication error"))

        # Create temporary repository
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            
            # Create .git directory
            git_dir = repo_path / ".git"
            git_dir.mkdir()
            
            # Create test file
            test_file = repo_path / "test.py"
            test_file.write_text("def hello_world():\n    return 'Hello, World!'\n")

            # Create CodebaseTools instance
            from repository_manager import RepositoryConfig
            
            repo_config = RepositoryConfig.create_repository_config(
                name="test-repo",
                workspace=str(repo_path),
                description="Test repository",
                language=Language.PYTHON,
                port=8080,
                python_path="/usr/bin/python3",
            )
            repositories = {"test-repo": repo_config}
            
            tools = codebase_tools_factory(repositories=repositories)
            
            # Mock SimpleLSPClient constructor since find_hover creates it directly
            with patch('codebase_tools.SimpleLSPClient', return_value=mock_lsp_client):
                # Test hover request
                result_json = await tools.find_hover(
                    repository_id="test-repo",
                    file_path="test.py",
                    line=1,
                    character=5
                )
                result = json.loads(result_json)

                # Verify error response
                assert "error" in result
                assert "Hover request failed" in result["error"]
                assert "LSP communication error" in result["error"]

    @pytest.mark.asyncio
    async def test_shutdown_success(self, codebase_tools_factory):
        """Test successful CodebaseTools shutdown."""
        tools = codebase_tools_factory(repositories={})
        
        # Verify shutdown completes without error
        try:
            await tools.shutdown()
            # If we reach here, shutdown was successful
            assert True
        except Exception as e:
            pytest.fail(f"Shutdown should not raise an exception: {e}")

    @pytest.mark.asyncio
    async def test_shutdown_logs_message(self, codebase_tools_factory, caplog):
        """Test that shutdown logs appropriate message."""
        tools = codebase_tools_factory(repositories={})
        
        # Capture log output
        with caplog.at_level("INFO"):
            await tools.shutdown()
        
        # Verify log message
        assert any(
            "CodebaseTools shutdown" in record.message
            for record in caplog.records
        )
        assert any(
            "SimpleLSPClient instances are stateless" in record.message
            for record in caplog.records
        )

    @pytest.mark.asyncio
    async def test_shutdown_multiple_calls(self, codebase_tools_factory):
        """Test that multiple shutdown calls are safe."""
        tools = codebase_tools_factory(repositories={})
        
        # Call shutdown multiple times - should not raise errors
        try:
            await tools.shutdown()
            await tools.shutdown()
            await tools.shutdown()
            assert True
        except Exception as e:
            pytest.fail(f"Multiple shutdown calls should be safe: {e}")

    @pytest.mark.asyncio
    async def test_execute_tool_find_hover(self, codebase_tools_factory):
        """Test executing find_hover through the execute_tool interface."""
        # Create mock LSP client with hover response
        mock_lsp_client = Mock()
        mock_hover_response = {
            "contents": {
                "kind": "markdown", 
                "value": "```python\ndef test_func() -> None\n```\nTest function."
            }
        }
        mock_lsp_client.get_hover = AsyncMock(return_value=mock_hover_response)

        # Create temporary repository
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            
            # Create .git directory
            git_dir = repo_path / ".git"
            git_dir.mkdir()
            
            # Create test file
            test_file = repo_path / "test.py"
            test_file.write_text("def test_func():\n    pass\n")

            # Create CodebaseTools instance
            from repository_manager import RepositoryConfig
            
            repo_config = RepositoryConfig.create_repository_config(
                name="test-repo",
                workspace=str(repo_path),
                description="Test repository",
                language=Language.PYTHON,
                port=8080,
                python_path="/usr/bin/python3",
            )
            repositories = {"test-repo": repo_config}
            
            tools = codebase_tools_factory(repositories=repositories)
            
            # Mock SimpleLSPClient constructor since find_hover creates it directly
            with patch('codebase_tools.SimpleLSPClient', return_value=mock_lsp_client):
                # Test executing find_hover through execute_tool
                result_json = await tools.execute_tool(
                    "find_hover",
                    repository_id="test-repo",
                    file_path="test.py",
                    line=1,
                    character=5
                )
                result = json.loads(result_json)

                # Verify result
                assert "hover_info" in result
                assert result["repository_id"] == "test-repo"
                assert result["hover_info"] == mock_hover_response


if __name__ == "__main__":
    pytest.main([__file__])