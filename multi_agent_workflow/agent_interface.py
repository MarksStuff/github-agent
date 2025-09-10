"""Agent interface for wrapping coding personas in the workflow system."""

import logging
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any

from coding_personas import CLIWrapper, CodingPersonas

logger = logging.getLogger(__name__)


class AgentInterface(ABC):
    """Base class for all agent implementations."""

    def __init__(self, persona_factory: Callable[[], CLIWrapper], agent_type: str):
        """Initialize agent with a specific persona.

        Args:
            persona_factory: Factory function to create the persona
            agent_type: Type identifier for this agent
        """
        self.agent_type = agent_type
        self.persona = persona_factory()
        logger.info(f"Initialized {agent_type} agent")

    def analyze_task(self, context: dict[str, Any], task_spec: str) -> dict[str, Any]:
        """Analyze a task and produce agent-specific analysis.

        Args:
            context: Shared context including codebase info
            task_spec: Task specification to analyze

        Returns:
            Analysis results including content and metadata
        """
        prompt = self._build_analysis_prompt(context, task_spec)

        # Log the full prompt for debugging
        logger.debug(
            f"{self.agent_type} analysis prompt (length={len(prompt)}):\n{prompt}\n============================"
        )

        try:
            response = self.persona.ask(prompt)

            # Log the raw response for debugging
            logger.debug(
                f"{self.agent_type} raw response (length={len(response) if response else 0}):\n{response}\n============================"
            )

            return {
                "agent_type": self.agent_type,
                "analysis": response,
                "status": "success",
            }
        except Exception as e:
            logger.error(f"{self.agent_type} analysis failed: {e}")
            return {
                "agent_type": self.agent_type,
                "analysis": "",
                "status": "error",
                "error": str(e),
            }

    @abstractmethod
    def _build_analysis_prompt(self, context: dict[str, Any], task_spec: str) -> str:
        """Build the analysis prompt for this agent type.

        Args:
            context: Shared context
            task_spec: Task specification

        Returns:
            Formatted prompt for the persona
        """
        pass

    def review_peer_output(
        self, peer_analyses: dict[str, str], context: dict[str, Any]
    ) -> dict[str, Any]:
        """Review other agents' analyses and provide feedback.

        Args:
            peer_analyses: Analyses from other agents
            context: Shared context

        Returns:
            Review results including feedback and agreement/disagreement
        """
        prompt = self._build_peer_review_prompt(peer_analyses, context)

        # Log the full prompt for debugging
        logger.debug(
            f"{self.agent_type} peer review prompt (length={len(prompt)}):\n{prompt}\n============================"
        )

        try:
            response = self.persona.ask(prompt)

            # Log the raw response for debugging
            logger.debug(
                f"{self.agent_type} peer review raw response (length={len(response) if response else 0}):\n{response}\n============================"
            )

            logger.info(
                f"{self.agent_type} peer review response length: {len(response) if response else 0}"
            )
            logger.info(
                f"{self.agent_type} peer review response preview: {response[:100] if response else 'None'}..."
            )

            return {
                "agent_type": self.agent_type,
                "peer_review": response,
                "status": "success",
            }
        except Exception as e:
            logger.error(f"{self.agent_type} peer review failed: {e}")
            return {
                "agent_type": self.agent_type,
                "peer_review": "",
                "status": "error",
                "error": str(e),
            }

    def incorporate_human_feedback(
        self, feedback_items: list[dict], context: dict[str, Any]
    ) -> dict[str, Any]:
        """Process human feedback and update analysis.

        Args:
            feedback_items: List of human feedback items
            context: Shared context

        Returns:
            Updated analysis incorporating feedback
        """
        prompt = self._build_feedback_response_prompt(feedback_items, context)

        # Log the full prompt for debugging
        logger.debug(
            f"{self.agent_type} feedback response prompt (length={len(prompt)}):\n{prompt}\n============================"
        )

        try:
            response = self.persona.ask(prompt)

            # Log the raw response for debugging
            logger.debug(
                f"{self.agent_type} feedback response raw result (length={len(response) if response else 0}):\n{response}\n============================"
            )

            return {
                "agent_type": self.agent_type,
                "updated_analysis": response,
                "status": "success",
            }
        except Exception as e:
            logger.error(f"{self.agent_type} feedback incorporation failed: {e}")
            return {
                "agent_type": self.agent_type,
                "updated_analysis": "",
                "status": "error",
                "error": str(e),
            }

    @abstractmethod
    def _build_peer_review_prompt(
        self, peer_analyses: dict[str, str], context: dict[str, Any]
    ) -> str:
        """Build prompt for reviewing peer analyses."""
        pass

    @abstractmethod
    def _build_feedback_response_prompt(
        self, feedback_items: list[dict], context: dict[str, Any]
    ) -> str:
        """Build prompt for incorporating human feedback."""
        pass

    def cleanup(self):
        """Clean up the persona resources."""
        if hasattr(self.persona, "_cleanup"):
            self.persona._cleanup()

    async def implement_code(
        self, context: dict[str, Any], prompt: str
    ) -> dict[str, Any]:
        """Implement code based on design specifications.

        Args:
            context: Task context
            prompt: Implementation prompt

        Returns:
            Implementation result with code content
        """
        # Log the full prompt for debugging
        logger.debug(
            f"{self.agent_type} implement code prompt (length={len(prompt)}):\n{prompt}\n============================"
        )

        # Make it async-compatible but actually synchronous
        result = self.persona.ask(prompt)

        # Log the raw response for debugging
        logger.debug(
            f"{self.agent_type} implement code raw result (length={len(result) if result else 0}):\n{result}\n============================"
        )

        return {"content": result, "status": "success"}

    async def review_code(self, context: dict[str, Any], prompt: str) -> dict[str, Any]:
        """Review code implementation.

        Args:
            context: Task context
            prompt: Review prompt

        Returns:
            Review result with suggestions
        """
        # Log the full prompt for debugging
        logger.debug(
            f"{self.agent_type} review code prompt (length={len(prompt)}):\n{prompt}\n============================"
        )

        result = self.persona.ask(prompt)

        # Log the raw response for debugging
        logger.debug(
            f"{self.agent_type} review code raw result (length={len(result) if result else 0}):\n{result}\n============================"
        )

        # Parse suggestions from the review
        suggestions = []
        if "suggest" in result.lower() or "improve" in result.lower():
            # Extract suggestions - simple heuristic
            lines = result.split("\n")
            for line in lines:
                if line.strip().startswith(("-", "*", "•")) and (
                    "should" in line or "could" in line
                ):
                    suggestions.append(line.strip())

        return {"content": result, "suggestions": suggestions, "status": "success"}

    async def refine_implementation(
        self, context: dict[str, Any], original: dict, suggestions: list
    ) -> dict[str, Any]:
        """Refine implementation based on review suggestions.

        Args:
            context: Task context
            original: Original implementation
            suggestions: Review suggestions

        Returns:
            Refined implementation
        """
        prompt = f"""Please refine this implementation based on the following suggestions:

Original Implementation:
{original.get('content', '')}

Suggestions:
{chr(10).join(f"- {s}" for s in suggestions)}

Please provide the improved implementation addressing these suggestions."""

        # Log the full prompt for debugging
        logger.debug(
            f"{self.agent_type} refine implementation prompt (length={len(prompt)}):\n{prompt}\n============================"
        )

        result = self.persona.ask(prompt)

        # Log the raw response for debugging
        logger.debug(
            f"{self.agent_type} refine implementation raw result (length={len(result) if result else 0}):\n{result}\n============================"
        )

        return {"content": result, "status": "success"}

    async def create_tests(
        self, context: dict[str, Any], prompt: str
    ) -> dict[str, Any]:
        """Create tests for implemented features.

        Args:
            context: Task context
            prompt: Test creation prompt

        Returns:
            Test creation result
        """
        # Log the full prompt for debugging
        logger.debug(
            f"{self.agent_type} create tests prompt (length={len(prompt)}):\n{prompt}\n============================"
        )

        result = self.persona.ask(prompt)

        # Log the raw response for debugging
        logger.debug(
            f"{self.agent_type} create tests raw result (length={len(result) if result else 0}):\n{result}\n============================"
        )

        return {"content": result, "status": "success"}


class ArchitectAgent(AgentInterface):
    """Architect agent focusing on system design and architecture."""

    def __init__(self, use_claude_code: bool | None = None):
        factory = CodingPersonas(use_claude_code=use_claude_code)
        super().__init__(factory.architect, "architect")

    def _build_analysis_prompt(self, context: dict[str, Any], task_spec: str) -> str:
        codebase_analysis_path = context.get("codebase_analysis_path")
        if not codebase_analysis_path:
            # Fallback to absolute path if not provided in context
            from pathlib import Path

            codebase_analysis_path = str(
                (Path.cwd() / ".workflow/codebase_analysis.md").resolve()
            )

        # Get repo path for direct file access
        repo_path = context.get("repo_path", "/Users/mstriebeck/Code/github-agent")

        prompt = f"""TASK FOCUS: System architecture and design patterns analysis.

TASK SPECIFICATION:
{task_spec}

STEP 1: Read the codebase analysis file at: {codebase_analysis_path}
STEP 2: If the analysis file is incomplete or empty, explore the codebase directly:
   - Use LS tool on: {repo_path}
   - Read the main Python files you discover
   - Understand the module structure and patterns
STEP 3: Understand the existing architecture and patterns
STEP 4: Provide specific architectural guidance for this feature

## ARCHITECTURE ANALYSIS REQUIREMENTS:

**READ THE CODEBASE ANALYSIS FILE, then provide:**

### 1. Existing System Integration
- Which specific modules/tools will need to be modified for this feature?
- Which existing classes or patterns can be reused or extended?
- What interfaces or APIs does this feature need to integrate with?

### 2. Data Architecture
- How should data be persisted (database, files, memory)?
- What data structures are needed?
- Which existing storage/persistence patterns should be followed?

### 3. Implementation Plan
- Which specific files need to be created or modified?
- What new classes/methods are needed?
- How will this integrate with the existing system?

### 4. Architecture Patterns
- Which existing design patterns from the codebase apply?
- What error handling approach should be used?
- How should configuration be managed?

## REQUIREMENTS:
- Reference specific files, classes, and methods from the existing codebase
- Explain HOW this feature fits into the current architecture
- Be concrete: "modify github_tools.py line X" not "integrate with GitHub API"
- Base all decisions on patterns already established in the codebase"""

        return prompt

    def _build_peer_review_prompt(
        self, peer_analyses: dict[str, str], context: dict[str, Any]
    ) -> str:
        codebase_analysis_path = context.get("codebase_analysis_path")
        if not codebase_analysis_path:
            # Fallback to absolute path if not provided in context
            from pathlib import Path

            codebase_analysis_path = str(
                (Path.cwd() / ".workflow/codebase_analysis.md").resolve()
            )
        prompt = f"""TASK FOCUS: Architectural consistency and design patterns review.

CODEBASE ANALYSIS:
Read the codebase analysis at: {codebase_analysis_path}

FEATURE: {context.get('feature_spec', {}).get('name', 'Unknown')}

PEER ANALYSES TO REVIEW:
"""
        for agent_type, analysis in peer_analyses.items():
            if agent_type != self.agent_type:
                prompt += f"\n--- {agent_type.replace('_', ' ').title()} Analysis ---\n{analysis}\n"

        prompt += """
REVIEW REQUIREMENTS (BE SPECIFIC - REFERENCE ACTUAL CODE):
1. Architectural Alignment
   - Do proposals follow the EXISTING patterns in the codebase? (name them)
   - Which SPECIFIC modules/classes conflict with current architecture?
   - What CONCRETE risks exist based on the current implementation?

2. System Integration
   - Name SPECIFIC existing systems/APIs that need integration
   - Which EXACT interfaces are missing from proposals?
   - What dependencies from requirements.txt/package.json are needed?

3. Pattern Consistency
   - Do proposals match CURRENT naming conventions? (give examples)
   - Are they using the SAME error handling as existing code?
   - Do they follow the EXISTING testing patterns?

4. Specific Improvements
   - What EXACT classes/methods need modification?
   - Which SPECIFIC files should be created/updated?
   - What CONCRETE alternatives align better with current code?

Ground all feedback in the actual codebase. Reference specific files and patterns.
Avoid generic advice - every point must be specific to this codebase and implementation."""

        return prompt

    def _build_feedback_response_prompt(
        self, feedback_items: list[dict], context: dict[str, Any]
    ) -> str:
        prompt = f"""TASK FOCUS: Incorporating human feedback from architectural perspective.

ORIGINAL ANALYSIS CONTEXT:
Feature: {context.get('feature_spec', {}).get('name', 'Unknown')}
Codebase: {context.get('codebase_summary', 'No summary available')}

HUMAN FEEDBACK TO ADDRESS:
"""
        for item in feedback_items:
            prompt += f"\n--- Feedback from {item['author']} ---\n"
            if item.get("file_path"):
                prompt += f"File: {item['file_path']}\n"
            prompt += f"Comment: {item['content']}\n"

        prompt += """
RESPONSE REQUIREMENTS:
1. Address each feedback item from an architectural perspective
2. Update your analysis to incorporate valid concerns
3. Explain how the feedback impacts system design
4. Propose architectural solutions to address the feedback
5. Maintain consistency with architectural principles

Please provide an updated architectural analysis that addresses the human feedback while maintaining architectural integrity.
Ground all responses in specific code patterns and implementations - avoid generic architectural advice."""

        return prompt


class DeveloperAgent(AgentInterface):
    """Developer agent focusing on implementation approach."""

    def __init__(self, use_claude_code: bool | None = None):
        factory = CodingPersonas(use_claude_code=use_claude_code)
        super().__init__(factory.fast_coder, "developer")

    def _build_analysis_prompt(self, context: dict[str, Any], task_spec: str) -> str:
        codebase_analysis_path = context.get("codebase_analysis_path")
        if not codebase_analysis_path:
            # Fallback to absolute path if not provided in context
            from pathlib import Path

            codebase_analysis_path = str(
                (Path.cwd() / ".workflow/codebase_analysis.md").resolve()
            )
        prompt = f"""TASK FOCUS: Implementation approach analysis - HOW to solve the problem, not generating actual code.

TASK SPECIFICATION:
{task_spec}

CODEBASE ANALYSIS:
Read the codebase analysis at: {codebase_analysis_path}

## IMPLEMENTATION ANALYSIS REQUIREMENTS (ANALYZE, DON'T CODE):

### 1. Implementation Strategy Analysis
- **Architecture Fit**: How does this feature align with existing patterns (CodebaseTools, RepositoryManager, etc.)?
- **File Organization**: Which directories should contain the new functionality based on current structure?
- **Class Design**: What classes are needed and how do they fit existing abstractions?
- **Integration Points**: Where does this feature hook into existing workflows?

### 2. Existing Code Leverage Analysis
- **Reusable Components**: Which existing classes can be extended or composed?
- **Utility Functions**: What helper functions already exist that can be reused?
- **Patterns to Follow**: Which existing implementation patterns should be mirrored?
- **Dependencies**: What existing dependencies can be leveraged vs. new ones needed?

### 3. Implementation Complexity Assessment
- **Core vs. Optional**: What is the minimal viable implementation?
- **Complexity Ranking**: Which parts are straightforward vs. challenging?
- **Risk Areas**: Where are the most likely implementation pitfalls?
- **Validation Strategy**: How to prove the approach works incrementally?

### 4. Technical Decision Analysis
- **Data Flow**: How will data move through the system?
- **Error Handling**: What failure modes need to be considered?
- **Performance**: What are the performance implications?
- **Configuration**: What configuration options are needed?

### 5. Development Approach Recommendation
- **Implementation Order**: What sequence minimizes risk and enables quick feedback?
- **Testing Strategy**: How to validate each component as it's built?
- **MVP Definition**: What constitutes a working proof of concept?

FOCUS ON ANALYSIS AND REASONING, NOT CODE GENERATION. Explain your thinking and approach.
Avoid generic implementation advice - base all recommendations on the actual codebase patterns and architecture."""

        return prompt

    def _build_peer_review_prompt(
        self, peer_analyses: dict[str, str], context: dict[str, Any]
    ) -> str:
        prompt = f"""TASK FOCUS: Fast Developer perspective on peer analyses review.

FEATURE: {context.get('feature_spec', {}).get('name', 'Unknown')}

PEER ANALYSES TO REVIEW:
"""
        for agent_type, analysis in peer_analyses.items():
            if agent_type != self.agent_type:
                prompt += f"\n--- {agent_type.replace('_', ' ').title()} Analysis ---\n{analysis}\n"

        prompt += """
REVIEW REQUIREMENTS:
1. Implementation Feasibility
   - Are the proposed approaches realistic to implement quickly?
   - What would be the fastest path to a working solution?
   - Which ideas can be built iteratively?

2. Technical Practicality
   - Do the analyses consider available libraries and tools?
   - Are there simpler alternatives to complex proposals?
   - What existing code can be leveraged?

3. Development Speed
   - Which approaches would take longest to implement?
   - Where are the team likely to get stuck?
   - What can be prototyped first for validation?

4. Iterative Opportunities
   - How can we break this into smaller deliverable chunks?
   - What's the minimum viable version?
   - Where do you agree/disagree with the complexity levels?

Focus on practical implementation concerns specific to this codebase and getting working software quickly.
Avoid generic development advice - reference specific existing tools, patterns, and implementations."""

        return prompt

    def _build_feedback_response_prompt(
        self, feedback_items: list[dict], context: dict[str, Any]
    ) -> str:
        prompt = f"""TASK FOCUS: Fast Developer perspective on incorporating human feedback.

ORIGINAL ANALYSIS CONTEXT:
Feature: {context.get('feature_spec', {}).get('name', 'Unknown')}
Codebase: {context.get('codebase_summary', 'No summary available')}

HUMAN FEEDBACK TO ADDRESS:
"""
        for item in feedback_items:
            prompt += f"\n--- Feedback from {item['author']} ---\n"
            if item.get("file_path"):
                prompt += f"File: {item['file_path']}\n"
            prompt += f"Comment: {item['content']}\n"

        prompt += """
RESPONSE REQUIREMENTS:
1. Address feedback with practical implementation solutions
2. Update your approach to incorporate the human input
3. Maintain focus on rapid iteration and working software
4. Propose concrete next steps that address the concerns
5. Keep solutions simple and implementable

Please provide an updated implementation analysis that addresses the human feedback while maintaining focus on getting working software quickly.
Base all responses on specific existing code patterns and tools - avoid generic development suggestions."""

        return prompt


class SeniorEngineerAgent(AgentInterface):
    """Senior engineer agent focusing on code quality and maintainability."""

    def __init__(self, use_claude_code: bool | None = None):
        factory = CodingPersonas(use_claude_code=use_claude_code)
        super().__init__(factory.senior_engineer, "senior_engineer")

    def _build_analysis_prompt(self, context: dict[str, Any], task_spec: str) -> str:
        codebase_analysis_path = context.get("codebase_analysis_path")
        if not codebase_analysis_path:
            # Fallback to absolute path if not provided in context
            from pathlib import Path

            codebase_analysis_path = str(
                (Path.cwd() / ".workflow/codebase_analysis.md").resolve()
            )
        prompt = f"""TASK FOCUS: Code quality and maintainability analysis.

TASK SPECIFICATION:
{task_spec}

CODEBASE ANALYSIS:
Read the codebase analysis at: {codebase_analysis_path}

## CODE QUALITY ANALYSIS REQUIREMENTS (BE SPECIFIC):

### 1. Code Organization and Structure
- Which EXACT existing classes demonstrate good patterns to follow?
- What are the SPECIFIC naming conventions used (give examples from code)?
- Name the EXACT file structure patterns that should be maintained
- List SPECIFIC methods that exemplify clean code in the current codebase

### 2. Technical Debt and Refactoring
- Which SPECIFIC existing files need refactoring before adding this feature?
- Name the EXACT code smells present in related existing code
- List the SPECIFIC methods that should be extracted or simplified
- What are the PRECISE dependencies that create coupling issues?

### 3. Design Pattern Implementation
- Which SPECIFIC design patterns are already used in the codebase? (give file examples)
- What are the EXACT patterns that should be applied to this feature?
- Name the SPECIFIC interfaces or base classes that should be created/extended
- List the EXACT abstractions that would improve maintainability

### 4. Error Handling and Logging
- What are the EXACT error handling patterns used in the existing code?
- Which SPECIFIC exception classes are already defined that should be used?
- Name the EXACT logging patterns and formats used in the codebase
- List the SPECIFIC error scenarios this feature needs to handle

### 5. Maintainability Improvements
- Which SPECIFIC existing code would benefit from refactoring alongside this feature?
- What are the EXACT documentation standards used in the codebase?
- Name the SPECIFIC code review checklist items this feature should meet
- List the EXACT future extension points that should be designed in

NO GENERIC ADVICE. Reference specific classes, methods, and file patterns from the existing codebase.
Avoid theoretical principles - ground all recommendations in the actual code structure and quality standards already established."""

        return prompt

    def _build_peer_review_prompt(
        self, peer_analyses: dict[str, str], context: dict[str, Any]
    ) -> str:
        prompt = f"""TASK FOCUS: Senior Engineer perspective on peer analyses review.

FEATURE: {context.get('feature_spec', {}).get('name', 'Unknown')}

PEER ANALYSES TO REVIEW:
"""
        for agent_type, analysis in peer_analyses.items():
            if agent_type != self.agent_type:
                prompt += f"\n--- {agent_type.replace('_', ' ').title()} Analysis ---\n{analysis}\n"

        prompt += """
REVIEW REQUIREMENTS:
1. Code Quality Assessment
   - Do the approaches promote clean, maintainable code?
   - Are there opportunities for better abstractions?
   - What code quality concerns do you see?

2. Long-term Maintainability
   - How will these approaches age over time?
   - What technical debt might be created?
   - Are the solutions too complex or too simple?

3. Best Practices
   - Are the analyses following established patterns?
   - What industry best practices should be applied?
   - Where do you see opportunities for improvement?

4. Team and Codebase Impact
   - How will these changes affect other developers?
   - Are the solutions consistent with existing code?
   - What refactoring opportunities exist?

Focus on long-term code health and maintainability specific to this codebase.
Reference actual existing patterns and quality standards - avoid generic engineering principles."""

        return prompt

    def _build_feedback_response_prompt(
        self, feedback_items: list[dict], context: dict[str, Any]
    ) -> str:
        prompt = f"""TASK FOCUS: Senior Engineer perspective on incorporating human feedback.

ORIGINAL ANALYSIS CONTEXT:
Feature: {context.get('feature_spec', {}).get('name', 'Unknown')}
Codebase: {context.get('codebase_summary', 'No summary available')}

HUMAN FEEDBACK TO ADDRESS:
"""
        for item in feedback_items:
            prompt += f"\n--- Feedback from {item['author']} ---\n"
            if item.get("file_path"):
                prompt += f"File: {item['file_path']}\n"
            prompt += f"Comment: {item['content']}\n"

        prompt += """
RESPONSE REQUIREMENTS:
1. Address feedback with focus on code quality and maintainability
2. Update analysis to incorporate engineering best practices
3. Consider long-term implications of the feedback
4. Propose solutions that improve overall codebase health
5. Balance immediate needs with long-term maintainability

Please provide an updated analysis that addresses the human feedback while maintaining focus on code quality and long-term maintainability.
Reference specific existing code quality patterns and maintainability practices already in use - avoid generic engineering advice."""

        return prompt


class TesterAgent(AgentInterface):
    """Tester agent focusing on testing strategy and quality assurance."""

    def __init__(self, use_claude_code: bool | None = None):
        factory = CodingPersonas(use_claude_code=use_claude_code)
        super().__init__(factory.test_focused_coder, "tester")

    def _build_analysis_prompt(self, context: dict[str, Any], task_spec: str) -> str:
        codebase_analysis_path = context.get("codebase_analysis_path")
        if not codebase_analysis_path:
            # Fallback to absolute path if not provided in context
            from pathlib import Path

            codebase_analysis_path = str(
                (Path.cwd() / ".workflow/codebase_analysis.md").resolve()
            )
        prompt = f"""TASK FOCUS: Testing strategy and comprehensive test specifications.

TASK SPECIFICATION:
{task_spec}

CODEBASE ANALYSIS:
Read the codebase analysis at: {codebase_analysis_path}

## TESTING ANALYSIS REQUIREMENTS:

### 1. Test Strategy Analysis
- **Testing Approach**: What testing strategy fits this feature based on existing patterns?
- **Test Categories**: Which types of tests are needed (unit, integration, end-to-end)?
- **Mock Strategy**: Which components need mocking and which existing mock patterns to follow?
- **Test Organization**: How should tests be organized following existing test structure?

### 2. Required Test Files
- **Unit Test Files**: Which specific test files need to be created (exact filenames)?
- **Integration Test Files**: What integration tests are needed for component interactions?
- **Mock Files**: Which mock classes need to be created in `tests/mocks/` following existing patterns?
- **Test Dependencies**: What existing test infrastructure can be reused?

### 3. Specific Test Scenarios
- **Happy Path Tests**: What are the main success scenarios that need testing?
- **Error Handling Tests**: Which failure modes and error conditions must be tested?
- **Edge Cases**: What boundary conditions and edge cases need coverage?
- **Integration Scenarios**: How do components interact and what needs testing?

### 4. Mock Specifications
- **Mock Classes Needed**: Which specific mock classes should be created?
- **Mock Methods**: What methods do these mocks need to implement?
- **Mock Behaviors**: What should these mocks return for different test scenarios?
- **Existing Mocks**: Which existing mocks from `tests/mocks/` can be reused?

### 5. Test Implementation Details
- **Test Method Names**: What specific test methods need to be written?
- **Test Data**: What specific input data and expected outputs are needed?
- **Assertions**: What specific assertions should be made in each test?
- **Coverage Goals**: What coverage targets should be achieved?

FOCUS ON PRACTICAL TESTING. Base all recommendations on existing test patterns in the codebase.
Avoid generic testing advice - reference specific test files and mock implementations that already exist."""

        return prompt

    def _build_peer_review_prompt(
        self, peer_analyses: dict[str, str], context: dict[str, Any]
    ) -> str:
        prompt = f"""TASK FOCUS: Test-Focused Developer perspective on peer analyses review.

FEATURE: {context.get('feature_spec', {}).get('name', 'Unknown')}

PEER ANALYSES TO REVIEW:
"""
        for agent_type, analysis in peer_analyses.items():
            if agent_type != self.agent_type:
                prompt += f"\n--- {agent_type.replace('_', ' ').title()} Analysis ---\n{analysis}\n"

        prompt += """
REVIEW REQUIREMENTS:
1. Testing Coverage Assessment
   - Do the proposed approaches consider comprehensive testing?
   - What testing gaps do you see in the analyses?
   - Are edge cases and error scenarios addressed?

2. Quality Assurance
   - How testable are the proposed implementations?
   - What quality risks are present?
   - Are there opportunities for better test-driven development?

3. Testing Strategy Alignment
   - Do the approaches support good testing practices?
   - What testing frameworks and tools should be used?
   - How can we ensure high test coverage?

4. Risk Assessment
   - What are the biggest quality risks in these approaches?
   - Where might bugs be introduced?
   - What testing should be prioritized?

Focus on ensuring comprehensive testing and quality assurance specific to this codebase's testing framework and patterns.
Reference actual existing test structures and avoid generic testing advice."""

        return prompt

    def _build_feedback_response_prompt(
        self, feedback_items: list[dict], context: dict[str, Any]
    ) -> str:
        prompt = f"""TASK FOCUS: Test-Focused Developer perspective on incorporating human feedback.

ORIGINAL ANALYSIS CONTEXT:
Feature: {context.get('feature_spec', {}).get('name', 'Unknown')}
Codebase: {context.get('codebase_summary', 'No summary available')}

HUMAN FEEDBACK TO ADDRESS:
"""
        for item in feedback_items:
            prompt += f"\n--- Feedback from {item['author']} ---\n"
            if item.get("file_path"):
                prompt += f"File: {item['file_path']}\n"
            prompt += f"Comment: {item['content']}\n"

        prompt += """
RESPONSE REQUIREMENTS:
1. Address feedback with comprehensive testing considerations
2. Update testing strategy to incorporate human concerns
3. Identify new test scenarios based on the feedback
4. Propose quality assurance measures for the feedback points
5. Maintain focus on comprehensive test coverage

Please provide an updated testing analysis that addresses the human feedback while maintaining focus on comprehensive testing and quality assurance.
Reference specific existing test patterns and frameworks already in use - avoid generic testing methodologies."""

        return prompt
