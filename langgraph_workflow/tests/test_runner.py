"""Test runner for all LangGraph workflow tests."""

import sys
import unittest
from pathlib import Path

# Add the parent directory to the path so we can import the modules
sys.path.insert(0, str(Path(__file__).parent.parent))


def run_all_tests():
    """Run all tests and return results."""
    # Discover all tests in the tests directory
    loader = unittest.TestLoader()
    start_dir = Path(__file__).parent
    suite = loader.discover(start_dir, pattern="test_*.py")

    # Run tests with detailed output
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result


def run_specific_test_module(module_name):
    """Run tests for a specific module."""
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromName(f"test_{module_name}")

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result


def print_test_summary():
    """Print a summary of all test modules."""
    test_files = list(Path(__file__).parent.glob("test_*.py"))

    print("Available test modules:")
    print("=" * 50)

    for test_file in test_files:
        if test_file.name == "test_runner.py":
            continue

        module_name = test_file.stem
        print(f"- {module_name}")

        # Try to load and count tests
        try:
            loader = unittest.TestLoader()
            suite = loader.loadTestsFromName(module_name)
            test_count = suite.countTestCases()
            print(f"  Tests: {test_count}")
        except Exception as e:
            print(f"  Error loading: {e}")
        print()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run LangGraph workflow tests")
    parser.add_argument(
        "--module", help="Run specific test module (e.g., workflow_phases)"
    )
    parser.add_argument("--summary", action="store_true", help="Print test summary")
    parser.add_argument(
        "--coverage", action="store_true", help="Run with coverage reporting"
    )

    args = parser.parse_args()

    if args.summary:
        print_test_summary()
        sys.exit(0)

    if args.coverage:
        try:
            import coverage

            cov = coverage.Coverage()
            cov.start()
        except ImportError:
            print("Coverage.py not installed. Install with: pip install coverage")
            sys.exit(1)

    try:
        if args.module:
            result = run_specific_test_module(args.module)
        else:
            result = run_all_tests()

        if args.coverage:
            cov.stop()
            cov.save()

            print("\n" + "=" * 50)
            print("COVERAGE REPORT")
            print("=" * 50)
            cov.report()

        # Print summary
        print("\n" + "=" * 50)
        print("TEST SUMMARY")
        print("=" * 50)
        print(f"Tests run: {result.testsRun}")
        print(f"Failures: {len(result.failures)}")
        print(f"Errors: {len(result.errors)}")
        print(f"Skipped: {len(result.skipped)}")

        if result.failures:
            print("\nFAILURES:")
            for test, _ in result.failures:
                print(f"- {test}")

        if result.errors:
            print("\nERRORS:")
            for test, _ in result.errors:
                print(f"- {test}")

        # Exit with non-zero code if tests failed
        if result.failures or result.errors:
            sys.exit(1)
        else:
            print("\nAll tests passed! ✅")
            sys.exit(0)

    except KeyboardInterrupt:
        print("\nTests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"Error running tests: {e}")
        sys.exit(1)
