"""Mock symbol extractor for testing."""

from python_symbol_extractor import AbstractSymbolExtractor
from symbol_storage import Symbol


class MockSymbolExtractor(AbstractSymbolExtractor):
    """Mock symbol extractor for testing."""

    def __init__(self):
        """Initialize empty mock extractor."""
        self.symbols: list[Symbol] = []

    def extract_from_file(self, file_path: str, repository_id: str) -> list[Symbol]:
        """Return predefined symbols."""
        return self.symbols.copy()

    def extract_from_source(
        self, source: str, file_path: str, repository_id: str
    ) -> list[Symbol]:
        """Return predefined symbols."""
        return self.symbols.copy()
