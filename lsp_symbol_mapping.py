#!/usr/bin/env python3

"""
LSP symbol kind mapping utilities.

Maps between LSP symbol kinds (numeric/string) and internal SymbolKind enum.
Handles variations between different LSP server implementations.
"""

from enum import IntEnum
from typing import Any, ClassVar

from symbol_storage import SymbolKind


class LSPSymbolKind(IntEnum):
    """LSP symbol kind constants as defined in the LSP specification."""

    File = 1
    Module = 2
    Namespace = 3
    Package = 4
    Class = 5
    Method = 6
    Property = 7
    Field = 8
    Constructor = 9
    Enum = 10
    Interface = 11
    Function = 12
    Variable = 13
    Constant = 14
    String = 15
    Number = 16
    Boolean = 17
    Array = 18
    Object = 19
    Key = 20
    Null = 21
    EnumMember = 22
    Struct = 23
    Event = 24
    Operator = 25
    TypeParameter = 26


class LSPSymbolMapper:
    """Maps between LSP and internal symbol representations."""

    # Mapping from LSP numeric kinds to internal SymbolKind
    LSP_TO_INTERNAL: ClassVar[dict[int, SymbolKind]] = {
        LSPSymbolKind.Class: SymbolKind.CLASS,
        LSPSymbolKind.Method: SymbolKind.METHOD,
        LSPSymbolKind.Function: SymbolKind.FUNCTION,
        LSPSymbolKind.Property: SymbolKind.PROPERTY,
        LSPSymbolKind.Variable: SymbolKind.VARIABLE,
        LSPSymbolKind.Constant: SymbolKind.CONSTANT,
        LSPSymbolKind.Module: SymbolKind.MODULE,
        # Additional mappings
        LSPSymbolKind.Constructor: SymbolKind.METHOD,
        LSPSymbolKind.Field: SymbolKind.VARIABLE,
    }

    # String variations from different LSP servers
    STRING_TO_INTERNAL: ClassVar[dict[str, SymbolKind]] = {
        "class": SymbolKind.CLASS,
        "Class": SymbolKind.CLASS,
        "method": SymbolKind.METHOD,
        "Method": SymbolKind.METHOD,
        "function": SymbolKind.FUNCTION,
        "Function": SymbolKind.FUNCTION,
        "property": SymbolKind.PROPERTY,
        "Property": SymbolKind.PROPERTY,
        "variable": SymbolKind.VARIABLE,
        "Variable": SymbolKind.VARIABLE,
        "constant": SymbolKind.CONSTANT,
        "Constant": SymbolKind.CONSTANT,
        "module": SymbolKind.MODULE,
        "Module": SymbolKind.MODULE,
        # Python-specific
        "staticmethod": SymbolKind.STATICMETHOD,
        "classmethod": SymbolKind.CLASSMETHOD,
        "setter": SymbolKind.SETTER,
        "deleter": SymbolKind.DELETER,
    }

    @classmethod
    def map_lsp_kind(cls, lsp_kind: int | str) -> SymbolKind:
        """Map LSP symbol kind to internal SymbolKind.

        Args:
            lsp_kind: LSP symbol kind (numeric or string)

        Returns:
            Internal SymbolKind enum value
        """
        if isinstance(lsp_kind, int):
            return cls.LSP_TO_INTERNAL.get(lsp_kind, SymbolKind.OTHER)
        elif isinstance(lsp_kind, str):
            return cls.STRING_TO_INTERNAL.get(lsp_kind, SymbolKind.OTHER)
        else:
            return SymbolKind.OTHER

    @classmethod
    def map_to_lsp_kind(cls, internal_kind: SymbolKind) -> int:
        """Map internal SymbolKind to LSP numeric kind.

        Args:
            internal_kind: Internal SymbolKind

        Returns:
            LSP numeric symbol kind
        """
        # Reverse mapping
        for lsp_kind, internal in cls.LSP_TO_INTERNAL.items():
            if internal == internal_kind:
                return lsp_kind
        return LSPSymbolKind.Variable  # Default

    @classmethod
    def normalize_lsp_symbol(cls, lsp_symbol: dict[str, Any]) -> dict[str, Any]:
        """Normalize LSP symbol response to consistent format.

        Handles variations between different LSP servers (pylsp, pyright, etc).

        Args:
            lsp_symbol: Raw LSP symbol dictionary

        Returns:
            Normalized symbol dictionary
        """
        normalized = dict(lsp_symbol)

        # Normalize kind field
        if "kind" in normalized:
            normalized["kind"] = cls.map_lsp_kind(normalized["kind"])

        # Ensure range fields exist
        if "range" not in normalized and "location" in normalized:
            normalized["range"] = normalized["location"].get("range", {})

        # Ensure selection range exists
        if "selectionRange" not in normalized:
            normalized["selectionRange"] = normalized.get("range", {})

        return normalized

    @classmethod
    def extract_symbol_range(
        cls, lsp_symbol: dict[str, Any]
    ) -> tuple[int, int, int, int]:
        """Extract symbol range from LSP response.

        Args:
            lsp_symbol: LSP symbol dictionary

        Returns:
            Tuple of (start_line, start_col, end_line, end_col)
        """
        range_data = lsp_symbol.get("range", {})
        start = range_data.get("start", {})
        end = range_data.get("end", {})

        return (
            start.get("line", 0),
            start.get("character", 0),
            end.get("line", 0),
            end.get("character", 0),
        )

    @classmethod
    def build_hierarchy_from_flat(cls, symbols: list[dict]) -> list[dict]:
        """Build hierarchy from flat symbol list.

        Some LSP servers return flat lists with containment info.
        This method builds the hierarchy based on ranges.

        Args:
            symbols: Flat list of symbols

        Returns:
            Hierarchical symbol list
        """
        if not symbols:
            return []

        # Sort symbols by position
        sorted_symbols = sort_symbols_by_position(symbols)

        # Build hierarchy
        roots = []
        for i, symbol in enumerate(sorted_symbols):
            symbol["children"] = []

            # Find parent
            parent_found = False
            for j in range(i - 1, -1, -1):
                if is_symbol_contained(sorted_symbols[j], symbol):
                    sorted_symbols[j]["children"].append(symbol)
                    parent_found = True
                    break

            if not parent_found:
                roots.append(symbol)

        return roots

    @classmethod
    def flatten_hierarchy(cls, symbols: list[dict]) -> list[dict]:
        """Flatten hierarchical symbol structure.

        Args:
            symbols: Hierarchical symbol list

        Returns:
            Flat list of all symbols
        """
        flat = []

        def flatten_recursive(syms: list[dict]) -> None:
            for symbol in syms:
                flat.append(symbol)
                if "children" in symbol:
                    flatten_recursive(symbol["children"])

        flatten_recursive(symbols)
        return flat


def is_symbol_contained(parent: dict, child: dict) -> bool:
    """Check if child symbol is contained within parent.

    Args:
        parent: Parent symbol dictionary
        child: Child symbol dictionary

    Returns:
        True if child is contained within parent's range
    """
    parent_range = parent.get("range", {})
    child_range = child.get("range", {})

    parent_start = parent_range.get("start", {})
    parent_end = parent_range.get("end", {})
    child_start = child_range.get("start", {})
    child_end = child_range.get("end", {})

    # Check if child is fully contained within parent
    parent_start_line = parent_start.get("line", 0)
    parent_end_line = parent_end.get("line", 0)
    child_start_line = child_start.get("line", 0)
    child_end_line = child_end.get("line", 0)

    if child_start_line < parent_start_line or child_end_line > parent_end_line:
        return False

    # Check column positions for same-line boundaries
    if child_start_line == parent_start_line:
        if child_start.get("character", 0) < parent_start.get("character", 0):
            return False

    if child_end_line == parent_end_line:
        if child_end.get("character", 0) > parent_end.get("character", 0):
            return False

    return True


def sort_symbols_by_position(symbols: list[dict]) -> list[dict]:
    """Sort symbols by their position in the file.

    Args:
        symbols: List of symbols to sort

    Returns:
        Sorted symbol list
    """

    def get_sort_key(symbol: dict) -> tuple:
        range_data = symbol.get("range", {})
        start = range_data.get("start", {})
        return (start.get("line", 0), start.get("character", 0))

    return sorted(symbols, key=get_sort_key)


# Export the mapper for convenience
LSP_SYMBOL_KIND_MAP = LSPSymbolMapper()
