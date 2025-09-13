"""Startup validation for LangGraph workflow dependencies.

This module provides functions to validate that required services and API keys
are available before running the workflow.
"""

import os
import sys
from pathlib import Path
from typing import Any

import requests


def validate_environment_variables() -> dict[str, Any]:
    """Validate required environment variables are set.

    Returns:
        dict: Validation results with status and messages
    """
    results: dict[str, Any] = {
        "valid": True,
        "warnings": [],
        "errors": [],
        "services": {
            "anthropic": False,
            "ollama": False,
            "github": False,
        },
    }

    # Check Claude CLI availability (preferred) or Anthropic API key (fallback)
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")

    # Try Claude CLI first
    try:
        import subprocess

        result = subprocess.run(
            ["claude", "--version"], capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0 and "Claude Code" in result.stdout:
            results["services"]["anthropic"] = True
        else:
            # Fallback to API key check
            if anthropic_key and anthropic_key.startswith("sk-ant-"):
                results["services"]["anthropic"] = True
            else:
                results["warnings"].append(
                    "Claude CLI not available and ANTHROPIC_API_KEY not set. Install Claude Code CLI or set API key."
                )
    except (
        subprocess.TimeoutExpired,
        subprocess.CalledProcessError,
        FileNotFoundError,
    ):
        # Fallback to API key check
        if anthropic_key and anthropic_key.startswith("sk-ant-"):
            results["services"]["anthropic"] = True
        else:
            results["warnings"].append(
                "Claude CLI not available and ANTHROPIC_API_KEY not set. Install Claude Code CLI or set API key."
            )

    # Check GitHub token
    github_token = os.getenv("GITHUB_TOKEN")
    if github_token and github_token.startswith(("ghp_", "github_pat_")):
        results["services"]["github"] = True
    else:
        results["warnings"].append(
            "GITHUB_TOKEN not set or invalid format. GitHub integration features will be limited."
        )

    return results


def validate_ollama_connection() -> dict[str, Any]:
    """Validate Ollama service is running and accessible.

    Returns:
        dict: Validation results
    """
    results: dict[str, Any] = {
        "valid": False,
        "url": None,
        "version": None,
        "models": [],
        "error": None,
    }

    ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    results["url"] = ollama_url

    try:
        # Test basic connection
        response = requests.get(f"{ollama_url}/api/version", timeout=5)
        if response.status_code == 200:
            results["valid"] = True
            version_data = response.json()
            results["version"] = version_data.get("version", "unknown")

            # Get available models
            models_response = requests.get(f"{ollama_url}/api/tags", timeout=5)
            if models_response.status_code == 200:
                models_data = models_response.json()
                results["models"] = [
                    model.get("name", "unknown")
                    for model in models_data.get("models", [])
                ]
        else:
            results["error"] = f"HTTP {response.status_code}: {response.text}"

    except requests.exceptions.ConnectionError:
        results[
            "error"
        ] = f"Cannot connect to Ollama at {ollama_url}. Is Ollama running?"
    except requests.exceptions.Timeout:
        results["error"] = f"Timeout connecting to Ollama at {ollama_url}"
    except Exception as e:
        results["error"] = f"Unexpected error: {e!s}"

    return results


def validate_required_models(ollama_results: dict[str, Any]) -> dict[str, Any]:
    """Validate required models are available in Ollama.

    Args:
        ollama_results: Results from validate_ollama_connection

    Returns:
        dict: Model validation results
    """
    results = {
        "valid": True,
        "missing_models": [],
        "available_models": ollama_results.get("models", []),
    }

    # Required models from config
    required_models = ["qwen2.5-coder:7b", "llama3.1"]

    available_models = ollama_results.get("models", [])

    for model in required_models:
        # Check exact match or partial match (e.g., "llama3.1:latest" matches "llama3.1")
        if not any(
            model in available or available.startswith(model)
            for available in available_models
        ):
            results["missing_models"].append(model)
            results["valid"] = False

    return results


def validate_data_directories() -> dict[str, Any]:
    """Validate data directories can be created.

    Returns:
        dict: Directory validation results
    """
    from .config import get_artifacts_path, get_checkpoint_path

    results: dict[str, Any] = {"valid": True, "directories": {}, "errors": []}

    # Test directory creation
    try:
        # Test checkpoint directory
        checkpoint_path = Path(get_checkpoint_path("test")).parent
        checkpoint_path.mkdir(parents=True, exist_ok=True)
        results["directories"]["checkpoints"] = str(checkpoint_path)

        # Test artifacts directory
        artifacts_path = get_artifacts_path("test")
        results["directories"]["artifacts"] = str(artifacts_path)

        # Clean up test directory
        test_artifacts = artifacts_path / "test"
        if test_artifacts.exists():
            import shutil

            shutil.rmtree(test_artifacts, ignore_errors=True)

    except Exception as e:
        results["valid"] = False
        results["errors"].append(f"Cannot create data directories: {e!s}")

    return results


def run_startup_validation(verbose: bool = True) -> dict[str, Any]:
    """Run complete startup validation.

    Args:
        verbose: Print validation results to stdout

    Returns:
        dict: Complete validation results
    """
    env_results = validate_environment_variables()
    ollama_results = validate_ollama_connection()
    dirs_results = validate_data_directories()

    results: dict[str, Any] = {
        "overall_valid": True,
        "environment": env_results,
        "ollama": ollama_results,
        "directories": dirs_results,
        "models": {},
        "recommendations": [],
    }

    # Validate models if Ollama is available
    if ollama_results["valid"]:
        results["models"] = validate_required_models(ollama_results)
    else:
        results["models"] = {
            "valid": False,
            "missing_models": [],
            "available_models": [],
        }

    # Determine overall validity
    critical_failures = [
        not dirs_results["valid"],  # Data directories must be accessible
        not env_results["services"]["anthropic"],  # Anthropic API key required
        not ollama_results["valid"],  # Ollama service must be running
    ]

    if any(critical_failures):
        results["overall_valid"] = False

    # Generate recommendations
    if not env_results["services"]["anthropic"]:
        results["recommendations"].append(
            "Install Claude Code CLI or set ANTHROPIC_API_KEY: claude --version || export ANTHROPIC_API_KEY=sk-ant-xxxxx"
        )

    if not ollama_results["valid"]:
        results["recommendations"].append(
            "Start Ollama service: 'ollama serve' then 'ollama pull qwen2.5-coder:7b'"
        )
    elif not results["models"]["valid"]:
        for model in results["models"]["missing_models"]:
            results["recommendations"].append(f"Install model: 'ollama pull {model}'")

    if not env_results["services"]["github"]:
        results["recommendations"].append(
            "Set GITHUB_TOKEN for GitHub features: export GITHUB_TOKEN=ghp_xxxxx"
        )

    # Print results if verbose
    if verbose:
        print_validation_results(results)

    return results


def print_validation_results(results: dict[str, Any]) -> None:
    """Print validation results in a user-friendly format."""
    print("\n🔍 LangGraph Workflow Startup Validation")
    print("=" * 50)

    # Overall status
    if results["overall_valid"]:
        print("✅ Overall Status: READY")
    else:
        print("❌ Overall Status: NOT READY - Critical issues found")

    # Environment variables
    print("\n📝 Environment Variables:")
    env = results["environment"]
    for service, available in env["services"].items():
        status = "✅" if available else "⚠️"
        print(
            f"   {status} {service.title()}: {'Available' if available else 'Not configured'}"
        )

    # Ollama service
    print("\n🤖 Ollama Service:")
    ollama = results["ollama"]
    if ollama["valid"]:
        print(f"   ✅ Connected: {ollama['url']} (v{ollama['version']})")
        print(f"   📦 Models available: {len(ollama['models'])}")
        for model in ollama["models"]:
            print(f"      - {model}")
    else:
        print(f"   ❌ Not available: {ollama.get('error', 'Unknown error')}")

    # Model validation
    print("\n🎯 Required Models:")
    models = results["models"]
    if models["valid"]:
        print("   ✅ All required models available")
    else:
        for model in models["missing_models"]:
            print(f"   ❌ Missing: {model}")

    # Data directories
    print("\n📁 Data Directories:")
    dirs = results["directories"]
    if dirs["valid"]:
        print("   ✅ All directories accessible")
        for name, path in dirs["directories"].items():
            print(f"      - {name}: {path}")
    else:
        for error in dirs["errors"]:
            print(f"   ❌ {error}")

    # Recommendations
    if results["recommendations"]:
        print("\n💡 Recommendations:")
        for i, rec in enumerate(results["recommendations"], 1):
            print(f"   {i}. {rec}")

    # Usage info
    print("\n🚀 Usage:")
    if results["overall_valid"]:
        print("   Ready to run: python -m langgraph_workflow.run --help")
    else:
        print("   Fix critical issues above, then retry validation")

    print()


def check_mock_mode() -> bool:
    """Check if mock mode is enabled."""
    return os.getenv("USE_MOCK_DEPENDENCIES", "false").lower() == "true"


if __name__ == "__main__":
    """Run validation when called directly."""
    if check_mock_mode():
        print("🧪 Mock mode enabled - skipping service validation")
        print("   All external services will be mocked")
        print("   Ready to run: python -m langgraph_workflow.run --help")
        sys.exit(0)

    results = run_startup_validation(verbose=True)
    sys.exit(0 if results["overall_valid"] else 1)
