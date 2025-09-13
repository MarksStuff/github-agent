"""Real agent implementations for integration testing.

These agents actually call Ollama models instead of returning mock responses.
Only used for integration tests to verify GPU activity.
"""

import os
from typing import Any

from langchain_core.messages import HumanMessage
from langchain_ollama import ChatOllama


class RealOllamaPersona:
    """Real persona that makes actual calls to Ollama models."""

    def __init__(self, agent_type: str, model_name: str = "qwen3:8b"):
        """Initialize with agent type and model.

        Args:
            agent_type: Type of agent (e.g., "senior-engineer", "test-first")
            model_name: Ollama model to use
        """
        self.agent_type = agent_type
        self.model_name = model_name

        # Create ChatOllama instance
        ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.model = ChatOllama(model=model_name, base_url=ollama_url, temperature=0.3)

    def ask(self, prompt: str) -> str:
        """Ask the persona a question (synchronous interface expected by workflow).

        Args:
            prompt: Question/task prompt

        Returns:
            Real model response
        """
        import asyncio

        # Check if we're already in an async context
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # We're in an async context, need to use run_until_complete
                # This is a bit hacky but needed for sync interface
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, self._async_ask(prompt))
                    return future.result()
            else:
                return asyncio.run(self._async_ask(prompt))
        except RuntimeError:
            return asyncio.run(self._async_ask(prompt))

    async def _async_ask(self, prompt: str) -> str:
        """Async implementation of ask."""
        agent_prompt = f"""You are a {self.agent_type} agent.

Task: {prompt}

Please provide a helpful analysis as a {self.agent_type}.
Keep your response concise but informative (2-3 sentences max).
"""

        try:
            print(f"🔥 {self.agent_type} calling Ollama model {self.model_name}...")
            response = await self.model.ainvoke([HumanMessage(content=agent_prompt)])
            print(f"✅ {self.agent_type} got response from Ollama!")
            return response.content
        except Exception as e:
            return f"Error calling Ollama: {e}"


class RealOllamaAgent:
    """Real agent that makes actual calls to Ollama models."""

    def __init__(self, agent_type: str, model_name: str = "qwen3:8b"):
        """Initialize with agent type and model.

        Args:
            agent_type: Type of agent (e.g., "senior-engineer", "test-first")
            model_name: Ollama model to use
        """
        self.agent_type = agent_type
        self.model_name = model_name
        self.persona = RealOllamaPersona(agent_type, model_name)

    async def analyze(self, prompt: str, context: dict[str, Any] | None = None) -> str:
        """Analyze using real Ollama model.

        Args:
            prompt: Analysis prompt
            context: Additional context (optional)

        Returns:
            Real model response
        """
        # Create agent-specific prompt
        agent_prompt = f"""You are a {self.agent_type} agent.

Task: {prompt}

Please provide a helpful analysis as a {self.agent_type}.
Keep your response concise but informative (2-3 sentences max).
"""

        if context:
            agent_prompt += f"\n\nContext: {context}"

        try:
            print(f"🔥 {self.agent_type} calling Ollama model {self.model_name}...")
            response = await self.model.ainvoke([HumanMessage(content=agent_prompt)])
            print(f"✅ {self.agent_type} got response from Ollama!")
            return response.content
        except Exception as e:
            return f"Error calling Ollama: {e}"

    async def review(self, content: str, context: dict[str, Any] | None = None) -> str:
        """Review content using real Ollama model.

        Args:
            content: Content to review
            context: Additional context (optional)

        Returns:
            Real model review
        """
        review_prompt = f"""You are a {self.agent_type} reviewing the following content:

{content}

Please provide a brief review focusing on what a {self.agent_type} would care about.
Keep it concise (2-3 sentences).
"""

        if context:
            review_prompt += f"\n\nContext: {context}"

        try:
            print(
                f"🔥 {self.agent_type} reviewing with Ollama model {self.model_name}..."
            )
            response = await self.model.ainvoke([HumanMessage(content=review_prompt)])
            print(f"✅ {self.agent_type} completed review with Ollama!")
            return response.content
        except Exception as e:
            return f"Error during review: {e}"


def create_real_ollama_agents() -> dict[str, RealOllamaAgent]:
    """Create real agents that call Ollama for integration testing.

    Returns:
        Dictionary of agent_type -> RealOllamaAgent
    """
    return {
        "senior-engineer": RealOllamaAgent("senior-engineer"),
        "test-first": RealOllamaAgent("test-first"),
        "fast-coder": RealOllamaAgent("fast-coder"),
        "architect": RealOllamaAgent("architect"),
    }
