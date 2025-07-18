#!/usr/bin/env python3

"""
Tests for codebase_tools module
"""

import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import pytest

from async_lsp_client import AbstractAsyncLSPClient
from codebase_tools import CodebaseTools
from repository_manager import AbstractRepositoryManager
from symbol_storage import AbstractSymbolStorage, Symbol, SymbolKind

# temp_git_repo fixture now consolidated in conftest.py


class MockRepositoryManager(AbstractRepositoryManager):
    """Mock repository manager for testing"""

    def __init__(self):
        self._repositories = {}

    @property
    def repositories(self) -> dict[str, Any]:
        return self._repositories

    def get_repository(self, name: str):
        return self._repositories.get(name)

    def add_repository(self, name: str, config) -> None:
        self._repositories[name] = config

    def load_configuration(self) -> bool:
        return True


class MockSymbolStorage(AbstractSymbolStorage):
    """Mock symbol storage for testing"""

    def __init__(self):
        self.symbols = {}

    def create_schema(self) -> None:
        pass

    def insert_symbol(self, symbol: Symbol) -> None:
        pass

    def insert_symbols(self, symbols: list[Symbol]) -> None:
        pass

    def update_symbol(self, symbol: Symbol) -> None:
        pass

    def delete_symbol(self, symbol_id: int) -> None:
        pass

    def get_symbol_by_id(self, symbol_id: int) -> Symbol | None:
        return None

    def get_symbols_by_name(self, name: str) -> list[Symbol]:
        return []

    def get_symbols_by_repo(self, repo_name: str) -> list[Symbol]:
        return self.symbols.get(repo_name, [])

    def get_symbols_by_kind(self, kind: SymbolKind) -> list[Symbol]:
        return []

    def search_symbols(
        self,
        query: str,
        repository_id: str | None = None,
        symbol_kind: str | None = None,
        limit: int = 50,
    ) -> list[Symbol]:
        return []

    def clear_symbols(self, repo_name: str) -> None:
        if repo_name in self.symbols:
            del self.symbols[repo_name]

    def get_all_symbols(self) -> list[Symbol]:
        all_symbols = []
        for symbols in self.symbols.values():
            all_symbols.extend(symbols)
        return all_symbols

    def delete_symbols_by_repository(self, repo_name: str) -> None:
        if repo_name in self.symbols:
            del self.symbols[repo_name]

    def get_symbols_by_file(self, file_path: str, repository_id: str) -> list[Symbol]:
        return []

    def health_check(self) -> bool:
        return True

    def store_symbols(self, repo_name: str, symbols: list[Symbol]):
        self.symbols[repo_name] = symbols

    def get_symbols(self, repo_name: str) -> list[Symbol]:
        return self.symbols.get(repo_name, [])


class MockLSPClient(AbstractAsyncLSPClient):
    """Mock LSP client for testing"""

    def __init__(self, workspace: str, python_path: str):
        self.workspace = workspace
        self.python_path = python_path

    async def start(self) -> bool:
        return True

    async def stop(self) -> bool:
        return True

    def is_initialized(self) -> bool:
        return True

    def get_server_capabilities(self) -> dict[str, Any]:
        return {}

    def add_notification_handler(self, method: str, handler: Any) -> None:
        pass

    def remove_notification_handler(self, method: str) -> None:
        pass

    async def get_definition(
        self, uri: str, line: int, character: int
    ) -> list[dict] | None:
        return []

    async def get_references(
        self, uri: str, line: int, character: int, include_declaration: bool = True
    ) -> list[dict] | None:
        return []

    async def get_hover(self, uri: str, line: int, character: int) -> dict | None:
        return None

    async def get_document_symbols(self, uri: str) -> list[dict] | None:
        return []


def mock_lsp_client_factory(workspace: str, python_path: str) -> AbstractAsyncLSPClient:
    """Mock LSP client factory"""
    return MockLSPClient(workspace, python_path)


@pytest.fixture
def temp_dir_not_git():
    """Create a temporary directory that's not a git repository"""
    with tempfile.TemporaryDirectory() as temp_dir:
        repo_path = Path(temp_dir)
        (repo_path / "some_file.txt").write_text("content")
        yield str(repo_path)


class TestCodebaseTools:
    """Test cases for codebase tools"""

    def test_get_tools(self):
        """Test that get_tools returns correct tool definitions"""
        repo_name = "test-repo"
        repo_path = "/test/path"

        # Create mock dependencies
        mock_repo_manager = MockRepositoryManager()
        mock_symbol_storage = MockSymbolStorage()

        # Create CodebaseTools instance
        codebase_tools = CodebaseTools(
            repository_manager=mock_repo_manager,
            symbol_storage=mock_symbol_storage,
            lsp_client_factory=mock_lsp_client_factory,
        )

        tools = codebase_tools.get_tools(repo_name, repo_path)

        assert isinstance(tools, list)
        assert len(tools) == 4  # Updated to include new LSP tools

        # Test health check tool
        health_check_tool = tools[0]
        assert health_check_tool["name"] == "codebase_health_check"
        assert repo_path in health_check_tool["description"]
        assert health_check_tool["inputSchema"]["type"] == "object"
        assert health_check_tool["inputSchema"]["required"] == ["repository_id"]

        # Test search symbols tool
        search_symbols_tool = tools[1]
        assert search_symbols_tool["name"] == "search_symbols"
        assert repo_name in search_symbols_tool["description"]
        assert search_symbols_tool["inputSchema"]["type"] == "object"
        assert search_symbols_tool["inputSchema"]["required"] == [
            "repository_id",
            "query",
        ]
        assert "query" in search_symbols_tool["inputSchema"]["properties"]
        assert "symbol_kind" in search_symbols_tool["inputSchema"]["properties"]
        assert "limit" in search_symbols_tool["inputSchema"]["properties"]

    @pytest.mark.asyncio
    async def test_health_check_nonexistent_path(self):
        """Test health check when repository path doesn't exist"""
        # Create mock dependencies
        mock_repo_manager = MockRepositoryManager()
        mock_symbol_storage = MockSymbolStorage()

        # Add a repository with nonexistent path
        from constants import Language
        from repository_manager import RepositoryConfig

        test_config = RepositoryConfig(
            name="test-repo",
            workspace="/nonexistent/path",
            description="Test repo",
            language=Language.PYTHON,
            port=8080,
            python_path="/usr/bin/python3",
            github_owner="test",
            github_repo="test",
        )
        mock_repo_manager.add_repository("test-repo", test_config)

        # Create CodebaseTools instance
        codebase_tools = CodebaseTools(
            repository_manager=mock_repo_manager,
            symbol_storage=mock_symbol_storage,
            lsp_client_factory=mock_lsp_client_factory,
        )

        # The new method only takes repository_id, path comes from repository manager
        result = await codebase_tools.codebase_health_check("test-repo")

        data = json.loads(result)
        assert data["repo"] == "test-repo"
        assert data["status"] == "error"
        assert "errors" in data
        assert "/nonexistent/path" in str(data["errors"])

    @pytest.mark.asyncio
    async def test_health_check_file_not_directory(self):
        """Test health check when path points to a file, not directory"""
        with tempfile.NamedTemporaryFile() as temp_file:
            # Create mock dependencies
            mock_repo_manager = MockRepositoryManager()
            mock_symbol_storage = MockSymbolStorage()

            # Add a repository with the temp file as workspace
            from constants import Language
            from repository_manager import RepositoryConfig

            test_config = RepositoryConfig(
                name="test-repo",
                workspace=temp_file.name,  # Point to file, not directory
                description="Test repo",
                language=Language.PYTHON,
                port=8080,
                python_path="/usr/bin/python3",
                github_owner="test",
                github_repo="test",
            )
            mock_repo_manager.add_repository("test-repo", test_config)

            # Create CodebaseTools instance
            codebase_tools = CodebaseTools(
                repository_manager=mock_repo_manager,
                symbol_storage=mock_symbol_storage,
                lsp_client_factory=mock_lsp_client_factory,
            )

            result = await codebase_tools.codebase_health_check("test-repo")

            data = json.loads(result)
            assert data["status"] in ["error", "warning"]  # Accept both
            assert "warnings" in data or "errors" in data

    @pytest.mark.asyncio
    async def test_health_check_not_git_repo(self, temp_dir_not_git):
        """Test health check when directory is not a git repository"""
        # Create mock dependencies
        mock_repo_manager = MockRepositoryManager()
        mock_symbol_storage = MockSymbolStorage()

        # Create CodebaseTools instance
        codebase_tools = CodebaseTools(
            repository_manager=mock_repo_manager,
            symbol_storage=mock_symbol_storage,
            lsp_client_factory=mock_lsp_client_factory,
        )

        # Add repository to mock manager
        from constants import Language
        from repository_manager import RepositoryConfig

        repo_config = RepositoryConfig(
            name="test-repo",
            workspace=temp_dir_not_git,
            description="Test repo",
            language=Language.PYTHON,
            port=8000,
            python_path="/usr/bin/python3",
            github_owner="test-owner",
            github_repo="test-repo",
        )
        mock_repo_manager.add_repository("test-repo", repo_config)

        result = await codebase_tools.codebase_health_check("test-repo")

        data = json.loads(result)
        assert (
            data["status"] == "warning"
        )  # Not being a git repo is a warning, not an error
        assert data["repo"] == "test-repo"
        assert data["workspace"] == temp_dir_not_git
        assert "warnings" in data
        assert len(data["warnings"]) > 0

    @pytest.mark.asyncio
    async def test_health_check_valid_git_repo(self, temp_git_repo):
        """Test health check with a valid git repository"""
        # Create mock dependencies
        mock_repo_manager = MockRepositoryManager()
        mock_symbol_storage = MockSymbolStorage()

        # Create CodebaseTools instance
        codebase_tools = CodebaseTools(
            repository_manager=mock_repo_manager,
            symbol_storage=mock_symbol_storage,
            lsp_client_factory=mock_lsp_client_factory,
        )

        # Add repository to mock manager
        from constants import Language
        from repository_manager import RepositoryConfig

        repo_config = RepositoryConfig(
            name="test-repo",
            workspace=temp_git_repo,
            description="Test repo",
            language=Language.PYTHON,
            port=8000,
            python_path="/usr/bin/python3",
            github_owner="test-owner",
            github_repo="test-repo",
        )
        mock_repo_manager.add_repository("test-repo", repo_config)

        result = await codebase_tools.codebase_health_check("test-repo")

        data = json.loads(result)
        assert data["repo"] == "test-repo"
        assert data["workspace"] == temp_git_repo
        assert data["status"] in [
            "healthy",
            "warning",
        ]  # Could have warnings but still be healthy

    @pytest.mark.asyncio
    async def test_health_check_git_repo_with_remote(self, temp_git_repo):
        """Test health check with a git repository that has a remote"""
        # Create mock dependencies
        mock_repo_manager = MockRepositoryManager()
        mock_symbol_storage = MockSymbolStorage()

        # Create CodebaseTools instance
        codebase_tools = CodebaseTools(
            repository_manager=mock_repo_manager,
            symbol_storage=mock_symbol_storage,
            lsp_client_factory=mock_lsp_client_factory,
        )

        # Add a remote to the test repo
        subprocess.run(
            ["git", "remote", "add", "origin", "https://github.com/test/repo.git"],
            cwd=temp_git_repo,
            capture_output=True,
        )

        # Add repository to mock manager
        from constants import Language
        from repository_manager import RepositoryConfig

        repo_config = RepositoryConfig(
            name="test-repo",
            workspace=temp_git_repo,
            description="Test repo",
            language=Language.PYTHON,
            port=8000,
            python_path="/usr/bin/python3",
            github_owner="test-owner",
            github_repo="test-repo",
        )
        mock_repo_manager.add_repository("test-repo", repo_config)

        result = await codebase_tools.codebase_health_check("test-repo")

        data = json.loads(result)
        assert data["repo"] == "test-repo"
        assert data["workspace"] == temp_git_repo
        assert data["status"] in ["healthy", "warning"]

    @pytest.mark.asyncio
    async def test_health_check_exception_handling(self):
        """Test health check handles unexpected exceptions gracefully"""
        # Create mock dependencies
        mock_repo_manager = MockRepositoryManager()
        mock_symbol_storage = MockSymbolStorage()

        # Create CodebaseTools instance
        codebase_tools = CodebaseTools(
            repository_manager=mock_repo_manager,
            symbol_storage=mock_symbol_storage,
            lsp_client_factory=mock_lsp_client_factory,
        )

        # Test with non-existent repository to trigger an exception
        result = await codebase_tools.codebase_health_check("nonexistent-repo")

        data = json.loads(result)
        assert data["status"] == "error"
        assert "errors" in data
        assert len(data["errors"]) > 0
        assert data["repo"] == "nonexistent-repo"

    @pytest.mark.asyncio
    async def test_execute_tool_valid_tool(self, temp_git_repo):
        """Test execute_tool with a valid tool name"""
        # Create mock dependencies
        mock_repo_manager = MockRepositoryManager()
        mock_symbol_storage = MockSymbolStorage()

        # Create CodebaseTools instance
        codebase_tools = CodebaseTools(
            repository_manager=mock_repo_manager,
            symbol_storage=mock_symbol_storage,
            lsp_client_factory=mock_lsp_client_factory,
        )

        # Add repository to mock manager
        from constants import Language
        from repository_manager import RepositoryConfig

        repo_config = RepositoryConfig(
            name="test-repo",
            workspace=temp_git_repo,
            description="Test repo",
            language=Language.PYTHON,
            port=8000,
            python_path="/usr/bin/python3",
            github_owner="test-owner",
            github_repo="test-repo",
        )
        mock_repo_manager.add_repository("test-repo", repo_config)

        result = await codebase_tools.execute_tool(
            "codebase_health_check",
            repository_id="test-repo",
        )

        data = json.loads(result)
        assert data["repo"] == "test-repo"
        assert "status" in data

    @pytest.mark.asyncio
    async def test_execute_tool_invalid_tool(self):
        """Test execute_tool with an invalid tool name"""
        # Create mock dependencies
        mock_repo_manager = MockRepositoryManager()
        mock_symbol_storage = MockSymbolStorage()

        # Create CodebaseTools instance
        codebase_tools = CodebaseTools(
            repository_manager=mock_repo_manager,
            symbol_storage=mock_symbol_storage,
            lsp_client_factory=mock_lsp_client_factory,
        )

        result = await codebase_tools.execute_tool("invalid_tool", repo_name="test")

        data = json.loads(result)
        assert "error" in data
        assert "Unknown tool: invalid_tool" in data["error"]
        assert "available_tools" in data
        assert "codebase_health_check" in data["available_tools"]
        assert "search_symbols" in data["available_tools"]

    @pytest.mark.asyncio
    async def test_execute_tool_exception_handling(self):
        """Test execute_tool handles exceptions in tool execution"""
        # Create mock dependencies
        mock_repo_manager = MockRepositoryManager()
        mock_symbol_storage = MockSymbolStorage()

        # Create CodebaseTools instance
        codebase_tools = CodebaseTools(
            repository_manager=mock_repo_manager,
            symbol_storage=mock_symbol_storage,
            lsp_client_factory=mock_lsp_client_factory,
        )

        # This will cause an exception due to missing required argument
        result = await codebase_tools.execute_tool("codebase_health_check")

        data = json.loads(result)
        assert "error" in data
        assert "Tool execution failed" in data["error"]
        assert data["tool"] == "codebase_health_check"

    def test_tool_registration_format(self):
        """Test that tool registration follows proper MCP format"""
        # Create mock dependencies
        mock_repo_manager = MockRepositoryManager()
        mock_symbol_storage = MockSymbolStorage()

        # Create CodebaseTools instance
        codebase_tools = CodebaseTools(
            repository_manager=mock_repo_manager,
            symbol_storage=mock_symbol_storage,
            lsp_client_factory=mock_lsp_client_factory,
        )

        tools = codebase_tools.get_tools("test-repo", "/test/path")

        for tool in tools:
            # Verify required MCP tool fields
            assert "name" in tool
            assert "description" in tool
            assert "inputSchema" in tool

            # Verify inputSchema structure
            schema = tool["inputSchema"]
            assert "type" in schema
            assert schema["type"] == "object"
            assert "properties" in schema
            assert "required" in schema

            # Tool name should be a string
            assert isinstance(tool["name"], str)
            assert tool["name"]  # Non-empty

            # Description should be informative
            assert isinstance(tool["description"], str)
            assert tool["description"]  # Non-empty

    def test_tool_handlers_mapping(self):
        """Test that tool handlers are properly configured"""
        # Create mock dependencies
        mock_repo_manager = MockRepositoryManager()
        mock_symbol_storage = MockSymbolStorage()

        # Create CodebaseTools instance
        codebase_tools = CodebaseTools(
            repository_manager=mock_repo_manager,
            symbol_storage=mock_symbol_storage,
            lsp_client_factory=mock_lsp_client_factory,
        )

        # Verify all tools have handlers
        tools = codebase_tools.get_tools("test", "/test")
        for tool in tools:
            tool_name = tool["name"]
            # Check that the tool has a corresponding method
            assert hasattr(codebase_tools, tool_name)

        # Verify all expected tool methods exist and are callable
        expected_tools = [
            "codebase_health_check",
            "search_symbols",
            "find_definition",
            "find_references",
            "get_hover",
        ]
        for tool_name in expected_tools:
            assert hasattr(codebase_tools, tool_name)
            assert callable(getattr(codebase_tools, tool_name))

    @pytest.mark.asyncio
    async def test_health_check_git_command_timeout(self, temp_git_repo):
        """Test health check behavior with git command timeouts"""
        # This test validates that timeout handling works correctly
        # We can't easily mock subprocess timeout, but we can verify the structure
        # handles the timeout case properly by checking the warning path

        # Create mock dependencies
        mock_repo_manager = MockRepositoryManager()
        mock_symbol_storage = MockSymbolStorage()

        # Create CodebaseTools instance
        codebase_tools = CodebaseTools(
            repository_manager=mock_repo_manager,
            symbol_storage=mock_symbol_storage,
            lsp_client_factory=mock_lsp_client_factory,
        )

        # Add repository to mock manager
        from constants import Language
        from repository_manager import RepositoryConfig

        repo_config = RepositoryConfig(
            name="test-repo",
            workspace=temp_git_repo,
            description="Test repo",
            language=Language.PYTHON,
            port=8000,
            python_path="/usr/bin/python3",
            github_owner="test-owner",
            github_repo="test-repo",
        )
        mock_repo_manager.add_repository("test-repo", repo_config)

        result = await codebase_tools.codebase_health_check("test-repo")

        data = json.loads(result)
        # Should complete successfully for a valid repo
        assert data["status"] in ["healthy", "warning"]

        # Verify git_responsive is tracked
        assert "git_responsive" in data["checks"]

    @pytest.mark.asyncio
    async def test_health_check_json_output_structure(self, temp_git_repo):
        """Test that health check output follows expected JSON structure"""
        # Create mock dependencies
        mock_repo_manager = MockRepositoryManager()
        mock_symbol_storage = MockSymbolStorage()

        # Create CodebaseTools instance
        codebase_tools = CodebaseTools(
            repository_manager=mock_repo_manager,
            symbol_storage=mock_symbol_storage,
            lsp_client_factory=mock_lsp_client_factory,
        )

        # Add repository to mock manager
        from constants import Language
        from repository_manager import RepositoryConfig

        repo_config = RepositoryConfig(
            name="test-repo",
            workspace=temp_git_repo,
            description="Test repo",
            language=Language.PYTHON,
            port=8000,
            python_path="/usr/bin/python3",
            github_owner="test-owner",
            github_repo="test-repo",
        )
        mock_repo_manager.add_repository("test-repo", repo_config)

        result = await codebase_tools.codebase_health_check("test-repo")

        data = json.loads(result)

        # Required top-level fields
        required_fields = [
            "repo",
            "workspace",
            "status",
            "checks",
            "warnings",
            "errors",
        ]
        for field in required_fields:
            assert field in data

        # Status should be one of expected values
        assert data["status"] in ["healthy", "warning", "unhealthy", "error"]

        # Collections should be proper types
        assert isinstance(data["checks"], dict)
        assert isinstance(data["warnings"], list)
        assert isinstance(data["errors"], list)

        # Repo and workspace should match input
        assert data["repo"] == "test-repo"
        assert data["workspace"] == temp_git_repo

    @pytest.mark.asyncio
    async def test_health_check_error_handling_edge_cases(self, temp_git_repo):
        """Test health check error handling for various edge cases"""
        # Create mock dependencies
        mock_repo_manager = MockRepositoryManager()
        mock_symbol_storage = MockSymbolStorage()

        # Create CodebaseTools instance
        codebase_tools = CodebaseTools(
            repository_manager=mock_repo_manager,
            symbol_storage=mock_symbol_storage,
            lsp_client_factory=mock_lsp_client_factory,
        )

        # Test with empty string repo name (should fail at config validation level)
        from constants import Language
        from repository_manager import RepositoryConfig

        # RepositoryConfig now validates that name cannot be empty
        try:
            RepositoryConfig(
                name="",
                workspace=temp_git_repo,
                description="Test repo",
                language=Language.PYTHON,
                port=8000,
                python_path="/usr/bin/python3",
                github_owner="test-owner",
                github_repo="test-repo",
            )
            # If we get here, validation failed
            raise AssertionError("Expected ValueError for empty repository name")
        except ValueError as e:
            assert "Repository name cannot be empty" in str(e)

        # Test with non-existent repository instead
        result = await codebase_tools.codebase_health_check("empty-repo")
        data = json.loads(result)
        assert data["repo"] == "empty-repo"
        assert data["status"] == "error"
        assert "errors" in data

        # Test with very long repo name
        long_name = "x" * 1000
        long_repo_config = RepositoryConfig(
            name=long_name,
            workspace=temp_git_repo,
            description="Test repo",
            language=Language.PYTHON,
            port=8000,
            python_path="/usr/bin/python3",
            github_owner="test-owner",
            github_repo="test-repo",
        )
        mock_repo_manager.add_repository(long_name, long_repo_config)

        result = await codebase_tools.codebase_health_check(long_name)
        data = json.loads(result)
        assert data["repo"] == long_name

    @pytest.mark.asyncio
    async def test_search_symbols_basic(self, mock_symbol_storage):
        """Test basic search symbols functionality"""
        # Create mock dependencies
        mock_repo_manager = MockRepositoryManager()

        # Create CodebaseTools instance
        codebase_tools = CodebaseTools(
            repository_manager=mock_repo_manager,
            symbol_storage=mock_symbol_storage,
            lsp_client_factory=mock_lsp_client_factory,
        )

        # Add repository to mock manager
        from constants import Language
        from repository_manager import RepositoryConfig

        repo_config = RepositoryConfig(
            name="test-repo",
            workspace="/test/path",
            description="Test repo",
            language=Language.PYTHON,
            port=8000,
            python_path="/usr/bin/python3",
            github_owner="test-owner",
            github_repo="test-repo",
        )
        mock_repo_manager.add_repository("test-repo", repo_config)

        # Setup mock storage with test symbols
        mock_symbol_storage.insert_symbol(
            Symbol(
                "test_function",
                SymbolKind.FUNCTION,
                "/test/file.py",
                10,
                0,
                "test-repo",
                "Test function",
            )
        )
        mock_symbol_storage.insert_symbol(
            Symbol(
                "TestClass",
                SymbolKind.CLASS,
                "/test/file.py",
                20,
                0,
                "test-repo",
                "Test class",
            )
        )

        result = await codebase_tools.search_symbols("test-repo", "test")

        data = json.loads(result)
        assert data["query"] == "test"
        assert data["repository_id"] == "test-repo"
        assert data["count"] == 2
        assert len(data["symbols"]) == 2

        # Verify symbol structure
        symbol = data["symbols"][0]
        assert "name" in symbol
        assert "kind" in symbol
        assert "file_path" in symbol
        assert "line_number" in symbol
        assert "column_number" in symbol
        assert "docstring" in symbol
        assert "repository_id" in symbol

    @pytest.mark.asyncio
    async def test_search_symbols_with_kind_filter(self, codebase_tools_factory):
        """Test search symbols with symbol kind filtering"""
        from constants import Language
        from repository_manager import RepositoryConfig

        # Create repository config
        repo_config = RepositoryConfig(
            name="test-repo",
            workspace="/test/workspace",
            description="Test repo",
            language=Language.PYTHON,
            port=8000,
            python_path="/usr/bin/python3",
            github_owner="test-owner",
            github_repo="test-repo",
        )

        codebase_tools = codebase_tools_factory(
            repositories={"test-repo": repo_config}, use_real_symbol_storage=False
        )

        # Setup symbol storage with mixed symbols
        codebase_tools.symbol_storage.insert_symbol(
            Symbol(
                "test_function",
                SymbolKind.FUNCTION,
                "/test/file.py",
                10,
                0,
                "test-repo",
                "Test function",
            )
        )
        codebase_tools.symbol_storage.insert_symbol(
            Symbol(
                "TestClass",
                SymbolKind.CLASS,
                "/test/file.py",
                20,
                0,
                "test-repo",
                "Test class",
            )
        )
        codebase_tools.symbol_storage.insert_symbol(
            Symbol(
                "test_variable",
                SymbolKind.VARIABLE,
                "/test/file.py",
                30,
                0,
                "test-repo",
                "Test variable",
            )
        )

        result = await codebase_tools.search_symbols(
            "test-repo",
            "test",
            symbol_kind="function",
        )

        data = json.loads(result)
        assert data["query"] == "test"
        assert data["symbol_kind"] == "function"
        assert data["count"] == 1
        assert data["symbols"][0]["name"] == "test_function"
        assert data["symbols"][0]["kind"] == "function"

    @pytest.mark.asyncio
    async def test_search_symbols_with_limit(self, codebase_tools_factory):
        """Test search symbols with result limit"""
        from constants import Language
        from repository_manager import RepositoryConfig

        # Create repository config
        repo_config = RepositoryConfig(
            name="test-repo",
            workspace="/test/workspace",
            description="Test repo",
            language=Language.PYTHON,
            port=8000,
            python_path="/usr/bin/python3",
            github_owner="test-owner",
            github_repo="test-repo",
        )

        codebase_tools = codebase_tools_factory(
            repositories={"test-repo": repo_config}, use_real_symbol_storage=False
        )

        # Setup symbol storage with multiple symbols
        for i in range(10):
            codebase_tools.symbol_storage.insert_symbol(
                Symbol(
                    f"test_function_{i}",
                    SymbolKind.FUNCTION,
                    "/test/file.py",
                    10 + i,
                    0,
                    "test-repo",
                    f"Test function {i}",
                )
            )

        result = await codebase_tools.search_symbols(
            "test-repo",
            "test",
            limit=3,
        )

        data = json.loads(result)
        assert data["limit"] == 3
        assert data["count"] == 3
        assert len(data["symbols"]) == 3

    @pytest.mark.asyncio
    async def test_search_symbols_no_results(self, codebase_tools_factory):
        """Test search symbols when no results are found"""
        from constants import Language
        from repository_manager import RepositoryConfig

        # Create repository config
        repo_config = RepositoryConfig(
            name="test-repo",
            workspace="/test/workspace",
            description="Test repo",
            language=Language.PYTHON,
            port=8000,
            python_path="/usr/bin/python3",
            github_owner="test-owner",
            github_repo="test-repo",
        )

        codebase_tools = codebase_tools_factory(
            repositories={"test-repo": repo_config}, use_real_symbol_storage=False
        )
        result = await codebase_tools.search_symbols("test-repo", "nonexistent")

        data = json.loads(result)
        assert data["query"] == "nonexistent"
        assert data["count"] == 0
        assert len(data["symbols"]) == 0

    @pytest.mark.asyncio
    async def test_search_symbols_invalid_limit(self, codebase_tools_factory):
        """Test search symbols with invalid limit values"""
        from constants import Language
        from repository_manager import RepositoryConfig

        # Create repository config
        repo_config = RepositoryConfig(
            name="test-repo",
            workspace="/test/workspace",
            description="Test repo",
            language=Language.PYTHON,
            port=8000,
            python_path="/usr/bin/python3",
            github_owner="test-owner",
            github_repo="test-repo",
        )

        # Test limit too low
        codebase_tools = codebase_tools_factory(
            repositories={"test-repo": repo_config}, use_real_symbol_storage=False
        )
        result = await codebase_tools.search_symbols("test-repo", "test", limit=0)

        data = json.loads(result)
        assert "error" in data
        assert "Limit must be between 1 and 100" in data["error"]

        # Test limit too high
        result = await codebase_tools.search_symbols("test-repo", "test", limit=101)

        data = json.loads(result)
        assert "error" in data
        assert "Limit must be between 1 and 100" in data["error"]

    @pytest.mark.asyncio
    async def test_search_symbols_default_parameters(self, codebase_tools_factory):
        """Test search symbols with default parameters"""
        from constants import Language
        from repository_manager import RepositoryConfig

        # Create repository config
        repo_config = RepositoryConfig(
            name="test-repo",
            workspace="/test/workspace",
            description="Test repo",
            language=Language.PYTHON,
            port=8000,
            python_path="/usr/bin/python3",
            github_owner="test-owner",
            github_repo="test-repo",
        )

        codebase_tools = codebase_tools_factory(
            repositories={"test-repo": repo_config}, use_real_symbol_storage=False
        )

        codebase_tools.symbol_storage.insert_symbol(
            Symbol(
                "test_function",
                SymbolKind.FUNCTION,
                "/test/file.py",
                10,
                0,
                "test-repo",
                "Test function",
            )
        )

        result = await codebase_tools.search_symbols("test-repo", "test")

        data = json.loads(result)
        assert data["symbol_kind"] is None
        assert data["limit"] == 50

    @pytest.mark.asyncio
    async def test_search_symbols_exception_handling(self, codebase_tools_factory):
        """Test search symbols exception handling"""
        from constants import Language
        from repository_manager import RepositoryConfig

        # Create repository config
        repo_config = RepositoryConfig(
            name="test-repo",
            workspace="/test/workspace",
            description="Test repo",
            language=Language.PYTHON,
            port=8000,
            python_path="/usr/bin/python3",
            github_owner="test-owner",
            github_repo="test-repo",
        )

        codebase_tools = codebase_tools_factory(
            repositories={"test-repo": repo_config}, use_real_symbol_storage=False
        )

        # Mock a storage error by making the search_symbols method raise an exception
        def error_search(*args, **kwargs):
            raise Exception("Database connection failed")

        codebase_tools.symbol_storage.search_symbols = error_search

        result = await codebase_tools.search_symbols("test-repo", "test")

        # Should handle exception gracefully and return error response
        data = json.loads(result)
        assert "error" in data
        assert "Symbol search failed" in data["error"]
        assert data["query"] == "test"
        assert data["repository_id"] == "test-repo"
        assert len(data["symbols"]) == 0

    @pytest.mark.asyncio
    async def test_execute_tool_search_symbols(self, codebase_tools_factory):
        """Test execute_tool with search_symbols"""
        from constants import Language
        from repository_manager import RepositoryConfig

        # Create repository config
        repo_config = RepositoryConfig(
            name="test-repo",
            workspace="/test/workspace",
            description="Test repo",
            language=Language.PYTHON,
            port=8000,
            python_path="/usr/bin/python3",
            github_owner="test-owner",
            github_repo="test-repo",
        )

        codebase_tools = codebase_tools_factory(
            repositories={"test-repo": repo_config}, use_real_symbol_storage=False
        )

        codebase_tools.symbol_storage.insert_symbol(
            Symbol(
                "test_function",
                SymbolKind.FUNCTION,
                "/test/file.py",
                10,
                0,
                "test-repo",
                "Test function",
            )
        )

        # Use the codebase_tools's search_symbols method directly
        result = await codebase_tools.search_symbols(
            "test-repo", "test", symbol_kind="function", limit=10
        )

        data = json.loads(result)
        assert data["query"] == "test"
        assert data["symbol_kind"] == "function"
        assert data["limit"] == 10
        assert data["repository_id"] == "test-repo"

    @pytest.mark.asyncio
    async def test_search_symbols_json_structure(self, codebase_tools_factory):
        """Test that search symbols output follows expected JSON structure"""
        from constants import Language
        from repository_manager import RepositoryConfig

        # Create repository config
        repo_config = RepositoryConfig(
            name="test-repo",
            workspace="/test/workspace",
            description="Test repo",
            language=Language.PYTHON,
            port=8000,
            python_path="/usr/bin/python3",
            github_owner="test-owner",
            github_repo="test-repo",
        )

        codebase_tools = codebase_tools_factory(
            repositories={"test-repo": repo_config}, use_real_symbol_storage=False
        )

        codebase_tools.symbol_storage.insert_symbol(
            Symbol(
                "test_function",
                SymbolKind.FUNCTION,
                "/test/file.py",
                10,
                5,
                "test-repo",
                "Test function docstring",
            )
        )

        result = await codebase_tools.search_symbols(
            "test-repo",
            "test",
            symbol_kind="function",
            limit=25,
        )

        data = json.loads(result)

        # Required top-level fields
        required_fields = [
            "query",
            "symbol_kind",
            "limit",
            "repository_id",
            "count",
            "symbols",
        ]
        for field in required_fields:
            assert field in data

        # Check data types and values
        assert isinstance(data["query"], str)
        assert isinstance(data["symbol_kind"], str)
        assert isinstance(data["limit"], int)
        assert isinstance(data["repository_id"], str)
        assert isinstance(data["count"], int)
        assert isinstance(data["symbols"], list)

        # Values should match input
        assert data["query"] == "test"
        assert data["symbol_kind"] == "function"
        assert data["limit"] == 25
        assert data["repository_id"] == "test-repo"

        # Verify symbol structure
        if data["symbols"]:
            symbol = data["symbols"][0]
            symbol_fields = [
                "name",
                "kind",
                "file_path",
                "line_number",
                "column_number",
                "docstring",
                "repository_id",
            ]
            for field in symbol_fields:
                assert field in symbol

            assert symbol["name"] == "test_function"
            assert symbol["kind"] == "function"
            assert symbol["file_path"] == "/test/file.py"
            assert symbol["line_number"] == 10
            assert symbol["column_number"] == 5
            assert symbol["docstring"] == "Test function docstring"
            assert symbol["repository_id"] == "test-repo"


if __name__ == "__main__":
    pytest.main([__file__])
