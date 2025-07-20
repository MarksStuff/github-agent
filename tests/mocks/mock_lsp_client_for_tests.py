"""Mock LSP client for test compatibility."""


class MockLSPClientForTests:
    """Mock LSP client for test compatibility in RepositoryManager."""

    def __init__(self, workspace_root: str):
        self.workspace_root = workspace_root
