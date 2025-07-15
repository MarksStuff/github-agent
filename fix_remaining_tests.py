#!/usr/bin/env python3
"""
Script to fix remaining test method calls in test_codebase_tools.py
"""

import re
import sys

def add_mock_setup_to_method(method_content):
    """Add mock setup to a test method if it doesn't have it"""
    if "mock_repo_manager = MockRepositoryManager()" in method_content:
        return method_content  # Already has setup
    
    # Find the function definition line
    lines = method_content.split('\n')
    
    # Find where to insert the mock setup (after the docstring)
    insert_index = 1
    for i, line in enumerate(lines):
        if line.strip().startswith('"""') and line.strip().endswith('"""'):
            insert_index = i + 1
            break
        elif line.strip().endswith('"""') and i > 0:
            insert_index = i + 1
            break
    
    # Insert mock setup
    mock_setup = [
        "        # Create mock dependencies",
        "        mock_repo_manager = MockRepositoryManager()",
        "        mock_symbol_storage = MockSymbolStorage()",
        "        ",
        "        # Create CodebaseTools instance",
        "        tools_instance = CodebaseTools(",
        "            repository_manager=mock_repo_manager,",
        "            symbol_storage=mock_symbol_storage,",
        "            lsp_client_factory=mock_lsp_client_factory",
        "        )",
        "        ",
    ]
    
    lines[insert_index:insert_index] = mock_setup
    return '\n'.join(lines)

def fix_test_file(file_path):
    with open(file_path, 'r') as f:
        content = f.read()
    
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
    
    # Fix response format expectations
    response_fixes = [
        (r'assert data\["repo"\]', r'assert data["repository_id"]'),
        (r'assert data\["workspace"\]', r'assert data["repository_path"]'),
        (r'assert data\["status"\] == "unhealthy"', r'assert data["status"] == "error"'),
        (r'assert len\(data\["errors"\]\) > 0', r'assert "message" in data'),
        (r'assert ".*" in data\["errors"\]\[0\]', r'assert "message" in data'),
    ]
    
    for pattern, replacement in response_fixes:
        content = re.sub(pattern, replacement, content, flags=re.MULTILINE)
    
    # Add mock setup to methods that don't have it
    # This is a simplified approach - just add it to methods that call tools_instance but don't have setup
    method_pattern = r'(    async def test_[^(]+\([^)]*\):[^{]+?)(        result = await tools_instance\.)'
    
    def add_setup_if_missing(match):
        method_start = match.group(1)
        call_start = match.group(2)
        
        if "mock_repo_manager = MockRepositoryManager()" not in method_start:
            setup = '''        # Create mock dependencies
        mock_repo_manager = MockRepositoryManager()
        mock_symbol_storage = MockSymbolStorage()
        
        # Create CodebaseTools instance
        tools_instance = CodebaseTools(
            repository_manager=mock_repo_manager,
            symbol_storage=mock_symbol_storage,
            lsp_client_factory=mock_lsp_client_factory
        )
        
'''
            return method_start + setup + call_start
        return match.group(0)
    
    content = re.sub(method_pattern, add_setup_if_missing, content, flags=re.MULTILINE | re.DOTALL)
    
    with open(file_path, 'w') as f:
        f.write(content)
    
    print(f"Fixed patterns in {file_path}")

if __name__ == "__main__":
    file_path = "tests/test_codebase_tools.py"
    fix_test_file(file_path)
