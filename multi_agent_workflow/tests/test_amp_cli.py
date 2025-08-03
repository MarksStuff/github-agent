#!/usr/bin/env python3
"""Test script to verify AmpCLI is working correctly."""

import logging
import sys
from pathlib import Path

# Add parent directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from amp_cli_wrapper import AmpCLI, AmpCLIError

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def test_basic_amp():
    """Test basic AmpCLI functionality."""
    logger.info("Testing basic AmpCLI...")

    try:
        amp = AmpCLI()
        response = amp.ask("What is 2+2?")
        logger.info(f"Basic response: {response}")
        logger.info(f"Response length: {len(response)}")

        if not response:
            logger.error("Empty response from AmpCLI!")
            return False

        return True
    except AmpCLIError as e:
        logger.error(f"AmpCLI error: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return False


def test_with_system_prompt():
    """Test AmpCLI with system prompt."""
    logger.info("Testing AmpCLI with system prompt...")

    try:
        amp = AmpCLI(system_prompt="You are a helpful assistant. Be concise.")
        response = amp.ask("Explain what SQLite is in one sentence.")
        logger.info(f"System prompt response: {response}")
        logger.info(f"Response length: {len(response)}")

        if not response:
            logger.error("Empty response from AmpCLI with system prompt!")
            return False

        return True
    except AmpCLIError as e:
        logger.error(f"AmpCLI error: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return False


def test_long_prompt():
    """Test AmpCLI with a longer prompt similar to peer review."""
    logger.info("Testing AmpCLI with long prompt...")

    prompt = """You are reviewing peer analyses as a Software Architect.

FEATURE: Persist comment replies in database

PEER ANALYSES TO REVIEW:

--- Developer Analysis ---
Simple SQLite table with comment_id and timestamp.
Quick implementation using existing database infrastructure.

--- Tester Analysis ---
Need comprehensive tests for concurrent access.
Test edge cases and error scenarios.

REVIEW REQUIREMENTS:
1. Do the approaches align with good architectural principles?
2. Are there any conflicts between the analyses?
3. What improvements would you suggest?

Please provide a brief architectural review."""

    try:
        amp = AmpCLI()
        response = amp.ask(prompt)
        logger.info(
            f"Long prompt response preview: {response[:200] if response else 'None'}..."
        )
        logger.info(f"Response length: {len(response) if response else 0}")

        if not response:
            logger.error("Empty response from AmpCLI with long prompt!")
            return False

        return True
    except AmpCLIError as e:
        logger.error(f"AmpCLI error: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    logger.info("Starting AmpCLI tests...")

    tests = [
        ("Basic", test_basic_amp),
        ("System Prompt", test_with_system_prompt),
        ("Long Prompt", test_long_prompt),
    ]

    results = []
    for name, test_func in tests:
        logger.info(f"\n--- Running {name} Test ---")
        success = test_func()
        results.append((name, success))
        logger.info(f"{name} Test: {'PASSED' if success else 'FAILED'}")

    logger.info("\n--- Test Summary ---")
    for name, success in results:
        logger.info(f"{name}: {'✓' if success else '✗'}")

    all_passed = all(success for _, success in results)
    logger.info(
        f"\nOverall: {'All tests passed!' if all_passed else 'Some tests failed!'}"
    )
