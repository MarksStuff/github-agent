#!/usr/bin/env python3
"""
Example usage of the Claude Code Python wrapper
"""

import json

from claude_code_wrapper import run_claude_code, run_claude_code_with_file_output


def example_basic_prompt():
    """Example: Basic prompt execution"""
    print("=== Example 1: Basic Prompt ===")

    result = run_claude_code(
        prompt="List all Python files in the current directory and show their sizes",
        system_prompt_append="Format file sizes in human-readable format (KB/MB)",
    )

    if result["success"]:
        print("Claude Code output:")
        print(result["output"])
    else:
        print(f"Error: {result['error']}")
    print()


def example_code_generation():
    """Example: Generate code and retrieve it"""
    print("=== Example 2: Code Generation ===")

    result = run_claude_code_with_file_output(
        prompt="Create a Python module for data validation with functions to validate email, phone numbers, and URLs. Save it as validators.py",
        output_file="validators.py",
        system_prompt_append="Use regex for validation. Include comprehensive docstrings and type hints.",
    )

    if result["success"]:
        print("Claude Code executed successfully!")
        if result.get("file_content"):
            print("\nGenerated code:")
            print("-" * 50)
            print(result["file_content"])
            print("-" * 50)
    else:
        print(f"Error: {result['error']}")
    print()


def example_analysis_task():
    """Example: Analyze code and return results"""
    print("=== Example 3: Code Analysis ===")

    # First, let's create a sample file to analyze
    sample_code = """
def calculate_average(numbers):
    total = 0
    for num in numbers:
        total += num
    return total / len(numbers)

def find_max(numbers):
    max_num = numbers[0]
    for num in numbers:
        if num > max_num:
            max_num = num
    return max_num
"""

    with open("sample_analysis.py", "w") as f:
        f.write(sample_code)

    result = run_claude_code(
        prompt="Analyze the file sample_analysis.py and provide a JSON report with: 1) List of functions, 2) Potential improvements, 3) Missing error handling. Output only the JSON.",
        system_prompt_append="Output should be valid JSON only, no additional text or markdown formatting.",
    )

    if result["success"]:
        try:
            # Try to parse the JSON output
            analysis = json.loads(result["output"])
            print("Analysis results:")
            print(json.dumps(analysis, indent=2))
        except json.JSONDecodeError:
            print("Raw output (not valid JSON):")
            print(result["output"])
    else:
        print(f"Error: {result['error']}")
    print()


def example_multi_file_task():
    """Example: Complex task with multiple files"""
    print("=== Example 4: Multi-file Task ===")

    result = run_claude_code(
        prompt="""Create a simple REST API client module with the following:
        1. A base APIClient class in api_client.py
        2. Example usage in example_usage.py
        3. Unit tests in test_api_client.py
        Focus on GET and POST methods with proper error handling.""",
        system_prompt_append="Use the requests library. Include proper logging. Follow PEP 8 standards.",
        timeout=600,  # Longer timeout for complex tasks
    )

    if result["success"]:
        print("Multi-file task completed successfully!")
        print("\nClaude Code output:")
        print(
            result["output"][:500] + "..."
            if len(result["output"]) > 500
            else result["output"]
        )
    else:
        print(f"Error: {result['error']}")


if __name__ == "__main__":
    # Run examples
    example_basic_prompt()
    example_code_generation()
    example_analysis_task()
    example_multi_file_task()
