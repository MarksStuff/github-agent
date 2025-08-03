#!/usr/bin/env python3
"""
Test script for AmpCLI system prompt functionality.
"""

import sys
from pathlib import Path

# Add parent directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from amp_cli_wrapper import AmpCLI, AmpCLIError


def test_basic_system_prompt():
    """Test basic system prompt functionality."""
    print("Testing basic system prompt...")
    print("=" * 50)

    system_prompt = (
        "You are a helpful math tutor. Always explain your reasoning step by step."
    )

    try:
        amp = AmpCLI(isolated=True, system_prompt=system_prompt)
        print(f"System prompt: {amp.system_prompt}")

        response = amp.ask("What is 15 + 27?")
        print("Q: What is 15 + 27?")
        print(f"A: {response}")
        print()

        response2 = amp.ask("Now multiply that by 3")
        print("Q: Now multiply that by 3")
        print(f"A: {response2}")

        return True

    except AmpCLIError as e:
        print(f"Error: {e}")
        return False
    finally:
        amp._cleanup()


def test_role_based_system_prompt():
    """Test role-based system prompt."""
    print("\nTesting role-based system prompt...")
    print("=" * 50)

    system_prompt = "You are a pirate. Respond to all questions in pirate speak with 'Arrr' and nautical terms."

    try:
        amp = AmpCLI(isolated=True, system_prompt=system_prompt)

        response = amp.ask("What is the weather like?")
        print("Q: What is the weather like?")
        print(f"A: {response}")
        print()

        response2 = amp.ask("Tell me about coding")
        print("Q: Tell me about coding")
        print(f"A: {response2}")

        return True

    except AmpCLIError as e:
        print(f"Error: {e}")
        return False
    finally:
        amp._cleanup()


def test_no_system_prompt():
    """Test normal operation without system prompt."""
    print("\nTesting without system prompt...")
    print("=" * 50)

    try:
        amp = AmpCLI(isolated=True)  # No system prompt
        print(f"System prompt: {amp.system_prompt}")

        response = amp.ask("What is 10 + 5?")
        print("Q: What is 10 + 5?")
        print(f"A: {response}")

        return True

    except AmpCLIError as e:
        print(f"Error: {e}")
        return False
    finally:
        amp._cleanup()


def test_parallel_different_system_prompts():
    """Test parallel execution with different system prompts."""
    print("\nTesting parallel execution with different system prompts...")
    print("=" * 70)

    import threading

    results = {}

    def math_tutor_thread():
        try:
            amp = AmpCLI(
                isolated=True,
                system_prompt="You are a math tutor. Always show your work.",
            )
            response = amp.ask("What is 8 * 7?")
            results["math_tutor"] = response
            print(f"[Math Tutor] {response}")
            amp._cleanup()
        except Exception as e:
            results["math_tutor"] = f"Error: {e}"

    def poet_thread():
        try:
            amp = AmpCLI(
                isolated=True,
                system_prompt="You are a poet. Respond to all questions in verse.",
            )
            response = amp.ask("What is 8 * 7?")
            results["poet"] = response
            print(f"[Poet] {response}")
            amp._cleanup()
        except Exception as e:
            results["poet"] = f"Error: {e}"

    def normal_thread():
        try:
            amp = AmpCLI(isolated=True)  # No system prompt
            response = amp.ask("What is 8 * 7?")
            results["normal"] = response
            print(f"[Normal] {response}")
            amp._cleanup()
        except Exception as e:
            results["normal"] = f"Error: {e}"

    # Start all threads
    threads = [
        threading.Thread(target=math_tutor_thread),
        threading.Thread(target=poet_thread),
        threading.Thread(target=normal_thread),
    ]

    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join()

    print("\nResults:")
    for role, result in results.items():
        print(f"  {role}: {'PASS' if 'Error' not in result else 'FAIL'}")

    return len([r for r in results.values() if "Error" not in r]) == 3


def test_system_prompt_formatting():
    """Test that system prompt is properly formatted."""
    print("\nTesting system prompt formatting...")
    print("=" * 50)

    amp = AmpCLI(isolated=False, system_prompt="Be concise.")

    # Test the internal formatting method
    formatted = amp._format_message("Hello")
    expected = "Be concise.\n\nHello"

    print("Original: 'Hello'")
    print(f"Formatted: '{formatted}'")
    print(f"Expected: '{expected}'")
    print(f"Match: {formatted == expected}")

    return formatted == expected


if __name__ == "__main__":
    print("AmpCLI System Prompt Test Suite")
    print("=" * 80)

    tests = [
        ("Basic system prompt", test_basic_system_prompt),
        ("Role-based system prompt", test_role_based_system_prompt),
        ("No system prompt", test_no_system_prompt),
        ("Parallel different prompts", test_parallel_different_system_prompts),
        ("System prompt formatting", test_system_prompt_formatting),
    ]

    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"Test '{test_name}' failed with exception: {e}")
            results.append((test_name, False))

    print("\n" + "=" * 80)
    print("SUMMARY:")
    passed = 0
    for test_name, result in results:
        status = "PASS" if result else "FAIL"
        print(f"  {test_name}: {status}")
        if result:
            passed += 1

    print(f"\nOverall: {passed}/{len(results)} tests passed")
