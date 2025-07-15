#!/usr/bin/env python3

"""
Tests for Repository Manager LSP Integration - Task 4
"""

import json
import logging
import os
import shutil
import sys
import tempfile
import threading
import unittest

from lsp_client import LSPClientState
from repository_manager import RepositoryManager


class TestRepositoryLSPIntegration(unittest.TestCase):
    """Integration tests for repository manager with LSP servers"""

    def setUp(self):
        """Set up test fixtures"""
        # Create temporary directory for test repositories
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = os.path.join(self.temp_dir, "repositories.json")

        # Create a mock Python repository
        self.test_repo_path = os.path.join(self.temp_dir, "test-repo")
        os.makedirs(self.test_repo_path, exist_ok=True)

        # Initialize as git repository
        os.system(f"cd {self.test_repo_path} && git init")

        # Create test Python files
        self._create_test_python_files()

        # Create repositories.json
        config_data = {
            "repositories": {
                "test-python-repo": {
                    "workspace": self.test_repo_path,
                    "description": "Test Python repository",
                    "language": "python",
                    "port": 8081,
                    "python_path": sys.executable,
                },
                "test-swift-repo": {
                    "workspace": self.test_repo_path,
                    "description": "Test Swift repository",
                    "language": "swift",
                    "port": 8082,
                    "python_path": sys.executable,
                },
            }
        }

        with open(self.config_file, "w") as f:
            json.dump(config_data, f)

        # Set up logging to capture log messages
        self.log_messages: list[str] = []
        self.log_handler = logging.StreamHandler()
        self.log_handler.setLevel(logging.DEBUG)

        def emit_handler(record):
            self.log_messages.append(record.getMessage())

        self.log_handler.emit = emit_handler

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_test_python_files(self):
        """Create test Python files in the repository"""
        # Main module
        main_py = os.path.join(self.test_repo_path, "main.py")
        with open(main_py, "w") as f:
            f.write(
                """
def main():
    print("Hello, World!")
    return 42

class TestClass:
    def __init__(self, value: int):
        self.value = value

    def get_value(self) -> int:
        return self.value

if __name__ == "__main__":
    main()
"""
            )

        # Utils module
        utils_py = os.path.join(self.test_repo_path, "utils.py")
        with open(utils_py, "w") as f:
            f.write(
                """
from typing import List, Optional

def calculate_sum(numbers: List[int]) -> int:
    return sum(numbers)

def find_max(numbers: List[int]) -> Optional[int]:
    return max(numbers) if numbers else None
"""
            )

    def test_lsp_server_lifecycle_management(self):
        """Test complete LSP server lifecycle management"""
        # Use mock client provider for dependency injection
        from tests.conftest import mock_lsp_client_provider

        # Create repository manager with mock provider
        manager = RepositoryManager(
            self.config_file, lsp_client_provider=mock_lsp_client_provider
        )
        manager.logger.addHandler(self.log_handler)

        self.assertTrue(manager.load_configuration())

        # Test starting LSP server (will use real PyrightLSPManager but mock LSP client)
        result = manager.start_lsp_server("test-python-repo")
        self.assertTrue(result)

        # Test getting LSP client
        client = manager.get_lsp_client("test-python-repo")
        self.assertIsNotNone(client)

        # Test LSP status
        status = manager.get_lsp_status("test-python-repo")
        self.assertEqual(status["repository"], "test-python-repo")
        self.assertTrue(status["running"])
        self.assertEqual(status["state"], "initialized")
        self.assertTrue(status["healthy"])

        # Test stopping LSP server
        result = manager.stop_lsp_server("test-python-repo")
        self.assertTrue(result)

        # Verify client is removed
        client = manager.get_lsp_client("test-python-repo")
        self.assertIsNone(client)

    def test_lsp_server_health_monitoring(self):
        """Test LSP server health monitoring and restart"""
        # Create mock client provider that returns unhealthy clients
        from tests.conftest import MockLSPClient

        def unhealthy_client_provider(workspace_root: str, python_path: str):
            mock_client = MockLSPClient(workspace_root=workspace_root)
            mock_client.state = LSPClientState.ERROR
            return mock_client

        manager = RepositoryManager(
            self.config_file, lsp_client_provider=unhealthy_client_provider
        )
        self.assertTrue(manager.load_configuration())

        # Start LSP server
        manager.start_lsp_server("test-python-repo")

        # Monitor health - should detect unhealthy server and restart
        health_status = manager.monitor_lsp_health()

        # Should have attempted restart
        self.assertIn("test-python-repo", health_status)

    def test_lsp_server_configuration_validation(self):
        """Test LSP server configuration validation"""
        manager = RepositoryManager(self.config_file)
        self.assertTrue(manager.load_configuration())

        # Test status for Python repository (supported)
        status = manager.get_lsp_status("test-python-repo")
        self.assertTrue(status["supported"])
        self.assertEqual(status["language"], "python")

        # Test status for Swift repository (not yet supported)
        status = manager.get_lsp_status("test-swift-repo")
        self.assertFalse(status["supported"])  # Swift LSP not implemented yet
        self.assertEqual(status["language"], "swift")

    def test_concurrent_lsp_operations(self):
        """Test concurrent LSP operations are thread-safe"""
        # Use mock client provider for dependency injection
        from tests.conftest import mock_lsp_client_provider

        manager = RepositoryManager(
            self.config_file, lsp_client_provider=mock_lsp_client_provider
        )
        self.assertTrue(manager.load_configuration())

        # Define concurrent operations
        results = {}

        def start_server():
            results["start"] = manager.start_lsp_server("test-python-repo")

        def get_status():
            status_result = manager.get_lsp_status("test-python-repo")
            results["status"] = status_result is not None

        def get_client():
            client_result = manager.get_lsp_client("test-python-repo")
            results["client"] = client_result is not None

        # Run operations concurrently
        threads = []
        for operation in [start_server, get_status, get_client]:
            thread = threading.Thread(target=operation)
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Verify no exceptions occurred and operations completed
        self.assertIn("start", results)
        self.assertIn("status", results)
        self.assertIn("client", results)

    def test_repository_info_integration(self):
        """Test that repository info properly integrates LSP status"""
        # Use mock client provider for dependency injection
        from tests.conftest import mock_lsp_client_provider

        manager = RepositoryManager(
            self.config_file, lsp_client_provider=mock_lsp_client_provider
        )
        self.assertTrue(manager.load_configuration())

        # Get repository info before starting LSP
        info = manager.get_repository_info("test-python-repo")
        self.assertIsNotNone(info)
        self.assertIn("lsp_enabled", info)
        self.assertIn("lsp_status", info)
        self.assertTrue(info["lsp_enabled"])
        self.assertFalse(info["lsp_status"]["running"])

        # Start LSP server
        manager.start_lsp_server("test-python-repo")

        # Get repository info after starting LSP
        info_after = manager.get_repository_info("test-python-repo")
        self.assertIsNotNone(info_after)
        self.assertTrue(info_after["lsp_status"]["running"])
        self.assertTrue(info_after["lsp_status"]["healthy"])

    def test_multiple_repositories_lsp_management(self):
        """Test managing LSP servers for multiple repositories"""
        # Add another Python repository to config
        config_data = {
            "repositories": {
                "repo1": {
                    "workspace": self.test_repo_path,
                    "description": "Repository 1",
                    "language": "python",
                    "port": 8081,
                    "python_path": sys.executable,
                },
                "repo2": {
                    "workspace": self.test_repo_path,
                    "description": "Repository 2",
                    "language": "python",
                    "port": 8082,
                    "python_path": sys.executable,
                },
            }
        }

        multi_config_file = os.path.join(self.temp_dir, "multi_repositories.json")
        with open(multi_config_file, "w") as f:
            json.dump(config_data, f)

        # Use mock client provider for dependency injection
        from tests.conftest import mock_lsp_client_provider

        manager = RepositoryManager(
            multi_config_file, lsp_client_provider=mock_lsp_client_provider
        )
        self.assertTrue(manager.load_configuration())

        # Start all LSP servers
        results = manager.start_all_lsp_servers()

        self.assertEqual(len(results), 2)
        self.assertTrue(results["repo1"])
        self.assertTrue(results["repo2"])

        # Verify both clients exist
        self.assertIsNotNone(manager.get_lsp_client("repo1"))
        self.assertIsNotNone(manager.get_lsp_client("repo2"))

        # Stop all LSP servers
        results = manager.stop_all_lsp_servers()

        self.assertEqual(len(results), 2)
        self.assertTrue(results["repo1"])
        self.assertTrue(results["repo2"])

    def test_lsp_error_handling(self):
        """Test LSP error handling for various failure scenarios"""
        manager = RepositoryManager(self.config_file)
        self.assertTrue(manager.load_configuration())

        # Test starting LSP for non-existent repository
        result = manager.start_lsp_server("non-existent")
        self.assertFalse(result)

        # Test stopping LSP for repository that doesn't have LSP running
        result = manager.stop_lsp_server("test-python-repo")
        self.assertTrue(result)  # Should succeed (no-op)

        # Test getting client for repository without LSP
        client = manager.get_lsp_client("test-python-repo")
        self.assertIsNone(client)

    def test_manager_shutdown_cleanup(self):
        """Test that manager shutdown properly cleans up LSP servers"""
        # Use mock client provider for dependency injection
        from tests.conftest import mock_lsp_client_provider

        manager = RepositoryManager(
            self.config_file, lsp_client_provider=mock_lsp_client_provider
        )
        manager.logger.addHandler(self.log_handler)
        manager.logger.setLevel(logging.DEBUG)
        self.assertTrue(manager.load_configuration())

        # Start LSP server
        manager.start_lsp_server("test-python-repo")

        # Verify server is running
        self.assertIsNotNone(manager.get_lsp_client("test-python-repo"))

        # Shutdown manager
        manager.shutdown()

        # Check that appropriate log messages were generated
        log_messages = [msg for msg in self.log_messages if "shutdown" in msg.lower()]
        
        # The shutdown method should log "Shutting down repository manager..." 
        # and "Repository manager shutdown complete"
        expected_messages = ["shutting down repository manager", "repository manager shutdown complete"]
        found_messages = [msg for msg in expected_messages if any(msg in log_msg.lower() for log_msg in self.log_messages)]
        self.assertTrue(len(found_messages) > 0, f"Expected shutdown messages not found. All messages: {self.log_messages}")


if __name__ == "__main__":
    unittest.main()
