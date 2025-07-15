#!/usr/bin/env python3
"""
Script to fix remaining test method calls in test_codebase_tools.py
"""

import re
import sys

def fix_test_file(file_path):
    with open(file_path, 'r') as f:
        content = f.read()
    
    # First, let's find all the remaining methods that need fixing
    # by looking for codebase_tools.execute_* calls
    
    # Pattern to match method definitions that need fixing
    patterns_to_fix = [
        (r'result = await tools_instance\.execute_codebase_health_check\(([^)]+)\)', 
         r'result = await tools_instance.codebase_health_check(\1)'),
        (r'result = await tools_instance\.execute_search_symbols\(([^)]+)\)', 
         r'result = await tools_instance.search_symbols(\1)'),
        (r'result = await codebase_tools\.execute_codebase_health_check\(([^)]+)\)', 
         r'result = await tools_instance.codebase_health_check(\1)'),
        (r'result = await codebase_tools\.execute_search_symbols\(([^)]+)\)', 
         r'result = await tools_instance.search_symbols(\1)'),
        (r'result = await codebase_tools\.execute_tool\(([^)]+)\)', 
         r'result = await tools_instance.execute_tool(\1)'),
        (r'tools = codebase_tools\.get_tools\(([^)]+)\)', 
         r'tools = tools_instance.get_tools(\1)'),
        (r'codebase_tools\.TOOL_HANDLERS', 
         r'tools_instance.TOOL_HANDLERS'),
    ]
    
    for pattern, replacement in patterns_to_fix:
        content = re.sub(pattern, replacement, content, flags=re.MULTILINE)
    
    # Also need to add the mock setup for methods that don't have it
    # This is more complex - let's focus on the basic replacements first
    
    with open(file_path, 'w') as f:
        f.write(content)
    
    print(f"Fixed patterns in {file_path}")

if __name__ == "__main__":
    file_path = "tests/test_codebase_tools.py"
    fix_test_file(file_path)
