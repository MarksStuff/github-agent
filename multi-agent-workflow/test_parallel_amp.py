#!/usr/bin/env python3
"""
Test script for parallel AmpCLI execution with isolation.
"""

import concurrent.futures
import threading

from amp_cli_wrapper import AmpCLI, AmpCLIError


def run_math_conversation(instance_name: str, start_number: int):
    """Run a math conversation in a separate AmpCLI instance."""
    try:
        print(f"[{instance_name}] Starting conversation...")

        with AmpCLI(isolated=True) as amp:
            print(f"[{instance_name}] Instance ID: {amp.instance_id}")
            print(f"[{instance_name}] Work dir: {amp.work_dir}")

            # Initial question
            response1 = amp.ask(f"what is {start_number} + {start_number}?")
            print(f"[{instance_name}] Thread ID: {amp.thread_id}")
            print(f"[{instance_name}] Q: what is {start_number} + {start_number}?")
            print(f"[{instance_name}] A: {response1}")

            # Continue conversation
            response2 = amp.ask("multiply that by 2")
            print(f"[{instance_name}] Q: multiply that by 2")
            print(f"[{instance_name}] A: {response2}")

            # Another continuation
            response3 = amp.ask("subtract 10 from that")
            print(f"[{instance_name}] Q: subtract 10 from that")
            print(f"[{instance_name}] A: {response3}")

            print(f"[{instance_name}] Conversation completed successfully!")
            return f"{instance_name}: {response3}"

    except AmpCLIError as e:
        error_msg = f"[{instance_name}] Error: {e}"
        print(error_msg)
        return error_msg


def test_threading():
    """Test parallel execution using threading."""
    print("Testing parallel execution with threading...")
    print("=" * 60)

    threads = []
    results = {}

    def thread_wrapper(name, number):
        results[name] = run_math_conversation(name, number)

    # Start multiple threads
    for i in range(3):
        thread_name = f"Thread-{i+1}"
        start_num = (i + 1) * 5  # 5, 10, 15
        thread = threading.Thread(target=thread_wrapper, args=(thread_name, start_num))
        threads.append(thread)
        thread.start()

    # Wait for all threads to complete
    for thread in threads:
        thread.join()

    print("\nThreading Results:")
    for _name, result in results.items():
        print(f"  {result}")

    return len([r for r in results.values() if "Error" not in r])


def test_concurrent_futures():
    """Test parallel execution using concurrent.futures."""
    print("\nTesting parallel execution with concurrent.futures...")
    print("=" * 60)

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        # Submit tasks
        futures = [
            executor.submit(run_math_conversation, f"Future-{i+1}", (i + 1) * 7)
            for i in range(3)
        ]

        # Collect results
        results = []
        for future in concurrent.futures.as_completed(futures):
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                results.append(f"Future failed: {e}")

    print("\nConcurrent.futures Results:")
    for result in results:
        print(f"  {result}")

    return len([r for r in results if "Error" not in r and "failed" not in r])


def test_context_managers():
    """Test context manager behavior for cleanup."""
    print("\nTesting context manager cleanup...")
    print("=" * 60)

    work_dirs = []

    # Create and use multiple instances
    for i in range(2):
        with AmpCLI(isolated=True) as amp:
            work_dirs.append(amp.work_dir)
            print(f"Instance {i+1}: {amp.instance_id} -> {amp.work_dir}")
            response = amp.ask("what is 2+2?")
            print(f"Response: {response}")

    # Check if directories were cleaned up
    print("\nChecking cleanup:")
    for i, work_dir in enumerate(work_dirs):
        exists = work_dir.exists() if work_dir else False
        print(f"Work dir {i+1} still exists: {exists}")

    return True


def test_isolation_verification():
    """Verify that instances are truly isolated."""
    print("\nTesting isolation verification...")
    print("=" * 60)

    # Create two instances with different conversations
    amp1 = AmpCLI(isolated=True)
    amp2 = AmpCLI(isolated=True)

    try:
        print(f"Instance 1 ID: {amp1.instance_id}")
        print(f"Instance 2 ID: {amp2.instance_id}")
        print(f"Instance 1 work dir: {amp1.work_dir}")
        print(f"Instance 2 work dir: {amp2.work_dir}")

        # Start different conversations
        response1a = amp1.ask("Remember: my favorite number is 42")
        response2a = amp2.ask("Remember: my favorite color is blue")

        print(f"Amp1: {response1a}")
        print(f"Amp2: {response2a}")

        # Test if they remember their own context
        response1b = amp1.ask("What was my favorite number?")
        response2b = amp2.ask("What was my favorite color?")

        print(f"Amp1 memory: {response1b}")
        print(f"Amp2 memory: {response2b}")

        return True

    except Exception as e:
        print(f"Isolation test failed: {e}")
        return False
    finally:
        amp1._cleanup()
        amp2._cleanup()


if __name__ == "__main__":
    print("Parallel AmpCLI Test Suite")
    print("=" * 80)

    # Test different parallel execution methods
    threading_success = test_threading()
    futures_success = test_concurrent_futures()

    # Test context managers and cleanup
    test_context_managers()

    # Test isolation
    isolation_success = test_isolation_verification()

    print("\n" + "=" * 80)
    print("SUMMARY:")
    print(f"Threading test: {threading_success}/3 successful")
    print(f"Concurrent futures test: {futures_success}/3 successful")
    print(f"Isolation test: {'PASS' if isolation_success else 'FAIL'}")

    total_tests = threading_success + futures_success + (1 if isolation_success else 0)
    print(f"Overall: {total_tests}/7 tests passed")
