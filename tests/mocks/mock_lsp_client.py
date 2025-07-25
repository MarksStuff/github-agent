"""Mock LSP client for testing."""

import logging


class MockLSPClient:
    """Minimal mock LSP client for testing compatibility."""

    def __init__(self, workspace_root: str = "/test"):
        self.workspace_root = workspace_root
        self.logger = logging.getLogger(__name__)

    async def get_definition(
        self, uri: str, line: int, character: int
    ) -> list[dict] | None:
        """Mock get_definition method."""
        return []

    async def get_references(
        self, uri: str, line: int, character: int, include_declaration: bool = True
    ) -> list[dict] | None:
        """Mock get_references method."""
        return []

    async def get_hover(self, uri: str, line: int, character: int) -> dict | None:
        """Mock get_hover method."""
        return None
