"""Test fixtures for LangGraph workflow tests."""

import tempfile
from pathlib import Path

import pytest

from ..mocks import create_mock_dependencies


@pytest.fixture
def temp_directory():
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir


@pytest.fixture
def repo_path(temp_directory):
    """Create a temporary repository path."""
    return temp_directory


@pytest.fixture
def thread_id():
    """Standard test thread ID."""
    return "test-thread-123"


@pytest.fixture
def mock_dependencies(thread_id):
    """Create mock dependencies for testing."""
    return create_mock_dependencies(thread_id)


@pytest.fixture
def sample_feature_description():
    """Sample feature description for testing."""
    return "Add comprehensive user authentication with JWT tokens, role-based access control, and session management"


@pytest.fixture
def sample_prd_content():
    """Sample PRD content for testing."""
    return """# Product Requirements Document

## Authentication System
Comprehensive user authentication with the following features:
- User registration with email verification
- Login/logout with JWT tokens
- Password reset functionality
- Role-based access control
- Session management
- Two-factor authentication (optional)

Security requirements:
- Passwords must be hashed using bcrypt
- JWT tokens should expire after 24 hours
- Support for refresh tokens
- Rate limiting on login attempts

## User Profile Management
User profile functionality including:
- Update personal information
- Upload profile pictures
- Privacy settings
- Account deletion

## Dashboard
Analytics dashboard with:
- User activity metrics
- System health monitoring
- Performance statistics
"""


@pytest.fixture
def sample_code_context():
    """Sample code context document."""
    return """# Code Context Document

## Architecture Overview
FastAPI-based REST API with PostgreSQL database and Redis for caching

## Technology Stack
- Languages: Python 3.11, TypeScript
- Backend: FastAPI, SQLAlchemy, Pydantic
- Frontend: React, Next.js
- Database: PostgreSQL
- Cache: Redis
- Testing: pytest, Jest

## Design Patterns
- Repository pattern for data access
- Dependency injection for services
- Factory pattern for object creation
- Observer pattern for event handling

## Code Conventions
- Snake_case for Python variables and functions
- CamelCase for TypeScript classes
- PascalCase for React components
- Type hints required for all Python functions
- ESLint configuration for TypeScript

## Key Interfaces
- UserRepository: Data access for user entities
- AuthService: Authentication and authorization
- NotificationService: User notifications
- CacheService: Redis caching abstraction

## Infrastructure Services
- PostgreSQL database with connection pooling
- Redis cluster for caching and sessions
- Docker containers for local development
- AWS RDS and ElastiCache for production

## Testing Approach
- Unit tests with pytest (Python) and Jest (TypeScript)
- Integration tests for API endpoints
- End-to-end tests with Playwright
- Test coverage minimum 80%

## Recent Changes
- Migrated from SQLite to PostgreSQL (v2.1.0)
- Added Redis for session storage (v2.0.5)
- Updated to Python 3.11 (v2.0.0)
"""


@pytest.fixture
def sample_synthesis_document():
    """Sample synthesis document from architect."""
    return """# Design Synthesis: User Authentication

## Common Themes
- **JWT-based authentication**: All agents agree on using JWT tokens
- **Role-based access control**: Consensus on implementing RBAC
- **Security first**: Strong focus on security best practices
- **Integration with existing patterns**: Use current repository and service patterns

## Conflicts
### Conflict 1: Session Storage
- **Fast-coder**: Simple in-memory sessions for quick implementation
- **Senior Engineer**: Database-backed sessions for persistence
- **Architect**: Redis-based sessions for scalability

### Conflict 2: Password Complexity
- **Test-first**: Strict password requirements with comprehensive validation
- **Fast-coder**: Basic password validation to ship quickly
- **Senior Engineer**: Configurable password policies

## Trade-offs
- **Fast-coder optimizes for**: Speed of delivery and simplicity
- **Test-first optimizes for**: Comprehensive coverage and edge cases
- **Senior Engineer optimizes for**: Code maintainability and patterns
- **Architect optimizes for**: System scalability and integration

## Questions Requiring Code Investigation
- What authentication libraries are currently integrated?
- How is the existing User model structured?
- Are there any auth-related API endpoints already implemented?
- What session management approach is currently used?
"""


@pytest.fixture
def sample_git_repo(temp_directory):
    """Create a sample git repository for testing."""
    import git

    repo_path = Path(temp_directory)
    repo = git.Repo.init(repo_path)

    # Create initial file and commit
    readme = repo_path / "README.md"
    readme.write_text("# Test Repository")

    repo.index.add([str(readme)])
    repo.index.commit("Initial commit")

    # Add remote
    repo.create_remote("origin", "https://github.com/test/repo.git")

    return repo_path


@pytest.fixture
def performance_timer():
    """Timer fixture for performance testing."""
    import time

    class Timer:
        def __init__(self):
            self.start_time = None
            self.end_time = None

        def start(self):
            self.start_time = time.time()

        def stop(self):
            self.end_time = time.time()

        @property
        def elapsed(self):
            if self.start_time and self.end_time:
                return self.end_time - self.start_time
            return None

    return Timer()
