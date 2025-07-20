"""
Python LSP Server (pylsp) Management

This module implements Python-specific LSP server management using python-lsp-server (pylsp).
It provides lifecycle management, workspace configuration, and Python-specific
capabilities for LSP-based code analysis.
"""

import logging
import subprocess
from pathlib import Path
from typing import Any

from lsp_server_manager import LSPCommunicationMode, LSPServerManager


class PylspManager(LSPServerManager):
    """LSP Server Manager for Python LSP Server (pylsp)."""

    def __init__(self, workspace_path: str, python_path: str):
        """
        Initialize the pylsp Manager.

        Args:
            workspace_path: Path to the Python workspace/project
            python_path: Path to the Python interpreter
        """
        self.workspace_path = Path(workspace_path)
        self.python_path = python_path
        self.logger = logging.getLogger(__name__)

        # Check if pylsp is available
        self.pylsp_version = self._check_pylsp_availability()

    def _check_pylsp_availability(self) -> str:
        """Check if pylsp is available and return version."""
        try:
            result = subprocess.run(
                [self.python_path, "-m", "pylsp", "--version"],
                capture_output=True,
                text=True,
                check=True,
            )
            version = result.stdout.strip()
            self.logger.info(f"pylsp version: {version}")
            return version
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            self.logger.error(f"Failed to check pylsp availability: {e}")
            raise RuntimeError("pylsp is not available") from e

    def get_server_command(self) -> list[str]:
        """Get the command to start the pylsp server."""
        return [self.python_path, "-m", "pylsp"]

    def get_server_args(self) -> list[str]:
        """Get additional arguments for the LSP server."""
        return []  # pylsp uses stdio by default, no additional args needed

    def get_communication_mode(self) -> LSPCommunicationMode:
        """Return the communication mode for pylsp (stdio)."""
        return LSPCommunicationMode.STDIO

    def get_initialization_options(self) -> dict[str, Any] | None:
        """Get pylsp-specific initialization options."""
        # Optimize pylsp for performance by disabling expensive plugins
        return {
            "settings": {
                "pylsp": {
                    "plugins": {
                        # Disable all expensive analysis plugins
                        "autopep8": {"enabled": False},
                        "flake8": {"enabled": False},
                        "mccabe": {"enabled": False},
                        "preload": {"enabled": False},
                        "pycodestyle": {"enabled": False},
                        "pydocstyle": {"enabled": False},
                        "pyflakes": {"enabled": False},
                        "pylint": {"enabled": False},
                        "rope_autoimport": {"enabled": False},
                        "rope_completion": {"enabled": False},
                        "yapf": {"enabled": False},
                        # Enable and optimize essential plugins for definition lookup
                        "jedi_completion": {
                            "enabled": True,
                            "include_params": False,
                            "include_class_objects": False,
                            "fuzzy": False,
                        },
                        "jedi_definition": {
                            "enabled": True,
                            "follow_imports": False,
                            "follow_builtin_imports": False,
                        },
                        "jedi_hover": {"enabled": True},
                        "jedi_references": {"enabled": True},
                        "jedi_symbols": {"enabled": True},
                    }
                }
            }
        }

    def get_server_capabilities(self) -> dict[str, Any]:
        """Return the expected server capabilities for pylsp."""
        return {
            "textDocumentSync": 2,  # Incremental sync
            "hoverProvider": True,
            "completionProvider": {"resolveProvider": True, "triggerCharacters": ["."]},
            "signatureHelpProvider": {"triggerCharacters": ["(", ","]},
            "definitionProvider": True,
            "referencesProvider": True,
            "documentHighlightProvider": True,
            "documentSymbolProvider": True,
            "workspaceSymbolProvider": True,
            "codeActionProvider": True,
            "documentFormattingProvider": True,
            "documentRangeFormattingProvider": True,
            "renameProvider": True,
            "foldingRangeProvider": True,
        }

    def prepare_workspace(self) -> bool:
        """Prepare the workspace for pylsp."""
        # pylsp doesn't require special workspace preparation
        # It works with any Python project
        self.logger.info(f"Workspace prepared for pylsp: {self.workspace_path}")
        return True

    def cleanup_workspace(self) -> bool:
        """Clean up pylsp-specific workspace artifacts."""
        # pylsp doesn't create persistent artifacts that need cleanup
        self.logger.info("Workspace cleanup completed for pylsp")
        return True

    def validate_server_response(self, response: dict[str, Any]) -> bool:
        """Validate server initialization response."""
        # Check for basic LSP response structure
        if not isinstance(response, dict):
            return False

        # Check for server capabilities
        capabilities = response.get("capabilities", {})
        if not isinstance(capabilities, dict):
            return False

        # pylsp should provide at least text document sync and completion
        required_caps = ["textDocumentSync"]
        for cap in required_caps:
            if cap not in capabilities:
                self.logger.warning(f"Missing expected capability: {cap}")

        return True

    def validate_configuration(self) -> bool:
        """Validate the pylsp configuration."""
        # Check if workspace exists and is accessible
        if not self.workspace_path.exists():
            self.logger.error(f"Workspace path does not exist: {self.workspace_path}")
            return False

        if not self.workspace_path.is_dir():
            self.logger.error(
                f"Workspace path is not a directory: {self.workspace_path}"
            )
            return False

        # Check if Python interpreter is accessible
        try:
            result = subprocess.run(
                [self.python_path, "--version"],
                capture_output=True,
                text=True,
                check=True,
            )
            self.logger.debug(f"Python interpreter version: {result.stdout.strip()}")
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            self.logger.error(f"Python interpreter not accessible: {e}")
            return False

        return True
