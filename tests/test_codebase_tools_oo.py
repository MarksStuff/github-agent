#!/usr/bin/env python3

"""
Tests for Refactored Object-Oriented Codebase Tools
"""

import json
import os
import sys
import tempfile
import unittest

from codebase_tools import CodebaseTools
from constants import Language
from repository_manager import RepositoryConfig
from symbol_storage import AbstractSymbolStorage, Symbol, SymbolKind
from tests.conftest import MockLSPClient


class MockSymbolStorage(AbstractSymbolStorage):
    """Mock symbol storage for testing."""

    def __init__(self):
        self.symbols = []

    def search_symbols(
        self,
        query: str,
        repository_id: str | None = None,
        symbol_kind: str | None = None,
        limit: int = 50,
    ) -> list[Symbol]:
        """Mock symbol search."""
        # Create mock symbols for testing
        mock_symbols = [
            Symbol(
                name="hello_world",
                kind=SymbolKind.FUNCTION,
                file_path="test.py",
                line_number=1,
                column_number=1,
                repository_id="test-repo",
                docstring="Test function",
            ),
            Symbol(
                name="TestClass",
                kind=SymbolKind.CLASS,
                file_path="test.py",
                line_number=10,
                column_number=1,
                repository_id="test-repo",
                docstring="Test class",
            ),
        ]

        # Filter by query
        results = [s for s in mock_symbols if query.lower() in s.name.lower()]

        # Filter by symbol kind if specified
        if symbol_kind:
            results = [s for s in results if s.kind.value == symbol_kind]

        return results[:limit]

    def add_mock_symbol(self, symbol: dict):
        """Add a mock symbol for testing."""
        self.symbols.append(symbol)

    # Required abstract method implementations for testing
    def create_schema(self) -> None:
        """Mock create schema."""
        pass

    def insert_symbol(self, symbol: dict) -> int:
        """Mock insert symbol."""
        self.symbols.append(symbol)
        return len(self.symbols) - 1

    def insert_symbols(self, symbols: list[dict]) -> list[int]:
        """Mock insert symbols."""
        ids = []
        for symbol in symbols:
            ids.append(self.insert_symbol(symbol))
        return ids

    def get_symbol_by_id(self, symbol_id: int) -> dict | None:
        """Mock get symbol by ID."""
        if 0 <= symbol_id < len(self.symbols):
            return self.symbols[symbol_id]
        return None

    def update_symbol(self, symbol_id: int, symbol: dict) -> bool:
        """Mock update symbol."""
        if 0 <= symbol_id < len(self.symbols):
            self.symbols[symbol_id] = symbol
            return True
        return False

    def delete_symbol(self, symbol_id: int) -> bool:
        """Mock delete symbol."""
        if 0 <= symbol_id < len(self.symbols):
            del self.symbols[symbol_id]
            return True
        return False

    def get_symbols_by_file(self, repository_id: str, file_path: str) -> list[dict]:
        """Mock get symbols by file."""
        return [s for s in self.symbols if s.get("file") == file_path]

    def delete_symbols_by_repository(self, repository_id: str) -> int:
        """Mock delete symbols by repository."""
        original_count = len(self.symbols)
        self.symbols = [
            s for s in self.symbols if s.get("repository_id") != repository_id
        ]
        return original_count - len(self.symbols)

    def health_check(self) -> dict:
        """Mock health check."""
        return {"status": "healthy", "symbol_count": len(self.symbols)}


class MockRepositoryManager:
    """Mock repository manager for testing."""

    def __init__(self):
        self.repositories = {}

    def get_repository(self, repo_name: str) -> RepositoryConfig | None:
        """Get repository by name."""
        return self.repositories.get(repo_name)

    def add_repository(self, name: str, config: RepositoryConfig):
        """Add repository for testing."""
        self.repositories[name] = config


class TestCodebaseTools(unittest.IsolatedAsyncioTestCase):
    """Test the refactored CodebaseTools class."""

    def setUp(self):
        """Set up test fixtures."""
        # Create temporary directory for test repositories
        self.temp_dir = tempfile.mkdtemp()

        # Create test repository
        self.test_repo_path = os.path.join(self.temp_dir, "test-repo")
        os.makedirs(self.test_repo_path, exist_ok=True)

        # Initialize as git repository
        os.system(f"cd {self.test_repo_path} && git init")

        # Create test Python file
        test_py_file = os.path.join(self.test_repo_path, "test.py")
        with open(test_py_file, "w") as f:
            f.write(
                """
def hello_world():
    return "Hello, World!"

class TestClass:
    def __init__(self, value: int):
        self.value = value

    def get_value(self) -> int:
        return self.value
"""
            )

        # Set up mock repository manager
        self.mock_repo_manager = MockRepositoryManager()
        self.test_repo_config = RepositoryConfig(
            name="test-repo",
            workspace=self.test_repo_path,
            description="Test repository",
            language=Language.PYTHON,
            port=8081,
            python_path=sys.executable,
            github_owner="test",
            github_repo="test-repo",
        )
        self.mock_repo_manager.add_repository("test-repo", self.test_repo_config)

        # Set up mock symbol storage
        self.mock_symbol_storage = MockSymbolStorage()
        self.mock_symbol_storage.add_mock_symbol(
            {
                "name": "hello_world",
                "kind": "function",
                "file": "test.py",
                "line": 2,
            }
        )
        self.mock_symbol_storage.add_mock_symbol(
            {
                "name": "TestClass",
                "kind": "class",
                "file": "test.py",
                "line": 5,
            }
        )

        # Create CodebaseTools instance
        def mock_lsp_client_factory(workspace: str, python_path: str):
            from codebase_tools import CodebaseLSPClient

            return CodebaseLSPClient(workspace, python_path)

        self.tools = CodebaseTools(
            repository_manager=self.mock_repo_manager,
            symbol_storage=self.mock_symbol_storage,
            lsp_client_factory=mock_lsp_client_factory,
        )

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_get_tools(self):
        """Test that get_tools returns proper tool definitions."""
        tools_list = self.tools.get_tools("test-repo", self.test_repo_path)

        self.assertIsInstance(tools_list, list)
        self.assertEqual(len(tools_list), 4)  # 4 tools defined

        tool_names = [tool["name"] for tool in tools_list]
        expected_tools = [
            "codebase_health_check",
            "search_symbols",
            "find_definition",
            "find_references",
        ]

        for expected_tool in expected_tools:
            self.assertIn(expected_tool, tool_names)

        # Check that each tool has required fields
        for tool in tools_list:
            self.assertIn("name", tool)
            self.assertIn("description", tool)
            self.assertIn("inputSchema", tool)
            self.assertIn("repository_id", tool["inputSchema"]["properties"])

    async def test_codebase_health_check_success(self):
        """Test successful codebase health check."""
        result_json = await self.tools.codebase_health_check("test-repo")
        result = json.loads(result_json)

        self.assertIn(result["status"], ["healthy", "warning"])  # Accept both
        self.assertEqual(result["repo"], "test-repo")
        self.assertEqual(result["workspace"], self.test_repo_path)
        self.assertIn("current_commit", result)

    async def test_codebase_health_check_repo_not_found(self):
        """Test health check for non-existent repository."""
        result_json = await self.tools.codebase_health_check("non-existent")
        result = json.loads(result_json)

        self.assertIn("errors", result)
        self.assertGreater(len(result["errors"]), 0)
        self.assertIn("not found", str(result["errors"]))

    async def test_search_symbols_success(self):
        """Test successful symbol search."""
        result_json = await self.tools.search_symbols("test-repo", "hello", limit=10)
        result = json.loads(result_json)

        self.assertEqual(result["repository_id"], "test-repo")
        self.assertEqual(result["query"], "hello")
        self.assertIn("symbols", result)
        self.assertGreaterEqual(len(result["symbols"]), 1)

        # Should find hello_world function
        symbol_names = [s["name"] for s in result["symbols"]]
        self.assertIn("hello_world", symbol_names)

    async def test_search_symbols_with_kind_filter(self):
        """Test symbol search with kind filter."""
        result_json = await self.tools.search_symbols(
            "test-repo", "test", symbol_kind="class", limit=10
        )
        result = json.loads(result_json)

        self.assertEqual(result["symbol_kind"], "class")
        self.assertIn("symbols", result)

        # Should only find class symbols
        for symbol in result["symbols"]:
            self.assertEqual(symbol["kind"], "class")

    async def test_search_symbols_repo_not_found(self):
        """Test symbol search for non-existent repository."""
        result_json = await self.tools.search_symbols("non-existent", "test")
        result = json.loads(result_json)

        self.assertIn("error", result)
        self.assertEqual(result["symbols"], [])

    async def test_find_definition_success(self):
        """Test successful definition finding."""
        # Create mock LSP client with specific response
        mock_lsp_client = MockLSPClient()
        mock_lsp_client.set_definition_response(
            [
                {
                    "uri": f"file://{self.test_repo_path}/test.py",
                    "range": {
                        "start": {"line": 1, "character": 4},
                        "end": {"line": 1, "character": 15},
                    },
                }
            ]
        )

        # Create repository manager that returns our mock LSP client
        mock_repo_manager = MockRepositoryManager()
        mock_repo_manager.add_repository("test-repo", self.test_repo_config)
        mock_repo_manager.get_lsp_client = lambda repo_id: mock_lsp_client

        # Create tools with mock dependencies
        def mock_lsp_client_factory(
            workspace_root: str, python_path: str
        ) -> MockLSPClient:
            return mock_lsp_client

        tools = CodebaseTools(
            repository_manager=mock_repo_manager,
            symbol_storage=self.mock_symbol_storage,
            lsp_client_factory=mock_lsp_client_factory,
        )

        result_json = await tools.find_definition(
            "test-repo", "hello_world", "test.py", 2, 5
        )
        result = json.loads(result_json)

        self.assertEqual(result["symbol"], "hello_world")
        self.assertEqual(result["repository_id"], "test-repo")
        self.assertIn("definitions", result)
        self.assertGreater(len(result["definitions"]), 0)

        definition = result["definitions"][0]
        self.assertIn("file", definition)
        self.assertIn("line", definition)
        self.assertIn("column", definition)

    async def test_find_definition_repo_not_found(self):
        """Test definition finding for non-existent repository."""
        result_json = await self.tools.find_definition(
            "non-existent", "test_symbol", "test.py", 1, 1
        )
        result = json.loads(result_json)

        self.assertIn("error", result)
        self.assertEqual(result["symbol"], "test_symbol")

    async def test_find_references_success(self):
        """Test successful reference finding."""
        # Create mock LSP client with specific response
        mock_lsp_client = MockLSPClient()
        mock_lsp_client.set_references_response(
            [
                {
                    "uri": f"file://{self.test_repo_path}/test.py",
                    "range": {
                        "start": {"line": 1, "character": 4},
                        "end": {"line": 1, "character": 15},
                    },
                },
                {
                    "uri": f"file://{self.test_repo_path}/another.py",
                    "range": {
                        "start": {"line": 5, "character": 8},
                        "end": {"line": 5, "character": 19},
                    },
                },
            ]
        )

        # Create repository manager that returns our mock LSP client
        mock_repo_manager = MockRepositoryManager()
        mock_repo_manager.add_repository("test-repo", self.test_repo_config)
        mock_repo_manager.get_lsp_client = lambda repo_id: mock_lsp_client

        # Create tools with mock dependencies
        def mock_lsp_client_factory(
            workspace_root: str, python_path: str
        ) -> MockLSPClient:
            return mock_lsp_client

        tools = CodebaseTools(
            repository_manager=mock_repo_manager,
            symbol_storage=self.mock_symbol_storage,
            lsp_client_factory=mock_lsp_client_factory,
        )

        result_json = await tools.find_references(
            "test-repo", "hello_world", "test.py", 2, 5
        )
        result = json.loads(result_json)

        self.assertEqual(result["symbol"], "hello_world")
        self.assertEqual(result["repository_id"], "test-repo")
        self.assertIn("references", result)
        self.assertEqual(len(result["references"]), 2)

        # Check reference format
        for ref in result["references"]:
            self.assertIn("file", ref)
            self.assertIn("line", ref)
            self.assertIn("column", ref)

    async def test_execute_tool_unknown_tool(self):
        """Test executing unknown tool."""
        result_json = await self.tools.execute_tool(
            "unknown_tool", repository_id="test-repo"
        )
        result = json.loads(result_json)

        self.assertIn("error", result)
        self.assertIn("Unknown tool", result["error"])
        self.assertIn("available_tools", result)

    async def test_execute_tool_health_check(self):
        """Test executing health check tool."""
        result_json = await self.tools.execute_tool(
            "codebase_health_check", repository_id="test-repo"
        )
        result = json.loads(result_json)

        self.assertIn(result["status"], ["healthy", "warning"])  # Accept both
        self.assertEqual(result["repo"], "test-repo")

    async def test_execute_tool_search_symbols(self):
        """Test executing search symbols tool."""
        result_json = await self.tools.execute_tool(
            "search_symbols", repository_id="test-repo", query="hello"
        )
        result = json.loads(result_json)

        self.assertEqual(result["repository_id"], "test-repo")
        self.assertEqual(result["query"], "hello")
        self.assertIn("symbols", result)

    def test_resolve_file_path_relative(self):
        """Test resolving relative file path."""
        resolved = self.tools._resolve_file_path("test.py", self.test_repo_path)
        expected = os.path.realpath(os.path.join(self.test_repo_path, "test.py"))
        self.assertEqual(resolved, expected)

    def test_resolve_file_path_absolute(self):
        """Test resolving absolute file path."""
        test_file = os.path.join(self.test_repo_path, "test.py")
        resolved = self.tools._resolve_file_path(test_file, self.test_repo_path)
        self.assertEqual(resolved, os.path.realpath(test_file))

    def test_resolve_file_path_outside_workspace(self):
        """Test resolving file path outside workspace raises error."""
        with self.assertRaises(ValueError):
            self.tools._resolve_file_path("/etc/passwd", self.test_repo_path)

    def test_resolve_file_path_nonexistent(self):
        """Test resolving non-existent file raises error."""
        with self.assertRaises(ValueError):
            self.tools._resolve_file_path("nonexistent.py", self.test_repo_path)

    async def test_lsp_client_caching(self):
        """Test that LSP clients are properly cached when using repository manager."""
        # Create mock LSP client
        mock_lsp_client = MockLSPClient()

        # Create repository manager that returns our mock LSP client
        mock_repo_manager = MockRepositoryManager()
        mock_repo_manager.add_repository("test-repo", self.test_repo_config)
        mock_repo_manager.get_lsp_client = lambda repo_id: mock_lsp_client

        # Create tools with mock dependencies
        def mock_lsp_client_factory(
            workspace_root: str, python_path: str
        ) -> MockLSPClient:
            return mock_lsp_client

        tools = CodebaseTools(
            repository_manager=mock_repo_manager,
            symbol_storage=self.mock_symbol_storage,
            lsp_client_factory=mock_lsp_client_factory,
        )

        # Both calls should return the same client from repository manager
        client1 = await tools._get_lsp_client("test-repo")
        self.assertIsNotNone(client1)

        client2 = await tools._get_lsp_client("test-repo")
        self.assertEqual(client1, client2)

    async def test_lsp_client_unsupported_language(self):
        """Test LSP client creation for unsupported language."""
        # Add Swift repository
        swift_config = RepositoryConfig(
            name="swift-repo",
            workspace=self.test_repo_path,
            description="Swift repository",
            language=Language.SWIFT,
            port=8082,
            python_path=sys.executable,
            github_owner="test",
            github_repo="swift-repo",
        )
        self.mock_repo_manager.add_repository("swift-repo", swift_config)

        # Should return None for unsupported language
        client = await self.tools._get_lsp_client("swift-repo")
        self.assertIsNone(client)

    async def test_shutdown(self):
        """Test proper shutdown of tools."""
        # Create mock LSP client
        mock_lsp_client = MockLSPClient()

        # Create repository manager that returns our mock LSP client
        mock_repo_manager = MockRepositoryManager()
        mock_repo_manager.add_repository("test-repo", self.test_repo_config)
        mock_repo_manager.get_lsp_client = lambda repo_id: mock_lsp_client

        # Create tools with mock dependencies
        def mock_lsp_client_factory(
            workspace_root: str, python_path: str
        ) -> MockLSPClient:
            return mock_lsp_client

        tools = CodebaseTools(
            repository_manager=mock_repo_manager,
            symbol_storage=self.mock_symbol_storage,
            lsp_client_factory=mock_lsp_client_factory,
        )

        # Get an LSP client (would be cached in fallback mode)
        await tools._get_lsp_client("test-repo")

        # Shutdown should clean up any cached clients
        await tools.shutdown()

        # Verify clients cache is cleared (in fallback mode)
        self.assertEqual(len(tools._lsp_clients), 0)


if __name__ == "__main__":
    unittest.main()
