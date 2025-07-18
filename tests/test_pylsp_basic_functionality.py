#!/usr/bin/env python3

"""
Test basic pylsp functionality with simple Python code to verify it works.
This helps isolate whether pylsp works on simple code vs complex codebases.
"""

import asyncio
import tempfile
import unittest
from pathlib import Path

from async_lsp_client import AsyncLSPClient
from lsp_server_factory import LSPServerFactory
from lsp_server_manager import LSPServerManager


class TestPylspBasicFunctionality(unittest.TestCase):
    """Test pylsp on simple Python code."""

    def test_pylsp_on_simple_code(self):
        """Test that pylsp works on very simple Python code."""
        print(f"\\nTesting pylsp on simple Python code")
        
        async def test_simple_pylsp():
            with tempfile.TemporaryDirectory() as temp_dir:
                workspace = Path(temp_dir)
                
                # Create a very simple Python file
                simple_file = workspace / "simple.py"
                simple_file.write_text("""
class SimpleClass:
    def __init__(self):
        self.value = 42
    
    def get_value(self):
        return self.value

def simple_function():
    obj = SimpleClass()
    return obj.get_value()
""")
                
                # Create pylsp manager
                import sys
                server_manager = LSPServerFactory.create_server_manager(
                    "pylsp", str(workspace), sys.executable
                )
                
                # Create LSP client manually with all required parameters
                import logging
                from async_lsp_client import LSPProtocol

                logger = logging.getLogger("test_pylsp")
                protocol = LSPProtocol(logger)
                
                lsp_client = AsyncLSPClient(
                    workspace_root=workspace,
                    server_manager=server_manager,
                    logger=logger,
                    protocol=protocol
                )
                
                try:
                    print(f"Starting pylsp...")
                    await lsp_client.start()
                    print(f"LSP client state: {lsp_client.state}")
                    
                    if lsp_client.state.name != "INITIALIZED":
                        print(f"❌ LSP not initialized: {lsp_client.state}")
                        return False
                    
                    # Test find_definition on SimpleClass
                    file_uri = simple_file.as_uri()
                    print(f"Testing find_definition on SimpleClass")
                    
                    # Set a short timeout to quickly identify issues
                    original_timeout = lsp_client._request_timeout
                    lsp_client._request_timeout = 10.0  # 10 second timeout
                    
                    try:
                        # Line 2 (0-based line 1), column 6 should be "SimpleClass"
                        definitions = await lsp_client.get_definition(file_uri, 1, 6)
                        print(f"✅ find_definition returned: {definitions}")
                        
                        if definitions and len(definitions) > 0:
                            print(f"✅ SUCCESS: Found {len(definitions)} definitions")
                            for def_item in definitions:
                                print(f"  - {def_item}")
                            return True
                        else:
                            print(f"⚠️  No definitions found, but no timeout")
                            return "no_results"
                            
                    except asyncio.TimeoutError:
                        print(f"❌ TIMEOUT: pylsp hung on simple code")
                        return False
                    except Exception as e:
                        print(f"❌ ERROR: {e}")
                        return False
                    finally:
                        lsp_client._request_timeout = original_timeout
                        
                finally:
                    try:
                        await lsp_client.stop()
                    except:
                        pass
        
        # Run the test
        result = asyncio.run(test_simple_pylsp())
        
        if result is True:
            print("✅ pylsp works correctly on simple code")
        elif result == "no_results":
            print("⚠️  pylsp doesn't timeout but returns no results on simple code")
        else:
            print("❌ pylsp fails even on simple code")
            self.fail(f"pylsp failed on simple code: {result}")


if __name__ == "__main__":
    unittest.main()
