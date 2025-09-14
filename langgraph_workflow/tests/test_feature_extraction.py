"""Comprehensive tests for feature extraction from PRD documents."""

import os
from unittest.mock import Mock, patch

import pytest

from langgraph_workflow.run import extract_feature_from_prd
from langgraph_workflow.tests.test_utils import (
    LLMTestCase,
    LLMTestFramework,
    LLMTestingMixin,
    MockLLMResponse,
    integration_test,
    requires_ollama,
)


class TestFeatureExtractionUnit(LLMTestingMixin):
    """Unit tests for feature extraction using mocks."""

    @pytest.fixture
    def sample_prd_content(self):
        """Sample PRD content for testing."""
        return """# Product Requirements Document

## 1. User Authentication
Implement a secure login system with the following features:
- JWT token-based authentication
- Two-factor authentication (2FA) support
- Password reset functionality
- Session management
- OAuth integration with Google and GitHub

### Acceptance Criteria
- Users can register with email/password
- Users can log in and receive JWT tokens
- 2FA can be enabled/disabled per user
- Password reset emails are sent successfully

## 2. Data Processing Pipeline
Build an ETL pipeline for data transformation:
- Extract data from multiple sources
- Transform data according to business rules
- Load processed data into data warehouse
- Real-time streaming support
- Error handling and retry logic

### Acceptance Criteria
- Pipeline processes 1M+ records per hour
- Data quality checks are performed
- Failed records are logged and retried"""

    @pytest.fixture
    def test_cases(self):
        """Test cases for feature extraction."""
        return [
            LLMTestCase(
                name="extract_auth_feature",
                inputs={
                    "prd_content": "## User Authentication\nJWT-based login system with 2FA support.",
                    "feature_name": "User Authentication",
                },
                expected_mock_output="## User Authentication\nJWT-based login system with 2FA support.",
                structural_requirements={
                    "min_length": 20,
                    "max_length": 1000,
                    "required_sections": ["Authentication"],
                },
                semantic_requirements={
                    "expected_concepts": ["authentication", "login", "jwt", "2fa"],
                    "min_concept_matches": 2,
                    "unexpected_concepts": ["data processing", "pipeline", "etl"],
                },
                instruction_requirements={
                    "should_contain": ["Authentication"],
                    "should_not_contain": ["Data Processing"],
                },
            ),
            LLMTestCase(
                name="extract_data_pipeline_feature",
                inputs={
                    "prd_content": "## Data Processing\nETL pipeline with real-time streaming.",
                    "feature_name": "Data Processing",
                },
                expected_mock_output="## Data Processing\nETL pipeline with real-time streaming.",
                structural_requirements={
                    "min_length": 15,
                    "max_length": 1000,
                },
                semantic_requirements={
                    "expected_concepts": ["data", "processing", "etl", "pipeline"],
                    "min_concept_matches": 2,
                    "unexpected_concepts": ["authentication", "login", "jwt"],
                },
            ),
            LLMTestCase(
                name="case_insensitive_extraction",
                inputs={
                    "prd_content": "## User AUTHENTICATION\nLogin system with security features.",
                    "feature_name": "user authentication",
                },
                expected_mock_output="## User AUTHENTICATION\nLogin system with security features.",
                structural_requirements={
                    "required_sections": ["AUTHENTICATION"],
                },
                semantic_requirements={
                    "expected_concepts": ["authentication", "login", "security"],
                    "min_concept_matches": 2,
                },
            ),
        ]

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_extract_feature_llm_mock_success(self, test_cases):
        """Test successful feature extraction with LLM mock."""
        test_case = test_cases[0]  # Use auth feature test case
        framework = LLMTestFramework(extract_feature_from_prd)

        # Create mock for successful LLM response
        mock_response = MockLLMResponse(test_case.expected_mock_output)
        mock_calls = (
            mock_response.create_claude_cli_mock()
        )  # This creates generic subprocess mocks

        await framework.run_mock_test(test_case, mock_subprocess_calls=mock_calls)

    @pytest.mark.asyncio
    async def test_extract_feature_api_fallback(self, test_cases):
        """Test fallback to API when CLI not available."""
        test_case = test_cases[0]
        framework = LLMTestFramework(extract_feature_from_prd)

        # Mock CLI as unavailable
        cli_unavailable_mocks = [
            Mock(returncode=1, stderr="Command not found")  # CLI check fails
        ]

        # Mock API response
        api_mock = Mock()
        api_mock.content = test_case.expected_mock_output

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test-key"}):
            await framework.run_mock_test(
                test_case,
                mock_subprocess_calls=cli_unavailable_mocks,
                mock_api_response=api_mock,
            )

    @pytest.mark.asyncio
    async def test_extract_feature_case_insensitive(self, test_cases):
        """Test case-insensitive feature matching."""
        test_case = test_cases[2]  # Case insensitive test case
        framework = LLMTestFramework(extract_feature_from_prd)

        mock_response = MockLLMResponse(test_case.expected_mock_output)
        mock_calls = mock_response.create_claude_cli_mock()

        await framework.run_mock_test(test_case, mock_subprocess_calls=mock_calls)

    @pytest.mark.asyncio
    async def test_extract_feature_not_found(self):
        """Test when feature is not found in PRD."""
        mock_response = MockLLMResponse("FEATURE_NOT_FOUND")
        mock_calls = mock_response.create_claude_cli_mock()

        with patch("subprocess.run", side_effect=mock_calls):
            result = await extract_feature_from_prd(
                "## Different Feature\nSomething else", "Nonexistent Feature"
            )

        assert result is None

    @pytest.mark.asyncio
    async def test_extract_feature_cli_failure_fallback(self, sample_prd_content):
        """Test fallback to text search when LLM fails."""
        # Mock CLI failure
        mock_calls = MockLLMResponse("").create_subprocess_error_mock("CLI failed")

        with patch("subprocess.run", side_effect=mock_calls):
            # Should fall back to simple text search
            result = await extract_feature_from_prd(
                sample_prd_content, "User Authentication"
            )

            # Text fallback should find the feature
            assert result is not None
            assert "User Authentication" in result
            assert "JWT token-based authentication" in result
            # Should not include the data processing section
            assert "Data Processing Pipeline" not in result

    @pytest.mark.asyncio
    async def test_extract_feature_no_llm_fallback(self):
        """Test fallback behavior when no LLM is available."""
        # Mock CLI unavailable
        with patch("subprocess.run", side_effect=FileNotFoundError()):
            with patch.dict(os.environ, {}, clear=True):  # No API key
                # The function should fall back to text search, not raise an error
                # This test demonstrates the fallback behavior
                result = await extract_feature_from_prd(
                    "## Test Feature\nSome content", "Test Feature"
                )
                # Should fall back to simple text extraction and find the feature
                assert result is not None
                assert "Test Feature" in result

    @pytest.mark.asyncio
    async def test_multiple_features_separation(self, sample_prd_content):
        """Test that extraction properly separates different features."""
        framework = LLMTestFramework(extract_feature_from_prd)

        # Test extracting auth feature - should not include data processing
        auth_case = LLMTestCase(
            name="auth_isolation",
            inputs={
                "prd_content": sample_prd_content,
                "feature_name": "User Authentication",
            },
            expected_mock_output="## 1. User Authentication\nImplement a secure login system with JWT token-based authentication and 2FA support.",
            semantic_requirements={
                "expected_concepts": ["authentication", "jwt", "2fa"],
                "min_concept_matches": 2,
                "unexpected_concepts": ["etl", "pipeline", "data warehouse"],
            },
        )

        mock_response = MockLLMResponse(auth_case.expected_mock_output)
        mock_calls = mock_response.create_claude_cli_mock()

        await framework.run_mock_test(auth_case, mock_subprocess_calls=mock_calls)


@pytest.mark.integration
class TestFeatureExtractionIntegration(LLMTestingMixin):
    """Integration tests for feature extraction with real LLM."""

    @pytest.fixture
    def complex_prd_content(self):
        """More complex PRD content for integration testing."""
        return """# Advanced Product Requirements

## Feature 1: Advanced User Authentication System
Implement a comprehensive authentication system that includes:

### Core Requirements
- Multi-factor authentication (MFA) with SMS, email, and authenticator apps
- Social login integration (Google, GitHub, Microsoft, Facebook)
- Passwordless authentication using WebAuthn/FIDO2
- JWT refresh token rotation for enhanced security
- Account lockout policies after failed attempts
- Audit logging for all authentication events

### Technical Specifications
- Use bcrypt for password hashing with minimum 12 rounds
- JWT tokens expire after 15 minutes, refresh tokens after 7 days
- Rate limiting: 5 login attempts per IP per minute
- Support for custom authentication providers via SAML/OIDC
- Database encryption for sensitive user data

### Acceptance Criteria
- User registration flow completes in under 30 seconds
- Login success rate > 99.5% under normal conditions
- MFA setup completion rate > 80% for new users
- Zero downtime deployment for authentication updates

## Feature 2: Real-time Data Analytics Dashboard
Build a high-performance analytics dashboard with:

### Core Requirements
- Real-time data visualization with sub-second updates
- Custom dashboard creation with drag-and-drop interface
- Advanced filtering and query builder
- Export capabilities (PDF, Excel, CSV)
- Collaborative sharing and commenting features
- Mobile-responsive design

### Technical Specifications
- WebSocket connections for real-time updates
- Redis caching layer for frequently accessed data
- Elasticsearch for fast full-text search and aggregations
- Support for 100+ concurrent dashboard viewers
- Data refresh intervals configurable from 1 second to 1 hour

### Acceptance Criteria
- Dashboard loads within 2 seconds for datasets up to 1M records
- Real-time updates have <500ms latency from data source
- Support for 10+ chart types and visualization options
- 99.9% uptime SLA for analytics services"""

    @requires_ollama
    @integration_test
    @pytest.mark.asyncio
    async def test_extract_auth_feature_real_llm(self, complex_prd_content):
        """Test authentication feature extraction with real LLM."""
        result = await extract_feature_from_prd(
            complex_prd_content, "Advanced User Authentication System"
        )

        # Structural assertions
        self.assert_structural_quality(
            result,
            min_length=100,
            max_length=3000,
            required_sections=["Authentication", "System"],
            forbidden_sections=["Analytics", "Dashboard"],
        )

        # Semantic assertions
        self.assert_semantic_quality(
            result,
            expected_concepts=[
                "authentication",
                "mfa",
                "jwt",
                "login",
                "security",
                "webauthn",
                "social",
                "passwordless",
            ],
            min_concept_matches=4,
            unexpected_concepts=[
                "dashboard",
                "analytics",
                "websocket",
                "elasticsearch",
                "visualization",
                "charts",
            ],
        )

        # Instruction following assertions
        self.assert_instruction_following(
            result,
            should_contain=["Authentication"],
            should_not_contain=["Analytics Dashboard", "Real-time Data"],
        )

    @requires_ollama
    @integration_test
    @pytest.mark.asyncio
    async def test_extract_analytics_feature_real_llm(self, complex_prd_content):
        """Test analytics feature extraction with real LLM."""
        result = await extract_feature_from_prd(
            complex_prd_content, "Real-time Data Analytics Dashboard"
        )

        # Structural assertions
        self.assert_structural_quality(
            result,
            min_length=100,
            max_length=3000,
            required_sections=["Analytics", "Dashboard"],
            forbidden_sections=["Authentication", "User Authentication"],
        )

        # Semantic assertions
        self.assert_semantic_quality(
            result,
            expected_concepts=[
                "analytics",
                "dashboard",
                "real-time",
                "visualization",
                "data",
                "websocket",
                "elasticsearch",
                "charts",
            ],
            min_concept_matches=4,
            unexpected_concepts=[
                "authentication",
                "login",
                "jwt",
                "mfa",
                "password",
                "webauthn",
                "social",
            ],
        )

    @integration_test
    @pytest.mark.asyncio
    async def test_feature_extraction_edge_cases_real_llm(self):
        """Test edge cases with real LLM."""
        # Test with minimal content
        minimal_content = "## Auth\nBasic login."
        result = await extract_feature_from_prd(minimal_content, "Auth")

        if result:  # LLM might return something
            assert "auth" in result.lower()
            assert len(result) >= 5

        # Test with no matching feature
        result = await extract_feature_from_prd(
            "## Different Feature\nNot what we want", "Nonexistent Feature"
        )

        # Should either return None or fallback to text search
        if result:
            assert len(result) > 0


class TestFeatureExtractionErrorHandling(LLMTestingMixin):
    """Test error handling and edge cases."""

    @pytest.mark.asyncio
    async def test_empty_prd_content(self):
        """Test handling of empty PRD content."""
        result = await extract_feature_from_prd("", "Any Feature")

        # Should handle gracefully - either return None or empty string
        assert result is None or result == ""

    @pytest.mark.asyncio
    async def test_empty_feature_name(self):
        """Test handling of empty feature name."""
        result = await extract_feature_from_prd("## Some Feature\nContent", "")

        # Should handle gracefully
        assert result is None or isinstance(result, str)

    @pytest.mark.asyncio
    async def test_very_long_prd_content(self):
        """Test handling of very long PRD content."""
        # Create a very long PRD (simulate memory pressure)
        long_content = "## Test Feature\n" + "Content line.\n" * 10000

        with patch("subprocess.run") as mock_run:
            # Mock successful CLI response
            mock_run.side_effect = [
                Mock(returncode=0, stdout="1.0.113 (Claude Code)"),
                Mock(returncode=0, stdout="## Test Feature\nExtracted content"),
            ]

            result = await extract_feature_from_prd(long_content, "Test Feature")

            # Should handle without crashing
            assert result is not None
            assert "Test Feature" in result

    @pytest.mark.asyncio
    async def test_special_characters_in_feature_name(self):
        """Test handling of special characters in feature names."""
        prd_content = "## API v2.0 Integration (OAuth 2.0)\nAPI integration details."
        feature_name = "API v2.0 Integration (OAuth 2.0)"

        mock_response = MockLLMResponse(
            "## API v2.0 Integration (OAuth 2.0)\nAPI integration details."
        )
        mock_calls = mock_response.create_claude_cli_mock()

        with patch("subprocess.run", side_effect=mock_calls):
            result = await extract_feature_from_prd(prd_content, feature_name)

            assert result is not None
            assert "API v2.0" in result
            assert "OAuth 2.0" in result

    @pytest.mark.asyncio
    async def test_unicode_content(self):
        """Test handling of Unicode content in PRD."""
        prd_content = """## Internationalization 🌐
支持多语言界面
- 中文支持
- العربية support
- Русский язык
"""

        mock_response = MockLLMResponse(prd_content)
        mock_calls = mock_response.create_claude_cli_mock()

        with patch("subprocess.run", side_effect=mock_calls):
            result = await extract_feature_from_prd(prd_content, "Internationalization")

            assert result is not None
            # Should preserve Unicode characters
            assert "🌐" in result
            assert "支持" in result
