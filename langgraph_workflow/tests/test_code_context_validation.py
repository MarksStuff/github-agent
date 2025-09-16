"""Test for code context document validation."""

import unittest
from unittest.mock import patch

from ..nodes.extract_code_context import extract_code_context_handler


class TestCodeContextValidation(unittest.IsolatedAsyncioTestCase):
    """Test that code context document validation works correctly."""

    def setUp(self):
        """Set up test fixtures."""
        self.state = {
            "repo_path": "/test/repo",
            "feature_description": "Test feature",
            "current_phase": None,
            "code_context_document": None,
            "artifacts_index": {},
            "pr_number": None,
        }

    async def test_short_context_fails(self):
        """Test that a short context document (like a summary) fails validation."""
        # Mock the Claude Code agent to return a short summary (the actual problem case)
        short_summary = """The Code Context Document has been completed. This Python codebase implements a sophisticated GitHub MCP (Model Context Protocol) server with a master-worker architecture, providing both GitHub API integration and LSP-based code intelligence for AI coding assistants. The system uses modern Python patterns, comprehensive testing, and robust process management to serve multiple repositories simultaneously through dedicated ports."""

        # Verify this is indeed less than 2000 chars
        self.assertLess(len(short_summary), 2000)

        with patch(
            "langgraph_workflow.nodes.extract_code_context._call_claude_code_agent"
        ) as mock_agent:
            mock_agent.return_value = short_summary

            # Should raise RuntimeError for insufficient analysis
            with self.assertRaises(RuntimeError) as context:
                await extract_code_context_handler(self.state)

            error_msg = str(context.exception)
            self.assertIn("Code context document is too short", error_msg)
            self.assertIn(f"{len(short_summary)} chars", error_msg)
            self.assertIn("minimum: 2000", error_msg)

    async def test_comprehensive_context_passes(self):
        """Test that a comprehensive context document passes validation."""
        # Create a comprehensive analysis that's over 2000 chars
        comprehensive_analysis = """# Comprehensive Code Context Document

## Architecture Overview
This repository implements a sophisticated multi-tier architecture with clear separation of concerns.
The system is built around a master-worker pattern where a main process manages multiple worker processes.

## Technology Stack
- **Language**: Python 3.12+
- **Frameworks**: FastAPI, LangChain, LangGraph
- **Testing**: pytest, unittest
- **Type Checking**: mypy with strict typing
- **Code Quality**: ruff for linting and formatting

## Repository Structure
```
├── langgraph_workflow/     # Main workflow implementation
│   ├── nodes/             # Workflow node implementations
│   ├── tests/             # Comprehensive test suite
│   ├── mocks/             # Mock implementations for testing
│   └── config.py          # Configuration management
├── multi_agent_workflow/   # Legacy multi-agent system
├── scripts/               # Automation and deployment scripts
└── docs/                  # Documentation
```

## Design Patterns
- **Dependency Injection**: Used throughout for testability
- **Abstract Base Classes**: Define interfaces for agents and analyzers
- **TypedDict**: For type-safe state management
- **Async/Await**: For concurrent operations

## Code Conventions
- All functions have type hints
- Comprehensive docstrings following Google style
- Test files mirror source structure
- Mock implementations instead of MagicMock for internal objects

## Testing Strategy
- Unit tests for all components
- Integration tests for workflow execution
- Mock implementations for external dependencies
- No use of MagicMock for internal objects

## Recent Changes
- Migrated from MultiAgentWorkflow to EnhancedMultiAgentWorkflow
- Implemented Claude CLI integration for code analysis
- Added comprehensive validation for code context documents
- Improved test infrastructure with proper mock inheritance

## Key Files and Their Purposes
- enhanced_workflow.py: Main workflow orchestration
- nodes/extract_code_context.py: Code context extraction logic
- config.py: Centralized configuration management
- tests/mocks/test_workflow.py: Comprehensive test mock implementation

## Integration Points
- GitHub API via MCP server
- Claude CLI for code analysis
- Ollama for text generation
- LSP servers for code intelligence

## Security Considerations
- No credentials in code
- Secure subprocess execution
- Input validation at all boundaries
- Error messages don't leak sensitive info
"""

        # Verify this is indeed over 2000 chars
        self.assertGreater(len(comprehensive_analysis), 2000)

        with patch(
            "langgraph_workflow.nodes.extract_code_context._call_claude_code_agent"
        ) as mock_agent:
            mock_agent.return_value = comprehensive_analysis

            with patch("pathlib.Path.mkdir"):
                with patch("pathlib.Path.write_text"):
                    result = await extract_code_context_handler(self.state)

            # Should succeed and store the document
            self.assertEqual(result["code_context_document"], comprehensive_analysis)
            self.assertIsNotNone(result["code_context_document"])

    async def test_empty_context_fails(self):
        """Test that an empty context document fails validation."""
        with patch(
            "langgraph_workflow.nodes.extract_code_context._call_claude_code_agent"
        ) as mock_agent:
            mock_agent.return_value = ""

            # Should raise RuntimeError for empty analysis
            with self.assertRaises(RuntimeError) as context:
                await extract_code_context_handler(self.state)

            error_msg = str(context.exception)
            self.assertIn("Agent failed to provide any analysis", error_msg)

    async def test_none_context_fails(self):
        """Test that None context document fails validation."""
        with patch(
            "langgraph_workflow.nodes.extract_code_context._call_claude_code_agent"
        ) as mock_agent:
            mock_agent.return_value = None

            # Should raise RuntimeError for None analysis
            with self.assertRaises(RuntimeError) as context:
                await extract_code_context_handler(self.state)

            error_msg = str(context.exception)
            self.assertIn("Agent failed to provide any analysis", error_msg)

    async def test_borderline_context_fails(self):
        """Test that a context just under 2000 chars fails."""
        # Create analysis that's just under 2000 chars
        borderline_analysis = "x" * 1999

        self.assertEqual(len(borderline_analysis), 1999)

        with patch(
            "langgraph_workflow.nodes.extract_code_context._call_claude_code_agent"
        ) as mock_agent:
            mock_agent.return_value = borderline_analysis

            # Should raise RuntimeError for insufficient analysis
            with self.assertRaises(RuntimeError) as context:
                await extract_code_context_handler(self.state)

            error_msg = str(context.exception)
            self.assertIn("Code context document is too short", error_msg)
            self.assertIn("1999 chars", error_msg)

    async def test_exactly_2000_chars_passes(self):
        """Test that a context with exactly 2000 chars passes."""
        exact_analysis = "x" * 2000

        self.assertEqual(len(exact_analysis), 2000)

        with patch(
            "langgraph_workflow.nodes.extract_code_context._call_claude_code_agent"
        ) as mock_agent:
            mock_agent.return_value = exact_analysis

            with patch("pathlib.Path.mkdir"):
                with patch("pathlib.Path.write_text"):
                    result = await extract_code_context_handler(self.state)

            # Should succeed
            self.assertEqual(result["code_context_document"], exact_analysis)
