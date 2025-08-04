#!/usr/bin/env python3
"""
Test script for the Amp CLI wrapper.
"""

import sys
from pathlib import Path

# Add parent directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from amp_cli_wrapper import AmpCLI, AmpCLIError  # noqa: E402


def test_conversation():
    """Test a complete conversation flow."""
    amp = AmpCLI()

    try:
        print("Testing Amp CLI wrapper...")
        print("=" * 40)

        # Test 1: Initial prompt
        print("Test 1: Initial prompt")
        response1 = amp.ask("what is 2+2?")
        print("Q: what is 2+2?")
        print(f"A: {response1}")
        print()

        # Test 2: Continue conversation
        print("Test 2: Continue conversation")
        response2 = amp.ask("add 5 to that")
        print("Q: add 5 to that")
        print(f"A: {response2}")
        print()

        # Test 3: Another continuation
        print("Test 3: Another continuation")
        response3 = amp.ask("now minus 3")
        print("Q: now minus 3")
        print(f"A: {response3}")
        print()

        # Test 4: Reset and start new conversation
        print("Test 4: Reset conversation")
        amp.reset_conversation()
        response4 = amp.ask("what is 10 * 3?")
        print("Q: what is 10 * 3?")
        print(f"A: {response4}")
        print()

        print("All tests completed successfully!")

    except AmpCLIError as e:
        print(f"Error: {e}")
        return False

    return True


def test_explicit_methods():
    """Test explicit prompt and continue methods."""
    amp = AmpCLI()

    try:
        print("Testing explicit methods...")
        print("=" * 40)

        # Start with prompt
        response1 = amp.prompt("Hello, can you help me with math?")
        print(f"Initial: {response1}")

        # Continue explicitly
        response2 = amp.continue_conversation("What is 7 + 8?")
        print(f"Continue: {response2}")

        print("Explicit method tests completed!")

    except AmpCLIError as e:
        print(f"Error: {e}")
        return False

    return True


if __name__ == "__main__":
    print("Amp CLI Wrapper Test Suite")
    print("=" * 50)

    # Test conversation flow
    test_conversation()
    print()

    # Test explicit methods
    test_explicit_methods()
