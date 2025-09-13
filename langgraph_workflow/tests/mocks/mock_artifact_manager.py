"""Mock artifact manager for testing."""

from ...interfaces import ArtifactManagerInterface


class MockArtifactManager(ArtifactManagerInterface):
    """Mock artifact manager for testing."""

    def __init__(self, thread_id: str):
        """Initialize mock artifact manager."""
        self.thread_id = thread_id
        self.artifacts: dict[str, str] = {}  # key -> content
        self.artifact_paths: dict[str, str] = {}  # key -> path

    async def save_artifact(self, key: str, content: str, artifact_type: str) -> str:
        """Mock save artifact."""
        path = f"mock/artifacts/{self.thread_id}/{artifact_type}_{key}.txt"
        self.artifacts[key] = content
        self.artifact_paths[key] = path
        return path

    async def get_artifact(self, key: str) -> str | None:
        """Mock get artifact."""
        return self.artifacts.get(key)

    async def list_artifacts(self) -> dict[str, str]:
        """Mock list artifacts."""
        return self.artifact_paths.copy()
