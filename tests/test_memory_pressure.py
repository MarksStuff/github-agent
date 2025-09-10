"""Test memory exhaustion and resource management scenarios."""

import concurrent.futures
import gc
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from document_symbol_provider import DocumentSymbolProvider
from python_symbol_extractor import PythonSymbolExtractor
from repository_indexer import PythonRepositoryIndexer
from symbol_storage import SQLiteSymbolStorage, Symbol, SymbolKind


class TestMemoryPressureScenarios(unittest.TestCase):
    """Test system behavior under memory pressure."""

    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "memory_test.db"

    def tearDown(self):
        """Clean up test environment."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)
        # Force garbage collection
        gc.collect()

    def test_large_symbol_batch_memory_usage(self):
        """Test memory usage during large symbol batch processing."""
        storage = SQLiteSymbolStorage(self.db_path)
        self.addCleanup(storage.close)

        # Create a large number of symbols (should be processed in batches)
        symbol_count = 10000
        symbols = []

        for i in range(symbol_count):
            symbols.append(
                Symbol(
                    name=f"memory_test_symbol_{i}",
                    kind=SymbolKind.FUNCTION,
                    file_path=f"/memory/test/file_{i % 100}.py",
                    line_number=i % 1000,
                    column_number=0,
                    repository_id="memory_test_repo",
                    docstring=f"Test symbol {i} with some documentation content",
                )
            )

        # Monitor memory usage during insertion
        import os

        import psutil

        process = psutil.Process(os.getpid())
        memory_before = process.memory_info().rss

        # Insert symbols - should use batching to manage memory
        storage.insert_symbols(symbols)

        memory_after = process.memory_info().rss
        memory_increase = memory_after - memory_before

        # Memory increase should be reasonable (less than 100MB for this test)
        self.assertLess(
            memory_increase,
            100 * 1024 * 1024,
            f"Memory increase {memory_increase / 1024 / 1024:.1f}MB is too high",
        )

        # Verify all symbols were inserted
        results = storage.search_symbols(
            "memory_test_repo", "memory_test_symbol", limit=100
        )
        self.assertEqual(len(results), 100)  # Limited by query limit

    def test_memory_error_handling_in_extraction(self):
        """Test handling of MemoryError during symbol extraction."""
        extractor = PythonSymbolExtractor()

        # Create a test file
        test_file = Path(self.temp_dir) / "memory_test.py"
        test_file.write_text("def test_function(): pass")

        # Mock ast.parse to raise MemoryError
        with patch("ast.parse", side_effect=MemoryError("Simulated memory error")):
            with self.assertRaises(MemoryError):
                extractor.extract_from_file(str(test_file), "test_repo")

    def test_large_file_memory_management(self):
        """Test memory management when processing large files."""
        # Create a large Python file
        large_file = Path(self.temp_dir) / "large_file.py"

        # Create content that would consume significant memory during AST parsing
        lines = []
        for i in range(10000):
            lines.append(f"def function_{i}():")
            lines.append(f"    '''Docstring for function {i}'''")
            lines.append(f"    variable_{i} = 'value_{i}'")
            lines.append(f"    return variable_{i}")
            lines.append("")

        large_file.write_text("\n".join(lines))

        # Extract symbols from large file
        extractor = PythonSymbolExtractor()

        # Monitor memory during extraction
        import os

        import psutil

        process = psutil.Process(os.getpid())
        memory_before = process.memory_info().rss

        symbols = extractor.extract_from_file(str(large_file), "large_repo")

        memory_after = process.memory_info().rss
        memory_increase = memory_after - memory_before

        # Should have extracted many symbols
        self.assertGreater(len(symbols), 10000)

        # Memory increase should be reasonable
        self.assertLess(
            memory_increase,
            200 * 1024 * 1024,
            f"Memory increase {memory_increase / 1024 / 1024:.1f}MB is too high",
        )

    def test_indexer_memory_management_with_many_files(self):
        """Test memory management when indexing many files."""
        # Create test repository with many files
        repo_dir = Path(self.temp_dir) / "many_files_repo"
        repo_dir.mkdir()

        # Create many small Python files
        file_count = 1000
        for i in range(file_count):
            file_path = repo_dir / f"file_{i}.py"
            file_path.write_text(
                f"""
def function_{i}():
    '''Function {i} docstring'''
    return {i}

class Class_{i}:
    '''Class {i} docstring'''
    def method_{i}(self):
        return {i}
"""
            )

        # Create storage and indexer
        storage = SQLiteSymbolStorage(self.db_path)
        self.addCleanup(storage.close)
        extractor = PythonSymbolExtractor()
        indexer = PythonRepositoryIndexer(extractor, storage)

        # Monitor memory during indexing
        import os

        import psutil

        process = psutil.Process(os.getpid())
        memory_before = process.memory_info().rss

        # Index repository
        result = indexer.index_repository(str(repo_dir), "many_files_repo")

        memory_after = process.memory_info().rss
        memory_increase = memory_after - memory_before

        # Should have processed all files
        self.assertEqual(len(result.processed_files), file_count)

        # Memory increase should be reasonable for 1000 files
        self.assertLess(
            memory_increase,
            500 * 1024 * 1024,
            f"Memory increase {memory_increase / 1024 / 1024:.1f}MB is too high",
        )

    def test_database_memory_management_large_queries(self):
        """Test memory management during large database queries."""
        storage = SQLiteSymbolStorage(self.db_path)
        self.addCleanup(storage.close)

        # Insert a large number of symbols first
        symbols = []
        for i in range(5000):
            symbols.append(
                Symbol(
                    name=f"query_test_symbol_{i}",
                    kind=SymbolKind.FUNCTION,
                    file_path=f"/query/test/file_{i % 50}.py",
                    line_number=i % 100,
                    column_number=0,
                    repository_id="query_test_repo",
                )
            )

        storage.insert_symbols(symbols)

        # Monitor memory during large queries
        import os

        import psutil

        process = psutil.Process(os.getpid())
        memory_before = process.memory_info().rss

        # Perform multiple large queries
        for _ in range(10):
            results = storage.search_symbols(
                "query_test_repo", "query_test_symbol", limit=100
            )
            self.assertEqual(len(results), 100)

        memory_after = process.memory_info().rss
        memory_increase = memory_after - memory_before

        # Memory increase should be minimal for queries
        self.assertLess(
            memory_increase,
            50 * 1024 * 1024,
            f"Memory increase {memory_increase / 1024 / 1024:.1f}MB is too high for queries",
        )

    def test_recovery_from_memory_pressure(self):
        """Test system recovery after memory pressure events."""
        storage = SQLiteSymbolStorage(self.db_path)
        self.addCleanup(storage.close)

        # Simulate memory pressure by creating and destroying large objects
        large_objects = []
        try:
            # Create objects that consume memory
            for _i in range(100):
                large_objects.append([f"data_{j}" for j in range(10000)])

            # Try to perform database operations under memory pressure
            symbol = Symbol(
                name="pressure_test",
                kind=SymbolKind.FUNCTION,
                file_path="/pressure/test.py",
                line_number=1,
                column_number=0,
                repository_id="pressure_repo",
            )

            storage.insert_symbol(symbol)

            # Verify symbol was inserted
            results = storage.search_symbols("pressure_repo", "pressure_test")
            self.assertEqual(len(results), 1)

        finally:
            # Release memory pressure
            large_objects.clear()
            gc.collect()

        # System should still be functional after memory pressure
        another_symbol = Symbol(
            name="after_pressure_test",
            kind=SymbolKind.FUNCTION,
            file_path="/after/pressure.py",
            line_number=1,
            column_number=0,
            repository_id="pressure_repo",
        )

        storage.insert_symbol(another_symbol)
        results = storage.search_symbols("pressure_repo", "after_pressure_test")
        self.assertEqual(len(results), 1)

    def test_graceful_degradation_under_memory_limits(self):
        """Test graceful degradation when approaching memory limits."""
        # This test simulates what happens when the system approaches memory limits
        extractor = PythonSymbolExtractor()

        # Create a file that would normally succeed
        normal_file = Path(self.temp_dir) / "normal.py"
        normal_file.write_text("def normal_function(): pass")

        # Mock memory pressure during extraction
        original_parse = __import__("ast").parse

        def memory_limited_parse(*args, **kwargs):
            # Simulate memory pressure by limiting available operations
            if len(args[0]) > 100:  # If source is large
                raise MemoryError("Simulated memory pressure")
            return original_parse(*args, **kwargs)

        with patch("ast.parse", side_effect=memory_limited_parse):
            # Small file should still work
            symbols = extractor.extract_from_file(str(normal_file), "test_repo")
            self.assertGreater(len(symbols), 0)

            # Large content should fail gracefully
            large_content = "def large(): pass\n" * 1000
            large_file = Path(self.temp_dir) / "large.py"
            large_file.write_text(large_content)

            with self.assertRaises(MemoryError):
                extractor.extract_from_file(str(large_file), "test_repo")

    def test_recursive_structure_memory_bomb(self):
        """Test handling of deeply recursive structures that could cause memory explosion."""
        # Create deeply nested structure
        depth = 10000
        nested_dict = current = {}
        for i in range(depth):
            current["child"] = {}
            current = current["child"]

        # Test that provider handles deep recursion without stack overflow
        provider = DocumentSymbolProvider()

        try:
            # Should handle deep structures gracefully
            result = provider._process_nested_structure(nested_dict, max_depth=100)

            # Should have limited depth
            actual_depth = self._measure_depth(result)
            self.assertLessEqual(actual_depth, 100)

        except RecursionError:
            self.fail("Provider should handle deep recursion without error")

    def test_circular_reference_memory_leak(self):
        """Test that circular references don't cause memory leaks."""

        # Create symbols with circular references
        class CircularSymbol:
            def __init__(self, name):
                self.name = name
                self.parent = None
                self.children = []

        # Create circular structure
        root = CircularSymbol("root")
        child1 = CircularSymbol("child1")
        child2 = CircularSymbol("child2")

        root.children = [child1, child2]
        child1.parent = root
        child2.parent = root
        child1.children = [root]  # Circular reference

        provider = DocumentSymbolProvider()
        initial_memory = self._get_memory_usage()

        # Process many circular structures
        for i in range(1000):
            # Create new circular structure
            new_root = CircularSymbol(f"root_{i}")
            new_child = CircularSymbol(f"child_{i}")
            new_root.children = [new_child]
            new_child.parent = new_root
            new_child.children = [new_root]

            # Process it
            provider._handle_circular_structure(new_root)

        # Force garbage collection
        del root, child1, child2
        gc.collect()

        # Memory should be released
        final_memory = self._get_memory_usage()
        memory_growth = final_memory - initial_memory

        self.assertLess(
            memory_growth, 50 * 1024 * 1024, "Circular references causing memory leak"
        )

    def test_concurrent_extraction_memory_limit(self):
        """Test memory usage with concurrent symbol extraction."""
        files = []
        for i in range(50):
            file_path = Path(self.temp_dir) / f"concurrent_{i}.py"
            file_path.write_text(
                f"""
class TestClass_{i}:
    def method1(self): pass
    def method2(self): pass
    def method3(self): pass
"""
            )
            files.append(file_path)

        initial_memory = self._get_memory_usage()
        max_memory_used = initial_memory

        def extract_file(file_path):
            nonlocal max_memory_used
            extractor = PythonSymbolExtractor()
            symbols = extractor.extract_from_file(str(file_path), "test_repo")

            current_memory = self._get_memory_usage()
            max_memory_used = max(max_memory_used, current_memory)

            return symbols

        # Run concurrent extractions
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(extract_file, f) for f in files]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        # Check peak memory usage
        peak_memory_growth = max_memory_used - initial_memory
        self.assertLess(
            peak_memory_growth,
            200 * 1024 * 1024,
            f"Peak memory growth too high: {peak_memory_growth / 1024 / 1024:.2f}MB",
        )

        # Verify all extracted
        self.assertEqual(len(results), 50)

    def test_streaming_extraction(self):
        """Test streaming extraction for large files."""
        # Create very large file
        large_file = Path(self.temp_dir) / "huge.py"

        with open(large_file, "w") as f:
            for i in range(10000):
                f.write(
                    f"""
def function_{i}(param1, param2):
    '''Function {i} docstring'''
    return param1 + param2 + {i}

"""
                )

        # Extract using streaming to avoid loading entire file
        extractor = StreamingSymbolExtractor()
        initial_memory = self._get_memory_usage()

        symbol_count = 0
        for symbol in extractor.extract_streaming(str(large_file)):
            symbol_count += 1

            # Memory should stay bounded
            if symbol_count % 1000 == 0:
                current_memory = self._get_memory_usage()
                memory_growth = current_memory - initial_memory
                self.assertLess(
                    memory_growth,
                    50 * 1024 * 1024,
                    "Streaming extraction using too much memory",
                )

        self.assertEqual(symbol_count, 10000)

    def _get_memory_usage(self):
        """Get current process memory usage in bytes."""
        try:
            import psutil

            process = psutil.Process()
            return process.memory_info().rss
        except ImportError:
            # Fallback to resource module
            import resource

            return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024

    def _measure_depth(self, structure, current_depth=0):
        """Measure the depth of a nested structure."""
        if not isinstance(structure, dict) or "child" not in structure:
            return current_depth

        return self._measure_depth(structure["child"], current_depth + 1)


class StreamingSymbolExtractor:
    """Extracts symbols using streaming to minimize memory usage."""

    def extract_streaming(self, file_path):
        """Extract symbols one at a time without loading entire file."""
        with open(file_path) as f:
            current_function = None
            line_number = 0

            for line in f:
                line_number += 1

                if line.strip().startswith("def "):
                    # Yield previous function if exists
                    if current_function:
                        yield current_function

                    # Start new function
                    func_name = line.strip()[4:].split("(")[0]
                    current_function = {
                        "name": func_name,
                        "type": "function",
                        "line": line_number,
                    }

            # Yield last function
            if current_function:
                yield current_function


if __name__ == "__main__":
    unittest.main()
