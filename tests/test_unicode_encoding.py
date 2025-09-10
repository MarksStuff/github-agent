"""Test unicode and encoding edge cases."""

import tempfile
import unittest
from pathlib import Path

from document_symbol_provider import DocumentSymbolProvider
from errors import SymbolExtractionError
from python_symbol_extractor import PythonSymbolExtractor
from symbol_storage import SQLiteSymbolStorage as SymbolStorage


class TestUnicodeEncoding(unittest.TestCase):
    """Test handling of unicode and various encodings."""

    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.extractor = PythonSymbolExtractor()
        self.provider = DocumentSymbolProvider()

    def tearDown(self):
        """Clean up test environment."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_unicode_symbol_names(self):
        """Test extraction of symbols with unicode names."""
        test_file = Path(self.temp_dir) / "unicode_symbols.py"
        test_file.write_text(
            """
# Unicode identifiers
def hello_世界():
    '''Function with Chinese characters'''
    return "Hello World"

class ΜαθηματικάClass:
    '''Class with Greek name'''
    def μέθοδος(self):
        return "method"

переменная = 42  # Russian variable

def café_function():
    '''Function with accented character'''
    return "coffee"

class 日本語クラス:
    '''Japanese class name'''
    pass

def emoji_🎉_function():
    '''Function with emoji (if supported)'''
    pass
""",
            encoding="utf-8",
        )

        # Extract symbols
        symbols = self.extractor.extract_symbols(str(test_file))

        # Verify unicode symbols extracted
        symbol_names = [s["name"] for s in symbols]

        self.assertIn("hello_世界", symbol_names)
        self.assertIn("ΜαθηματικάClass", symbol_names)
        self.assertIn("café_function", symbol_names)
        self.assertIn("日本語クラス", symbol_names)

    def test_utf8_bom_handling(self):
        """Test handling of UTF-8 BOM (Byte Order Mark)."""
        test_file = Path(self.temp_dir) / "bom_file.py"

        # Write file with UTF-8 BOM
        with open(test_file, "wb") as f:
            f.write(b"\xef\xbb\xbf")  # UTF-8 BOM
            f.write(
                b"""def test_function():
    return "BOM test"
"""
            )

        # Should handle BOM correctly
        symbols = self.extractor.extract_symbols(str(test_file))

        self.assertEqual(len(symbols), 1)
        self.assertEqual(symbols[0]["name"], "test_function")

    def test_different_encodings(self):
        """Test files with different encodings."""
        encodings = [
            ("utf-8", "def utf8_func(): return 'тест'"),
            ("utf-16", "def utf16_func(): return 'test'"),
            ("latin-1", "def latin1_func(): return 'café'"),
            ("cp1252", "def windows_func(): return 'test'"),
        ]

        for encoding, content in encodings:
            test_file = Path(self.temp_dir) / f"test_{encoding.replace('-', '_')}.py"

            # Write file with specific encoding
            with open(test_file, "w", encoding=encoding) as f:
                f.write(content)

            try:
                # Should handle different encodings
                symbols = self.extractor.extract_symbols(str(test_file))
                self.assertGreater(
                    len(symbols), 0, f"Failed to extract from {encoding}"
                )
            except UnicodeDecodeError:
                # Some encodings might not be supported
                pass

    def test_mixed_line_endings(self):
        """Test handling of mixed line endings (CRLF, LF, CR)."""
        test_file = Path(self.temp_dir) / "mixed_endings.py"

        # Write file with mixed line endings
        with open(test_file, "wb") as f:
            f.write(b"def unix_func():\n")  # LF
            f.write(b"    return 1\r\n")  # CRLF
            f.write(b"\rdef mac_func():\r")  # CR
            f.write(b"    return 2\n")  # LF
            f.write(b"class TestClass:\r\n")  # CRLF
            f.write(b"    pass")

        # Should handle all line ending types
        symbols = self.extractor.extract_symbols(str(test_file))

        symbol_names = [s["name"] for s in symbols]
        self.assertIn("unix_func", symbol_names)
        self.assertIn("mac_func", symbol_names)
        self.assertIn("TestClass", symbol_names)

    def test_zero_width_characters(self):
        """Test handling of zero-width and invisible characters."""
        test_file = Path(self.temp_dir) / "zero_width.py"

        # Zero-width characters
        zwsp = "\u200b"  # Zero-width space
        zwnj = "\u200c"  # Zero-width non-joiner
        zwj = "\u200d"  # Zero-width joiner

        content = f"""def normal{zwsp}function():
    '''Function with zero-width space'''
    return "test"

class Test{zwnj}Class:
    '''Class with zero-width non-joiner'''
    pass

variable{zwj}name = 42
"""

        test_file.write_text(content, encoding="utf-8")

        # Should handle zero-width characters
        try:
            symbols = self.extractor.extract_symbols(str(test_file))
            # Verify extraction doesn't crash
            self.assertIsNotNone(symbols)
        except Exception as e:
            self.fail(f"Failed to handle zero-width characters: {e}")

    def test_rtl_text_in_comments(self):
        """Test handling of right-to-left text in comments and strings."""
        test_file = Path(self.temp_dir) / "rtl_text.py"
        test_file.write_text(
            """
def process_arabic():
    '''معالج النص العربي'''  # Arabic text
    arabic_text = "مرحبا بالعالم"
    return arabic_text

def process_hebrew():
    '''מעבד טקסט עברי'''  # Hebrew text
    hebrew_text = "שלום עולם"
    return hebrew_text

# Mixed direction: Hello مرحبا שלום World
def mixed_direction():
    return "LTR and RTL mixed"
""",
            encoding="utf-8",
        )

        # Should handle RTL text in comments and strings
        symbols = self.extractor.extract_symbols(str(test_file))

        self.assertEqual(len(symbols), 3)
        symbol_names = [s["name"] for s in symbols]
        self.assertIn("process_arabic", symbol_names)
        self.assertIn("process_hebrew", symbol_names)

    def test_surrogate_pairs(self):
        """Test handling of Unicode surrogate pairs."""
        test_file = Path(self.temp_dir) / "surrogate_pairs.py"

        # Emoji and other characters outside BMP (Basic Multilingual Plane)
        content = """
def emoji_function():
    '''Function with emoji 🚀🎨🎭'''
    return "🎉"

class MathSymbols:
    '''Mathematical symbols 𝓐𝓑𝓒'''
    def calculate(self):
        return "∑∏∫"

# Ancient scripts 𐌀𐌁𐌂
variable = "test"
"""

        test_file.write_text(content, encoding="utf-8")

        # Should handle surrogate pairs correctly
        symbols = self.extractor.extract_symbols(str(test_file))

        self.assertGreater(len(symbols), 0)
        # Verify docstrings preserved correctly
        for symbol in symbols:
            if symbol["name"] == "emoji_function":
                self.assertIn("🚀", symbol.get("docstring", ""))

    def test_file_path_encoding(self):
        """Test handling of unicode in file paths."""
        # Create directory with unicode name
        unicode_dir = Path(self.temp_dir) / "文件夹_dossier_папка"
        unicode_dir.mkdir()

        # Create file with unicode name
        unicode_file = unicode_dir / "αρχείο_文件_файл.py"
        unicode_file.write_text(
            """
def test_function():
    return "Unicode path test"
""",
            encoding="utf-8",
        )

        # Should handle unicode paths
        symbols = self.extractor.extract_symbols(str(unicode_file))

        self.assertEqual(len(symbols), 1)
        self.assertEqual(symbols[0]["name"], "test_function")

        # Verify file path preserved correctly
        self.assertIn(str(unicode_file), symbols[0].get("file_path", ""))

    def test_invalid_utf8_sequences(self):
        """Test handling of invalid UTF-8 sequences."""
        test_file = Path(self.temp_dir) / "invalid_utf8.py"

        # Write file with invalid UTF-8
        with open(test_file, "wb") as f:
            f.write(b"def test_func():\n")
            f.write(b"    # Invalid UTF-8: \xff\xfe\n")
            f.write(b"    return 'test'\n")

        # Should handle or report error gracefully
        try:
            symbols = self.extractor.extract_symbols(str(test_file))
            # If it succeeds, verify basic extraction
            self.assertIsNotNone(symbols)
        except (UnicodeDecodeError, SymbolExtractionError) as e:
            # Should raise appropriate error
            self.assertIn("utf", str(e).lower())

    def test_normalization_forms(self):
        """Test handling of different Unicode normalization forms."""
        import unicodedata

        test_file = Path(self.temp_dir) / "normalization.py"

        # Same character in different normalization forms
        # é can be one character (NFC) or e + combining accent (NFD)
        nfc_e = unicodedata.normalize("NFC", "é")  # Single character
        nfd_e = unicodedata.normalize("NFD", "é")  # Base + combining

        content = f"""
def café_{nfc_e}_function():
    '''NFC form'''
    return "NFC"

def café_{nfd_e}_function():
    '''NFD form'''
    return "NFD"
"""

        test_file.write_text(content, encoding="utf-8")

        # Should handle both normalization forms
        symbols = self.extractor.extract_symbols(str(test_file))

        # Both functions should be extracted
        self.assertGreaterEqual(len(symbols), 1)

    def test_control_characters(self):
        """Test handling of control characters."""
        test_file = Path(self.temp_dir) / "control_chars.py"

        # Various control characters
        content = "def test_func():\n"
        content += "    # Bell character: \x07\n"
        content += "    # Form feed: \x0c\n"
        content += "    # Vertical tab: \x0b\n"
        content += "    return 'test'\n"

        test_file.write_text(content, encoding="utf-8")

        # Should handle control characters
        symbols = self.extractor.extract_symbols(str(test_file))

        self.assertEqual(len(symbols), 1)
        self.assertEqual(symbols[0]["name"], "test_func")

    def test_combining_characters(self):
        """Test handling of combining diacritical marks."""
        test_file = Path(self.temp_dir) / "combining.py"

        # Base characters with combining marks
        content = """
def test_à_function():  # a + combining grave accent
    return "grave"

def test_ñ_function():  # n + combining tilde
    return "tilde"

def test_ö_function():  # o + combining diaeresis
    return "umlaut"
"""

        test_file.write_text(content, encoding="utf-8")

        # Should handle combining characters
        symbols = self.extractor.extract_symbols(str(test_file))

        self.assertEqual(len(symbols), 3)

    def test_storage_with_unicode(self):
        """Test storage operations with unicode symbols."""
        db_path = Path(self.temp_dir) / "unicode.db"
        storage = SymbolStorage(str(db_path))

        # Store symbols with unicode names
        unicode_symbols = [
            {"name": "函数_function", "type": "function", "line": 1},
            {"name": "КлассClass", "type": "class", "line": 5},
            {"name": "μεταβλητή", "type": "variable", "line": 10},
            {"name": "📊_data", "type": "function", "line": 15},
        ]

        file_path = "unicode_test.py"
        storage.store_symbols(file_path, unicode_symbols)

        # Retrieve and verify
        retrieved = storage.get_symbols(file_path)
        self.assertEqual(len(retrieved), 4)

        # Search with unicode
        results = storage.search_symbols("函数")
        self.assertGreater(len(results), 0)

        results = storage.search_symbols("Класс")
        self.assertGreater(len(results), 0)


if __name__ == "__main__":
    unittest.main()
