"""Unit tests for symbol storage hierarchy extensions."""

from symbol_storage import Symbol, SymbolKind
from tests.mocks.mock_storage_with_hierarchy import MockStorageWithHierarchy


class TestSymbolStorageHierarchyFields:
    """Test hierarchy field additions to storage."""

    def test_symbol_with_parent_id(self):
        """Test creating symbol with parent_id."""
        symbol = Symbol(
            name="my_method",
            kind=SymbolKind.METHOD,
            line_number=10,
            column=4,
            file_path="test.py",
            repository_id="repo1",
        )
        symbol.parent_id = "MyClass"

        assert hasattr(symbol, "parent_id")
        assert symbol.parent_id == "MyClass"

    def test_symbol_without_parent_id(self):
        """Test symbol without parent_id defaults to None."""
        symbol = Symbol(
            name="standalone_func",
            kind=SymbolKind.FUNCTION,
            line_number=1,
            column=0,
            file_path="test.py",
            repository_id="repo1",
        )

        assert getattr(symbol, "parent_id", None) is None

    def test_symbol_hierarchy_level(self):
        """Test symbol hierarchy level tracking."""
        symbol = Symbol(
            name="nested_func",
            kind=SymbolKind.FUNCTION,
            line_number=20,
            column=8,
            file_path="test.py",
            repository_id="repo1",
        )
        symbol.hierarchy_level = 2

        assert hasattr(symbol, "hierarchy_level")
        assert symbol.hierarchy_level == 2


class TestMockStorageHierarchyMigration:
    """Test hierarchy migration behavior with mock storage."""

    def test_migrate_schema_for_hierarchy(self):
        """Test schema migration is called."""
        storage = MockStorageWithHierarchy()
        storage.migrate_schema_for_hierarchy()
        assert storage.migrate_called

    def test_migration_idempotent(self):
        """Test migration can be run multiple times safely."""
        storage = MockStorageWithHierarchy()

        # Run migration multiple times
        storage.migrate_schema_for_hierarchy()
        storage.migrate_schema_for_hierarchy()
        storage.migrate_schema_for_hierarchy()

        # Should not raise errors
        symbol = Symbol(
            name="test",
            kind=SymbolKind.FUNCTION,
            line_number=1,
            column=0,
            file_path="test.py",
            repository_id="repo1",
        )
        storage.save_symbol(symbol)

        results = storage.get_symbols_by_file("test.py")
        assert len(results) == 1


class TestMockStorageHierarchyOperations:
    """Test hierarchy-specific storage operations."""

    def test_save_symbol_with_hierarchy(self):
        """Test saving symbol with hierarchy information."""
        storage = MockStorageWithHierarchy()
        storage.migrate_schema_for_hierarchy()

        # Parent symbol
        parent = Symbol(
            name="MyClass",
            kind=SymbolKind.CLASS,
            line_number=1,
            column=0,
            file_path="test.py",
            repository_id="repo1",
        )
        parent.parent_id = None
        parent.hierarchy_level = 0
        parent.id = 1  # Mock ID for testing
        storage.save_symbol(parent)

        # Get the saved parent
        saved_parent = storage.get_symbols_by_file("test.py")[0]

        # Child symbol
        child = Symbol(
            name="my_method",
            kind=SymbolKind.METHOD,
            line_number=5,
            column=4,
            file_path="test.py",
            repository_id="repo1",
        )
        child.parent_id = str(saved_parent.id)
        child.hierarchy_level = 1
        storage.save_symbol(child)

        symbols = storage.get_symbols_by_file("test.py")
        assert len(symbols) == 2

        # Find child and verify parent_id
        child_symbol = next(s for s in symbols if s.name == "my_method")
        assert hasattr(child_symbol, "parent_id")
        assert child_symbol.parent_id == str(saved_parent.id)

    def test_get_symbol_hierarchy(self):
        """Test retrieving symbol hierarchy."""
        storage = MockStorageWithHierarchy()
        storage.migrate_schema_for_hierarchy()

        # Create hierarchy: Class -> Method -> Nested Function
        class_sym = Symbol(
            name="MyClass",
            kind=SymbolKind.CLASS,
            line_number=1,
            column=0,
            file_path="test.py",
            repository_id="repo1",
        )
        class_sym.parent_id = None
        class_sym.id = 1
        storage.save_symbol(class_sym)

        method_sym = Symbol(
            name="my_method",
            kind=SymbolKind.METHOD,
            line_number=5,
            column=4,
            file_path="test.py",
            repository_id="repo1",
        )
        method_sym.parent_id = "1"
        method_sym.id = 2
        storage.save_symbol(method_sym)

        func_sym = Symbol(
            name="nested_func",
            kind=SymbolKind.FUNCTION,
            line_number=10,
            column=8,
            file_path="test.py",
            repository_id="repo1",
        )
        func_sym.parent_id = "2"
        func_sym.id = 3
        storage.save_symbol(func_sym)

        hierarchy = storage.get_symbol_hierarchy("test.py")

        assert len(hierarchy) == 1  # One root element
        assert hierarchy[0]["name"] == "MyClass"
        assert len(hierarchy[0]["children"]) == 1
        assert hierarchy[0]["children"][0]["name"] == "my_method"
        assert len(hierarchy[0]["children"][0]["children"]) == 1
        assert hierarchy[0]["children"][0]["children"][0]["name"] == "nested_func"

    def test_get_symbol_hierarchy_multiple_roots(self):
        """Test hierarchy with multiple root elements."""
        storage = MockStorageWithHierarchy()
        storage.migrate_schema_for_hierarchy()

        # Two root classes
        class1 = Symbol(
            name="Class1",
            kind=SymbolKind.CLASS,
            line_number=1,
            column=0,
            file_path="test.py",
            repository_id="repo1",
        )
        class1.parent_id = None
        storage.save_symbol(class1)

        class2 = Symbol(
            name="Class2",
            kind=SymbolKind.CLASS,
            line_number=20,
            column=0,
            file_path="test.py",
            repository_id="repo1",
        )
        class2.parent_id = None
        storage.save_symbol(class2)

        # Standalone function
        func = Symbol(
            name="standalone",
            kind=SymbolKind.FUNCTION,
            line_number=40,
            column=0,
            file_path="test.py",
            repository_id="repo1",
        )
        func.parent_id = None
        storage.save_symbol(func)

        hierarchy = storage.get_symbol_hierarchy("test.py")

        assert len(hierarchy) == 3
        names = [h["name"] for h in hierarchy]
        assert "Class1" in names
        assert "Class2" in names
        assert "standalone" in names

    def test_batch_save_with_hierarchy(self):
        """Test batch saving symbols with hierarchy."""
        storage = MockStorageWithHierarchy()
        storage.migrate_schema_for_hierarchy()

        symbols = []

        # Create parent
        parent = Symbol(
            name="Parent",
            kind=SymbolKind.CLASS,
            line_number=1,
            column=0,
            file_path="test.py",
            repository_id="repo1",
        )
        parent.parent_id = None
        symbols.append(parent)

        # Create children (using string parent reference)
        for i in range(3):
            child = Symbol(
                name=f"child_{i}",
                kind=SymbolKind.METHOD,
                line_number=10 + i,
                column=4,
                file_path="test.py",
                repository_id="repo1",
            )
            child.parent_id = "Parent"
            symbols.append(child)

        storage.save_symbols_batch(symbols)

        saved = storage.get_symbols_by_file("test.py")
        assert len(saved) == 4

        # Verify parent-child relationships preserved
        children = [s for s in saved if s.name.startswith("child_")]
        assert all(hasattr(c, "parent_id") for c in children)


class TestMockStorageHierarchyQueries:
    """Test hierarchy-aware queries."""

    def test_get_children_of_symbol(self):
        """Test getting all children of a symbol."""
        storage = MockStorageWithHierarchy()
        storage.migrate_schema_for_hierarchy()

        # Create parent and children
        parent = Symbol(
            name="Parent",
            kind=SymbolKind.CLASS,
            line_number=1,
            column=0,
            file_path="test.py",
            repository_id="repo1",
        )
        parent.parent_id = None
        parent.id = 1
        storage.save_symbol(parent)

        for i in range(3):
            child = Symbol(
                name=f"child_{i}",
                kind=SymbolKind.METHOD,
                line_number=10 + i,
                column=4,
                file_path="test.py",
                repository_id="repo1",
            )
            child.parent_id = "1"
            storage.save_symbol(child)

        # Query children
        all_symbols = storage.get_symbols_by_file("test.py")
        children = [s for s in all_symbols if getattr(s, "parent_id", None) == "1"]

        assert len(children) == 3
        assert all(c.name.startswith("child_") for c in children)

    def test_get_symbols_at_level(self):
        """Test getting symbols at specific hierarchy level."""
        storage = MockStorageWithHierarchy()
        storage.migrate_schema_for_hierarchy()

        # Level 0
        root = Symbol(
            name="Root",
            kind=SymbolKind.MODULE,
            line_number=0,
            column=0,
            file_path="test.py",
            repository_id="repo1",
        )
        root.hierarchy_level = 0
        storage.save_symbol(root)

        # Level 1
        class1 = Symbol(
            name="Class1",
            kind=SymbolKind.CLASS,
            line_number=10,
            column=0,
            file_path="test.py",
            repository_id="repo1",
        )
        class1.hierarchy_level = 1
        storage.save_symbol(class1)

        class2 = Symbol(
            name="Class2",
            kind=SymbolKind.CLASS,
            line_number=30,
            column=0,
            file_path="test.py",
            repository_id="repo1",
        )
        class2.hierarchy_level = 1
        storage.save_symbol(class2)

        # Level 2
        method = Symbol(
            name="method",
            kind=SymbolKind.METHOD,
            line_number=15,
            column=4,
            file_path="test.py",
            repository_id="repo1",
        )
        method.hierarchy_level = 2
        storage.save_symbol(method)

        all_symbols = storage.get_symbols_by_file("test.py")

        level_0 = [s for s in all_symbols if getattr(s, "hierarchy_level", None) == 0]
        level_1 = [s for s in all_symbols if getattr(s, "hierarchy_level", None) == 1]
        level_2 = [s for s in all_symbols if getattr(s, "hierarchy_level", None) == 2]

        assert len(level_0) == 1
        assert len(level_1) == 2
        assert len(level_2) == 1


class TestMockStorageHierarchyErrors:
    """Test error handling in hierarchy operations."""

    def test_invalid_parent_reference(self):
        """Test handling invalid parent references."""
        storage = MockStorageWithHierarchy()
        storage.migrate_schema_for_hierarchy()

        # Symbol with non-existent parent
        orphan = Symbol(
            name="orphan",
            kind=SymbolKind.METHOD,
            line_number=10,
            column=4,
            file_path="test.py",
            repository_id="repo1",
        )
        orphan.parent_id = "NonExistentParent"

        # Should save without error
        storage.save_symbol(orphan)

        # But hierarchy building should handle it gracefully
        hierarchy = storage.get_symbol_hierarchy("test.py")

        # Orphan should appear as root since parent doesn't exist
        assert len(hierarchy) == 1
        assert hierarchy[0]["name"] == "orphan"

    def test_circular_hierarchy_detection(self):
        """Test detection of circular parent references."""
        storage = MockStorageWithHierarchy()
        storage.migrate_schema_for_hierarchy()

        # Create circular reference A -> B -> A
        sym_a = Symbol(
            name="A",
            kind=SymbolKind.CLASS,
            line_number=1,
            column=0,
            file_path="test.py",
            repository_id="repo1",
        )
        sym_a.parent_id = "B"
        storage.save_symbol(sym_a)

        sym_b = Symbol(
            name="B",
            kind=SymbolKind.CLASS,
            line_number=10,
            column=0,
            file_path="test.py",
            repository_id="repo1",
        )
        sym_b.parent_id = "A"
        storage.save_symbol(sym_b)

        # Hierarchy building should handle circular refs
        hierarchy = storage.get_symbol_hierarchy("test.py")

        # Both should appear as roots due to circular ref
        assert len(hierarchy) >= 1

    def test_corrupted_hierarchy_data(self):
        """Test handling corrupted hierarchy data."""
        storage = MockStorageWithHierarchy()
        storage.migrate_schema_for_hierarchy()

        # Insert symbol with invalid parent_id
        bad_symbol = Symbol(
            name="BadSymbol",
            kind=SymbolKind.OTHER,
            line_number=10,
            column=4,
            file_path="test.py",
            repository_id="repo1",
        )
        bad_symbol.parent_id = ";;;INVALID;;;"
        storage.save_symbol(bad_symbol)

        # Should handle gracefully
        symbols = storage.get_symbols_by_file("test.py")
        assert len(symbols) == 1

        hierarchy = storage.get_symbol_hierarchy("test.py")
        # Should still build hierarchy despite bad data
        assert isinstance(hierarchy, list)
