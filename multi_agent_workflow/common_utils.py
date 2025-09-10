#!/usr/bin/env python3
"""
Common utilities shared across step scripts in the multi-agent workflow.
"""

import argparse
import os
from pathlib import Path
from typing import Any

try:
    from dotenv import load_dotenv

    DOTENV_AVAILABLE = True
except ImportError:
    DOTENV_AVAILABLE = False

from logging_config import setup_logging


def setup_common_environment(
    step_name: str, args: argparse.Namespace
) -> dict[str, Any]:
    """Setup common environment for all step scripts.

    Args:
        step_name: Name of the step (e.g., "step1_analysis", "step2_design")
        args: Parsed command line arguments with log_level attribute

    Returns:
        Dictionary containing:
            - repo_path: Repository path
            - repo_name: Repository name
            - log_dir: Log directory path
    """
    # Load .env file if available
    if DOTENV_AVAILABLE:
        # Try to find .env file in current directory or parent directories
        current_path = Path.cwd()
        while current_path != current_path.parent:
            env_file = current_path / ".env"
            if env_file.exists():
                load_dotenv(env_file)
                print(f"📄 Loaded environment from: {env_file}")
                break
            current_path = current_path.parent
        else:
            # Also try loading from default location
            load_dotenv()

    # Setup logging
    log_dir = Path.home() / ".local" / "share" / "multi-agent-workflow" / "logs"
    setup_logging(log_level=args.log_level, log_file=log_dir / f"{step_name}.log")

    # Get repository information
    # Find the actual git repository by looking for .git directory
    current_path = Path.cwd()
    repo_path = None

    # Search upward for .git directory
    while current_path != current_path.parent:
        if (current_path / ".git").exists():
            repo_path = str(current_path)
            break
        current_path = current_path.parent

    # Fallback to environment variable or current directory
    if repo_path is None:
        repo_path = os.environ.get("REPO_PATH", str(Path.cwd()))

    repo_name = os.environ.get("GITHUB_REPO", "github-agent")

    return {
        "repo_path": repo_path,
        "repo_name": repo_name,
        "log_dir": log_dir,
    }


def add_common_arguments(parser: argparse.ArgumentParser) -> None:
    """Add common command line arguments to a parser.

    Args:
        parser: ArgumentParser to add arguments to
    """
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Set the logging level",
    )


def validate_github_token() -> bool:
    """Validate that GITHUB_TOKEN is set and provide helpful error message if not.

    Returns:
        True if token is set, False otherwise (and prints error message)
    """
    github_token = os.environ.get("GITHUB_TOKEN")
    if not github_token:
        print("❌ ERROR: GITHUB_TOKEN is required but not set")
        print()
        print(
            "The multi-agent workflow requires GitHub integration to create and manage PRs."
        )
        print("Please set the GITHUB_TOKEN environment variable:")
        print()
        print("Option 1 - Export for current session:")
        print("  export GITHUB_TOKEN=your_token_here")
        print()
        print("Option 2 - Add to your shell profile (~/.bashrc, ~/.zshrc, etc.):")
        print("  echo 'export GITHUB_TOKEN=your_token_here' >> ~/.zshrc")
        print()
        print("Option 3 - Create a .env file in the project root:")
        print("  echo 'GITHUB_TOKEN=your_token_here' >> .env")
        print()
        print("To create a GitHub token:")
        print("1. Go to https://github.com/settings/tokens")
        print("2. Click 'Generate new token (classic)'")
        print("3. Select scopes: 'repo', 'workflow'")
        print("4. Copy the generated token")
        print()
        print(
            "Alternative: You can also use 'claude setup-token' if you have Claude Code CLI."
        )
        print()
        return False
    return True


def print_step_header(step_name: str, step_description: str, **kwargs: Any) -> None:
    """Print a standardized header for step scripts.

    Args:
        step_name: Name of the step (e.g., "Step 1")
        step_description: Description of what the step does
        **kwargs: Additional key-value pairs to display (e.g., pr_number=123)
    """
    print("=" * 60)
    print(f"{step_name}: {step_description}")
    print("=" * 60)

    for key, value in kwargs.items():
        # Convert snake_case to Title Case for display
        display_key = key.replace("_", " ").title()
        print(f"{display_key}: {value}")
