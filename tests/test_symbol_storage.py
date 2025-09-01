"""
Unit tests for symbol storage functionality.
"""

import tempfile
from pathlib import Path

from symbol_storage import (
    AbstractSymbolStorage,
    SQLiteSymbolStorage,
    Symbol,
    SymbolKind,
)


class TestSymbol:
    """Test the Symbol dataclass."""

    def test_symbol_creation(self):
        """Test creating a Symbol instance."""
        symbol = Symbol(
            name="test_function",
            kind=SymbolKind.FUNCTION,
            file_path="test.py",
            line_number=10,
            column_number=0,
            repository_id="test-repo",
        )

        assert symbol.name == "test_function"
        assert symbol.kind == SymbolKind.FUNCTION
        assert symbol.file_path == "test.py"
        assert symbol.line_number == 10
        assert symbol.column_number == 0
        assert symbol.repository_id == "test-repo"
        assert symbol.docstring is None

    def test_symbol_with_docstring(self):
        """Test creating a Symbol with docstring."""
        symbol = Symbol(
            name="test_class",
            kind=SymbolKind.CLASS,
            file_path="test.py",
            line_number=1,
            column_number=0,
            repository_id="test-repo",
            docstring="A test class.",
        )

        assert symbol.docstring == "A test class."

    def test_symbol_to_dict(self):
        """Test converting Symbol to dictionary."""
        symbol = Symbol(
            name="test_method",
            kind=SymbolKind.METHOD,
            file_path="test.py",
            line_number=5,
            column_number=4,
            repository_id="test-repo",
            docstring="A test method.",
        )

        expected = {
            "name": "test_method",
            "kind": "method",
            "file_path": "test.py",
            "line_number": 5,
            "column_number": 4,
            "repository_id": "test-repo",
            "docstring": "A test method.",
        }

        assert symbol.to_dict() == expected


class TestSQLiteSymbolStorage:
    """Test SQLite symbol storage implementation."""

    # Use sample_symbols fixture from conftest.py

    def test_database_schema_creation(self, storage):
        """Test that database schema is created correctly."""
        # Schema should be created during initialization
        with storage._get_connection() as conn:
            # Check that symbols table exists
            cursor = conn.execute(
                """
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='symbols'
            """
            )
            table_exists = cursor.fetchone() is not None
            assert table_exists

            # Check that indexes exist
            cursor = conn.execute(
                """
                SELECT name FROM sqlite_master
                WHERE type='index' AND tbl_name='symbols'
            """
            )
            indexes = [row[0] for row in cursor.fetchall()]
            expected_indexes = [
                "idx_symbols_name",
                "idx_symbols_repository_id",
                "idx_symbols_kind",
                "idx_symbols_file_path",
                "idx_symbols_name_repo",
            ]

            for idx in expected_indexes:
                assert idx in indexes

    def test_insert_single_symbol(self, storage):
        """Test inserting a single symbol."""
        symbol = Symbol(
            name="test_function",
            kind=SymbolKind.FUNCTION,
            file_path="test.py",
            line_number=10,
            column_number=0,
            repository_id="test-repo",
        )

        storage.insert_symbol(symbol)

        # Verify insertion
        results = storage.search_symbols("test-repo", "test_function")
        assert len(results) == 1
        assert results[0].name == "test_function"
        assert results[0].kind == SymbolKind.FUNCTION

    def test_insert_multiple_symbols(self, storage, sample_symbols):
        """Test inserting multiple symbols."""
        storage.insert_symbols(sample_symbols)

        # Verify all symbols were inserted
        all_symbols = storage.search_symbols("test-repo", "")
        assert len(all_symbols) == 4  # 4 symbols with test-repo

        other_repo_symbols = storage.search_symbols("other-repo", "")
        assert len(other_repo_symbols) == 1  # 1 symbol with other-repo

    def test_insert_empty_symbols_list(self, storage):
        """Test inserting empty symbols list."""
        storage.insert_symbols([])

        # Should not raise an error
        results = storage.search_symbols("test-repo", "")
        assert len(results) == 0

    def test_search_symbols_by_name(self, storage, sample_symbols):
        """Test searching symbols by name."""
        storage.insert_symbols(sample_symbols)

        # Exact match
        results = storage.search_symbols("test-repo", "TestClass")
        assert len(results) == 1
        assert results[0].name == "TestClass"

        # Partial match
        results = storage.search_symbols("test-repo", "test")
        assert len(results) >= 2  # Should find test_function and test_method

        # Case insensitive search
        results = storage.search_symbols("test-repo", "testclass")
        assert len(results) == 1
        assert results[0].name == "TestClass"

    def test_search_symbols_by_repository(self, storage, sample_symbols):
        """Test searching symbols by repository."""
        storage.insert_symbols(sample_symbols)

        # Search in specific repository
        results = storage.search_symbols("test-repo", "")
        assert len(results) == 4

        results = storage.search_symbols("other-repo", "")
        assert len(results) == 1
        assert results[0].name == "helper_function"

    def test_search_symbols_by_kind(self, storage, sample_symbols):
        """Test searching symbols by kind."""
        storage.insert_symbols(sample_symbols)

        # Search for functions only in test-repo
        results = storage.search_symbols("test-repo", "", symbol_kind=SymbolKind.FUNCTION)
        assert len(results) == 1
        assert results[0].name == "test_function"
        
        # Search for functions in other-repo
        results = storage.search_symbols("other-repo", "", symbol_kind=SymbolKind.FUNCTION)
        assert len(results) == 1
        assert results[0].name == "helper_function"

        # Search for classes only in test-repo
        results = storage.search_symbols("test-repo", "", symbol_kind=SymbolKind.CLASS)
        assert len(results) == 1
        assert results[0].name == "TestClass"

    def test_search_symbols_with_limit(self, storage, sample_symbols):
        """Test searching symbols with result limit."""
        storage.insert_symbols(sample_symbols)

        # Search with limit
        results = storage.search_symbols("test-repo", "", limit=2)
        assert len(results) == 2

        # Search with higher limit than available results in test-repo
        results = storage.search_symbols("test-repo", "", limit=100)
        assert len(results) == 4  # test-repo has 4 symbols

    def test_search_symbols_ordering(self, storage):
        """Test that search results are ordered with exact matches first."""
        symbols = [
            Symbol("test", SymbolKind.FUNCTION, "test.py", 1, 0, "test-repo"),
            Symbol("test_helper", SymbolKind.FUNCTION, "test.py", 2, 0, "test-repo"),
            Symbol("other_test", SymbolKind.FUNCTION, "test.py", 3, 0, "test-repo"),
        ]
        storage.insert_symbols(symbols)

        results = storage.search_symbols("test-repo", "test")

        # Exact match should come first
        assert results[0].name == "test"
        # Others should be sorted by name
        assert results[1].name in ["other_test", "test_helper"]
        assert results[2].name in ["other_test", "test_helper"]

    def test_update_symbol(self, storage):
        """Test updating a symbol."""
        symbol = Symbol(
            name="test_function",
            kind=SymbolKind.FUNCTION,
            file_path="test.py",
            line_number=10,
            column_number=0,
            repository_id="test-repo",
        )
        storage.insert_symbol(symbol)

        # Update the symbol
        updated_symbol = Symbol(
            name="test_function",
            kind=SymbolKind.FUNCTION,
            file_path="test.py",
            line_number=20,  # Changed line number
            column_number=4,  # Changed column number
            repository_id="test-repo",
            docstring="Updated docstring",
        )
        storage.update_symbol(updated_symbol)

        # Verify update
        results = storage.search_symbols("test-repo", "test_function")
        assert len(results) == 1
        assert results[0].line_number == 20
        assert results[0].column_number == 4
        assert results[0].docstring == "Updated docstring"

    def test_delete_symbols_by_repository(self, storage, sample_symbols):
        """Test deleting all symbols for a repository."""
        storage.insert_symbols(sample_symbols)

        # Verify symbols exist
        results = storage.search_symbols("test-repo", "")
        assert len(results) == 4

        # Delete symbols for test-repo
        storage.delete_symbols_by_repository("test-repo")

        # Verify symbols are deleted
        results = storage.search_symbols("test-repo", "")
        assert len(results) == 0

        # Verify other repository symbols are unaffected
        results = storage.search_symbols("other-repo", "")
        assert len(results) == 1

    def test_get_symbols_by_file(self, storage, sample_symbols):
        """Test getting symbols from a specific file."""
        storage.insert_symbols(sample_symbols)

        # Get symbols from test.py
        results = storage.get_symbols_by_file("test.py", "test-repo")
        assert len(results) == 3

        # Should be ordered by line number
        assert results[0].line_number == 1  # TestClass
        assert results[1].line_number == 10  # test_function
        assert results[2].line_number == 15  # test_method

        # Get symbols from constants.py
        results = storage.get_symbols_by_file("constants.py", "test-repo")
        assert len(results) == 1
        assert results[0].name == "TEST_CONSTANT"

        # Get symbols from non-existent file
        results = storage.get_symbols_by_file("nonexistent.py", "test-repo")
        assert len(results) == 0

    def test_get_symbol_by_id(self, storage):
        """Test getting a symbol by its ID."""
        symbol = Symbol(
            name="test_function",
            kind=SymbolKind.FUNCTION,
            file_path="test.py",
            line_number=10,
            column_number=0,
            repository_id="test-repo",
        )
        storage.insert_symbol(symbol)

        # Get the symbol ID from search results
        results = storage.search_symbols("test-repo", "test_function")
        assert len(results) == 1

        # This test verifies the method exists and handles missing IDs
        # Note: We can't easily get the actual ID without exposing it
        # in the current implementation, but we can test the method exists
        result = storage.get_symbol_by_id(999)  # Non-existent ID
        assert result is None

    def test_multiple_repositories(self, storage):
        """Test operations with multiple repositories."""
        repo1_symbols = [
            Symbol("func1", SymbolKind.FUNCTION, "file1.py", 1, 0, "repo1"),
            Symbol("class1", SymbolKind.CLASS, "file1.py", 10, 0, "repo1"),
        ]

        repo2_symbols = [
            Symbol(
                "func1", SymbolKind.FUNCTION, "file1.py", 1, 0, "repo2"
            ),  # Same name, different repo
            Symbol("func2", SymbolKind.FUNCTION, "file2.py", 5, 0, "repo2"),
        ]

        storage.insert_symbols(repo1_symbols + repo2_symbols)

        # Search in repo1
        results = storage.search_symbols("repo1", "func1")
        assert len(results) == 1
        assert results[0].repository_id == "repo1"

        # Search in repo2 (also has func1 with same name)
        results = storage.search_symbols("repo2", "func1")
        assert len(results) == 1
        assert results[0].repository_id == "repo2"
        
        # Verify isolation - searching repo1 doesn't find repo2's func2
        results = storage.search_symbols("repo1", "func2")
        assert len(results) == 0

    def test_abstract_base_class_interface(self, storage):
        """Test that SQLiteSymbolStorage implements all abstract methods."""
        # This ensures we haven't missed any required methods
        assert isinstance(storage, AbstractSymbolStorage)

        # Check that all abstract methods are implemented
        abstract_methods = [
            "create_schema",
            "insert_symbol",
            "insert_symbols",
            "update_symbol",
            "delete_symbol",
            "delete_symbols_by_repository",
            "search_symbols",
            "get_symbol_by_id",
            "get_symbols_by_file",
        ]

        for method_name in abstract_methods:
            assert hasattr(storage, method_name)
            assert callable(getattr(storage, method_name))

    def test_health_check_success(self, storage):
        """Test that health_check returns True for a functioning database."""
        # The storage fixture creates a working SQLite database
        result = storage.health_check()
        assert result is True

    def test_health_check_with_real_database(self):
        """Test health_check with a real SQLite database (assumes SQLite available)."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "health_test.db"
            storage = SQLiteSymbolStorage(db_path)

            try:
                # Test health check on a fresh database
                result = storage.health_check()
                assert result is True
            finally:
                storage.close()
