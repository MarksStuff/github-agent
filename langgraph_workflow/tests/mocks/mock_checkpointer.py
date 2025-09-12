"""Mock checkpointer for testing."""

from ...interfaces import CheckpointerInterface


class MockCheckpointer(CheckpointerInterface):
    """Mock checkpointer for testing."""

    def __init__(self):
        """Initialize mock checkpointer."""
        self.checkpoints = {}

    async def put(self, config: dict, checkpoint: dict, metadata: dict) -> None:
        """Save mock checkpoint."""
        thread_id = config.get("configurable", {}).get("thread_id", "default")
        self.checkpoints[thread_id] = {
            "config": config.copy(),
            "checkpoint": checkpoint.copy(),
            "metadata": metadata.copy(),
        }

    async def get(self, config: dict) -> dict | None:
        """Get mock checkpoint."""
        thread_id = config.get("configurable", {}).get("thread_id", "default")
        saved = self.checkpoints.get(thread_id)
        return saved["checkpoint"].copy() if saved else None
