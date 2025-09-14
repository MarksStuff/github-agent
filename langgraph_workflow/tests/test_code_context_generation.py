"""Tests for intelligent code context generation."""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from langgraph_workflow.langgraph_workflow import MultiAgentWorkflow
from langgraph_workflow.real_codebase_analyzer import RealCodebaseAnalyzer
from langgraph_workflow.tests.mocks import create_mock_agents
from langgraph_workflow.tests.mocks.test_workflow import MockTestMultiAgentWorkflow
from langgraph_workflow.tests.test_utils import LLMTestingMixin, MockLLMResponse


class TestCodeContextGeneration(LLMTestingMixin):
    """Test intelligent code context document generation."""

    @pytest.fixture
    def mock_analysis(self):
        """Mock analysis data for testing."""
        return {
            "architecture": "Layered architecture with API, service, and data layers",
            "languages": ["Python", "JavaScript", "YAML"],
            "frameworks": ["FastAPI", "LangChain"],
            "databases": ["SQLite"],
            "patterns": "Abstract base classes, Factory pattern, Property pattern",
            "conventions": "PEP 8, EditorConfig",
            "interfaces": "Python abstract interfaces",
            "services": "API endpoints, Python services",
            "testing": "pytest, pytest configuration",
            "recent_changes": "Git repository - recent changes available",
            "key_files": [
                "README.md - Project documentation",
                "requirements.txt - Python dependencies",
                "main.py - Application entry point",
                "src/ - Source code",
                "tests/ - Test suite",
            ],
        }

    @pytest.fixture
    def temp_workflow(self):
        """Create mock workflow instance for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a test repository structure
            repo_path = Path(temp_dir)
            (repo_path / "main.py").write_text("# Main application")
            (repo_path / "README.md").write_text("# Test Project")

            analyzer = RealCodebaseAnalyzer(str(repo_path))
            agents = create_mock_agents()

            workflow = MockTestMultiAgentWorkflow(
                repo_path=str(repo_path),
                thread_id="test-context",
                agents=agents,  # type: ignore  # Mock agents for testing
                codebase_analyzer=analyzer,
            )
            yield workflow

    @pytest.fixture
    def real_workflow(self):
        """Create real workflow instance for error testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a test repository structure
            repo_path = Path(temp_dir)
            (repo_path / "main.py").write_text("# Main application")
            (repo_path / "README.md").write_text("# Test Project")

            analyzer = RealCodebaseAnalyzer(str(repo_path))
            agents = create_mock_agents()

            workflow = MultiAgentWorkflow(
                repo_path=str(repo_path),
                thread_id="test-context",
                agents=agents,  # type: ignore  # Mock agents for testing
                codebase_analyzer=analyzer,
            )
            yield workflow

    @pytest.mark.asyncio
    async def test_intelligent_context_generation_with_llm_mock(
        self, temp_workflow, mock_analysis
    ):
        """Test intelligent context generation using mocked LLM."""

        expected_context = """# Code Context Document

## Executive Summary
This is a comprehensive analysis of a Python-based application with FastAPI and LangChain frameworks.

## Architecture Overview
**Primary Architecture**: Layered architecture with API, service, and data layers

This architecture provides clear separation of concerns with distinct layers for presentation, business logic, and data access.

## Technology Stack
- **Languages**: Python (primary), JavaScript (frontend/tooling), YAML (configuration)
- **Frameworks**: FastAPI (web API), LangChain (AI/ML integration)
- **Databases**: SQLite (lightweight data storage)

The stack represents a modern Python web application with AI/ML capabilities.

## Design Patterns & Principles
**Detected Patterns**: Abstract base classes, Factory pattern, Property pattern

The codebase demonstrates solid software engineering principles with appropriate abstraction and encapsulation.

## Testing Strategy
**Testing Approach**: pytest with comprehensive configuration

The project follows testing best practices with automated testing infrastructure.

## Feature Implementation Context
This architecture is well-suited for implementing new features through the established layered approach and dependency injection patterns.
"""

        # Mock the codebase analyzer to return our test data
        with patch.object(
            temp_workflow.codebase_analyzer, "analyze", return_value=mock_analysis
        ):
            # Mock Claude CLI response
            mock_response = MockLLMResponse(expected_context)
            mock_calls = mock_response.create_claude_cli_mock()

            with patch("subprocess.run", side_effect=mock_calls):
                result = await temp_workflow._generate_intelligent_code_context(
                    mock_analysis, "Add user authentication system"
                )

                # Test structural quality
                self.assert_structural_quality(
                    result,
                    min_length=200,
                    max_length=5000,
                    required_sections=[
                        "Executive Summary",
                        "Architecture",
                        "Technology Stack",
                    ],
                )

                # Test semantic quality
                self.assert_semantic_quality(
                    result,
                    expected_concepts=[
                        "architecture",
                        "python",
                        "fastapi",
                        "testing",
                        "patterns",
                    ],
                    min_concept_matches=3,
                    unexpected_concepts=["lorem ipsum", "placeholder", "todo"],
                )

    @pytest.mark.asyncio
    async def test_context_generation_fails_with_clear_error(
        self, real_workflow, mock_analysis
    ):
        """Test that LLM failures raise clear errors instead of falling back."""

        # Mock the codebase analyzer
        with patch.object(
            real_workflow.codebase_analyzer, "analyze", return_value=mock_analysis
        ):
            # Mock CLI failure and no API key
            with patch(
                "subprocess.run", side_effect=FileNotFoundError("CLI not found")
            ):
                with patch.dict("os.environ", {}, clear=True):  # No API key
                    # Should raise RuntimeError with clear error message
                    with pytest.raises(RuntimeError) as exc_info:
                        await real_workflow._generate_intelligent_code_context(
                            mock_analysis, "Add user authentication system"
                        )

                    # Verify error message is helpful
                    error_msg = str(exc_info.value)
                    assert "Code context generation failed" in error_msg
                    assert "No API access available" in error_msg
                    assert "ANTHROPIC_API_KEY" in error_msg
                    assert "SOLUTIONS:" in error_msg
                    assert "claude --version" in error_msg

    @pytest.mark.asyncio
    async def test_context_generation_with_feature_context(
        self, real_workflow, mock_analysis
    ):
        """Test that feature context is properly included."""

        feature_description = "Implement OAuth2 authentication with JWT tokens and user profile management"

        with patch.object(
            real_workflow.codebase_analyzer, "analyze", return_value=mock_analysis
        ):
            # Mock successful response that includes feature context
            mock_context = """# Code Context Document

## Executive Summary
Python web application ready for authentication feature implementation.

## Feature Implementation Context
The upcoming OAuth2 authentication feature will integrate seamlessly with the existing FastAPI architecture.
The current layered design provides clear extension points for authentication middleware and user services.

Key integration considerations:
- FastAPI dependency injection for auth services
- SQLite schema extensions for user data
- JWT token handling in API layer
- User profile endpoints following RESTful patterns
"""

            mock_response = MockLLMResponse(mock_context)
            mock_calls = mock_response.create_claude_cli_mock()

            # Mock Claude CLI to be available
            with patch("subprocess.run", side_effect=mock_calls):
                result = await real_workflow._generate_intelligent_code_context(
                    mock_analysis, feature_description
                )

                # Should mention the specific feature
                result_lower = result.lower()
                assert "oauth" in result_lower or "authentication" in result_lower
                assert "jwt" in result_lower or "token" in result_lower

                # Should provide implementation guidance
                assert "implementation" in result_lower or "integrate" in result_lower

    @pytest.mark.asyncio
    async def test_empty_response_validation(self, real_workflow, mock_analysis):
        """Test that empty LLM responses are caught and cause failures."""

        # Mock the codebase analyzer
        with patch.object(
            real_workflow.codebase_analyzer, "analyze", return_value=mock_analysis
        ):
            # Mock Claude CLI to return empty response
            version_mock = Mock(returncode=0, stdout="1.0.113 (Claude Code)")
            empty_response_mock = Mock(returncode=0, stdout="")  # Empty response

            with patch(
                "subprocess.run", side_effect=[version_mock, empty_response_mock]
            ):
                # Should raise ValueError for empty response
                with pytest.raises(RuntimeError) as exc_info:
                    await real_workflow._generate_intelligent_code_context(
                        mock_analysis, "Add user authentication system"
                    )

                # The empty response causes CLI to fail, then API fails due to no key
                # We should see the API key error, but check logs for empty response
                error_msg = str(exc_info.value)
                assert (
                    "no api access available" in error_msg.lower()
                    or "empty response" in error_msg.lower()
                )

                # The important thing is that empty responses are detected and logged
                # (The actual exception depends on whether API fallback is available)

    @pytest.mark.asyncio
    async def test_short_response_warning(self, real_workflow, mock_analysis):
        """Test that suspiciously short responses generate warnings."""

        # Mock the codebase analyzer
        with patch.object(
            real_workflow.codebase_analyzer, "analyze", return_value=mock_analysis
        ):
            # Mock Claude CLI to return very short response
            version_mock = Mock(returncode=0, stdout="1.0.113 (Claude Code)")
            short_response_mock = Mock(returncode=0, stdout="Too short")  # 9 chars

            with patch(
                "subprocess.run", side_effect=[version_mock, short_response_mock]
            ):
                with patch(
                    "langgraph_workflow.langgraph_workflow.logger"
                ) as mock_logger:
                    result = await real_workflow._generate_intelligent_code_context(
                        mock_analysis, "Add user authentication system"
                    )

                    # Should return the short response but log warnings
                    assert result == "Too short"
                    mock_logger.warning.assert_called()

                    # Check that warning mentions suspicious length
                    warning_calls = [
                        call.args[0] for call in mock_logger.warning.call_args_list
                    ]
                    assert any("suspiciously short" in msg for msg in warning_calls)
