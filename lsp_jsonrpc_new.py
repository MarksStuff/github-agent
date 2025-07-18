"""
JSON-RPC 2.0 Protocol Implementation for LSP

This module uses python-lsp-jsonrpc correctly with plain dictionaries,
avoiding custom wrapper classes that cause bugs.
"""

import io
import logging
import uuid
from typing import Any

from pylsp_jsonrpc.streams import JsonRpcStreamReader, JsonRpcStreamWriter

from lsp_constants import LSPErrorCode


class JSONRPCError(Exception):
    """Exception for JSON-RPC protocol errors."""

    def __init__(self, code: LSPErrorCode, message: str, data: Any | None = None):
        self.code = code
        self.message = message
        self.data = data
        super().__init__(f"JSON-RPC Error {code.value}: {message}")


class JSONRPCProtocol:
    """
    Simplified JSON-RPC protocol using python-lsp-jsonrpc correctly.
    
    Uses plain dictionaries instead of custom wrapper objects.
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Use python-lsp-jsonrpc streams directly
        self._stream_buffer = io.BytesIO()
        self._stream_writer = JsonRpcStreamWriter(self._stream_buffer)
        
        # Track pending requests (for completeness, though LSP client manages this)
        self._pending_requests: dict[str | int, dict[str, Any]] = {}

    def create_request(
        self, method: str, params: dict[str, Any] | None = None, request_id: str | int | None = None
    ) -> dict[str, Any]:
        """Create a JSON-RPC request as a plain dictionary."""
        if request_id is None:
            request_id = str(uuid.uuid4())
            
        request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
        }
        
        if params is not None:
            request["params"] = params
            
        # Track the request
        self._pending_requests[request_id] = request
        
        return request

    def create_notification(
        self, method: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Create a JSON-RPC notification as a plain dictionary."""
        notification = {
            "jsonrpc": "2.0",
            "method": method,
        }
        
        if params is not None:
            notification["params"] = params
            
        return notification

    def create_response(self, message_id: str | int, result: Any) -> dict[str, Any]:
        """Create a successful JSON-RPC response as a plain dictionary."""
        # Remove from pending requests
        self._pending_requests.pop(message_id, None)
        
        return {
            "jsonrpc": "2.0",
            "id": message_id,
            "result": result,
        }

    def create_error_response(
        self,
        message_id: str | int,
        code: LSPErrorCode,
        message: str,
        data: Any | None = None,
    ) -> dict[str, Any]:
        """Create an error JSON-RPC response as a plain dictionary."""
        # Remove from pending requests
        self._pending_requests.pop(message_id, None)
        
        error = {
            "code": code.value,
            "message": message,
        }
        
        if data is not None:
            error["data"] = data
            
        return {
            "jsonrpc": "2.0",
            "id": message_id,
            "error": error,
        }

    def serialize_message(self, message: dict[str, Any]) -> bytes:
        """
        Serialize a JSON-RPC message using python-lsp-jsonrpc.
        
        Args:
            message: Plain dictionary representing the JSON-RPC message
            
        Returns:
            Serialized message as bytes
        """
        # Reset the buffer
        self._stream_buffer.seek(0)
        self._stream_buffer.truncate()
        
        # Use python-lsp-jsonrpc to serialize
        self._stream_writer.write(message)
        
        # Read the serialized data
        self._stream_buffer.seek(0)
        return self._stream_buffer.read()

    def parse_lsp_message(self, raw_data: bytes) -> tuple[dict[str, str], str]:
        """
        Parse LSP message using python-lsp-jsonrpc.
        
        Returns:
            Tuple of (headers, content)
        """
        # Split headers and content manually for now
        # python-lsp-jsonrpc handles this internally, but we need the split
        try:
            # Find the header/content separator
            separator = b"\\r\\n\\r\\n"
            if separator not in raw_data:
                raise ValueError("Invalid LSP message format: no header separator found")
            
            headers_data, content = raw_data.split(separator, 1)
            
            # Parse headers
            headers = {}
            for line in headers_data.decode('utf-8').split('\\r\\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    headers[key.strip()] = value.strip()
            
            return headers, content.decode('utf-8')
            
        except Exception as e:
            raise ValueError(f"Failed to parse LSP message: {e}") from e

    def parse_json_rpc_message(self, content: str) -> dict[str, Any]:
        """
        Parse JSON-RPC message content.
        
        Args:
            content: JSON string content
            
        Returns:
            Parsed message as dictionary
        """
        try:
            message = json.loads(content)
            
            # Basic validation
            if not isinstance(message, dict):
                raise ValueError("Message must be a JSON object")
                
            if message.get("jsonrpc") != "2.0":
                raise ValueError("Invalid JSON-RPC version")
                
            return message
            
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in message: {e}") from e

    def is_request(self, message: dict[str, Any]) -> bool:
        """Check if message is a request."""
        return "method" in message and "id" in message

    def is_notification(self, message: dict[str, Any]) -> bool:
        """Check if message is a notification."""
        return "method" in message and "id" not in message

    def is_response(self, message: dict[str, Any]) -> bool:
        """Check if message is a response."""
        return "id" in message and "method" not in message

    def get_message_id(self, message: dict[str, Any]) -> str | int | None:
        """Get the ID from a message."""
        return message.get("id")

    def get_message_method(self, message: dict[str, Any]) -> str | None:
        """Get the method from a message."""
        return message.get("method")

    def get_message_params(self, message: dict[str, Any]) -> dict[str, Any] | list[Any] | None:
        """Get the params from a message."""
        return message.get("params")

    def get_message_result(self, message: dict[str, Any]) -> Any:
        """Get the result from a response message."""
        return message.get("result")

    def get_message_error(self, message: dict[str, Any]) -> dict[str, Any] | None:
        """Get the error from a response message."""
        return message.get("error")
