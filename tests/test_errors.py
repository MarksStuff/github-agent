"""Unit tests for custom exception hierarchy."""

import pytest

from errors import (
    CacheCorruptionError,
    ConfigurationError,
    DatabaseMigrationError,
    DocumentSymbolError,
    HierarchyValidationError,
    LSPConnectionError,
    SymbolExtractionError,
)


class TestDocumentSymbolError:
    """Test base exception class."""

    def test_base_exception_creation(self):
        """Test creating base exception."""
        error = DocumentSymbolError("Base error")
        assert str(error) == "Base error"
        assert isinstance(error, Exception)

    def test_base_exception_inheritance(self):
        """Test exception inheritance chain."""
        error = DocumentSymbolError("Test")
        assert isinstance(error, Exception)
        assert type(error).__name__ == "DocumentSymbolError"


class TestSymbolExtractionError:
    """Test symbol extraction error handling."""

    def test_extraction_error_creation(self):
        """Test creating extraction error."""
        error = SymbolExtractionError("Failed to extract")
        assert str(error) == "Failed to extract"
        assert isinstance(error, DocumentSymbolError)

    def test_extraction_error_with_file_path(self):
        """Test extraction error with context."""
        error = SymbolExtractionError("Failed to parse file: /path/to/file.py")
        assert "file.py" in str(error)

    def test_extraction_error_chain(self):
        """Test error chaining."""
        cause = ValueError("Invalid syntax")
        error = SymbolExtractionError("Extraction failed")
        error.__cause__ = cause
        assert error.__cause__ == cause


class TestLSPConnectionError:
    """Test LSP connection error handling."""

    def test_lsp_error_creation(self):
        """Test creating LSP connection error."""
        error = LSPConnectionError("Connection refused")
        assert str(error) == "Connection refused"
        assert isinstance(error, DocumentSymbolError)

    def test_lsp_error_timeout(self):
        """Test LSP timeout error."""
        error = LSPConnectionError("Connection timeout after 30s")
        assert "timeout" in str(error).lower()

    def test_lsp_error_port_info(self):
        """Test LSP error with port information."""
        error = LSPConnectionError("Failed to connect to localhost:8080")
        assert "8080" in str(error)


class TestHierarchyValidationError:
    """Test hierarchy validation error handling."""

    def test_hierarchy_error_creation(self):
        """Test creating hierarchy validation error."""
        error = HierarchyValidationError("Invalid parent reference")
        assert str(error) == "Invalid parent reference"
        assert isinstance(error, DocumentSymbolError)

    def test_hierarchy_error_with_details(self):
        """Test hierarchy error with details."""
        error = HierarchyValidationError("Circular reference detected: A -> B -> A")
        assert "Circular reference" in str(error)


class TestCacheCorruptionError:
    """Test cache corruption error handling."""

    def test_cache_error_creation(self):
        """Test creating cache corruption error."""
        error = CacheCorruptionError("Cache data invalid")
        assert str(error) == "Cache data invalid"
        assert isinstance(error, DocumentSymbolError)

    def test_cache_error_with_details(self):
        """Test cache error with details."""
        error = CacheCorruptionError("Failed to deserialize cache entry for file.py")
        assert "file.py" in str(error)
        assert "deserialize" in str(error)


class TestConfigurationError:
    """Test configuration error handling."""

    def test_config_error_creation(self):
        """Test creating configuration error."""
        error = ConfigurationError("Invalid config")
        assert str(error) == "Invalid config"
        assert isinstance(error, DocumentSymbolError)

    def test_config_error_missing_field(self):
        """Test config error for missing field."""
        error = ConfigurationError("Missing required field: 'database_path'")
        assert "database_path" in str(error)

    def test_config_error_invalid_value(self):
        """Test config error for invalid value."""
        error = ConfigurationError("Invalid value for 'max_workers': -1")
        assert "max_workers" in str(error)
        assert "-1" in str(error)


class TestDatabaseMigrationError:
    """Test database migration error handling."""

    def test_migration_error_creation(self):
        """Test creating migration error."""
        error = DatabaseMigrationError("Migration failed")
        assert str(error) == "Migration failed"
        assert isinstance(error, DocumentSymbolError)

    def test_migration_error_with_version(self):
        """Test migration error with version info."""
        error = DatabaseMigrationError("Cannot migrate from v1 to v3: missing v2")
        assert "v1" in str(error)
        assert "v3" in str(error)


class TestExceptionHierarchy:
    """Test the complete exception hierarchy."""

    def test_all_exceptions_inherit_from_base(self):
        """Test all exceptions inherit from DocumentSymbolError."""
        exceptions = [
            SymbolExtractionError("test"),
            LSPConnectionError("test"),
            HierarchyValidationError("test"),
            CacheCorruptionError("test"),
            ConfigurationError("test"),
            DatabaseMigrationError("test"),
        ]

        for exc in exceptions:
            assert isinstance(exc, DocumentSymbolError)
            assert isinstance(exc, Exception)

    def test_exception_types_are_distinct(self):
        """Test each exception type is distinct."""
        exceptions = [
            SymbolExtractionError("test"),
            LSPConnectionError("test"),
            HierarchyValidationError("test"),
            CacheCorruptionError("test"),
            ConfigurationError("test"),
            DatabaseMigrationError("test"),
        ]

        types = [type(exc) for exc in exceptions]
        assert len(types) == len(set(types))  # All unique types

    def test_raising_and_catching(self):
        """Test raising and catching specific exceptions."""
        with pytest.raises(SymbolExtractionError):
            raise SymbolExtractionError("Test extraction error")

        with pytest.raises(DocumentSymbolError):
            raise HierarchyValidationError("Test validation error")

        # Test catching base catches all
        try:
            raise CacheCorruptionError("test")
        except DocumentSymbolError as e:
            assert isinstance(e, CacheCorruptionError)
