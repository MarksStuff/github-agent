"""Tests for model routing logic."""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from langgraph_workflow.routing.model_router import ModelRouter
from langgraph_workflow.state import AgentType, WorkflowPhase, initialize_state


class TestModelRouter:
    """Test model router functionality."""

    @pytest.fixture
    def model_router(self):
        """Create a model router instance."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            router = ModelRouter()
            # Mock the clients
            router.ollama_client = MagicMock()
            router.claude_client = MagicMock()
            return router

    def test_initialization_with_remote_ollama(self):
        """Test initialization with remote Ollama URL."""
        with patch.dict(
            os.environ,
            {
                "OLLAMA_BASE_URL": "http://remote-machine:11434",
                "ANTHROPIC_API_KEY": "test-key",
            },
        ):
            with patch("langgraph_workflow.routing.model_router.ChatOllama") as mock_ollama:
                with patch(
                    "langgraph_workflow.routing.model_router.ChatAnthropic"
                ) as mock_claude:
                    router = ModelRouter()

                    mock_ollama.assert_called_once_with(
                        base_url="http://remote-machine:11434",
                        model="qwen2.5-coder:7b",
                        temperature=0.1,
                    )
                    mock_claude.assert_called_once()

    def test_initialization_without_anthropic_key(self):
        """Test initialization without Anthropic API key."""
        with patch.dict(os.environ, {}, clear=True):
            router = ModelRouter()
            assert router.claude_client is None
            assert router.ollama_client is not None

    def test_should_escalate_on_explicit_flag(self, model_router):
        """Test escalation with explicit flag."""
        state = initialize_state("thread", "repo", "/path")
        state["escalation_needed"] = True

        should_escalate = model_router.should_escalate_to_claude(state, AgentType.DEVELOPER)
        assert should_escalate is True

    def test_should_escalate_on_finalization_phase(self, model_router):
        """Test escalation during finalization phase."""
        state = initialize_state("thread", "repo", "/path")
        state["current_phase"] = "finalization"

        should_escalate = model_router.should_escalate_to_claude(state, AgentType.DEVELOPER)
        assert should_escalate is True

    def test_should_escalate_on_retry_count(self, model_router):
        """Test escalation based on retry count."""
        state = initialize_state("thread", "repo", "/path")
        state["retry_count"] = 2

        should_escalate = model_router.should_escalate_to_claude(state, AgentType.DEVELOPER)
        assert should_escalate is True

        # Should not escalate with lower retry count
        state["retry_count"] = 1
        should_escalate = model_router.should_escalate_to_claude(state, AgentType.DEVELOPER)
        assert should_escalate is False

    def test_should_escalate_on_design_conflicts(self, model_router):
        """Test escalation based on design conflicts."""
        state = initialize_state("thread", "repo", "/path")
        state["design_conflicts"] = [{"conflict": i} for i in range(6)]

        should_escalate = model_router.should_escalate_to_claude(state, AgentType.DEVELOPER)
        assert should_escalate is True

        # Should not escalate with fewer conflicts
        state["design_conflicts"] = [{"conflict": i} for i in range(5)]
        should_escalate = model_router.should_escalate_to_claude(state, AgentType.DEVELOPER)
        assert should_escalate is False

    def test_should_escalate_for_complex_agents_in_analysis(self, model_router):
        """Test escalation for senior engineer and architect during analysis."""
        state = initialize_state("thread", "repo", "/path")
        state["current_phase"] = "analysis"

        # Should escalate for senior engineer
        should_escalate = model_router.should_escalate_to_claude(
            state, AgentType.SENIOR_ENGINEER
        )
        assert should_escalate is True

        # Should escalate for architect
        should_escalate = model_router.should_escalate_to_claude(state, AgentType.ARCHITECT)
        assert should_escalate is True

        # Should not escalate for developer
        should_escalate = model_router.should_escalate_to_claude(state, AgentType.DEVELOPER)
        assert should_escalate is False

    def test_should_escalate_on_file_count(self, model_router):
        """Test escalation based on file count."""
        state = initialize_state("thread", "repo", "/path")
        state["implementation_code"] = {f"file{i}.py": "code" for i in range(11)}

        should_escalate = model_router.should_escalate_to_claude(state, AgentType.DEVELOPER)
        assert should_escalate is True

    @pytest.mark.asyncio
    async def test_call_model_routes_to_claude(self, model_router):
        """Test routing to Claude when escalation is needed."""
        state = initialize_state("thread", "repo", "/path")
        state["escalation_needed"] = True

        model_router.claude_client.ainvoke = AsyncMock(
            return_value=MagicMock(content="Claude response")
        )

        result = await model_router.call_model("Test prompt", state, AgentType.DEVELOPER)

        assert result == "Claude response"
        model_router.claude_client.ainvoke.assert_called_once()

    @pytest.mark.asyncio
    async def test_call_model_routes_to_ollama(self, model_router):
        """Test routing to Ollama for routine tasks."""
        state = initialize_state("thread", "repo", "/path")

        model_router.ollama_client.ainvoke = AsyncMock(
            return_value=MagicMock(content="Ollama response")
        )

        result = await model_router.call_model("Test prompt", state, AgentType.DEVELOPER)

        assert result == "Ollama response"
        model_router.ollama_client.ainvoke.assert_called_once()

    @pytest.mark.asyncio
    async def test_call_model_fallback_on_claude_failure(self, model_router):
        """Test fallback to Ollama when Claude fails."""
        state = initialize_state("thread", "repo", "/path")
        state["escalation_needed"] = True

        model_router.claude_client.ainvoke = AsyncMock(side_effect=Exception("Claude error"))
        model_router.ollama_client.ainvoke = AsyncMock(
            return_value=MagicMock(content="Ollama fallback")
        )

        result = await model_router.call_model("Test prompt", state, AgentType.DEVELOPER)

        assert result == "Ollama fallback"
        model_router.claude_client.ainvoke.assert_called_once()
        model_router.ollama_client.ainvoke.assert_called_once()

    @pytest.mark.asyncio
    async def test_call_model_escalation_on_ollama_failure(self, model_router):
        """Test escalation to Claude when Ollama fails."""
        state = initialize_state("thread", "repo", "/path")

        model_router.ollama_client.ainvoke = AsyncMock(side_effect=Exception("Ollama error"))
        model_router.claude_client.ainvoke = AsyncMock(
            return_value=MagicMock(content="Claude escalation")
        )

        result = await model_router.call_model("Test prompt", state, AgentType.DEVELOPER)

        assert result == "Claude escalation"
        model_router.ollama_client.ainvoke.assert_called_once()
        model_router.claude_client.ainvoke.assert_called_once()

    def test_add_context_for_claude(self, model_router):
        """Test context enrichment for Claude."""
        state = initialize_state("thread", "repo", "/path")
        state["current_phase"] = WorkflowPhase.DESIGN
        state["feature_name"] = "Test Feature"
        state["retry_count"] = 2
        state["design_conflicts"] = [{"conflict": "1"}]
        state["messages_window"] = [{"role": "system", "content": "Previous message"}]

        prompt = "Original prompt"
        enriched = model_router._add_context_for_claude(prompt, state, AgentType.ARCHITECT)

        assert "Architect" in enriched
        assert "Test Feature" in enriched
        assert "retry attempt #2" in enriched
        assert "1 design conflicts" in enriched
        assert "Recent workflow context" in enriched
        assert "Original prompt" in enriched

    def test_add_context_for_ollama(self, model_router):
        """Test minimal context for Ollama."""
        state = initialize_state("thread", "repo", "/path")
        state["feature_name"] = "Test Feature"

        prompt = "Original prompt"
        enriched = model_router._add_context_for_ollama(prompt, state, AgentType.DEVELOPER)

        assert "Developer" in enriched
        assert "Test Feature" in enriched
        assert "Original prompt" in enriched
        assert len(enriched) < 500  # Should be concise

    def test_fallback_response(self, model_router):
        """Test fallback responses when no models available."""
        response = model_router._fallback_response("Test prompt", AgentType.ARCHITECT)
        assert "Architecture analysis pending" in response

        response = model_router._fallback_response("Test prompt", AgentType.DEVELOPER)
        assert "Implementation analysis pending" in response

        response = model_router._fallback_response("Test prompt", AgentType.SENIOR_ENGINEER)
        assert "Code quality review pending" in response

        response = model_router._fallback_response("Test prompt", AgentType.TESTER)
        assert "Test strategy analysis pending" in response

    def test_get_model_stats(self, model_router):
        """Test getting model statistics."""
        stats = model_router.get_model_stats()

        assert "ollama_available" in stats
        assert "claude_available" in stats
        assert "ollama_url" in stats
        assert "escalation_threshold" in stats
        assert "routing_config" in stats
        assert stats["routing_config"]["diff_size_limit"] == 300
        assert stats["routing_config"]["files_limit"] == 10

    @pytest.mark.asyncio
    async def test_test_connections(self, model_router):
        """Test connection testing."""
        model_router.ollama_client.ainvoke = AsyncMock(
            return_value=MagicMock(content="Ollama OK")
        )
        model_router.claude_client.ainvoke = AsyncMock(
            return_value=MagicMock(content="Claude OK")
        )

        results = await model_router.test_connections()

        assert results["ollama"]["status"] == "connected"
        assert "OK" in results["ollama"]["response"]
        assert results["claude"]["status"] == "connected"
        assert "OK" in results["claude"]["response"]

    @pytest.mark.asyncio
    async def test_test_connections_with_failures(self, model_router):
        """Test connection testing with failures."""
        model_router.ollama_client.ainvoke = AsyncMock(
            side_effect=Exception("Connection failed")
        )
        model_router.claude_client = None  # Not configured

        results = await model_router.test_connections()

        assert results["ollama"]["status"] == "failed"
        assert "Connection failed" in results["ollama"]["error"]
        assert results["claude"]["status"] == "not_configured"