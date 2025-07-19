#!/usr/bin/env python3

"""
Debug LSP startup to understand why pylsp isn't starting properly.
"""

import subprocess
import sys
import unittest

from repository_manager import RepositoryManager


class TestDebugLSPStart(unittest.TestCase):
    """Debug LSP startup issues."""

    def test_debug_repository_manager_lsp(self):
        """Debug what happens when repository manager tries to get LSP client."""
        print("\\nDebugging repository manager LSP client creation...")

        # Set up repository manager
        repo_manager = RepositoryManager()

        # Add the github-agent repository
        from constants import Language
        from repository_manager import RepositoryConfig

        repo_config = RepositoryConfig.create_repository_config(
            name="github-agent",
            workspace="/Volumes/Code/github-agent",
            description="Test repository",
            language=Language.PYTHON,
            port=8081,
            python_path=sys.executable,
        )

        repo_manager.add_repository("github-agent", repo_config)
        print("✅ Repository added successfully")

        # Try to get LSP client
        print("🔍 Attempting to get LSP client...")
        try:
            lsp_client = repo_manager.get_lsp_client("github-agent")

            if lsp_client is None:
                print("❌ LSP client is None")
                return

            print(f"✅ LSP client obtained: {lsp_client}")
            print(f"📊 LSP client type: {type(lsp_client)}")

            # Note: With SimpleLSPClient architecture, LSP clients are created on-demand
            # The repository manager returns a mock client for test compatibility
            if hasattr(lsp_client, "workspace_root"):
                print(f"📊 LSP client workspace: {lsp_client.workspace_root}")

            # Check if there's a server process
            if hasattr(lsp_client, "_server_process"):
                process = lsp_client._server_process
                print(f"📊 Server process: {process}")
                if process:
                    print(f"📊 Process PID: {process.pid}")
                    print(f"📊 Process returncode: {process.returncode}")
            else:
                print("⚠️  LSP client has no _server_process attribute")

        except Exception as e:
            print(f"❌ Exception getting LSP client: {e}")
            import traceback

            traceback.print_exc()

    def test_manual_pylsp_version_check(self):
        """Test if pylsp is working manually."""
        print("\\nTesting pylsp manually...")

        try:
            result = subprocess.run(
                [sys.executable, "-m", "pylsp", "--version"],
                capture_output=True,
                text=True,
                check=True,
                timeout=5,
            )
            print(f"✅ pylsp version: {result.stdout.strip()}")

        except subprocess.CalledProcessError as e:
            print(f"❌ pylsp version check failed: {e}")
            print(f"stdout: {e.stdout}")
            print(f"stderr: {e.stderr}")
        except subprocess.TimeoutExpired:
            print("❌ pylsp version check timed out")
        except Exception as e:
            print(f"❌ Exception running pylsp: {e}")

    def test_check_current_pylsp_processes(self):
        """Check if there are any pylsp processes running."""
        print("\\nChecking for running pylsp processes...")

        try:
            result = subprocess.run(
                ["ps", "aux"], capture_output=True, text=True, check=True
            )

            pylsp_lines = [
                line
                for line in result.stdout.split("\\n")
                if "pylsp" in line and "grep" not in line
            ]

            if pylsp_lines:
                print(f"✅ Found {len(pylsp_lines)} pylsp processes:")
                for line in pylsp_lines:
                    print(f"  {line}")
            else:
                print("INFO: No pylsp processes currently running")

        except Exception as e:
            print(f"❌ Error checking processes: {e}")


if __name__ == "__main__":
    unittest.main()
