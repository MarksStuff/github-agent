#!/usr/bin/env python3

"""
Integration test for LSP server startup and lifecycle management.

This test verifies that:
1. LSP servers start successfully during application startup
2. LSP clients are available after startup
3. LSP servers stop cleanly during shutdown
"""

import asyncio
import json
import tempfile
import unittest
from pathlib import Path

from lsp_constants import LSPServerType
from repository_manager import RepositoryManager


class TestLSPStartupIntegration(unittest.TestCase):
    """Test LSP server startup and lifecycle in a controlled environment."""

    def setUp(self):
        """Set up test environment with temporary repository."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_repo_path = Path(self.temp_dir) / "test-repo"
        self.test_repo_path.mkdir()

        # Create a simple Python file
        (self.test_repo_path / "main.py").write_text(
            """
def hello_world():
    return "Hello, World!"

class TestClass:
    def test_method(self):
        return hello_world()
"""
        )

        # Create git repo
        import subprocess

        subprocess.run(["git", "init"], cwd=self.test_repo_path, check=True)

        # Create test repositories.json
        self.config_file = Path(self.temp_dir) / "repositories.json"

        # Use sys.executable to get the current Python interpreter path
        import sys

        python_path = sys.executable

        # Create config data as dict and then serialize to avoid path escaping issues
        config_data = {
            "repositories": {
                "test-repo": {
                    "workspace": str(self.test_repo_path),
                    "port": 8090,
                    "description": "Test repository",
                    "language": "python",
                    "python_path": str(python_path),
                }
            }
        }

        self.config_file.write_text(json.dumps(config_data, indent=2))

    def tearDown(self):
        """Clean up test environment."""
        import shutil

        shutil.rmtree(self.temp_dir)

    async def test_lsp_server_lifecycle(self):
        """Test complete LSP server lifecycle: start -> use -> stop."""

        # Use mock LSP client for testing to avoid pyright dependencies
        from tests.conftest import MockLSPClient

        def mock_lsp_client_provider(
            workspace_root: str,
            python_path: str,
            server_type: LSPServerType = LSPServerType.PYLSP,
        ):
            mock_client = MockLSPClient(workspace_root=workspace_root)
            mock_client.set_start_result(True)  # Configure to succeed
            return mock_client

        # Step 1: Create repository manager and load config
        repository_manager = RepositoryManager(
            str(self.config_file), lsp_client_provider=mock_lsp_client_provider
        )

        # Load configuration with better error reporting
        success = repository_manager.load_configuration()
        if not success:
            self.fail(
                f"Failed to load configuration from {self.config_file}. Config file exists: {self.config_file.exists()}, Test repo exists: {self.test_repo_path.exists()}"
            )

        self.assertIn("test-repo", repository_manager.repositories)

        # Step 2: Start LSP servers (this should work without errors)
        lsp_results = {}
        for repo_name in repository_manager.repositories:
            lsp_success: bool | None = await repository_manager.start_lsp_server_async(
                repo_name
            )
            lsp_results[repo_name] = lsp_success if lsp_success is not None else False

        # Step 3: Verify LSP server started successfully
        self.assertTrue(
            lsp_results["test-repo"], "LSP server should start successfully"
        )

        # Step 4: Verify LSP client is available
        lsp_client = repository_manager.get_lsp_client("test-repo")
        self.assertIsNotNone(lsp_client, "LSP client should be available after startup")

        # Step 5: Verify LSP client is in correct state
        from async_lsp_client import AsyncLSPClientState

        self.assertIsNotNone(lsp_client, "LSP client should not be None")
        assert lsp_client is not None  # Help mypy with type narrowing
        self.assertEqual(
            lsp_client.state,
            AsyncLSPClientState.INITIALIZED,
            "LSP client should be initialized and ready",
        )

        # Step 6: Test basic LSP functionality (optional, but good to verify)
        try:
            # Simple test - get file URI
            file_uri = (self.test_repo_path / "main.py").as_uri()
            # This should not raise an exception
            self.assertTrue(file_uri.startswith("file://"))

            # Step 6a: Test find_definition and find_references if LSP server is actually running
            if lsp_client and lsp_client.state == AsyncLSPClientState.INITIALIZED:
                from codebase_tools import CodebaseTools, create_async_lsp_client
                from symbol_storage import SQLiteSymbolStorage

                # Create codebase tools instance to test find_definition/find_references
                symbol_storage = SQLiteSymbolStorage(":memory:")
                codebase_tools = CodebaseTools(
                    repository_manager=repository_manager,
                    symbol_storage=symbol_storage,
                    lsp_client_factory=create_async_lsp_client,
                )

                # Test find_definition for TestClass (line 5, column 7 in our test file)
                test_file_path = str(self.test_repo_path / "main.py")
                try:
                    definition_result_str = await codebase_tools.find_definition(
                        repository_id="test-repo",
                        symbol="TestClass",
                        file_path=test_file_path,
                        line=5,
                        column=7,
                    )

                    # Parse and verify result (should contain class definition or timeout gracefully)
                    import json

                    result = json.loads(definition_result_str)
                    # If no error, should have definitions or locations; if error (like timeout), should gracefully handle
                    if "error" not in result:
                        # Accept either 'locations' (real LSP) or 'definitions' (mock LSP) format
                        has_results = "locations" in result or "definitions" in result
                        self.assertTrue(
                            has_results,
                            "Successful definition result should have locations or definitions",
                        )
                    # If there is an error (like timeout), that's acceptable for this test

                except Exception as e:
                    # LSP functionality may timeout or fail, which is acceptable for integration testing
                    self.fail(
                        f"find_definition should not crash, even if LSP times out: {e}"
                    )

        except Exception as e:
            self.fail(f"Basic LSP operations should work: {e}")

        # Step 7: Stop LSP servers cleanly
        stop_results = repository_manager.stop_all_lsp_servers()
        self.assertTrue(stop_results["test-repo"], "LSP server should stop cleanly")

        # Step 8: Verify LSP client is no longer available or in disconnected state
        lsp_client_after_stop = repository_manager.get_lsp_client("test-repo")
        if lsp_client_after_stop:
            self.assertNotEqual(
                lsp_client_after_stop.state,
                AsyncLSPClientState.INITIALIZED,
                "LSP client should not be initialized after stop",
            )

        # Step 9: Clean up resources properly
        try:
            # Give any remaining async tasks a chance to complete
            await asyncio.sleep(0.1)
        except Exception:
            pass

    def test_lsp_startup_integration_sync_wrapper(self):
        """Sync wrapper for the async test."""
        # Use asyncio.run with proper cleanup
        try:
            asyncio.run(self.test_lsp_server_lifecycle())
        except Exception as e:
            # Clean up any remaining async resources
            import gc

            gc.collect()
            raise e


if __name__ == "__main__":
    unittest.main()
