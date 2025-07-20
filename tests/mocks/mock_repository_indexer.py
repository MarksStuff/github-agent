"""Mock repository indexer for testing."""

from repository_indexer import AbstractRepositoryIndexer, IndexingResult


class MockRepositoryIndexer(AbstractRepositoryIndexer):
    """Mock repository indexer for testing."""

    def __init__(self):
        """Initialize empty mock indexer."""
        self.predefined_result = IndexingResult()
        self.last_repository_path = ""
        self.last_repository_id = ""
        self.clear_calls: list[str] = []

    def index_repository(
        self, repository_path: str, repository_id: str
    ) -> IndexingResult:
        """Return predefined result and track call parameters."""
        self.last_repository_path = repository_path
        self.last_repository_id = repository_id
        return self.predefined_result

    def clear_repository_index(self, repository_id: str) -> None:
        """Track clear repository calls."""
        self.clear_calls.append(repository_id)
