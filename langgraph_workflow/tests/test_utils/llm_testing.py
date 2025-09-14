"""Reusable testing utilities for LLM-based functions."""

import os
from typing import Any, Protocol
from unittest.mock import Mock, patch

import pytest
import requests


class LLMFunction(Protocol):
    """Protocol for LLM-based functions that can be tested."""

    async def __call__(self, *args: Any, **kwargs: Any) -> str | None:
        """Call the LLM function."""
        ...


class LLMTestingMixin:
    """Mixin class providing common LLM testing utilities."""

    @staticmethod
    def check_ollama_available() -> bool:
        """Check if Ollama is available for integration testing."""
        import os

        ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        try:
            response = requests.get(f"{ollama_url}/api/version", timeout=2)
            return response.status_code == 200
        except Exception:
            return False

    @staticmethod
    def check_claude_cli_available() -> bool:
        """Check if Claude CLI is available."""
        try:
            import subprocess

            result = subprocess.run(
                ["claude", "--version"], capture_output=True, text=True, timeout=5
            )
            return result.returncode == 0 and "Claude Code" in result.stdout
        except Exception:
            return False

    def assert_structural_quality(
        self,
        result: str | None,
        min_length: int = 10,
        max_length: int = 5000,
        required_sections: list[str] | None = None,
        forbidden_sections: list[str] | None = None,
    ) -> None:
        """Assert structural quality of LLM output."""
        assert result is not None, "LLM output should not be None"
        assert isinstance(result, str), "LLM output should be a string"
        assert (
            min_length <= len(result) <= max_length
        ), f"Output length {len(result)} not in range [{min_length}, {max_length}]"

        if required_sections:
            result_lower = result.lower()
            for section in required_sections:
                assert (
                    section.lower() in result_lower
                ), f"Required section '{section}' not found in output"

        if forbidden_sections:
            result_lower = result.lower()
            for section in forbidden_sections:
                assert (
                    section.lower() not in result_lower
                ), f"Forbidden section '{section}' found in output"

    def assert_semantic_quality(
        self,
        result: str | None,
        expected_concepts: list[str],
        min_concept_matches: int = 1,
        unexpected_concepts: list[str] | None = None,
    ) -> None:
        """Assert semantic quality of LLM output."""
        assert result is not None, "LLM output should not be None"

        result_lower = result.lower()

        # Check for expected concepts
        concept_matches = sum(
            1 for concept in expected_concepts if concept.lower() in result_lower
        )
        assert (
            concept_matches >= min_concept_matches
        ), f"Expected at least {min_concept_matches} matching concepts from {expected_concepts}, got {concept_matches}"

        # Check for unexpected concepts
        if unexpected_concepts:
            unexpected_found = [
                concept
                for concept in unexpected_concepts
                if concept.lower() in result_lower
            ]
            assert (
                not unexpected_found
            ), f"Found unexpected concepts in output: {unexpected_found}"

    def assert_instruction_following(
        self,
        result: str | None,
        should_contain: list[str] | None = None,
        should_not_contain: list[str] | None = None,
        format_requirements: dict[str, Any] | None = None,
    ) -> None:
        """Assert that LLM followed specific instructions."""
        assert result is not None, "LLM output should not be None"

        if should_contain:
            for item in should_contain:
                assert item in result, f"Output should contain '{item}' but doesn't"

        if should_not_contain:
            for item in should_not_contain:
                assert (
                    item not in result
                ), f"Output should not contain '{item}' but does"

        if format_requirements:
            # Check format-specific requirements
            if format_requirements.get("starts_with"):
                assert result.startswith(
                    format_requirements["starts_with"]
                ), f"Output should start with '{format_requirements['starts_with']}'"

            if format_requirements.get("ends_with"):
                assert result.endswith(
                    format_requirements["ends_with"]
                ), f"Output should end with '{format_requirements['ends_with']}'"

            if format_requirements.get("line_count_range"):
                line_count = len(result.split("\n"))
                min_lines, max_lines = format_requirements["line_count_range"]
                assert (
                    min_lines <= line_count <= max_lines
                ), f"Line count {line_count} not in range [{min_lines}, {max_lines}]"


class MockLLMResponse:
    """Mock LLM response builder for testing."""

    def __init__(self, response_text: str):
        self.response_text = response_text

    def create_cli_mock(self) -> list[Mock]:
        """Create mocks for CLI calls using stdin."""
        version_mock = Mock(returncode=0, stdout="1.0.113 (CLI Tool)")
        response_mock = Mock(returncode=0, stdout=self.response_text)
        return [version_mock, response_mock]

    def create_claude_cli_mock(self) -> list[Mock]:
        """Create mocks for Claude CLI calls specifically."""
        version_mock = Mock(returncode=0, stdout="1.0.113 (Claude Code)")
        response_mock = Mock(returncode=0, stdout=self.response_text)
        return [version_mock, response_mock]

    def create_api_mock(self) -> Mock:
        """Create mock for API response."""
        response_mock = Mock()
        response_mock.content = self.response_text
        return response_mock

    def create_claude_api_mock(self) -> Mock:
        """Deprecated: Use create_api_mock() instead."""
        return self.create_api_mock()

    def create_subprocess_error_mock(
        self, error_message: str = "CLI failed"
    ) -> list[Mock]:
        """Create mocks for CLI failure scenarios."""
        version_mock = Mock(returncode=0, stdout="1.0.113 (CLI Tool)")
        error_mock = Mock(returncode=1, stderr=error_message)
        return [version_mock, error_mock]


class LLMTestCase:
    """Test case data structure for LLM function testing."""

    def __init__(
        self,
        name: str,
        inputs: dict[str, Any],
        expected_mock_output: str,
        structural_requirements: dict[str, Any] | None = None,
        semantic_requirements: dict[str, Any] | None = None,
        instruction_requirements: dict[str, Any] | None = None,
    ):
        self.name = name
        self.inputs = inputs
        self.expected_mock_output = expected_mock_output
        self.structural_requirements = structural_requirements or {}
        self.semantic_requirements = semantic_requirements or {}
        self.instruction_requirements = instruction_requirements or {}


# Pytest fixtures and markers
@pytest.fixture(scope="session")
def ollama_available():
    """Session-scoped fixture to check Ollama availability."""
    return LLMTestingMixin.check_ollama_available()


@pytest.fixture(scope="session")
def claude_cli_available():
    """Session-scoped fixture to check Claude CLI availability."""
    return LLMTestingMixin.check_claude_cli_available()


# Custom pytest markers
def requires_ollama(func):
    """Decorator to skip tests that require Ollama."""
    return pytest.mark.skipif(
        not LLMTestingMixin.check_ollama_available(), reason="Ollama not available"
    )(func)


def requires_claude_cli(func):
    """Decorator to skip tests that require Claude CLI."""
    return pytest.mark.skipif(
        not LLMTestingMixin.check_claude_cli_available(),
        reason="Claude CLI not available",
    )(func)


def integration_test(func):
    """Decorator to mark integration tests."""
    return pytest.mark.integration(func)


class LLMTestFramework(LLMTestingMixin):
    """Complete testing framework for LLM-based functions."""

    def __init__(self, function_under_test: LLMFunction):
        self.function_under_test = function_under_test

    async def run_mock_test(
        self,
        test_case: LLMTestCase,
        mock_subprocess_calls: list[Mock] | None = None,
        mock_api_response: Mock | None = None,
    ) -> None:
        """Run a mock-based test for the LLM function."""
        # Default to successful Claude CLI mock
        if mock_subprocess_calls is None:
            mock_response = MockLLMResponse(test_case.expected_mock_output)
            mock_subprocess_calls = mock_response.create_claude_cli_mock()

        with patch("subprocess.run", side_effect=mock_subprocess_calls):
            if mock_api_response:
                # Mock API case
                with patch("langchain_anthropic.ChatAnthropic") as mock_claude:
                    mock_claude.return_value.ainvoke.return_value = mock_api_response
                    result = await self.function_under_test(**test_case.inputs)
            else:
                # Mock CLI case
                result = await self.function_under_test(**test_case.inputs)

        # Run assertions
        if test_case.structural_requirements:
            self.assert_structural_quality(result, **test_case.structural_requirements)

        if test_case.semantic_requirements:
            self.assert_semantic_quality(result, **test_case.semantic_requirements)

        if test_case.instruction_requirements:
            self.assert_instruction_following(
                result, **test_case.instruction_requirements
            )

    async def run_integration_test(
        self,
        test_case: LLMTestCase,
        use_ollama: bool = True,
    ) -> None:
        """Run an integration test with real LLM."""
        if use_ollama and not self.check_ollama_available():
            pytest.skip("Ollama not available for integration testing")

        # Configure environment for Ollama if requested
        env_patches = {}
        if use_ollama:
            # Use existing OLLAMA_BASE_URL or default
            import os

            ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
            env_patches["OLLAMA_BASE_URL"] = ollama_url
            # Clear Claude CLI availability to force API usage with Ollama
            env_patches["PATH"] = ""

        with patch.dict(os.environ, env_patches):
            result = await self.function_under_test(**test_case.inputs)

        # For integration tests, we focus on structural and semantic quality
        # rather than exact output matching
        if test_case.structural_requirements:
            self.assert_structural_quality(result, **test_case.structural_requirements)

        if test_case.semantic_requirements:
            self.assert_semantic_quality(result, **test_case.semantic_requirements)

        if test_case.instruction_requirements:
            self.assert_instruction_following(
                result, **test_case.instruction_requirements
            )

    async def run_error_handling_test(
        self,
        test_case: LLMTestCase,
        error_scenario: str = "cli_failure",
    ) -> None:
        """Run tests for error handling scenarios."""
        if error_scenario == "cli_failure":
            mock_calls = MockLLMResponse("").create_subprocess_error_mock()
            with patch("subprocess.run", side_effect=mock_calls):
                await self.function_under_test(**test_case.inputs)
                # Should fall back to text search or return None gracefully
                # Specific assertions depend on function behavior

        elif error_scenario == "no_claude_no_api":
            # Mock both CLI and API unavailable
            env_patch = {"PATH": "", "ANTHROPIC_API_KEY": ""}
            with patch.dict(os.environ, env_patch, clear=False):
                with patch("subprocess.run", side_effect=FileNotFoundError()):
                    try:
                        await self.function_under_test(**test_case.inputs)
                        # Should either return fallback result or raise gracefully
                    except ValueError as e:
                        assert "Claude CLI" in str(e) or "ANTHROPIC_API_KEY" in str(e)
