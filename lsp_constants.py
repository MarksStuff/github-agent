"""LSP constants and enums."""

from enum import Enum
from typing import Any


class LSPServerType(Enum):
    """Supported LSP server types."""

    PYLSP = "pylsp"
    PYRIGHT = "pyright"


# Default LSP server type
DEFAULT_LSP_SERVER_TYPE = LSPServerType.PYLSP


class LSPErrorCode(Enum):
    """LSP Error Codes as defined in the specification."""

    # JSON-RPC Error Codes
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603

    # LSP-specific Error Codes
    SERVER_NOT_INITIALIZED = -32002
    UNKNOWN_ERROR_CODE = -32001
    REQUEST_FAILED = -32803
    SERVER_CANCELLED = -32802
    CONTENT_MODIFIED = -32801
    REQUEST_CANCELLED = -32800


class LSPMethod:
    """LSP Method Names as constants."""

    # General
    INITIALIZE = "initialize"
    INITIALIZED = "initialized"
    SHUTDOWN = "shutdown"
    EXIT = "exit"
    CANCEL_REQUEST = "$/cancelRequest"
    SET_TRACE = "$/setTrace"

    # Text Document Sync
    DID_OPEN = "textDocument/didOpen"
    DID_CHANGE = "textDocument/didChange"
    DID_CLOSE = "textDocument/didClose"
    DID_SAVE = "textDocument/didSave"
    WILL_SAVE = "textDocument/willSave"
    WILL_SAVE_WAIT_UNTIL = "textDocument/willSaveWaitUntil"

    # Language Features
    DEFINITION = "textDocument/definition"
    REFERENCES = "textDocument/references"
    HOVER = "textDocument/hover"
    COMPLETION = "textDocument/completion"
    COMPLETION_RESOLVE = "completionItem/resolve"
    SIGNATURE_HELP = "textDocument/signatureHelp"
    DOCUMENT_SYMBOLS = "textDocument/documentSymbol"
    CODE_ACTION = "textDocument/codeAction"
    RENAME = "textDocument/rename"
    FORMATTING = "textDocument/formatting"
    RANGE_FORMATTING = "textDocument/rangeFormatting"
    ON_TYPE_FORMATTING = "textDocument/onTypeFormatting"
    PUBLISH_DIAGNOSTICS = "textDocument/publishDiagnostics"

    # Workspace Features
    WORKSPACE_SYMBOLS = "workspace/symbol"
    DID_CHANGE_CONFIGURATION = "workspace/didChangeConfiguration"
    DID_CHANGE_WATCHED_FILES = "workspace/didChangeWatchedFiles"

    # Window Features
    SHOW_MESSAGE = "window/showMessage"
    SHOW_MESSAGE_REQUEST = "window/showMessageRequest"
    LOG_MESSAGE = "window/logMessage"
    PROGRESS = "$/progress"


class LSPCapabilities:
    """LSP Capabilities structure templates."""

    @staticmethod
    def client_capabilities() -> dict[str, Any]:
        """Default client capabilities."""
        return {
            "textDocument": {
                "synchronization": {
                    "dynamicRegistration": True,
                    "willSave": True,
                    "willSaveWaitUntil": True,
                    "didSave": True,
                },
                "completion": {
                    "dynamicRegistration": True,
                    "completionItem": {
                        "snippetSupport": True,
                        "commitCharactersSupport": True,
                        "documentationFormat": ["markdown", "plaintext"],
                    },
                },
                "hover": {
                    "dynamicRegistration": True,
                    "contentFormat": ["markdown", "plaintext"],
                },
                "definition": {"dynamicRegistration": True, "linkSupport": True},
                "references": {"dynamicRegistration": True},
                "documentSymbol": {
                    "dynamicRegistration": True,
                    "symbolKind": {
                        "valueSet": list(range(1, 26))  # All symbol kinds
                    },
                },
                "codeAction": {
                    "dynamicRegistration": True,
                    "codeActionLiteralSupport": {
                        "codeActionKind": {
                            "valueSet": [
                                "quickfix",
                                "refactor",
                                "refactor.extract",
                                "refactor.inline",
                                "refactor.rewrite",
                                "source",
                                "source.organizeImports",
                            ]
                        }
                    },
                },
                "publishDiagnostics": {
                    "relatedInformation": True,
                    "versionSupport": True,
                },
            },
            "workspace": {
                "applyEdit": True,
                "workspaceEdit": {
                    "documentChanges": True,
                    "resourceOperations": ["create", "rename", "delete"],
                    "failureHandling": "textOnlyTransactional",
                },
                "didChangeConfiguration": {"dynamicRegistration": True},
                "didChangeWatchedFiles": {"dynamicRegistration": True},
                "symbol": {
                    "dynamicRegistration": True,
                    "symbolKind": {
                        "valueSet": list(range(1, 26))  # All symbol kinds
                    },
                },
                "configuration": True,
                "workspaceFolders": True,
            },
            "window": {
                "showMessage": {
                    "messageActionItem": {"additionalPropertiesSupport": True}
                },
                "showDocument": {"support": True},
                "workDoneProgress": True,
            },
            "experimental": {},
        }


# JSON-RPC 2.0 Message Types
JsonRPCRequest = dict[str, Any]
JsonRPCResponse = dict[str, Any]
JsonRPCNotification = dict[str, Any]
JsonRPCMessage = JsonRPCRequest | JsonRPCResponse | JsonRPCNotification
