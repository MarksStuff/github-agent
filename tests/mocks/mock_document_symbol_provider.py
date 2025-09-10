#!/usr/bin/env python3

"""
Mock document symbol provider for testing.

Provides a mock implementation of AbstractDocumentSymbolProvider
for use in unit tests.
"""

from typing import Any

from abstract_document_symbol_provider import AbstractDocumentSymbolProvider
from symbol_storage import Symbol, SymbolKind


class MockDocumentSymbolProvider(AbstractDocumentSymbolProvider):
    """Mock document symbol provider for testing."""

    def __init__(self):
        """Initialize mock provider."""
        self.symbols_by_file: dict[str, list[Symbol]] = {}
        self.cache_cleared_count: int = 0
        self.get_symbols_call_count: int = 0

    async def get_document_symbols(self, file_path: str) -> list[Symbol]:
        """Get hierarchical symbols for a file.

        Args:
            file_path: Absolute path to the file

        Returns:
            List of Symbol objects with hierarchy information
        """
        self.get_symbols_call_count += 1
        return self.symbols_by_file.get(file_path, [])

    def clear_cache(self, file_path: str | None = None) -> None:
        """Clear cached symbols.

        Args:
            file_path: Specific file to clear, or None to clear all
        """
        self.cache_cleared_count += 1
        if file_path and file_path in self.symbols_by_file:
            del self.symbols_by_file[file_path]
        elif file_path is None:
            self.symbols_by_file.clear()

    def get_cache_stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        return {
            "cache_size": len(self.symbols_by_file),
            "total_symbols": sum(
                len(symbols) for symbols in self.symbols_by_file.values()
            ),
            "cache_cleared_count": self.cache_cleared_count,
            "get_symbols_call_count": self.get_symbols_call_count,
        }

    def set_symbols_for_file(self, file_path: str, symbols: list[Symbol]) -> None:
        """Set mock symbols for a file.

        Args:
            file_path: Path to the file
            symbols: List of symbols to return for this file
        """
        self.symbols_by_file[file_path] = symbols

    def create_test_hierarchy(self) -> list[Symbol]:
        """Create a test symbol hierarchy.

        Returns:
            List of symbols with parent-child relationships
        """
        # Create a simple class with methods
        class_symbol = Symbol(
            name="TestClass",
            kind=SymbolKind.CLASS,
            file_path="/test/file.py",
            line_number=1,
            column_number=0,
            repository_id="test_repo",
            parent_id=None,
            end_line=10,
            end_column=0,
        )

        method1 = Symbol(
            name="method1",
            kind=SymbolKind.METHOD,
            file_path="/test/file.py",
            line_number=3,
            column_number=4,
            repository_id="test_repo",
            parent_id="TestClass",
            end_line=5,
            end_column=0,
        )

        method2 = Symbol(
            name="method2",
            kind=SymbolKind.METHOD,
            file_path="/test/file.py",
            line_number=7,
            column_number=4,
            repository_id="test_repo",
            parent_id="TestClass",
            end_line=9,
            end_column=0,
        )

        # Set up parent-child relationships
        class_symbol.children = [method1, method2]

        return [class_symbol]
