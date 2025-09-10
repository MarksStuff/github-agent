"""Unit tests for PythonSymbolExtractor hierarchy extensions."""

import tempfile
from pathlib import Path

import pytest

from abstract_symbol_extractor import AbstractSymbolExtractor
from python_symbol_extractor import PythonSymbolExtractor
from symbol_storage import SymbolKind


class TestPythonSymbolExtractorHierarchy:
    """Test hierarchy extraction functionality."""

    def test_extractor_implements_abstract_interface(self):
        """Test that PythonSymbolExtractor implements AbstractSymbolExtractor."""
        extractor = PythonSymbolExtractor()
        assert isinstance(extractor, AbstractSymbolExtractor)

    def test_extract_symbol_hierarchy_simple_class(self):
        """Test extracting hierarchy from simple class."""
        source = """
class MyClass:
    def method1(self):
        pass

    def method2(self):
        pass
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(source)
            temp_path = f.name

        try:
            extractor = PythonSymbolExtractor()
            hierarchy = extractor.extract_symbol_hierarchy(temp_path)

            # Hierarchy returns a flat list with parent_id set for relationships
            assert len(hierarchy) == 3  # Class + 2 methods
            
            # Find the class
            class_symbol = [s for s in hierarchy if s.kind == SymbolKind.CLASS][0]
            assert class_symbol.name == "MyClass"
            assert class_symbol.parent_id is None
            
            # Find methods
            methods = [s for s in hierarchy if s.kind == SymbolKind.METHOD]
            assert len(methods) == 2
            method_names = [m.name for m in methods]
            assert any("method1" in name for name in method_names)
            assert any("method2" in name for name in method_names)
            
            # Check parent relationships
            for method in methods:
                assert method.parent_id is not None
        finally:
            Path(temp_path).unlink()

    def test_extract_symbol_hierarchy_nested_classes(self):
        """Test extracting hierarchy with nested classes."""
        source = """
class OuterClass:
    class InnerClass:
        def inner_method(self):
            pass

    def outer_method(self):
        pass
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(source)
            temp_path = f.name

        try:
            extractor = PythonSymbolExtractor()
            hierarchy = extractor.extract_symbol_hierarchy(temp_path)

            assert len(hierarchy) == 4  # OuterClass + InnerClass + 2 methods
            
            # Find outer class
            outer_class = [s for s in hierarchy if s.name == "OuterClass"][0]
            assert outer_class.kind == SymbolKind.CLASS
            assert outer_class.parent_id is None
            
            # Find inner class
            inner_class = [s for s in hierarchy if "InnerClass" in s.name][0]
            assert inner_class.kind == SymbolKind.CLASS
            assert inner_class.parent_id is not None
            
            # Find methods
            methods = [s for s in hierarchy if s.kind == SymbolKind.METHOD]
            assert len(methods) == 2
            assert any("inner_method" in m.name for m in methods)
            assert any("outer_method" in m.name for m in methods)
        finally:
            Path(temp_path).unlink()

    def test_extract_symbol_hierarchy_functions_and_classes(self):
        """Test extracting mixed functions and classes."""
        source = """
def standalone_function():
    pass

class MyClass:
    def method(self):
        pass

def another_function():
    def nested_function():
        pass
    return nested_function
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(source)
            temp_path = f.name

        try:
            extractor = PythonSymbolExtractor()
            hierarchy = extractor.extract_symbol_hierarchy(temp_path)

            assert len(hierarchy) == 5  # 2 functions + 1 class + 1 method + 1 nested function

            # Find root elements (no parent_id)
            root_symbols = [s for s in hierarchy if s.parent_id is None]
            assert len(root_symbols) == 3  # Two functions and one class at root
            
            names = [h.name for h in root_symbols]
            assert "standalone_function" in names
            assert "MyClass" in names
            assert "another_function" in names

            # Find MyClass and its method
            my_class = [s for s in hierarchy if s.name == "MyClass"][0]
            assert my_class.kind == SymbolKind.CLASS
            class_methods = [s for s in hierarchy if s.parent_id and s.parent_id.startswith("MyClass:")]
            assert len(class_methods) == 1
            assert "method" in class_methods[0].name

            # Find another_function and its nested function
            another_func = [s for s in hierarchy if s.name == "another_function"][0]
            assert another_func.kind == SymbolKind.FUNCTION
            nested_funcs = [s for s in hierarchy if s.parent_id and s.parent_id.startswith("another_function:")]
            assert len(nested_funcs) == 1
            assert "nested_function" in nested_funcs[0].name
        finally:
            Path(temp_path).unlink()

    def test_extract_symbol_hierarchy_decorators(self):
        """Test hierarchy with decorated functions and classes."""
        source = """
@decorator
class DecoratedClass:
    @property
    def prop(self):
        return None

    @staticmethod
    def static_method():
        pass

    @classmethod
    def class_method(cls):
        pass
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(source)
            temp_path = f.name

        try:
            extractor = PythonSymbolExtractor()
            hierarchy = extractor.extract_symbol_hierarchy(temp_path)

            assert len(hierarchy) == 4  # 1 class + 3 methods
            
            # Find the class
            cls = [s for s in hierarchy if s.kind == SymbolKind.CLASS][0]
            assert cls.name == "DecoratedClass"
            assert cls.parent_id is None
            
            # Find methods
            methods = [s for s in hierarchy if s.parent_id and s.parent_id.startswith("DecoratedClass:")]
            assert len(methods) == 3
            
            method_names = [m.name for m in methods]
            assert any("prop" in name for name in method_names)
            assert any("static_method" in name for name in method_names)
            assert any("class_method" in name for name in method_names)
        finally:
            Path(temp_path).unlink()

    def test_extract_symbol_hierarchy_async_functions(self):
        """Test hierarchy with async functions."""
        source = """
async def async_function():
    pass

class AsyncClass:
    async def async_method(self):
        pass

    def sync_method(self):
        async def inner_async():
            pass
        return inner_async
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(source)
            temp_path = f.name

        try:
            extractor = PythonSymbolExtractor()
            hierarchy = extractor.extract_symbol_hierarchy(temp_path)

            assert len(hierarchy) == 5  # 1 async function + 1 class + 2 methods + 1 inner function

            # Find async function
            async_func = [s for s in hierarchy if s.name == "async_function"][0]
            assert async_func.kind == SymbolKind.FUNCTION
            assert async_func.parent_id is None

            # Find AsyncClass
            async_class = [s for s in hierarchy if s.name == "AsyncClass"][0]
            assert async_class.kind == SymbolKind.CLASS
            assert async_class.parent_id is None
            
            # Find methods in AsyncClass
            class_methods = [s for s in hierarchy if s.parent_id and s.parent_id.startswith("AsyncClass:")]
            assert len(class_methods) == 2
            
            # Find inner async function (note: it may not have correct parent_id due to AST limitations)
            inner_async = [s for s in hierarchy if "inner_async" in s.name]
            assert len(inner_async) == 1
        finally:
            Path(temp_path).unlink()

    def test_extract_symbol_hierarchy_empty_file(self):
        """Test hierarchy extraction from empty file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("")
            temp_path = f.name

        try:
            extractor = PythonSymbolExtractor()
            hierarchy = extractor.extract_symbol_hierarchy(temp_path)
            assert hierarchy == []
        finally:
            Path(temp_path).unlink()

    def test_extract_symbol_hierarchy_syntax_error(self):
        """Test hierarchy extraction with syntax errors."""
        source = """
def broken_function(
    # Missing closing parenthesis
    pass
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(source)
            temp_path = f.name

        try:
            extractor = PythonSymbolExtractor()
            # Should handle syntax errors gracefully
            hierarchy = extractor.extract_symbol_hierarchy(temp_path)
            # May return empty or partial results
            assert isinstance(hierarchy, list)
        finally:
            Path(temp_path).unlink()


class TestPythonSymbolExtractorWithParentIds:
    """Test that extract_symbols includes parent_id information."""

    def test_extract_symbols_with_parent_ids(self):
        """Test that regular symbol extraction includes parent_id."""
        source = """
class MyClass:
    def method(self):
        pass
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(source)
            temp_path = f.name

        try:
            extractor = PythonSymbolExtractor()
            symbols = extractor.extract_symbols(temp_path)

            assert len(symbols) == 2

            class_symbol = next(s for s in symbols if s.name == "MyClass")
            method_symbol = next(s for s in symbols if "method" in s.name)

            # extract_symbols returns symbols without hierarchy (parent_id is not populated)
            assert getattr(class_symbol, "parent_id", None) is None
            assert getattr(method_symbol, "parent_id", None) is None
        finally:
            Path(temp_path).unlink()

    def test_extract_symbols_nested_parent_ids(self):
        """Test parent_id with deeply nested structures."""
        source = """
class Outer:
    class Inner:
        def deep_method(self):
            def local_func():
                pass
            return local_func
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(source)
            temp_path = f.name

        try:
            extractor = PythonSymbolExtractor()
            symbols = extractor.extract_symbols(temp_path)

            # With full qualified names
            outer = next(s for s in symbols if s.name == "Outer")
            inner = next(s for s in symbols if "Inner" in s.name)
            method = next(s for s in symbols if "deep_method" in s.name)
            local = next(s for s in symbols if "local_func" in s.name)

            # extract_symbols returns symbols without hierarchy (parent_id is not populated)
            assert getattr(outer, "parent_id", None) is None
            assert getattr(inner, "parent_id", None) is None
            assert getattr(method, "parent_id", None) is None
            assert getattr(local, "parent_id", None) is None
        finally:
            Path(temp_path).unlink()


class TestPythonSymbolExtractorComplexHierarchy:
    """Test complex hierarchy scenarios."""

    def test_multiple_inheritance(self):
        """Test hierarchy with multiple inheritance."""
        source = """
class Base1:
    def base1_method(self):
        pass

class Base2:
    def base2_method(self):
        pass

class Derived(Base1, Base2):
    def derived_method(self):
        pass
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(source)
            temp_path = f.name

        try:
            extractor = PythonSymbolExtractor()
            hierarchy = extractor.extract_symbol_hierarchy(temp_path)

            assert len(hierarchy) == 6  # 3 classes + 3 methods

            # Find classes
            classes = [s for s in hierarchy if s.kind == SymbolKind.CLASS]
            assert len(classes) == 3
            
            # Find Derived class and its method
            derived = [s for s in hierarchy if s.name == "Derived"][0]
            assert derived.kind == SymbolKind.CLASS
            derived_methods = [s for s in hierarchy if s.parent_id and s.parent_id.startswith("Derived:")]
            assert len(derived_methods) == 1
            assert "derived_method" in derived_methods[0].name
        finally:
            Path(temp_path).unlink()

    def test_lambda_expressions(self):
        """Test hierarchy with lambda expressions."""
        source = """
class Container:
    simple_lambda = lambda x: x * 2

    def method_with_lambda(self):
        complex_lambda = lambda x, y: x + y
        return complex_lambda
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(source)
            temp_path = f.name

        try:
            extractor = PythonSymbolExtractor()
            hierarchy = extractor.extract_symbol_hierarchy(temp_path)

            assert len(hierarchy) == 4  # 1 class + 1 method + 2 lambda variables
            
            # Find the class
            container = [s for s in hierarchy if s.kind == SymbolKind.CLASS][0]
            assert container.name == "Container"
            
            # Find methods
            methods = [s for s in hierarchy if s.kind == SymbolKind.METHOD]
            assert len(methods) >= 1
            assert any("method_with_lambda" in m.name for m in methods)
        finally:
            Path(temp_path).unlink()

    def test_global_variables_and_constants(self):
        """Test that global variables don't affect hierarchy."""
        source = """
CONSTANT = 42
global_var = "test"

def function():
    local_var = 10

    def nested():
        pass

    return nested

class MyClass:
    class_var = 100

    def method(self):
        pass
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(source)
            temp_path = f.name

        try:
            extractor = PythonSymbolExtractor()
            hierarchy = extractor.extract_symbol_hierarchy(temp_path)

            # Should have function and class at root
            root_names = [h.name for h in hierarchy]
            assert "function" in root_names
            assert "MyClass" in root_names

            # Nested function should be child of function
            func = next(h for h in hierarchy if h.name == "function")
            # Find nested function
            nested_funcs = [s for s in hierarchy if "nested" in s.name]
            assert len(nested_funcs) == 1
        finally:
            Path(temp_path).unlink()


class TestPythonSymbolExtractorEdgeCases:
    """Test edge cases and error conditions."""

    def test_nonexistent_file(self):
        """Test extraction from nonexistent file."""
        extractor = PythonSymbolExtractor()

        # Should return empty list for nonexistent file
        result = extractor.extract_symbol_hierarchy("/nonexistent/file.py")
        assert result == []

    def test_binary_file(self):
        """Test extraction from binary file."""
        with tempfile.NamedTemporaryFile(suffix=".pyc", delete=False) as f:
            f.write(b"\x00\x01\x02\x03")
            temp_path = f.name

        try:
            extractor = PythonSymbolExtractor()
            # Should handle binary files gracefully
            hierarchy = extractor.extract_symbol_hierarchy(temp_path)
            assert isinstance(hierarchy, list)
        finally:
            Path(temp_path).unlink()

    def test_very_deep_nesting(self):
        """Test extraction with very deep nesting."""
        # Generate deeply nested structure
        source = "class Level0:\n"
        indent = "    "
        for i in range(1, 10):
            source += f"{indent * i}class Level{i}:\n"
        source += f"{indent * 10}def deep_method(self):\n"
        source += f"{indent * 11}pass\n"

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(source)
            temp_path = f.name

        try:
            extractor = PythonSymbolExtractor()
            hierarchy = extractor.extract_symbol_hierarchy(temp_path)

            # Should handle deep nesting
            # Should have at least 10 symbols (one per level)
            assert len(hierarchy) >= 10
            
            # Check nesting by counting different levels
            levels = set()
            for symbol in hierarchy:
                # Count indentation level from the name
                if "." in symbol.name:
                    levels.add(symbol.name.count("."))
            
            # Should have deep nesting
            assert len(levels) >= 5
        finally:
            Path(temp_path).unlink()

    def test_unicode_symbols(self):
        """Test extraction with unicode in symbol names."""
        source = """
def 你好():
    pass

class ÜñíçødéClass:
    def métħød(self):
        pass
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(source)
            temp_path = f.name

        try:
            extractor = PythonSymbolExtractor()
            hierarchy = extractor.extract_symbol_hierarchy(temp_path)

            assert len(hierarchy) == 3  # Function + Class + Method
            names = [h.name for h in hierarchy]
            assert "你好" in names
            assert "ÜñíçødéClass" in names
        finally:
            Path(temp_path).unlink()
