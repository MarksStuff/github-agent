"""Custom exception hierarchy for the github-agent system."""


class DocumentSymbolError(Exception):
    """Base exception for document symbol extraction errors."""

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class LSPConnectionError(DocumentSymbolError):
    """LSP server connection or communication failure."""


class SymbolExtractionError(DocumentSymbolError):
    """Failed to extract symbols from source code."""


class HierarchyValidationError(DocumentSymbolError):
    """Symbol hierarchy validation failed."""


class CacheCorruptionError(DocumentSymbolError):
    """Cache data is corrupted or invalid."""


class ConfigurationError(DocumentSymbolError):
    """Configuration loading or validation error."""


class DatabaseMigrationError(DocumentSymbolError):
    """Database schema migration failed."""


# Alias for compatibility with test expectations
ExtractionError = SymbolExtractionError
StorageError = DocumentSymbolError
InvalidFileTypeError = ConfigurationError
SchemaVersionError = DatabaseMigrationError
