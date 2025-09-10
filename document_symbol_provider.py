#!/usr/bin/env python3

"""
Document Symbol Provider - Orchestrates document symbol extraction from LSP or AST fallback.

This module provides hierarchical symbol extraction capabilities for documents,
coordinating between LSP servers and AST-based fallback extraction.
"""

import asyncio
import hashlib
import json
import logging
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from abstract_document_symbol_provider import AbstractDocumentSymbolProvider
from abstract_symbol_extractor import AbstractSymbolExtractor
from errors import (
    LSPConnectionError,
    SymbolExtractionError,
)
from lsp_symbol_mapping import LSP_SYMBOL_KIND_MAP
from simple_lsp_client import SimpleLSPClient
from symbol_storage import Symbol, SymbolKind

logger = logging.getLogger(__name__)


class DocumentSymbolProvider(AbstractDocumentSymbolProvider):
    """Orchestrates document symbol extraction from LSP or AST fallback."""

    def __init__(
        self,
        lsp_client: SimpleLSPClient | None = None,
        symbol_extractor: AbstractSymbolExtractor | None = None,
        cache_dir: Path | None = None,
        cache_ttl: float = 300.0,  # 5 minutes default
        config: Any | None = None,  # DocumentSymbolConfig
        storage: Any | None = None,  # SQLiteSymbolStorage
    ):
        """Initialize with various configuration options.

        Args:
            lsp_client: LSP client for symbol extraction
            symbol_extractor: AST-based fallback symbol extractor
            cache_dir: Optional directory for caching symbols
            cache_ttl: Cache time-to-live in seconds
            config: DocumentSymbolConfig instance
            storage: SQLiteSymbolStorage instance
        """
        # Handle different initialization patterns
        if config is not None:
            # Integration test pattern with config
            from document_symbol_config import DocumentSymbolConfig
            if isinstance(config, DocumentSymbolConfig):
                cache_dir = config.cache_dir if config.cache_enabled else None
                cache_ttl = config.cache_ttl_seconds
        
        self.lsp_client = lsp_client
        self.symbol_extractor = symbol_extractor
        self.cache_dir = cache_dir
        self.cache_ttl = cache_ttl
        self.storage = storage
        self.config = config
        self._cache: dict[str, DocumentSymbolCache] = {}
        self._extractors: dict[str, Any] = {}  # For register_extractor pattern

        if cache_dir:
            cache_dir.mkdir(parents=True, exist_ok=True)
    
    def register_extractor(self, language: str, extractor: Any) -> None:
        """Register a symbol extractor for a language.
        
        Args:
            language: Language identifier (e.g., "python")
            extractor: Extractor instance
        """
        self._extractors[language] = extractor
        # Set as default symbol extractor if none set
        if self.symbol_extractor is None:
            self.symbol_extractor = extractor
    
    async def batch_extract_symbols(
        self, 
        files: list[str], 
        repository_id: str | None = None,
        progress_callback: Any | None = None
    ) -> dict[str, list[Symbol]]:
        """Extract symbols from multiple files.
        
        Args:
            files: List of file paths
            repository_id: Optional repository identifier
            progress_callback: Optional callback for progress updates
            
        Returns:
            Dictionary mapping file paths to symbol lists
        """
        results = {}
        total = len(files)
        
        for i, file_path in enumerate(files):
            try:
                symbols = await self.get_document_symbols(file_path, repository_id)
                results[file_path] = symbols
                
                if progress_callback:
                    progress_callback(file_path, (i + 1) / total)
            except Exception as e:
                logger.warning(f"Failed to extract symbols from {file_path}: {e}")
                results[file_path] = []
        
        return results
    
    async def get_symbol_hierarchy(self, file_path: str, repository_id: str | None = None) -> dict[str, Any]:
        """Get hierarchical symbol structure for a file.
        
        Args:
            file_path: Path to the file
            repository_id: Optional repository identifier
            
        Returns:
            Dictionary with file, repository_id, and hierarchical symbols
        """
        symbols = await self.get_document_symbols(file_path, repository_id)
        
        # Build hierarchy from flat list
        hierarchy: dict[str, Any] = {
            "file": file_path,
            "repository_id": repository_id or "",
            "symbols": []
        }
        
        # If symbols already have children populated, use them directly
        if symbols and hasattr(symbols[0], 'children') and any(s.children for s in symbols):
            # Symbols already have hierarchy, just convert to dict format
            root_symbols = [s for s in symbols if not getattr(s, 'parent_id', None)]
            
            def symbol_to_dict(symbol: Any) -> dict[str, Any]:
                result = {
                    "name": symbol.name,
                    "kind": symbol.kind.value if hasattr(symbol.kind, 'value') else str(symbol.kind),
                    "line": symbol.line_number,
                    "children": []
                }
                if hasattr(symbol, 'children') and symbol.children:
                    for child in symbol.children:
                        result["children"].append(symbol_to_dict(child))
                return result
            
            for symbol in root_symbols:
                hierarchy["symbols"].append(symbol_to_dict(symbol))
        else:
            # Build hierarchy from parent_id relationships
            root_symbols = []
            children_by_parent: dict[str, list[Any]] = {}
            symbol_by_name: dict[str, Any] = {}
            
            # First, collect all symbols by name for lookup
            for symbol in symbols:
                # Track both full name and base name
                base_name = symbol.name.split('.')[0] if '.' in symbol.name else symbol.name
                # Only store the first symbol with each base name (the class/function definition)
                if base_name not in symbol_by_name:
                    symbol_by_name[base_name] = symbol
                symbol_by_name[symbol.name] = symbol
            
            for symbol in symbols:
                parent_id = getattr(symbol, 'parent_id', None)
                if parent_id:
                    # The parent_id format is "ParentName:line_number"
                    # We need to find the actual parent symbol to get its correct line number
                    parent_name = parent_id.split(':')[0] if ':' in parent_id else parent_id
                    
                    # Find the actual parent symbol
                    if parent_name in symbol_by_name:
                        parent_symbol = symbol_by_name[parent_name]
                        parent_key = f"{parent_symbol.name}:{parent_symbol.line_number}"
                        if parent_key not in children_by_parent:
                            children_by_parent[parent_key] = []
                        children_by_parent[parent_key].append(symbol)
                    else:
                        # Parent not found, treat as root
                        root_symbols.append(symbol)
                else:
                    # No parent, this is a root symbol
                    # Filter out variables from root level - they should have parents
                    if not (hasattr(symbol, 'kind') and symbol.kind.value == 'variable'):
                        root_symbols.append(symbol)
            
            def build_symbol_dict(symbol: Any) -> dict[str, Any]:
                symbol_dict = {
                    "name": symbol.name,
                    "kind": symbol.kind.value if hasattr(symbol.kind, 'value') else str(symbol.kind),
                    "line": symbol.line_number,
                    "children": []
                }
                
                # Look for children using the symbol's identifier
                symbol_key = f"{symbol.name}:{symbol.line_number}"
                if symbol_key in children_by_parent:
                    for child in children_by_parent[symbol_key]:
                        symbol_dict["children"].append(build_symbol_dict(child))
                
                return symbol_dict
            
            # Build root level symbols
            for symbol in root_symbols:
                hierarchy["symbols"].append(build_symbol_dict(symbol))
        
        return hierarchy

    async def get_document_symbols(self, file_path: str, repository_id: str | None = None) -> list[Symbol]:
        """Get hierarchical symbols for a file.

        Attempts to retrieve symbols via LSP first, falls back to AST extraction
        if LSP is unavailable. Results are cached to reduce repeated extractions.

        Args:
            file_path: Absolute path to the file
            repository_id: Optional repository identifier

        Returns:
            List of Symbol objects with hierarchy information
        """
        # Validate file type if config is available
        if self.config:
            from pathlib import Path
            from errors import InvalidFileTypeError
            file_ext = Path(file_path).suffix.lower()
            if not self.config.is_supported_file(file_path):
                raise InvalidFileTypeError(
                    f"Unsupported file type: {file_ext}",
                    {"file": file_path, "extension": file_ext}
                )
        
        self.repository_id = repository_id  # Store for use in extraction
        # Check cache first
        cached = self._check_cache(file_path)
        if cached is not None:
            logger.debug(f"Using cached symbols for {file_path}")
            return cached

        try:
            # Try LSP first
            if self.lsp_client and hasattr(self.lsp_client, 'is_connected') and self.lsp_client.is_connected():
                lsp_response = await self.lsp_client.get_document_symbols(file_path)
                if lsp_response:
                    symbols = self._convert_lsp_response(lsp_response)
                    if self._validate_symbol_ranges(symbols):
                        self._save_to_cache(file_path, symbols)
                        return symbols
        except (LSPConnectionError, Exception) as e:
            logger.warning(f"LSP extraction failed for {file_path}: {e}")

        # Fallback to AST extraction
        return await self._extract_with_ast_fallback(file_path)

    def _check_cache(self, file_path: str) -> list[Symbol] | None:
        """Check JSON cache for valid symbols.

        Validates cache freshness based on file modification time and TTL.

        Args:
            file_path: Path to the file

        Returns:
            List of cached symbols if valid, None otherwise
        """
        if not self.cache_dir:
            return None

        cache_file = (
            self.cache_dir / f"{hashlib.md5(file_path.encode()).hexdigest()}.json"
        )
        if not cache_file.exists():
            return None

        try:
            current_hash = self._calculate_file_hash(file_path)
            with open(cache_file) as f:
                cache_data = json.load(f)
                cache_entry = DocumentSymbolCache.from_json(json.dumps(cache_data))
                if cache_entry.is_valid(current_hash, self.cache_ttl):
                    return cache_entry.symbols
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Cache read error for {file_path}: {e}")

        return None

    def _save_to_cache(self, file_path: str, symbols: list[Symbol]) -> None:
        """Save symbols to JSON cache.

        Stores symbols with file hash and timestamp for validation.

        Args:
            file_path: Path to the file
            symbols: List of symbols to cache
        """
        if not self.cache_dir:
            return

        cache_entry = DocumentSymbolCache(
            file_path=file_path,
            file_hash=self._calculate_file_hash(file_path),
            timestamp=time.time(),
            symbols=symbols,
        )

        cache_file = (
            self.cache_dir / f"{hashlib.md5(file_path.encode()).hexdigest()}.json"
        )
        try:
            with open(cache_file, "w") as f:
                f.write(cache_entry.to_json())
        except OSError as e:
            logger.warning(f"Cache write error for {file_path}: {e}")

    def _convert_lsp_response(self, lsp_symbols: list[dict]) -> list[Symbol]:
        """Convert LSP response to Symbol hierarchy.

        Handles both flat and nested LSP response formats.

        Args:
            lsp_symbols: Raw LSP documentSymbol response

        Returns:
            List of Symbol objects with hierarchy
        """
        symbols = []

        def convert_recursive(lsp_sym: dict, parent_id: str | None = None) -> Symbol:
            # Extract basic info
            name = lsp_sym.get("name", "")
            kind = self._normalize_symbol_kind(lsp_sym.get("kind", 0))

            # Extract range
            range_data = lsp_sym.get("range", {})
            start = range_data.get("start", {})
            end = range_data.get("end", {})

            symbol = Symbol(
                name=name,
                kind=kind,
                file_path=None,  # Will be set by storage
                line_number=start.get("line", 0) + 1,  # LSP is 0-based
                column=start.get("character", 0),
                end_line=end.get("line", 0) + 1,
                end_column=end.get("character", 0),
                parent_id=parent_id,
            )

            symbols.append(symbol)

            # Process children
            if "children" in lsp_sym:
                for child in lsp_sym.get("children", []):
                    convert_recursive(child, f"{name}:{start.get('line', 0)}")

            return symbol

        for lsp_symbol in lsp_symbols:
            convert_recursive(lsp_symbol)

        return symbols

    def _build_hierarchy(self, symbols: list[Symbol]) -> list[Symbol]:
        """Build parent-child relationships.

        Constructs the symbol hierarchy based on containment ranges.

        Args:
            symbols: Flat list of symbols with range information

        Returns:
            Hierarchical list of root symbols with children
        """
        # Sort symbols by position
        sorted_symbols = sorted(symbols, key=lambda s: (s.line_number, s.column))

        # Build hierarchy based on containment
        roots = []
        for i, symbol in enumerate(sorted_symbols):
            # Find potential parent
            parent_found = False
            for j in range(i - 1, -1, -1):
                parent = sorted_symbols[j]
                # Check if symbol is contained within parent
                if (
                    parent.line_number <= symbol.line_number
                    and parent.end_line >= symbol.end_line
                ):
                    symbol.parent_id = f"{parent.name}:{parent.line_number}"
                    parent_found = True
                    break

            if not parent_found:
                roots.append(symbol)

        return roots

    def _calculate_file_hash(self, file_path: str) -> str:
        """Calculate SHA256 hash of file contents.

        Args:
            file_path: Path to the file

        Returns:
            Hex string of file hash
        """
        try:
            with open(file_path, "rb") as f:
                return hashlib.sha256(f.read()).hexdigest()
        except OSError:
            return ""

    def _normalize_symbol_kind(self, kind: str | int) -> SymbolKind:
        """Normalize LSP symbol kind to internal SymbolKind enum.

        Handles both numeric and string constants from different LSP servers.

        Args:
            kind: LSP symbol kind (numeric or string)

        Returns:
            Normalized SymbolKind enum value
        """
        return LSP_SYMBOL_KIND_MAP.map_lsp_kind(kind)

    async def _extract_with_ast_fallback(self, file_path: str) -> list[Symbol]:
        """Extract symbols using AST when LSP is unavailable.

        Args:
            file_path: Path to the file

        Returns:
            List of symbols extracted via AST
        """
        # Additional file type check before attempting extraction
        if self.config:
            from pathlib import Path
            from errors import InvalidFileTypeError
            if not self.config.is_supported_file(file_path):
                file_ext = Path(file_path).suffix.lower()
                raise InvalidFileTypeError(
                    f"Unsupported file type: {file_ext}",
                    {"file": file_path, "extension": file_ext}
                )
        
        if not self.symbol_extractor:
            return []
            
        try:
            # Use the appropriate extraction method based on available interface
            # Prefer hierarchy-aware extraction if available
            if hasattr(self.symbol_extractor, 'extract_symbol_hierarchy'):
                # Hierarchy-aware extraction (preferred)
                symbols = self.symbol_extractor.extract_symbol_hierarchy(file_path)
                # Set repository_id if available
                repository_id = getattr(self, 'repository_id', None)
                if repository_id:
                    for symbol in symbols:
                        symbol.repository_id = repository_id
            elif hasattr(self.symbol_extractor, 'extract_from_file'):
                # PythonSymbolExtractor pattern
                repository_id = getattr(self, 'repository_id', 'unknown')
                symbols = self.symbol_extractor.extract_from_file(file_path, repository_id)
            elif hasattr(self.symbol_extractor, 'extract'):
                # Simple extraction
                symbols = self.symbol_extractor.extract(file_path)
            else:
                logger.warning(f"Extractor {type(self.symbol_extractor)} has no known extraction method")
                return []
                
            self._save_to_cache(file_path, symbols)
            return symbols
        except Exception as e:
            logger.error(f"AST extraction failed for {file_path}: {e}")
            raise SymbolExtractionError(
                f"Failed to extract symbols from {file_path}: {e}"
            ) from e

        return []

    def _validate_symbol_ranges(self, symbols: list[Symbol]) -> bool:
        """Validate that symbol ranges are consistent and non-overlapping.

        Args:
            symbols: List of symbols to validate

        Returns:
            True if all ranges are valid
        """
        for symbol in symbols:
            # Check basic range validity
            if symbol.line_number < 1 or symbol.end_line < symbol.line_number:
                return False
            if (
                symbol.line_number == symbol.end_line
                and symbol.end_column < symbol.column
            ):
                return False

        # Check for circular references
        if self._detect_circular_references(symbols):
            return False

        return True

    def _detect_circular_references(self, symbols: list[Symbol]) -> bool:
        """Detect and prevent circular parent-child references.

        Args:
            symbols: List of symbols to check

        Returns:
            True if circular references detected
        """
        # Build parent map
        parent_map = {s.name: s.parent_id for s in symbols if s.parent_id}

        # Check for cycles
        for symbol in symbols:
            visited = set()
            current = symbol.name

            while current in parent_map:
                if current in visited:
                    return True  # Cycle detected
                visited.add(current)
                parent_id = parent_map[current]
                if parent_id:
                    # Extract parent name from parent_id format
                    current = parent_id.split(":")[0]
                else:
                    break

        return False

    def clear_cache(self, file_path: str | None = None) -> None:
        """Clear cached symbols.

        Args:
            file_path: Specific file to clear, or None to clear all
        """
        if not self.cache_dir:
            return

        if file_path:
            # Clear specific file
            cache_file = (
                self.cache_dir / f"{hashlib.md5(file_path.encode()).hexdigest()}.json"
            )
            if cache_file.exists():
                try:
                    cache_file.unlink()
                except OSError as e:
                    logger.warning(f"Failed to clear cache for {file_path}: {e}")

            # Remove from memory cache
            self._cache.pop(file_path, None)
        else:
            # Clear all cache files
            if self.cache_dir.exists():
                for cache_file in self.cache_dir.glob("*.json"):
                    try:
                        cache_file.unlink()
                    except OSError as e:
                        logger.warning(f"Failed to clear cache file {cache_file}: {e}")

            # Clear memory cache
            self._cache.clear()

    def get_cache_stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        stats = {
            "cache_enabled": self.cache_dir is not None,
            "cache_dir": str(self.cache_dir) if self.cache_dir else None,
            "cache_ttl": self.cache_ttl,
            "memory_cache_size": len(self._cache),
            "disk_cache_files": 0,
            "disk_cache_size_mb": 0.0,
        }

        if self.cache_dir and self.cache_dir.exists():
            cache_files = list(self.cache_dir.glob("*.json"))
            stats["disk_cache_files"] = len(cache_files)
            total_size = sum(f.stat().st_size for f in cache_files)
            stats["disk_cache_size_mb"] = total_size / (1024 * 1024)

        return stats

    async def get_batch_symbols(
        self,
        file_paths: list[str],
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> dict[str, list[Symbol]]:
        """Extract symbols from multiple files concurrently.

        Args:
            file_paths: List of file paths to process
            progress_callback: Optional callback for progress reporting (current, total)

        Returns:
            Dictionary mapping file paths to their symbols

        Raises:
            SymbolExtractionError: If batch extraction fails
        """
        results = {}
        total = len(file_paths)
        completed = 0

        # Process files concurrently
        tasks = []
        for file_path in file_paths:
            task = asyncio.create_task(self.get_document_symbols(file_path))
            tasks.append((file_path, task))

        # Gather results
        for file_path, task in tasks:
            try:
                symbols = await task
                results[file_path] = symbols
                completed += 1

                if progress_callback:
                    progress_callback(completed, total)
            except Exception as e:
                logger.error(f"Failed to extract symbols from {file_path}: {e}")
                results[file_path] = []

        return results


@dataclass
class DocumentSymbolCache:
    """Cache entry for document symbols."""

    file_path: str
    file_hash: str
    timestamp: float
    symbols: list[Symbol]

    def is_valid(self, current_hash: str, ttl: float) -> bool:
        """Check if cache entry is still valid.

        Args:
            current_hash: Current file hash
            ttl: Time-to-live in seconds

        Returns:
            True if cache is valid
        """
        # Check hash match
        if self.file_hash != current_hash:
            return False

        # Check TTL
        age = time.time() - self.timestamp
        return age < ttl

    def to_json(self) -> str:
        """Serialize cache entry to JSON.

        Returns:
            JSON string representation
        """
        data = {
            "file_path": self.file_path,
            "file_hash": self.file_hash,
            "timestamp": self.timestamp,
            "symbols": [asdict(s) for s in self.symbols],
        }
        return json.dumps(data, indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> "DocumentSymbolCache":
        """Deserialize cache entry from JSON.

        Args:
            json_str: JSON string representation

        Returns:
            DocumentSymbolCache instance
        """
        data = json.loads(json_str)
        symbols = [Symbol(**s) for s in data["symbols"]]
        return cls(
            file_path=data["file_path"],
            file_hash=data["file_hash"],
            timestamp=data["timestamp"],
            symbols=symbols,
        )
