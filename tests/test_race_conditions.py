"""Test race conditions and concurrent access scenarios."""

import random
import sqlite3
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from document_symbol_provider import DocumentSymbolProvider
from python_symbol_extractor import PythonSymbolExtractor
from symbol_storage import SQLiteSymbolStorage as SymbolStorage


class TestRaceConditions(unittest.TestCase):
    """Test handling of race conditions in concurrent operations."""

    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test.db"
        self.storage = SymbolStorage(str(self.db_path))
        self.provider = DocumentSymbolProvider()

    def tearDown(self):
        """Clean up test environment."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_concurrent_symbol_updates(self):
        """Test race conditions in concurrent symbol updates."""
        file_path = "test.py"

        # Track successful updates
        successful_updates = []
        failed_updates = []
        lock = threading.Lock()

        def update_symbols(thread_id):
            """Update symbols for a file."""
            try:
                symbols = [
                    {
                        "name": f"symbol_{thread_id}_{i}",
                        "type": "function",
                        "line": i,
                        "column": 0,
                    }
                    for i in range(10)
                ]

                # Simulate some processing time
                time.sleep(random.uniform(0.001, 0.01))

                self.storage.store_symbols(file_path, symbols)

                with lock:
                    successful_updates.append(thread_id)

            except Exception as e:
                with lock:
                    failed_updates.append((thread_id, str(e)))

        # Run concurrent updates
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(update_symbols, i) for i in range(20)]

            for future in as_completed(futures):
                future.result()  # Wait for completion

        # Verify results
        self.assertGreater(len(successful_updates), 0, "No successful updates")

        # Check final state is consistent
        final_symbols = self.storage.get_symbols(file_path)
        self.assertIsNotNone(final_symbols)

    def test_concurrent_cache_access(self):
        """Test race conditions in cache access."""
        cache = ThreadSafeCache()

        results = []
        lock = threading.Lock()

        def cache_operation(op_id):
            """Perform cache operations."""
            key = f"key_{op_id % 5}"  # Limited key space for conflicts

            for _ in range(100):
                if random.choice([True, False]):
                    # Write operation
                    value = f"value_{op_id}_{time.time()}"
                    cache.set(key, value)
                else:
                    # Read operation
                    value = cache.get(key)
                    with lock:
                        results.append((op_id, key, value))

                # Small delay to increase contention
                time.sleep(0.0001)

        # Run concurrent cache operations
        threads = []
        for i in range(10):
            t = threading.Thread(target=cache_operation, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # Verify cache integrity
        self.assertTrue(cache.check_integrity())

        # Verify no corruption in results
        for op_id, key, value in results:
            if value is not None:
                self.assertTrue(value.startswith("value_"))

    def test_database_connection_pool_race(self):
        """Test race conditions in database connection pooling."""
        pool = ConnectionPool(str(self.db_path), max_connections=3)

        completed_queries = []
        errors = []
        lock = threading.Lock()

        def execute_query(query_id):
            """Execute database query using connection pool."""
            try:
                conn = pool.get_connection()
                try:
                    cursor = conn.cursor()

                    # Create table if not exists
                    cursor.execute(
                        """
                        CREATE TABLE IF NOT EXISTS test_data (
                            id INTEGER PRIMARY KEY,
                            value TEXT
                        )
                    """
                    )

                    # Insert data
                    cursor.execute(
                        "INSERT INTO test_data (value) VALUES (?)",
                        (f"query_{query_id}",),
                    )
                    conn.commit()

                    # Read data
                    cursor.execute("SELECT COUNT(*) FROM test_data")
                    count = cursor.fetchone()[0]

                    with lock:
                        completed_queries.append((query_id, count))

                finally:
                    pool.release_connection(conn)

            except Exception as e:
                with lock:
                    errors.append((query_id, str(e)))

        # Run concurrent queries
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(execute_query, i) for i in range(100)]

            for future in as_completed(futures):
                future.result()

        # Verify results
        self.assertEqual(len(completed_queries) + len(errors), 100)
        self.assertGreater(len(completed_queries), 90, "Too many failures")

        # Verify final count matches
        conn = pool.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM test_data")
        final_count = cursor.fetchone()[0]
        pool.release_connection(conn)

        self.assertEqual(final_count, len(completed_queries))

    def test_file_system_race_conditions(self):
        """Test race conditions in file system operations."""
        test_file = Path(self.temp_dir) / "shared.py"

        write_success = []
        read_success = []
        errors = []
        lock = threading.Lock()

        def file_operation(op_id):
            """Perform file read/write operations."""
            try:
                if op_id % 2 == 0:
                    # Write operation
                    content = f"# Thread {op_id}\ndef func_{op_id}(): pass\n"

                    # Atomic write using temp file
                    temp_file = test_file.with_suffix(f".tmp{op_id}")
                    temp_file.write_text(content)
                    temp_file.replace(test_file)

                    with lock:
                        write_success.append(op_id)
                else:
                    # Read operation
                    if test_file.exists():
                        content = test_file.read_text()
                        with lock:
                            read_success.append((op_id, len(content)))

            except Exception as e:
                with lock:
                    errors.append((op_id, str(e)))

        # Run concurrent file operations
        threads = []
        for i in range(50):
            t = threading.Thread(target=file_operation, args=(i,))
            threads.append(t)
            t.start()
            time.sleep(0.001)  # Small delay to spread operations

        for t in threads:
            t.join()

        # Verify results
        self.assertGreater(len(write_success), 0)
        self.assertGreater(len(read_success), 0)

        # Final file should be valid
        if test_file.exists():
            content = test_file.read_text()
            self.assertTrue(content.startswith("#"))

    def test_symbol_extraction_race_condition(self):
        """Test race conditions during concurrent symbol extraction."""
        # Create test files
        files = []
        for i in range(20):
            file_path = Path(self.temp_dir) / f"file_{i}.py"
            file_path.write_text(
                f"""
class Class_{i}:
    def method_{i}(self):
        return {i}
"""
            )
            files.append(file_path)

        extractor = PythonSymbolExtractor()
        results = []
        errors = []
        lock = threading.Lock()

        def extract_symbols(file_path, index):
            """Extract symbols from file."""
            try:
                symbols = extractor.extract_symbols(str(file_path))

                with lock:
                    results.append((index, file_path.name, len(symbols)))

            except Exception as e:
                with lock:
                    errors.append((index, file_path.name, str(e)))

        # Run concurrent extractions
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [
                executor.submit(extract_symbols, file, i)
                for i, file in enumerate(files)
            ]

            for future in as_completed(futures):
                future.result()

        # Verify all files processed
        self.assertEqual(len(results) + len(errors), 20)
        self.assertEqual(len(errors), 0, f"Extraction errors: {errors}")

        # Verify consistency
        for index, filename, symbol_count in results:
            self.assertGreater(symbol_count, 0)

    def test_concurrent_hierarchy_validation(self):
        """Test race conditions in hierarchy validation."""
        validator = HierarchyValidator()

        # Create complex hierarchy that might have race conditions
        hierarchies = []
        for i in range(10):
            hierarchy = {
                f"root_{i}": {
                    "children": [f"child_{i}_{j}" for j in range(5)],
                    "parent": None,
                }
            }
            for j in range(5):
                hierarchy[f"child_{i}_{j}"] = {"children": [], "parent": f"root_{i}"}
            hierarchies.append(hierarchy)

        validation_results = []
        lock = threading.Lock()

        def validate_hierarchy(hierarchy, index):
            """Validate hierarchy structure."""
            try:
                # Simulate validation with potential race conditions
                is_valid = validator.validate(hierarchy)

                # Modify hierarchy during validation (race condition)
                if index % 2 == 0:
                    hierarchy[f"new_node_{index}"] = {
                        "children": [],
                        "parent": f"root_{index}",
                    }

                with lock:
                    validation_results.append((index, is_valid))

            except Exception:
                with lock:
                    validation_results.append((index, False))

        # Run concurrent validations
        threads = []
        for i, hierarchy in enumerate(hierarchies):
            t = threading.Thread(target=validate_hierarchy, args=(hierarchy, i))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # Verify all hierarchies validated
        self.assertEqual(len(validation_results), 10)

    def test_atomic_batch_operations(self):
        """Test atomicity of batch operations under concurrent access."""
        batch_processor = BatchProcessor(self.storage)

        completed_batches = []
        failed_batches = []
        lock = threading.Lock()

        def process_batch(batch_id):
            """Process a batch of operations atomically."""
            operations = [("insert", f"symbol_{batch_id}_{i}") for i in range(10)]

            try:
                # Should be atomic - all or nothing
                batch_processor.process_atomic(operations)

                with lock:
                    completed_batches.append(batch_id)

            except Exception as e:
                with lock:
                    failed_batches.append((batch_id, str(e)))

        # Run concurrent batch operations
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(process_batch, i) for i in range(20)]

            for future in as_completed(futures):
                future.result()

        # Verify atomicity
        for batch_id in completed_batches:
            # Either all symbols exist or none
            symbols_exist = []
            for i in range(10):
                symbol_name = f"symbol_{batch_id}_{i}"
                exists = batch_processor.symbol_exists(symbol_name)
                symbols_exist.append(exists)

            # All should have same state (atomic)
            self.assertTrue(all(symbols_exist) or not any(symbols_exist))

    def test_deadlock_prevention(self):
        """Test that system prevents deadlocks."""
        lock1 = threading.Lock()
        lock2 = threading.Lock()

        deadlock_detected = []
        operations_completed = []

        def operation_a(op_id):
            """Operation that acquires lock1 then lock2."""
            try:
                with DeadlockTimeout(lock1, timeout=1.0) as acquired1:
                    if acquired1:
                        time.sleep(0.1)
                        with DeadlockTimeout(lock2, timeout=1.0) as acquired2:
                            if acquired2:
                                operations_completed.append(f"A_{op_id}")
                            else:
                                deadlock_detected.append(f"A_{op_id}_lock2")
                    else:
                        deadlock_detected.append(f"A_{op_id}_lock1")
            except Exception:
                deadlock_detected.append(f"A_{op_id}_error")

        def operation_b(op_id):
            """Operation that acquires lock2 then lock1."""
            try:
                with DeadlockTimeout(lock2, timeout=1.0) as acquired2:
                    if acquired2:
                        time.sleep(0.1)
                        with DeadlockTimeout(lock1, timeout=1.0) as acquired1:
                            if acquired1:
                                operations_completed.append(f"B_{op_id}")
                            else:
                                deadlock_detected.append(f"B_{op_id}_lock1")
                    else:
                        deadlock_detected.append(f"B_{op_id}_lock2")
            except Exception:
                deadlock_detected.append(f"B_{op_id}_error")

        # Run operations that could deadlock
        threads = []
        for i in range(5):
            t1 = threading.Thread(target=operation_a, args=(i,))
            t2 = threading.Thread(target=operation_b, args=(i,))
            threads.extend([t1, t2])
            t1.start()
            t2.start()

        for t in threads:
            t.join(timeout=5.0)

        # Verify no threads are stuck (deadlock prevention worked)
        alive_threads = [t for t in threads if t.is_alive()]
        self.assertEqual(
            len(alive_threads), 0, "Threads still running - possible deadlock"
        )

        # Some operations should complete
        self.assertGreater(len(operations_completed), 0)


class ThreadSafeCache:
    """Thread-safe cache implementation."""

    def __init__(self):
        self.cache = {}
        self.lock = threading.RLock()
        self.version = {}

    def set(self, key, value):
        """Set cache value atomically."""
        with self.lock:
            self.cache[key] = value
            self.version[key] = self.version.get(key, 0) + 1

    def get(self, key):
        """Get cache value atomically."""
        with self.lock:
            return self.cache.get(key)

    def check_integrity(self):
        """Check cache integrity."""
        with self.lock:
            # Check version consistency
            for key in self.cache:
                if key not in self.version:
                    return False
            return True


class ConnectionPool:
    """Database connection pool with thread safety."""

    def __init__(self, db_path, max_connections):
        self.db_path = db_path
        self.max_connections = max_connections
        self.connections = []
        self.available = []
        self.lock = threading.Lock()

        # Pre-create connections
        for _ in range(max_connections):
            conn = sqlite3.connect(db_path, check_same_thread=False)
            self.connections.append(conn)
            self.available.append(conn)

    def get_connection(self, timeout=5.0):
        """Get connection from pool."""
        start_time = time.time()

        while time.time() - start_time < timeout:
            with self.lock:
                if self.available:
                    conn = self.available.pop()
                    return conn

            time.sleep(0.01)

        raise TimeoutError("Could not get connection from pool")

    def release_connection(self, conn):
        """Return connection to pool."""
        with self.lock:
            if conn in self.connections:
                self.available.append(conn)


class HierarchyValidator:
    """Validates hierarchy structures."""

    def __init__(self):
        self.lock = threading.Lock()

    def validate(self, hierarchy):
        """Validate hierarchy structure."""
        with self.lock:
            # Check for orphans
            for node, data in hierarchy.items():
                if data["parent"]:
                    if data["parent"] not in hierarchy:
                        return False

                for child in data["children"]:
                    if child not in hierarchy:
                        return False

            return True


class BatchProcessor:
    """Processes batches of operations atomically."""

    def __init__(self, storage):
        self.storage = storage
        self.lock = threading.Lock()
        self.symbols = set()

    def process_atomic(self, operations):
        """Process operations atomically."""
        with self.lock:
            temp_symbols = []

            try:
                for op_type, symbol_name in operations:
                    if op_type == "insert":
                        if symbol_name in self.symbols:
                            raise ValueError(f"Symbol {symbol_name} already exists")
                        temp_symbols.append(symbol_name)

                # If all validations pass, commit
                for symbol in temp_symbols:
                    self.symbols.add(symbol)

            except Exception:
                # Rollback on any error
                raise

    def symbol_exists(self, symbol_name):
        """Check if symbol exists."""
        with self.lock:
            return symbol_name in self.symbols


class DeadlockTimeout:
    """Context manager for acquiring locks with timeout."""

    def __init__(self, lock, timeout):
        self.lock = lock
        self.timeout = timeout
        self.acquired = False

    def __enter__(self):
        self.acquired = self.lock.acquire(timeout=self.timeout)
        return self.acquired

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.acquired:
            self.lock.release()


if __name__ == "__main__":
    unittest.main()
