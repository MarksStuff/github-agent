#!/usr/bin/env python3

"""
Simple test to reproduce the LSP find_definition timeout issue.

This test bypasses the complex repository setup and directly tests
the LSP client timeout behavior.
"""

import asyncio
import sys
import unittest
from pathlib import Path

from async_lsp_client import AsyncLSPClient


class TestLSPTimeoutSimple(unittest.TestCase):
    """Simple test for LSP timeout issue."""

    def test_lsp_find_definition_timeout(self):
        """Test that reproduces the LSP find_definition timeout."""
        print(f"\\nTesting LSP find_definition timeout with direct client")
        
        workspace_root = Path("/Volumes/Code/github-agent")
        python_path = sys.executable
        
        async def test_lsp_timeout():
            # Create LSP client directly using correct constructor
            import logging
            from lsp_server_factory import LSPServerFactory
            from async_lsp_client import LSPProtocol
            
            server_manager = LSPServerFactory.create_server_manager(
                "pylsp", str(workspace_root), python_path
            )
            logger = logging.getLogger("test_lsp_timeout")
            protocol = LSPProtocol(logger)
            
            lsp_client = AsyncLSPClient(
                workspace_root=workspace_root,
                server_manager=server_manager,
                logger=logger,
                protocol=protocol
            )
            
            try:
                print(f"Starting LSP client...")
                await lsp_client.start()
                print(f"LSP client state: {lsp_client.state}")
                
                if lsp_client.state.name != "INITIALIZED":
                    print(f"❌ LSP client not initialized properly: {lsp_client.state}")
                    return False
                
                # Test with shorter timeout
                original_timeout = lsp_client._request_timeout
                lsp_client._request_timeout = 3.0  # 3 second timeout
                
                file_path = workspace_root / "codebase_tools.py"
                file_uri = file_path.as_uri()
                
                print(f"Testing find_definition on {file_uri}")
                print(f"Looking for CodebaseTools class at line 37")
                
                try:
                    # This should timeout if the issue exists
                    definitions = await lsp_client.get_definition(file_uri, 36, 6)  # 0-based
                    print(f"✅ LSP returned {len(definitions) if definitions else 0} definitions")
                    return True
                    
                except asyncio.TimeoutError as e:
                    print(f"❌ LSP timed out in 3 seconds: {e}")
                    return False
                except Exception as e:
                    print(f"❌ LSP failed with error: {e}")
                    return False
                finally:
                    lsp_client._request_timeout = original_timeout
                    
            finally:
                try:
                    await lsp_client.stop()
                except:
                    pass
        
        # Run the test
        result = asyncio.run(test_lsp_timeout())
        
        if not result:
            self.fail("LSP find_definition timed out - this reproduces the exact issue")


if __name__ == "__main__":
    unittest.main()
