"""Test fixtures for document symbol testing."""

from typing import Any

from symbol_storage import Symbol, SymbolKind


class SymbolTestFixtures:
    """Factory for creating test fixtures for symbol extraction testing."""

    @staticmethod
    def create_flat_lsp_response() -> list[dict[str, Any]]:
        """Create a flat LSP documentSymbol response.

        Returns:
            List of LSP DocumentSymbol dictionaries without hierarchy
        """
        return [
            {
                "name": "MyClass",
                "kind": 5,  # Class
                "range": {
                    "start": {"line": 0, "character": 0},
                    "end": {"line": 10, "character": 0},
                },
                "selectionRange": {
                    "start": {"line": 0, "character": 6},
                    "end": {"line": 0, "character": 13},
                },
            },
            {
                "name": "__init__",
                "kind": 9,  # Constructor
                "range": {
                    "start": {"line": 1, "character": 4},
                    "end": {"line": 3, "character": 0},
                },
                "selectionRange": {
                    "start": {"line": 1, "character": 8},
                    "end": {"line": 1, "character": 16},
                },
            },
            {
                "name": "my_method",
                "kind": 6,  # Method
                "range": {
                    "start": {"line": 4, "character": 4},
                    "end": {"line": 6, "character": 0},
                },
                "selectionRange": {
                    "start": {"line": 4, "character": 8},
                    "end": {"line": 4, "character": 17},
                },
            },
        ]

    @staticmethod
    def create_nested_lsp_response() -> list[dict[str, Any]]:
        """Create a nested LSP documentSymbol response.

        Returns:
            List of LSP DocumentSymbol dictionaries with children
        """
        return [
            {
                "name": "MyClass",
                "kind": 5,  # Class
                "range": {
                    "start": {"line": 0, "character": 0},
                    "end": {"line": 10, "character": 0},
                },
                "children": [
                    {
                        "name": "__init__",
                        "kind": 9,  # Constructor
                        "range": {
                            "start": {"line": 1, "character": 4},
                            "end": {"line": 3, "character": 0},
                        },
                    },
                    {
                        "name": "my_method",
                        "kind": 6,  # Method
                        "range": {
                            "start": {"line": 4, "character": 4},
                            "end": {"line": 6, "character": 0},
                        },
                    },
                ],
            },
            {
                "name": "standalone_function",
                "kind": 12,  # Function
                "range": {
                    "start": {"line": 12, "character": 0},
                    "end": {"line": 14, "character": 0},
                },
            },
        ]

    @staticmethod
    def create_circular_hierarchy() -> list[Symbol]:
        """Create symbols with circular parent-child relationships.

        Returns:
            List of symbols with circular references for testing
        """
        symbol_a = Symbol(
            name="ClassA",
            kind=SymbolKind.CLASS,
            file_path="test.py",
            line_number=1,
            column=0,
            parent_id="ClassC:10",  # Circular reference
        )
        symbol_b = Symbol(
            name="ClassB",
            kind=SymbolKind.CLASS,
            file_path="test.py",
            line_number=5,
            column=0,
            parent_id="ClassA:1",
        )
        symbol_c = Symbol(
            name="ClassC",
            kind=SymbolKind.CLASS,
            file_path="test.py",
            line_number=10,
            column=0,
            parent_id="ClassB:5",
        )
        return [symbol_a, symbol_b, symbol_c]

    @staticmethod
    def create_deep_nesting(depth: int) -> list[Symbol]:
        """Create deeply nested symbol hierarchy.

        Args:
            depth: Number of nesting levels to create

        Returns:
            List of symbols with specified nesting depth
        """
        symbols = []
        parent_id = None

        for i in range(depth):
            symbol = Symbol(
                name=f"Level{i}",
                kind=SymbolKind.CLASS if i % 2 == 0 else SymbolKind.FUNCTION,
                file_path="nested.py",
                line_number=i * 5 + 1,
                column=i * 4,
                parent_id=parent_id,
                end_line=i * 5 + 4,
                end_column=0,
            )
            symbols.append(symbol)
            parent_id = f"Level{i}:{i * 5 + 1}"

        return symbols

    @staticmethod
    def create_malformed_lsp_response() -> dict[str, Any]:
        """Create a malformed LSP response for error testing.

        Returns:
            Malformed response dictionary
        """
        return {
            "name": "BadSymbol",
            # Missing 'kind' field
            "range": {
                "start": {},  # Missing line/character
                "end": {"line": "not_a_number"},  # Invalid type
            },
            "children": "not_a_list",  # Should be a list
        }

    @staticmethod
    def create_mixed_language_symbols() -> list[Symbol]:
        """Create symbols from multiple language types.

        Returns:
            List of symbols with different language origins
        """
        return [
            Symbol(
                name="PythonClass",
                kind=SymbolKind.CLASS,
                file_path="main.py",
                line_number=1,
                column=0,
            ),
            Symbol(
                name="typescript_function",
                kind=SymbolKind.FUNCTION,
                file_path="main.ts",
                line_number=10,
                column=0,
            ),
            Symbol(
                name="RustStruct",
                kind=SymbolKind.CLASS,
                file_path="lib.rs",
                line_number=5,
                column=0,
            ),
            Symbol(
                name="GO_CONSTANT",
                kind=SymbolKind.CONSTANT,
                file_path="main.go",
                line_number=3,
                column=0,
            ),
        ]

    @staticmethod
    def create_large_symbol_set(count: int) -> list[Symbol]:
        """Create a large number of symbols for performance testing.

        Args:
            count: Number of symbols to generate

        Returns:
            List of generated symbols
        """
        symbols = []
        kinds = list(SymbolKind)

        for i in range(count):
            symbol = Symbol(
                name=f"Symbol_{i:06d}",
                kind=kinds[i % len(kinds)],
                file_path=f"file_{i // 100}.py",
                line_number=i + 1,
                column=(i % 80),
                docstring=f"Documentation for symbol {i}" if i % 10 == 0 else None,
            )
            symbols.append(symbol)

        return symbols

    @staticmethod
    def create_python_test_file() -> str:
        """Create Python source code for testing.

        Returns:
            Python source code as string
        """
        return '''"""Test module for symbol extraction."""

import os
from typing import Optional

CONSTANT_VALUE = 42

class MyClass:
    """A sample class for testing."""

    class_variable = "test"

    def __init__(self, value: int):
        """Initialize the class."""
        self.value = value

    @property
    def computed_value(self) -> int:
        """Compute a value."""
        return self.value * 2

    @computed_value.setter
    def computed_value(self, new_value: int):
        """Set computed value."""
        self.value = new_value // 2

    @staticmethod
    def static_method():
        """A static method."""
        return "static"

    @classmethod
    def class_method(cls):
        """A class method."""
        return cls.__name__

    class NestedClass:
        """A nested class."""

        def nested_method(self):
            """Method in nested class."""
            pass

def standalone_function(arg1: str, arg2: Optional[int] = None) -> str:
    """A standalone function."""
    if arg2 is None:
        arg2 = 0
    return f"{arg1}_{arg2}"

async def async_function():
    """An async function."""
    await some_async_operation()

# Global variable
global_var = "global"

if __name__ == "__main__":
    instance = MyClass(10)
    result = standalone_function("test")
'''

    @staticmethod
    def create_encoding_test_cases() -> dict[str, bytes]:
        """Create test cases with different encodings.

        Returns:
            Dictionary mapping encoding name to byte content
        """
        test_content = "# -*- coding: {encoding} -*-\nclass TestClass:\n    pass\n"

        return {
            "utf-8": test_content.format(encoding="utf-8").encode("utf-8"),
            "utf-8-sig": b"\xef\xbb\xbf"
            + test_content.format(encoding="utf-8").encode("utf-8"),
            "latin-1": test_content.format(encoding="latin-1").encode("latin-1"),
            "cp1252": test_content.format(encoding="cp1252").encode("cp1252"),
            "ascii": b"class SimpleClass:\n    pass\n",
        }
