#!/usr/bin/env python3

"""
Abstract base class for document symbol providers.

Defines the interface for document symbol extraction with hierarchy support.
"""

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any

from symbol_storage import Symbol


class AbstractDocumentSymbolProvider(ABC):
    """Abstract base class for document symbol providers."""

    @abstractmethod
    async def get_document_symbols(self, file_path: str) -> list[Symbol]:
        """Get hierarchical symbols for a file.

        Args:
            file_path: Absolute path to the file

        Returns:
            List of Symbol objects with hierarchy information
        """

    @abstractmethod
    def clear_cache(self, file_path: str | None = None) -> None:
        """Clear cached symbols.

        Args:
            file_path: Specific file to clear, or None to clear all
        """

    @abstractmethod
    def get_cache_stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dictionary with cache statistics
        """

    @abstractmethod
    async def get_batch_symbols(
        self,
        file_paths: list[str],
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> dict[str, list[Symbol]]:
        """Extract symbols from multiple files concurrently.

        Args:
            file_paths: List of file paths to process
            progress_callback: Optional callback for progress reporting (current, total)

        Returns:
            Dictionary mapping file paths to their symbols
        """
