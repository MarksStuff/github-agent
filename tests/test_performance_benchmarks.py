"""Performance benchmark tests for symbol extraction system."""

import statistics
import tempfile
import time
import unittest
from contextlib import contextmanager
from pathlib import Path

from python_symbol_extractor import PythonSymbolExtractor
from repository_indexer import PythonRepositoryIndexer
from symbol_storage import SQLiteSymbolStorage as SymbolStorage


class TestPerformanceBenchmarks(unittest.TestCase):
    """Performance benchmarks for the symbol extraction system."""

    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.extractor = PythonSymbolExtractor()
        self.results = []

    def tearDown(self):
        """Clean up and report results."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

        # Report benchmark results
        if self.results:
            print("\n=== Performance Benchmark Results ===")
            for result in self.results:
                print(result)

    @contextmanager
    def benchmark(self, name):
        """Context manager for benchmarking."""
        start_time = time.perf_counter()
        yield
        elapsed = time.perf_counter() - start_time
        result = f"{name}: {elapsed:.3f}s"
        self.results.append(result)
        return elapsed

    def test_single_file_extraction_performance(self):
        """Benchmark single file extraction performance."""
        # Create test file with various complexity levels
        sizes = [100, 500, 1000, 5000]

        for size in sizes:
            file_path = Path(self.temp_dir) / f"test_{size}.py"
            self._create_test_file(file_path, size)

            with self.benchmark(f"Extract {size} symbols"):
                symbols = self.extractor.extract_symbols(str(file_path))
                self.assertGreater(len(symbols), 0)

            # Performance assertion - should be roughly linear
            # Allow 0.01s per 100 symbols
            max_time = size * 0.0001
            elapsed = self.results[-1].split(": ")[1].replace("s", "")
            self.assertLess(
                float(elapsed), max_time, f"Extraction too slow for {size} symbols"
            )

    def test_batch_extraction_performance(self):
        """Benchmark batch file extraction performance."""
        file_counts = [10, 50, 100]

        for count in file_counts:
            files = []
            for i in range(count):
                file_path = Path(self.temp_dir) / f"batch_{count}_{i}.py"
                self._create_test_file(file_path, 100)
                files.append(file_path)

            with self.benchmark(f"Batch extract {count} files"):
                for file in files:
                    self.extractor.extract_symbols(str(file))

            # Should scale linearly with file count
            max_time = count * 0.1
            elapsed = float(self.results[-1].split(": ")[1].replace("s", ""))
            self.assertLess(
                elapsed, max_time, f"Batch extraction too slow for {count} files"
            )

    def test_storage_insertion_performance(self):
        """Benchmark database insertion performance."""
        db_path = Path(self.temp_dir) / "perf.db"
        storage = SymbolStorage(str(db_path))

        symbol_counts = [100, 1000, 10000]

        for count in symbol_counts:
            symbols = self._generate_symbols(count)

            with self.benchmark(f"Insert {count} symbols"):
                storage.store_symbols("test.py", symbols)

            # Verify insertion
            retrieved = storage.get_symbols("test.py")
            self.assertEqual(len(retrieved), count)

            # Clear for next test
            storage.clear_symbols("test.py")

    def test_search_performance(self):
        """Benchmark symbol search performance."""
        db_path = Path(self.temp_dir) / "search.db"
        storage = SymbolStorage(str(db_path))

        # Populate database
        total_symbols = 50000
        files_count = 100
        symbols_per_file = total_symbols // files_count

        for i in range(files_count):
            symbols = self._generate_symbols(symbols_per_file, prefix=f"file_{i}")
            storage.store_symbols(f"file_{i}.py", symbols)

        # Benchmark different search patterns
        search_patterns = [
            ("Exact match", "file_50_symbol_25"),
            ("Prefix search", "file_50"),
            ("Substring search", "symbol"),
            ("Rare match", "file_99_symbol_499"),
        ]

        for pattern_name, query in search_patterns:
            with self.benchmark(f"Search '{pattern_name}' in {total_symbols} symbols"):
                results = storage.search_symbols(query)
                self.assertIsNotNone(results)

    def test_concurrent_extraction_performance(self):
        """Benchmark concurrent extraction performance."""
        import concurrent.futures

        # Create test files
        file_count = 100
        files = []
        for i in range(file_count):
            file_path = Path(self.temp_dir) / f"concurrent_{i}.py"
            self._create_test_file(file_path, 50)
            files.append(file_path)

        # Single-threaded baseline
        with self.benchmark(f"Sequential extraction of {file_count} files"):
            for file in files:
                self.extractor.extract_symbols(str(file))

        sequential_time = float(self.results[-1].split(": ")[1].replace("s", ""))

        # Multi-threaded extraction
        worker_counts = [2, 4, 8]

        for workers in worker_counts:
            with self.benchmark(f"Concurrent extraction with {workers} workers"):
                with concurrent.futures.ThreadPoolExecutor(
                    max_workers=workers
                ) as executor:
                    futures = [
                        executor.submit(self.extractor.extract_symbols, str(file))
                        for file in files
                    ]
                    results = [
                        f.result() for f in concurrent.futures.as_completed(futures)
                    ]

            concurrent_time = float(self.results[-1].split(": ")[1].replace("s", ""))

            # Should show speedup with more workers
            speedup = sequential_time / concurrent_time
            self.assertGreater(speedup, 1.0, f"No speedup with {workers} workers")

    def test_memory_efficiency_large_files(self):
        """Benchmark memory efficiency with large files."""
        import os

        import psutil

        process = psutil.Process(os.getpid())

        # Create increasingly large files
        sizes = [1000, 5000, 10000, 20000]
        memory_usage = []

        for size in sizes:
            file_path = Path(self.temp_dir) / f"large_{size}.py"
            self._create_test_file(file_path, size)

            # Measure memory before and after
            memory_before = process.memory_info().rss

            with self.benchmark(f"Extract {size} symbols (memory test)"):
                symbols = self.extractor.extract_symbols(str(file_path))

            memory_after = process.memory_info().rss
            memory_increase = (memory_after - memory_before) / 1024 / 1024  # MB
            memory_usage.append(memory_increase)

            # Memory usage should be reasonable
            self.assertLess(
                memory_increase,
                size * 0.01,
                f"Excessive memory use for {size} symbols: {memory_increase:.2f}MB",
            )

        # Memory usage should scale sub-linearly
        if len(memory_usage) > 1:
            growth_rate = memory_usage[-1] / memory_usage[0]
            size_growth = sizes[-1] / sizes[0]
            self.assertLess(
                growth_rate, size_growth, "Memory usage scaling is not sub-linear"
            )

    def test_cache_performance(self):
        """Benchmark cache hit/miss performance."""
        cache = SymbolCache(max_size=1000)

        # Populate cache
        with self.benchmark("Populate cache with 1000 entries"):
            for i in range(1000):
                cache.put(f"key_{i}", f"value_{i}")

        # Cache hits
        hit_times = []
        for _ in range(10):
            start = time.perf_counter()
            for i in range(100):
                value = cache.get(f"key_{i}")
                self.assertIsNotNone(value)
            hit_times.append(time.perf_counter() - start)

        avg_hit_time = statistics.mean(hit_times)
        self.results.append(f"Average cache hit time (100 items): {avg_hit_time:.6f}s")

        # Cache misses
        miss_times = []
        for _ in range(10):
            start = time.perf_counter()
            for i in range(100):
                value = cache.get(f"missing_{i}")
                self.assertIsNone(value)
            miss_times.append(time.perf_counter() - start)

        avg_miss_time = statistics.mean(miss_times)
        self.results.append(
            f"Average cache miss time (100 items): {avg_miss_time:.6f}s"
        )

        # Hits should be faster than misses
        self.assertLess(avg_hit_time, avg_miss_time * 2)

    def test_incremental_update_performance(self):
        """Benchmark incremental update performance."""
        db_path = Path(self.temp_dir) / "incremental.db"
        storage = SymbolStorage(str(db_path))

        # Initial population
        initial_symbols = self._generate_symbols(1000)
        storage.store_symbols("test.py", initial_symbols)

        # Benchmark incremental updates
        update_sizes = [10, 50, 100, 500]

        for size in update_sizes:
            new_symbols = self._generate_symbols(size, prefix="updated")

            with self.benchmark(f"Incremental update of {size} symbols"):
                # Remove old symbols
                storage.clear_symbols("test.py")
                # Add updated symbols
                all_symbols = initial_symbols[: 1000 - size] + new_symbols
                storage.store_symbols("test.py", all_symbols)

            # Verify update
            retrieved = storage.get_symbols("test.py")
            self.assertEqual(len(retrieved), 1000)

    def test_repository_indexing_performance(self):
        """Benchmark full repository indexing performance."""
        # Create mock repository structure
        repo_dir = Path(self.temp_dir) / "test_repo"
        repo_dir.mkdir()

        # Create directory structure
        subdirs = ["src", "tests", "lib", "utils"]
        total_files = 0

        for subdir in subdirs:
            dir_path = repo_dir / subdir
            dir_path.mkdir()

            for i in range(25):
                file_path = dir_path / f"module_{i}.py"
                self._create_test_file(file_path, 100)
                total_files += 1

        # Create indexer
        db_path = Path(self.temp_dir) / "repo.db"
        storage = SymbolStorage(str(db_path))
        indexer = PythonRepositoryIndexer(self.extractor, storage)

        with self.benchmark(f"Index repository with {total_files} files"):
            result = indexer.index_repository(str(repo_dir), "test_repo")

        self.assertEqual(len(result.processed_files), total_files)

        # Performance target: ~10ms per file
        elapsed = float(self.results[-1].split(": ")[1].replace("s", ""))
        self.assertLess(
            elapsed,
            total_files * 0.01,
            f"Repository indexing too slow: {elapsed:.2f}s for {total_files} files",
        )

    def test_query_optimization(self):
        """Benchmark query optimization strategies."""
        db_path = Path(self.temp_dir) / "query.db"
        storage = SymbolStorage(str(db_path))

        # Populate with hierarchical data
        for i in range(100):
            symbols = []
            for j in range(100):
                symbols.append(
                    {
                        "name": f"class_{i}_method_{j}",
                        "type": "method",
                        "line": j,
                        "parent": f"class_{i}",
                    }
                )
            storage.store_symbols(f"file_{i}.py", symbols)

        # Benchmark different query types
        queries = [
            ("Simple lookup", lambda: storage.get_symbol_by_name("class_50_method_50")),
            ("Wildcard search", lambda: storage.search_symbols("class_*_method_*")),
            ("Type filter", lambda: storage.get_symbols_by_type("method")),
            ("Parent filter", lambda: storage.get_children("class_50")),
        ]

        for query_name, query_func in queries:
            times = []
            for _ in range(10):
                start = time.perf_counter()
                result = query_func()
                times.append(time.perf_counter() - start)

            avg_time = statistics.mean(times)
            self.results.append(f"{query_name} average: {avg_time:.6f}s")

            # All queries should complete quickly
            self.assertLess(avg_time, 0.1, f"{query_name} too slow: {avg_time:.3f}s")

    def _create_test_file(self, file_path, symbol_count):
        """Create a test Python file with specified number of symbols."""
        content = []

        for i in range(symbol_count // 3):
            content.append(
                f"""
class Class_{i}:
    '''Class {i} docstring'''

    def method_{i}(self):
        '''Method {i} docstring'''
        return {i}

    @property
    def property_{i}(self):
        return self._value_{i}
"""
            )

        for i in range(symbol_count // 3):
            content.append(
                f"""
def function_{i}(param1, param2):
    '''Function {i} docstring'''
    return param1 + param2 + {i}
"""
            )

        for i in range(symbol_count // 3):
            content.append(f"variable_{i} = {i}")

        file_path.write_text("\n".join(content))

    def _generate_symbols(self, count, prefix="symbol"):
        """Generate test symbols."""
        symbols = []
        for i in range(count):
            symbols.append(
                {
                    "name": f"{prefix}_symbol_{i}",
                    "type": "function" if i % 2 == 0 else "class",
                    "line": i,
                    "column": 0,
                    "docstring": f"Docstring for {prefix}_symbol_{i}",
                }
            )
        return symbols


class SymbolCache:
    """Simple cache implementation for benchmarking."""

    def __init__(self, max_size):
        self.max_size = max_size
        self.cache = {}
        self.access_count = {}

    def put(self, key, value):
        """Add item to cache."""
        if len(self.cache) >= self.max_size:
            # Evict least recently used
            lru_key = min(self.access_count, key=self.access_count.get)
            del self.cache[lru_key]
            del self.access_count[lru_key]

        self.cache[key] = value
        self.access_count[key] = time.time()

    def get(self, key):
        """Get item from cache."""
        if key in self.cache:
            self.access_count[key] = time.time()
            return self.cache[key]
        return None


if __name__ == "__main__":
    # Run with verbose output for benchmark results
    unittest.main(verbosity=2)
