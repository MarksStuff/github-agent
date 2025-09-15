"""Constants for the LangGraph workflow.

This module contains constants that are used throughout the workflow.
URLs and configurable values should be sourced from config.py, not here.
"""

# Model name constants - each model has its own constant
OLLAMA_QWEN3_8B = "qwen3:8b"
OLLAMA_LLAMA3_1 = "llama3.1"

# Default assignments using the specific model constants
DEFAULT_OLLAMA_MODEL = OLLAMA_QWEN3_8B
FALLBACK_OLLAMA_MODEL = OLLAMA_LLAMA3_1

# Timeout constants (in seconds)
CLAUDE_CLI_TIMEOUT = 600  # 10 minutes for file access operations
OLLAMA_TIMEOUT = 120  # 2 minutes for text generation
MODEL_VERSION_CHECK_TIMEOUT = 5
FEATURE_EXTRACTION_TIMEOUT = 30

# Note: Quality thresholds should be defined at the specific nodes/functions where they're used
# This avoids having global constants that are hard to maintain

# Retry limits
DEFAULT_MODEL_RETRIES = 3
DEFAULT_GIT_RETRIES = 2
DEFAULT_CI_RETRIES = 5

# Phase logging prefixes
PHASE_LOG_PREFIX = "Phase"
