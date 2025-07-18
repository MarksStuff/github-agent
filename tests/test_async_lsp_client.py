#!/usr/bin/env python3
"""
Comprehensive unit tests for AsyncLSPClient.

Tests each component incrementally to ensure proper functionality.
"""

import asyncio
import json
import logging
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from async_lsp_client import (
    AsyncLSPClient,
    AsyncLSPClientState,
    LSPMessage,
    LSPProtocol,
)
from lsp_server_manager import LSPServerManager


class MockLSPServerManager(LSPServerManager):
    """Mock LSP server manager for testing."""

    def __init__(self, workspace_path: str = "/tmp", python_path: str = "python"):
        self.workspace_path = workspace_path
        self.python_path = python_path

    def get_server_command(self) -> list[str]:
        return ["echo", "mock-lsp-server"]

    def get_server_args(self) -> list[str]:
        return []

    def get_communication_mode(self):
        from lsp_server_manager import LSPCommunicationMode

        return LSPCommunicationMode.STDIO

    def get_server_capabilities(self) -> dict:
        return {"textDocumentSync": 1}

    def get_initialization_options(self) -> dict | None:
        return {"test": True}

    def validate_server_response(self, response: dict) -> bool:
        return True

    def prepare_workspace(self) -> bool:
        return True

    def cleanup_workspace(self) -> bool:
        return True

    def validate_configuration(self) -> bool:
        return True


class TestLSPMessage(unittest.TestCase):
    """Test LSPMessage class."""

    def test_request_message(self):
        """Test request message identification."""
        content = {
            "jsonrpc": "2.0",
            "id": "123",
            "method": "textDocument/definition",
            "params": {},
        }

        message = LSPMessage(content)

        self.assertTrue(message.is_request)
        self.assertFalse(message.is_response)
        self.assertFalse(message.is_notification)
        self.assertEqual(message.id, "123")
        self.assertEqual(message.method, "textDocument/definition")

    def test_response_message(self):
        """Test response message identification."""
        content = {
            "jsonrpc": "2.0",
            "id": "123",
            "result": {"uri": "file:///test.py", "range": {}},
        }

        message = LSPMessage(content)

        self.assertFalse(message.is_request)
        self.assertTrue(message.is_response)
        self.assertFalse(message.is_notification)
        self.assertEqual(message.id, "123")
        self.assertIsNone(message.method)

    def test_error_response_message(self):
        """Test error response message identification."""
        content = {
            "jsonrpc": "2.0",
            "id": "123",
            "error": {"code": -32602, "message": "Invalid params"},
        }

        message = LSPMessage(content)

        self.assertFalse(message.is_request)
        self.assertTrue(message.is_response)
        self.assertFalse(message.is_notification)
        self.assertEqual(message.id, "123")
        self.assertIsNotNone(message.error)

    def test_notification_message(self):
        """Test notification message identification."""
        content = {
            "jsonrpc": "2.0",
            "method": "textDocument/didOpen",
            "params": {"textDocument": {}},
        }

        message = LSPMessage(content)

        self.assertFalse(message.is_request)
        self.assertFalse(message.is_response)
        self.assertTrue(message.is_notification)
        self.assertIsNone(message.id)
        self.assertEqual(message.method, "textDocument/didOpen")


class TestLSPProtocol(unittest.TestCase):
    """Test LSPProtocol class."""

    def setUp(self):
        self.logger = logging.getLogger("test")
        self.protocol = LSPProtocol(self.logger)

    def test_serialize_message(self):
        """Test message serialization."""
        content = {
            "jsonrpc": "2.0",
            "id": "test-123",
            "method": "initialize",
            "params": {"test": True},
        }

        serialized = self.protocol.serialize_message(content)

        # Check it's bytes
        self.assertIsInstance(serialized, bytes)

        # Check LSP format
        decoded = serialized.decode("utf-8")
        lines = decoded.split("\r\n")

        # Should have Content-Length header
        self.assertTrue(lines[0].startswith("Content-Length:"))

        # Should have empty line separator
        self.assertEqual(lines[1], "")

        # Should have valid JSON content
        json_content = "\r\n".join(lines[2:])
        parsed = json.loads(json_content)
        self.assertEqual(parsed, content)

    def test_create_request(self):
        """Test request creation."""
        request = self.protocol.create_request(
            "textDocument/definition", {"test": True}
        )

        self.assertEqual(request["jsonrpc"], "2.0")
        self.assertEqual(request["method"], "textDocument/definition")
        self.assertEqual(request["params"], {"test": True})
        self.assertIn("id", request)
        self.assertIsInstance(request["id"], str)

    def test_create_request_with_custom_id(self):
        """Test request creation with custom ID."""
        request = self.protocol.create_request("test", None, "custom-id")

        self.assertEqual(request["id"], "custom-id")
        self.assertEqual(request["method"], "test")
        self.assertNotIn("params", request)  # None params should be omitted

    def test_create_notification(self):
        """Test notification creation."""
        notification = self.protocol.create_notification("initialized", {})

        self.assertEqual(notification["jsonrpc"], "2.0")
        self.assertEqual(notification["method"], "initialized")
        self.assertEqual(notification["params"], {})
        self.assertNotIn("id", notification)

    def test_create_notification_no_params(self):
        """Test notification creation without params."""
        notification = self.protocol.create_notification("exit")

        self.assertEqual(notification["method"], "exit")
        self.assertNotIn("params", notification)


class TestAsyncLSPClientBasics(unittest.IsolatedAsyncioTestCase):
    """Test basic AsyncLSPClient functionality."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.workspace = Path(self.temp_dir)
        self.server_manager = MockLSPServerManager(str(self.workspace))
        self.logger = logging.getLogger("test")
        self.client = AsyncLSPClient(
            self.server_manager, str(self.workspace), self.logger
        )

    def tearDown(self):
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_initialization(self):
        """Test client initialization."""
        self.assertEqual(self.client.state, AsyncLSPClientState.DISCONNECTED)
        self.assertEqual(self.client.workspace_root, self.workspace)
        self.assertIsNotNone(self.client.protocol)
        self.assertEqual(self.client._stats["messages_sent"], 0)

    def test_state_changes(self):
        """Test state change logging."""
        with self.assertLogs(self.logger, level="INFO") as cm:
            self.client._set_state(AsyncLSPClientState.CONNECTING)

        self.assertEqual(self.client.state, AsyncLSPClientState.CONNECTING)
        self.assertIn("State change", cm.output[0])

    def test_message_extraction_incomplete(self):
        """Test message extraction with incomplete data."""
        # Incomplete header
        buffer = b"Content-Length: 50\r\n"

        result = asyncio.run(self.client._extract_message(buffer))
        message, remaining = result

        self.assertIsNone(message)
        self.assertEqual(remaining, buffer)

    def test_message_extraction_complete(self):
        """Test message extraction with complete message."""
        content = {"jsonrpc": "2.0", "method": "test"}
        json_str = json.dumps(content)
        buffer = f"Content-Length: {len(json_str)}\r\n\r\n{json_str}".encode()

        result = asyncio.run(self.client._extract_message(buffer))
        message, remaining = result

        self.assertIsNotNone(message)
        assert message is not None  # Help mypy with type narrowing
        self.assertEqual(message.method, "test")
        self.assertEqual(remaining, b"")

    def test_message_extraction_with_remaining(self):
        """Test message extraction with remaining data."""
        content1 = {"jsonrpc": "2.0", "method": "test1"}
        content2 = {"jsonrpc": "2.0", "method": "test2"}

        json1 = json.dumps(content1)
        json2 = json.dumps(content2)

        buffer = (
            f"Content-Length: {len(json1)}\r\n\r\n{json1}"
            f"Content-Length: {len(json2)}\r\n\r\n{json2}"
        ).encode()

        result = asyncio.run(self.client._extract_message(buffer))
        message, remaining = result

        self.assertIsNotNone(message)
        assert message is not None  # Help mypy with type narrowing
        self.assertEqual(message.method, "test1")

        # Remaining should contain second message
        self.assertTrue(remaining.startswith(b"Content-Length:"))

    def test_invalid_content_length(self):
        """Test handling of invalid Content-Length."""
        buffer = b"Content-Length: invalid\r\n\r\n{}"

        with self.assertLogs(self.client.logger, level="ERROR"):
            result = asyncio.run(self.client._extract_message(buffer))
            message, remaining = result

        self.assertIsNone(message)
        self.assertEqual(remaining, b"{}")  # Should skip past header

    def test_missing_content_length(self):
        """Test handling of missing Content-Length."""
        buffer = b"Content-Type: application/json\r\n\r\n{}"

        with self.assertLogs(self.client.logger, level="ERROR"):
            result = asyncio.run(self.client._extract_message(buffer))
            message, remaining = result

        self.assertIsNone(message)
        self.assertEqual(remaining, b"{}")

    async def test_send_message_no_connection(self):
        """Test sending message without connection."""
        with self.assertRaises(RuntimeError):
            await self.client._send_message({"test": True})

    async def test_lsp_operations_not_initialized(self):
        """Test LSP operations when not initialized."""
        with self.assertRaises(RuntimeError):
            await self.client.get_definition("file:///test.py", 0, 0)

        with self.assertRaises(RuntimeError):
            await self.client.get_references("file:///test.py", 0, 0)

        with self.assertRaises(RuntimeError):
            await self.client.get_hover("file:///test.py", 0, 0)

        with self.assertRaises(RuntimeError):
            await self.client.get_document_symbols("file:///test.py")


class TestAsyncLSPClientMessageHandling(unittest.IsolatedAsyncioTestCase):
    """Test AsyncLSPClient message handling."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.workspace = Path(self.temp_dir)
        self.server_manager = MockLSPServerManager(str(self.workspace))
        self.logger = logging.getLogger("test")
        self.client = AsyncLSPClient(
            self.server_manager, str(self.workspace), self.logger
        )

    def tearDown(self):
        import shutil

        shutil.rmtree(self.temp_dir)

    async def test_handle_response(self):
        """Test response handling."""
        # Set up pending request
        request_id = "test-123"
        future: asyncio.Future[LSPMessage] = asyncio.Future()
        self.client._pending_requests[request_id] = future

        # Create response message
        response_content = {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {"test": "success"},
        }
        response_message = LSPMessage(response_content)

        # Handle response
        await self.client._handle_response(response_message)

        # Check future was resolved
        self.assertTrue(future.done())
        result = future.result()
        self.assertEqual(result.content, response_content)
        self.assertEqual(self.client._stats["responses_received"], 1)

    async def test_handle_response_no_pending(self):
        """Test response handling with no pending request."""
        response_content = {
            "jsonrpc": "2.0",
            "id": "unknown-123",
            "result": {"test": "success"},
        }
        response_message = LSPMessage(response_content)

        with self.assertLogs(self.client.logger, level="WARNING"):
            await self.client._handle_response(response_message)

    async def test_handle_request_workspace_configuration(self):
        """Test handling workspace/configuration request."""
        # Mock _send_message
        with patch.object(
            self.client, "_send_message", new_callable=AsyncMock
        ) as mock_send:
            request_content = {
                "jsonrpc": "2.0",
                "id": "config-123",
                "method": "workspace/configuration",
                "params": {},
            }
            request_message = LSPMessage(request_content)

            await self.client._handle_request(request_message)

            # Should send response
            mock_send.assert_called_once()
            sent_response = mock_send.call_args[0][0]
            self.assertEqual(sent_response["id"], "config-123")
            self.assertEqual(sent_response["result"], {})

    async def test_handle_request_unknown_method(self):
        """Test handling unknown request method."""
        # Mock _send_message
        with patch.object(
            self.client, "_send_message", new_callable=AsyncMock
        ) as mock_send:
            request_content = {
                "jsonrpc": "2.0",
                "id": "unknown-123",
                "method": "unknown/method",
                "params": {},
            }
            request_message = LSPMessage(request_content)

            await self.client._handle_request(request_message)

            # Should send error response
            mock_send.assert_called_once()
            sent_response = mock_send.call_args[0][0]
            self.assertEqual(sent_response["id"], "unknown-123")
            self.assertIn("error", sent_response)
            self.assertEqual(sent_response["error"]["code"], -32601)

    async def test_handle_notification_show_message(self):
        """Test handling window/showMessage notification."""
        notification_content = {
            "jsonrpc": "2.0",
            "method": "window/showMessage",
            "params": {"message": "Test message", "type": 1},
        }
        notification_message = LSPMessage(notification_content)

        with self.assertLogs(self.client.logger, level="INFO") as cm:
            await self.client._handle_notification(notification_message)

        self.assertIn("Test message", cm.output[-1])
        self.assertEqual(self.client._stats["notifications_received"], 1)

    async def test_handle_notification_log_message(self):
        """Test handling window/logMessage notification."""
        notification_content = {
            "jsonrpc": "2.0",
            "method": "window/logMessage",
            "params": {"message": "Debug info", "type": 4},
        }
        notification_message = LSPMessage(notification_content)

        with self.assertLogs(self.client.logger, level="DEBUG") as cm:
            await self.client._handle_notification(notification_message)

        self.assertIn("Debug info", cm.output[-1])


class TestAsyncLSPClientIntegration(unittest.IsolatedAsyncioTestCase):
    """Integration tests for AsyncLSPClient with mock server."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.workspace = Path(self.temp_dir)
        self.server_manager = MockLSPServerManager(str(self.workspace))
        self.logger = logging.getLogger("test")

    def tearDown(self):
        import shutil

        shutil.rmtree(self.temp_dir)

    @patch("asyncio.create_subprocess_exec")
    async def test_start_server_process_success(self, mock_subprocess):
        """Test successful server process start."""
        # Mock subprocess
        mock_process = AsyncMock()
        mock_process.pid = 12345
        mock_subprocess.return_value = mock_process

        client = AsyncLSPClient(self.server_manager, str(self.workspace), self.logger)

        result = await client._start_server_process()

        self.assertTrue(result)
        self.assertEqual(client._server_process, mock_process)
        mock_subprocess.assert_called_once()

    @patch("asyncio.create_subprocess_exec")
    async def test_start_server_process_failure(self, mock_subprocess):
        """Test server process start failure."""
        mock_subprocess.side_effect = OSError("Command not found")

        client = AsyncLSPClient(self.server_manager, str(self.workspace), self.logger)

        with self.assertLogs(client.logger, level="ERROR"):
            result = await client._start_server_process()

        self.assertFalse(result)
        self.assertIsNone(client._server_process)

    async def test_establish_streams_no_process(self):
        """Test establishing streams without server process."""
        client = AsyncLSPClient(self.server_manager, str(self.workspace), self.logger)

        with self.assertLogs(client.logger, level="ERROR"):
            result = await client._establish_streams()

        self.assertFalse(result)

    async def test_establish_streams_success(self):
        """Test successful stream establishment."""
        # Mock process with streams
        mock_process = MagicMock()
        mock_process.stdout = MagicMock()
        mock_process.stdin = MagicMock()

        client = AsyncLSPClient(self.server_manager, str(self.workspace), self.logger)
        client._server_process = mock_process

        result = await client._establish_streams()

        self.assertTrue(result)
        self.assertEqual(client._reader, mock_process.stdout)
        self.assertEqual(client._writer, mock_process.stdin)
        self.assertEqual(client.state, AsyncLSPClientState.CONNECTED)

    async def test_send_request_timeout(self):
        """Test request timeout handling."""
        client = AsyncLSPClient(self.server_manager, str(self.workspace), self.logger)
        client._writer = AsyncMock()

        with self.assertRaises(asyncio.TimeoutError):
            await client._send_request("test/method", timeout=0.1)

    async def test_send_request_with_error_response(self):
        """Test request with error response."""
        client = AsyncLSPClient(self.server_manager, str(self.workspace), self.logger)
        client._writer = AsyncMock()

        # Create error response
        error_response = LSPMessage(
            {
                "jsonrpc": "2.0",
                "id": "test-id",
                "error": {"code": -32602, "message": "Invalid params"},
            }
        )

        # Mock the request to immediately return error
        async def mock_send_message(content):
            request_id = content["id"]
            if request_id in client._pending_requests:
                future = client._pending_requests[request_id]
                future.set_result(error_response)

        with patch.object(client, "_send_message", side_effect=mock_send_message):
            with self.assertRaises(RuntimeError) as cm:
                await client._send_request("test/method")

            self.assertIn("Invalid params", str(cm.exception))


if __name__ == "__main__":
    # Configure logging for tests
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    unittest.main()
