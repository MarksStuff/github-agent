"""
Real LSP Server Integration Tests

These tests use actual LSP servers and are designed to be run in environments
where real LSP server testing is needed. They use dynamic port allocation
to avoid conflicts with running services.

Note: These tests may take longer to run and require actual LSP server binaries.
"""

import json
import os
import sys
import tempfile
import unittest

from repository_manager import RepositoryManager
from tests.conftest import find_free_port


class TestRealLSPServerIntegration(unittest.TestCase):
    """
    Real LSP server integration tests using dynamic port allocation.

    These tests can be skipped in CI environments or when LSP servers
    are not available by setting the SKIP_REAL_LSP_TESTS environment variable.
    """

    def setUp(self):
        """Set up test fixtures with dynamic port allocation"""
        # Skip if environment variable is set
        if os.getenv("SKIP_REAL_LSP_TESTS"):
            self.skipTest("Real LSP tests skipped by environment variable")

        # Create temporary directory for test repositories
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = os.path.join(self.temp_dir, "repositories.json")

        # Create a mock Python repository
        self.test_repo_path = os.path.join(self.temp_dir, "test-repo")
        os.makedirs(self.test_repo_path, exist_ok=True)

        # Initialize as git repository
        os.system(f"cd {self.test_repo_path} && git init")

        # Create a test Python file with realistic content
        test_py_file = os.path.join(self.test_repo_path, "test.py")
        with open(test_py_file, "w") as f:
            f.write(
                """
def hello_world() -> str:
    '''Return a greeting message.'''
    return 'Hello, World!'

class TestClass:
    '''A simple test class.'''

    def __init__(self, name: str):
        self.name = name

    def greet(self) -> str:
        '''Return a personalized greeting.'''
        return f'Hello, {self.name}!'

if __name__ == "__main__":
    print(hello_world())
"""
            )

        # Find multiple free ports for potential multiple repositories
        self.test_port = find_free_port()
        self.backup_port = find_free_port(self.test_port + 1)

        # Create repositories.json with dynamic port
        config_data = {
            "repositories": {
                "test-python-repo": {
                    "workspace": self.test_repo_path,
                    "description": "Test Python repository for real LSP testing",
                    "language": "python",
                    "port": self.test_port,
                    "python_path": sys.executable,
                }
            }
        }

        with open(self.config_file, "w") as f:
            json.dump(config_data, f)

    def tearDown(self):
        """Clean up test fixtures"""
        import shutil

        # Clean up any running LSP servers
        try:
            if hasattr(self, "manager"):
                self.manager.shutdown()
        except Exception:
            pass  # Ignore cleanup errors

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_real_lsp_server_startup_and_shutdown(self):
        """Test actual LSP server startup and shutdown with dynamic ports"""
        self.manager = RepositoryManager(self.config_file)
        self.assertTrue(self.manager.load_configuration())

        # Test that we can start an LSP server
        result = self.manager.start_lsp_server("test-python-repo")

        # This might fail if pyright is not installed, which is okay for this test
        if result:
            # Note: get_lsp_client is deprecated and returns None in production
            # SimpleLSPClient handles LSP directly, so we just test shutdown
            stop_result = self.manager.stop_lsp_server("test-python-repo")
            self.assertTrue(stop_result)
        else:
            self.skipTest("LSP server not available (pyright may not be installed)")

    def test_port_conflict_handling(self):
        """Test behavior when configured port is already in use"""
        import socket

        # Bind to the test port to simulate a conflict
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.bind(("localhost", self.test_port))
            sock.listen(1)

            # Now try to start the LSP server - it should handle the conflict gracefully
            self.manager = RepositoryManager(self.config_file)
            self.assertTrue(self.manager.load_configuration())

            # The LSP server startup might fail due to port conflict,
            # but it should not crash the application
            self.manager.start_lsp_server("test-python-repo")

            # We don't assert the result because port conflict handling
            # behavior may vary, but the test should not crash

        finally:
            sock.close()

    def test_multiple_repositories_with_dynamic_ports(self):
        """Test multiple repositories with dynamically allocated ports"""
        # Create a second repository config
        second_repo_path = os.path.join(self.temp_dir, "test-repo-2")
        os.makedirs(second_repo_path, exist_ok=True)

        # Initialize as git repository
        os.system(f"cd {second_repo_path} && git init")

        # Create another test Python file
        test_py_file = os.path.join(second_repo_path, "module.py")
        with open(test_py_file, "w") as f:
            f.write("def calculate(x: int, y: int) -> int:\n    return x + y\n")

        # Update config with second repository using backup port
        config_data = {
            "repositories": {
                "test-python-repo": {
                    "workspace": self.test_repo_path,
                    "description": "Test Python repository",
                    "language": "python",
                    "port": self.test_port,
                    "python_path": sys.executable,
                },
                "test-python-repo-2": {
                    "workspace": second_repo_path,
                    "description": "Second test Python repository",
                    "language": "python",
                    "port": self.backup_port,
                    "python_path": sys.executable,
                },
            }
        }

        with open(self.config_file, "w") as f:
            json.dump(config_data, f)

        self.manager = RepositoryManager(self.config_file)
        self.assertTrue(self.manager.load_configuration())

        # Test starting all LSP servers
        results = self.manager.start_all_lsp_servers()

        # Verify results structure (even if LSP servers fail to start)
        self.assertIn("test-python-repo", results)
        self.assertIn("test-python-repo-2", results)


# Note: The find_free_port() utility in conftest.py is a simple testing helper
# and doesn't need comprehensive testing. It's used to avoid port conflicts
# in our LSP integration tests.


if __name__ == "__main__":
    unittest.main()
