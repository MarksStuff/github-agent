"""
LSP Server Factory

This module provides a factory for creating LSP server managers,
enabling easy switching between different LSP server implementations.
"""

import logging
from typing import Any

from lsp_server_manager import LSPServerManager


class LSPServerType:
    """LSP server type constants."""

    PYLSP = "pylsp"
    PYRIGHT = "pyright"


class LSPServerFactory:
    """Factory for creating LSP server manager instances."""

    @staticmethod
    def create_server_manager(
        server_type: str, workspace_path: str, python_path: str, **kwargs: Any
    ) -> LSPServerManager:
        """
        Create an LSP server manager of the specified type.

        Args:
            server_type: Type of LSP server (pylsp, pyright)
            workspace_path: Path to the workspace/project
            python_path: Path to the Python interpreter
            **kwargs: Additional server-specific options

        Returns:
            LSPServerManager instance

        Raises:
            ValueError: If server_type is not supported
        """
        logger = logging.getLogger(__name__)

        if server_type == LSPServerType.PYLSP:
            from pylsp_manager import PylspManager

            logger.info(f"Creating pylsp manager for workspace: {workspace_path}")
            return PylspManager(workspace_path, python_path)

        elif server_type == LSPServerType.PYRIGHT:
            from pyright_lsp_manager import PyrightLSPManager

            logger.info(f"Creating pyright manager for workspace: {workspace_path}")
            return PyrightLSPManager(workspace_path, python_path)

        else:
            supported_types = [LSPServerType.PYLSP, LSPServerType.PYRIGHT]
            raise ValueError(
                f"Unsupported LSP server type: {server_type}. "
                f"Supported types: {supported_types}"
            )

    @staticmethod
    def get_default_server_type() -> str:
        """Get the default LSP server type for Python projects."""
        # Use pylsp as default due to better reliability
        return LSPServerType.PYLSP

    @staticmethod
    def get_supported_server_types() -> list[str]:
        """Get list of supported LSP server types."""
        return [LSPServerType.PYLSP, LSPServerType.PYRIGHT]


def create_default_python_lsp_manager(
    workspace_path: str, python_path: str
) -> LSPServerManager:
    """
    Create the default Python LSP server manager.

    This is a convenience function that creates the recommended
    LSP server manager for Python projects.

    Args:
        workspace_path: Path to the workspace/project
        python_path: Path to the Python interpreter

    Returns:
        LSPServerManager instance
    """
    return LSPServerFactory.create_server_manager(
        LSPServerFactory.get_default_server_type(), workspace_path, python_path
    )
