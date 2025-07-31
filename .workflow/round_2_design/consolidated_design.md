# Consolidated Design Document

## 1. Introduction

This design document specifies the architecture for GitHub PR comment persistence functionality that enables tracking which comments have been replied to in Pull Request workflows. The system integrates with the existing `/Users/mstriebeck/Code/github-agent` codebase, following established patterns in `symbol_storage.py`, `github_tools.py`, and testing frameworks.

The feature addresses the requirement: "When we use the github_post_pr_reply tool, we need to persist which comments we replied to. And then use this to make sure that subsequent calls of github_get_pr_comments don't return comments that we already replied to."

## 2. Goals / Non-Goals

### Goals

1. **Persistent Comment Tracking**: Store which PR comments have received replies
2. **Existing Tool Integration**: Extend `github_get_pr_comments` to filter replied comments
3. **Architectural Consistency**: Follow existing `SQLiteSymbolStorage` patterns
4. **Backward Compatibility**: Maintain existing GitHub tool interfaces
5. **Repository Isolation**: Support per-repository comment tracking
6. **Resilient Storage**: Implement retry logic matching existing patterns

### Non-Goals

1. **Cross-Repository Analytics**: No aggregation across multiple repositories
2. **Comment Content Storage**: Store only tracking metadata, not full comment content
3. **Real-time Synchronization**: No live updates or webhooks
4. **Advanced Search**: Basic lookup only, no complex querying
5. **User Management**: No user-specific tracking or permissions
6. **Performance Optimization**: Focus on correctness over performance for MVP

## 3. Proposed Architecture

The architecture extends the existing storage pattern with a new `AbstractCommentStorage` interface and `SQLiteCommentStorage` implementation, mirroring the `symbol_storage.py` design. Integration occurs through modification of existing GitHub tools rather than creating parallel systems.

**Core Components:**
- `AbstractCommentStorage`: Interface following existing `AbstractSymbolStorage` pattern
- `SQLiteCommentStorage`: SQLite implementation with internal retry logic
- `CommentRecord`: Data class for comment tracking metadata
- Modified `github_get_pr_comments()`: Filters replied comments
- New `github_mark_comment_replied()`: Marks comments as replied

**Storage Strategy:** SQLite database following existing `symbols.db` pattern, with ISO string timestamps and internal retry mechanisms.

## 4. Detailed Design

### 4.1 Data Model

```python
@dataclass
class CommentRecord:
    """Comment tracking record following existing Symbol pattern."""
    comment_id: str
    pr_number: int
    repository_id: str
    created_at: str  # ISO string from GitHub API
    replied_at: str | None = None
    
    @property
    def created_datetime(self) -> datetime:
        """Parse ISO string to datetime following health_monitor.py:456 pattern."""
        return datetime.fromisoformat(self.created_at)
    
    @property
    def replied_datetime(self) -> datetime | None:
        """Parse replied timestamp to datetime."""
        return datetime.fromisoformat(self.replied_at) if self.replied_at else None
```

### 4.2 Abstract Interface

```python
class AbstractCommentStorage(ABC):
    """Abstract base class for comment storage operations."""
    
    @abstractmethod
    def create_schema(self) -> None:
        """Create the database schema for comment storage."""
        pass
    
    @abstractmethod
    def mark_comment_replied(self, comment_id: str, pr_number: int, repository_id: str) -> None:
        """Mark a comment as replied."""
        pass
    
    @abstractmethod
    def is_comment_replied(self, comment_id: str, repository_id: str) -> bool:
        """Check if a comment has been replied to."""
        pass
    
    @abstractmethod
    def get_replied_comments(self, pr_number: int, repository_id: str) -> list[CommentRecord]:
        """Get all replied comments for a PR."""
        pass
    
    @abstractmethod
    def health_check(self) -> bool:
        """Check if the comment storage is accessible and functional."""
        pass
```

### 4.3 SQLite Implementation

```python
class SQLiteCommentStorage(AbstractCommentStorage):
    """SQLite implementation following SQLiteSymbolStorage pattern."""
    
    def __init__(self, db_path: str | Path, max_retries: int = 3, retry_delay: float = 0.1):
        """Initialize following SQLiteSymbolStorage pattern (line 127)."""
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection: sqlite3.Connection | None = None
        self._connection_lock = threading.Lock()
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.create_schema()
    
    def _execute_with_retry(self, operation_name: str, operation_func, *args, **kwargs):
        """Execute with retry following SQLiteSymbolStorage pattern (line 201)."""
        # Exact implementation from symbol_storage.py lines 201-225
    
    def mark_comment_replied(self, comment_id: str, pr_number: int, repository_id: str) -> None:
        """Mark comment as replied with current timestamp."""
        def _mark_replied():
            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO comment_replies 
                    (comment_id, pr_number, repository_id, created_at, replied_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (comment_id, pr_number, repository_id, 
                     datetime.now().isoformat(), datetime.now().isoformat())
                )
                conn.commit()
        
        self._execute_with_retry("Mark comment replied", _mark_replied)
```

### 4.4 Database Schema

```sql
CREATE TABLE IF NOT EXISTS comment_replies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    comment_id TEXT NOT NULL,
    pr_number INTEGER NOT NULL,
    repository_id TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    replied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(comment_id, repository_id)
);

CREATE INDEX IF NOT EXISTS idx_comment_replies_comment_id 
ON comment_replies(comment_id);

CREATE INDEX IF NOT EXISTS idx_comment_replies_pr_repository 
ON comment_replies(pr_number, repository_id);

CREATE INDEX IF NOT EXISTS idx_comment_replies_repository 
ON comment_replies(repository_id);
```

### 4.5 GitHub Tool Integration

#### Modified github_get_pr_comments (line 392)

```python
async def execute_get_pr_comments(repo_name: str, pr_number: int) -> str:
    """Get PR comments, filtering out already replied comments."""
    try:
        # ... existing logic through line 478 ...
        
        # NEW: Filter replied comments
        comment_storage = get_comment_storage(repo_name)
        
        # Filter review comments
        filtered_review_comments = []
        for comment in formatted_review_comments:
            if not comment_storage.is_comment_replied(str(comment["id"]), context.repo_name):
                filtered_review_comments.append(comment)
        
        # Filter issue comments  
        filtered_issue_comments = []
        for comment in formatted_issue_comments:
            if not comment_storage.is_comment_replied(str(comment["id"]), context.repo_name):
                filtered_issue_comments.append(comment)
        
        # Return filtered results
        return json.dumps({
            "success": True,
            "pr_number": pr_number,
            "review_comments": filtered_review_comments,
            "issue_comments": filtered_issue_comments,
            "total_unread_comments": len(filtered_review_comments) + len(filtered_issue_comments)
        })
```

#### New github_mark_comment_replied Tool

```python
async def execute_mark_comment_replied(repo_name: str, comment_id: int, pr_number: int) -> str:
    """Mark a comment as replied to."""
    try:
        context = get_github_context(repo_name)
        comment_storage = get_comment_storage(repo_name)
        
        comment_storage.mark_comment_replied(str(comment_id), pr_number, context.repo_name)
        
        return json.dumps({
            "success": True,
            "comment_id": comment_id,
            "pr_number": pr_number,
            "repository": context.repo_name,
            "marked_at": datetime.now().isoformat()
        })
    except Exception as e:
        return json.dumps({"error": f"Failed to mark comment replied: {e!s}"})
```

#### TOOL_HANDLERS Update (line 880)

```python
TOOL_HANDLERS: dict[str, Callable[..., Awaitable[str]]] = {
    "git_get_current_branch": execute_get_current_branch,
    "git_get_current_commit": execute_get_current_commit,
    "github_find_pr_for_branch": execute_find_pr_for_branch,
    "github_get_pr_comments": execute_get_pr_comments,  # MODIFIED
    "github_post_pr_reply": execute_post_pr_reply,
    "github_mark_comment_replied": execute_mark_comment_replied,  # NEW
    # ... existing handlers
}
```

### 4.6 Configuration and Factory

```python
def get_comment_storage(repo_name: str) -> AbstractCommentStorage:
    """Get comment storage for repository following existing patterns."""
    if not repo_manager:
        raise ValueError("Repository manager not initialized")
    
    repo_config = repo_manager.get_repository(repo_name)
    if not repo_config:
        raise ValueError(f"Repository '{repo_name}' not found")
    
    # Use DATA_DIR pattern from constants.py
    db_path = DATA_DIR / f"comments_{repo_name.replace('/', '_')}.db"
    return SQLiteCommentStorage(db_path)
```

## 5. Alternatives Considered

### 5.1 External Retry Composition (Rejected)
**Proposed by**: Senior Engineer, Tester analyses
**Approach**: RetryStrategy interface with dependency injection
**Rejection Reason**: Conflicts with existing `SQLiteSymbolStorage` internal retry pattern (line 201). Would require architectural changes across the codebase.

### 5.2 JSON File Storage (Rejected)
**Proposed by**: Developer analysis
**Approach**: Simple JSON file persistence
**Rejection Reason**: Inconsistent with existing SQLite pattern in `symbol_storage.py`. No transaction safety or concurrent access handling.

### 5.3 Date Object Serialization (Rejected)
**Proposed by**: Senior Engineer analysis  
**Approach**: Complex serialization boundaries with Date objects
**Rejection Reason**: Existing codebase uses ISO strings with `datetime.fromisoformat()` parsing (health_monitor.py:456). Over-engineered for simple timestamp storage.

### 5.4 New CommentTracker Component (Rejected)
**Proposed by**: Developer analysis
**Approach**: Separate tracking component independent of GitHub tools
**Rejection Reason**: Would require parallel systems. Better to extend existing `github_get_pr_comments` function following single responsibility principle.

## 6. Testing / Validation

### 6.1 Mock Implementation

```python
class MockCommentStorage(AbstractCommentStorage):
    """Mock comment storage following mock_symbol_storage.py pattern."""
    
    def __init__(self):
        self.replies: dict[str, CommentRecord] = {}
        self._health_check_result: bool = True
    
    def create_schema(self) -> None:
        """No-op for mock."""
        pass
    
    def mark_comment_replied(self, comment_id: str, pr_number: int, repository_id: str) -> None:
        key = f"{comment_id}:{repository_id}"
        self.replies[key] = CommentRecord(
            comment_id=comment_id,
            pr_number=pr_number,
            repository_id=repository_id,
            created_at=datetime.now().isoformat(),
            replied_at=datetime.now().isoformat()
        )
    
    def is_comment_replied(self, comment_id: str, repository_id: str) -> bool:
        key = f"{comment_id}:{repository_id}"
        return key in self.replies
```

### 6.2 Unit Tests

```python
class TestSQLiteCommentStorage:
    """Unit tests following test_symbol_storage.py pattern."""
    
    @pytest.fixture
    def storage(self, tmp_path):
        """Create test storage instance."""
        db_path = tmp_path / "test_comments.db"
        return SQLiteCommentStorage(db_path)
    
    def test_mark_comment_replied(self, storage):
        """Test marking comment as replied."""
        storage.mark_comment_replied("123", 456, "owner/repo")
        assert storage.is_comment_replied("123", "owner/repo") is True
    
    def test_comment_not_replied_initially(self, storage):
        """Test comment not replied by default."""
        assert storage.is_comment_replied("999", "owner/repo") is False
    
    def test_get_replied_comments_for_pr(self, storage):
        """Test retrieving replied comments for specific PR."""
        storage.mark_comment_replied("123", 456, "owner/repo")
        storage.mark_comment_replied("124", 456, "owner/repo")
        
        replied = storage.get_replied_comments(456, "owner/repo")
        assert len(replied) == 2
        assert all(r.pr_number == 456 for r in replied)
```

### 6.3 Integration Tests

```python
class TestGitHubCommentIntegration:
    """Integration tests for GitHub comment workflow."""
    
    @pytest.mark.asyncio
    async def test_end_to_end_comment_workflow(self, mock_github_context):
        """Test complete comment reply and filtering workflow."""
        # Setup mock PR with comments
        mock_pr_comments = [
            {"id": 123, "body": "Please fix this", "user": {"login": "reviewer"}},
            {"id": 124, "body": "Also this", "user": {"login": "reviewer"}}
        ]
        
        # Get initial comments (should return all)
        result = await execute_get_pr_comments("test-repo", 456)
        data = json.loads(result)
        assert len(data["review_comments"]) == 2
        
        # Mark one comment as replied
        await execute_mark_comment_replied("test-repo", 123, 456)
        
        # Get comments again (should filter replied)
        result = await execute_get_pr_comments("test-repo", 456)
        data = json.loads(result)
        assert len(data["review_comments"]) == 1
        assert data["review_comments"][0]["id"] == 124
```

### 6.4 Error Handling Tests

```python
def test_database_corruption_recovery(self, tmp_path):
    """Test database corruption recovery following symbol_storage pattern."""
    db_path = tmp_path / "corrupt.db"
    
    # Create corrupted database file
    with open(db_path, "wb") as f:
        f.write(b"corrupted data")
    
    # Should recover and create new schema
    storage = SQLiteCommentStorage(db_path)
    assert storage.health_check() is True

def test_retry_mechanism_on_database_lock(self, tmp_path):
    """Test retry logic on database lock scenarios."""
    # Implementation following SQLiteSymbolStorage retry tests
```

## 7. Migration / Deployment & Rollout

### 7.1 Implementation Sequence

1. **Step 1**: Create `comment_storage.py` with abstract interface and SQLite implementation
2. **Step 2**: Add `get_comment_storage()` factory function to `github_tools.py`
3. **Step 3**: Modify `execute_get_pr_comments()` to filter replied comments
4. **Step 4**: Add `execute_mark_comment_replied()` function and tool definition
5. **Step 5**: Update `TOOL_HANDLERS` mapping with new tool
6. **Step 6**: Add `github_mark_comment_replied` to `get_tools()` function
7. **Step 7**: Create mock implementation in `tests/mocks/mock_comment_storage.py`
8. **Step 8**: Add unit and integration tests

### 7.2 Database Migration

```python
def migrate_comment_storage_schema():
    """Migrate existing databases if needed."""
    # Check for existing comment_replies table
    # Add any missing indexes
    # No data migration required for new feature
```

### 7.3 Backward Compatibility

- **Existing Tools**: All existing GitHub tools maintain same interfaces
- **Configuration**: No configuration changes required
- **Dependencies**: No new external dependencies

### 7.4 Rollout Process

1. **Development**: Implement with comprehensive tests
2. **Testing**: Verify with real GitHub PR workflows
3. **Staging**: Deploy to staging environment with existing repositories
4. **Production**: Enable for specific repositories first, then expand

## Appendix

### A.1 Conflict Resolutions

**Storage Technology Conflict**: Developer advocated JSON files, Architect required SQLite consistency. **Resolution**: Follow existing SQLite pattern for architectural consistency.

**Development Methodology Conflict**: Developer wanted ship-first approach, Tester demanded test-first. **Resolution**: Implement with comprehensive tests but focus on working functionality over perfect coverage initially.

**Abstraction Level Conflict**: Developer wanted simple classes, Senior Engineer wanted complex interfaces. **Resolution**: Use existing abstract base class pattern but keep implementation simple.

**Integration Strategy Conflict**: Developer wanted new component, Architect wanted existing tool modification. **Resolution**: Extend existing `github_get_pr_comments` function following single responsibility principle.

**Retry Implementation Conflict**: Multiple approaches proposed. **Resolution**: Follow exact `SQLiteSymbolStorage` internal retry pattern for consistency.

### A.2 File Modifications Required

- **github_tools.py**: Lines 392-500 (modify `execute_get_pr_comments`), line 880 (update `TOOL_HANDLERS`)
- **New file**: `comment_storage.py` (complete implementation)
- **New file**: `tests/mocks/mock_comment_storage.py` (mock implementation)
- **New file**: `tests/test_comment_storage.py` (unit tests)

### A.3 Database Schema Details

Database file location: `DATA_DIR / comments_{repository}.db` following existing pattern from `symbol_storage.py:544`.

Total storage overhead: ~50 bytes per replied comment (minimal impact).

Query performance: Indexed on comment_id and repository_id for O(log n) lookup time.