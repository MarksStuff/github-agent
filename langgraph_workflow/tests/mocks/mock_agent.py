"""Mock agent for testing."""

from typing import Any

from ...interfaces import AgentInterface


class MockAgent(AgentInterface):
    """Mock agent for testing."""

    def __init__(self, agent_type: str, responses: dict[str, str] | None = None):
        """Initialize mock agent.

        Args:
            agent_type: Type of agent
            responses: Dict of prompt_keyword -> response
        """
        self.agent_type = agent_type
        self.responses = responses or {}
        self.call_history = []

        # Add persona attribute for compatibility with existing code
        self.persona = self

    def ask(self, prompt: str) -> str:
        """Mock persona ask method (synchronous)."""
        self.call_history.append(("ask", prompt))

        # Return specific response if keyword matches
        for keyword, response in self.responses.items():
            if keyword.lower() in prompt.lower():
                return response

        return f"Mock {self.agent_type} analysis: {prompt[:50]}..."

    async def analyze(self, prompt: str) -> str:
        """Mock analysis."""
        return self.ask(prompt)

    async def review(self, content: str, context: dict[str, Any]) -> str:
        """Mock review."""
        self.call_history.append(("review", content, context))
        return f"Mock {self.agent_type} review: Looks good"
