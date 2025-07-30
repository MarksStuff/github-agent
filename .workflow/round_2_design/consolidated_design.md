# Consolidated Design Document

## 1. Introduction

This design document specifies the implementation of PR comment reply persistence for the GitHub Agent codebase. The feature tracks which GitHub PR comments have been replied to, enabling subsequent `github_get_pr_comments` calls to filter out already-replied comments. This prevents duplicate responses and improves workflow efficiency.

The design maintains architectural consistency with existing patterns in [`symbol_storage.py`](file:///Users/mstriebeck/Code/github-agent/symbol_storage.py) and [`github_tools.py`](file:///Users/mstriebeck/Code/github-agent/github_tools.py), following the established multi-worker, repository-isolated architecture.

## 2. Goals / Non-Goals

### Goals
- **Primary**: Track comment reply relationships to prevent duplicate responses
- **Secondary**: Filter replied comments from `github_get_pr_comments` results automatically
- **Tertiary**: Maintain repository isolation following existing worker process patterns
- **Quality**: Achieve 100% test coverage following existing TDD patterns
- **Compatibility**: Zero breaking changes to existing GitHub tool APIs

### Non-Goals
- **Comment Content Analysis**: Not analyzing reply quality or content matching
- **Cross-Repository Tracking**: Comments tracked per repository only, no global tracking
- **Historical Migration**: No backfilling of existing comment/reply relationships
- **Real-time Notifications**: Not implementing webhooks or real-time updates
- **Comment Thread Modeling**: Not tracking complex reply hierarchies or conversations

## 3. Proposed Architecture

The architecture extends the existing worker-based, repository-isolated pattern with a new `CommentReplyStorage` component that mirrors [`SQLiteSymbolStorage`](file:///Users/mstriebeck/Code/github-agent/symbol_storage.py#L124) patterns.

**Key Components:**
- **`AbstractCommentReplyStorage`**: Abstract base class following [`AbstractSymbolStorage`](file:///Users/mstriebeck/Code/github-agent/symbol_storage.py#L64) pattern
- **`SQLiteCommentReplyStorage`**: Concrete implementation with repository-scoped databases
- **Modified GitHub Tools**: Extended [`execute_post_pr_reply`](file:///Users/mstriebeck/Code/github-agent/github_tools.py#L539) and `execute_get_pr_comments` functions
- **Worker Integration**: Storage initialization in [`mcp_worker.py`](file:///Users/mstriebeck/Code/github-agent/mcp_worker.py) alongside symbol storage

**Data Flow:**
```
github_post_pr_reply() → Success → storage.record_reply(comment_id, reply_id, repo_id)
github_get_pr_comments() → storage.get_replied_comment_ids() → filter results
```

**Repository Isolation:**
Each repository worker maintains its own `comments_{repo_name}.db` file in [`DATA_DIR`](file:///Users/mstriebeck/Code/github-agent/constants.py), ensuring complete isolation between repositories.

## 4. Detailed Design

### 4.1 Core Data Model

```python
@dataclass
class CommentReply:
    """Represents a tracked reply to a GitHub comment."""
    comment_id: int
    reply_id: int
    repository_id: str
    pr_number: int
    reply_timestamp: str
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "comment_id": self.comment_id,
            "reply_id": self.reply_id,
            "repository_id": self.repository_id,
            "pr_number": self.pr_number,
            "reply_timestamp": self.reply_timestamp,
        }
```

### 4.2 Abstract Base Class

```python
class AbstractCommentReplyStorage(ABC):
    """Abstract base class for comment reply storage operations."""
    
    @abstractmethod
    def create_schema(self) -> None:
        """Create the database schema for comment reply storage."""
        pass
    
    @abstractmethod
    def record_reply(self, comment_reply: CommentReply) -> None:
        """Record a successful reply to a comment."""
        pass
    
    @abstractmethod
    def get_replied_comment_ids(self, repository_id: str, pr_number: int) -> set[int]:
        """Get set of comment IDs that have been replied to."""
        pass
    
    @abstractmethod
    def is_comment_replied(self, comment_id: int, repository_id: str) -> bool:
        """Check if a specific comment has been replied to."""
        pass
    
    @abstractmethod
    def health_check(self) -> bool:
        """Check storage health status."""
        pass
```

### 4.3 SQLite Implementation

```python
class SQLiteCommentReplyStorage(AbstractCommentReplyStorage):
    """SQLite implementation of comment reply storage."""
    
    def __init__(self, db_path: str | Path, max_retries: int = 3, retry_delay: float = 0.1):
        self.db_path = Path(db_path)
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._lock = threading.Lock()
    
    def create_schema(self) -> None:
        """Create comment reply tracking table with indexes."""
        schema_sql = """
        CREATE TABLE IF NOT EXISTS comment_replies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            comment_id INTEGER NOT NULL,
            reply_id INTEGER NOT NULL,
            repository_id TEXT NOT NULL,
            pr_number INTEGER NOT NULL,
            reply_timestamp TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(comment_id, repository_id)
        );
        
        CREATE INDEX IF NOT EXISTS idx_comment_replies_repo_pr 
        ON comment_replies(repository_id, pr_number);
        
        CREATE INDEX IF NOT EXISTS idx_comment_replies_comment 
        ON comment_replies(comment_id, repository_id);
        """
        self._execute_with_retry(schema_sql)
    
    def record_reply(self, comment_reply: CommentReply) -> None:
        """Record a successful reply, using REPLACE to handle duplicates."""
        sql = """
        REPLACE INTO comment_replies 
        (comment_id, reply_id, repository_id, pr_number, reply_timestamp)
        VALUES (?, ?, ?, ?, ?)
        """
        params = (
            comment_reply.comment_id,
            comment_reply.reply_id,
            comment_reply.repository_id,
            comment_reply.pr_number,
            comment_reply.reply_timestamp,
        )
        self._execute_with_retry(sql, params)
    
    def get_replied_comment_ids(self, repository_id: str, pr_number: int) -> set[int]:
        """Get all replied comment IDs for a specific PR."""
        sql = """
        SELECT DISTINCT comment_id FROM comment_replies 
        WHERE repository_id = ? AND pr_number = ?
        """
        rows = self._execute_with_retry(sql, (repository_id, pr_number), fetch=True)
        return {row[0] for row in rows}
    
    def _execute_with_retry(self, sql: str, params: tuple = (), fetch: bool = False) -> Any:
        """Execute SQL with retry logic following symbol_storage pattern."""
        # Implementation mirrors SQLiteSymbolStorage._execute_with_retry()
        pass
```

### 4.4 Database Schema Details

**Primary Table:**
```sql
CREATE TABLE comment_replies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    comment_id INTEGER NOT NULL,
    reply_id INTEGER NOT NULL,
    repository_id TEXT NOT NULL,
    pr_number INTEGER NOT NULL,
    reply_timestamp TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(comment_id, repository_id)
);
```

**Performance Indexes:**
```sql
-- For filtering comments by repository and PR
CREATE INDEX idx_comment_replies_repo_pr ON comment_replies(repository_id, pr_number);

-- For checking individual comment reply status
CREATE INDEX idx_comment_replies_comment ON comment_replies(comment_id, repository_id);
```

### 4.5 GitHub Tools Integration

**Modified `execute_post_pr_reply` function:**
```python
async def execute_post_pr_reply(repo_name: str, comment_id: int, message: str) -> str:
    """Reply to a PR comment and track the reply."""
    try:
        context = get_github_context(repo_name)
        # ... existing reply logic ...
        
        if reply_resp.status_code in [200, 201]:
            # NEW: Record successful reply
            try:
                comment_storage = get_comment_storage(repo_name)
                reply_data = CommentReply(
                    comment_id=comment_id,
                    reply_id=reply_resp.json()["id"],
                    repository_id=context.repo_name,
                    pr_number=pr_number,
                    reply_timestamp=datetime.utcnow().isoformat(),
                )
                comment_storage.record_reply(reply_data)
            except Exception as storage_error:
                logger.warning(f"Failed to track reply for comment {comment_id}: {storage_error}")
                # Continue - don't fail the reply if tracking fails
            
            return json.dumps({
                "success": True,
                "method": "direct_reply",
                "repo": context.repo_name,
                "comment_id": reply_resp.json()["id"],
                "replied_to_comment_id": comment_id,  # NEW
                "url": reply_resp.json()["html_url"],
            })
    except Exception as e:
        return json.dumps({"error": f"Failed to post PR reply: {e!s}"})
```

**Modified `execute_get_pr_comments` function:**
```python
async def execute_get_pr_comments(repo_name: str, pr_number: int | None = None) -> str:
    """Get PR comments, filtering out already-replied comments."""
    try:
        context = get_github_context(repo_name)
        # ... existing comment retrieval logic ...
        
        # NEW: Filter out replied comments
        try:
            comment_storage = get_comment_storage(repo_name)
            replied_comment_ids = comment_storage.get_replied_comment_ids(
                context.repo_name, pr_number
            )
            
            # Filter both review and issue comments
            filtered_review_comments = [
                comment for comment in review_comments
                if comment["id"] not in replied_comment_ids
            ]
            filtered_issue_comments = [
                comment for comment in issue_comments
                if comment["id"] not in replied_comment_ids
            ]
            
            return json.dumps({
                "pr_number": pr_number,
                "review_comments": filtered_review_comments,
                "issue_comments": filtered_issue_comments,
                "total_comments": len(filtered_review_comments) + len(filtered_issue_comments),
                "filtered_count": len(replied_comment_ids),  # NEW
            })
        except Exception as storage_error:
            logger.warning(f"Failed to filter replied comments: {storage_error}")
            # Fall back to unfiltered results
            return json.dumps({
                "pr_number": pr_number,
                "review_comments": review_comments,
                "issue_comments": issue_comments,
                "total_comments": len(review_comments) + len(issue_comments),
                "filtered_count": 0,
            })
    except Exception as e:
        return json.dumps({"error": f"Failed to get PR comments: {e!s}"})
```

### 4.6 Worker Integration

**Storage Factory Function:**
```python
def get_comment_storage(repo_name: str) -> AbstractCommentReplyStorage:
    """Get comment reply storage for a repository."""
    global _comment_storage_cache
    
    if repo_name not in _comment_storage_cache:
        db_path = DATA_DIR / f"comments_{repo_name}.db"
        storage = SQLiteCommentReplyStorage(db_path)
        storage.create_schema()
        _comment_storage_cache[repo_name] = storage
    
    return _comment_storage_cache[repo_name]

# Global cache for storage instances (per worker process)
_comment_storage_cache: dict[str, AbstractCommentReplyStorage] = {}
```

## 5. Alternatives Considered

### 5.1 JSON File Storage vs SQLite Database
**Alternative**: Use JSON files for persistence like configuration files
**Decision**: SQLite chosen for consistency with [`symbol_storage.py`](file:///Users/mstriebeck/Code/github-agent/symbol_storage.py) and better query performance
**Reasoning**: JSON files lack indexing and atomic operations needed for filtering operations

### 5.2 Single Global Database vs Repository-Scoped Databases  
**Alternative**: One database for all repositories
**Decision**: Repository-scoped databases following existing pattern
**Reasoning**: Maintains worker process isolation and prevents cross-repository data contamination

### 5.3 Decorator Pattern vs Direct Function Modification
**Alternative**: Use `@track_replies` and `@filter_replied` decorators
**Decision**: Direct function modification for simplicity
**Reasoning**: Less complexity, easier debugging, and consistent with existing function structure

### 5.4 Rich Domain Objects vs Simple Data Classes
**Alternative**: Complex `GitHubComment` and `Reply` domain objects
**Decision**: Simple `CommentReply` dataclass following [`Symbol`](file:///Users/mstriebeck/Code/github-agent/symbol_storage.py#L39) pattern
**Reasoning**: Matches existing codebase patterns and sufficient for requirements

### 5.5 Abstract Base Class vs Concrete Implementation Only
**Alternative**: Skip abstraction and implement SQLite storage directly
**Decision**: Abstract base class for testability and consistency
**Reasoning**: Enables mock testing following [`AbstractSymbolStorage`](file:///Users/mstriebeck/Code/github-agent/symbol_storage.py#L64) pattern

## 6. Testing / Validation

### 6.1 Unit Test Classes

**Storage Tests (`tests/test_comment_reply_storage.py`):**
```python
class TestSQLiteCommentReplyStorage:
    def test_create_schema_success(self, temp_db_path):
        storage = SQLiteCommentReplyStorage(temp_db_path)
        storage.create_schema()
        # Verify tables and indexes exist
    
    def test_record_reply_success(self, storage_with_schema):
        reply = CommentReply(123, 456, "repo1", 10, "2024-01-01T00:00:00Z")
        storage_with_schema.record_reply(reply)
        assert storage_with_schema.is_comment_replied(123, "repo1")
    
    def test_get_replied_comment_ids_multiple(self, storage_with_data):
        ids = storage_with_data.get_replied_comment_ids("repo1", 10)
        assert ids == {123, 124, 125}
    
    def test_repository_isolation(self, storage_with_schema):
        # Record reply for repo1
        reply1 = CommentReply(123, 456, "repo1", 10, "2024-01-01T00:00:00Z")
        storage_with_schema.record_reply(reply1)
        
        # Verify repo2 doesn't see repo1's data
        assert not storage_with_schema.is_comment_replied(123, "repo2")
```

**Integration Tests (`tests/test_pr_comment_workflow.py`):**
```python
class TestPRCommentWorkflow:
    @pytest.mark.asyncio
    async def test_post_reply_records_tracking(self, mock_github_api):
        result = await execute_post_pr_reply("test-repo", 123, "Test reply")
        data = json.loads(result)
        
        assert data["success"] is True
        assert data["replied_to_comment_id"] == 123
        
        # Verify tracking was recorded
        storage = get_comment_storage("test-repo")
        assert storage.is_comment_replied(123, "test-repo")
    
    @pytest.mark.asyncio  
    async def test_get_comments_filters_replied(self, mock_github_api, replied_comments):
        result = await execute_get_pr_comments("test-repo", 10)
        data = json.loads(result)
        
        # Verify replied comments are filtered out
        comment_ids = {c["id"] for c in data["review_comments"]}
        assert 123 not in comment_ids  # This comment was replied to
        assert 124 in comment_ids     # This comment was not replied to
        assert data["filtered_count"] > 0
```

### 6.2 Mock Implementations

**Mock Storage (`tests/mocks/mock_comment_reply_storage.py`):**
```python
class MockCommentReplyStorage(AbstractCommentReplyStorage):
    def __init__(self):
        self.replies: list[CommentReply] = []
        self._health_status = True
    
    def record_reply(self, comment_reply: CommentReply) -> None:
        # Remove existing reply for same comment (simulate REPLACE)
        self.replies = [r for r in self.replies if r.comment_id != comment_reply.comment_id]
        self.replies.append(comment_reply)
    
    def get_replied_comment_ids(self, repository_id: str, pr_number: int) -> set[int]:
        return {
            r.comment_id for r in self.replies 
            if r.repository_id == repository_id and r.pr_number == pr_number
        }
    
    def is_comment_replied(self, comment_id: int, repository_id: str) -> bool:
        return any(
            r.comment_id == comment_id and r.repository_id == repository_id 
            for r in self.replies
        )
    
    def health_check(self) -> bool:
        return self._health_status
```

### 6.3 Test Fixtures

```python
@pytest.fixture
def temp_db_path():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        yield f.name
    Path(f.name).unlink(missing_ok=True)

@pytest.fixture
def storage_with_schema(temp_db_path):
    storage = SQLiteCommentReplyStorage(temp_db_path)
    storage.create_schema()
    return storage

@pytest.fixture
def sample_comment_replies():
    return [
        CommentReply(123, 456, "repo1", 10, "2024-01-01T00:00:00Z"),
        CommentReply(124, 457, "repo1", 10, "2024-01-01T01:00:00Z"),
        CommentReply(125, 458, "repo2", 20, "2024-01-01T02:00:00Z"),
    ]
```

### 6.4 Coverage Requirements

- **Line Coverage**: 100% for all new classes and functions
- **Branch Coverage**: 100% for error handling and filtering logic  
- **Integration Coverage**: All GitHub tool workflows with and without storage
- **Error Path Coverage**: Database failures, GitHub API failures, storage unavailable

## 7. Migration / Deployment & Rollout

### 7.1 Implementation Sequence

**Phase 1: Core Storage (Week 1)**
1. Create `comment_storage.py` with abstract base class
2. Implement `SQLiteCommentReplyStorage` 
3. Add unit tests for storage operations
4. Create mock implementations for testing

**Phase 2: GitHub Tools Integration (Week 1)**  
5. Modify `execute_post_pr_reply` to record replies
6. Modify `execute_get_pr_comments` to filter results
7. Add `get_comment_storage()` factory function
8. Add integration tests

**Phase 3: Worker Integration (Week 2)**
9. Add storage initialization to worker startup
10. Add error handling and graceful degradation
11. Add performance monitoring and logging
12. Complete end-to-end testing

### 7.2 Deployment Steps

**Step 1: Create New Files**
- Add `comment_storage.py` to repository root
- Add test files to `tests/` directory
- Add mock implementations to `tests/mocks/`

**Step 2: Modify Existing Files**
- Update [`github_tools.py`](file:///Users/mstriebeck/Code/github-agent/github_tools.py) with tracking calls
- Update worker initialization (implementation-specific)
- Update imports and dependencies

**Step 3: Database Creation**
- Databases auto-created on first worker startup
- No migration needed (fresh feature)
- Storage files created in existing [`DATA_DIR`](file:///Users/mstriebeck/Code/github-agent/constants.py)

### 7.3 Rollback Plan

**Immediate Rollback**: Remove tracking calls from GitHub tools
**Database Cleanup**: Delete `comments_*.db` files if needed
**Code Rollback**: Remove new files and revert modifications
**Zero Data Loss**: No existing data affected (new feature only)

### 7.4 Monitoring and Observability

**Key Metrics:**
- Storage operation success/failure rates
- Comment filtering effectiveness (comments filtered per request)
- Database file sizes and growth rates
- Query performance times

**Logging Additions:**
```python
logger.info(f"Recorded reply for comment {comment_id} in repo {repo_name}")
logger.info(f"Filtered {len(replied_ids)} replied comments from PR {pr_number}")
logger.warning(f"Comment storage failed: {error} - continuing without tracking")
```

## Appendix

### Conflict Resolutions

**1. Abstraction Level Conflict**
- **Developer Analysis**: Full `AbstractCommentStorage` pattern
- **Senior Engineer Review**: Simple `ReplyTracker` service  
- **Resolution**: Use abstract base class for testability but keep interface minimal (5 methods max)

**2. Integration Strategy Conflict**
- **Developer Analysis**: Direct function modification
- **Senior Engineer Review**: Decorator pattern approach
- **Resolution**: Direct modification for Phase 1, decorator refactoring in Phase 2 if needed

**3. Error Handling Philosophy Conflict**  
- **Architect Review**: JSON error returns (blocking)
- **Senior Engineer Review**: Non-blocking with compensation
- **Resolution**: Non-blocking tracking with graceful degradation, JSON structure maintained

**4. Code Reuse Strategy Conflict**
- **Developer/Senior Engineer Analysis**: Copy SQLite patterns
- **Senior Engineer Review**: Extract shared utilities
- **Resolution**: Copy patterns for Phase 1, extract utilities in Phase 2 if duplication becomes significant

### Database Size Estimates

**Typical Usage**: 10-50 comments per PR, 1-10 PRs per day per repository
**Storage per Reply**: ~100 bytes (integers, short strings, timestamp)
**Annual Storage**: <10MB per active repository
**Query Performance**: <1ms for typical filtering operations with indexes

### Future Enhancement Hooks

**Reply Metadata**: Schema supports additional columns without migration
**Comment Types**: Extensible to different GitHub comment types
**Audit Trail**: Timestamp and user tracking already in place
**Batch Operations**: Abstract interface supports bulk operations
**Health Monitoring**: Health check method enables monitoring integration