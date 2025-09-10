#!/usr/bin/env python3

"""
Configuration for document symbol functionality.

Defines configuration parameters for document symbol extraction
and caching behavior.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from errors import ConfigurationError


@dataclass
class DocumentSymbolConfig:
    """Configuration for document symbol extraction."""

    # Database configuration
    database_path: str | None = None
    rebuild_on_schema_change: bool = True
    auto_backup_before_rebuild: bool = True
    backup_retention_days: int = 7

    # Feature flags
    use_document_symbols: bool = True
    enable_hierarchy: bool = True

    # Cache configuration
    cache_enabled: bool = True
    cache_dir: Path | None = None
    cache_ttl_seconds: int = 3600  # 1 hour default
    max_cache_size_mb: int = 100

    # LSP configuration
    lsp_document_symbol_timeout: float = 30.0  # seconds
    prefer_lsp_over_ast: bool = True
    fallback_to_ast: bool = True

    # Performance configuration
    max_workers: int = 4
    max_symbols_per_file: int = 10000
    max_nesting_depth: int = 10
    parallel_extraction: bool = False
    batch_size: int = 10

    # Extractor configuration
    extractors: dict[str, str] = field(default_factory=lambda: {"python": "PythonSymbolExtractor"})
    file_extensions: dict[str, str] = field(default_factory=lambda: {".py": "python", ".pyw": "python"})

    def __post_init__(self):
        """Set defaults and validate configuration."""
        if self.database_path is None:
            self.database_path = str(Path.home() / ".github-agent" / "document_symbols.db")
        
        # Validation
        if self.max_workers <= 0:
            raise ConfigurationError(f"max_workers must be positive: {self.max_workers}")
        if self.cache_ttl_seconds < 0:
            raise ConfigurationError(f"cache_ttl_seconds cannot be negative: {self.cache_ttl_seconds}")
        if self.database_path == "":
            raise ConfigurationError("database_path cannot be empty")

    @classmethod
    def from_dict(cls, config_dict: dict[str, Any]) -> "DocumentSymbolConfig":
        """Create configuration from dictionary.

        Args:
            config_dict: Configuration dictionary

        Returns:
            DocumentSymbolConfig instance
        """
        kwargs = {}
        for key, value in config_dict.items():
            if key == "cache_dir" and value is not None:
                kwargs[key] = Path(value)
            elif hasattr(cls, key):
                kwargs[key] = value
        return cls(**kwargs)

    def to_dict(self) -> dict[str, Any]:
        """Convert configuration to dictionary.

        Returns:
            Configuration dictionary
        """
        result = {}
        for key, value in self.__dict__.items():
            if isinstance(value, Path):
                result[key] = str(value)
            else:
                result[key] = value
        return result

    def validate(self) -> None:
        """Validate configuration parameters.

        Raises:
            ConfigurationError: If configuration is invalid
        """
        errors = []
        if self.cache_ttl_seconds <= 0:
            errors.append("cache_ttl_seconds must be positive")
        if self.max_cache_size_mb <= 0:
            errors.append("max_cache_size_mb must be positive")
        if self.lsp_document_symbol_timeout <= 0:
            errors.append("lsp_document_symbol_timeout must be positive")
        if self.max_symbols_per_file <= 0:
            errors.append("max_symbols_per_file must be positive")
        if self.max_nesting_depth <= 0:
            errors.append("max_nesting_depth must be positive")
        if self.batch_size <= 0:
            errors.append("batch_size must be positive")
        if self.backup_retention_days < 0:
            errors.append("backup_retention_days must be non-negative")
        if self.max_workers <= 0:
            errors.append("max_workers must be positive")
        
        if errors:
            raise ConfigurationError(f"Invalid configuration: {', '.join(errors)}")

    def merge_with(self, other: "DocumentSymbolConfig") -> "DocumentSymbolConfig":
        """Merge this configuration with another.

        Args:
            other: Configuration to merge with

        Returns:
            New merged configuration
        """
        merged_dict = self.to_dict()
        other_dict = other.to_dict()
        merged_dict.update(other_dict)
        return DocumentSymbolConfig.from_dict(merged_dict)
    
    def merge(self, other: "DocumentSymbolConfig") -> None:
        """Merge another configuration into this one in-place.
        
        Only merges fields that were explicitly set in the other config
        (i.e., different from defaults).

        Args:
            other: Configuration to merge into this one
            
        Raises:
            ConfigurationError: If merged configuration would be invalid
        """
        # Get default values for comparison
        default_config = DocumentSymbolConfig()
        default_dict = default_config.to_dict()
        
        # Only merge values that differ from defaults in other
        other_dict = other.to_dict()
        for key, value in other_dict.items():
            if key in default_dict and value != default_dict[key]:
                if hasattr(self, key):
                    setattr(self, key, value)
        
        # Validate the merged configuration
        self.validate()

    def save_to_file(self, file_path: str) -> None:
        """Save configuration to JSON file.

        Args:
            file_path: Path to save configuration to
        """
        with open(file_path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load_from_file(cls, file_path: str) -> "DocumentSymbolConfig":
        """Load configuration from JSON file.

        Args:
            file_path: Path to load configuration from

        Returns:
            Loaded configuration
        
        Raises:
            ConfigurationError: If file cannot be read or parsed
        """
        try:
            with open(file_path) as f:
                return cls.from_dict(json.load(f))
        except (FileNotFoundError, OSError) as e:
            raise ConfigurationError(f"Failed to load config from {file_path}: {e}") from e
        except json.JSONDecodeError as e:
            raise ConfigurationError(f"Invalid JSON in {file_path}: {e}") from e

    @classmethod
    def get_default_config_path(cls) -> Path:
        """Get default configuration file path.

        Returns:
            Path to default config file
        """
        return Path.home() / ".github-agent" / "document_symbols.json"
    
    def get_extractor_for_file(self, file_path: str) -> str | None:
        """Get the extractor name for a given file.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Extractor name or None if no extractor for file type
        """
        from pathlib import Path
        
        file_ext = Path(file_path).suffix
        if file_ext in self.file_extensions:
            extractor_type = self.file_extensions[file_ext]
            return self.extractors.get(extractor_type)
        return None
    
    def is_supported_file(self, file_path: str) -> bool:
        """Check if a file is supported for symbol extraction.
        
        Args:
            file_path: Path to the file
            
        Returns:
            True if file is supported, False otherwise
        """
        return self.get_extractor_for_file(file_path) is not None
    
    def ensure_database_directory(self) -> None:
        """Ensure the database directory exists.
        
        Creates the parent directory of the database path if it doesn't exist.
        """
        from pathlib import Path
        
        db_path = Path(self.database_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)


@dataclass
class RepositorySymbolConfig:
    """Repository-specific symbol configuration."""

    repository_id: str
    enabled: bool = True
    custom_cache_ttl: float | None = None
    excluded_patterns: list[str] = field(default_factory=list)
    included_patterns: list[str] = field(default_factory=list)

    def should_process_file(self, file_path: str) -> bool:
        """Check if file should be processed for symbols.

        Args:
            file_path: Path to file

        Returns:
            True if file should be processed
        """
        import fnmatch

        if not self.enabled:
            return False

        file_path_str = str(file_path)

        # Check excluded patterns
        for pattern in self.excluded_patterns:
            if fnmatch.fnmatch(file_path_str, pattern):
                return False

        # If included patterns are specified, file must match one
        if self.included_patterns:
            for pattern in self.included_patterns:
                if fnmatch.fnmatch(file_path_str, pattern):
                    return True
            return False

        # No included patterns specified, process by default
        return True


class DocumentSymbolConfigManager:
    """Manages document symbol configuration."""

    def __init__(self, config_file: Path | None = None):
        """Initialize configuration manager.

        Args:
            config_file: Path to configuration file, uses default if None
        """
        self.config_file = config_file or DocumentSymbolConfig.get_default_config_path()
        self._config: DocumentSymbolConfig | None = None
        self._repo_configs: dict[str, RepositorySymbolConfig] = {}

    def load_config(self) -> DocumentSymbolConfig:
        """Load configuration from file.

        Returns:
            Loaded configuration
        """
        if self.config_file.exists():
            try:
                with open(self.config_file) as f:
                    data = json.load(f)
                    self._config = DocumentSymbolConfig.from_dict(
                        data.get("config", {})
                    )
                    self._repo_configs = {
                        k: RepositorySymbolConfig(**v)
                        for k, v in data.get("repositories", {}).items()
                    }
            except (json.JSONDecodeError, OSError) as e:
                raise ConfigurationError(
                    f"Failed to load config from {self.config_file}: {e}"
                ) from e
        else:
            self._config = DocumentSymbolConfig()

        return self._config

    def save_config(self, config: DocumentSymbolConfig) -> None:
        """Save configuration to file.

        Args:
            config: Configuration to save
        """
        self._config = config
        self.config_file.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "config": config.to_dict(),
            "repositories": {
                k: {
                    "repository_id": v.repository_id,
                    "enabled": v.enabled,
                    "custom_cache_ttl": v.custom_cache_ttl,
                    "excluded_patterns": v.excluded_patterns,
                    "included_patterns": v.included_patterns,
                }
                for k, v in self._repo_configs.items()
            },
        }

        try:
            with open(self.config_file, "w") as f:
                json.dump(data, f, indent=2)
        except OSError as e:
            raise ConfigurationError(
                f"Failed to save config to {self.config_file}: {e}"
            ) from e

    def get_repository_config(self, repository_id: str) -> RepositorySymbolConfig:
        """Get repository-specific configuration.

        Args:
            repository_id: Repository identifier

        Returns:
            Repository configuration
        """
        if repository_id not in self._repo_configs:
            self._repo_configs[repository_id] = RepositorySymbolConfig(
                repository_id=repository_id
            )
        return self._repo_configs[repository_id]

    def set_repository_config(self, config: RepositorySymbolConfig) -> None:
        """Set repository-specific configuration.

        Args:
            config: Repository configuration
        """
        self._repo_configs[config.repository_id] = config
        if self._config:
            self.save_config(self._config)

    def reload_config(self) -> None:
        """Reload configuration from file."""
        self._config = None
        self._repo_configs = {}
        self.load_config()

    def get_effective_config(
        self, repository_id: str | None = None
    ) -> DocumentSymbolConfig:
        """Get effective configuration with repository overrides.

        Args:
            repository_id: Optional repository identifier

        Returns:
            Effective configuration
        """
        if self._config is None:
            self.load_config()

        base_config = self._config or DocumentSymbolConfig()

        if repository_id and repository_id in self._repo_configs:
            repo_config = self._repo_configs[repository_id]
            if repo_config.custom_cache_ttl is not None:
                # Create a copy with the overridden cache TTL
                config_dict = base_config.to_dict()
                config_dict["cache_ttl"] = repo_config.custom_cache_ttl
                return DocumentSymbolConfig.from_dict(config_dict)

        return base_config
