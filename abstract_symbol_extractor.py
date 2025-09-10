"""Abstract base class for symbol extraction implementations."""

from abc import ABC, abstractmethod

from symbol_storage import Symbol


class AbstractSymbolExtractor(ABC):
    """Interface for symbol extraction from source code files."""

    @abstractmethod
    def extract_symbols(self, file_path: str) -> list[Symbol]:
        """Extract symbols from a source file.

        Args:
            file_path: Path to the source file

        Returns:
            List of extracted symbols without hierarchy
        """

    @abstractmethod
    def extract_symbol_hierarchy(self, file_path: str) -> list[Symbol]:
        """Extract symbols with parent-child relationships.

        Args:
            file_path: Path to the source file

        Returns:
            List of symbols with hierarchy information populated
        """

    @abstractmethod
    def supports_file_type(self, file_path: str) -> bool:
        """Check if this extractor supports the given file type.

        Args:
            file_path: Path to check

        Returns:
            True if file type is supported
        """

    @abstractmethod
    def get_supported_extensions(self) -> list[str]:
        """Get list of supported file extensions.

        Returns:
            List of extensions (e.g., ['.py', '.pyi'])
        """
