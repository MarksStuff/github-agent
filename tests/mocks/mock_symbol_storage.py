"""Mock symbol storage for testing."""

from datetime import UTC, datetime

from symbol_storage import AbstractSymbolStorage, CommentReply, Symbol


class MockSymbolStorage(AbstractSymbolStorage):
    """Mock symbol storage for testing."""

    def __init__(self):
        """Initialize mock storage."""
        self.symbols: list[Symbol] = []
        self.deleted_repositories: list[str] = []
        self._health_check_result: bool = True
        self._comment_replies: dict[tuple[int, int], CommentReply] = {}

    def create_schema(self) -> None:
        """Create schema (no-op for mock)."""
        pass

    def insert_symbol(self, symbol: Symbol) -> None:
        """Insert a symbol into mock storage."""
        self.symbols.append(symbol)

    def insert_symbols(self, symbols: list[Symbol]) -> None:
        """Insert symbols into mock storage."""
        self.symbols.extend(symbols)

    def update_symbol(self, symbol: Symbol) -> None:
        """Update symbol in mock storage (no-op for mock)."""
        pass

    def delete_symbol(self, symbol_id: int) -> None:
        """Delete symbol by ID (no-op for mock)."""
        pass

    def delete_symbols_by_repository(self, repository_id: str) -> None:
        """Delete symbols by repository in mock storage."""
        self.deleted_repositories.append(repository_id)
        self.symbols = [s for s in self.symbols if s.repository_id != repository_id]

    def search_symbols(
        self,
        query: str,
        repository_id: str | None = None,
        symbol_kind: str | None = None,
        limit: int = 50,
    ) -> list[Symbol]:
        """Search symbols in mock storage."""
        results = self.symbols.copy()

        if query:
            results = [s for s in results if query.lower() in s.name.lower()]
        if repository_id:
            results = [s for s in results if s.repository_id == repository_id]
        if symbol_kind:
            results = [s for s in results if s.kind.value == symbol_kind]

        return results[:limit]

    def get_symbol_by_id(self, symbol_id: int) -> Symbol | None:
        """Get symbol by ID in mock storage (not implemented for mock)."""
        return None

    def get_symbols_by_file(self, file_path: str, repository_id: str) -> list[Symbol]:
        """Get symbols by file path in mock storage."""
        return [
            s
            for s in self.symbols
            if s.file_path == file_path and s.repository_id == repository_id
        ]

    def health_check(self) -> bool:
        """Mock health check returns configurable result."""
        return self._health_check_result

    def set_health_check_result(self, result: bool) -> None:
        """Set the health check result for testing."""
        self._health_check_result = result

    def mark_comment_replied(self, comment_reply: CommentReply) -> None:
        """Mark comment as replied in memory."""
        key = (comment_reply.comment_id, comment_reply.pr_number)
        self._comment_replies[key] = comment_reply

    def is_comment_replied(self, comment_id: int, pr_number: int) -> bool:
        """Check if comment is replied in memory."""
        key = (comment_id, pr_number)
        return key in self._comment_replies

    def get_replied_comment_ids(self, pr_number: int) -> set[int]:
        """Get all replied comment IDs for a PR from memory."""
        return {
            comment_id
            for (comment_id, pr_num) in self._comment_replies.keys()
            if pr_num == pr_number
        }

    def cleanup_old_comment_replies(self, days_old: int = 30) -> int:
        """Clean up old comment reply records from memory."""
        now = datetime.now(UTC)
        old_keys = []
        for key, reply in self._comment_replies.items():
            days_diff = (now - reply.replied_at).days
            if days_diff > days_old:
                old_keys.append(key)

        for key in old_keys:
            del self._comment_replies[key]

        return len(old_keys)

    def get_all_comment_replies(self) -> list[CommentReply]:
        """Testing helper method to get all comment replies."""
        return list(self._comment_replies.values())

    def clear_comment_replies(self) -> None:
        """Testing helper method to clear all comment replies."""
        self._comment_replies.clear()
