#!/usr/bin/env python3
"""Utility to populate LangGraph checkpoint state from existing files.

This helps transition from file-based workflows to state-based workflows
by importing existing valid artifacts into the checkpoint state.
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def populate_code_context_from_file(state: dict, repo_path: str) -> dict:
    """Populate code context in state from existing CODE_CONTEXT_DOCUMENT.md if valid.

    Args:
        state: Current workflow state
        repo_path: Path to repository

    Returns:
        Updated state with code context if found and valid
    """
    # Check if state already has valid code context
    existing_context = state.get("code_context_document")
    min_length = 2000

    if existing_context and len(existing_context) >= min_length:
        logger.info(
            f"✅ State already has valid code context ({len(existing_context)} chars)"
        )
        return state

    # Look for existing file
    doc_path = Path(repo_path) / "CODE_CONTEXT_DOCUMENT.md"
    if not doc_path.exists():
        logger.info("📄 No existing CODE_CONTEXT_DOCUMENT.md found")
        return state

    content = doc_path.read_text()
    if len(content) < min_length:
        logger.warning(
            f"⚠️  Existing document too short ({len(content)} chars, minimum: {min_length})"
        )
        return state

    # Valid content found - add to state
    logger.info(f"✅ Importing valid code context from file ({len(content)} chars)")
    state["code_context_document"] = content

    return state


def populate_all_artifacts_from_files(state: dict, repo_path: str) -> dict:
    """Populate all possible artifacts from existing files.

    This is a migration helper to move from file-based to state-based workflows.

    Args:
        state: Current workflow state
        repo_path: Path to repository

    Returns:
        Updated state with any valid artifacts found
    """
    logger.info("🔄 Checking for existing artifacts to import into workflow state")

    # Import code context
    state = populate_code_context_from_file(state, repo_path)

    # TODO: Add other artifact imports as needed:
    # - feature documents
    # - design documents
    # - agent analyses

    return state
