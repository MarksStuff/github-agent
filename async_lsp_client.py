"""
Async-Native LSP Client Implementation

This module provides a clean, async-native LSP client that avoids the threading
complexity that caused timeout issues in the original implementation.

Architecture:
1. Single async event loop (no threading)
2. Async subprocess communication using asyncio streams
3. Direct message processing without cross-thread scheduling
4. Comprehensive logging for debugging
5. Modular design with testable components
"""

import asyncio
import json
import logging
import os
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from lsp_constants import LSPMethod
from lsp_server_manager import LSPServerManager


class AsyncLSPClientState(Enum):
    """States for the async LSP client."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    INITIALIZING = "initializing"
    INITIALIZED = "initialized"
    SHUTTING_DOWN = "shutting_down"
    ERROR = "error"


@dataclass
class LSPMessage:
    """Represents an LSP message with proper typing."""

    content: dict[str, Any]

    @property
    def id(self) -> str | None:
        """Get message ID."""
        return self.content.get("id")

    @property
    def method(self) -> str | None:
        """Get message method."""
        return self.content.get("method")

    @property
    def params(self) -> dict[str, Any] | None:
        """Get message params."""
        return self.content.get("params")

    @property
    def result(self) -> dict[str, Any] | None:
        """Get message result."""
        return self.content.get("result")

    @property
    def error(self) -> dict[str, Any] | None:
        """Get message error."""
        return self.content.get("error")

    @property
    def is_request(self) -> bool:
        """Check if this is a request message."""
        return self.method is not None and self.id is not None

    @property
    def is_response(self) -> bool:
        """Check if this is a response message."""
        return self.id is not None and (
            self.result is not None or self.error is not None
        )

    @property
    def is_notification(self) -> bool:
        """Check if this is a notification message."""
        return self.method is not None and self.id is None

    def asdict(self) -> dict[str, Any]:
        """Convert message to dictionary."""
        return self.content


class LSPProtocol:
    """Handles LSP protocol message serialization/deserialization."""

    def __init__(self, logger: logging.Logger):
        self.logger = logger

    def serialize_message(self, content: dict[str, Any]) -> bytes:
        """Serialize a message to LSP format."""
        json_content = json.dumps(content, separators=(",", ":"))
        message = f"Content-Length: {len(json_content)}\r\n\r\n{json_content}"

        self.logger.debug(
            f"Serializing message: {content.get('method', 'response')} "
            f"(ID: {content.get('id', 'N/A')}) - {len(message)} bytes"
        )

        return message.encode("utf-8")

    def create_request(
        self, method: str, params: Any = None, request_id: str | None = None
    ) -> dict[str, Any]:
        """Create a JSON-RPC request."""
        if request_id is None:
            request_id = str(uuid.uuid4())

        request = {"jsonrpc": "2.0", "id": request_id, "method": method}

        if params is not None:
            request["params"] = params

        self.logger.debug(f"Created request: {method} (ID: {request_id})")
        return request

    def create_notification(self, method: str, params: Any = None) -> dict[str, Any]:
        """Create a JSON-RPC notification."""
        notification = {"jsonrpc": "2.0", "method": method}

        if params is not None:
            notification["params"] = params

        self.logger.debug(f"Created notification: {method}")
        return notification


class AbstractAsyncLSPClient(ABC):
    """Abstract base class for async LSP client implementations."""

    @abstractmethod
    async def start(self) -> bool:
        """Start the LSP client."""
        pass

    @abstractmethod
    async def stop(self) -> bool:
        """Stop the LSP client."""
        pass

    @abstractmethod
    def is_initialized(self) -> bool:
        """Check if the client is initialized."""
        pass

    @abstractmethod
    def get_server_capabilities(self) -> dict[str, Any]:
        """Get server capabilities."""
        pass

    @abstractmethod
    def add_notification_handler(self, method: str, handler: Any) -> None:
        """Add a notification handler."""
        pass

    @abstractmethod
    def remove_notification_handler(self, method: str) -> None:
        """Remove a notification handler."""
        pass

    @abstractmethod
    async def get_definition(
        self, uri: str, line: int, character: int
    ) -> list[dict[str, Any]] | None:
        """Get definition for a symbol."""
        pass

    @abstractmethod
    async def get_references(
        self, uri: str, line: int, character: int, include_declaration: bool = True
    ) -> list[dict[str, Any]] | None:
        """Get references for a symbol."""
        pass

    @abstractmethod
    async def get_hover(
        self, uri: str, line: int, character: int
    ) -> dict[str, Any] | None:
        """Get hover information for a symbol."""
        pass

    @abstractmethod
    async def get_document_symbols(self, uri: str) -> list[dict[str, Any]] | None:
        """Get document symbols."""
        pass

    @property
    @abstractmethod
    def state(self) -> "AsyncLSPClientState":
        """Get the current client state."""
        pass

    @state.setter
    @abstractmethod
    def state(self, value: "AsyncLSPClientState") -> None:
        """Set the current client state."""
        pass


class AsyncLSPClient(AbstractAsyncLSPClient):
    """
    Async-native LSP client implementation.

    This client uses asyncio streams for communication and avoids threading
    to eliminate the timeout issues present in the original implementation.
    """

    @classmethod
    def create(cls, workspace_root: str, python_path: str) -> "AsyncLSPClient":
        """Factory method to create AsyncLSPClient instances."""
        from lsp_server_factory import create_default_python_lsp_manager

        server_manager = create_default_python_lsp_manager(workspace_root, python_path)
        logger = logging.getLogger(f"{__name__}.{Path(workspace_root).name}")
        protocol = LSPProtocol(logger)
        return cls(server_manager, workspace_root, logger, protocol)

    def __init__(
        self,
        server_manager: LSPServerManager,
        workspace_root: str,
        logger: logging.Logger,
        protocol: LSPProtocol,
    ):
        """
        Initialize the async LSP client.

        Args:
            server_manager: LSP server manager for server-specific configuration
            workspace_root: Root directory of the workspace
            logger: Logger instance (required)
            protocol: LSP protocol handler (required)
        """
        # Initialize instance variables
        self.server_manager = server_manager
        self.workspace_root = Path(workspace_root)
        self.logger = logger

        # Server capabilities
        self.server_capabilities: dict[str, Any] = {}

        # Connection state
        self._state = AsyncLSPClientState.DISCONNECTED
        self._server_process: asyncio.subprocess.Process | None = None
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None

        # Protocol handling (override parent's JSONRPCProtocol with LSPProtocol)
        self.protocol = protocol

        # Request/response tracking
        self._pending_requests: dict[str, asyncio.Future] = {}
        self._request_timeout = 30.0

        # Message processing
        self._reader_task: asyncio.Task | None = None
        self._shutdown_event = asyncio.Event()

        # Notification handlers
        self._notification_handlers: dict[str, Any] = {}

        # Statistics for debugging
        self._stats = {
            "messages_sent": 0,
            "messages_received": 0,
            "requests_sent": 0,
            "responses_received": 0,
            "notifications_sent": 0,
            "notifications_received": 0,
            "errors": 0,
        }

        self.logger.info(
            f"🔧 AsyncLSPClient initialized for workspace: {self.workspace_root}"
        )

    async def start(self) -> bool:
        """
        Start the LSP server and establish connection.

        Returns:
            True if connection established successfully, False otherwise
        """
        if self.state != AsyncLSPClientState.DISCONNECTED:
            self.logger.warning(f"Cannot start client in state: {self.state}")
            return False

        self.logger.info("🚀 Starting LSP client...")
        self._set_state(AsyncLSPClientState.CONNECTING)

        try:
            # Start server process
            if not await self._start_server_process():
                return False

            # Establish streams
            if not await self._establish_streams():
                return False

            # Start message reader
            self._start_message_reader()

            # Initialize LSP connection
            if not await self._initialize_lsp():
                return False

            self.logger.info("✅ LSP client started successfully")
            return True

        except Exception as e:
            self.logger.error(f"❌ Failed to start LSP client: {e}")
            self._set_state(AsyncLSPClientState.ERROR)
            await self._cleanup()
            return False

    async def stop(self) -> bool:
        """
        Stop the LSP client and clean up resources.

        Returns:
            True if stopped successfully, False otherwise
        """
        if self.state == AsyncLSPClientState.DISCONNECTED:
            self.logger.debug("Client already disconnected")
            return True

        self.logger.info("🛑 Stopping LSP client...")
        self._set_state(AsyncLSPClientState.SHUTTING_DOWN)

        try:
            # Send shutdown request if connected
            if self.state in [
                AsyncLSPClientState.INITIALIZED,
                AsyncLSPClientState.CONNECTED,
            ]:
                await self._send_shutdown()

            # Signal shutdown and cleanup
            self._shutdown_event.set()
            await self._cleanup()

            self.logger.info("✅ LSP client stopped successfully")
            self._log_stats()
            return True

        except Exception as e:
            self.logger.error(f"❌ Error stopping LSP client: {e}")
            return False

    def _set_state(self, new_state: AsyncLSPClientState) -> None:
        """Set client state with logging."""
        old_state = self._state
        self._state = new_state
        self.logger.info(f"🔄 State change: {old_state.value} → {new_state.value}")

    def _log_stats(self) -> None:
        """Log client statistics for debugging."""
        self.logger.info(f"📊 LSP Client Statistics: {self._stats}")

    async def _start_server_process(self) -> bool:
        """Start the LSP server process."""
        command = self.server_manager.get_server_command()
        args = self.server_manager.get_server_args()
        full_command = command + args

        self.logger.info(f"🖥️  Starting server process: {' '.join(full_command)}")

        try:
            # Start process with pipes for communication
            self._server_process = await asyncio.create_subprocess_exec(
                *full_command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.workspace_root),
            )

            self.logger.info(
                f"✅ Server process started (PID: {self._server_process.pid})"
            )
            return True

        except Exception as e:
            self.logger.error(f"❌ Failed to start server process: {e}")
            return False

    async def _establish_streams(self) -> bool:
        """Establish communication streams with the server."""
        if not self._server_process:
            self.logger.error("❌ No server process to establish streams with")
            return False

        self.logger.info("📡 Establishing communication streams...")

        try:
            self._reader = self._server_process.stdout
            self._writer = self._server_process.stdin

            if not self._reader or not self._writer:
                self.logger.error("❌ Failed to get server streams")
                return False

            self.logger.info("✅ Communication streams established")
            self._set_state(AsyncLSPClientState.CONNECTED)
            return True

        except Exception as e:
            self.logger.error(f"❌ Failed to establish streams: {e}")
            return False

    def _start_message_reader(self) -> None:
        """Start the async message reader task."""
        self.logger.info("📖 Starting message reader task...")
        self._reader_task = asyncio.create_task(self._message_reader_loop())
        self.logger.info("✅ Message reader task started")

    async def _message_reader_loop(self) -> None:
        """Main message reading loop (async, no threading)."""
        self.logger.debug("📚 Message reader loop started")
        buffer = b""

        try:
            while not self._shutdown_event.is_set() and self._reader:
                try:
                    # Read data with timeout
                    data = await asyncio.wait_for(self._reader.read(4096), timeout=0.1)

                    if not data:
                        # EOF - server closed connection
                        if (
                            self._server_process
                            and self._server_process.returncode is not None
                        ):
                            self.logger.warning(
                                f"📪 Server process terminated (exit code: {self._server_process.returncode})"
                            )
                        else:
                            self.logger.warning("📪 Server closed connection")
                        break

                    buffer += data
                    self.logger.debug(
                        f"📨 Read {len(data)} bytes (buffer: {len(buffer)} bytes)"
                    )

                    # Process complete messages
                    while True:
                        message, remaining_buffer = await self._extract_message(buffer)
                        if message is None:
                            break

                        buffer = remaining_buffer
                        await self._process_message(message)

                except TimeoutError:
                    # Normal timeout, continue reading
                    continue
                except Exception as e:
                    if not self._shutdown_event.is_set():
                        self.logger.error(f"❌ Error in message reader loop: {e}")
                        self._stats["errors"] += 1
                    break

        except Exception as e:
            if not self._shutdown_event.is_set():
                self.logger.error(f"❌ Fatal error in message reader loop: {e}")
                self._stats["errors"] += 1

        finally:
            self.logger.debug("📚 Message reader loop ended")

    async def _extract_message(self, buffer: bytes) -> tuple[LSPMessage | None, bytes]:
        """
        Extract a complete LSP message from the buffer.

        Returns:
            Tuple of (message, remaining_buffer) or (None, buffer) if incomplete
        """
        # Look for header separator
        header_end = buffer.find(b"\r\n\r\n")
        if header_end == -1:
            # Incomplete header
            return None, buffer

        # Parse header
        header_data = buffer[:header_end].decode("utf-8")
        content_length = None

        for line in header_data.split("\r\n"):
            if line.startswith("Content-Length:"):
                try:
                    content_length = int(line.split(":", 1)[1].strip())
                    break
                except ValueError as e:
                    self.logger.error(f"❌ Invalid Content-Length header: {line} - {e}")
                    return None, buffer[header_end + 4 :]

        if content_length is None:
            self.logger.error(f"❌ Missing Content-Length header: {header_data}")
            return None, buffer[header_end + 4 :]

        # Check if we have complete message
        content_start = header_end + 4
        content_end = content_start + content_length

        if len(buffer) < content_end:
            # Incomplete message
            self.logger.debug(
                f"📦 Incomplete message: need {content_length} bytes, have {len(buffer) - content_start}"
            )
            return None, buffer

        # Extract and parse message content
        try:
            content_bytes = buffer[content_start:content_end]
            content_str = content_bytes.decode("utf-8")
            content_dict = json.loads(content_str)

            message = LSPMessage(content_dict)
            remaining_buffer = buffer[content_end:]

            self.logger.debug(
                f"📥 Extracted message: {message.method or 'response'} "
                f"(ID: {message.id or 'N/A'}) - {content_length} bytes"
            )

            return message, remaining_buffer

        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            self.logger.error(f"❌ Failed to parse message content: {e}")
            self._stats["errors"] += 1
            return None, buffer[content_end:]

    async def _process_message(self, message: LSPMessage) -> None:
        """Process a received LSP message."""
        self._stats["messages_received"] += 1

        self.logger.debug(
            f"🔍 Processing message: {message.method or 'response'} (ID: {message.id or 'N/A'})"
        )

        try:
            if message.is_response:
                await self._handle_response(message)
            elif message.is_request:
                await self._handle_request(message)
            elif message.is_notification:
                await self._handle_notification(message)
            else:
                self.logger.warning(f"⚠️  Unknown message type: {message.content}")

        except Exception as e:
            self.logger.error(f"❌ Error processing message: {e}")
            self._stats["errors"] += 1

    async def _handle_response(self, message: LSPMessage) -> None:
        """Handle a response message."""
        self._stats["responses_received"] += 1

        request_id = message.id
        if request_id in self._pending_requests:
            future = self._pending_requests.pop(request_id)
            if not future.done():
                future.set_result(message)
                self.logger.debug(f"✅ Response handled for request {request_id}")
            else:
                self.logger.warning(
                    f"⚠️  Response for already completed request {request_id}"
                )
        else:
            self.logger.warning(f"⚠️  No handler for response ID: {request_id}")

    async def _handle_request(self, message: LSPMessage) -> None:
        """Handle a request message from the server."""
        self.logger.debug(f"📥 Server request: {message.method} (ID: {message.id})")

        # Handle common server requests
        if message.method == "workspace/configuration":
            response: dict[str, Any] = {
                "jsonrpc": "2.0",
                "id": message.id,
                "result": {},
            }
            await self._send_message(response)
        else:
            # Unknown request - send error
            error_response: dict[str, Any] = {
                "jsonrpc": "2.0",
                "id": message.id,
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {message.method}",
                },
            }
            await self._send_message(error_response)

    async def _handle_notification(self, message: LSPMessage) -> None:
        """Handle a notification message from the server."""
        self._stats["notifications_received"] += 1
        self.logger.debug(f"📢 Server notification: {message.method}")

        # Handle common notifications
        if message.method == "window/showMessage":
            params = message.params or {}
            msg_text = params.get("message", "")
            self.logger.info(f"💬 Server message: {msg_text}")
        elif message.method == "window/logMessage":
            params = message.params or {}
            msg_text = params.get("message", "")
            self.logger.debug(f"📝 Server log: {msg_text}")

    async def _send_message(self, content: dict[str, Any]) -> None:
        """Send a message to the server."""
        if not self._writer:
            raise RuntimeError("No connection to server")

        try:
            serialized = self.protocol.serialize_message(content)
            self._writer.write(serialized)
            await self._writer.drain()

            self._stats["messages_sent"] += 1

            if "id" in content and "method" in content:
                self._stats["requests_sent"] += 1
            elif "method" in content:
                self._stats["notifications_sent"] += 1

            self.logger.debug(
                f"📤 Sent message: {content.get('method', 'response')} "
                f"(ID: {content.get('id', 'N/A')}) - {len(serialized)} bytes"
            )

        except Exception as e:
            self.logger.error(f"❌ Failed to send message: {e}")
            self._stats["errors"] += 1
            raise

    async def _send_request(
        self, method: str, params: Any = None, timeout: float | None = None
    ) -> LSPMessage:
        """
        Send a request and wait for response.

        Args:
            method: LSP method name
            params: Request parameters
            timeout: Request timeout (uses default if not specified)

        Returns:
            Response message

        Raises:
            asyncio.TimeoutError: If request times out
            RuntimeError: If request fails
        """
        if timeout is None:
            timeout = self._request_timeout

        request = self.protocol.create_request(method, params)
        request_id = request["id"]

        # Create future for response
        response_future: asyncio.Future[LSPMessage] = asyncio.Future()
        self._pending_requests[request_id] = response_future

        try:
            self.logger.debug(f"📤 Sending request: {method} (ID: {request_id})")
            await self._send_message(request)

            # Wait for response
            response = await asyncio.wait_for(response_future, timeout=timeout)

            self.logger.debug(f"📥 Received response for: {method} (ID: {request_id})")

            if response.error:
                error_msg = f"LSP error: {response.error}"
                self.logger.error(f"❌ {error_msg}")
                raise RuntimeError(error_msg)

            return response

        except TimeoutError:
            self._pending_requests.pop(request_id, None)
            error_msg = f"Request timeout: {method} (ID: {request_id}) after {timeout}s"
            self.logger.error(f"⏰ {error_msg}")
            raise TimeoutError(error_msg) from None
        except Exception as e:
            self._pending_requests.pop(request_id, None)
            self.logger.error(f"❌ Request failed: {method} (ID: {request_id}) - {e}")
            raise

    async def _initialize_lsp(self) -> bool:
        """Initialize the LSP connection."""
        self.logger.info("🤝 Initializing LSP connection...")
        self._set_state(AsyncLSPClientState.INITIALIZING)

        try:
            # Create initialize request
            init_params = {
                "processId": os.getpid(),
                "clientInfo": {
                    "name": "async-github-agent-lsp-client",
                    "version": "2.0.0",
                },
                "rootUri": self.workspace_root.as_uri(),
                "workspaceFolders": [
                    {
                        "uri": self.workspace_root.as_uri(),
                        "name": self.workspace_root.name,
                    }
                ],
                "capabilities": {
                    "textDocument": {
                        "definition": {"dynamicRegistration": True},
                        "references": {"dynamicRegistration": True},
                        "hover": {"dynamicRegistration": True},
                        "documentSymbol": {"dynamicRegistration": True},
                    }
                },
            }

            # Add server-specific initialization options
            init_options = self.server_manager.get_initialization_options()
            if init_options:
                init_params["initializationOptions"] = init_options
                self.logger.debug(f"🔧 Using initialization options: {init_options}")

            # Send initialize request
            self.logger.info("📤 Sending initialize request...")
            response = await self._send_request(
                LSPMethod.INITIALIZE, init_params, timeout=15.0
            )

            # Validate response - pass the result part, not the entire message
            result = response.content.get("result", {})
            if not self.server_manager.validate_server_response(result):
                self.logger.error("❌ Server response validation failed")
                return False

            self.logger.info("✅ Initialize request successful")

            # Send initialized notification
            await self._send_message(
                self.protocol.create_notification("initialized", {})
            )
            self.logger.info("📤 Sent initialized notification")

            self._set_state(AsyncLSPClientState.INITIALIZED)
            self.logger.info("🎉 LSP initialization complete!")
            return True

        except Exception as e:
            self.logger.error(f"❌ LSP initialization failed: {e}")
            self._set_state(AsyncLSPClientState.ERROR)
            return False

    async def _send_shutdown(self) -> None:
        """Send shutdown request to server."""
        try:
            self.logger.info("📤 Sending shutdown request...")
            await self._send_request(LSPMethod.SHUTDOWN, timeout=5.0)

            # Send exit notification
            await self._send_message(self.protocol.create_notification("exit"))
            self.logger.info("📤 Sent exit notification")

        except Exception as e:
            self.logger.warning(f"⚠️  Error during shutdown: {e}")

    async def _cleanup(self) -> None:
        """Clean up resources."""
        self.logger.info("🧹 Cleaning up resources...")

        # Cancel reader task
        if self._reader_task and not self._reader_task.done():
            self._reader_task.cancel()
            try:
                await self._reader_task
            except asyncio.CancelledError:
                pass

        # Close streams
        if self._writer:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except Exception as e:
                self.logger.debug(f"Error closing writer: {e}")

        # Terminate server process
        if self._server_process:
            try:
                if self._server_process.returncode is None:
                    self._server_process.terminate()
                    try:
                        await asyncio.wait_for(self._server_process.wait(), timeout=5.0)
                    except TimeoutError:
                        self.logger.warning(
                            "⚠️  Server process didn't terminate, killing..."
                        )
                        self._server_process.kill()
                        await self._server_process.wait()
            except Exception as e:
                self.logger.debug(f"Error terminating server process: {e}")

        # Cancel pending requests
        for _request_id, future in self._pending_requests.items():
            if not future.done():
                future.cancel()
        self._pending_requests.clear()

        # Cleanup workspace
        try:
            self.server_manager.cleanup_workspace()
        except Exception as e:
            self.logger.debug(f"Error cleaning up workspace: {e}")

        self._set_state(AsyncLSPClientState.DISCONNECTED)
        self.logger.info("✅ Cleanup complete")

    # Public interface methods

    def is_initialized(self) -> bool:
        """Check if the client is initialized."""
        return self.state == AsyncLSPClientState.INITIALIZED

    def get_server_capabilities(self) -> dict[str, Any]:
        """Get server capabilities."""
        return self.server_capabilities

    def add_notification_handler(self, method: str, handler: Any) -> None:
        """Add a notification handler."""
        self._notification_handlers[method] = handler

    def remove_notification_handler(self, method: str) -> None:
        """Remove a notification handler."""
        self._notification_handlers.pop(method, None)

    # Public API methods for LSP operations

    async def get_definition(
        self, uri: str, line: int, character: int
    ) -> list[dict[str, Any]] | None:
        """Get definition for a symbol."""
        if self.state != AsyncLSPClientState.INITIALIZED:
            raise RuntimeError(f"Client not initialized (state: {self.state})")

        params = {
            "textDocument": {"uri": uri},
            "position": {"line": line, "character": character},
        }

        try:
            response = await self._send_request("textDocument/definition", params)
            result = response.result
            if result is None:
                return None
            # Ensure we always return a list
            if isinstance(result, list):
                return result
            else:
                return [result]
        except Exception as e:
            self.logger.error(f"❌ Definition request failed: {e}")
            return None

    async def get_references(
        self, uri: str, line: int, character: int, include_declaration: bool = True
    ) -> list[dict[str, Any]] | None:
        """Get references for a symbol."""
        if self.state != AsyncLSPClientState.INITIALIZED:
            raise RuntimeError(f"Client not initialized (state: {self.state})")

        params = {
            "textDocument": {"uri": uri},
            "position": {"line": line, "character": character},
            "context": {"includeDeclaration": include_declaration},
        }

        try:
            response = await self._send_request("textDocument/references", params)
            result = response.result
            if result is None:
                return None
            # Ensure we always return a list
            if isinstance(result, list):
                return result
            else:
                return [result]
        except Exception as e:
            self.logger.error(f"❌ References request failed: {e}")
            return None

    async def get_hover(
        self, uri: str, line: int, character: int
    ) -> dict[str, Any] | None:
        """Get hover information for a symbol."""
        if self.state != AsyncLSPClientState.INITIALIZED:
            raise RuntimeError(f"Client not initialized (state: {self.state})")

        params = {
            "textDocument": {"uri": uri},
            "position": {"line": line, "character": character},
        }

        try:
            response = await self._send_request("textDocument/hover", params)
            return response.result
        except Exception as e:
            self.logger.error(f"❌ Hover request failed: {e}")
            return None

    async def get_document_symbols(self, uri: str) -> list[dict[str, Any]] | None:
        """Get document symbols."""
        if self.state != AsyncLSPClientState.INITIALIZED:
            raise RuntimeError(f"Client not initialized (state: {self.state})")

        params = {"textDocument": {"uri": uri}}

        try:
            response = await self._send_request("textDocument/documentSymbol", params)
            result = response.result
            if result is None:
                return None
            # Ensure we always return a list
            if isinstance(result, list):
                return result
            else:
                return [result]
        except Exception as e:
            self.logger.error(f"❌ Document symbols request failed: {e}")
            return None

    @property
    def state(self) -> AsyncLSPClientState:
        """Get the current client state."""
        return self._state

    @state.setter
    def state(self, value: AsyncLSPClientState) -> None:
        """Set the current client state."""
        self._state = value
