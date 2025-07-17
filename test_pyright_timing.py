#!/usr/bin/env python3
"""
Test script to time Pyright operations and identify bottlenecks.
"""

import json
import subprocess
import sys
import time
from pathlib import Path


def test_pyright_timing():
    """Test different Pyright operations to identify the bottleneck."""
    print("=== Pyright Timing Test ===")
    
    # Test 1: Basic version check
    print("\n1. Testing version check...")
    start = time.time()
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pyright", "--version"],
            capture_output=True, text=True, timeout=10, check=True
        )
        elapsed = time.time() - start
        print(f"   Version check: {elapsed:.1f}s - {result.stdout.strip()}")
    except Exception as e:
        print(f"   Version check failed: {e}")
    
    # Test 2: Simple file check
    print("\n2. Testing simple file analysis...")
    test_file = Path("simple_test.py")
    test_file.write_text('print("hello")\n')
    
    start = time.time()
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pyright", str(test_file)],
            capture_output=True, text=True, timeout=30
        )
        elapsed = time.time() - start
        print(f"   Simple file analysis: {elapsed:.1f}s")
        if result.stdout:
            print(f"   Output: {result.stdout.strip()}")
    except subprocess.TimeoutExpired:
        elapsed = time.time() - start
        print(f"   Simple file analysis: TIMEOUT after {elapsed:.1f}s")
    except Exception as e:
        print(f"   Simple file analysis failed: {e}")
    finally:
        test_file.unlink(missing_ok=True)
    
    # Test 3: Project analysis with current config
    print("\n3. Testing project analysis with current config...")
    start = time.time()
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pyright", "."],
            capture_output=True, text=True, timeout=60
        )
        elapsed = time.time() - start
        print(f"   Project analysis: {elapsed:.1f}s")
        print(f"   Exit code: {result.returncode}")
        if result.stdout:
            print(f"   Stdout: {result.stdout[:200]}...")
        if result.stderr:
            print(f"   Stderr: {result.stderr[:200]}...")
    except subprocess.TimeoutExpired:
        elapsed = time.time() - start
        print(f"   Project analysis: TIMEOUT after {elapsed:.1f}s")
    except Exception as e:
        print(f"   Project analysis failed: {e}")
    
    # Test 4: Language server test
    print("\n4. Testing language server startup...")
    langserver_path = Path(".venv/bin/pyright-langserver")
    if langserver_path.exists():
        start = time.time()
        try:
            proc = subprocess.Popen(
                [str(langserver_path), "--stdio"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=False
            )
            time.sleep(1)  # Give it a moment
            proc.terminate()
            proc.wait(timeout=5)
            elapsed = time.time() - start
            print(f"   Language server startup: {elapsed:.1f}s")
        except Exception as e:
            print(f"   Language server test failed: {e}")
    else:
        print("   Language server not found")


if __name__ == "__main__":
    test_pyright_timing()
