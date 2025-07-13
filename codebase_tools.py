#!/usr/bin/env python3

"""
Codebase Tools for MCP Server
Contains codebase-related tool implementations for repository analysis and management.
"""

import json
import logging
import os
import subprocess
import sys
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from constants import DATA_DIR, Language
from lsp_client import AbstractLSPClient, LSPClientState
from lsp_constants import LSPMethod
from pyright_lsp_manager import PyrightLSPManager
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


def _resolve_file_path(file_path: str, workspace_root: str) -> str:
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

    if Path(file_path).is_absolute():
        resolved_path = Path(file_path).resolve()
    else:
        resolved_path = (workspace_path / file_path).resolve()

    # Ensure the file is within the workspace
    try:
        resolved_path.relative_to(workspace_path)
    except ValueError as e:
        raise ValueError(
            f"File path '{file_path}' is outside workspace '{workspace_root}'"
        ) from e

    return str(resolved_path)


def _path_to_uri(file_path: str) -> str:
    """Convert file path to LSP URI format."""
    return f"file://{Path(file_path).as_posix()}"


def _uri_to_path(uri: str) -> str:
    """Convert LSP URI to file path."""
    if uri.startswith("file://"):
        return uri[7:]  # Remove "file://" prefix
    return uri


def _lsp_position_to_user_friendly(line: int, character: int) -> dict[str, int]:
    """
    Convert LSP position (0-based) to user-friendly format (1-based).

    Args:
        line: LSP line number (0-based)
        character: LSP character position (0-based)

    Returns:
        Dictionary with 1-based line and column numbers
    """
    return {
        "line": line + 1,
        "column": character + 1,
    }


def _user_friendly_to_lsp_position(line: int, column: int) -> dict[str, int]:
    """
    Convert user-friendly position (1-based) to LSP format (0-based).

    Args:
        line: User-friendly line number (1-based)
        column: User-friendly column position (1-based)

    Returns:
        Dictionary with 0-based line and character positions
    """
    return {
        "line": max(0, line - 1),
        "character": max(0, column - 1),
    }


def validate(logger: logging.Logger, repositories: dict[str, Any]) -> None:
    """
    Validate codebase service prerequisites.

    Args:
        logger: Logger instance for debugging and monitoring
        repositories: Dictionary of repository configurations

    Raises:
        RuntimeError: If codebase prerequisites are not met
    """
    logger.info("Validating codebase service prerequisites...")

    # Validate symbol storage service
    _validate_symbol_storage(logger)

    # Validate language-specific tools for each repository
    for repo_name, repo_config in repositories.items():
        language = repo_config.language
        workspace = repo_config.workspace

        # Validate workspace accessibility
        _validate_workspace_access(logger, workspace, repo_name)

        # Validate language-specific LSP tools
        if language == Language.PYTHON:
            _validate_python_lsp_tools(logger, repo_name)

    logger.info(
        f"✅ Codebase service validation passed for {len(repositories)} repositories"
    )


def _validate_workspace_access(
    logger: logging.Logger, workspace: str, repo_name: str
) -> None:
    """
    Validate that the workspace is accessible for reading/writing.
    """
    if not os.path.exists(workspace):
        raise RuntimeError(
            f"Repository workspace does not exist: {workspace} (repo: {repo_name})"
        )

    if not os.path.isdir(workspace):
        raise RuntimeError(
            f"Repository workspace is not a directory: {workspace} (repo: {repo_name})"
        )

    if not os.access(workspace, os.R_OK):
        raise RuntimeError(
            f"Repository workspace is not readable: {workspace} (repo: {repo_name})"
        )

    if not os.access(workspace, os.W_OK):
        raise RuntimeError(
            f"Repository workspace is not writable: {workspace} (repo: {repo_name})"
        )

    logger.debug(f"Workspace access validation passed: {workspace} (repo: {repo_name})")


def _validate_symbol_storage(logger: logging.Logger) -> None:
    """
    Validate that symbol storage service is available and configured.
    """
    try:
        # Create storage instance and test connection
        storage = SQLiteSymbolStorage(DATA_DIR / "symbols.db")
        if not storage.health_check():
            raise RuntimeError("Symbol storage connection failed")

        logger.debug("Symbol storage validation passed: connection successful")
    except ImportError as e:
        raise RuntimeError(
            f"Symbol storage not available: {e}. Required for codebase indexing."
        ) from e
    except Exception as e:
        raise RuntimeError(
            f"Symbol storage validation failed: {e}. Required for codebase indexing."
        ) from e


def _validate_python_lsp_tools(logger: logging.Logger, repo_name: str) -> None:
    """
    Validate Python-specific LSP tools for codebase service.
    """
    # Validate pyright is available since that's the main LSP tool for Python
    try:
        # Try to use pyright from virtual environment first, then system PATH
        pyright_cmd = "pyright"
        if hasattr(sys, "real_prefix") or (
            hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix
        ):
            # We're in a virtual environment, try the venv path first
            venv_pyright = Path(sys.prefix) / "bin" / "pyright"
            if venv_pyright.exists():
                pyright_cmd = str(venv_pyright)

        result = subprocess.run(
            [pyright_cmd, "--version"],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        version = result.stdout.strip()
        logger.debug(
            f"Python LSP tools validation passed for {repo_name}: pyright {version}"
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        raise RuntimeError(
            f"Python LSP tools not available for repository {repo_name}. "
            "Please add it to requirements.txt"
        ) from e
    except subprocess.TimeoutExpired:
        raise RuntimeError(
            f"Pyright command timed out for repository {repo_name}"
        ) from None


def get_tools(repo_name: str, repository_workspace: str) -> list[dict]:
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
                "properties": {},
                "required": [],
            },
        },
        {
            "name": "search_symbols",
            "description": f"Search for symbols (functions, classes, variables) in the {repo_name} repository. Supports fuzzy matching by symbol name with optional filtering by symbol kind.",
            "inputSchema": {
                "type": "object",
                "properties": {
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
                "required": ["query"],
            },
        },
        {
            "name": "find_definition",
            "description": f"Find the definition of a symbol in the {repo_name} repository using LSP. Returns the exact file location and line number where the symbol is defined.",
            "inputSchema": {
                "type": "object",
                "properties": {
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
                "required": ["symbol", "file_path", "line", "column"],
            },
        },
        {
            "name": "find_references",
            "description": f"Find all references to a symbol in the {repo_name} repository using LSP. Returns all usage locations for the symbol across the codebase.",
            "inputSchema": {
                "type": "object",
                "properties": {
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
                    "include_declaration": {
                        "type": "boolean",
                        "description": "Whether to include the declaration/definition in results (default: true)",
                        "default": True,
                    },
                },
                "required": ["symbol", "file_path", "line", "column"],
            },
        },
    ]


async def execute_codebase_health_check(
    repo_name: str, repository_workspace: str
) -> str:
    """Execute basic health check for the repository

    Args:
        repo_name: Repository name to check
        repository_workspace: Path to the repository

    Returns:
        JSON string with health check results
    """
    logger.info(f"Performing health check for repository: {repo_name}")

    try:
        repository_workspace_obj = Path(repository_workspace)

        health_status: dict[str, Any] = {
            "repo": repo_name,
            "workspace": str(repository_workspace_obj),
            "status": "healthy",
            "checks": {},
            "warnings": [],
            "errors": [],
        }

        # Check 1: Repository exists and is accessible
        if not repository_workspace_obj.exists():
            health_status["status"] = "unhealthy"
            health_status["checks"]["path_exists"] = False
            health_status["errors"].append(
                f"Repository path does not exist: {repository_workspace_obj}"
            )
            return json.dumps(health_status)

        if not repository_workspace_obj.is_dir():
            health_status["status"] = "unhealthy"
            health_status["checks"]["path_exists"] = True
            health_status["checks"]["is_directory"] = False
            health_status["errors"].append(
                f"Repository path is not a directory: {repository_workspace_obj}"
            )
            return json.dumps(health_status)

        health_status["checks"]["path_exists"] = True
        health_status["checks"]["is_directory"] = True

        # Check 2: Git repository validation
        git_dir = repository_workspace_obj / ".git"
        if not git_dir.exists():
            health_status["status"] = "unhealthy"
            health_status["checks"]["is_git_repo"] = False
            health_status["errors"].append(
                "Not a Git repository (no .git directory found)"
            )
            return json.dumps(health_status)

        health_status["checks"]["is_git_repo"] = True

        # Check 3: Basic Git metadata access
        try:
            # Get current branch
            result = subprocess.run(
                ["git", "branch", "--show-current"],
                cwd=repository_workspace_obj,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                current_branch = result.stdout.strip()
                health_status["checks"]["current_branch"] = current_branch
            else:
                health_status["warnings"].append(
                    "Could not determine current Git branch"
                )

            # Get remote origin URL
            result = subprocess.run(
                ["git", "config", "--get", "remote.origin.url"],
                cwd=repository_workspace_obj,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                remote_url = result.stdout.strip()
                health_status["checks"]["has_remote"] = bool(remote_url)
                if remote_url:
                    health_status["checks"]["remote_url"] = remote_url
            else:
                health_status["checks"]["has_remote"] = False

            health_status["checks"]["git_responsive"] = True

        except subprocess.TimeoutExpired:
            health_status["warnings"].append("Git commands timed out")
            health_status["checks"]["git_responsive"] = False
        except subprocess.CalledProcessError as e:
            health_status["warnings"].append(f"Could not access Git metadata: {e}")
            health_status["checks"]["git_responsive"] = False

        # Determine overall health
        if health_status["errors"]:
            health_status["status"] = "unhealthy"
        elif health_status["warnings"]:
            health_status["status"] = "warning"
        else:
            health_status["status"] = "healthy"

        return json.dumps(health_status, indent=2)

    except Exception as e:
        logger.exception(f"Error during health check for {repo_name}")
        error_response = {
            "repo": repo_name,
            "workspace": repository_workspace,
            "status": "error",
            "errors": [f"Health check failed: {e!s}"],
            "checks": {},
            "warnings": [],
        }
        return json.dumps(error_response)


async def execute_search_symbols(
    repo_name: str,
    repository_workspace: str,
    query: str,
    symbol_storage: AbstractSymbolStorage,
    symbol_kind: str | None = None,
    limit: int = 50,
) -> str:
    """Execute symbol search for the repository with enhanced error handling

    Args:
        repo_name: Repository name to search
        repository_workspace: Path to the repository
        query: Search query for symbol names
        symbol_storage: Symbol storage instance for search operations
        symbol_kind: Optional filter by symbol kind (function, class, variable)
        limit: Maximum number of results to return

    Returns:
        JSON string with search results
    """
    logger.info(
        f"Searching symbols in repository: {repo_name}, query: '{query}', kind: {symbol_kind}, limit: {limit}"
    )

    try:
        # Validate inputs
        if not query or not query.strip():
            return json.dumps(
                {
                    "error": "Query cannot be empty",
                    "query": query,
                    "repository": repo_name,
                    "symbols": [],
                    "total_results": 0,
                }
            )

        if limit < 1 or limit > 100:
            return json.dumps(
                {
                    "error": "Limit must be between 1 and 100",
                    "query": query,
                    "repository": repo_name,
                    "symbols": [],
                    "total_results": 0,
                }
            )

        # Validate symbol_kind if provided
        valid_kinds = [
            "function",
            "class",
            "variable",
            "method",
            "property",
            "constant",
            "module",
        ]
        if symbol_kind and symbol_kind not in valid_kinds:
            return json.dumps(
                {
                    "error": f"Invalid symbol kind '{symbol_kind}'. Valid kinds: {valid_kinds}",
                    "query": query,
                    "repository": repo_name,
                    "symbols": [],
                    "total_results": 0,
                }
            )

        # Execute symbol search with timeout and error handling
        try:
            symbols = symbol_storage.search_symbols(
                query=query,
                repository_id=repo_name,
                symbol_kind=symbol_kind,
                limit=limit,
            )
        except Exception as search_error:
            logger.error(f"Database search error for {repo_name}: {search_error}")
            return json.dumps(
                {
                    "error": f"Database search failed: {search_error!s}",
                    "query": query,
                    "repository": repo_name,
                    "symbols": [],
                    "total_results": 0,
                    "troubleshooting": {
                        "suggestions": [
                            "Check if the repository has been indexed",
                            "Try a simpler query",
                            "Check database connectivity",
                        ]
                    },
                }
            )

        # Format results for JSON response
        results = []
        for symbol in symbols:
            try:
                results.append(
                    {
                        "name": symbol.name,
                        "kind": symbol.kind.value,
                        "file_path": symbol.file_path,
                        "line_number": symbol.line_number,
                        "column_number": symbol.column_number,
                        "docstring": symbol.docstring,
                        "repository_id": symbol.repository_id,
                    }
                )
            except Exception as format_error:
                logger.warning(f"Error formatting symbol result: {format_error}")
                # Continue with other symbols
                continue

        response = {
            "query": query,
            "symbol_kind": symbol_kind,
            "limit": limit,
            "repository": repo_name,
            "total_results": len(results),
            "symbols": results,
        }

        logger.info(f"Found {len(results)} symbols for query '{query}' in {repo_name}")
        return json.dumps(response, indent=2)

    except Exception as e:
        logger.exception(f"Error during symbol search for {repo_name}")
        error_response = {
            "query": query,
            "repository": repo_name,
            "error": f"Symbol search failed: {e!s}",
            "symbols": [],
            "total_results": 0,
            "troubleshooting": {
                "error_type": type(e).__name__,
                "suggestions": [
                    "Check repository configuration",
                    "Verify database is accessible",
                    "Try re-indexing the repository",
                ],
            },
        }
        return json.dumps(error_response)


async def execute_find_definition(
    repo_name: str,
    repository_workspace: str,
    symbol: str,
    file_path: str,
    line: int,
    column: int,
    python_path: str | None = None,
) -> str:
    """Execute LSP-based definition lookup for a symbol

    Args:
        repo_name: Repository name for logging
        repository_workspace: Path to the repository workspace
        symbol: Symbol name to find definition for
        file_path: File path containing the symbol
        line: Line number (1-based)
        column: Column number (1-based)
        python_path: Optional Python path for LSP server

    Returns:
        JSON string with definition results
    """
    logger.info(
        f"Finding definition for '{symbol}' in {repo_name} at {file_path}:{line}:{column}"
    )

    try:
        # Resolve file path
        resolved_file_path = _resolve_file_path(file_path, repository_workspace)

        # Check if file exists
        if not Path(resolved_file_path).exists():
            return json.dumps(
                {
                    "error": f"File not found: {file_path}",
                    "symbol": symbol,
                    "repository": repo_name,
                }
            )

        # Use default Python path if not provided
        if python_path is None:
            python_path = sys.executable

        # Create LSP client
        lsp_client = CodebaseLSPClient(repository_workspace, python_path)

        try:
            # Connect to LSP server
            if not await lsp_client.connect():
                # Fallback to symbol index search
                logger.warning("LSP server unavailable, falling back to symbol index")
                return await _fallback_definition_search(
                    repo_name, symbol, file_path, line, column
                )

            if lsp_client.state != LSPClientState.INITIALIZED:
                logger.warning(
                    "LSP client not properly initialized, falling back to symbol index"
                )
                return await _fallback_definition_search(
                    repo_name, symbol, file_path, line, column
                )

            # Convert to LSP position format
            lsp_position = _user_friendly_to_lsp_position(line, column)

            # Prepare LSP definition request
            uri = _path_to_uri(resolved_file_path)
            definition_params = {
                "textDocument": {"uri": uri},
                "position": lsp_position,
            }

            # Send definition request
            request = lsp_client.protocol.create_request(
                LSPMethod.DEFINITION, definition_params
            )
            response = await lsp_client._send_request(request, timeout=10.0)

            if response is None:
                logger.warning(
                    "LSP definition request failed, falling back to symbol index"
                )
                return await _fallback_definition_search(
                    repo_name, symbol, file_path, line, column
                )

            # Process response
            result = response.get("result")
            if not result:
                return json.dumps(
                    {
                        "symbol": symbol,
                        "repository": repo_name,
                        "query_location": {
                            "file_path": file_path,
                            "line": line,
                            "column": column,
                        },
                        "definitions": [],
                        "message": "No definition found",
                        "method": "lsp",
                    }
                )

            # Handle different result formats (Location | Location[] | LocationLink[])
            definitions = []
            if isinstance(result, list):
                for item in result:
                    if "targetUri" in item:  # LocationLink
                        def_uri = item["targetUri"]
                        def_range = item.get(
                            "targetRange", item.get("targetSelectionRange", {})
                        )
                    else:  # Location
                        def_uri = item.get("uri")
                        def_range = item.get("range", {})

                    if def_uri and def_range:
                        def_file_path = _uri_to_path(def_uri)
                        start_pos = def_range.get("start", {})
                        if start_pos:
                            user_pos = _lsp_position_to_user_friendly(
                                start_pos.get("line", 0), start_pos.get("character", 0)
                            )
                            # Make path relative to workspace if possible
                            try:
                                rel_path = Path(def_file_path).relative_to(
                                    repository_workspace
                                )
                                display_path = str(rel_path)
                            except ValueError:
                                display_path = def_file_path

                            definitions.append(
                                {
                                    "file_path": display_path,
                                    "line": user_pos["line"],
                                    "column": user_pos["column"],
                                    "absolute_path": def_file_path,
                                }
                            )
            else:
                # Single Location
                def_uri = result.get("uri")
                def_range = result.get("range", {})
                if def_uri and def_range:
                    def_file_path = _uri_to_path(def_uri)
                    start_pos = def_range.get("start", {})
                    if start_pos:
                        user_pos = _lsp_position_to_user_friendly(
                            start_pos.get("line", 0), start_pos.get("character", 0)
                        )
                        # Make path relative to workspace if possible
                        try:
                            rel_path = Path(def_file_path).relative_to(
                                repository_workspace
                            )
                            display_path = str(rel_path)
                        except ValueError:
                            display_path = def_file_path

                        definitions.append(
                            {
                                "file_path": display_path,
                                "line": user_pos["line"],
                                "column": user_pos["column"],
                                "absolute_path": def_file_path,
                            }
                        )

            result_data = {
                "symbol": symbol,
                "repository": repo_name,
                "query_location": {
                    "file_path": file_path,
                    "line": line,
                    "column": column,
                },
                "definitions": definitions,
                "total_results": len(definitions),
                "method": "lsp",
            }

            logger.info(
                f"Found {len(definitions)} definition(s) for '{symbol}' using LSP"
            )
            return json.dumps(result_data, indent=2)

        finally:
            # Always cleanup LSP client
            try:
                await lsp_client.disconnect()
            except Exception as cleanup_error:
                logger.warning(f"Error during LSP client cleanup: {cleanup_error}")

    except Exception as e:
        logger.exception(
            f"Error during LSP definition lookup for {symbol} in {repo_name}"
        )
        # Fallback to symbol index on any error
        try:
            return await _fallback_definition_search(
                repo_name, symbol, file_path, line, column
            )
        except Exception as fallback_error:
            logger.error(f"Fallback definition search also failed: {fallback_error}")
            return json.dumps(
                {
                    "error": f"Definition lookup failed: {e!s}",
                    "symbol": symbol,
                    "repository": repo_name,
                    "query_location": {
                        "file_path": file_path,
                        "line": line,
                        "column": column,
                    },
                    "definitions": [],
                    "method": "lsp_failed",
                }
            )


async def execute_find_references(
    repo_name: str,
    repository_workspace: str,
    symbol: str,
    file_path: str,
    line: int,
    column: int,
    include_declaration: bool = True,
    python_path: str | None = None,
) -> str:
    """Execute LSP-based reference lookup for a symbol

    Args:
        repo_name: Repository name for logging
        repository_workspace: Path to the repository workspace
        symbol: Symbol name to find references for
        file_path: File path containing the symbol
        line: Line number (1-based)
        column: Column number (1-based)
        include_declaration: Whether to include declaration in results
        python_path: Optional Python path for LSP server

    Returns:
        JSON string with reference results
    """
    logger.info(
        f"Finding references for '{symbol}' in {repo_name} at {file_path}:{line}:{column}"
    )

    try:
        # Resolve file path
        resolved_file_path = _resolve_file_path(file_path, repository_workspace)

        # Check if file exists
        if not Path(resolved_file_path).exists():
            return json.dumps(
                {
                    "error": f"File not found: {file_path}",
                    "symbol": symbol,
                    "repository": repo_name,
                }
            )

        # Use default Python path if not provided
        if python_path is None:
            python_path = sys.executable

        # Create LSP client
        lsp_client = CodebaseLSPClient(repository_workspace, python_path)

        try:
            # Connect to LSP server
            if not await lsp_client.connect():
                # Fallback to symbol index search
                logger.warning("LSP server unavailable, falling back to symbol index")
                return await _fallback_references_search(
                    repo_name, symbol, file_path, line, column
                )

            if lsp_client.state != LSPClientState.INITIALIZED:
                logger.warning(
                    "LSP client not properly initialized, falling back to symbol index"
                )
                return await _fallback_references_search(
                    repo_name, symbol, file_path, line, column
                )

            # Convert to LSP position format
            lsp_position = _user_friendly_to_lsp_position(line, column)

            # Prepare LSP references request
            uri = _path_to_uri(resolved_file_path)
            references_params = {
                "textDocument": {"uri": uri},
                "position": lsp_position,
                "context": {"includeDeclaration": include_declaration},
            }

            # Send references request
            request = lsp_client.protocol.create_request(
                LSPMethod.REFERENCES, references_params
            )
            response = await lsp_client._send_request(request, timeout=15.0)

            if response is None:
                logger.warning(
                    "LSP references request failed, falling back to symbol index"
                )
                return await _fallback_references_search(
                    repo_name, symbol, file_path, line, column
                )

            # Process response
            result = response.get("result")
            if not result:
                return json.dumps(
                    {
                        "symbol": symbol,
                        "repository": repo_name,
                        "query_location": {
                            "file_path": file_path,
                            "line": line,
                            "column": column,
                        },
                        "references": [],
                        "include_declaration": include_declaration,
                        "message": "No references found",
                        "method": "lsp",
                    }
                )

            # Process references
            references = []
            for item in result:
                ref_uri = item.get("uri")
                ref_range = item.get("range", {})

                if ref_uri and ref_range:
                    ref_file_path = _uri_to_path(ref_uri)
                    start_pos = ref_range.get("start", {})
                    if start_pos:
                        user_pos = _lsp_position_to_user_friendly(
                            start_pos.get("line", 0), start_pos.get("character", 0)
                        )
                        # Make path relative to workspace if possible
                        try:
                            rel_path = Path(ref_file_path).relative_to(
                                repository_workspace
                            )
                            display_path = str(rel_path)
                        except ValueError:
                            display_path = ref_file_path

                        references.append(
                            {
                                "file_path": display_path,
                                "line": user_pos["line"],
                                "column": user_pos["column"],
                                "absolute_path": ref_file_path,
                            }
                        )

            result_data = {
                "symbol": symbol,
                "repository": repo_name,
                "query_location": {
                    "file_path": file_path,
                    "line": line,
                    "column": column,
                },
                "references": references,
                "total_results": len(references),
                "include_declaration": include_declaration,
                "method": "lsp",
            }

            logger.info(
                f"Found {len(references)} reference(s) for '{symbol}' using LSP"
            )
            return json.dumps(result_data, indent=2)

        finally:
            # Always cleanup LSP client
            try:
                await lsp_client.disconnect()
            except Exception as cleanup_error:
                logger.warning(f"Error during LSP client cleanup: {cleanup_error}")

    except Exception as e:
        logger.exception(
            f"Error during LSP references lookup for {symbol} in {repo_name}"
        )
        # Fallback to symbol index on any error
        try:
            return await _fallback_references_search(
                repo_name, symbol, file_path, line, column
            )
        except Exception as fallback_error:
            logger.error(f"Fallback references search also failed: {fallback_error}")
            return json.dumps(
                {
                    "error": f"References lookup failed: {e!s}",
                    "symbol": symbol,
                    "repository": repo_name,
                    "query_location": {
                        "file_path": file_path,
                        "line": line,
                        "column": column,
                    },
                    "references": [],
                    "method": "lsp_failed",
                }
            )


async def _fallback_definition_search(
    repo_name: str, symbol: str, file_path: str, line: int, column: int
) -> str:
    """Fallback definition search using symbol index when LSP is unavailable."""
    logger.info(f"Using fallback symbol index search for definition of '{symbol}'")

    # This is a simplified fallback - in a real implementation, you might
    # use the symbol storage to find definitions
    return json.dumps(
        {
            "symbol": symbol,
            "repository": repo_name,
            "query_location": {
                "file_path": file_path,
                "line": line,
                "column": column,
            },
            "definitions": [],
            "message": "LSP server unavailable, symbol index fallback not yet implemented",
            "method": "fallback",
        }
    )


async def _fallback_references_search(
    repo_name: str, symbol: str, file_path: str, line: int, column: int
) -> str:
    """Fallback references search using symbol index when LSP is unavailable."""
    logger.info(f"Using fallback symbol index search for references of '{symbol}'")

    # This is a simplified fallback - in a real implementation, you might
    # use the symbol storage to find references
    return json.dumps(
        {
            "symbol": symbol,
            "repository": repo_name,
            "query_location": {
                "file_path": file_path,
                "line": line,
                "column": column,
            },
            "references": [],
            "message": "LSP server unavailable, symbol index fallback not yet implemented",
            "method": "fallback",
        }
    )


# Tool execution mapping
TOOL_HANDLERS: dict[str, Callable[..., Awaitable[str]]] = {
    "codebase_health_check": execute_codebase_health_check,
    "search_symbols": execute_search_symbols,
    "find_definition": execute_find_definition,
    "find_references": execute_find_references,
}


async def execute_tool(tool_name: str, **kwargs) -> str:
    """Execute a codebase tool by name

    Args:
        tool_name: Name of the tool to execute
        **kwargs: Tool-specific arguments (including symbol_storage for search_symbols)

    Returns:
        Tool execution result as JSON string
    """
    if tool_name not in TOOL_HANDLERS:
        return json.dumps(
            {
                "error": f"Unknown tool: {tool_name}",
                "available_tools": list(TOOL_HANDLERS.keys()),
            }
        )

    handler = TOOL_HANDLERS[tool_name]
    try:
        return await handler(**kwargs)
    except Exception as e:
        logger.exception(f"Error executing tool {tool_name}")
        return json.dumps({"error": f"Tool execution failed: {e!s}", "tool": tool_name})
