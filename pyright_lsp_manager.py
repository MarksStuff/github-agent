"""
Pyright LSP Server Management

This module implements Python-specific LSP server management using pyright.
It provides lifecycle management, workspace configuration, and Python-specific
capabilities for LSP-based code analysis.
"""

import json
import logging
import subprocess
from pathlib import Path
from typing import Any

from lsp_server_manager import LSPCommunicationMode, LSPServerManager


class PyrightLSPManager(LSPServerManager):
    """LSP Server Manager for Pyright Python Language Server."""

    def __init__(self, workspace_path: str, python_path: str):
        """
        Initialize the Pyright LSP Manager.

        Args:
            workspace_path: Path to the Python workspace/project
            python_path: Path to the Python interpreter
        """
        self.workspace_path = Path(workspace_path)
        self.python_path = python_path
        self.logger = logging.getLogger(__name__)

        # Check if pyright is available and store version/method
        self.pyright_version, self.use_python_module = (
            self._check_pyright_availability()
        )

    def _check_pyright_availability(self) -> tuple[str, bool]:
        """Check if pyright is available in the system and return version and method.

        Returns:
            Tuple of (version_string, use_python_module)
        """
        # First try using the Python module (pip installed pyright)
        try:
            result = subprocess.run(
                [self.python_path, "-m", "pyright", "--version"],
                capture_output=True,
                text=True,
                check=True,
            )
            version = result.stdout.strip()
            self.logger.info(f"Pyright version (Python module): {version}")
            return version, True
        except (subprocess.CalledProcessError, FileNotFoundError):
            # Fallback to global npm installation
            try:
                result = subprocess.run(
                    ["pyright", "--version"], capture_output=True, text=True, check=True
                )
                version = result.stdout.strip()
                self.logger.info(f"Pyright version (global npm): {version}")
                return version, False
            except (subprocess.CalledProcessError, FileNotFoundError) as e:
                raise RuntimeError(
                    "Pyright is not available. Please install it with: pip install pyright or npm install -g pyright"
                ) from e

    def get_server_command(self) -> list[str]:
        """Get the command to start the pyright LSP server."""
        if self.use_python_module:
            # Use the pip-installed pyright langserver
            import os

            venv_path = os.path.dirname(
                os.path.dirname(self.python_path)
            )  # Go up from bin/python to venv root
            langserver_path = os.path.join(venv_path, "bin", "pyright-langserver")
            return [langserver_path, "--stdio"]
        else:
            # Use the global npm version
            return ["pyright-langserver", "--stdio"]

    def get_server_args(self) -> list[str]:
        """Get additional arguments for the pyright LSP server."""
        return []  # pyright-langserver doesn't need additional args for basic operation

    def get_communication_mode(self) -> LSPCommunicationMode:
        """Get the communication mode for pyright (stdio)."""
        return LSPCommunicationMode.STDIO

    def get_server_capabilities(self) -> dict[str, Any]:
        """Get the expected capabilities for pyright."""
        return {
            "textDocumentSync": 1,  # Full document sync
            "completionProvider": {
                "resolveProvider": True,
                "triggerCharacters": [".", "[", '"', "'"],
            },
            "hoverProvider": True,
            "signatureHelpProvider": {"triggerCharacters": ["(", ","]},
            "definitionProvider": True,
            "referencesProvider": True,
            "documentHighlightProvider": True,
            "documentSymbolProvider": True,
            "workspaceSymbolProvider": True,
            "codeActionProvider": True,
            "codeLensProvider": {"resolveProvider": True},
            "documentFormattingProvider": False,  # Pyright doesn't format
            "documentRangeFormattingProvider": False,
            "documentOnTypeFormattingProvider": None,
            "renameProvider": True,
            "documentLinkProvider": None,
            "colorProvider": None,
            "foldingRangeProvider": None,
            "executeCommandProvider": None,
            "workspace": {
                "workspaceFolders": {"supported": True, "changeNotifications": True}
            },
        }

    def get_initialization_options(self) -> dict[str, Any]:
        """Get initialization options for pyright."""
        options = {
            "settings": {
                "python": {
                    "analysis": {
                        "autoSearchPaths": True,
                        "useLibraryCodeForTypes": True,
                        "diagnosticMode": "workspace",
                    }
                }
            }
        }

        # Add Python path if specified
        options["settings"]["python"]["pythonPath"] = self.python_path  # type: ignore

        return options

    def validate_server_response(self, response: dict[str, Any]) -> bool:
        """Validate server initialization response."""
        # Check if the response contains expected pyright capabilities
        if "capabilities" not in response:
            return False

        capabilities = response["capabilities"]

        # Check for basic LSP capabilities that pyright should support
        required_capabilities = [
            "textDocumentSync",
            "completionProvider",
            "hoverProvider",
            "definitionProvider",
        ]

        missing_capabilities = [
            cap for cap in required_capabilities if cap not in capabilities
        ]

        if missing_capabilities:
            missing_caps_str = ", ".join(missing_capabilities)
            error_msg = (
                f"Pyright server missing required capabilities: {missing_caps_str}"
            )
            self.logger.error(error_msg)
            raise RuntimeError(error_msg)

        return True

    def get_workspace_folders(self) -> list[dict[str, Any]]:
        """Get workspace folders for pyright initialization."""
        workspace_uri = self.workspace_path.as_uri()
        workspace_name = self.workspace_path.name

        return [{"uri": workspace_uri, "name": workspace_name}]

    def prepare_workspace(self) -> None:
        """Prepare the workspace for pyright analysis."""
        self.logger.debug(f"Preparing workspace: {self.workspace_path}")

        # Create or update pyrightconfig.json if needed
        self._create_pyright_config()

        # Verify workspace is a valid Python project
        if not self._is_valid_python_workspace():
            self.logger.warning(
                f"Workspace {self.workspace_path} may not be a valid Python project"
            )
        else:
            self.logger.debug(
                f"Workspace {self.workspace_path} is a valid Python project"
            )

    def _create_pyright_config(self) -> None:
        """Create or update pyrightconfig.json for the workspace."""
        config_path = self.workspace_path / "pyrightconfig.json"

        # Default pyright configuration
        config = {
            "include": ["**/*.py"],
            "exclude": [
                "**/.git",
                "**/__pycache__",
                "**/node_modules",
                "**/.venv",
                "**/venv",
            ],
            "reportMissingImports": "warning",
            "reportMissingTypeStubs": "information",
            "pythonVersion": "3.8",
            "pythonPlatform": "All",
            "typeCheckingMode": "basic",
        }

        # Add Python path if specified
        config["pythonPath"] = self.python_path

        # Only create config if it doesn't exist
        if not config_path.exists():
            try:
                with open(config_path, "w") as f:
                    json.dump(config, f, indent=2)
                self.logger.info(f"Created pyrightconfig.json at {config_path}")
                self.logger.debug(f"Pyright config content: {config}")
            except Exception as e:
                self.logger.error(f"Failed to create pyrightconfig.json: {e}")
        else:
            self.logger.debug(f"Pyrightconfig.json already exists at {config_path}")

    def _is_valid_python_workspace(self) -> bool:
        """Check if the workspace is a valid Python project."""
        python_indicators = [
            "*.py",
            "pyproject.toml",
            "setup.py",
            "requirements.txt",
            "Pipfile",
            "poetry.lock",
        ]

        for indicator in python_indicators:
            if list(self.workspace_path.glob(indicator)):
                return True

        return False

    def cleanup(self) -> None:
        """Clean up any resources used by the manager."""
        # Remove any temporary configuration files if needed
        # Currently pyright doesn't require special cleanup
        self.logger.debug("Cleaning up Pyright LSP manager resources")
        pass

    def restart_required(self) -> bool:
        """Check if server restart is required due to configuration changes."""
        # Check if pyrightconfig.json has been modified
        config_path = self.workspace_path / "pyrightconfig.json"
        if config_path.exists():
            try:
                with open(config_path) as f:
                    config = json.load(f)
                    # Check if Python path has changed
                    if config.get("pythonPath") != self.python_path:
                        return True
            except Exception as e:
                self.logger.warning(f"Could not read pyrightconfig.json: {e}")
                return True

        return False

    def get_restart_delay(self) -> float:
        """Get recommended delay before restart in seconds."""
        return 1.0  # Pyright starts quickly

    def is_healthy(self) -> bool:
        """Check if the manager configuration is healthy."""
        try:
            return self.validate_configuration()
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            return False

    def validate_configuration(self) -> bool:
        """Validate the current configuration."""
        # Check if workspace exists
        if not self.workspace_path.exists():
            self.logger.error(f"Workspace path does not exist: {self.workspace_path}")
            return False

        # Check if Python path is valid
        python_path = Path(self.python_path)
        if not python_path.exists():
            self.logger.error(f"Python path does not exist: {self.python_path}")
            return False

        # Test Python executable
        try:
            result = subprocess.run(
                [self.python_path, "--version"],
                capture_output=True,
                text=True,
                check=True,
            )
            self.logger.info(f"Using Python: {result.stdout.strip()}")
        except (subprocess.CalledProcessError, FileNotFoundError):
            self.logger.error(f"Invalid Python executable: {self.python_path}")
            return False

        return True

    def get_server_info(self) -> dict[str, Any]:
        """Get information about the pyright server."""
        return {
            "name": "pyright",
            "version": self.pyright_version,
            "workspace": str(self.workspace_path),
            "python_path": self.python_path,
        }
