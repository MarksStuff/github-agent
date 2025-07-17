"""
AsyncCodebaseLSPClient - Integration with existing codebase tools.

This module provides an adapter that implements the AbstractLSPClient interface
using our new AsyncLSPClient for seamless integration with the existing system.
"""

import asyncio
import json
import logging
from typing import Any

from async_lsp_client import AsyncLSPClient
from lsp_client import AbstractLSPClient, LSPClientState
from lsp_server_factory import LSPServerFactory, create_default_python_lsp_manager


class AsyncCodebaseLSPClient(AbstractLSPClient):
    """
    Adapter class that implements AbstractLSPClient using AsyncLSPClient.

    This allows seamless integration with the existing codebase tools while
    using the new async-native implementation that solves the timeout issues.
    """

    def __init__(
        self, workspace_root: str, python_path: str, server_type: str | None = None
    ):
        """
        Initialize the async codebase LSP client.

        Args:
            workspace_root: Path to the workspace root
            python_path: Path to the Python interpreter
            server_type: LSP server type to use (defaults to pylsp)
        """
        self.workspace_root = workspace_root
        self.python_path = python_path
        self.logger = logging.getLogger(f"{__name__}.{workspace_root.split('/')[-1]}")

        # Create server manager
        if server_type:
            self.server_manager = LSPServerFactory.create_server_manager(
                server_type, workspace_root, python_path
            )
        else:
            self.server_manager = create_default_python_lsp_manager(
                workspace_root, python_path
            )

        # Create async client
        self._async_client = AsyncLSPClient(
            self.server_manager, workspace_root, self.logger
        )

        self.logger.info(
            f"🔧 AsyncCodebaseLSPClient initialized with {server_type or 'default'} server"
        )

    @property
    def state(self) -> LSPClientState:
        """Get the current LSP client state."""
        # Map AsyncLSPClientState to LSPClientState
        from async_lsp_client import AsyncLSPClientState

        state_mapping = {
            AsyncLSPClientState.DISCONNECTED: LSPClientState.DISCONNECTED,
            AsyncLSPClientState.CONNECTING: LSPClientState.CONNECTING,
            AsyncLSPClientState.CONNECTED: LSPClientState.CONNECTING,  # Map to CONNECTING since no CONNECTED state
            AsyncLSPClientState.INITIALIZING: LSPClientState.INITIALIZING,
            AsyncLSPClientState.INITIALIZED: LSPClientState.INITIALIZED,
            AsyncLSPClientState.SHUTTING_DOWN: LSPClientState.SHUTTING_DOWN,
            AsyncLSPClientState.ERROR: LSPClientState.ERROR,
        }

        return state_mapping.get(self._async_client.state, LSPClientState.DISCONNECTED)

    async def start(self) -> bool:
        """Start the LSP client."""
        self.logger.info("🚀 Starting AsyncCodebaseLSPClient...")

        start_time = asyncio.get_event_loop().time()
        success = await self._async_client.start()
        elapsed = asyncio.get_event_loop().time() - start_time

        if success:
            self.logger.info(
                f"✅ AsyncCodebaseLSPClient started successfully in {elapsed:.2f}s"
            )
        else:
            self.logger.error(
                f"❌ AsyncCodebaseLSPClient failed to start after {elapsed:.2f}s"
            )

        return success

    async def stop(self) -> bool:
        """Stop the LSP client."""
        self.logger.info("🛑 Stopping AsyncCodebaseLSPClient...")

        success = await self._async_client.stop()

        if success:
            self.logger.info("✅ AsyncCodebaseLSPClient stopped successfully")
        else:
            self.logger.error("❌ AsyncCodebaseLSPClient failed to stop cleanly")

        return success

    async def get_definition(
        self, uri: str, line: int, character: int
    ) -> list[dict[str, Any]] | None:
        """Get definition for a symbol using LSP."""
        self.logger.debug(f"🔍 Getting definition for {uri}:{line}:{character}")

        try:
            result = await self._async_client.get_definition(uri, line, character)

            if result:
                self.logger.debug(f"📍 Found {len(result)} definition(s)")
            else:
                self.logger.debug("📍 No definitions found")

            return result

        except Exception as e:
            self.logger.error(f"❌ Definition lookup failed: {e}")
            return None

    async def get_references(
        self, uri: str, line: int, character: int, include_declaration: bool = True
    ) -> list[dict[str, Any]] | None:
        """Get references for a symbol using LSP."""
        self.logger.debug(f"🔍 Getting references for {uri}:{line}:{character}")

        try:
            result = await self._async_client.get_references(
                uri, line, character, include_declaration
            )

            if result:
                self.logger.debug(f"📎 Found {len(result)} reference(s)")
            else:
                self.logger.debug("📎 No references found")

            return result

        except Exception as e:
            self.logger.error(f"❌ References lookup failed: {e}")
            return None

    async def get_hover(
        self, uri: str, line: int, character: int
    ) -> dict[str, Any] | None:
        """Get hover information for a symbol using LSP."""
        self.logger.debug(f"🔍 Getting hover for {uri}:{line}:{character}")

        try:
            result = await self._async_client.get_hover(uri, line, character)

            if result:
                self.logger.debug("💬 Hover information retrieved")
            else:
                self.logger.debug("💬 No hover information available")

            return result

        except Exception as e:
            self.logger.error(f"❌ Hover lookup failed: {e}")
            return None

    async def get_document_symbols(self, uri: str) -> list[dict[str, Any]] | None:
        """Get document symbols using LSP."""
        self.logger.debug(f"🔍 Getting document symbols for {uri}")

        try:
            result = await self._async_client.get_document_symbols(uri)

            if result:
                self.logger.debug(f"📄 Found {len(result)} symbol(s)")
            else:
                self.logger.debug("📄 No symbols found")

            return result

        except Exception as e:
            self.logger.error(f"❌ Document symbols lookup failed: {e}")
            return None

    # Additional helper methods for integration

    async def find_definition(
        self, file_path: str, symbol: str, line: int, column: int
    ) -> str | None:
        """
        Find definition for a symbol and return JSON result.

        This method provides compatibility with the existing codebase tools API.
        """
        try:
            from pathlib import Path

            file_uri = Path(file_path).as_uri()

            definitions = await self.get_definition(
                file_uri, line - 1, column
            )  # LSP uses 0-based indexing

            if definitions:
                # Convert to expected format
                result = {
                    "definitions": definitions,
                    "symbol": symbol,
                    "file": file_path,
                    "line": line,
                    "column": column,
                }
                return json.dumps(result, indent=2)
            else:
                return json.dumps({"definitions": [], "symbol": symbol})

        except Exception as e:
            self.logger.error(f"❌ find_definition failed: {e}")
            return json.dumps({"error": str(e), "symbol": symbol})

    async def find_references(
        self, file_path: str, symbol: str, line: int, column: int
    ) -> str | None:
        """
        Find references for a symbol and return JSON result.

        This method provides compatibility with the existing codebase tools API.
        """
        try:
            from pathlib import Path

            file_uri = Path(file_path).as_uri()

            references = await self.get_references(
                file_uri, line - 1, column
            )  # LSP uses 0-based indexing

            if references:
                # Convert to expected format
                result = {
                    "references": references,
                    "symbol": symbol,
                    "file": file_path,
                    "line": line,
                    "column": column,
                }
                return json.dumps(result, indent=2)
            else:
                return json.dumps({"references": [], "symbol": symbol})

        except Exception as e:
            self.logger.error(f"❌ find_references failed: {e}")
            return json.dumps({"error": str(e), "symbol": symbol})

    def get_stats(self) -> dict[str, Any]:
        """Get client statistics for debugging."""
        return {
            "state": self.state.value,
            "server_type": type(self.server_manager).__name__,
            "workspace": self.workspace_root,
            "async_stats": getattr(self._async_client, "_stats", {}),
        }
