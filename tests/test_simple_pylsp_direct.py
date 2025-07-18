#!/usr/bin/env python3

"""
Direct test of pylsp with AsyncLSPClient to isolate the hanging issue.

This bypasses the worker architecture and directly tests:
1. Can we start pylsp successfully?
2. Does find_definition work on simple code?
3. Does it hang or return results promptly?
"""

import asyncio
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from async_lsp_client import AsyncLSPClient
from lsp_jsonrpc import JSONRPCProtocol
from pylsp_manager import PylspManager


class TestSimplePylspDirect(unittest.TestCase):
    """Direct test of pylsp functionality."""

    def test_pylsp_direct_simple_code(self):
        """Test pylsp directly on simple Python code."""
        print(f"\\n🧪 Direct pylsp test on simple code")
        
        async def test_pylsp():
            with tempfile.TemporaryDirectory() as temp_dir:
                workspace = Path(temp_dir)
                
                # Create simple Python file
                test_file = workspace / "simple.py"
                test_file.write_text("""
class SimpleClass:
    def __init__(self):
        self.value = 42
    
    def get_value(self):
        return self.value

def create_instance():
    return SimpleClass()
""")
                
                print(f"📁 Created test file: {test_file}")
                
                # Create pylsp manager
                print(f"🔧 Creating pylsp manager...")
                pylsp_manager = PylspManager(str(workspace), sys.executable)
                print(f"✅ Pylsp manager created")
                
                # Create LSP client
                import logging
                from async_lsp_client import LSPProtocol
                
                logger = logging.getLogger("test_pylsp")
                logger.setLevel(logging.DEBUG)
                protocol = LSPProtocol(logger)
                
                lsp_client = AsyncLSPClient(
                    workspace_root=workspace,
                    server_manager=pylsp_manager,
                    logger=logger,
                    protocol=protocol
                )
                
                try:
                    print(f"🚀 Starting LSP client...")
                    start_time = time.time()
                    
                    # Enable debug logging to see what fails
                    logger.setLevel(logging.DEBUG)
                    handler = logging.StreamHandler()
                    handler.setLevel(logging.DEBUG)
                    formatter = logging.Formatter('%(levelname)s - %(name)s - %(message)s')
                    handler.setFormatter(formatter)
                    logger.addHandler(handler)
                    
                    await lsp_client.start()
                    init_time = time.time() - start_time
                    
                    print(f"⏱️  LSP initialization took {init_time:.2f} seconds")
                    print(f"📊 LSP client state: {lsp_client.state}")
                    
                    if lsp_client.state.name != "INITIALIZED":
                        # Check if there's a server process
                        if hasattr(lsp_client, '_server_process') and lsp_client._server_process:
                            process = lsp_client._server_process
                            print(f"📊 Server process PID: {process.pid}")
                            print(f"📊 Server process returncode: {process.returncode}")
                            
                            # Check stderr for errors
                            if process.stderr:
                                try:
                                    stderr_data = await process.stderr.read()
                                    if stderr_data:
                                        print(f"❌ Server stderr: {stderr_data.decode()}")
                                except:
                                    pass
                        else:
                            print(f"❌ No server process found")
                        
                        return f"❌ LSP not initialized: {lsp_client.state}"
                    
                    # Test find_definition on SimpleClass
                    file_uri = test_file.as_uri()
                    print(f"🔍 Testing find_definition on SimpleClass...")
                    print(f"📍 File URI: {file_uri}")
                    
                    # Test with timeout to detect hanging
                    start_time = time.time()
                    
                    try:
                        # Line 2 (0-based line 1), column 6 is "SimpleClass"
                        definitions = await asyncio.wait_for(
                            lsp_client.get_definition(file_uri, 1, 6),
                            timeout=10.0  # 10 second timeout
                        )
                        
                        elapsed = time.time() - start_time
                        print(f"⏱️  find_definition took {elapsed:.2f} seconds")
                        
                        if definitions:
                            print(f"✅ SUCCESS: Found {len(definitions)} definitions:")
                            for i, defn in enumerate(definitions):
                                print(f"  {i+1}. {defn}")
                            return "success"
                        else:
                            print(f"⚠️  No definitions found (but no timeout)")
                            return "no_results"
                            
                    except asyncio.TimeoutError:
                        elapsed = time.time() - start_time  
                        print(f"❌ TIMEOUT: find_definition hung for {elapsed:.2f} seconds")
                        return "timeout"
                    except Exception as e:
                        elapsed = time.time() - start_time
                        print(f"❌ ERROR after {elapsed:.2f} seconds: {e}")
                        return f"error: {e}"
                
                finally:
                    try:
                        print(f"🛑 Stopping LSP client...")
                        await lsp_client.stop()
                        print(f"✅ LSP client stopped")
                    except Exception as e:
                        print(f"⚠️  Error stopping LSP client: {e}")
        
        # Run the test
        result = asyncio.run(test_pylsp())
        
        print(f"\\n🏁 Test result: {result}")
        
        if result == "timeout":
            self.fail("pylsp hung on simple code - this reproduces the hanging issue")
        elif result.startswith("error"):
            self.fail(f"pylsp failed: {result}")
        elif result == "success":
            print("✅ pylsp works correctly on simple code!")
        else:
            print("⚠️  pylsp doesn't return definitions but doesn't hang")

    def test_pylsp_version_check(self):
        """Test that pylsp is available and working."""
        print(f"\\n🔧 Testing pylsp availability...")
        
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pylsp", "--version"],
                capture_output=True,
                text=True,
                check=True,
                timeout=5
            )
            print(f"✅ pylsp version: {result.stdout.strip()}")
        except Exception as e:
            print(f"❌ pylsp not available: {e}")
            self.fail(f"pylsp not available: {e}")


if __name__ == "__main__":
    unittest.main()
