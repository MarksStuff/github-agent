"""Unit tests for AbstractSymbolExtractor interface."""


import pytest

from abstract_symbol_extractor import AbstractSymbolExtractor
from symbol_storage import Symbol, SymbolKind
from tests.mocks.mock_abstract_symbol_extractor import (
    FailingSymbolExtractor,
    MockSymbolExtractor,
    SlowSymbolExtractor,
)


class TestAbstractSymbolExtractor:
    """Test the abstract base class."""

    def test_cannot_instantiate_abstract_class(self):
        """Test that abstract class cannot be instantiated."""
        with pytest.raises(TypeError):
            AbstractSymbolExtractor()

    def test_abstract_methods_defined(self):
        """Test that abstract methods are defined."""
        assert hasattr(AbstractSymbolExtractor, "extract_symbols")
        assert hasattr(AbstractSymbolExtractor, "extract_symbol_hierarchy")

    def test_subclass_must_implement_methods(self):
        """Test that subclass must implement all abstract methods."""

        class IncompleteExtractor(AbstractSymbolExtractor):
            def extract_symbols(self, file_path: str):
                return []

        # Should fail because extract_symbol_hierarchy not implemented
        with pytest.raises(TypeError):
            IncompleteExtractor()


class TestMockSymbolExtractor:
    """Test mock implementation functionality."""

    def test_mock_extractor_creation(self):
        """Test creating mock extractor."""
        extractor = MockSymbolExtractor()
        assert extractor.return_symbols == []
        assert not extractor.extract_called

    def test_mock_extractor_with_symbols(self):
        """Test mock with predefined symbols."""
        symbols = [
            Symbol(
                name="test_func",
                kind=SymbolKind.FUNCTION,
                line_number=10,
                column=0,
                file_path="test.py",
                repository_id="repo1",
            )
        ]
        extractor = MockSymbolExtractor(return_symbols=symbols)

        result = extractor.extract_symbols("test.py")
        assert len(result) == 1
        assert result[0].name == "test_func"
        assert extractor.extract_called
        assert extractor.last_file_path == "test.py"

    def test_mock_extractor_hierarchy(self):
        """Test hierarchy extraction."""
        symbols = [
            Symbol(
                name="MyClass",
                kind=SymbolKind.CLASS,
                line_number=1,
                column=0,
                file_path="test.py",
                repository_id="repo1",
            )
        ]
        # Add parent_id attribute
        symbols[0].parent_id = None

        extractor = MockSymbolExtractor(return_symbols=symbols)
        hierarchy = extractor.extract_symbol_hierarchy("test.py")

        assert len(hierarchy) == 1
        assert hierarchy[0].name == "MyClass"
        assert hierarchy[0].kind == SymbolKind.CLASS
        assert getattr(hierarchy[0], "parent_id", None) is None
        assert extractor.extract_hierarchy_called

    def test_mock_returns_copy_not_reference(self):
        """Test that mock returns copies, not references."""
        symbols = [
            Symbol(
                name="original",
                kind=SymbolKind.FUNCTION,
                line_number=1,
                column=0,
                file_path="test.py",
                repository_id="repo1",
            )
        ]
        extractor = MockSymbolExtractor(return_symbols=symbols)

        result1 = extractor.extract_symbols("test.py")
        result2 = extractor.extract_symbols("test.py")

        # Modify first result
        result1[0].name = "modified"

        # Second result should be unchanged
        assert result2[0].name == "original"
        assert symbols[0].name == "original"


class TestFailingSymbolExtractor:
    """Test error handling in extractors."""

    def test_failing_extractor_creation(self):
        """Test creating failing extractor."""
        extractor = FailingSymbolExtractor()
        assert extractor.error_message == "Extraction failed"

    def test_failing_extractor_custom_message(self):
        """Test failing with custom message."""
        extractor = FailingSymbolExtractor("Custom error")

        with pytest.raises(Exception) as exc_info:
            extractor.extract_symbols("test.py")

        assert str(exc_info.value) == "Custom error"

    def test_failing_hierarchy_extraction(self):
        """Test hierarchy extraction failure."""
        extractor = FailingSymbolExtractor("Hierarchy failed")

        with pytest.raises(Exception) as exc_info:
            extractor.extract_symbol_hierarchy("test.py")

        assert str(exc_info.value) == "Hierarchy failed"


class TestSlowSymbolExtractor:
    """Test performance-related scenarios."""

    def test_slow_extractor_creation(self):
        """Test creating slow extractor."""
        extractor = SlowSymbolExtractor(delay_seconds=0.01)
        assert extractor.delay_seconds == 0.01
        assert extractor.symbols == []

    def test_slow_extraction(self):
        """Test extraction with delay."""
        import time

        symbols = [
            Symbol(
                name="slow_func",
                kind=SymbolKind.FUNCTION,
                line_number=1,
                column=0,
                file_path="test.py",
                repository_id="repo1",
            )
        ]
        extractor = SlowSymbolExtractor(delay_seconds=0.01, symbols=symbols)

        start_time = time.time()
        result = extractor.extract_symbols("test.py")
        elapsed = time.time() - start_time

        assert elapsed >= 0.01
        assert len(result) == 1
        assert result[0].name == "slow_func"

    def test_slow_hierarchy_extraction(self):
        """Test hierarchy extraction with delay."""
        import time

        extractor = SlowSymbolExtractor(delay_seconds=0.01)

        start_time = time.time()
        result = extractor.extract_symbol_hierarchy("test.py")
        elapsed = time.time() - start_time

        assert elapsed >= 0.01
        assert result == []


class TestExtractorContract:
    """Test that implementations follow the contract."""

    def test_extractor_returns_list(self):
        """Test that extract_symbols returns a list."""
        extractor = MockSymbolExtractor()
        result = extractor.extract_symbols("test.py")
        assert isinstance(result, list)

    def test_extractor_handles_empty_file(self):
        """Test extraction from non-existent or empty file."""
        extractor = MockSymbolExtractor(return_symbols=[])
        result = extractor.extract_symbols("empty.py")
        assert result == []

    def test_hierarchy_returns_list(self):
        """Test that hierarchy extraction returns a list."""
        extractor = MockSymbolExtractor()
        result = extractor.extract_symbol_hierarchy("test.py")
        assert isinstance(result, list)

    def test_extractor_preserves_repository_id(self):
        """Test that repository ID is preserved."""
        symbols = [
            Symbol(
                name="func",
                kind=SymbolKind.FUNCTION,
                line_number=1,
                column=0,
                file_path="test.py",
                repository_id="custom_repo",
            )
        ]
        extractor = MockSymbolExtractor(return_symbols=symbols)

        result = extractor.extract_symbols("test.py")
        assert all(s.repository_id == "custom_repo" for s in result)
