"""Test database migration rollback and recovery scenarios."""

import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from errors import DatabaseMigrationError
from symbol_storage import SQLiteSymbolStorage as SymbolStorage


class TestMigrationRollback(unittest.TestCase):
    """Test database migration failure recovery."""

    def setUp(self):
        """Create temporary database for testing."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test.db"
        self.storage = SymbolStorage(str(self.db_path))

    def tearDown(self):
        """Clean up test database."""
        if self.db_path.exists():
            self.db_path.unlink()
        os.rmdir(self.temp_dir)

    def test_migration_rollback_on_schema_error(self):
        """Test rollback when schema migration fails."""
        # Create old schema database
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        # Create v1 schema
        cursor.execute(
            """
            CREATE TABLE symbols (
                id INTEGER PRIMARY KEY,
                name TEXT,
                type TEXT,
                file_path TEXT
            )
        """
        )
        cursor.execute("INSERT INTO symbols VALUES (1, 'test', 'function', 'test.py')")
        conn.commit()

        # Simulate migration failure
        with patch.object(self.storage, "_migrate_schema") as mock_migrate:
            mock_migrate.side_effect = DatabaseMigrationError("Migration failed")

            # Attempt to use storage
            with self.assertRaises(DatabaseMigrationError):
                self.storage.initialize()

            # Verify original data intact
            cursor.execute("SELECT * FROM symbols WHERE id = 1")
            row = cursor.fetchone()
            self.assertEqual(row[1], "test")

        conn.close()

    def test_migration_rollback_on_constraint_violation(self):
        """Test rollback when migration violates constraints."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        # Create schema with unique constraint
        cursor.execute(
            """
            CREATE TABLE symbols (
                id INTEGER PRIMARY KEY,
                name TEXT UNIQUE,
                type TEXT
            )
        """
        )
        cursor.execute("INSERT INTO symbols VALUES (1, 'duplicate', 'function')")
        cursor.execute("INSERT INTO symbols VALUES (2, 'duplicate', 'class')")
        conn.commit()

        # Migration should detect duplicate and rollback
        with self.assertRaises(DatabaseMigrationError) as ctx:
            self.storage._validate_migration_integrity(conn)

        self.assertIn("constraint", str(ctx.exception).lower())

        # Verify data unchanged
        cursor.execute("SELECT COUNT(*) FROM symbols")
        self.assertEqual(cursor.fetchone()[0], 2)

        conn.close()

    def test_migration_partial_failure_recovery(self):
        """Test recovery from partial migration failure."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        # Start transaction
        conn.execute("BEGIN TRANSACTION")

        try:
            # Partial schema update
            cursor.execute(
                """
                CREATE TABLE new_symbols (
                    id INTEGER PRIMARY KEY,
                    name TEXT,
                    parent_id INTEGER
                )
            """
            )

            # Simulate failure mid-migration
            raise DatabaseMigrationError("Disk full")

        except DatabaseMigrationError:
            # Rollback transaction
            conn.rollback()

            # Verify no partial changes
            cursor.execute(
                """
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='new_symbols'
            """
            )
            self.assertIsNone(cursor.fetchone())

        conn.close()

    def test_migration_data_preservation(self):
        """Test that rollback preserves all original data."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        # Create and populate original schema
        cursor.execute(
            """
            CREATE TABLE symbols (
                id INTEGER PRIMARY KEY,
                name TEXT,
                metadata TEXT
            )
        """
        )

        # Insert test data
        test_data = [
            (1, "func1", '{"line": 10}'),
            (2, "class1", '{"line": 20}'),
            (3, "var1", '{"line": 30}'),
        ]
        cursor.executemany("INSERT INTO symbols VALUES (?, ?, ?)", test_data)
        conn.commit()

        # Create savepoint
        conn.execute("SAVEPOINT before_migration")

        try:
            # Attempt migration that will fail
            cursor.execute("ALTER TABLE symbols ADD COLUMN invalid_type INVALID")
        except sqlite3.OperationalError:
            # Rollback to savepoint
            conn.execute("ROLLBACK TO SAVEPOINT before_migration")

        # Verify all data preserved
        cursor.execute("SELECT * FROM symbols ORDER BY id")
        rows = cursor.fetchall()
        self.assertEqual(rows, test_data)

        conn.close()

    def test_concurrent_migration_conflict(self):
        """Test handling of concurrent migration attempts."""
        import threading
        import time

        migration_errors = []

        def attempt_migration():
            try:
                storage = SymbolStorage(str(self.db_path))
                storage._migrate_schema()
            except DatabaseMigrationError as e:
                migration_errors.append(e)

        # Start multiple migration threads
        threads = []
        for _ in range(3):
            t = threading.Thread(target=attempt_migration)
            threads.append(t)
            t.start()
            time.sleep(0.01)  # Small delay to ensure conflicts

        # Wait for completion
        for t in threads:
            t.join()

        # At least one should fail with lock error
        self.assertTrue(
            any(
                "locked" in str(e).lower() or "concurrent" in str(e).lower()
                for e in migration_errors
            )
        )

    def test_migration_backup_creation(self):
        """Test that backup is created before migration."""
        # Create original database
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE symbols (id INTEGER, name TEXT)")
        cursor.execute("INSERT INTO symbols VALUES (1, 'test')")
        conn.commit()
        conn.close()

        # Perform migration
        storage = SymbolStorage(str(self.db_path))
        backup_path = Path(self.temp_dir) / "test.db.backup"

        with patch.object(storage, "_create_backup") as mock_backup:
            mock_backup.return_value = str(backup_path)
            storage._migrate_with_backup()

        # Verify backup was created
        mock_backup.assert_called_once()

    def test_migration_version_tracking(self):
        """Test schema version tracking during migration."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        # Create version table
        cursor.execute(
            """
            CREATE TABLE schema_version (
                version INTEGER PRIMARY KEY,
                applied_at TIMESTAMP
            )
        """
        )
        cursor.execute("INSERT INTO schema_version VALUES (1, datetime('now'))")
        conn.commit()

        # Attempt migration to version 2
        storage = SymbolStorage(str(self.db_path))
        storage._target_version = 2

        try:
            storage._apply_migration(conn, from_version=1, to_version=2)
        except Exception:
            # Check version not updated on failure
            cursor.execute("SELECT MAX(version) FROM schema_version")
            self.assertEqual(cursor.fetchone()[0], 1)

        conn.close()


if __name__ == "__main__":
    unittest.main()
