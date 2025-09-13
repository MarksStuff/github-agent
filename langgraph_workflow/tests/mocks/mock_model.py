"""Mock language model for testing."""

from collections.abc import Sequence
from typing import Any

from langchain_core.messages import BaseMessage

from ...interfaces import ModelInterface


class MockModel(ModelInterface):
    """Mock language model for testing."""

    def __init__(self, responses: list[str] | None = None):
        """Initialize with predefined responses.

        Args:
            responses: List of responses to return (cycles through)
        """
        self.responses = responses or ["Mock response"]
        self.call_count = 0
        self.last_messages: list[BaseMessage] | None = None

    async def ainvoke(self, messages: Sequence[BaseMessage]) -> Any:
        """Return mock response."""
        self.last_messages = list(messages)
        response = self.responses[self.call_count % len(self.responses)]
        self.call_count += 1

        # Return object with content attribute like real models
        class MockResponse:
            def __init__(self, content: str):
                self.content = content

        return MockResponse(response)
