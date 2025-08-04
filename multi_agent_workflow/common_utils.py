#!/usr/bin/env python3
"""
Common utilities shared across step scripts in the multi-agent workflow.
"""

import argparse
import os
from pathlib import Path
from typing import Any

from logging_config import setup_logging


def setup_common_environment(step_name: str, args: argparse.Namespace) -> dict[str, Any]:
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
    # Setup logging
    log_dir = Path.home() / ".local" / "share" / "multi-agent-workflow" / "logs"
    setup_logging(log_level=args.log_level, log_file=log_dir / f"{step_name}.log")

    # Get repository information
    repo_path = os.environ.get("REPO_PATH", str(Path.cwd().parent))
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