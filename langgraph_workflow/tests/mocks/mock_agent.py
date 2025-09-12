"""Mock agent for testing."""

from typing import Any

from ...interfaces import AgentInterface


class MockAgent(AgentInterface):
    """Mock agent for testing with intelligent pattern-based responses."""

    def __init__(self, agent_type: str, responses: dict[str, str] | None = None, response_patterns: dict[str, str] | None = None):
        """Initialize mock agent.

        Args:
            agent_type: Type of agent
            responses: Dict of prompt_keyword -> response (legacy)
            response_patterns: Dict of feature_keyword -> intelligent response
        """
        self.agent_type = agent_type
        self.responses = responses or {}
        self.response_patterns = response_patterns or {}
        self.call_history = []

        # Add persona attribute for compatibility with existing code
        self.persona = self

    def ask(self, prompt: str) -> str:
        """Mock persona ask method (synchronous) with intelligent pattern matching."""
        self.call_history.append(("ask", prompt))
        
        prompt_lower = prompt.lower()

        # First check response patterns (more intelligent)
        for keyword, response in self.response_patterns.items():
            if keyword.lower() in prompt_lower:
                return response

        # Fallback to legacy responses  
        for keyword, response in self.responses.items():
            if keyword.lower() in prompt_lower:
                return response
                
        # Default response based on agent type
        if "default" in self.response_patterns:
            return self.response_patterns["default"]

        return f"Mock {self.agent_type} analysis: {prompt[:50]}..."

    async def analyze(self, prompt: str) -> str:
        """Mock analysis."""
        return self.ask(prompt)

    async def review(self, content: str, context: dict[str, Any]) -> str:
        """Mock review."""
        self.call_history.append(("review", content, context))
        return f"Mock {self.agent_type} review: Looks good"
    
    def get_response_history(self) -> list[tuple]:
        """Get the history of calls made to this agent."""
        return self.call_history.copy()
    
    def clear_history(self):
        """Clear the call history."""
        self.call_history.clear()
