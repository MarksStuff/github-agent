"""Constants for the LangGraph workflow.

This module contains constants that are used throughout the workflow.
URLs and configurable values should be sourced from config.py, not here.
"""

# Model name constants (referenced from config to avoid duplication)
DEFAULT_OLLAMA_MODEL = "qwen3:8b"
FALLBACK_OLLAMA_MODEL = "llama3.1"

# Timeout constants (in seconds)
CLAUDE_CLI_TIMEOUT = 600  # 10 minutes for file access operations
OLLAMA_TIMEOUT = 120  # 2 minutes for text generation
MODEL_VERSION_CHECK_TIMEOUT = 5
FEATURE_EXTRACTION_TIMEOUT = 30

# Quality thresholds
MIN_CODE_CONTEXT_LENGTH = 2000
MIN_FEATURE_DESCRIPTION_LENGTH = 10
MAX_ARTIFACT_SIZE_BYTES = 100_000

# Retry limits
DEFAULT_MODEL_RETRIES = 3
DEFAULT_GIT_RETRIES = 2
DEFAULT_CI_RETRIES = 5

# Phase logging prefixes
PHASE_LOG_PREFIX = "Phase"
