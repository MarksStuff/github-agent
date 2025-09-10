"""Mock implementations for AbstractSymbolExtractor."""

import copy

from abstract_symbol_extractor import AbstractSymbolExtractor
from symbol_storage import Symbol


class MockSymbolExtractor(AbstractSymbolExtractor):
    """Mock symbol extractor for testing."""

    def __init__(self, return_symbols: list[Symbol] | None = None):
        """Initialize with configurable symbols."""
        self.return_symbols = return_symbols or []
        self.extract_called = False
        self.extract_hierarchy_called = False
        self.last_file_path = None
        self.last_repository_id = None
        self.last_source = None

    def extract_symbols(self, file_path: str) -> list[Symbol]:
        """Return predefined symbols and track calls."""
        self.extract_called = True
        self.last_file_path = file_path
        return copy.deepcopy(self.return_symbols)

    def extract_symbol_hierarchy(self, file_path: str) -> list[Symbol]:
        """Return hierarchy format of symbols."""
        self.extract_hierarchy_called = True
        self.last_file_path = file_path

        # Return symbols with hierarchy information
        return copy.deepcopy(self.return_symbols)

    def supports_file_type(self, file_path: str) -> bool:
        """Mock always supports all file types."""
        return True

    def get_supported_extensions(self) -> list[str]:
        """Mock supports all extensions."""
        return [".py", ".pyi"]


class FailingSymbolExtractor(AbstractSymbolExtractor):
    """Mock that always fails for error testing."""

    def __init__(self, error_message: str = "Extraction failed"):
        self.error_message = error_message

    def extract_symbols(self, file_path: str) -> list[Symbol]:
        """Always raise an exception."""
        raise Exception(self.error_message)

    def extract_symbol_hierarchy(self, file_path: str) -> list[Symbol]:
        """Always raise an exception."""
        raise Exception(self.error_message)

    def supports_file_type(self, file_path: str) -> bool:
        """Always fails."""
        raise Exception(self.error_message)

    def get_supported_extensions(self) -> list[str]:
        """Always fails."""
        raise Exception(self.error_message)


class SlowSymbolExtractor(AbstractSymbolExtractor):
    """Mock that simulates slow extraction."""

    def __init__(self, delay_seconds: float = 1.0, symbols: list[Symbol] | None = None):
        self.delay_seconds = delay_seconds
        self.symbols = symbols or []

    def extract_symbols(self, file_path: str) -> list[Symbol]:
        """Return symbols after a delay."""
        import time

        time.sleep(self.delay_seconds)
        return copy.deepcopy(self.symbols)

    def extract_symbol_hierarchy(self, file_path: str) -> list[Symbol]:
        """Return hierarchy after a delay."""
        import time

        time.sleep(self.delay_seconds)
        return copy.deepcopy(self.symbols)

    def supports_file_type(self, file_path: str) -> bool:
        """Mock supports all file types after delay."""
        import time

        time.sleep(self.delay_seconds)
        return True

    def get_supported_extensions(self) -> list[str]:
        """Mock supports all extensions after delay."""
        import time

        time.sleep(self.delay_seconds)
        return [".py", ".pyi"]
