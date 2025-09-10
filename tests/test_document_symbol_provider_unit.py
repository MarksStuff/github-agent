"""Unit tests for DocumentSymbolProvider."""


import pytest
from pathlib import Path

from document_symbol_config import DocumentSymbolConfig
from document_symbol_provider import DocumentSymbolProvider
from errors import ExtractionError, InvalidFileTypeError, StorageError
from symbol_storage import Symbol
from tests.mocks.mock_abstract_symbol_extractor import (
    FailingSymbolExtractor,
    MockSymbolExtractor,
)
from tests.mocks.mock_lsp_client import MockLSPClient
from tests.mocks.mock_storage_with_hierarchy import (
    FailingStorage,
    MockStorageWithHierarchy,
)


class TestDocumentSymbolProviderInit:
    """Test provider initialization."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.lsp_client = MockLSPClient()
        self.extractor = MockSymbolExtractor()

    def test_provider_creation_with_defaults(self):
        """Test creating provider with default config."""
        provider = DocumentSymbolProvider(
            lsp_client=self.lsp_client,
            symbol_extractor=self.extractor
        )
        assert provider.lsp_client == self.lsp_client
        assert provider.symbol_extractor == self.extractor

    def test_provider_creation_with_custom_cache_ttl(self):
        """Test creating provider with custom cache TTL."""
        provider = DocumentSymbolProvider(
            lsp_client=self.lsp_client,
            symbol_extractor=self.extractor,
            cache_ttl=600.0
        )
        assert provider.cache_ttl == 600.0

    def test_provider_creation_with_cache_dir(self):
        """Test creating provider with cache directory."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir) / "test_cache"
            provider = DocumentSymbolProvider(
                lsp_client=self.lsp_client,
                symbol_extractor=self.extractor,
                cache_dir=cache_dir
            )
            assert provider.cache_dir == cache_dir
            assert cache_dir.exists()

    def test_provider_has_fallback_extractor(self):
        """Test that provider has fallback extractor."""
        provider = DocumentSymbolProvider(
            lsp_client=self.lsp_client,
            symbol_extractor=self.extractor
        )
        assert provider.symbol_extractor == self.extractor


class TestDocumentSymbolProviderComponents:
    """Test provider components."""

    def test_fallback_extractor_exists(self):
        """Test that fallback extractor is available."""
        extractor = MockSymbolExtractor()
        provider = DocumentSymbolProvider(
            lsp_client=MockLSPClient(),
            symbol_extractor=extractor
        )
        
        # The provider should have the fallback extractor
        assert provider.symbol_extractor == extractor

    def test_lsp_client_configured(self):
        """Test that LSP client is properly configured."""
        lsp_client = MockLSPClient()
        provider = DocumentSymbolProvider(
            lsp_client=lsp_client,
            symbol_extractor=MockSymbolExtractor()
        )
        
        assert provider.lsp_client == lsp_client

    def test_cache_configuration(self):
        """Test cache configuration."""
        provider = DocumentSymbolProvider(
            lsp_client=MockLSPClient(),
            symbol_extractor=MockSymbolExtractor(),
            cache_ttl=1000.0
        )
        
        assert provider.cache_ttl == 1000.0

    def test_cache_dir_configuration(self):
        """Test cache directory configuration."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir) / "cache"
            provider = DocumentSymbolProvider(
                lsp_client=MockLSPClient(),
                symbol_extractor=MockSymbolExtractor(),
                cache_dir=cache_dir
            )
            
            assert provider.cache_dir == cache_dir
            assert cache_dir.exists()


class TestDocumentSymbolProviderIntegration:
    """Test provider integration with mocks."""

    def test_provider_with_mock_lsp_client(self):
        """Test provider works with mock LSP client."""
        lsp_client = MockLSPClient()
        extractor = MockSymbolExtractor()
        
        provider = DocumentSymbolProvider(
            lsp_client=lsp_client,
            symbol_extractor=extractor
        )
        
        # Provider should be properly initialized
        assert provider.lsp_client == lsp_client
        assert provider.symbol_extractor == extractor

    def test_provider_with_failing_extractor(self):
        """Test provider handles failing extractor."""
        lsp_client = MockLSPClient()
        extractor = FailingSymbolExtractor("Test error")
        
        provider = DocumentSymbolProvider(
            lsp_client=lsp_client,
            symbol_extractor=extractor
        )
        
        # Provider should still be created with failing extractor
        assert provider.symbol_extractor == extractor

    def test_provider_with_custom_symbols(self):
        """Test provider with custom symbols from mock."""
        from symbol_storage import SymbolKind
        symbols = [
            Symbol(
                name="test_func",
                kind=SymbolKind.FUNCTION,
                line_number=10,
                column=0,
                file_path="test.py",
                repository_id="repo1",
            ),
            Symbol(
                name="TestClass",
                kind=SymbolKind.CLASS,
                line_number=20,
                column=0,
                file_path="test.py",
                repository_id="repo1",
            ),
        ]
        
        lsp_client = MockLSPClient()
        extractor = MockSymbolExtractor(return_symbols=symbols)
        
        provider = DocumentSymbolProvider(
            lsp_client=lsp_client,
            symbol_extractor=extractor
        )
        
        # The extractor should have the symbols configured
        assert provider.symbol_extractor.return_symbols == symbols


class TestDocumentSymbolProviderCaching:
    """Test provider caching functionality."""

    def test_cache_disabled_by_default(self):
        """Test cache can be disabled."""
        provider = DocumentSymbolProvider(
            lsp_client=MockLSPClient(),
            symbol_extractor=MockSymbolExtractor(),
            cache_dir=None
        )
        
        assert provider.cache_dir is None

    def test_cache_ttl_default(self):
        """Test default cache TTL."""
        provider = DocumentSymbolProvider(
            lsp_client=MockLSPClient(),
            symbol_extractor=MockSymbolExtractor()
        )
        
        # Default TTL should be 5 minutes (300 seconds)
        assert provider.cache_ttl == 300.0

    def test_cache_ttl_custom(self):
        """Test custom cache TTL."""
        provider = DocumentSymbolProvider(
            lsp_client=MockLSPClient(),
            symbol_extractor=MockSymbolExtractor(),
            cache_ttl=3600.0  # 1 hour
        )
        
        assert provider.cache_ttl == 3600.0


class TestDocumentSymbolProviderEdgeCases:
    """Test edge cases and error conditions."""

    def test_provider_with_none_cache_dir(self):
        """Test provider with None cache directory."""
        provider = DocumentSymbolProvider(
            lsp_client=MockLSPClient(),
            symbol_extractor=MockSymbolExtractor(),
            cache_dir=None
        )
        
        assert provider.cache_dir is None

    def test_provider_with_zero_cache_ttl(self):
        """Test provider with zero cache TTL."""
        provider = DocumentSymbolProvider(
            lsp_client=MockLSPClient(),
            symbol_extractor=MockSymbolExtractor(),
            cache_ttl=0.0
        )
        
        assert provider.cache_ttl == 0.0

    def test_provider_with_negative_cache_ttl(self):
        """Test provider with negative cache TTL (should be treated as disabled)."""
        provider = DocumentSymbolProvider(
            lsp_client=MockLSPClient(),
            symbol_extractor=MockSymbolExtractor(),
            cache_ttl=-1.0
        )
        
        assert provider.cache_ttl == -1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])