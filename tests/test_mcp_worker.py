#!/usr/bin/env python3

"""
Tests for the unified MCP worker
"""


import pytest
from fastapi.testclient import TestClient

from constants import Language
from mcp_worker import MCPWorker
from tests.mocks import MockGitHubAPIContext

# Note: The duplicate fixtures have been removed - using the consolidated ones from tests.fixtures
# The mcp_worker_factory fixture is overridden here to add specific GitHub context injection

# mcp_worker_factory fixture is now consolidated in tests/fixtures.py as mcp_worker_factory_with_github


class TestMCPWorker:
    """Test cases for the unified MCP worker"""

    def test_worker_initialization(self, mcp_worker_factory_with_github, temp_git_repo):
        """Test that the worker initializes correctly"""
        from repository_manager import RepositoryConfig

        repo_config = RepositoryConfig.create_repository_config(
            name="test-repo",
            workspace=temp_git_repo,
            description="Test repository",
            language=Language.PYTHON,
            port=8080,
            python_path="/usr/bin/python3",
        )
        worker = mcp_worker_factory_with_github(repo_config)

        assert worker.repo_name == "test-repo"
        assert worker.repo_path == temp_git_repo
        assert worker.port == 8080
        assert worker.description == "Test repository"
        assert worker.language == Language.PYTHON

    def test_worker_invalid_path(self, mock_github_token):
        """Test that worker fails with invalid repository path"""
        with pytest.raises(ValueError, match="Repository path .* does not exist"):
            from repository_manager import RepositoryConfig

            repo_config = RepositoryConfig.create_repository_config(
                name="test-repo",
                workspace="/nonexistent/path",
                description="Test repository",
                language=Language.PYTHON,
                port=8080,
                python_path="/usr/bin/python3",
            )
            MCPWorker(repo_config)

    def test_fastapi_app_creation(self, mcp_worker_factory_with_github, temp_git_repo):
        """Test that the FastAPI app is created correctly"""
        from repository_manager import RepositoryConfig

        repo_config = RepositoryConfig.create_repository_config(
            name="test-repo",
            workspace=temp_git_repo,
            description="Test repository",
            language=Language.PYTHON,
            port=8080,
            python_path="/usr/bin/python3",
        )
        worker = mcp_worker_factory_with_github(repo_config)

        assert worker.app is not None
        assert worker.app.title == "MCP Worker - test-repo"

    def test_app_endpoints(self, mcp_worker_factory_with_github, temp_git_repo):
        """Test that the app has the correct endpoints"""
        from repository_manager import RepositoryConfig

        repo_config = RepositoryConfig.create_repository_config(
            name="test-repo",
            workspace=temp_git_repo,
            description="Test repository",
            language=Language.PYTHON,
            port=8080,
            python_path="/usr/bin/python3",
        )
        worker = mcp_worker_factory_with_github(repo_config)

        client = TestClient(worker.app)

        # Test root endpoint
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "MCP Worker - test-repo"
        assert data["repository"] == "test-repo"
        assert data["port"] == 8080
        assert "github" in data["tool_categories"]
        assert "codebase" in data["tool_categories"]

    def test_health_endpoint(self, temp_git_repo, mock_github_token, mock_subprocess):
        """Test the health check endpoint"""
        from repository_manager import RepositoryConfig

        repo_config = RepositoryConfig.create_repository_config(
            name="test-repo",
            workspace=temp_git_repo,
            description="Test repository",
            language=Language.PYTHON,
            port=8080,
            python_path="/usr/bin/python3",
        )

        # Create mock GitHub context for dependency injection
        mock_github_context = MockGitHubAPIContext(
            repo_name="test/test-repo", github_token="fake_token_for_testing"
        )

        worker = MCPWorker(repo_config, github_context=mock_github_context)

        client = TestClient(worker.app)

        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["repository"] == "test-repo"
        assert data["github_configured"] is True
        assert data["repo_path_exists"] is True
        assert "github" in data["tool_categories"]
        assert "codebase" in data["tool_categories"]

    def test_mcp_initialize(self, temp_git_repo, mock_github_token, mock_subprocess):
        """Test MCP initialize method"""
        from repository_manager import RepositoryConfig

        repo_config = RepositoryConfig.create_repository_config(
            name="test-repo",
            workspace=temp_git_repo,
            description="Test repository",
            language=Language.PYTHON,
            port=8080,
            python_path="/usr/bin/python3",
        )

        # Create mock GitHub context for dependency injection
        mock_github_context = MockGitHubAPIContext(
            repo_name="test/test-repo", github_token="fake_token_for_testing"
        )

        worker = MCPWorker(repo_config, github_context=mock_github_context)

        client = TestClient(worker.app)

        # Test MCP initialize
        initialize_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {},
        }

        response = client.post("/mcp/", json=initialize_request)
        assert response.status_code == 200
        response_data = response.json()

        # Check direct JSON-RPC response format (no longer queued)
        assert response_data["jsonrpc"] == "2.0"
        assert response_data["id"] == 1
        assert "result" in response_data
        assert response_data["result"]["serverInfo"]["name"] == "mcp-agent-test-repo"

    def test_mcp_tools_list(self, temp_git_repo, mock_github_token, mock_subprocess):
        """Test MCP tools/list method"""
        from repository_manager import RepositoryConfig

        repo_config = RepositoryConfig.create_repository_config(
            name="test-repo",
            workspace=temp_git_repo,
            description="Test repository",
            language=Language.PYTHON,
            port=8080,
            python_path="/usr/bin/python3",
        )

        # Create mock GitHub context for dependency injection
        mock_github_context = MockGitHubAPIContext(
            repo_name="test/test-repo", github_token="fake_token_for_testing"
        )

        worker = MCPWorker(repo_config, github_context=mock_github_context)

        client = TestClient(worker.app)

        # Test tools/list
        tools_request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {},
        }

        response = client.post("/mcp/", json=tools_request)
        assert response.status_code == 200
        response_data = response.json()

        # Check direct JSON-RPC response format (no longer queued)
        assert response_data["jsonrpc"] == "2.0"
        assert response_data["id"] == 2
        assert "result" in response_data
        tools = response_data["result"]["tools"]

        # Should have both GitHub and codebase tools
        tool_names = [tool["name"] for tool in tools]

        # Check for GitHub tools
        assert "git_get_current_branch" in tool_names
        assert "git_get_current_commit" in tool_names
        assert "github_find_pr_for_branch" in tool_names
        assert "github_get_pr_comments" in tool_names
        assert "github_post_pr_reply" in tool_names
        assert "github_check_ci_build_and_test_errors_not_local" in tool_names
        assert "github_check_ci_lint_errors_not_local" in tool_names
        assert "github_get_build_status" in tool_names

        # Check for codebase tools
        assert "codebase_health_check" in tool_names

    @pytest.mark.asyncio
    async def test_mcp_tool_call_codebase_health_check(
        self, temp_git_repo, mock_github_token, mock_subprocess
    ):
        """Test MCP tool call for codebase health check"""
        from repository_manager import RepositoryConfig

        repo_config = RepositoryConfig.create_repository_config(
            name="test-repo",
            workspace=temp_git_repo,
            description="Test repository",
            language=Language.PYTHON,
            port=8080,
            python_path="/usr/bin/python3",
        )

        # Create mock GitHub context for dependency injection
        mock_github_context = MockGitHubAPIContext(
            repo_name="test/test-repo", github_token="fake_token_for_testing"
        )

        worker = MCPWorker(repo_config, github_context=mock_github_context)

        client = TestClient(worker.app)

        # Test codebase health check tool call
        tool_call_request = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "codebase_health_check", "arguments": {}},
        }

        response = client.post("/mcp/", json=tool_call_request)
        assert response.status_code == 200
        response_data = response.json()

        # Check direct JSON-RPC response format (no longer queued)
        assert response_data["jsonrpc"] == "2.0"
        assert response_data["id"] == 3
        assert "result" in response_data
        result_text = response_data["result"]["content"][0]["text"]
        assert '"status":' in result_text  # Accept any status (healthy, warning, etc.)
        assert '"repo": "test-repo"' in result_text

        # This is now an integration test - the actual health check runs

    @pytest.mark.asyncio
    async def test_mcp_tool_call_find_references_no_duplicate_args(
        self, temp_git_repo, mock_github_token, mock_subprocess
    ):
        """Test MCP tool call for find_references to prevent duplicate repository_id argument regression"""
        from repository_manager import RepositoryConfig

        repo_config = RepositoryConfig.create_repository_config(
            name="test-repo",
            workspace=temp_git_repo,
            description="Test repository",
            language=Language.PYTHON,
            port=8080,
            python_path="/usr/bin/python3",
        )

        # Create mock GitHub context for dependency injection
        mock_github_context = MockGitHubAPIContext(
            repo_name="test/test-repo", github_token="fake_token_for_testing"
        )

        worker = MCPWorker(repo_config, github_context=mock_github_context)

        client = TestClient(worker.app)

        # Test find_references tool call with repository_id argument
        # This specifically tests the fix for duplicate repository_id argument issue
        tool_call_request = {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "find_references",
                "arguments": {
                    "repository_id": "test-repo",
                    "symbol": "test_symbol",
                    "file_path": "main.py",
                    "line": 1,
                    "column": 1,
                },
            },
        }

        response = client.post("/mcp/", json=tool_call_request)
        assert response.status_code == 200
        response_data = response.json()

        # Check direct JSON-RPC response format (no longer queued)
        assert response_data["jsonrpc"] == "2.0"
        assert response_data["id"] == 4
        assert "result" in response_data
        result_text = response_data["result"]["content"][0]["text"]

        # Should not contain the specific duplicate argument error
        assert (
            "got multiple values for keyword argument 'repository_id'"
            not in result_text
        )
        # Should contain either a valid response or an LSP-related error (not argument error)
        assert '"error"' in result_text or '"symbol"' in result_text

    def test_mcp_unknown_tool(self, temp_git_repo, mock_github_token, mock_subprocess):
        """Test MCP tool call for unknown tool"""
        from repository_manager import RepositoryConfig

        repo_config = RepositoryConfig.create_repository_config(
            name="test-repo",
            workspace=temp_git_repo,
            description="Test repository",
            language=Language.PYTHON,
            port=8080,
            python_path="/usr/bin/python3",
        )

        # Create mock GitHub context for dependency injection
        mock_github_context = MockGitHubAPIContext(
            repo_name="test/test-repo", github_token="fake_token_for_testing"
        )

        worker = MCPWorker(repo_config, github_context=mock_github_context)

        client = TestClient(worker.app)

        # Test unknown tool call
        tool_call_request = {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {"name": "unknown_tool", "arguments": {}},
        }

        response = client.post("/mcp/", json=tool_call_request)
        assert response.status_code == 200
        response_data = response.json()

        # Check direct JSON-RPC response format (no longer queued)
        assert response_data["jsonrpc"] == "2.0"
        assert response_data["id"] == 4
        assert "result" in response_data
        result_text = response_data["result"]["content"][0]["text"]
        assert '"error"' in result_text
        assert "not implemented" in result_text

    def test_shutdown_endpoint(self, temp_git_repo, mock_github_token, mock_subprocess):
        """Test the shutdown endpoint"""
        from repository_manager import RepositoryConfig

        repo_config = RepositoryConfig.create_repository_config(
            name="test-repo",
            workspace=temp_git_repo,
            description="Test repository",
            language=Language.PYTHON,
            port=8080,
            python_path="/usr/bin/python3",
        )

        # Create mock GitHub context for dependency injection
        mock_github_context = MockGitHubAPIContext(
            repo_name="test/test-repo", github_token="fake_token_for_testing"
        )

        worker = MCPWorker(repo_config, github_context=mock_github_context)

        client = TestClient(worker.app)

        response = client.post("/shutdown")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "shutdown_initiated"

        # Check that shutdown event is set
        assert worker.shutdown_event.is_set()


if __name__ == "__main__":
    pytest.main([__file__])
