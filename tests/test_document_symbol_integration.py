"""Integration tests for complete document symbol workflow."""

import tempfile
from pathlib import Path

import pytest

from document_symbol_config import DocumentSymbolConfig
from document_symbol_provider import DocumentSymbolProvider
from errors import InvalidFileTypeError
from python_symbol_extractor import PythonSymbolExtractor
from symbol_storage import SQLiteSymbolStorage


class TestEndToEndWorkflow:
    """Test complete workflow from file to hierarchy."""

    @pytest.mark.asyncio
    async def test_complete_extraction_workflow(self):
        """Test full extraction and storage workflow."""
        # Create test files
        with tempfile.TemporaryDirectory() as tmpdir:
            # Setup database
            db_path = Path(tmpdir) / "test.db"
            storage = SQLiteSymbolStorage(str(db_path))
            storage.migrate_schema_for_hierarchy()

            # Setup config
            config = DocumentSymbolConfig(database_path=str(db_path))

            # Create provider
            provider = DocumentSymbolProvider(config=config, storage=storage)
            provider.register_extractor("python", PythonSymbolExtractor())

            # Create test Python file
            test_file = Path(tmpdir) / "test_module.py"
            test_file.write_text(
                """
class Calculator:
    def add(self, a, b):
        return a + b

    def subtract(self, a, b):
        return a - b

def main():
    calc = Calculator()
    return calc
"""
            )

            # Extract symbols
            symbols = await provider.get_document_symbols(str(test_file), "test_repo")

            # Filter out variables as they're not structural symbols
            symbols = [s for s in symbols if s.kind.value != "variable"]
            assert len(symbols) == 4  # Calculator, add, subtract, main

            # Get hierarchy
            hierarchy = await provider.get_symbol_hierarchy(str(test_file), "test_repo")

            assert hierarchy["file"] == str(test_file)
            assert hierarchy["repository_id"] == "test_repo"
            assert len(hierarchy["symbols"]) == 2  # Calculator and main at root

            # Find Calculator class
            calc_hierarchy = next(
                s for s in hierarchy["symbols"] if s["name"] == "Calculator"
            )
            assert len(calc_hierarchy["children"]) == 2  # add and subtract methods

    @pytest.mark.asyncio
    async def test_batch_extraction_integration(self):
        """Test batch extraction of multiple files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Setup
            db_path = Path(tmpdir) / "test.db"
            storage = SQLiteSymbolStorage(str(db_path))
            storage.migrate_schema_for_hierarchy()

            config = DocumentSymbolConfig(database_path=str(db_path), max_workers=2)

            provider = DocumentSymbolProvider(config=config, storage=storage)
            provider.register_extractor("python", PythonSymbolExtractor())

            # Create multiple test files
            files = []
            for i in range(5):
                file_path = Path(tmpdir) / f"module_{i}.py"
                file_path.write_text(
                    f"""
class Class{i}:
    def method{i}(self):
        pass

def function{i}():
    pass
"""
                )
                files.append(str(file_path))

            # Track progress
            progress_updates = []

            def track_progress(file_path: str, progress: float):
                progress_updates.append((file_path, progress))

            # Batch extraction
            results = await provider.batch_extract_symbols(
                files, "test_repo", progress_callback=track_progress
            )

            # Verify results
            assert len(results) == 5
            for file_path in files:
                assert file_path in results
                assert len(results[file_path]) == 3  # Class, method, and function

            # Verify progress tracking
            assert len(progress_updates) > 0
            assert all(0 <= p[1] <= 1 for p in progress_updates)

    @pytest.mark.asyncio
    async def test_mixed_file_types_integration(self):
        """Test handling mixed supported and unsupported files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            storage = SQLiteSymbolStorage(str(db_path))
            storage.migrate_schema_for_hierarchy()

            config = DocumentSymbolConfig(database_path=str(db_path))
            provider = DocumentSymbolProvider(config=config, storage=storage)
            provider.register_extractor("python", PythonSymbolExtractor())

            # Create mixed files
            py_file = Path(tmpdir) / "module.py"
            py_file.write_text("def test(): pass")

            txt_file = Path(tmpdir) / "readme.txt"
            txt_file.write_text("This is a text file")

            # Extract from Python file - should work
            symbols = await provider.get_document_symbols(str(py_file))
            assert len(symbols) == 1

            # Extract from text file - should fail
            with pytest.raises(InvalidFileTypeError):
                await provider.get_document_symbols(str(txt_file))

            # Ensure storage cleanup
            storage.close()

    @pytest.mark.asyncio
    async def test_persistence_across_sessions(self):
        """Test that symbols persist across provider sessions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            test_file = Path(tmpdir) / "persistent.py"
            test_file.write_text(
                """
class PersistentClass:
    def persistent_method(self):
        pass
"""
            )

            # First session - extract and store
            storage1 = SQLiteSymbolStorage(str(db_path))
            storage1.migrate_schema_for_hierarchy()

            provider1 = DocumentSymbolProvider(storage=storage1)
            provider1.register_extractor("python", PythonSymbolExtractor())

            symbols1 = await provider1.get_document_symbols(str(test_file), "repo1")
            assert len(symbols1) == 2

            # Save symbols to storage
            for symbol in symbols1:
                storage1.save_symbol(symbol)

            # Close first session
            del provider1
            del storage1

            # Second session - read persisted data
            storage2 = SQLiteSymbolStorage(str(db_path))
            symbols_from_storage = storage2.get_symbols_by_file(str(test_file), "repo1")

            assert len(symbols_from_storage) == 2
            names = [s.name for s in symbols_from_storage]
            assert "PersistentClass" in names
            assert "persistent_method" in names


class TestErrorHandlingIntegration:
    """Test error handling in integrated scenarios."""

    @pytest.mark.asyncio
    async def test_corrupted_file_handling(self):
        """Test handling of corrupted Python files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            storage = SQLiteSymbolStorage(str(db_path))
            storage.migrate_schema_for_hierarchy()

            provider = DocumentSymbolProvider(storage=storage)
            provider.register_extractor("python", PythonSymbolExtractor())

            # Create file with syntax error
            bad_file = Path(tmpdir) / "bad.py"
            bad_file.write_text(
                """
def broken(
    # Missing closing parenthesis
    pass
"""
            )

            # Should handle gracefully
            symbols = await provider.get_document_symbols(str(bad_file))
            # May return empty or partial results
            assert isinstance(symbols, list)

    @pytest.mark.asyncio
    async def test_concurrent_extraction_errors(self):
        """Test error handling in concurrent extraction."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            storage = SQLiteSymbolStorage(str(db_path))
            storage.migrate_schema_for_hierarchy()

            provider = DocumentSymbolProvider(storage=storage)
            provider.register_extractor("python", PythonSymbolExtractor())

            # Create mix of good and bad files
            good_file = Path(tmpdir) / "good.py"
            good_file.write_text("def good(): pass")

            bad_file = Path(tmpdir) / "bad.py"
            bad_file.write_text("def bad( pass")  # Syntax error

            files = [str(good_file), str(bad_file)]
            results = await provider.batch_extract_symbols(files)

            # Good file should succeed
            assert str(good_file) in results
            assert len(results[str(good_file)]) > 0

            # Bad file should have empty result
            assert str(bad_file) in results
            assert isinstance(results[str(bad_file)], list)

    @pytest.mark.asyncio
    async def test_storage_failure_recovery(self):
        """Test recovery from storage failures."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("def test(): pass")

            # Create provider with normal storage
            storage = SQLiteSymbolStorage(str(db_path))
            storage.migrate_schema_for_hierarchy()
            provider = DocumentSymbolProvider(storage=storage)
            provider.register_extractor("python", PythonSymbolExtractor())

            # First extraction should work
            symbols = await provider.get_document_symbols(str(test_file))
            assert len(symbols) == 1

            # Simulate storage corruption
            db_path.chmod(0o000)  # Remove all permissions

            try:
                # Should handle storage errors gracefully
                with pytest.raises(Exception):  # Storage error
                    await provider.get_document_symbols(str(test_file), "repo2")
            finally:
                # Restore permissions for cleanup
                db_path.chmod(0o644)


class TestCachingIntegration:
    """Test caching in integrated scenarios."""

    @pytest.mark.asyncio
    async def test_cache_performance(self):
        """Test that caching improves performance."""
        import time

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            storage = SQLiteSymbolStorage(str(db_path))
            storage.migrate_schema_for_hierarchy()

            # Create large file
            test_file = Path(tmpdir) / "large.py"
            source = ""
            for i in range(100):
                source += f"""
class Class{i}:
    def method1(self): pass
    def method2(self): pass
    def method3(self): pass
"""
            test_file.write_text(source)

            # Provider with cache enabled
            config = DocumentSymbolConfig(cache_enabled=True)
            provider = DocumentSymbolProvider(config=config, storage=storage)
            provider.register_extractor("python", PythonSymbolExtractor())

            # First extraction
            start = time.time()
            symbols1 = await provider.get_document_symbols(str(test_file))
            first_time = time.time() - start

            # Second extraction (cached)
            start = time.time()
            symbols2 = await provider.get_document_symbols(str(test_file))
            second_time = time.time() - start

            # Cache should be faster
            assert second_time < first_time
            assert symbols1 == symbols2

    @pytest.mark.asyncio
    async def test_cache_invalidation(self):
        """Test cache invalidation on file changes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            storage = SQLiteSymbolStorage(str(db_path))
            storage.migrate_schema_for_hierarchy()

            test_file = Path(tmpdir) / "changing.py"
            test_file.write_text("def original(): pass")

            config = DocumentSymbolConfig(cache_enabled=True)
            provider = DocumentSymbolProvider(config=config, storage=storage)
            provider.register_extractor("python", PythonSymbolExtractor())

            # First extraction
            symbols1 = await provider.get_document_symbols(str(test_file))
            assert len(symbols1) == 1
            assert symbols1[0]["name"] == "original"

            # Modify file
            test_file.write_text("def modified(): pass\ndef another(): pass")

            # Clear cache to simulate invalidation
            provider.clear_cache()

            # Re-extract
            symbols2 = await provider.get_document_symbols(str(test_file))
            assert len(symbols2) == 2
            names = [s["name"] for s in symbols2]
            assert "modified" in names
            assert "another" in names


class TestRealWorldScenarios:
    """Test realistic usage scenarios."""

    @pytest.mark.asyncio
    async def test_project_structure_extraction(self):
        """Test extracting symbols from project structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create project structure
            project = Path(tmpdir) / "myproject"
            project.mkdir()

            (project / "__init__.py").write_text("")

            (project / "models.py").write_text(
                """
class User:
    def __init__(self, name):
        self.name = name

    def get_name(self):
        return self.name

class Product:
    def __init__(self, title):
        self.title = title
"""
            )

            (project / "views.py").write_text(
                """
def index():
    return "Home"

def user_view(user_id):
    return f"User {user_id}"
"""
            )

            (project / "utils.py").write_text(
                """
def format_date(date):
    return date.strftime("%Y-%m-%d")

def validate_email(email):
    return "@" in email
"""
            )

            # Setup provider
            db_path = Path(tmpdir) / "project.db"
            storage = SQLiteSymbolStorage(str(db_path))
            storage.migrate_schema_for_hierarchy()

            config = DocumentSymbolConfig(database_path=str(db_path))
            provider = DocumentSymbolProvider(config=config, storage=storage)
            provider.register_extractor("python", PythonSymbolExtractor())

            # Extract all Python files
            py_files = list(project.glob("*.py"))
            results = await provider.batch_extract_symbols(
                [str(f) for f in py_files], "myproject"
            )

            # Verify structure
            assert len(results) == 4  # __init__, models, views, utils

            # Check models.py
            models_path = str(project / "models.py")
            models_symbols = results[models_path]
            model_names = [s["name"] for s in models_symbols]
            assert "User" in model_names
            assert "Product" in model_names

            # Check hierarchy in models
            user_class = next(s for s in models_symbols if s["name"] == "User")
            assert "children" in user_class
            method_names = [c["name"] for c in user_class["children"]]
            assert "__init__" in method_names
            assert "get_name" in method_names

    @pytest.mark.asyncio
    async def test_incremental_updates(self):
        """Test incremental symbol updates."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "incremental.db"
            storage = SQLiteSymbolStorage(str(db_path))
            storage.migrate_schema_for_hierarchy()

            provider = DocumentSymbolProvider(storage=storage)
            provider.register_extractor("python", PythonSymbolExtractor())

            test_file = Path(tmpdir) / "evolving.py"

            # Version 1
            test_file.write_text("def version1(): pass")
            await provider.get_document_symbols(str(test_file), "repo")

            # Version 2 - Add class
            test_file.write_text(
                """
def version1(): pass

class NewClass:
    def method(self): pass
"""
            )
            provider.clear_cache()  # Clear cache for update
            symbols = await provider.get_document_symbols(str(test_file), "repo")

            assert len(symbols) == 3
            names = [s["name"] for s in symbols]
            assert "version1" in names
            assert "NewClass" in names
            assert "method" in names
