#!/usr/bin/env python3

"""
Test different LSP operations to determine if timeout is specific 
to textDocument/definition or affects other operations.
"""

import asyncio
import sys
import unittest
from pathlib import Path

from async_lsp_client import AsyncLSPClient


class TestLSPOperationsTimeout(unittest.TestCase):
    """Test various LSP operations for timeout issues."""

    def test_multiple_lsp_operations(self):
        """Test various LSP operations to isolate the timeout issue."""
        print(f"\\nTesting multiple LSP operations for timeout behavior")
        
        workspace_root = Path("/Volumes/Code/github-agent")
        
        async def test_lsp_operations():
            # Create LSP client directly using correct constructor
            import sys
            import logging
            from lsp_server_factory import LSPServerFactory
            from async_lsp_client import LSPProtocol
            
            server_manager = LSPServerFactory.create_server_manager(
                "pylsp", str(workspace_root), sys.executable
            )
            logger = logging.getLogger("test_lsp_operations")
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
                    return {}
                
                # Test with shorter timeout for all operations
                original_timeout = lsp_client._request_timeout
                lsp_client._request_timeout = 5.0  # 5 second timeout
                
                file_path = workspace_root / "codebase_tools.py"
                file_uri = file_path.as_uri()
                
                results = {}
                
                # Test 1: textDocument/definition (we know this times out)
                print(f"\\n1. Testing textDocument/definition...")
                try:
                    definitions = await lsp_client.get_definition(file_uri, 36, 6)  # 0-based
                    results["definition"] = f"✅ Success: {len(definitions) if definitions else 0} definitions"
                except asyncio.TimeoutError:
                    results["definition"] = "❌ Timeout after 5 seconds"
                except Exception as e:
                    results["definition"] = f"❌ Error: {e}"
                
                # Test 2: textDocument/hover
                print(f"2. Testing textDocument/hover...")
                try:
                    hover = await lsp_client.get_hover(file_uri, 36, 6)
                    results["hover"] = f"✅ Success: {bool(hover)}"
                except asyncio.TimeoutError:
                    results["hover"] = "❌ Timeout after 5 seconds"
                except Exception as e:
                    results["hover"] = f"❌ Error: {e}"
                
                # Test 3: textDocument/references
                print(f"3. Testing textDocument/references...")
                try:
                    references = await lsp_client.get_references(file_uri, 36, 6)
                    results["references"] = f"✅ Success: {len(references) if references else 0} references"
                except asyncio.TimeoutError:
                    results["references"] = "❌ Timeout after 5 seconds"
                except Exception as e:
                    results["references"] = f"❌ Error: {e}"
                
                # Test 4: textDocument/documentSymbol
                print(f"4. Testing textDocument/documentSymbol...")
                try:
                    symbols = await lsp_client.get_document_symbols(file_uri)
                    results["documentSymbol"] = f"✅ Success: {len(symbols) if symbols else 0} symbols"
                except asyncio.TimeoutError:
                    results["documentSymbol"] = "❌ Timeout after 5 seconds"
                except Exception as e:
                    results["documentSymbol"] = f"❌ Error: {e}"
                
                # Test 5: A simple request that should work
                print(f"5. Testing a workspace request...")
                try:
                    # Try to send a simple request to see if communication works at all
                    # Let's try a manual request to see the server response
                    request = lsp_client.protocol.create_request("workspace/workspaceFolders", None)
                    response_future = asyncio.Future()
                    lsp_client._pending_requests[request["id"]] = response_future
                    
                    await lsp_client._send_message(request)
                    response = await asyncio.wait_for(response_future, timeout=5.0)
                    
                    results["workspace"] = "✅ Success: Basic communication works"
                except asyncio.TimeoutError:
                    results["workspace"] = "❌ Timeout after 5 seconds"
                except Exception as e:
                    results["workspace"] = f"❌ Error: {e}"
                finally:
                    # Clean up the pending request
                    lsp_client._pending_requests.pop(request["id"], None)
                
                lsp_client._request_timeout = original_timeout
                return results
                    
            finally:
                try:
                    await lsp_client.stop()
                except:
                    pass
        
        # Run the test
        results = asyncio.run(test_lsp_operations())
        
        print(f"\\n=== LSP Operation Results ===")
        for operation, result in results.items():
            print(f"{operation}: {result}")
        
        # Analyze results
        timeouts = [op for op, result in results.items() if "Timeout" in result]
        successes = [op for op, result in results.items() if "Success" in result]
        
        print(f"\\n=== Analysis ===")
        print(f"Operations that timed out: {timeouts}")
        print(f"Operations that succeeded: {successes}")
        
        if timeouts:
            if len(timeouts) == len(results):
                print("❌ ALL operations timed out - LSP server communication is broken")
            elif "definition" in timeouts and len(timeouts) == 1:
                print("❌ Only textDocument/definition times out - specific issue with definition requests")
            else:
                print(f"❌ Multiple operations timeout: {timeouts}")
                
        # Don't fail the test - we want to see the results
        return results


if __name__ == "__main__":
    unittest.main()
