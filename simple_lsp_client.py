#!/usr/bin/env python3

"""
Simple LSP Client - Direct subprocess approach for reliability
No persistent connections, no complex async coordination - just works.
"""

import asyncio
import json
import logging
from typing import Any


class SimpleLSPClient:
    """Simple LSP client using direct subprocess calls."""

    def __init__(self, workspace_root: str, python_path: str):
        """Initialize the simple LSP client.

        Args:
            workspace_root: Path to the workspace/project root
            python_path: Path to the Python interpreter with pylsp
        """
        self.workspace_root = workspace_root
        self.python_path = python_path
        self.logger = logging.getLogger("simple-lsp")

    async def get_definition(
        self, file_uri: str, line: int, character: int, timeout: float = 10.0
    ) -> list[dict[str, Any]]:
        """Get definition for symbol at position.

        Args:
            file_uri: URI of the file (file:///path/to/file.py)
            line: Line number (0-indexed)
            character: Character position (0-indexed)
            timeout: Request timeout in seconds

        Returns:
            List of definition locations
        """
        self.logger.info(f"Getting definition for {file_uri}:{line}:{character}")

        try:
            # Start fresh pylsp process
            proc = await asyncio.create_subprocess_exec(
                self.python_path,
                "-m",
                "pylsp",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.workspace_root,
            )

            self.logger.debug(f"Started pylsp process {proc.pid}")

            # Send initialize request
            init_request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "processId": None,
                    "rootUri": f"file://{self.workspace_root}",
                    "capabilities": {
                        "textDocument": {"definition": {"dynamicRegistration": True}}
                    },
                },
            }

            await self._send_message(proc, init_request)

            # Read initialize response
            response = await asyncio.wait_for(
                self._read_response(proc), timeout=timeout / 2
            )

            if "error" in response:
                raise Exception(f"Initialize failed: {response['error']}")

            # Send initialized notification
            init_notification = {
                "jsonrpc": "2.0",
                "method": "initialized",
                "params": {},
            }

            await self._send_message(proc, init_notification)

            # Send definition request
            def_request = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "textDocument/definition",
                "params": {
                    "textDocument": {"uri": file_uri},
                    "position": {"line": line, "character": character},
                },
            }

            await self._send_message(proc, def_request)

            # Read definition response
            response = await asyncio.wait_for(
                self._read_response(proc), timeout=timeout / 2
            )

            if "error" in response:
                raise Exception(f"Definition request failed: {response['error']}")

            result = response.get("result", [])
            self.logger.info(f"Got {len(result)} definition(s)")

            return result

        except asyncio.TimeoutError:
            self.logger.error(f"Definition request timed out after {timeout}s")
            raise
        except Exception as e:
            self.logger.error(f"Definition request failed: {e}")
            raise
        finally:
            # Enhanced cleanup to prevent MCP worker hanging
            try:
                if "proc" in locals() and proc.returncode is None:
                    self.logger.debug(f"Cleaning up pylsp process {proc.pid}")

                    # Close streams first to prevent deadlocks
                    if proc.stdin and not proc.stdin.is_closing():
                        proc.stdin.close()

                    # Graceful termination first
                    proc.terminate()
                    try:
                        await asyncio.wait_for(proc.wait(), timeout=1.0)
                        self.logger.debug(f"Process {proc.pid} terminated gracefully")
                    except asyncio.TimeoutError:
                        # Force kill if needed
                        self.logger.debug(f"Force killing process {proc.pid}")
                        proc.kill()
                        await proc.wait()

                    self.logger.debug(f"Process {proc.pid} cleanup complete")
            except Exception as cleanup_error:
                self.logger.warning(f"Cleanup error: {cleanup_error}")
                # Don't re-raise cleanup errors

    async def get_references(
        self, file_uri: str, line: int, character: int, timeout: float = 10.0
    ) -> list[dict[str, Any]]:
        """Get references for symbol at position.

        Args:
            file_uri: URI of the file (file:///path/to/file.py)
            line: Line number (0-indexed)
            character: Character position (0-indexed)
            timeout: Request timeout in seconds

        Returns:
            List of reference locations
        """
        self.logger.info(f"Getting references for {file_uri}:{line}:{character}")

        try:
            # Start fresh pylsp process
            proc = await asyncio.create_subprocess_exec(
                self.python_path,
                "-m",
                "pylsp",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.workspace_root,
            )

            # Initialize
            init_request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "processId": None,
                    "rootUri": f"file://{self.workspace_root}",
                    "capabilities": {
                        "textDocument": {"references": {"dynamicRegistration": True}}
                    },
                },
            }

            await self._send_message(proc, init_request)
            await asyncio.wait_for(self._read_response(proc), timeout=timeout / 2)

            # Send initialized notification
            await self._send_message(
                proc, {"jsonrpc": "2.0", "method": "initialized", "params": {}}
            )

            # Send references request
            ref_request = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "textDocument/references",
                "params": {
                    "textDocument": {"uri": file_uri},
                    "position": {"line": line, "character": character},
                    "context": {"includeDeclaration": True},
                },
            }

            await self._send_message(proc, ref_request)
            response = await asyncio.wait_for(
                self._read_response(proc), timeout=timeout / 2
            )

            if "error" in response:
                raise Exception(f"References request failed: {response['error']}")

            result = response.get("result", [])
            self.logger.info(f"Got {len(result)} reference(s)")

            return result

        except asyncio.TimeoutError:
            self.logger.error(f"References request timed out after {timeout}s")
            raise
        except Exception as e:
            self.logger.error(f"References request failed: {e}")
            raise
        finally:
            # Enhanced cleanup to prevent MCP worker hanging
            try:
                if "proc" in locals() and proc.returncode is None:
                    self.logger.debug(f"Cleaning up pylsp process {proc.pid}")

                    # Close streams first to prevent deadlocks
                    if proc.stdin and not proc.stdin.is_closing():
                        proc.stdin.close()

                    # Graceful termination first
                    proc.terminate()
                    try:
                        await asyncio.wait_for(proc.wait(), timeout=1.0)
                        self.logger.debug(f"Process {proc.pid} terminated gracefully")
                    except asyncio.TimeoutError:
                        # Force kill if needed
                        self.logger.debug(f"Force killing process {proc.pid}")
                        proc.kill()
                        await proc.wait()

                    self.logger.debug(f"Process {proc.pid} cleanup complete")
            except Exception as cleanup_error:
                self.logger.warning(f"Cleanup error: {cleanup_error}")
                # Don't re-raise cleanup errors

    async def get_hover(
        self, file_uri: str, line: int, character: int, timeout: float = 10.0
    ) -> dict[str, Any] | None:
        """Get hover information for symbol at position.

        Args:
            file_uri: URI of the file (file:///path/to/file.py)
            line: Line number (0-indexed)
            character: Character position (0-indexed)
            timeout: Request timeout in seconds

        Returns:
            Hover information or None
        """
        self.logger.info(f"Getting hover for {file_uri}:{line}:{character}")

        try:
            # Start fresh pylsp process
            proc = await asyncio.create_subprocess_exec(
                self.python_path,
                "-m",
                "pylsp",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.workspace_root,
            )

            # Initialize
            init_request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "processId": None,
                    "rootUri": f"file://{self.workspace_root}",
                    "capabilities": {
                        "textDocument": {"hover": {"dynamicRegistration": True}}
                    },
                },
            }

            await self._send_message(proc, init_request)
            await asyncio.wait_for(self._read_response(proc), timeout=timeout / 2)

            # Send initialized notification
            await self._send_message(
                proc, {"jsonrpc": "2.0", "method": "initialized", "params": {}}
            )

            # Send hover request
            hover_request = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "textDocument/hover",
                "params": {
                    "textDocument": {"uri": file_uri},
                    "position": {"line": line, "character": character},
                },
            }

            await self._send_message(proc, hover_request)
            response = await asyncio.wait_for(
                self._read_response(proc), timeout=timeout / 2
            )

            if "error" in response:
                raise Exception(f"Hover request failed: {response['error']}")

            result = response.get("result")
            self.logger.info(f"Got hover info: {bool(result)}")

            return result

        except asyncio.TimeoutError:
            self.logger.error(f"Hover request timed out after {timeout}s")
            raise
        except Exception as e:
            self.logger.error(f"Hover request failed: {e}")
            raise
        finally:
            # Enhanced cleanup to prevent MCP worker hanging
            try:
                if "proc" in locals() and proc.returncode is None:
                    self.logger.debug(f"Cleaning up pylsp process {proc.pid}")

                    # Close streams first to prevent deadlocks
                    if proc.stdin and not proc.stdin.is_closing():
                        proc.stdin.close()

                    # Graceful termination first
                    proc.terminate()
                    try:
                        await asyncio.wait_for(proc.wait(), timeout=1.0)
                        self.logger.debug(f"Process {proc.pid} terminated gracefully")
                    except asyncio.TimeoutError:
                        # Force kill if needed
                        self.logger.debug(f"Force killing process {proc.pid}")
                        proc.kill()
                        await proc.wait()

                    self.logger.debug(f"Process {proc.pid} cleanup complete")
            except Exception as cleanup_error:
                self.logger.warning(f"Cleanup error: {cleanup_error}")
                # Don't re-raise cleanup errors

    async def _send_message(
        self, proc: asyncio.subprocess.Process, message: dict[str, Any]
    ) -> None:
        """Send LSP message to process."""
        content = json.dumps(message)
        message_bytes = f"Content-Length: {len(content)}\r\n\r\n{content}".encode()

        proc.stdin.write(message_bytes)
        await proc.stdin.drain()

        self.logger.debug(f"Sent {message.get('method', 'response')} message")

    async def _read_response(self, proc: asyncio.subprocess.Process) -> dict[str, Any]:
        """Read LSP response from process."""
        # Read headers
        headers = {}
        while True:
            line = await proc.stdout.readline()
            if not line:
                raise Exception("Process ended unexpectedly")

            line_str = line.decode().strip()
            if not line_str:  # Empty line indicates end of headers
                break

            if ":" in line_str:
                key, value = line_str.split(":", 1)
                headers[key.strip()] = value.strip()

        # Read content
        content_length = int(headers.get("Content-Length", 0))
        if content_length == 0:
            raise Exception("No Content-Length header")

        content_bytes = await proc.stdout.read(content_length)
        content = content_bytes.decode()

        self.logger.debug(f"Read response: {len(content)} chars")

        return json.loads(content)


# Factory function for easy integration
def create_simple_lsp_client(workspace_root: str, python_path: str) -> SimpleLSPClient:
    """Create a simple LSP client instance.

    Args:
        workspace_root: Path to the workspace/project root
        python_path: Path to the Python interpreter with pylsp

    Returns:
        SimpleLSPClient instance
    """
    return SimpleLSPClient(workspace_root, python_path)
