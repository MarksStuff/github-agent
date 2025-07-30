# Consolidated Design Document

## 1. Introduction

This design document specifies the implementation of PR comment reply persistence for the GitHub MCP agent system. The feature enables tracking which PR comments have been replied to, preventing duplicate responses and improving workflow efficiency.

The implementation extends the existing SQLite storage patterns used by [`symbol_storage.py`](file:///Users/mstriebeck/Code/github-agent/symbol_storage.py) and integrates with the current GitHub tools architecture in [`github_tools.py`](file:///Users/mstriebeck/Code/github-agent/github_tools.py). The solution maintains architectural consistency with the master-worker process model and repository-aware database isolation.

## 2. Goals / Non-Goals

### Goals
- **Track replied comments**: Persist which comments have received replies to avoid duplicate responses
- **Filter unreplied comments**: Automatically exclude already-replied comments from `github_get_pr_comments` results
- **Repository isolation**: Maintain separate comment tracking per repository following existing patterns
- **Architectural consistency**: Reuse existing SQLite storage patterns, error handling, and dependency injection
- **Backward compatibility**: No breaking changes to existing API interfaces
- **Performance**: Efficient comment filtering with indexed database queries

### Non-Goals
- **Comment content storage**: Only track reply relationships, not comment text or metadata
- **Cross-repository analytics**: No aggregation of comment data across repositories
- **Real-time synchronization**: No live updates or webhooks for comment status changes
- **Comment threading analysis**: No deep analysis of comment conversation structures
- **GitHub API optimization**: No caching or rate limiting improvements beyond reply tracking

## 3. Proposed Architecture

The architecture extends the existing storage abstraction pattern with minimal system impact:

```mermaid
graph TB
    A[github_post_pr_reply] --> B[CommentReplyStorage]
    C[github_get_pr_comments] --> B
    B --> D[SQLiteCommentReplyStorage]
    D --> E[comment_replies_{repo}.db]
    
    F[AbstractCommentReplyStorage] --> D
    F --> G[MockCommentReplyStorage]
    
    H[Worker Process] --> I[CodebaseTools]
    I --> B
    
    subgraph "Per Repository"
        E
        J[symbols_{repo}.db]
    end
```

**Key Architectural Decisions**:
- **Repository-scoped databases**: Each repository maintains `DATA_DIR/comment_replies_{repo_id}.db`
- **Abstract base class pattern**: Follows existing `AbstractSymbolStorage` design for testability
- **Dependency injection**: Integrated into worker processes alongside existing symbol storage
- **Factory pattern**: Production factory class handles schema creation and configuration

## 4. Detailed Design

### 4.1 Core Data Structures

**CommentReply Dataclass**:
```python
@dataclass
class CommentReply:
    comment_id: int
    reply_id: int | None  # GitHub's response comment ID
    repository_id: str
    pr_number: int
    created_at: str | None = None
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "comment_id": self.comment_id,
            "reply_id": self.reply_id,
            "repository_id": self.repository_id,
            "pr_number": self.pr_number,
            "created_at": self.created_at,
        }
```

### 4.2 Abstract Base Class

**AbstractCommentReplyStorage** (`comment_storage.py`):
```python
class AbstractCommentReplyStorage(ABC):
    """Abstract base class for comment reply storage operations."""

    @abstractmethod
    def create_schema(self) -> None:
        """Create the database schema for comment reply storage."""
        pass

    @abstractmethod
    def record_reply(self, comment_id: int, reply_id: int | None, 
                    repository_id: str, pr_number: int) -> None:
        """Record that a comment has been replied to."""
        pass

    @abstractmethod
    def is_comment_replied(self, comment_id: int, repository_id: str) -> bool:
        """Check if a comment has been replied to."""
        pass

    @abstractmethod
    def get_replied_comment_ids(self, repository_id: str, 
                               pr_number: int | None = None) -> set[int]:
        """Get set of comment IDs that have been replied to."""
        pass

    @abstractmethod
    def health_check(self) -> bool:
        """Check if the comment reply storage is accessible."""
        pass
```

### 4.3 SQLite Implementation

**SQLiteCommentReplyStorage** (`comment_storage.py`):
```python
class SQLiteCommentReplyStorage(AbstractCommentReplyStorage):
    """SQLite implementation of comment reply storage."""

    def __init__(self, db_path: str | Path, max_retries: int = 3, 
                 retry_delay: float = 0.1):
        """Initialize SQLite comment reply storage."""
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection: sqlite3.Connection | None = None
        self._connection_lock = threading.Lock()
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.create_schema()

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection with retry logic."""
        # Implementation follows SQLiteSymbolStorage._get_connection pattern

    def _execute_with_retry(self, query: str, params: tuple = ()) -> Any:
        """Execute database operation with retry logic."""
        # Implementation follows SQLiteSymbolStorage._execute_with_retry pattern

    def create_schema(self) -> None:
        """Create comment reply tracking schema."""
        schema_sql = """
        CREATE TABLE IF NOT EXISTS comment_replies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            comment_id INTEGER NOT NULL,
            reply_id INTEGER,
            repository_id TEXT NOT NULL,
            pr_number INTEGER NOT NULL,
            created_at TEXT DEFAULT (datetime('now')),
            UNIQUE(comment_id, repository_id)
        );
        
        CREATE INDEX IF NOT EXISTS idx_comment_repo 
        ON comment_replies(repository_id, pr_number);
        
        CREATE INDEX IF NOT EXISTS idx_comment_lookup 
        ON comment_replies(comment_id, repository_id);
        """
        self._execute_with_retry(schema_sql)

    def record_reply(self, comment_id: int, reply_id: int | None,
                    repository_id: str, pr_number: int) -> None:
        """Record comment reply with conflict resolution."""
        insert_sql = """
        INSERT OR REPLACE INTO comment_replies 
        (comment_id, reply_id, repository_id, pr_number)
        VALUES (?, ?, ?, ?)
        """
        self._execute_with_retry(insert_sql, (comment_id, reply_id, repository_id, pr_number))

    def is_comment_replied(self, comment_id: int, repository_id: str) -> bool:
        """Check if comment has been replied to."""
        check_sql = """
        SELECT 1 FROM comment_replies 
        WHERE comment_id = ? AND repository_id = ?
        LIMIT 1
        """
        result = self._execute_with_retry(check_sql, (comment_id, repository_id))
        return bool(result.fetchone())

    def get_replied_comment_ids(self, repository_id: str, 
                               pr_number: int | None = None) -> set[int]:
        """Get replied comment IDs for filtering."""
        if pr_number is not None:
            query_sql = """
            SELECT comment_id FROM comment_replies 
            WHERE repository_id = ? AND pr_number = ?
            """
            params = (repository_id, pr_number)
        else:
            query_sql = """
            SELECT comment_id FROM comment_replies 
            WHERE repository_id = ?
            """
            params = (repository_id,)
        
        result = self._execute_with_retry(query_sql, params)
        return {row[0] for row in result.fetchall()}

    def health_check(self) -> bool:
        """Verify database accessibility."""
        try:
            self._execute_with_retry("SELECT 1")
            return True
        except Exception:
            return False
```

### 4.4 Production Factory

**ProductionCommentReplyStorage** (`comment_storage.py`):
```python
class ProductionCommentReplyStorage:
    """Factory for production comment reply storage instances."""

    @classmethod
    def create_with_schema(cls, repository_id: str) -> SQLiteCommentReplyStorage:
        """Create production storage instance with schema initialization."""
        db_path = DATA_DIR / f"comment_replies_{repository_id}.db"
        storage = SQLiteCommentReplyStorage(db_path)
        logger.info(f"Created comment reply storage for repository: {repository_id}")
        return storage
```

### 4.5 GitHub Tools Integration

**Modified execute_post_pr_reply** (`github_tools.py`):
```python
async def execute_post_pr_reply(repo_name: str, comment_id: int, message: str) -> str:
    """Reply to a PR comment and record the reply."""
    try:
        context = get_github_context(repo_name)
        if not context.repo:
            return json.dumps({"error": f"GitHub repository not configured for {repo_name}"})

        # Existing GitHub API logic (lines 548-625)...
        
        # NEW: After successful reply (line 591)
        if reply_resp.status_code in [200, 201]:
            # Record the successful reply
            comment_storage = ProductionCommentReplyStorage.create_with_schema(context.repo_name)
            comment_storage.record_reply(
                comment_id=comment_id,
                reply_id=reply_resp.json()["id"],
                repository_id=context.repo_name,
                pr_number=int(pr_number) if pr_number else 0
            )
            
            return json.dumps({
                "success": True,
                "method": "direct_reply",
                "repo": context.repo_name,
                "repo_config": repo_name,
                "comment_id": reply_resp.json()["id"],
                "url": reply_resp.json()["html_url"],
                "reply_recorded": True  # NEW field
            })
```

**Modified execute_get_pr_comments** (`github_tools.py`):
```python
async def execute_get_pr_comments(repo_name: str, pr_number: int) -> str:
    """Get PR comments with replied comment filtering."""
    try:
        context = get_github_context(repo_name)
        # Existing API calls (lines 410-478)...
        
        # NEW: Get replied comment IDs for filtering
        comment_storage = ProductionCommentReplyStorage.create_with_schema(context.repo_name)
        replied_comment_ids = comment_storage.get_replied_comment_ids(
            repository_id=context.repo_name,
            pr_number=pr_number
        )
        
        # Modified: Filter comments during formatting (line 483)
        formatted_review_comments = []
        for comment in review_comments:
            if comment["id"] not in replied_comment_ids:  # NEW filter condition
                formatted_review_comments.append({
                    "id": comment["id"],
                    "type": "review_comment",
                    "author": comment["user"]["login"],
                    "body": comment["body"],
                    "file": comment.get("path", ""),
                    "line": comment.get("line", comment.get("original_line", 0)),
                    "created_at": comment["created_at"],
                    "url": comment["html_url"],
                })

        # Similar filtering for issue comments...
        
        # Modified response with new fields
        result = {
            "pr_number": pr_number,
            "title": pr_data["title"],
            "repo": context.repo_name,
            "repo_config": repo_name,
            "review_comments": formatted_review_comments,
            "issue_comments": formatted_issue_comments,
            "total_comments": len(formatted_review_comments) + len(formatted_issue_comments),
            "replied_comment_count": len(replied_comment_ids),  # NEW field
            "unreplied_comment_count": total_original_comments - len(replied_comment_ids)  # NEW field
        }
```

### 4.6 Database Schema Details

**Complete DDL**:
```sql
CREATE TABLE IF NOT EXISTS comment_replies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    comment_id INTEGER NOT NULL,
    reply_id INTEGER,
    repository_id TEXT NOT NULL,
    pr_number INTEGER NOT NULL,
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(comment_id, repository_id)
);

-- Performance indexes
CREATE INDEX IF NOT EXISTS idx_comment_repo 
ON comment_replies(repository_id, pr_number);

CREATE INDEX IF NOT EXISTS idx_comment_lookup 
ON comment_replies(comment_id, repository_id);

-- Optional: Composite index for filtering queries
CREATE INDEX IF NOT EXISTS idx_repo_pr_comments 
ON comment_replies(repository_id, pr_number, comment_id);
```

**Sample Queries**:
```sql
-- Record a reply
INSERT OR REPLACE INTO comment_replies 
(comment_id, reply_id, repository_id, pr_number)
VALUES (123456, 789012, 'user/repo', 42);

-- Check if comment is replied
SELECT 1 FROM comment_replies 
WHERE comment_id = 123456 AND repository_id = 'user/repo'
LIMIT 1;

-- Get all replied comment IDs for PR
SELECT comment_id FROM comment_replies 
WHERE repository_id = 'user/repo' AND pr_number = 42;

-- Health check
SELECT COUNT(*) FROM comment_replies WHERE 1=1;
```

## 5. Alternatives Considered

### 5.1 JSON File Storage
**Rejected**: Would require custom locking mechanisms and lacks query performance of SQLite.

### 5.2 Single Global Database
**Rejected**: Violates existing repository isolation pattern and creates cross-repository dependencies.

### 5.3 In-Memory Cache Only
**Rejected**: Would lose reply tracking across worker process restarts.

### 5.4 GitHub API-based Tracking
**Rejected**: Would require additional API calls and doesn't scale with GitHub rate limits.

### 5.5 Extend Symbol Storage
**Rejected**: Comment replies are conceptually different from code symbols and would pollute the symbol schema.

## 6. Testing / Validation

### 6.1 Mock Implementation

**MockCommentReplyStorage** (`tests/mocks/mock_comment_storage.py`):
```python
class MockCommentReplyStorage(AbstractCommentReplyStorage):
    """Mock comment reply storage for testing."""

    def __init__(self):
        self.replied_comments: dict[tuple[int, str], CommentReply] = {}
        self._health_check_result: bool = True

    def create_schema(self) -> None:
        pass

    def record_reply(self, comment_id: int, reply_id: int | None,
                    repository_id: str, pr_number: int) -> None:
        key = (comment_id, repository_id)
        self.replied_comments[key] = CommentReply(
            comment_id=comment_id,
            reply_id=reply_id,
            repository_id=repository_id,
            pr_number=pr_number
        )

    def is_comment_replied(self, comment_id: int, repository_id: str) -> bool:
        return (comment_id, repository_id) in self.replied_comments

    def get_replied_comment_ids(self, repository_id: str, 
                               pr_number: int | None = None) -> set[int]:
        results = set()
        for (comment_id, repo_id), reply in self.replied_comments.items():
            if repo_id == repository_id:
                if pr_number is None or reply.pr_number == pr_number:
                    results.add(comment_id)
        return results

    def health_check(self) -> bool:
        return self._health_check_result

    def set_health_check_result(self, result: bool) -> None:
        self._health_check_result = result
```

### 6.2 Unit Test Specifications

**test_comment_storage.py**:
```python
class TestSQLiteCommentReplyStorage:
    @pytest.fixture
    def temp_db_path(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            yield f.name
        Path(f.name).unlink(missing_ok=True)

    @pytest.fixture
    def storage(self, temp_db_path):
        return SQLiteCommentReplyStorage(temp_db_path)

    def test_create_schema_success(self, storage):
        # Verify tables and indexes created
        conn = storage._get_connection()
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        assert "comment_replies" in tables

    def test_record_reply_success(self, storage):
        storage.record_reply(123, 456, "test/repo", 1)
        assert storage.is_comment_replied(123, "test/repo")

    def test_record_duplicate_reply_upsert(self, storage):
        storage.record_reply(123, 456, "test/repo", 1)
        storage.record_reply(123, 789, "test/repo", 1)  # Update reply_id
        # Should not raise error, should update existing record

    def test_get_replied_comment_ids_filtered_by_pr(self, storage):
        storage.record_reply(123, 456, "test/repo", 1)
        storage.record_reply(124, 457, "test/repo", 2)
        
        pr1_replies = storage.get_replied_comment_ids("test/repo", 1)
        assert pr1_replies == {123}

    def test_repository_isolation(self, storage):
        storage.record_reply(123, 456, "repo1", 1)
        storage.record_reply(123, 457, "repo2", 1)
        
        assert storage.is_comment_replied(123, "repo1")
        assert storage.is_comment_replied(123, "repo2")
        assert storage.get_replied_comment_ids("repo1") == {123}
        assert storage.get_replied_comment_ids("repo2") == {123}
```

### 6.3 Integration Test Specifications

**test_github_comment_integration.py**:
```python
class TestGitHubCommentIntegration:
    @pytest.fixture
    def mock_github_context(self):
        return MockGitHubAPIContext("test/repo")

    @pytest.mark.asyncio
    async def test_post_reply_records_tracking(self, mock_github_context):
        # Mock successful GitHub API response
        with patch('requests.post') as mock_post:
            mock_post.return_value.status_code = 201
            mock_post.return_value.json.return_value = {
                "id": 789,
                "html_url": "https://github.com/test/repo/pull/1#issuecomment-789"
            }
            
            result = await execute_post_pr_reply("test_repo", 123, "Test reply")
            response = json.loads(result)
            
            assert response["success"] is True
            assert response["reply_recorded"] is True

    @pytest.mark.asyncio
    async def test_get_comments_filters_replied(self, mock_github_context):
        # Pre-populate replied comments
        storage = ProductionCommentReplyStorage.create_with_schema("test/repo")
        storage.record_reply(123, 789, "test/repo", 1)
        
        # Mock GitHub API responses
        with patch('requests.get') as mock_get:
            # Setup mock responses for PR details and comments
            result = await execute_get_pr_comments("test_repo", 1)
            response = json.loads(result)
            
            # Verify replied comment 123 is filtered out
            comment_ids = [c["id"] for c in response["review_comments"]]
            assert 123 not in comment_ids
            assert response["replied_comment_count"] == 1
```

## 7. Migration / Deployment & Rollout

### 7.1 Implementation Steps

**Step 1: Create Base Infrastructure**
1. Create `comment_storage.py` with abstract base class
2. Implement `SQLiteCommentReplyStorage` class
3. Add production factory class
4. Create unit tests for storage layer

**Step 2: GitHub Tools Integration**
1. Modify `execute_post_pr_reply` to record successful replies
2. Modify `execute_get_pr_comments` to filter replied comments
3. Add integration tests for modified functions
4. Update response schemas with new fields

**Step 3: Worker Process Integration**
1. Add comment storage initialization to worker startup
2. Inject comment storage into GitHub tools context
3. Test worker process isolation

**Step 4: Testing and Validation**
1. Create mock implementations for testing
2. Add comprehensive unit test coverage
3. Run integration tests against test repositories
4. Performance testing with large comment datasets

**Step 5: Deployment**
1. Deploy to development environment
2. Test with real GitHub repositories
3. Monitor database performance and file creation
4. Production rollout with monitoring

### 7.2 Database Migration

**No Migration Required**: This is a new feature with clean schema creation.

**Database Cleanup** (if needed):
```python
# Utility function for clearing comment tracking
def reset_comment_tracking(repository_id: str) -> None:
    """Reset comment reply tracking for repository."""
    db_path = DATA_DIR / f"comment_replies_{repository_id}.db"
    if db_path.exists():
        db_path.unlink()
    logger.info(f"Cleared comment tracking for repository: {repository_id}")
```

### 7.3 Configuration

**Environment Variables** (optional):
- `GITHUB_AGENT_COMMENT_TRACKING_DISABLED`: Disable feature for testing
- `GITHUB_AGENT_COMMENT_DB_PATH`: Override default database location

**No Breaking Changes**: All modifications are backward compatible with existing tool interfaces.

## Appendix

### A.1 File Locations

**New Files**:
- `/Users/mstriebeck/Code/github-agent/comment_storage.py`
- `/Users/mstriebeck/Code/github-agent/tests/test_comment_storage.py`
- `/Users/mstriebeck/Code/github-agent/tests/mocks/mock_comment_storage.py`
- `/Users/mstriebeck/Code/github-agent/tests/test_github_comment_integration.py`

**Modified Files**:
- `/Users/mstriebeck/Code/github-agent/github_tools.py` (lines 583, 481)

### A.2 Error Handling Specifications

**Custom Exceptions**:
```python
class CommentStorageError(Exception):
    """Base exception for comment storage operations."""
    pass

class CommentTrackingDisabledError(CommentStorageError):
    """Raised when comment tracking is disabled."""
    pass
```

**Error Scenarios**:
- SQLite database corruption: Use retry pattern from symbol storage
- GitHub API failures: Don't record reply if posting fails
- Concurrent access: Use existing threading.Lock pattern
- Invalid comment IDs: Log warning but don't fail operation

### A.3 Performance Considerations

**Expected Load**:
- Comments per PR: 10-100 typical, 1000+ worst case
- Repositories: 10-50 per installation
- Database size: <1MB per repository for typical usage

**Optimization Strategies**:
- Composite indexes for filtering queries
- Connection pooling with existing SQLite patterns
- Batch operations for bulk comment processing

### A.4 Monitoring and Observability

**Logging Additions**:
```python
logger.info(f"Recording reply for comment {comment_id} in {repository_id}")
logger.info(f"Filtered {len(replied_ids)} replied comments from PR {pr_number}")
logger.warning(f"Comment storage health check failed for {repository_id}")
```

**Metrics to Track**:
- Comment reply recording success rate
- Comment filtering performance
- Database health check results
- Storage file sizes per repository