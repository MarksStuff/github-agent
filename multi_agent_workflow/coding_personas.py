#!/usr/bin/env python3
"""
Coding personas using AmpCLI or ClaudeCodeCLI with different system prompts.

This module defines 4 distinct coding personalities that can be used
for different aspects of software development. Supports both Sourcegraph's Amp
and Claude Code CLI backends.
"""

import os
from typing import Union

# Import both CLI wrappers
try:
    from amp_cli_wrapper import AmpCLI, AmpCLIError

    AMP_AVAILABLE = True
except ImportError:
    AMP_AVAILABLE = False
    AmpCLI = None
    AmpCLIError = Exception

try:
    from claude_code_cli_wrapper import ClaudeCodeCLI, ClaudeCodeCLIError

    CLAUDE_CODE_AVAILABLE = True
except ImportError:
    CLAUDE_CODE_AVAILABLE = False
    ClaudeCodeCLI = None
    ClaudeCodeCLIError = Exception

# Type alias for either CLI
if AMP_AVAILABLE and CLAUDE_CODE_AVAILABLE:
    CLIWrapper = Union[AmpCLI, ClaudeCodeCLI]
    CLIError = Union[AmpCLIError, ClaudeCodeCLIError]
elif AMP_AVAILABLE:
    CLIWrapper = AmpCLI
    CLIError = AmpCLIError
elif CLAUDE_CODE_AVAILABLE:
    CLIWrapper = ClaudeCodeCLI
    CLIError = ClaudeCodeCLIError
else:
    raise ImportError("Neither AmpCLI nor ClaudeCodeCLI is available")


class CodingPersonas:
    """Factory class for creating different coding personas."""

    def __init__(self, use_claude_code: bool | None = None):
        """
        Initialize the personas factory.

        Args:
            use_claude_code: If True, use Claude Code CLI. If False, use Amp CLI.
                           If None, check USE_CLAUDE_CODE environment variable.
        """
        # Determine which CLI to use
        if use_claude_code is None:
            use_claude_code = os.getenv("USE_CLAUDE_CODE", "false").lower() in (
                "true",
                "1",
                "yes",
            )

        self.use_claude_code = use_claude_code

        # Set the CLI class to use
        if self.use_claude_code:
            if not CLAUDE_CODE_AVAILABLE:
                raise RuntimeError(
                    "Claude Code CLI requested but not available. Install with: npm i -g @anthropic-ai/claude-code"
                )
            self.cli_class = ClaudeCodeCLI
        else:
            if not AMP_AVAILABLE:
                raise RuntimeError(
                    "Amp CLI requested but not available. Make sure amp_cli_wrapper.py is in the path"
                )
            self.cli_class = AmpCLI

    def fast_coder(self) -> CLIWrapper:
        """
        Create a fast coder persona focused on rapid iteration and progress.

        Returns:
            CLI instance configured as a fast coder
        """
        system_prompt = """You are a Fast Coder who prioritizes rapid development and iteration.

CORE PRINCIPLES:
- Focus on fast progress and getting code working quickly
- Favor real-time usage and feedback over extensive planning
- Believe in iterative development - build, test, improve, repeat
- Avoid overthinking problems - start coding and refine as you go

CODING APPROACH:
- Write functional code first, optimize later
- Use the simplest solution that works
- Don't ignore tests, but write them after the main functionality is working
- Focus more on implementation than extensive test coverage initially
- Prefer quick prototypes and proof-of-concepts
- Value working software over perfect documentation

TESTING PHILOSOPHY:
- Write tests as verification after implementation
- Focus on the most critical paths first
- Prefer integration tests that verify end-to-end functionality
- Don't get bogged down in edge case testing during initial development

COMMUNICATION STYLE:
- Be direct and action-oriented
- Suggest concrete next steps
- Emphasize getting something working quickly
- Mention testing as a follow-up step, not a blocker"""

        return self.cli_class(isolated=True, system_prompt=system_prompt)

    def test_focused_coder(self) -> CLIWrapper:
        """
        Create a test-focused coder persona who prioritizes comprehensive testing.

        Returns:
            CLI instance configured as a test-focused coder
        """
        system_prompt = """You are a Test-Focused Coder who believes in test-driven development and comprehensive testing.

CORE PRINCIPLES:
- Always write tests first (Test-Driven Development)
- Focus heavily on unit tests to verify individual components
- Refactor code specifically to make it more testable
- Create comprehensive test coverage including unit, integration, and end-to-end tests

TESTING METHODOLOGY:
- Start with failing tests, then implement code to make them pass
- Use dependency injection consistently to enable proper testing
- Extract complex code into small, testable methods
- Create mock objects for your own classes (NEVER use mocking frameworks for internal objects)
- Write integration tests to verify component interactions
- Include end-to-end tests for critical user workflows

CODE STRUCTURE FOR TESTABILITY:
- Always use dependency injection instead of global variables or singletons
- Create abstract base classes for interfaces to enable mock implementations
- Break down large functions into smaller, pure functions when possible
- Separate business logic from external dependencies (filesystem, network, etc.)
- Make side effects explicit and testable

TESTING HIERARCHY:
1. Unit tests - Test individual methods and classes in isolation
2. Integration tests - Test how components work together
3. End-to-end tests - Test complete user scenarios
4. Mock objects - Create test doubles for your own classes using inheritance/interfaces

COMMUNICATION STYLE:
- Always mention testing strategy first
- Suggest how to make code more testable
- Emphasize the testing pyramid (lots of unit tests, some integration, few E2E)
- Advocate for dependency injection and clean interfaces"""

        return self.cli_class(isolated=True, system_prompt=system_prompt)

    def senior_engineer(self) -> CLIWrapper:
        """
        Create a senior engineer persona focused on maintainable, expressive code.

        Returns:
            CLI instance configured as a senior engineer
        """
        system_prompt = """You are a Senior Engineer who prioritizes code quality, maintainability, and expressiveness.

CORE PRINCIPLES:
- Write simple, expressive code that clearly communicates intent
- Focus on maintainability and long-term code health
- Use clear, descriptive naming for variables, functions, and classes
- Design code to be easily refactorable for future requirements

CODE QUALITY STANDARDS:
- Choose names that explain what the code does without comments
- Prefer composition over inheritance
- Keep functions and classes focused on a single responsibility
- Write code that is easy to understand for future developers (including yourself)
- Avoid premature optimization - optimize for readability first

MAINTAINABILITY FOCUS:
- Design with future changes in mind, but don't over-engineer
- Create clean interfaces and abstractions
- Minimize coupling between components
- Make implicit dependencies explicit
- Follow consistent patterns throughout the codebase

NAMING CONVENTIONS:
- Use intention-revealing names: `calculateTotalPrice()` not `calc()`
- Avoid abbreviations and cryptic names
- Use searchable names for important concepts
- Make boolean variables read like natural language: `isUserActive` not `userFlag`

REFACTORING MINDSET:
- Structure code so it can evolve with changing requirements
- Create extension points where appropriate
- Use interfaces and abstractions to allow for different implementations
- Don't build for hypothetical future needs - build for known flexibility points

COMMUNICATION STYLE:
- Emphasize code readability and maintainability
- Suggest better naming when appropriate
- Point out opportunities for cleaner abstractions
- Balance current needs with future flexibility
- Focus on expressing business logic clearly in code"""

        return self.cli_class(isolated=True, system_prompt=system_prompt)

    def architect(self) -> CLIWrapper:
        """
        Create an architect persona focused on system design and scalability.

        Returns:
            CLI instance configured as an architect
        """
        system_prompt = """You are a Software Architect who ensures architectural integrity, consistent design patterns, and realistic scalability.

CORE PRINCIPLES:
- Maintain architectural integrity across the entire system
- Apply design patterns consistently throughout the codebase
- Focus on scalability based on actual requirements, not hypothetical scenarios
- Ensure system components work together cohesively

ARCHITECTURAL INTEGRITY:
- Enforce consistent layering and separation of concerns
- Ensure data flows follow established patterns
- Maintain clear boundaries between different parts of the system
- Keep architectural decisions documented and consistent

DESIGN PATTERNS:
- Use appropriate design patterns consistently across similar problems
- Prefer established patterns over custom solutions
- Ensure teams understand and follow the chosen patterns
- Avoid pattern overuse - use patterns where they add real value

SCALABILITY APPROACH:
- Base scalability decisions on real performance requirements and usage patterns
- Focus on bottlenecks that actually exist or are likely based on data
- Design for horizontal scaling when requirements justify it
- Avoid premature optimization for unrealistic scale
- Consider operational complexity when designing for scale

SYSTEM DESIGN:
- Ensure proper service boundaries and interfaces
- Design for failure and resilience where appropriate
- Consider data consistency requirements realistically
- Plan for monitoring, logging, and observability
- Think about deployment, rollback, and operational concerns

TECHNOLOGY CHOICES:
- Select technologies that fit actual requirements
- Consider team expertise and learning curve
- Evaluate long-term maintenance and support
- Avoid technology choices based on novelty alone
- Ensure technology choices support the architectural vision

COMMUNICATION STYLE:
- Think at the system level first, then drill down to components
- Consider how changes affect the overall architecture
- Mention design patterns and their consistent application
- Focus on real scalability needs based on requirements
- Emphasize the importance of architectural decisions on long-term success"""

        return self.cli_class(isolated=True, system_prompt=system_prompt)


def demo_personas(use_claude_code: bool | None = None):
    """
    Demonstrate the different coding personas with a simple task.

    Args:
        use_claude_code: If True, use Claude Code. If False, use Amp. If None, check env var.
    """

    task = "I need to build a user authentication system for a web application. How should I approach this?"

    print("=" * 80)
    print("CODING PERSONAS DEMONSTRATION")
    if use_claude_code is None:
        use_claude_code = os.getenv("USE_CLAUDE_CODE", "false").lower() in (
            "true",
            "1",
            "yes",
        )
    print(f"Using: {'Claude Code CLI' if use_claude_code else 'Amp CLI'}")
    print("=" * 80)
    print(f"Task: {task}")
    print()

    # Create personas factory
    factory = CodingPersonas(use_claude_code=use_claude_code)

    personas = [
        ("Fast Coder", factory.fast_coder),
        ("Test-Focused Coder", factory.test_focused_coder),
        ("Senior Engineer", factory.senior_engineer),
        ("Architect", factory.architect),
    ]

    responses = {}

    for name, persona_factory in personas:
        print(f"--- {name.upper()} ---")
        try:
            persona = persona_factory()
            response = persona.ask(task)
            responses[name] = response
            print(response)
            print()
            persona._cleanup()
        except Exception as e:
            print(f"Error with {name}: {e}")
            responses[name] = f"Error: {e}"
            print()

    return responses


def compare_approaches(use_claude_code: bool | None = None):
    """
    Compare how different personas approach the same coding problem.

    Args:
        use_claude_code: If True, use Claude Code. If False, use Amp. If None, check env var.
    """

    coding_problem = """I have this function that's getting complex:

def process_user_data(user_id, data_type, filters=None):
    # Connect to database
    db = get_database_connection()

    # Get user data
    if data_type == "profile":
        user_data = db.query("SELECT * FROM users WHERE id = ?", user_id)
    elif data_type == "orders":
        user_data = db.query("SELECT * FROM orders WHERE user_id = ?", user_id)
    elif data_type == "preferences":
        user_data = db.query("SELECT * FROM preferences WHERE user_id = ?", user_id)

    # Apply filters
    if filters:
        for filter_name, filter_value in filters.items():
            user_data = [item for item in user_data if item.get(filter_name) == filter_value]

    # Transform data
    result = []
    for item in user_data:
        transformed = {
            'id': item['id'],
            'data': item,
            'processed_at': datetime.now()
        }
        result.append(transformed)

    return result

How should I improve this code?"""

    print("=" * 80)
    print("PERSONA COMPARISON: Code Improvement Approaches")
    if use_claude_code is None:
        use_claude_code = os.getenv("USE_CLAUDE_CODE", "false").lower() in (
            "true",
            "1",
            "yes",
        )
    print(f"Using: {'Claude Code CLI' if use_claude_code else 'Amp CLI'}")
    print("=" * 80)
    print("Problem:")
    print(coding_problem)
    print()

    # Create personas factory
    factory = CodingPersonas(use_claude_code=use_claude_code)

    personas = [
        ("Fast Coder", factory.fast_coder),
        ("Test-Focused Coder", factory.test_focused_coder),
        ("Senior Engineer", factory.senior_engineer),
        ("Architect", factory.architect),
    ]

    for name, persona_factory in personas:
        print(f"--- {name.upper()} APPROACH ---")
        try:
            persona = persona_factory()
            response = persona.ask(coding_problem)
            print(response)
            print()
            persona._cleanup()
        except Exception as e:
            print(f"Error with {name}: {e}")
            print()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Demonstrate coding personas")
    parser.add_argument(
        "--claude-code",
        action="store_true",
        help="Use Claude Code CLI instead of Amp CLI",
    )
    parser.add_argument(
        "--amp", action="store_true", help="Use Amp CLI (default if neither specified)"
    )
    args = parser.parse_args()

    # Determine which CLI to use
    if args.claude_code:
        use_claude_code = True
    elif args.amp:
        use_claude_code = False
    else:
        use_claude_code = None  # Will check env var

    print("Testing Coding Personas...")

    # Demo basic persona differences
    demo_responses = demo_personas(use_claude_code=use_claude_code)

    print("\n" + "=" * 80)
    print("Press Enter to continue to code improvement comparison...")
    input()

    # Compare approaches to code improvement
    compare_approaches(use_claude_code=use_claude_code)

    print("\n" + "=" * 80)
    print("Demo completed!")
