"""
Legacy LSP Client Infrastructure - Deprecated

This module is being phased out in favor of the async_lsp_client module.
It only exports the LSPClientState enum for backward compatibility.
"""

from enum import Enum


class LSPClientState(Enum):
    """States for LSP client operations - kept for backward compatibility."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    INITIALIZING = "initializing"
    INITIALIZED = "initialized"
    SHUTTING_DOWN = "shutting_down"
    ERROR = "error"


# This module is deprecated - use async_lsp_client instead
__all__ = ["LSPClientState"]
