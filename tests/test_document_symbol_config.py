"""Unit tests for DocumentSymbolConfig."""

import json
import tempfile
from pathlib import Path

import pytest

from document_symbol_config import DocumentSymbolConfig
from errors import ConfigurationError


class TestDocumentSymbolConfigDefaults:
    """Test default configuration values."""

    def test_default_config_creation(self):
        """Test creating config with defaults."""
        config = DocumentSymbolConfig()
        assert config.database_path is not None
        assert config.max_workers == 4
        assert config.cache_enabled == True
        assert config.cache_ttl_seconds == 3600

    def test_default_database_path(self):
        """Test default database path location."""
        config = DocumentSymbolConfig()
        expected_path = Path.home() / ".github-agent" / "document_symbols.db"
        assert config.database_path == str(expected_path)

    def test_default_extractors(self):
        """Test default extractor configuration."""
        config = DocumentSymbolConfig()
        assert "python" in config.extractors
        assert config.extractors["python"] == "PythonSymbolExtractor"

    def test_default_file_extensions(self):
        """Test default file extension mappings."""
        config = DocumentSymbolConfig()
        assert ".py" in config.file_extensions
        assert config.file_extensions[".py"] == "python"


class TestDocumentSymbolConfigCustomization:
    """Test configuration customization."""

    def test_custom_database_path(self):
        """Test setting custom database path."""
        config = DocumentSymbolConfig(database_path="/custom/path/db.sqlite")
        assert config.database_path == "/custom/path/db.sqlite"

    def test_custom_max_workers(self):
        """Test setting custom worker count."""
        config = DocumentSymbolConfig(max_workers=8)
        assert config.max_workers == 8

    def test_disable_cache(self):
        """Test disabling cache."""
        config = DocumentSymbolConfig(cache_enabled=False)
        assert config.cache_enabled == False

    def test_custom_cache_ttl(self):
        """Test setting custom cache TTL."""
        config = DocumentSymbolConfig(cache_ttl_seconds=7200)
        assert config.cache_ttl_seconds == 7200

    def test_add_custom_extractor(self):
        """Test adding custom extractor."""
        config = DocumentSymbolConfig()
        config.extractors["rust"] = "RustSymbolExtractor"
        assert config.extractors["rust"] == "RustSymbolExtractor"

    def test_add_custom_file_extension(self):
        """Test adding custom file extension."""
        config = DocumentSymbolConfig()
        config.file_extensions[".rs"] = "rust"
        assert config.file_extensions[".rs"] == "rust"


class TestDocumentSymbolConfigValidation:
    """Test configuration validation."""

    def test_invalid_max_workers(self):
        """Test validation of max_workers."""
        with pytest.raises(ConfigurationError):
            DocumentSymbolConfig(max_workers=-1)

        with pytest.raises(ConfigurationError):
            DocumentSymbolConfig(max_workers=0)

    def test_invalid_cache_ttl(self):
        """Test validation of cache TTL."""
        with pytest.raises(ConfigurationError):
            DocumentSymbolConfig(cache_ttl_seconds=-1)

    def test_invalid_database_path(self):
        """Test validation of database path."""
        # Empty path
        with pytest.raises(ConfigurationError):
            DocumentSymbolConfig(database_path="")

    def test_validate_method(self):
        """Test explicit validation method."""
        config = DocumentSymbolConfig()
        config.validate()  # Should not raise

        config.max_workers = -1
        with pytest.raises(ConfigurationError):
            config.validate()


class TestDocumentSymbolConfigSerialization:
    """Test configuration save/load."""

    def test_to_dict(self):
        """Test converting config to dictionary."""
        config = DocumentSymbolConfig(max_workers=6)
        data = config.to_dict()

        assert isinstance(data, dict)
        assert data["max_workers"] == 6
        assert "database_path" in data
        assert "cache_enabled" in data
        assert "extractors" in data
        assert "file_extensions" in data

    def test_from_dict(self):
        """Test creating config from dictionary."""
        data = {
            "database_path": "/test/path.db",
            "max_workers": 2,
            "cache_enabled": False,
            "cache_ttl_seconds": 1800,
            "extractors": {"python": "PythonExtractor"},
            "file_extensions": {".py": "python"},
        }

        config = DocumentSymbolConfig.from_dict(data)
        assert config.database_path == "/test/path.db"
        assert config.max_workers == 2
        assert config.cache_enabled == False
        assert config.cache_ttl_seconds == 1800

    def test_save_to_file(self):
        """Test saving config to file."""
        from document_symbol_config import DocumentSymbolConfigManager

        config = DocumentSymbolConfig(max_workers=3)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            temp_path = Path(f.name)

        try:
            manager = DocumentSymbolConfigManager(config_file=temp_path)
            manager.save_config(config)

            with open(temp_path) as f:
                data = json.load(f)

            assert data["config"]["max_workers"] == 3
            assert "database_path" in data["config"]
        finally:
            temp_path.unlink()

    def test_load_from_file(self):
        """Test loading config from file."""
        data = {
            "database_path": "/loaded/path.db",
            "max_workers": 5,
            "cache_enabled": True,
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            temp_path = f.name

        try:
            config = DocumentSymbolConfig.load_from_file(temp_path)
            assert config.database_path == "/loaded/path.db"
            assert config.max_workers == 5
            assert config.cache_enabled == True
        finally:
            Path(temp_path).unlink()

    def test_load_from_invalid_file(self):
        """Test loading from invalid file."""
        with pytest.raises(ConfigurationError):
            DocumentSymbolConfig.load_from_file("/nonexistent/file.json")

    def test_load_from_malformed_json(self):
        """Test loading from malformed JSON."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("{ invalid json")
            temp_path = f.name

        try:
            with pytest.raises(ConfigurationError):
                DocumentSymbolConfig.load_from_file(temp_path)
        finally:
            Path(temp_path).unlink()


class TestDocumentSymbolConfigMerge:
    """Test configuration merging."""

    def test_merge_configs(self):
        """Test merging two configurations."""
        config1 = DocumentSymbolConfig(max_workers=2)
        config2 = DocumentSymbolConfig(cache_enabled=False)

        config1.merge(config2)

        assert config1.max_workers == 2  # Unchanged
        assert config1.cache_enabled == False  # Updated from config2

    def test_merge_extractors(self):
        """Test merging extractor configurations."""
        config1 = DocumentSymbolConfig()
        config2 = DocumentSymbolConfig()
        config2.extractors["rust"] = "RustExtractor"

        config1.merge(config2)

        assert "python" in config1.extractors  # Original preserved
        assert "rust" in config1.extractors  # New added

    def test_merge_with_validation(self):
        """Test that merge validates result."""
        config1 = DocumentSymbolConfig()
        config2 = DocumentSymbolConfig()
        config2.max_workers = -1  # Invalid

        with pytest.raises(ConfigurationError):
            config1.merge(config2)


class TestDocumentSymbolConfigHelpers:
    """Test helper methods."""

    def test_get_extractor_for_file(self):
        """Test getting extractor for file type."""
        config = DocumentSymbolConfig()

        assert config.get_extractor_for_file("test.py") == "PythonSymbolExtractor"
        assert (
            config.get_extractor_for_file("/path/to/module.py")
            == "PythonSymbolExtractor"
        )
        assert config.get_extractor_for_file("unknown.xyz") is None

    def test_is_supported_file(self):
        """Test checking if file is supported."""
        config = DocumentSymbolConfig()

        assert config.is_supported_file("test.py") == True
        assert config.is_supported_file("script.pyw") == True
        assert config.is_supported_file("unknown.xyz") == False

    def test_ensure_database_directory(self):
        """Test ensuring database directory exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "subdir" / "db.sqlite"
            config = DocumentSymbolConfig(database_path=str(db_path))

            config.ensure_database_directory()

            assert db_path.parent.exists()
            assert db_path.parent.is_dir()
