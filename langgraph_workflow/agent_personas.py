"""Agent personas for the LangGraph workflow, bridging with existing implementations."""

import logging
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Add parent directory to import existing agents
sys.path.append(str(Path(__file__).parent.parent))

# Try to import base agents, fall back to mock implementations if not available
try:
    from multi_agent_workflow.agent_interface import (
        ArchitectAgent as BaseArchitectAgent,
    )
    from multi_agent_workflow.agent_interface import (
        DeveloperAgent as BaseDeveloperAgent,
    )
    from multi_agent_workflow.agent_interface import (
        SeniorEngineerAgent as BaseSeniorEngineerAgent,
    )
    from multi_agent_workflow.agent_interface import (
        TesterAgent as BaseTesterAgent,
    )
except ImportError:
    # For testing or when dependencies aren't available, create mock base agents
    logger.warning(
        "Could not import base agents from multi_agent_workflow. Using mock implementations."
    )

    class MockBaseAgent:
        """Mock base agent for when real ones aren't available."""

        def __init__(self, agent_type: str):
            self.persona = self
            self.agent_type = agent_type

        def ask(self, prompt: str) -> str:
            return f"Mock {self.agent_type} response to: {prompt[:50]}..."

    class BaseTesterAgent(MockBaseAgent):
        def __init__(self):
            super().__init__("tester")

    class BaseDeveloperAgent(MockBaseAgent):
        def __init__(self):
            super().__init__("developer")

    class BaseSeniorEngineerAgent(MockBaseAgent):
        def __init__(self):
            super().__init__("senior-engineer")

    class BaseArchitectAgent(MockBaseAgent):
        def __init__(self):
            super().__init__("architect")


class LangGraphAgent:
    """Base class for LangGraph-compatible agents."""

    def __init__(self, base_agent: Any, agent_type: str):
        """Initialize with a base agent.

        Args:
            base_agent: Base agent implementation
            agent_type: Type identifier
        """
        self.base_agent = base_agent
        self.agent_type = agent_type
        self.persona = base_agent.persona

    async def analyze(self, prompt: str) -> str:
        """Analyze using the agent's persona.

        Args:
            prompt: Analysis prompt

        Returns:
            Analysis result
        """
        try:
            # Use the base agent's persona
            response = self.persona.ask(prompt)
            return response
        except Exception as e:
            logger.error(f"{self.agent_type} analysis error: {e}")
            return f"Error: {e}"

    async def review(self, content: str, context: dict[str, Any]) -> str:
        """Review content and provide feedback.

        Args:
            content: Content to review
            context: Additional context

        Returns:
            Review feedback
        """
        prompt = self._build_review_prompt(content, context)
        return await self.analyze(prompt)

    def _build_review_prompt(self, content: str, context: dict[str, Any]) -> str:
        """Build review prompt for the agent.

        Args:
            content: Content to review
            context: Additional context

        Returns:
            Formatted prompt
        """
        return f"""As {self.agent_type}, review the following content:

{content}

Context:
{context}

Provide your feedback focusing on your area of expertise."""


class TestFirstAgent(LangGraphAgent):
    """Test-first agent for LangGraph workflow."""

    def __init__(self, base_agent=None):
        """Initialize test-first agent.

        Args:
            base_agent: Optional base agent to use (for dependency injection)
        """
        if base_agent is None:
            base_agent = BaseTesterAgent()
        super().__init__(base_agent, "test-first")

    async def write_tests(self, skeleton: str, design: str) -> str:
        """Write tests based on skeleton and design.

        Args:
            skeleton: Code skeleton
            design: Design document

        Returns:
            Test code
        """
        prompt = f"""As a test-first developer, write comprehensive tests for this code skeleton:

Skeleton:
{skeleton}

Design Document:
{design}

Write tests that:
1. Cover all public interfaces
2. Test edge cases
3. Verify error handling
4. Ensure the design requirements are met

Return only the test code, no explanations."""

        return await self.analyze(prompt)

    async def write_component_tests(self, implementation: str, unit_tests: str) -> str:
        """Write component-level tests.

        Args:
            implementation: Implementation code
            unit_tests: Existing unit tests

        Returns:
            Component test code
        """
        prompt = f"""Write component-level tests that go beyond unit tests.

Implementation:
{implementation}

Existing Unit Tests:
{unit_tests}

Focus on:
1. Integration between components
2. Data flow through the system
3. Component interactions
4. State management

Return only the test code."""

        return await self.analyze(prompt)


class FastCoderAgent(LangGraphAgent):
    """Fast-coder agent for rapid implementation."""

    def __init__(self, base_agent=None):
        """Initialize fast-coder agent.

        Args:
            base_agent: Optional base agent to use (for dependency injection)
        """
        if base_agent is None:
            base_agent = BaseDeveloperAgent()
        super().__init__(base_agent, "fast-coder")

    async def implement(self, skeleton: str, design: str) -> str:
        """Implement based on skeleton and design.

        Args:
            skeleton: Code skeleton
            design: Design document

        Returns:
            Implementation code
        """
        prompt = f"""As a fast-coder, implement this skeleton quickly and efficiently:

Skeleton:
{skeleton}

Design Document:
{design}

Focus on:
1. Getting it working quickly
2. Meeting the functional requirements
3. Practical, straightforward solutions

Return only the implementation code."""

        return await self.analyze(prompt)

    async def refactor_for_tests(self, code: str, test_failures: dict) -> str:
        """Refactor code to fix test failures.

        Args:
            code: Current implementation
            test_failures: Test failure information

        Returns:
            Refactored code
        """
        prompt = f"""Fix the failing tests by refactoring this code:

Current Code:
{code}

Test Failures:
{test_failures}

Make minimal changes to fix the tests while maintaining functionality.

Return only the fixed code."""

        return await self.analyze(prompt)


class SeniorEngineerAgent(LangGraphAgent):
    """Senior engineer agent for code quality and patterns."""

    def __init__(self, base_agent=None):
        """Initialize senior engineer agent.

        Args:
            base_agent: Optional base agent to use (for dependency injection)
        """
        if base_agent is None:
            base_agent = BaseSeniorEngineerAgent()
        super().__init__(base_agent, "senior-engineer")

    async def analyze_codebase(self, repo_path: str) -> dict[str, Any]:
        """Analyze codebase to create context document.

        Args:
            repo_path: Repository path

        Returns:
            Codebase analysis
        """
        prompt = f"""Analyze the codebase at {repo_path} and provide:

1. Architecture overview
2. Technology stack
3. Design patterns used
4. Code conventions
5. Key interfaces and contracts
6. Infrastructure services
7. Testing approach
8. Areas marked for refactoring
9. Recent changes

Return a structured analysis."""

        response = await self.analyze(prompt)

        # Parse response into structured format
        # This would be more sophisticated in production
        return {
            "architecture": "Analyzed architecture",
            "languages": ["Python"],
            "frameworks": [],
            "patterns": "Identified patterns",
            "conventions": "Code conventions",
            "interfaces": "Key interfaces",
            "services": "Infrastructure services",
            "testing": "Testing approach",
            "recent_changes": "Recent changes",
        }

    async def create_skeleton(self, design: str) -> str:
        """Create code skeleton from design.

        Args:
            design: Design document

        Returns:
            Code skeleton
        """
        prompt = f"""Create a code skeleton (signatures only, no implementation) based on this design:

{design}

Include:
1. All classes and their methods
2. Function signatures with type hints
3. Proper interfaces and abstractions
4. Clear structure and organization

Return only the skeleton code with empty implementations (pass statements)."""

        return await self.analyze(prompt)

    async def refactor_for_quality(self, code: str, tests: str) -> str:
        """Refactor code for quality and patterns.

        Args:
            code: Current implementation
            tests: Test suite

        Returns:
            Refactored code
        """
        prompt = f"""Refactor this code for quality, simplicity, and proper patterns:

Code:
{code}

Tests (for reference):
{tests}

Focus on:
1. Removing duplication
2. Improving clarity
3. Applying design patterns where appropriate
4. Simplifying complex logic
5. Ensuring SOLID principles

Return only the refactored code."""

        return await self.analyze(prompt)


class ArchitectAgent(LangGraphAgent):
    """Architect agent for system design and scalability."""

    def __init__(self, base_agent=None):
        """Initialize architect agent.

        Args:
            base_agent: Optional base agent to use (for dependency injection)
        """
        if base_agent is None:
            base_agent = BaseArchitectAgent()
        super().__init__(base_agent, "architect")

    async def synthesize_analyses(self, analyses: dict[str, str]) -> str:
        """Synthesize multiple agent analyses.

        Args:
            analyses: Dict of agent_type -> analysis

        Returns:
            Synthesis document
        """
        prompt = f"""As the Architect, synthesize these agent analyses into a cohesive view:

{analyses}

Create a synthesis with:
1. Common Themes (where 2+ agents align)
2. Conflicts (explicit disagreements)
3. Trade-offs (what each approach optimizes for)
4. Questions requiring code investigation

Remain neutral - document rather than judge."""

        return await self.analyze(prompt)

    async def review_skeleton(self, skeleton: str) -> str:
        """Review skeleton for system consistency.

        Args:
            skeleton: Code skeleton

        Returns:
            Review feedback
        """
        prompt = f"""Review this code skeleton for system consistency and integration:

{skeleton}

Check for:
1. Proper system boundaries
2. Clean interfaces
3. Scalability considerations
4. Integration points
5. Potential architectural issues

Provide specific feedback. Say 'approve' if acceptable, or explain concerns."""

        return await self.analyze(prompt)

    async def design_scalability_tests(self, integration_tests: str) -> str:
        """Design scalability tests.

        Args:
            integration_tests: Existing integration tests

        Returns:
            Scalability test code
        """
        prompt = f"""Design scalability tests to complement these integration tests:

{integration_tests}

Focus on:
1. Performance under load
2. Resource usage
3. Concurrent operations
4. Data volume handling
5. System limits

Return test code that ensures scalability requirements."""

        return await self.analyze(prompt)

    async def assess_system_impact(self, solution: str) -> str:
        """Assess system-wide impact of a solution.

        Args:
            solution: Proposed solution

        Returns:
            Impact assessment
        """
        prompt = f"""Assess the system-wide impact of this solution:

{solution}

Consider:
1. Performance implications
2. Scalability effects
3. Integration complexity
4. Maintenance burden
5. Future extensibility

Provide a clear assessment of impacts and risks."""

        return await self.analyze(prompt)


# Factory function to create agents
def create_agents(
    base_agents: dict[str, Any] | None = None,
) -> dict[str, LangGraphAgent]:
    """Create all agents for the workflow.

    Args:
        base_agents: Optional dict of base agents for dependency injection

    Returns:
        Dict of agent_type -> agent instance
    """
    if base_agents is None:
        # Use default base agents
        return {
            "test-first": TestFirstAgent(),
            "fast-coder": FastCoderAgent(),
            "senior-engineer": SeniorEngineerAgent(),
            "architect": ArchitectAgent(),
        }
    else:
        # Use injected base agents
        return {
            "test-first": TestFirstAgent(base_agents.get("test-first")),
            "fast-coder": FastCoderAgent(base_agents.get("fast-coder")),
            "senior-engineer": SeniorEngineerAgent(base_agents.get("senior-engineer")),
            "architect": ArchitectAgent(base_agents.get("architect")),
        }
