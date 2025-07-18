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
from collections.abc import Callable
from pathlib import Path
from typing import Any, ClassVar

from async_lsp_client import AbstractAsyncLSPClient, AsyncLSPClient, AsyncLSPClientState
from constants import Language
from repository_manager import AbstractRepositoryManager
from symbol_storage import AbstractSymbolStorage

logger = logging.getLogger(__name__)


# Type for LSP client factory
LSPClientFactory = Callable[[str, str], AbstractAsyncLSPClient]


def create_async_lsp_client(workspace_root: str, python_path: str) -> AsyncLSPClient:
    """Factory function to create AsyncLSPClient instances."""
    return AsyncLSPClient.create(workspace_root, python_path)


# LSP Tools Implementation - Now using AsyncLSPClient directly


class CodebaseTools:
    """Object-oriented codebase tools with dependency injection."""

    # Class-level mapping of tool names to method names
    TOOL_HANDLERS: ClassVar[dict[str, str]] = {
        "codebase_health_check": "codebase_health_check",
        "search_symbols": "search_symbols",
        "find_definition": "find_definition",
        "find_references": "find_references",
        "find_hover": "find_hover",
    }

    def __init__(
        self,
        repository_manager: AbstractRepositoryManager,
        symbol_storage: AbstractSymbolStorage,
        lsp_client_factory: LSPClientFactory,
    ):
        """
        Initialize codebase tools with dependencies.

        Args:
            repository_manager: Repository manager for accessing repository configurations
            symbol_storage: Symbol storage for caching
            lsp_client_factory: Factory function to create LSP clients
        """
        self.repository_manager = repository_manager
        self.symbol_storage = symbol_storage
        self.lsp_client_factory = lsp_client_factory
        self.logger = logging.getLogger(__name__)

        # Thread safety for LSP client cache
        self._lsp_lock = threading.Lock()
        self._lsp_clients: dict[str, AbstractAsyncLSPClient] = {}

    def _user_friendly_to_lsp_position(self, line: int, column: int) -> dict:
        """Convert user-friendly (1-based) coordinates to LSP (0-based) coordinates."""
        return {
            "line": line - 1,
            "character": column - 1,
        }

    def _lsp_position_to_user_friendly(self, line: int, character: int) -> dict:
        """Convert LSP (0-based) coordinates to user-friendly (1-based) coordinates."""
        return {
            "line": line + 1,
            "column": character + 1,
        }

    def _path_to_uri(self, path: str) -> str:
        """Convert file path to URI."""
        return Path(path).as_uri()

    def _uri_to_path(self, uri: str) -> str:
        """Convert URI to file path."""
        return str(Path(uri.replace("file://", "")))

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
            {
                "name": "find_hover",
                "description": f"Find hover information for a symbol at a specific position in the {repo_name} repository using LSP. Returns detailed information about the symbol including documentation and type information.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "repository_id": {
                            "type": "string",
                            "description": "Repository identifier",
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
                        "character": {
                            "type": "integer",
                            "description": "Character position where the symbol appears (1-based)",
                            "minimum": 1,
                        },
                    },
                    "required": [
                        "repository_id",
                        "file_path",
                        "line",
                        "character",
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
        if tool_name not in self.TOOL_HANDLERS:
            return json.dumps(
                {
                    "error": f"Unknown tool: {tool_name}",
                    "available_tools": list(self.TOOL_HANDLERS.keys()),
                }
            )

        method_name = self.TOOL_HANDLERS[tool_name]
        handler = getattr(self, method_name)
        try:
            # Call handler with only keyword arguments to avoid parameter conflicts
            return await handler(**kwargs)
        except Exception as e:
            self.logger.exception(f"Error executing tool {tool_name}")
            return json.dumps(
                {"error": f"Tool execution failed: {e!s}", "tool": tool_name}
            )

    async def codebase_health_check(self, repository_id: str) -> str:
        """Perform a basic health check of the repository."""
        checks: dict[str, Any] = {}
        warnings: list[str] = []
        errors: list[str] = []

        try:
            repo_config = self.repository_manager.get_repository(repository_id)
            if not repo_config:
                return json.dumps(
                    {
                        "repo": repository_id,
                        "workspace": None,
                        "status": "error",
                        "checks": {},
                        "warnings": [],
                        "errors": [f"Repository '{repository_id}' not found"],
                    }
                )

            repository_workspace = repo_config.workspace

            # Check if repository exists and is accessible
            if not os.path.exists(repository_workspace):
                return json.dumps(
                    {
                        "repo": repository_id,
                        "workspace": repository_workspace,
                        "status": "error",
                        "checks": {"path_exists": False},
                        "warnings": [],
                        "errors": [
                            f"Repository path does not exist: {repository_workspace}"
                        ],
                    }
                )

            checks["path_exists"] = True

            if not os.access(repository_workspace, os.R_OK):
                return json.dumps(
                    {
                        "repo": repository_id,
                        "workspace": repository_workspace,
                        "status": "error",
                        "checks": {"path_exists": True, "path_readable": False},
                        "warnings": [],
                        "errors": [
                            f"Repository path is not readable: {repository_workspace}"
                        ],
                    }
                )

            checks["path_readable"] = True

            # Check if it's a git repository
            git_dir = os.path.join(repository_workspace, ".git")
            if not os.path.exists(git_dir):
                return json.dumps(
                    {
                        "repo": repository_id,
                        "workspace": repository_workspace,
                        "status": "warning",
                        "checks": {
                            "path_exists": True,
                            "path_readable": True,
                            "is_git_repo": False,
                        },
                        "warnings": [
                            f"Directory exists but is not a Git repository: {repository_workspace}"
                        ],
                        "errors": [],
                    }
                )

            checks["is_git_repo"] = True

            # Get basic git info and check git responsiveness
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
                checks["git_responsive"] = True
                checks["current_commit"] = current_commit
            except subprocess.TimeoutExpired:
                checks["git_responsive"] = False
                warnings.append("Git command timed out")
                current_commit = "unknown"
            except Exception as e:
                checks["git_responsive"] = False
                warnings.append(f"Git command failed: {e}")
                current_commit = "unknown"

            # Check LSP status if applicable
            lsp_status = None
            if hasattr(self.repository_manager, "get_lsp_status"):
                lsp_status = self.repository_manager.get_lsp_status(repository_id)
                checks["lsp_status"] = lsp_status

            # Determine overall status
            overall_status = "healthy"
            if errors:
                overall_status = "error"
            elif warnings:
                overall_status = "warning"

            return json.dumps(
                {
                    "repo": repository_id,
                    "workspace": repository_workspace,
                    "status": overall_status,
                    "checks": checks,
                    "warnings": warnings,
                    "errors": errors,
                    "current_commit": current_commit,
                    "lsp_status": lsp_status,
                }
            )

        except Exception as e:
            self.logger.exception(f"Error in codebase health check for {repository_id}")
            return json.dumps(
                {
                    "repo": repository_id,
                    "workspace": repository_workspace
                    if "repository_workspace" in locals()
                    else None,
                    "status": "error",
                    "checks": checks,
                    "warnings": warnings,
                    "errors": [f"Health check failed: {e!s}"],
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
            # Validate limit parameter
            if limit < 1 or limit > 100:
                return json.dumps(
                    {
                        "error": "Limit must be between 1 and 100",
                        "repository_id": repository_id,
                        "query": query,
                        "symbols": [],
                    }
                )

            repo_config = self.repository_manager.get_repository(repository_id)
            if not repo_config:
                return json.dumps(
                    {"error": f"Repository '{repository_id}' not found", "symbols": []}
                )

            # Search symbols using symbol storage
            symbols = self.symbol_storage.search_symbols(
                repository_id=repository_id,
                query=query,
                symbol_kind=symbol_kind,
                limit=limit,
            )

            return json.dumps(
                {
                    "repository_id": repository_id,
                    "query": query,
                    "symbol_kind": symbol_kind,
                    "limit": limit,
                    "symbols": [symbol.to_dict() for symbol in symbols],
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
        file_path: str | None = None,
        line: int | None = None,
        column: int | None = None,
    ) -> str:
        """Find the definition of a symbol using LSP.

        If file_path, line, and column are not provided, will first search for the symbol
        using search_symbols to find its location, then get the definition.
        """
        self.logger.info(
            f"Finding definition for symbol '{symbol}' in repository '{repository_id}'"
        )

        # If location not provided, search for the symbol first
        if file_path is None or line is None or column is None:
            self.logger.debug(f"Location not provided, searching for symbol '{symbol}'")
            search_result = await self.search_symbols(repository_id, symbol, limit=1)
            search_data = json.loads(search_result)

            if "error" in search_data:
                return json.dumps(
                    {
                        "error": f"Failed to search for symbol: {search_data['error']}",
                        "symbol": symbol,
                    }
                )

            symbols = search_data.get("symbols", [])
            if not symbols:
                return json.dumps(
                    {
                        "error": f"Symbol '{symbol}' not found in repository '{repository_id}'",
                        "symbol": symbol,
                    }
                )

            # Use the first symbol found
            symbol_info = symbols[0]
            file_path = symbol_info.get("file_path")
            line = symbol_info.get("line")
            column = symbol_info.get("column", 0)  # Default to column 0 if not provided

            self.logger.debug(f"Found symbol at {file_path}:{line}:{column}")

        self.logger.info(
            f"Getting definition for symbol '{symbol}' at {file_path}:{line}:{column}"
        )
        try:
            repo_config = self.repository_manager.get_repository(repository_id)
            if not repo_config:
                self.logger.error(f"Repository '{repository_id}' not found")
                return json.dumps(
                    {
                        "error": f"Repository '{repository_id}' not found",
                        "symbol": symbol,
                    }
                )

            self.logger.debug(
                f"Repository config found: {repo_config.workspace}, language: {repo_config.language}"
            )

            # Get or create LSP client for this repository
            self.logger.debug(f"Getting LSP client for repository '{repository_id}'")
            lsp_client = await self._get_lsp_client(repository_id)
            if not lsp_client:
                self.logger.error(
                    f"LSP client not available for repository '{repository_id}'"
                )
                return json.dumps(
                    {
                        "error": f"LSP not available for repository '{repository_id}'",
                        "symbol": symbol,
                    }
                )

            self.logger.debug(
                f"LSP client obtained successfully, state: {lsp_client.state}"
            )

            # Resolve file path
            resolved_path = self._resolve_file_path(file_path, repo_config.workspace)
            file_uri = Path(resolved_path).as_uri()
            self.logger.debug(f"Resolved file path: {resolved_path} -> {file_uri}")

            # Get definition from LSP
            self.logger.debug(
                f"Calling LSP get_definition with file_uri={file_uri}, line={line - 1}, column={column - 1}"
            )
            definitions = await lsp_client.get_definition(
                file_uri, line - 1, column - 1
            )

            self.logger.debug(
                f"LSP returned {len(definitions) if definitions else 0} definitions"
            )

            if not definitions:
                self.logger.info(
                    f"No definition found for symbol '{symbol}' at {file_path}:{line}:{column}"
                )
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
            for i, defn in enumerate(definitions):
                self.logger.debug(f"Processing definition {i + 1}: {defn}")
                if "uri" in defn and "range" in defn:
                    file_path = str(Path(defn["uri"].replace("file://", "")))
                    start_pos = defn["range"]["start"]
                    results.append(
                        {
                            "file": file_path,
                            "line": start_pos["line"] + 1,  # Convert to 1-based
                            "column": start_pos["character"] + 1,
                        }
                    )

            self.logger.info(f"Found {len(results)} definitions for symbol '{symbol}'")
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
        self.logger.info(
            f"Finding references for symbol '{symbol}' at {file_path}:{line}:{column} in repository '{repository_id}'"
        )
        try:
            repo_config = self.repository_manager.get_repository(repository_id)
            if not repo_config:
                self.logger.error(f"Repository '{repository_id}' not found")
                return json.dumps(
                    {
                        "error": f"Repository '{repository_id}' not found",
                        "symbol": symbol,
                    }
                )

            self.logger.debug(
                f"Repository config found: {repo_config.workspace}, language: {repo_config.language}"
            )

            # Get or create LSP client for this repository
            self.logger.debug(f"Getting LSP client for repository '{repository_id}'")
            lsp_client = await self._get_lsp_client(repository_id)
            if not lsp_client:
                self.logger.error(
                    f"LSP client not available for repository '{repository_id}'"
                )
                return json.dumps(
                    {
                        "error": f"LSP not available for repository '{repository_id}'",
                        "symbol": symbol,
                    }
                )

            self.logger.debug(
                f"LSP client obtained successfully, state: {lsp_client.state}"
            )

            # Resolve file path
            resolved_path = self._resolve_file_path(file_path, repo_config.workspace)
            file_uri = Path(resolved_path).as_uri()
            self.logger.debug(f"Resolved file path: {resolved_path} -> {file_uri}")

            # Get references from LSP
            self.logger.debug(
                f"Calling LSP get_references with file_uri={file_uri}, line={line - 1}, column={column - 1}"
            )
            references = await lsp_client.get_references(file_uri, line - 1, column - 1)

            self.logger.debug(
                f"LSP returned {len(references) if references else 0} references"
            )

            if not references:
                self.logger.info(
                    f"No references found for symbol '{symbol}' at {file_path}:{line}:{column}"
                )
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
            for i, ref in enumerate(references):
                self.logger.debug(f"Processing reference {i + 1}: {ref}")
                if "uri" in ref and "range" in ref:
                    file_path = str(Path(ref["uri"].replace("file://", "")))
                    start_pos = ref["range"]["start"]
                    results.append(
                        {
                            "file": file_path,
                            "line": start_pos["line"] + 1,  # Convert to 1-based
                            "column": start_pos["character"] + 1,
                        }
                    )

            self.logger.info(f"Found {len(results)} references for symbol '{symbol}'")
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

    async def find_hover(
        self, repository_id: str, file_path: str, line: int, character: int
    ) -> str:
        """Find hover information for a symbol at a specific position.

        Args:
            repository_id: The repository identifier
            file_path: Path to the file relative to repository root
            line: Line number (1-based)
            character: Character position (1-based)

        Returns:
            JSON string containing hover information or error details
        """
        try:
            self.logger.debug(
                f"Getting hover info for {repository_id}:{file_path}:{line}:{character}"
            )

            # Get repository config
            repo_config = self.repository_manager.get_repository(repository_id)
            if not repo_config:
                return json.dumps(
                    {
                        "error": f"Repository '{repository_id}' not found",
                        "file_path": file_path,
                        "line": line,
                        "character": character,
                    }
                )

            # Get LSP client
            client = await self._get_lsp_client(repository_id)
            if not client:
                return json.dumps(
                    {
                        "error": f"LSP client not available for repository {repository_id}",
                        "file_path": file_path,
                        "line": line,
                        "character": character,
                    }
                )

            # Resolve file path and convert to URI
            resolved_path = self._resolve_file_path(file_path, repo_config.workspace)
            file_uri = Path(resolved_path).as_uri()

            # Get hover information (convert 1-based to 0-based coordinates)
            hover_info = await client.get_hover(file_uri, line - 1, character - 1)

            if not hover_info:
                return json.dumps(
                    {
                        "message": "No hover information available",
                        "file_path": file_path,
                        "line": line,
                        "character": character,
                    }
                )

            return json.dumps(
                {
                    "hover_info": hover_info,
                    "file_path": file_path,
                    "line": line,
                    "character": character,
                    "repository_id": repository_id,
                }
            )

        except Exception as e:
            self.logger.error(
                f"Error getting hover info for {repository_id}:{file_path}:{line}:{character}: {e}",
                exc_info=True,
            )
            return json.dumps(
                {
                    "error": f"Hover request failed: {e!s}",
                    "file_path": file_path,
                    "line": line,
                    "character": character,
                    "repository_id": repository_id,
                }
            )

    async def _get_lsp_client(
        self, repository_id: str
    ) -> AbstractAsyncLSPClient | None:
        """Get LSP client for a repository from the repository manager."""
        self.logger.debug(f"Getting LSP client for repository '{repository_id}'")

        # Delegate to repository manager's LSP client management
        if hasattr(self.repository_manager, "get_lsp_client"):
            self.logger.debug(
                "Repository manager has get_lsp_client method, delegating"
            )
            client = self.repository_manager.get_lsp_client(repository_id)
            if client:
                self.logger.debug(
                    f"Repository manager returned LSP client with state: {client.state}"
                )
                self.logger.info(f"LSP client type: {type(client)} - {client.__class__.__module__}.{client.__class__.__name__}")
            else:
                self.logger.debug("Repository manager returned no LSP client")
            return client

        # Fallback: create our own LSP client if repository manager doesn't support it
        self.logger.debug(
            "Repository manager doesn't support LSP clients, creating our own"
        )
        with self._lsp_lock:
            # Check if we already have a client
            if repository_id in self._lsp_clients:
                existing_client = self._lsp_clients[repository_id]
                self.logger.debug(
                    f"Found existing LSP client with state: {existing_client.state}"
                )
                if existing_client.state == AsyncLSPClientState.INITIALIZED:
                    self.logger.debug("Returning existing healthy LSP client")
                    return existing_client
                else:
                    # Remove unhealthy client
                    self.logger.debug(
                        f"Removing unhealthy LSP client with state: {existing_client.state}"
                    )
                    del self._lsp_clients[repository_id]

            # Get repository configuration
            repo_config = self.repository_manager.get_repository(repository_id)
            if not repo_config:
                self.logger.error(f"Repository config not found for '{repository_id}'")
                return None

            self.logger.debug(
                f"Repository config: workspace={repo_config.workspace}, language={repo_config.language}, python_path={repo_config.python_path}"
            )

            # Only support Python repositories for now
            if repo_config.language != Language.PYTHON:
                self.logger.debug(
                    f"LSP not supported for language {repo_config.language}"
                )
                return None

            try:
                self.logger.debug("Creating new LSP client using factory")
                # Create new LSP client using the factory
                new_client: AbstractAsyncLSPClient = self.lsp_client_factory(
                    repo_config.workspace,
                    repo_config.python_path,
                )

                self.logger.debug(
                    f"Starting LSP client for repository '{repository_id}'"
                )
                # Start the client
                if await new_client.start():
                    self.logger.info(
                        f"Successfully started LSP client for repository '{repository_id}'"
                    )
                    self._lsp_clients[repository_id] = new_client
                    return new_client
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

    def validate(self, logger, repositories: dict) -> None:
        """Validate codebase service prerequisites."""
        try:
            logger.info("🔍 Validating codebase service prerequisites...")

            # Validate symbol storage
            if not self.symbol_storage:
                raise RuntimeError("Symbol storage not initialized")

            # Test symbol storage connection
            try:
                # Try to perform a basic operation to verify the storage works
                self.symbol_storage.health_check()
                logger.debug("✅ Symbol storage health check passed")
            except Exception as e:
                raise RuntimeError(f"Symbol storage health check failed: {e}") from e

            # Validate repository manager
            if not self.repository_manager:
                raise RuntimeError("Repository manager not initialized")

            logger.info("✅ Codebase service validation completed")

        except Exception as e:
            logger.error(f"❌ Codebase service validation failed: {e}")
            raise

    async def shutdown(self) -> None:
        """Shutdown all LSP clients and clean up resources."""
        with self._lsp_lock:
            for repository_id, client in self._lsp_clients.items():
                try:
                    await client.stop()
                except Exception as e:
                    self.logger.error(
                        f"Error stopping LSP client for {repository_id}: {e}"
                    )

            self._lsp_clients.clear()

        self.logger.info("CodebaseTools shutdown complete")


# End of CodebaseTools class
