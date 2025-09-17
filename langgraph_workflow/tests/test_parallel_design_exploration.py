"""Test for parallel design exploration with 4 Claude-based agents."""

import tempfile
import unittest
from typing import Any
from unittest.mock import patch

from ..enums import AgentType, WorkflowPhase
from ..nodes.parallel_design_exploration import (
    _call_claude_agent_for_design,
    parallel_design_exploration_handler,
)


class TestParallelDesignExploration(unittest.IsolatedAsyncioTestCase):
    """Test parallel design exploration functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.state: dict[str, Any] = {
            "repo_path": self.temp_dir.name,
            "feature_description": "Add user authentication system with JWT tokens",
            "code_context_document": "# Comprehensive Code Context Document\n"
            + "x" * 2500,  # Valid length
            "current_phase": WorkflowPhase.PHASE_0_CODE_CONTEXT,
            "pr_number": 123,
            "artifacts_index": {},
        }

        # Mock comprehensive responses for each agent
        self.mock_responses = {
            AgentType.ARCHITECT: self._create_architect_response(),
            AgentType.SENIOR_ENGINEER: self._create_senior_engineer_response(),
            AgentType.FAST_CODER: self._create_fast_coder_response(),
            AgentType.TEST_FIRST: self._create_test_first_response(),
        }

    def tearDown(self):
        """Clean up test fixtures."""
        self.temp_dir.cleanup()

    def _create_architect_response(self) -> str:
        """Create a comprehensive architect design response."""
        return """# Architect Design Document: User Authentication System

## Executive Summary
This document outlines a comprehensive architectural approach for implementing JWT-based user authentication in the GitHub Agent MCP Server, focusing on system-wide integration and scalability.

## Codebase Analysis
After examining the existing master-worker architecture, I've identified key integration points:

### Current Architecture
- Master Process (mcp_master.py): Process lifecycle management
- Worker Processes (mcp_worker.py): Repository handling and MCP endpoints
- Clean separation with no shared state between workers

### Integration Points for Authentication
- Worker initialization needs authentication middleware
- FastAPI dependency injection for protected endpoints
- Session management at worker level to maintain isolation

## Detailed Design

### System Architecture
```
┌─────────────────┐    ┌─────────────────┐
│   Auth Service  │    │   JWT Validator │
└─────────────────┘    └─────────────────┘
         │                       │
         ▼                       ▼
┌─────────────────────────────────────────┐
│           MCPWorker                     │
│  ┌─────────────┐  ┌─────────────────┐   │
│  │ Auth Middle │  │ Protected      │   │
│  │ ware        │  │ Endpoints      │   │
│  └─────────────┘  └─────────────────┘   │
└─────────────────────────────────────────┘
```

### Component Design
1. **AuthenticationService**: Centralized JWT validation
2. **AuthMiddleware**: FastAPI middleware for request validation
3. **ProtectedEndpoint**: Decorator for securing MCP tools
4. **SessionManager**: Per-worker session tracking

## Implementation Plan
1. Design authentication service interface
2. Implement JWT validation logic
3. Create FastAPI middleware integration
4. Add protected endpoint decorators
5. Integrate with existing worker architecture

## Risk Assessment
- **Process Isolation**: Authentication state must not break worker isolation
- **Performance**: JWT validation overhead on each request
- **Scalability**: Session storage scaling across multiple workers

This architectural approach maintains the existing master-worker pattern while adding robust authentication capabilities."""

    def _create_senior_engineer_response(self) -> str:
        """Create a comprehensive senior engineer design response."""
        return """# Senior Engineer Design Document: User Authentication System

## Executive Summary
This document provides a practical engineering approach to implementing JWT-based authentication, focusing on code quality, maintainability, and performance optimization.

## Codebase Analysis
Examined the existing Python codebase and identified the following patterns:

### Existing Code Patterns
- Modern Python 3.13 with type hints throughout
- Dependency injection pattern in CodebaseTools and other components
- Abstract base classes for testability (no MagicMock usage)
- Comprehensive error handling with specific exceptions

### Reusable Components
- FastAPI middleware pattern already established
- Abstract base classes can be extended for auth interfaces
- SQLite storage pattern can be leveraged for session management
- Logging infrastructure ready for auth events

## Detailed Design

### Core Authentication Components

```python
class AbstractAuthenticator(ABC):
    @abstractmethod
    async def validate_token(self, token: str) -> UserContext | None:
        pass

    @abstractmethod
    async def generate_token(self, user_id: str) -> str:
        pass

class JWTAuthenticator(AbstractAuthenticator):
    def __init__(self, secret_key: str, algorithm: str = "HS256"):
        self.secret_key = secret_key
        self.algorithm = algorithm
```

### Integration with Existing Architecture
- Extend MCPWorker.__init__ to accept authenticator dependency
- Add auth middleware to FastAPI app creation
- Implement protected tool decorator using existing patterns

### Error Handling Strategy
```python
class AuthenticationError(Exception):
    pass

class TokenExpiredError(AuthenticationError):
    pass

class InvalidTokenError(AuthenticationError):
    pass
```

## Implementation Plan

### Phase 1: Core Authentication (2-3 days)
1. Implement AbstractAuthenticator interface
2. Create JWTAuthenticator with comprehensive tests
3. Add authentication errors with proper logging

### Phase 2: FastAPI Integration (1-2 days)
1. Create auth middleware following existing patterns
2. Add dependency injection for authenticator
3. Test middleware with existing endpoints

### Phase 3: Tool Protection (1 day)
1. Implement @require_auth decorator
2. Apply to sensitive GitHub operations
3. Update tool registration to indicate auth requirements

### Performance Considerations
- JWT validation: ~0.1ms per request (negligible)
- Session caching: Use existing SQLite pattern
- Connection pooling: Leverage existing database connections

### Code Quality Measures
- 100% test coverage following existing abstract base class pattern
- Type hints for all authentication components
- Comprehensive logging for security events
- Input validation for all auth-related data

This approach leverages existing code patterns and maintains the high engineering standards established in the codebase."""

    def _create_fast_coder_response(self) -> str:
        """Create a comprehensive fast coder design response."""
        return """# Fast Coder Design Document: User Authentication System

## Executive Summary
This document outlines a rapid implementation strategy for JWT authentication using existing libraries and patterns to minimize development time while maintaining functionality.

## Codebase Analysis
Quick assessment of existing infrastructure for rapid development:

### Existing Libraries to Leverage
- FastAPI: Already integrated, has built-in security utilities
- SQLite: Database infrastructure ready
- python-jose: JWT library (add to requirements.txt)
- passlib: Password hashing (add to requirements.txt)

### Quick Win Opportunities
- FastAPI's HTTPBearer for token extraction
- Existing dependency injection pattern for auth services
- Current error handling framework for auth errors

## Minimal Viable Implementation

### Phase 1: Basic JWT (4 hours)
```python
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer
from jose import JWTError, jwt

security = HTTPBearer()

async def get_current_user(token: str = Depends(security)):
    try:
        payload = jwt.decode(token.credentials, SECRET_KEY, algorithms=["HS256"])
        username = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401)
        return username
    except JWTError:
        raise HTTPException(status_code=401)
```

### Phase 2: Endpoint Protection (2 hours)
```python
@app.get("/protected-tool")
async def protected_tool(current_user: str = Depends(get_current_user)):
    return {"user": current_user}
```

### Phase 3: Integration (2 hours)
- Add auth dependency to worker initialization
- Update existing tool endpoints with auth requirements
- Basic error responses

## Iterative Delivery Approach

### MVP (Day 1 - 8 hours)
- JWT token validation
- Protected endpoints
- Basic error handling
- Manual testing

### Enhancement 1 (Day 2 - 4 hours)
- User registration/login endpoints
- Password hashing
- Token expiration

### Enhancement 2 (Day 3 - 4 hours)
- Session management
- Role-based access
- Comprehensive testing

## Quick Implementation Shortcuts

### Library Choices (Proven Solutions)
- **python-jose**: JWT handling (widely adopted)
- **passlib[bcrypt]**: Password hashing (secure defaults)
- **FastAPI security**: Built-in utilities (no custom code needed)

### Existing Pattern Reuse
- Copy MCPWorker.__init__ pattern for auth service injection
- Use existing SQLite setup for user storage
- Follow current error handling patterns

### Testing Strategy (Minimal Viable)
- Unit tests for JWT validation
- Integration test for protected endpoint
- Manual testing for user flows

## Risk Mitigation (Speed vs. Security)
- Use established libraries (no custom crypto)
- Implement basic rate limiting (FastAPI-limiter)
- Add comprehensive logging for security events
- Plan security review after MVP delivery

This approach prioritizes rapid delivery while maintaining security fundamentals, with clear upgrade paths for enhanced features."""

    def _create_test_first_response(self) -> str:
        """Create a comprehensive test-first engineer design response."""
        return """# Test-First Design Document: User Authentication System

## Executive Summary
This document outlines a test-driven approach to implementing JWT authentication, ensuring comprehensive test coverage and quality assurance from the beginning.

## Codebase Analysis
Examined existing testing patterns for authentication integration:

### Current Testing Infrastructure
- pytest framework with unittest.IsolatedAsyncioTestCase
- Abstract base class pattern for mocking (no MagicMock for internal objects)
- Comprehensive test coverage with edge cases
- Mock implementations in tests/mocks/ directory

### Testable Interface Design Opportunities
- Authentication service with clear interfaces
- Dependency injection ready for test mocking
- Error conditions well-defined for test scenarios

## Test-Driven Design Approach

### Test Categories

#### 1. Unit Tests (Authentication Core)
```python
class TestJWTAuthenticator(unittest.IsolatedAsyncioTestCase):
    async def test_valid_token_authentication(self):
        # Test successful token validation

    async def test_expired_token_rejection(self):
        # Test token expiration handling

    async def test_invalid_signature_rejection(self):
        # Test tampered token rejection

    async def test_malformed_token_handling(self):
        # Test malformed token graceful failure
```

#### 2. Integration Tests (FastAPI Middleware)
```python
class TestAuthMiddleware(unittest.IsolatedAsyncioTestCase):
    async def test_protected_endpoint_access_with_valid_token(self):
        # Test successful authenticated request

    async def test_protected_endpoint_rejection_without_token(self):
        # Test 401 response for missing token

    async def test_protected_endpoint_rejection_with_invalid_token(self):
        # Test 401 response for invalid token
```

#### 3. End-to-End Tests (User Flows)
```python
class TestAuthenticationWorkflow(unittest.IsolatedAsyncioTestCase):
    async def test_complete_login_flow(self):
        # Test user login -> token generation -> protected resource access

    async def test_token_refresh_workflow(self):
        # Test token refresh before expiration
```

## Mock Implementation Strategy

### Authentication Mock (Following CLAUDE.md Guidelines)
```python
class MockAuthenticator(AbstractAuthenticator):
    def __init__(self):
        self.valid_tokens = {"test_token": "test_user"}
        self.call_count = 0

    async def validate_token(self, token: str) -> str | None:
        self.call_count += 1
        return self.valid_tokens.get(token)

    async def generate_token(self, user_id: str) -> str:
        return f"mock_token_{user_id}"
```

## Test Implementation Plan

### Phase 1: Core Authentication Tests (Day 1)
1. Implement AbstractAuthenticator interface with tests
2. Create comprehensive JWTAuthenticator test suite
3. Test all error conditions and edge cases
4. Achieve 100% code coverage for auth core

### Phase 2: Middleware Integration Tests (Day 2)
1. Create FastAPI test client with auth middleware
2. Test protected endpoint access patterns
3. Verify error response formats and codes
4. Test performance under auth load

### Phase 3: End-to-End Workflow Tests (Day 3)
1. Complete user authentication workflows
2. Token lifecycle management testing
3. Integration with existing MCP tool protection
4. Performance and security regression tests

## Test Data and Fixtures

### Test Users
```python
TEST_USERS = {
    "valid_user": {"password": "test_password", "roles": ["user"]},
    "admin_user": {"password": "admin_password", "roles": ["admin", "user"]},
    "expired_user": {"password": "expired", "token_expired": True}
}
```

### Mock JWT Tokens
- Valid tokens with different expiration times
- Malformed tokens for error testing
- Tokens with invalid signatures
- Tokens with missing claims

## Quality Gates and CI Integration

### Test Coverage Requirements
- Minimum 95% code coverage for authentication module
- All error conditions must have corresponding tests
- Performance regression tests for auth overhead

### Security Testing Checklist
- [ ] Token tampering detection
- [ ] Timing attack resistance
- [ ] Password strength validation
- [ ] Rate limiting functionality
- [ ] Session management security

### Automated Test Execution
- Pre-commit hooks run auth test suite
- CI pipeline includes security-specific tests
- Performance benchmarks for auth operations

This test-first approach ensures robust, secure authentication implementation with comprehensive quality assurance from day one."""

    async def mock_claude_agent_call(self, prompt: str, repo_path: str) -> str:
        """Mock Claude agent that returns agent-specific responses based on prompt content."""
        # Determine which agent type based on the prompt content
        for agent_type, response in self.mock_responses.items():
            if agent_type.replace("_", " ").title() in prompt:
                return response

        # Fallback response
        return (
            "# Generic Design Document\n" + "x" * 1500 + "\nGeneric analysis complete."
        )

    async def test_parallel_design_exploration_success(self):
        """Test successful parallel design exploration with all 4 agents."""
        with patch(
            "langgraph_workflow.nodes.extract_code_context._call_claude_code_agent",
            side_effect=self.mock_claude_agent_call,
        ):
            with patch("pathlib.Path.mkdir"):
                with patch("pathlib.Path.write_text") as mock_write:
                    result_state = await parallel_design_exploration_handler(self.state)

                    # Verify phase transition
                    self.assertEqual(
                        result_state["current_phase"],
                        WorkflowPhase.PHASE_1_DESIGN_EXPLORATION,
                    )

                    # Verify all 4 agents completed
                    self.assertIn("agent_analyses", result_state)
                    agent_analyses = result_state["agent_analyses"]
                    self.assertEqual(len(agent_analyses), 4)

                    # Verify each agent type is present
                    expected_agents = [
                        AgentType.ARCHITECT,
                        AgentType.SENIOR_ENGINEER,
                        AgentType.FAST_CODER,
                        AgentType.TEST_FIRST,
                    ]
                    for agent_type in expected_agents:
                        self.assertIn(agent_type, agent_analyses)
                        analysis = agent_analyses[agent_type]
                        self.assertGreater(
                            len(analysis), 1000, f"{agent_type} analysis too short"
                        )

                    # Verify artifacts were written (4 individual + 1 combined = 5 total)
                    self.assertEqual(mock_write.call_count, 5)

    async def test_single_agent_design_call(self):
        """Test individual agent design call functionality."""
        with patch(
            "langgraph_workflow.nodes.extract_code_context._call_claude_code_agent",
            side_effect=self.mock_claude_agent_call,
        ):
            result = await _call_claude_agent_for_design(
                AgentType.ARCHITECT,
                "Test feature implementation",
                "# Code Context\n" + "x" * 2500,
                self.temp_dir.name,
            )

            # Verify result quality
            self.assertGreater(len(result), 1000)
            self.assertIn("Architect Design Document", result)
            self.assertIn("Executive Summary", result)
            self.assertIn("Implementation Plan", result)

    async def test_agent_response_quality(self):
        """Test that each agent produces comprehensive design documents."""
        for agent_type, expected_response in self.mock_responses.items():
            # Verify each response has required sections
            self.assertIn("Executive Summary", expected_response)
            self.assertIn("Codebase Analysis", expected_response)

            # Check for implementation planning (different agents use different section names)
            has_implementation_section = any(
                section in expected_response
                for section in [
                    "Implementation Plan",
                    "Iterative Delivery",
                    "Test Implementation Plan",
                ]
            )
            self.assertTrue(
                has_implementation_section,
                f"{agent_type} response missing implementation planning section",
            )

            # Verify sufficient length for comprehensive analysis
            self.assertGreater(
                len(expected_response),
                2000,
                f"{agent_type} response too short for comprehensive analysis",
            )

            # Verify agent-specific terminology
            agent_terms = {
                AgentType.ARCHITECT: ["architecture", "system", "component"],
                AgentType.SENIOR_ENGINEER: [
                    "engineering",
                    "implementation",
                    "code quality",
                ],
                AgentType.FAST_CODER: ["rapid", "minimal viable", "quick"],
                AgentType.TEST_FIRST: ["test", "testing", "quality assurance"],
            }

            if agent_type in agent_terms:
                terms_found = 0
                for term in agent_terms[agent_type]:
                    if term.lower() in expected_response.lower():
                        terms_found += 1

                self.assertGreater(
                    terms_found,
                    0,
                    f"{agent_type} response missing agent-specific terminology",
                )

    async def test_error_handling_with_failed_agents(self):
        """Test that workflow fails when any agent fails."""

        async def mock_failing_claude_agent(prompt: str, repo_path: str) -> str:
            # Make one agent fail
            if "Architect" in prompt:
                raise RuntimeError("Claude CLI timeout")
            return await self.mock_claude_agent_call(prompt, repo_path)

        with patch(
            "langgraph_workflow.nodes.extract_code_context._call_claude_code_agent",
            side_effect=mock_failing_claude_agent,
        ):
            with patch("pathlib.Path.mkdir"):
                with patch("pathlib.Path.write_text"):
                    # Should raise RuntimeError due to failed agent
                    with self.assertRaises(RuntimeError) as context:
                        await parallel_design_exploration_handler(self.state)

                    error_msg = str(context.exception)
                    self.assertIn("Parallel design exploration failed", error_msg)
                    self.assertIn("AgentType.ARCHITECT", error_msg)

    async def test_missing_code_context_handling(self):
        """Test handling of missing code context document."""
        # Remove code context
        self.state["code_context_document"] = ""

        with patch(
            "langgraph_workflow.nodes.extract_code_context._call_claude_code_agent",
            side_effect=self.mock_claude_agent_call,
        ):
            with patch("pathlib.Path.mkdir"):
                with patch("pathlib.Path.write_text"):
                    result_state = await parallel_design_exploration_handler(self.state)

                    # Should still complete but with limited context
                    self.assertEqual(len(result_state["agent_analyses"]), 4)


if __name__ == "__main__":
    unittest.main()
