"""Mock storage implementation with hierarchy support."""

from symbol_storage import Symbol


class MockStorageWithHierarchy:
    """Mock storage that supports hierarchy operations."""

    def __init__(self):
        """Initialize empty storage."""
        self.symbols: list[Symbol] = []
        self.save_called = False
        self.save_batch_called = False
        self.migrate_called = False
        self.last_saved_symbols = []

    def save_symbol(self, symbol: Symbol) -> None:
        """Save a single symbol."""
        self.save_called = True
        self.symbols.append(symbol)
        self.last_saved_symbols = [symbol]

    def save_symbols_batch(self, symbols: list[Symbol]) -> None:
        """Save multiple symbols."""
        self.save_batch_called = True
        self.symbols.extend(symbols)
        self.last_saved_symbols = symbols.copy()

    def get_symbols_by_file(self, file_path: str) -> list[Symbol]:
        """Get symbols for a file."""
        return [s for s in self.symbols if s.file_path == file_path]

    def get_symbol_hierarchy(self, file_path: str) -> list[dict]:
        """Get symbol hierarchy for a file."""
        file_symbols = self.get_symbols_by_file(file_path)

        # Build hierarchy
        hierarchy = []
        symbol_map = {}
        orphaned_symbols = []

        for symbol in file_symbols:
            symbol_dict = {
                "id": getattr(symbol, "id", None),
                "name": symbol.name,
                "type": symbol.kind.value if hasattr(symbol, "kind") else "unknown",
                "line": symbol.line_number if hasattr(symbol, "line_number") else 0,
                "character": symbol.column if hasattr(symbol, "column") else 0,
                "parent_id": getattr(symbol, "parent_id", None),
                "children": [],
            }
            symbol_map[symbol_dict["id"]] = symbol_dict

            if symbol_dict["parent_id"] is None:
                hierarchy.append(symbol_dict)

        # Link children to parents
        for symbol_dict in symbol_map.values():
            if symbol_dict["parent_id"] is not None:
                # Try to find parent by ID (converted to string for comparison)
                parent_id = str(symbol_dict["parent_id"])
                parent_found = False
                for pid, parent in symbol_map.items():
                    if str(pid) == parent_id:
                        parent["children"].append(symbol_dict)
                        parent_found = True
                        break
                
                # If parent not found, treat as orphaned (root level)
                if not parent_found:
                    orphaned_symbols.append(symbol_dict)
        
        # Add orphaned symbols to hierarchy as roots
        hierarchy.extend(orphaned_symbols)

        return hierarchy

    def migrate_schema_for_hierarchy(self) -> None:
        """Simulate schema migration."""
        self.migrate_called = True

    def clear(self) -> None:
        """Clear all symbols."""
        self.symbols.clear()
        self.last_saved_symbols.clear()


class FailingStorage:
    """Storage that always fails."""

    def __init__(self, error_message: str = "Storage error"):
        self.error_message = error_message

    def save_symbol(self, symbol: Symbol) -> None:
        """Always fail."""
        raise Exception(self.error_message)

    def save_symbols_batch(self, symbols: list[Symbol]) -> None:
        """Always fail."""
        raise Exception(self.error_message)

    def get_symbols_by_file(self, file_path: str) -> list[Symbol]:
        """Always fail."""
        raise Exception(self.error_message)

    def get_symbol_hierarchy(self, file_path: str) -> list[dict]:
        """Always fail."""
        raise Exception(self.error_message)

    def migrate_schema_for_hierarchy(self) -> None:
        """Always fail."""
        raise Exception(self.error_message)
