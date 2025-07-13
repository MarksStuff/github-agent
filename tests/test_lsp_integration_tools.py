#!/usr/bin/env python3

"""
Integration tests for LSP-based codebase tools.

These tests verify that the LSP tools work end-to-end with real Python files
and can be integrated into the MCP worker system.
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

import codebase_tools


class TestLSPToolsIntegration(unittest.TestCase):
    """Integration tests for LSP tools."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp_dir.name)
        self.python_path = sys.executable
        
        # Create a more complex test Python file
        self.test_file = self.workspace / "example.py"
        self.test_file.write_text("""
class Calculator:
    \"\"\"A simple calculator class.\"\"\"
    
    def __init__(self):
        self.result = 0
    
    def add(self, value):
        \"\"\"Add a value to the result.\"\"\"
        self.result += value
        return self.result
    
    def multiply(self, value):
        \"\"\"Multiply the result by a value.\"\"\"
        self.result *= value
        return self.result

def create_calculator():
    \"\"\"Factory function to create a calculator.\"\"\"
    return Calculator()

def main():
    calc = create_calculator()
    calc.add(5)
    calc.multiply(2)
    print(f"Final result: {calc.result}")

if __name__ == "__main__":
    main()
""")

    def tearDown(self):
        """Clean up test fixtures."""
        self.temp_dir.cleanup()

    def test_tool_registration(self):
        """Test that LSP tools are properly registered."""
        tools = codebase_tools.get_tools("test-repo", str(self.workspace))
        
        tool_names = [tool["name"] for tool in tools]
        self.assertIn("find_definition", tool_names)
        self.assertIn("find_references", tool_names)
        
        # Check tool schemas
        find_def_tool = next(tool for tool in tools if tool["name"] == "find_definition")
        self.assertIn("symbol", find_def_tool["inputSchema"]["properties"])
        self.assertIn("file_path", find_def_tool["inputSchema"]["properties"])
        self.assertIn("line", find_def_tool["inputSchema"]["properties"])
        self.assertIn("column", find_def_tool["inputSchema"]["properties"])
        
        find_refs_tool = next(tool for tool in tools if tool["name"] == "find_references")
        self.assertIn("symbol", find_refs_tool["inputSchema"]["properties"])
        self.assertIn("include_declaration", find_refs_tool["inputSchema"]["properties"])

    def test_tool_handlers_exist(self):
        """Test that tool handlers are properly registered."""
        self.assertIn("find_definition", codebase_tools.TOOL_HANDLERS)
        self.assertIn("find_references", codebase_tools.TOOL_HANDLERS)

    def test_execute_tool_dispatcher(self):
        """Test that tools can be executed through the dispatcher."""
        # This test doesn't actually execute LSP (would require pyright to be available)
        # but verifies that the tool dispatcher can route to our new tools
        
        import asyncio
        
        async def run_test():
            # Test unknown tool
            result_json = await codebase_tools.execute_tool("unknown_tool")
            result = json.loads(result_json)
            self.assertIn("error", result)
            self.assertIn("Unknown tool", result["error"])
            
            # Verify our tools are in the available tools list
            available_tools = result["available_tools"]
            self.assertIn("find_definition", available_tools)
            self.assertIn("find_references", available_tools)
        
        asyncio.run(run_test())

    def test_file_path_validation(self):
        """Test file path validation in tool execution."""
        # This test checks that file validation works correctly
        # without requiring a full LSP server
        
        from codebase_tools import _resolve_file_path
        
        # Test valid file path
        resolved = _resolve_file_path("example.py", str(self.workspace))
        # Use resolved paths for comparison to handle symlinks
        self.assertEqual(Path(resolved).resolve(), self.test_file.resolve())
        
        # Test path outside workspace
        with self.assertRaises(ValueError):
            _resolve_file_path("../outside.py", str(self.workspace))

    def test_coordinate_conversion(self):
        """Test coordinate conversion utilities."""
        from codebase_tools import (
            _lsp_position_to_user_friendly,
            _user_friendly_to_lsp_position,
        )
        
        # Test round-trip conversion
        user_pos = {"line": 10, "column": 5}
        lsp_pos = _user_friendly_to_lsp_position(user_pos["line"], user_pos["column"])
        back_to_user = _lsp_position_to_user_friendly(lsp_pos["line"], lsp_pos["character"])
        
        self.assertEqual(user_pos["line"], back_to_user["line"])
        self.assertEqual(user_pos["column"], back_to_user["column"])

    def test_uri_conversion(self):
        """Test URI conversion utilities."""
        from codebase_tools import _path_to_uri, _uri_to_path
        
        # Test round-trip conversion
        original_path = str(self.test_file)
        uri = _path_to_uri(original_path)
        back_to_path = _uri_to_path(uri)
        
        self.assertTrue(uri.startswith("file://"))
        self.assertEqual(original_path, back_to_path)


if __name__ == "__main__":
    unittest.main()
