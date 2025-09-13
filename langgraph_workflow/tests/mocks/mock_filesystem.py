"""Mock file system for testing."""

from pathlib import Path

from ...interfaces import FileSystemInterface


class MockFileSystem(FileSystemInterface):
    """Mock file system for testing."""

    def __init__(self):
        """Initialize mock file system."""
        self.files = {}
        self.directories = set()

    async def write_text(self, path: Path, content: str) -> None:
        """Mock write text."""
        self.files[str(path)] = content
        # Add parent directories
        parent = path.parent
        while parent != Path("."):
            self.directories.add(str(parent))
            parent = parent.parent

    async def read_text(self, path: Path) -> str:
        """Mock read text."""
        content = self.files.get(str(path))
        if content is None:
            raise FileNotFoundError(f"Mock file not found: {path}")
        return content

    async def exists(self, path: Path) -> bool:
        """Mock exists check."""
        return str(path) in self.files or str(path) in self.directories

    async def mkdir(
        self, path: Path, parents: bool = True, exist_ok: bool = True
    ) -> None:
        """Mock mkdir."""
        if parents:
            current = path
            while current != Path("."):
                self.directories.add(str(current))
                current = current.parent
        else:
            self.directories.add(str(path))
