#!/usr/bin/env python3

"""
Codebase Tools for MCP Server - Object-Oriented Refactor
Contains codebase-related tool implementations for repository analysis and management.
"""

import json
import logging
import os
import subprocess
import threading
from pathlib import Path
from typing import Any

from constants import DATA_DIR, Language
from lsp_client import AbstractLSPClient, LSPClientState
from lsp_constants import LSPMethod
from pyright_lsp_manager import PyrightLSPManager
from repository_manager import AbstractRepositoryManager, RepositoryManager
from symbol_storage import AbstractSymbolStorage, SQLiteSymbolStorage

logger = logging.getLogger(__name__)


# LSP Tools Implementation
class CodebaseLSPClient(AbstractLSPClient):
    """Concrete LSP client implementation for codebase tools."""

    def __init__(self, workspace_root: str, python_path: str):
        """Initialize the LSP client for codebase operations."""
        server_manager = PyrightLSPManager(workspace_root, python_path)
        super().__init__(
            server_manager=server_manager,
            workspace_root=workspace_root,
            logger=logger,
        )

    async def get_definition(
        self, uri: str, line: int, character: int
    ) -> list[dict[str, Any]] | None:
        """Get definition for a symbol using LSP."""
        definition_params = {
            "textDocument": {"uri": uri},
            "position": {"line": line, "character": character},
        }
        request = self.protocol.create_request(LSPMethod.DEFINITION, definition_params)
        response = await self._send_request(request, timeout=10.0)
        return response.get("result") if response else None

    async def get_references(
        self, uri: str, line: int, character: int, include_declaration: bool = True
    ) -> list[dict[str, Any]] | None:
        """Get references for a symbol using LSP."""
        references_params = {
            "textDocument": {"uri": uri},
            "position": {"line": line, "character": character},
            "context": {"includeDeclaration": include_declaration},
        }
        request = self.protocol.create_request(LSPMethod.REFERENCES, references_params)
        response = await self._send_request(request, timeout=15.0)
        return response.get("result") if response else None

    async def get_hover(
        self, uri: str, line: int, character: int
    ) -> dict[str, Any] | None:
        """Get hover information for a symbol using LSP."""
        hover_params = {
            "textDocument": {"uri": uri},
            "position": {"line": line, "character": character},
        }
        request = self.protocol.create_request(LSPMethod.HOVER, hover_params)
        response = await self._send_request(request, timeout=5.0)
        return response.get("result") if response else None

    async def get_document_symbols(self, uri: str) -> list[dict[str, Any]] | None:
        """Get document symbols using LSP."""
        symbols_params = {"textDocument": {"uri": uri}}
        request = self.protocol.create_request(
            LSPMethod.DOCUMENT_SYMBOLS, symbols_params
        )
        response = await self._send_request(request, timeout=10.0)
        return response.get("result") if response else None

    async def connect(self) -> bool:
        """Connect to the LSP server."""
        try:
            if not await self._start_server():
                return False

            self._start_reader_thread()

            if not await self._initialize_connection():
                return False

            return True
        except Exception as e:
            self.logger.error(f"Failed to connect to LSP server: {e}")
            return False

    async def disconnect(self) -> None:
        """Disconnect from the LSP server."""
        await self.stop()


class CodebaseTools:
    """Object-oriented codebase tools with dependency injection."""

    def __init__(
        self,
        repository_manager: AbstractRepositoryManager,
        symbol_storage: AbstractSymbolStorage | None = None,
    ):
        """
        Initialize codebase tools with dependencies.

        Args:
            repository_manager: Repository manager for accessing repository configurations
            symbol_storage: Symbol storage for caching (defaults to SQLite storage)
        """
        self.repository_manager = repository_manager
        self.symbol_storage = symbol_storage or SQLiteSymbolStorage(DATA_DIR)
        self.logger = logging.getLogger(__name__)

        # Thread safety for LSP client cache
        self._lsp_lock = threading.Lock()
        self._lsp_clients: dict[str, CodebaseLSPClient] = {}

    def get_tools(self, repo_name: str, repository_workspace: str) -> list[dict]:
        """Get codebase tool definitions for MCP registration

        Args:
            repo_name: Repository name for display purposes
            repository_workspace: Repository path for tool descriptions

        Returns:
            List of tool definitions in MCP format
        """
        return [
            {
                "name": "codebase_health_check",
                "description": f"Perform a basic health check of the repository at {repository_workspace}. Validates that the path exists, is accessible, and is a valid Git repository with readable metadata.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "repository_id": {
                            "type": "string",
                            "description": "Repository identifier",
                        }
                    },
                    "required": ["repository_id"],
                },
            },
            {
                "name": "search_symbols",
                "description": f"Search for symbols (functions, classes, variables) in the {repo_name} repository. Supports fuzzy matching by symbol name with optional filtering by symbol kind.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "repository_id": {
                            "type": "string",
                            "description": "Repository identifier",
                        },
                        "query": {
                            "type": "string",
                            "description": "Search query for symbol names (supports partial matches)",
                        },
                        "symbol_kind": {
                            "type": "string",
                            "description": "Optional filter by symbol kind",
                            "enum": ["function", "class", "variable"],
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of results to return (default: 50, max: 100)",
                            "minimum": 1,
                            "maximum": 100,
                            "default": 50,
                        },
                    },
                    "required": ["repository_id", "query"],
                },
            },
            {
                "name": "find_definition",
                "description": f"Find the definition of a symbol in the {repo_name} repository using LSP. Returns the exact file location and line number where the symbol is defined.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "repository_id": {
                            "type": "string",
                            "description": "Repository identifier",
                        },
                        "symbol": {
                            "type": "string",
                            "description": "Symbol name to find the definition for",
                        },
                        "file_path": {
                            "type": "string",
                            "description": "File path containing the symbol (relative to repository root or absolute)",
                        },
                        "line": {
                            "type": "integer",
                            "description": "Line number where the symbol appears (1-based)",
                            "minimum": 1,
                        },
                        "column": {
                            "type": "integer",
                            "description": "Column number where the symbol appears (1-based)",
                            "minimum": 1,
                        },
                    },
                    "required": [
                        "repository_id",
                        "symbol",
                        "file_path",
                        "line",
                        "column",
                    ],
                },
            },
            {
                "name": "find_references",
                "description": f"Find all references to a symbol in the {repo_name} repository using LSP. Returns all usage locations for the symbol across the codebase.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "repository_id": {
                            "type": "string",
                            "description": "Repository identifier",
                        },
                        "symbol": {
                            "type": "string",
                            "description": "Symbol name to find references for",
                        },
                        "file_path": {
                            "type": "string",
                            "description": "File path containing the symbol (relative to repository root or absolute)",
                        },
                        "line": {
                            "type": "integer",
                            "description": "Line number where the symbol appears (1-based)",
                            "minimum": 1,
                        },
                        "column": {
                            "type": "integer",
                            "description": "Column number where the symbol appears (1-based)",
                            "minimum": 1,
                        },
                    },
                    "required": [
                        "repository_id",
                        "symbol",
                        "file_path",
                        "line",
                        "column",
                    ],
                },
            },
        ]

    async def execute_tool(self, tool_name: str, **kwargs) -> str:
        """Execute a codebase tool by name

        Args:
            tool_name: Name of the tool to execute
            **kwargs: Tool-specific arguments

        Returns:
            Tool execution result as JSON string
        """
        handlers = {
            "codebase_health_check": self.codebase_health_check,
            "search_symbols": self.search_symbols,
            "find_definition": self.find_definition,
            "find_references": self.find_references,
        }

        if tool_name not in handlers:
            return json.dumps(
                {
                    "error": f"Unknown tool: {tool_name}",
                    "available_tools": list(handlers.keys()),
                }
            )

        handler = handlers[tool_name]
        try:
            return await handler(**kwargs)
        except Exception as e:
            self.logger.exception(f"Error executing tool {tool_name}")
            return json.dumps(
                {"error": f"Tool execution failed: {e!s}", "tool": tool_name}
            )

    async def codebase_health_check(self, repository_id: str) -> str:
        """Perform a basic health check of the repository."""
        try:
            repo_config = self.repository_manager.get_repository(repository_id)
            if not repo_config:
                return json.dumps(
                    {
                        "error": f"Repository '{repository_id}' not found",
                        "status": "error",
                    }
                )

            repository_workspace = repo_config.workspace

            # Check if repository exists and is accessible
            if not os.path.exists(repository_workspace):
                return json.dumps(
                    {
                        "status": "error",
                        "message": f"Repository path does not exist: {repository_workspace}",
                        "repository_id": repository_id,
                    }
                )

            if not os.access(repository_workspace, os.R_OK):
                return json.dumps(
                    {
                        "status": "error",
                        "message": f"Repository path is not readable: {repository_workspace}",
                        "repository_id": repository_id,
                    }
                )

            # Check if it's a git repository
            git_dir = os.path.join(repository_workspace, ".git")
            if not os.path.exists(git_dir):
                return json.dumps(
                    {
                        "status": "warning",
                        "message": f"Directory exists but is not a Git repository: {repository_workspace}",
                        "repository_id": repository_id,
                    }
                )

            # Get basic git info
            try:
                result = subprocess.run(
                    ["git", "rev-parse", "HEAD"],
                    cwd=repository_workspace,
                    capture_output=True,
                    text=True,
                    check=True,
                    timeout=10,
                )
                current_commit = result.stdout.strip()
            except Exception:
                current_commit = "unknown"

            # Check LSP status if applicable
            lsp_status = None
            if hasattr(self.repository_manager, "get_lsp_status"):
                lsp_status = self.repository_manager.get_lsp_status(repository_id)

            return json.dumps(
                {
                    "status": "healthy",
                    "message": "Repository is accessible and appears to be a valid Git repository",
                    "repository_id": repository_id,
                    "repository_path": repository_workspace,
                    "current_commit": current_commit,
                    "lsp_status": lsp_status,
                }
            )

        except Exception as e:
            self.logger.exception(f"Error in codebase health check for {repository_id}")
            return json.dumps(
                {
                    "status": "error",
                    "message": f"Health check failed: {e!s}",
                    "repository_id": repository_id,
                }
            )

    async def search_symbols(
        self,
        repository_id: str,
        query: str,
        symbol_kind: str | None = None,
        limit: int = 50,
    ) -> str:
        """Search for symbols in the repository."""
        try:
            repo_config = self.repository_manager.get_repository(repository_id)
            if not repo_config:
                return json.dumps(
                    {"error": f"Repository '{repository_id}' not found", "symbols": []}
                )

            # Search symbols using symbol storage
            symbols = await self.symbol_storage.search_symbols(
                repository_id=repository_id,
                query=query,
                symbol_kind=symbol_kind,
                limit=min(limit, 100),  # Cap at 100
            )

            return json.dumps(
                {
                    "repository_id": repository_id,
                    "query": query,
                    "symbol_kind": symbol_kind,
                    "limit": limit,
                    "symbols": symbols,
                    "count": len(symbols),
                }
            )

        except Exception as e:
            self.logger.exception(f"Error searching symbols in {repository_id}")
            return json.dumps(
                {
                    "error": f"Symbol search failed: {e!s}",
                    "repository_id": repository_id,
                    "query": query,
                    "symbols": [],
                }
            )

    async def find_definition(
        self,
        repository_id: str,
        symbol: str,
        file_path: str,
        line: int,
        column: int,
    ) -> str:
        """Find the definition of a symbol using LSP."""
        try:
            repo_config = self.repository_manager.get_repository(repository_id)
            if not repo_config:
                return json.dumps(
                    {
                        "error": f"Repository '{repository_id}' not found",
                        "symbol": symbol,
                    }
                )

            # Get or create LSP client for this repository
            lsp_client = await self._get_lsp_client(repository_id)
            if not lsp_client:
                return json.dumps(
                    {
                        "error": f"LSP not available for repository '{repository_id}'",
                        "symbol": symbol,
                    }
                )

            # Resolve file path
            resolved_path = self._resolve_file_path(file_path, repo_config.workspace)
            file_uri = Path(resolved_path).as_uri()

            # Get definition from LSP
            definitions = await lsp_client.get_definition(
                file_uri, line - 1, column - 1
            )

            if not definitions:
                return json.dumps(
                    {
                        "symbol": symbol,
                        "repository_id": repository_id,
                        "definitions": [],
                        "message": "No definition found",
                    }
                )

            # Convert LSP response to user-friendly format
            results = []
            for defn in definitions:
                if "uri" in defn and "range" in defn:
                    file_path = Path(defn["uri"].replace("file://", ""))
                    start_pos = defn["range"]["start"]
                    results.append(
                        {
                            "file": str(file_path),
                            "line": start_pos["line"] + 1,  # Convert to 1-based
                            "column": start_pos["character"] + 1,
                        }
                    )

            return json.dumps(
                {
                    "symbol": symbol,
                    "repository_id": repository_id,
                    "definitions": results,
                    "count": len(results),
                }
            )

        except Exception as e:
            self.logger.exception(
                f"Error finding definition for {symbol} in {repository_id}"
            )
            return json.dumps(
                {
                    "error": f"Definition search failed: {e!s}",
                    "symbol": symbol,
                    "repository_id": repository_id,
                }
            )

    async def find_references(
        self,
        repository_id: str,
        symbol: str,
        file_path: str,
        line: int,
        column: int,
    ) -> str:
        """Find all references to a symbol using LSP."""
        try:
            repo_config = self.repository_manager.get_repository(repository_id)
            if not repo_config:
                return json.dumps(
                    {
                        "error": f"Repository '{repository_id}' not found",
                        "symbol": symbol,
                    }
                )

            # Get or create LSP client for this repository
            lsp_client = await self._get_lsp_client(repository_id)
            if not lsp_client:
                return json.dumps(
                    {
                        "error": f"LSP not available for repository '{repository_id}'",
                        "symbol": symbol,
                    }
                )

            # Resolve file path
            resolved_path = self._resolve_file_path(file_path, repo_config.workspace)
            file_uri = Path(resolved_path).as_uri()

            # Get references from LSP
            references = await lsp_client.get_references(file_uri, line - 1, column - 1)

            if not references:
                return json.dumps(
                    {
                        "symbol": symbol,
                        "repository_id": repository_id,
                        "references": [],
                        "message": "No references found",
                    }
                )

            # Convert LSP response to user-friendly format
            results = []
            for ref in references:
                if "uri" in ref and "range" in ref:
                    file_path = Path(ref["uri"].replace("file://", ""))
                    start_pos = ref["range"]["start"]
                    results.append(
                        {
                            "file": str(file_path),
                            "line": start_pos["line"] + 1,  # Convert to 1-based
                            "column": start_pos["character"] + 1,
                        }
                    )

            return json.dumps(
                {
                    "symbol": symbol,
                    "repository_id": repository_id,
                    "references": results,
                    "count": len(results),
                }
            )

        except Exception as e:
            self.logger.exception(
                f"Error finding references for {symbol} in {repository_id}"
            )
            return json.dumps(
                {
                    "error": f"Reference search failed: {e!s}",
                    "symbol": symbol,
                    "repository_id": repository_id,
                }
            )

    async def _get_lsp_client(self, repository_id: str) -> AbstractLSPClient | None:
        """Get LSP client for a repository from the repository manager."""
        # Delegate to repository manager's LSP client management
        if hasattr(self.repository_manager, 'get_lsp_client'):
            return self.repository_manager.get_lsp_client(repository_id)

        # Fallback: create our own LSP client if repository manager doesn't support it
        with self._lsp_lock:
            # Check if we already have a client
            if repository_id in self._lsp_clients:
                client = self._lsp_clients[repository_id]
                if client.state == LSPClientState.INITIALIZED:
                    return client
                else:
                    # Remove unhealthy client
                    del self._lsp_clients[repository_id]

            # Get repository configuration
            repo_config = self.repository_manager.get_repository(repository_id)
            if not repo_config:
                return None

            # Only support Python repositories for now
            if repo_config.language != Language.PYTHON:
                self.logger.debug(
                    f"LSP not supported for language {repo_config.language}"
                )
                return None

            try:
                # Create new LSP client
                client = CodebaseLSPClient(
                    workspace_root=repo_config.workspace,
                    python_path=repo_config.python_path,
                )

                # Start the client
                if await client.connect():
                    self._lsp_clients[repository_id] = client
                    return client
                else:
                    self.logger.error(f"Failed to start LSP client for {repository_id}")
                    return None

            except Exception as e:
                self.logger.error(f"Error creating LSP client for {repository_id}: {e}")
                return None

    def _resolve_file_path(self, file_path: str, workspace_root: str) -> str:
        """
        Resolve file path to absolute path within workspace.

        Args:
            file_path: Relative or absolute file path
            workspace_root: Root directory of the workspace

        Returns:
            Absolute file path within workspace

        Raises:
            ValueError: If file path is outside workspace
        """
        workspace_path = Path(workspace_root).resolve()

        if os.path.isabs(file_path):
            resolved_path = Path(file_path).resolve()
        else:
            resolved_path = (workspace_path / file_path).resolve()

        # Security check: ensure resolved path is within workspace
        try:
            resolved_path.relative_to(workspace_path)
        except ValueError:
            raise ValueError(f"File path is outside workspace: {file_path}") from None

        if not resolved_path.exists():
            raise ValueError(f"File does not exist: {resolved_path}")

        return str(resolved_path)

    async def shutdown(self) -> None:
        """Shutdown all LSP clients and clean up resources."""
        with self._lsp_lock:
            for repository_id, client in self._lsp_clients.items():
                try:
                    await client.disconnect()
                except Exception as e:
                    self.logger.error(
                        f"Error disconnecting LSP client for {repository_id}: {e}"
                    )

            self._lsp_clients.clear()

        self.logger.info("CodebaseTools shutdown complete")


# Backward compatibility functions for existing code
def get_tools(repo_name: str, repository_workspace: str) -> list[dict]:
    """Get codebase tool definitions for MCP registration (backward compatibility)"""
    # Create a temporary tools instance for compatibility
    repo_manager = RepositoryManager()
    tools = CodebaseTools(repo_manager)
    return tools.get_tools(repo_name, repository_workspace)


async def execute_tool(tool_name: str, **kwargs) -> str:
    """Execute a codebase tool by name (backward compatibility)"""
    # This requires a properly configured tools instance
    # In practice, this should be called through a configured CodebaseTools instance
    repo_manager = RepositoryManager()
    repo_manager.load_configuration()

    tools = CodebaseTools(repo_manager)
    return await tools.execute_tool(tool_name, **kwargs)
