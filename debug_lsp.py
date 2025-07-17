#!/usr/bin/env python3
"""
LSP Debugging Script
Run this in production to diagnose LSP server initialization issues.
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path


def check_environment():
    """Check the production environment setup."""
    print("=== Environment Check ===")
    print(f"Current directory: {os.getcwd()}")
    print(f"Python executable: {sys.executable}")
    print(f"Python version: {sys.version}")
    print(f"Working directory contents:")
    for item in sorted(Path(".").iterdir()):
        print(f"  {item}")
    print()


def check_pyright_config():
    """Check pyrightconfig.json."""
    print("=== Pyright Configuration ===")
    config_path = Path("pyrightconfig.json")
    print(f"pyrightconfig.json exists: {config_path.exists()}")
    
    if config_path.exists():
        try:
            config = json.loads(config_path.read_text())
            print("Configuration:")
            print(json.dumps(config, indent=2))
            
            # Check if pythonPath exists
            python_path = Path(config.get("pythonPath", ""))
            print(f"Configured Python path exists: {python_path.exists()}")
            if python_path.exists():
                print(f"Python path: {python_path.absolute()}")
        except Exception as e:
            print(f"Error reading config: {e}")
    print()


def check_pyright_availability():
    """Check if Pyright is available and working."""
    print("=== Pyright Availability ===")
    
    # Check pip-installed version first
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pyright", "--version"],
            capture_output=True, text=True, timeout=10, check=True
        )
        print(f"Pyright (pip): {result.stdout.strip()}")
    except subprocess.TimeoutExpired:
        print("Pyright (pip): TIMEOUT")
    except subprocess.CalledProcessError as e:
        print(f"Pyright (pip): ERROR - {e}")
    except FileNotFoundError:
        print("Pyright (pip): NOT FOUND")
    
    # Check global version
    try:
        result = subprocess.run(
            ["pyright", "--version"],
            capture_output=True, text=True, timeout=10, check=True
        )
        print(f"Pyright (global): {result.stdout.strip()}")
    except subprocess.TimeoutExpired:
        print("Pyright (global): TIMEOUT")
    except subprocess.CalledProcessError as e:
        print(f"Pyright (global): ERROR - {e}")
    except FileNotFoundError:
        print("Pyright (global): NOT FOUND")
    
    # Check pyright-langserver
    venv_langserver = Path(".venv/bin/pyright-langserver")
    print(f"pyright-langserver exists: {venv_langserver.exists()}")
    if venv_langserver.exists():
        print(f"pyright-langserver path: {venv_langserver.absolute()}")
    print()


def test_pyright_basic():
    """Test basic Pyright functionality."""
    print("=== Pyright Basic Test ===")
    
    # Create a simple test file
    test_file = Path("test_pyright.py")
    test_file.write_text('print("hello world")\n')
    
    try:
        # Try to run pyright on the test file
        result = subprocess.run(
            [sys.executable, "-m", "pyright", str(test_file)],
            capture_output=True, text=True, timeout=30
        )
        print(f"Pyright test exit code: {result.returncode}")
        if result.stdout:
            print(f"Stdout: {result.stdout}")
        if result.stderr:
            print(f"Stderr: {result.stderr}")
    except subprocess.TimeoutExpired:
        print("Pyright test: TIMEOUT (30s)")
    except Exception as e:
        print(f"Pyright test error: {e}")
    finally:
        # Clean up
        test_file.unlink(missing_ok=True)
    print()


def test_langserver_start():
    """Test if the language server can start."""
    print("=== Language Server Start Test ===")
    
    venv_langserver = Path(".venv/bin/pyright-langserver")
    if not venv_langserver.exists():
        print("pyright-langserver not found, skipping test")
        return
    
    try:
        # Try to start the language server briefly
        proc = subprocess.Popen(
            [str(venv_langserver), "--stdio"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=False,
            cwd="."
        )
        
        # Give it a moment to start
        time.sleep(2)
        
        # Check if it's running
        if proc.poll() is None:
            print("Language server started successfully")
            proc.terminate()
            proc.wait(timeout=5)
        else:
            print(f"Language server exited immediately with code: {proc.returncode}")
            if proc.stderr:
                stderr = proc.stderr.read().decode('utf-8', errors='replace')
                print(f"Stderr: {stderr}")
                
    except Exception as e:
        print(f"Language server test error: {e}")
    print()


def main():
    """Run all diagnostic checks."""
    print("LSP Diagnostic Script")
    print("=" * 50)
    
    check_environment()
    check_pyright_config()
    check_pyright_availability()
    test_pyright_basic()
    test_langserver_start()
    
    print("Diagnostic complete. Please share this output for debugging.")


if __name__ == "__main__":
    main()
