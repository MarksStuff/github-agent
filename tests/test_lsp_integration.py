"""
Simple smoke tests for LSP integration.

These tests verify that the LSP components can be created and wired together
correctly without requiring a full mock server setup.
"""

import tempfile
from typing import Any
from unittest.mock import Mock

from async_lsp_client import AbstractAsyncLSPClient, AsyncLSPClientState
from lsp_server_manager import LSPCommunicationMode, LSPServerManager
from pyright_lsp_manager import PyrightLSPManager


class SimpleLSPClient(AbstractAsyncLSPClient):
    """Minimal LSP client implementation for smoke testing."""

    def __init__(self, server_manager, workspace_root, logger):
        """Initialize simple LSP client."""
        self.server_manager = server_manager
        self.workspace_root = workspace_root
        self.logger = logger
        self._state = AsyncLSPClientState.DISCONNECTED
        self.server_process = None
        self.server_capabilities = {}
        self.communication_mode = server_manager.get_communication_mode()

        # Mock internal state for tests
        self._notification_handlers = {}
        self._stop_event = None

    async def start(self) -> bool:
        """Mock start implementation."""
        self._state = AsyncLSPClientState.INITIALIZED
        return True

    async def stop(self) -> bool:
        """Mock stop implementation."""
        self._state = AsyncLSPClientState.DISCONNECTED
        self.server_process = None
        return True

    def is_initialized(self) -> bool:
        """Check if client is initialized."""
        return self._state == AsyncLSPClientState.INITIALIZED

    def get_server_capabilities(self) -> dict[str, Any]:
        """Get server capabilities."""
        return self.server_capabilities

    def add_notification_handler(self, method: str, handler: Any) -> None:
        """Add a notification handler."""
        self._notification_handlers[method] = handler

    def remove_notification_handler(self, method: str) -> None:
        """Remove a notification handler."""
        self._notification_handlers.pop(method, None)

    # State management methods for tests
    def _set_state_connecting(self) -> None:
        """Mock state transition."""
        self._state = AsyncLSPClientState.CONNECTING

    def _set_state_initialized(self) -> None:
        """Mock state transition."""
        self._state = AsyncLSPClientState.INITIALIZED

    def _set_state_error(self, error: str) -> None:
        """Mock state transition."""
        self._state = AsyncLSPClientState.ERROR

    def _set_state_disconnected(self) -> None:
        """Mock state transition."""
        self._state = AsyncLSPClientState.DISCONNECTED

    async def get_definition(self, uri, line, character):
        return None

    async def get_references(self, uri, line, character, include_declaration=True):
        return None

    async def get_hover(self, uri, line, character):
        return None

    async def get_document_symbols(self, uri):
        return None

    @property
    def state(self) -> AsyncLSPClientState:
        """Get the current client state."""
        return self._state

    @state.setter
    def state(self, value: AsyncLSPClientState) -> None:
        """Set the current client state."""
        self._state = value


class MockServerManager(LSPServerManager):
    """Simple mock server manager for smoke testing."""

    def get_server_command(self):
        return ["echo", "mock-server"]

    def get_server_args(self):
        return []

    def get_communication_mode(self):
        return LSPCommunicationMode.STDIO

    def get_server_capabilities(self):
        return {"textDocumentSync": 2, "definitionProvider": True}

    def get_initialization_options(self):
        return None

    def validate_server_response(self, response):
        return "capabilities" in response

    def validate_configuration(self) -> bool:
        """Mock validate configuration."""
        return True

    def prepare_workspace(self) -> bool:
        """Mock prepare workspace."""
        return True

    def cleanup_workspace(self) -> bool:
        """Mock cleanup workspace."""
        return True


class TestLSPIntegration:
    """Simple smoke tests for LSP integration."""

    def test_lsp_client_creation(self):
        """Test that LSP client can be created with server manager."""
        with tempfile.TemporaryDirectory() as temp_dir:
            server_manager = MockServerManager()
            logger = Mock()

            client = SimpleLSPClient(
                server_manager=server_manager, workspace_root=temp_dir, logger=logger
            )

            assert client.server_manager is server_manager
            assert client.workspace_root == temp_dir
            assert client.logger is logger
            assert client.state == AsyncLSPClientState.DISCONNECTED
            assert not client.is_initialized()

    def test_pyright_manager_creation(self):
        """Test that Pyright LSP manager can be created."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a simple Python file
            python_file = temp_dir + "/test.py"
            with open(python_file, "w") as f:
                f.write("def hello(): pass\n")

            manager = PyrightLSPManager(temp_dir, "/unused/python_path")

            assert manager.workspace_path.name == temp_dir.split("/")[-1]
            assert manager.get_communication_mode() == LSPCommunicationMode.STDIO
            assert "pyright-langserver" in manager.get_server_command()

            # Pyright provides comprehensive LSP capabilities
            capabilities = manager.get_server_capabilities()
            assert isinstance(capabilities, dict)
            # Check for some key capabilities that Pyright should provide
            assert capabilities.get("definitionProvider") is True
            assert capabilities.get("hoverProvider") is True
            assert capabilities.get("referencesProvider") is True

    def test_lsp_client_with_pyright_manager(self):
        """Test that LSP client works with Pyright manager."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a simple Python file
            python_file = temp_dir + "/test.py"
            with open(python_file, "w") as f:
                f.write("def hello(): pass\n")

            server_manager = PyrightLSPManager(temp_dir, "/unused/python_path")
            logger = Mock()

            client = SimpleLSPClient(
                server_manager=server_manager,
                workspace_root=temp_dir,
                logger=logger,
            )

            # Test that components are properly wired
            assert client.server_manager is server_manager
            assert client.workspace_root == temp_dir
            assert client.communication_mode == LSPCommunicationMode.STDIO

            # Test that we can call server manager methods
            command = server_manager.get_server_command()
            assert isinstance(command, list)
            assert len(command) > 0

    def test_server_manager_interface_compliance(self):
        """Test that server managers implement the required interface."""
        server_manager = MockServerManager()

        # Test all required methods exist and return expected types
        assert isinstance(server_manager.get_server_command(), list)
        assert isinstance(server_manager.get_server_args(), list)
        assert isinstance(server_manager.get_communication_mode(), LSPCommunicationMode)
        assert isinstance(server_manager.get_server_capabilities(), dict)

        # get_initialization_options can return None or dict
        init_options = server_manager.get_initialization_options()
        assert init_options is None or isinstance(init_options, dict)

        # validate_server_response should accept a dict and return bool
        assert isinstance(
            server_manager.validate_server_response({"capabilities": {}}), bool
        )

    def test_lsp_client_state_management(self):
        """Test LSP client state management."""
        with tempfile.TemporaryDirectory() as temp_dir:
            server_manager = MockServerManager()
            logger = Mock()

            client = SimpleLSPClient(
                server_manager=server_manager, workspace_root=temp_dir, logger=logger
            )

            # Test initial state
            assert client.state == AsyncLSPClientState.DISCONNECTED
            assert not client.is_initialized()

            # Test state transitions (without actually starting server)
            client._set_state_connecting()
            assert client.state == AsyncLSPClientState.CONNECTING

            client._set_state_initialized()
            assert client.state == AsyncLSPClientState.INITIALIZED
            assert client.is_initialized()

            client._set_state_error("Test error")
            assert client.state == AsyncLSPClientState.ERROR
            assert not client.is_initialized()

            client._set_state_disconnected()
            assert client.state == AsyncLSPClientState.DISCONNECTED
            assert not client.is_initialized()
