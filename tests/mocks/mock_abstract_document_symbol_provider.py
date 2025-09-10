"""Mock implementations for AbstractDocumentSymbolProvider."""

import asyncio

from abstract_document_symbol_provider import AbstractDocumentSymbolProvider


class MockDocumentSymbolProvider(AbstractDocumentSymbolProvider):
    """Mock document symbol provider for testing."""

    def __init__(
        self,
        return_symbols: list[dict] | None = None,
        should_fail: bool = False,
        fail_message: str = "Provider failed",
    ):
        """Initialize with configurable behavior."""
        self.return_symbols = return_symbols or []
        self.should_fail = should_fail
        self.fail_message = fail_message

        # Call tracking
        self.get_symbols_called = False
        self.get_hierarchy_called = False
        self.batch_extract_called = False
        self.last_file_path = None
        self.last_repository_id = None
        self.last_file_paths = []
        self.progress_updates = []

    async def get_document_symbols(
        self, file_path: str, repository_id: str = "default"
    ) -> list[dict]:
        """Return predefined symbols."""
        self.get_symbols_called = True
        self.last_file_path = file_path
        self.last_repository_id = repository_id

        if self.should_fail:
            raise Exception(self.fail_message)

        return self.return_symbols.copy()

    async def get_symbol_hierarchy(
        self, file_path: str, repository_id: str = "default"
    ) -> dict:
        """Return symbol hierarchy."""
        self.get_hierarchy_called = True
        self.last_file_path = file_path
        self.last_repository_id = repository_id

        if self.should_fail:
            raise Exception(self.fail_message)

        return {
            "file": file_path,
            "repository_id": repository_id,
            "symbols": self.return_symbols,
        }

    async def batch_extract_symbols(
        self,
        file_paths: list[str],
        repository_id: str = "default",
        progress_callback=None,
        max_workers: int = 4,
    ) -> dict[str, list[dict]]:
        """Extract symbols from multiple files."""
        self.batch_extract_called = True
        self.last_file_paths = file_paths.copy()
        self.last_repository_id = repository_id

        if self.should_fail:
            raise Exception(self.fail_message)

        results = {}
        for i, file_path in enumerate(file_paths):
            results[file_path] = self.return_symbols.copy()
            if progress_callback:
                progress = (i + 1) / len(file_paths)
                self.progress_updates.append(progress)
                await progress_callback(file_path, progress)

        return results


class AsyncFailingProvider(AbstractDocumentSymbolProvider):
    """Provider that fails asynchronously."""

    def __init__(self, delay: float = 0.1):
        self.delay = delay

    async def get_document_symbols(
        self, file_path: str, repository_id: str = "default"
    ) -> list[dict]:
        """Fail after a delay."""
        await asyncio.sleep(self.delay)
        raise RuntimeError("Async operation failed")

    async def get_symbol_hierarchy(
        self, file_path: str, repository_id: str = "default"
    ) -> dict:
        """Fail after a delay."""
        await asyncio.sleep(self.delay)
        raise RuntimeError("Async hierarchy failed")

    async def batch_extract_symbols(
        self,
        file_paths: list[str],
        repository_id: str = "default",
        progress_callback=None,
        max_workers: int = 4,
    ) -> dict[str, list[dict]]:
        """Fail after processing some files."""
        results = {}
        for i, file_path in enumerate(file_paths):
            if i > 0:  # Fail after first file
                await asyncio.sleep(self.delay)
                raise RuntimeError(f"Batch failed at {file_path}")
            results[file_path] = []
        return results
