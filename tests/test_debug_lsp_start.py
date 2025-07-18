#!/usr/bin/env python3

"""
Debug LSP startup to understand why pylsp isn't starting properly.
"""

import asyncio
import subprocess
import sys
import unittest
from pathlib import Path

from repository_manager import RepositoryManager


class TestDebugLSPStart(unittest.TestCase):
    """Debug LSP startup issues."""

    def test_debug_repository_manager_lsp(self):
        """Debug what happens when repository manager tries to get LSP client."""
        print(f"\\nDebugging repository manager LSP client creation...")
        
        # Set up repository manager
        repo_manager = RepositoryManager()
        
        # Add the github-agent repository
        repo_config = {
            "workspace": "/Volumes/Code/github-agent",
            "language": "python",
            "python_path": sys.executable,
        }
        
        repo_manager.add_repository("github-agent", repo_config)
        print(f"✅ Repository added successfully")
        
        # Try to get LSP client
        print(f"🔍 Attempting to get LSP client...")
        try:
            lsp_client = repo_manager.get_lsp_client("github-agent")
            
            if lsp_client is None:
                print(f"❌ LSP client is None")
                return
                
            print(f"✅ LSP client obtained: {lsp_client}")
            print(f"📊 LSP client state: {lsp_client.state}")
            print(f"📊 LSP client type: {type(lsp_client)}")
            
            # Check if there's a server process
            if hasattr(lsp_client, '_server_process'):
                process = lsp_client._server_process
                print(f"📊 Server process: {process}")
                if process:
                    print(f"📊 Process PID: {process.pid}")
                    print(f"📊 Process returncode: {process.returncode}")
            else:
                print(f"⚠️  LSP client has no _server_process attribute")
                
        except Exception as e:
            print(f"❌ Exception getting LSP client: {e}")
            import traceback
            traceback.print_exc()
    
    def test_manual_pylsp_version_check(self):
        """Test if pylsp is working manually."""
        print(f"\\nTesting pylsp manually...")
        
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pylsp", "--version"],
                capture_output=True,
                text=True,
                check=True,
                timeout=5
            )
            print(f"✅ pylsp version: {result.stdout.strip()}")
            
        except subprocess.CalledProcessError as e:
            print(f"❌ pylsp version check failed: {e}")
            print(f"stdout: {e.stdout}")
            print(f"stderr: {e.stderr}")
        except subprocess.TimeoutExpired:
            print(f"❌ pylsp version check timed out")
        except Exception as e:
            print(f"❌ Exception running pylsp: {e}")
    
    def test_check_current_pylsp_processes(self):
        """Check if there are any pylsp processes running."""
        print(f"\\nChecking for running pylsp processes...")
        
        try:
            result = subprocess.run(
                ["ps", "aux"],
                capture_output=True,
                text=True,
                check=True
            )
            
            pylsp_lines = [line for line in result.stdout.split('\\n') if 'pylsp' in line and 'grep' not in line]
            
            if pylsp_lines:
                print(f"✅ Found {len(pylsp_lines)} pylsp processes:")
                for line in pylsp_lines:
                    print(f"  {line}")
            else:
                print(f"ℹ️  No pylsp processes currently running")
                
        except Exception as e:
            print(f"❌ Error checking processes: {e}")


if __name__ == "__main__":
    unittest.main()
