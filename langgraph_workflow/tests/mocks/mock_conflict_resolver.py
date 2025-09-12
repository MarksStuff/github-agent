"""Mock conflict resolver for testing."""

from typing import Any

from ...interfaces import ConflictResolverInterface


class MockConflictResolver(ConflictResolverInterface):
    """Mock conflict resolver for testing."""

    def __init__(self):
        """Initialize mock resolver."""
        self.identified_conflicts = []
        self.resolutions = {}

    async def identify_conflicts(
        self, analyses: dict[str, str]
    ) -> list[dict[str, Any]]:
        """Mock identify conflicts."""
        conflicts = []

        # Simple mock logic: create conflict if analyses mention "disagree"
        disagreeing_agents = []
        for agent, analysis in analyses.items():
            if "disagree" in analysis.lower() or "conflict" in analysis.lower():
                disagreeing_agents.append(agent)

        if disagreeing_agents:
            conflict = {
                "id": f"conflict_{len(self.identified_conflicts)}",
                "agents": disagreeing_agents,
                "description": "Mock conflict detected",
                "analyses": {agent: analyses[agent] for agent in disagreeing_agents},
            }
            conflicts.append(conflict)
            self.identified_conflicts.append(conflict)

        return conflicts

    async def resolve_conflict(self, conflict: dict[str, Any]) -> str:
        """Mock resolve conflict."""
        conflict_id = conflict.get("id", "unknown")
        resolution = self.resolutions.get(
            conflict_id, "Mock resolution: compromise reached"
        )
        return resolution

    def set_resolution(self, conflict_id: str, resolution: str) -> None:
        """Helper to set resolution for conflict."""
        self.resolutions[conflict_id] = resolution