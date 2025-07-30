# Consolidated Design Document

## 1. Introduction

This design document specifies the implementation of PR comment reply persistence for the GitHub Agent codebase. The feature tracks which PR comments have been replied to and filters them from subsequent `github_get_pr_comments` calls to prevent duplicate responses.

The solution extends the existing [`SQLiteSymbolStorage`](file:///Users/mstriebeck/Code/github-agent/symbol_storage.py) architecture pattern to maintain architectural consistency while adding minimal complexity to the established codebase patterns.

## 2. Goals / Non-Goals

### Goals
- **Persistent Reply Tracking**: Store comment IDs that have been replied to in SQLite database
- **Automatic Filtering**: Exclude already-replied comments from `github_get_pr_comments` results  
- **Repository Isolation**: Track comments per repository following existing patterns
- **Backward Compatibility**: No breaking changes to existing GitHub tool interfaces
- **Architectural Consistency**: Follow established `AbstractSymbolStorage` → `SQLiteSymbolStorage` patterns

### Non-Goals
- **Cross-Repository Comment Sharing**: Comments tracked independently per repository
- **Comment Metadata Storage**: Only storing comment IDs, not full comment content or timestamps
- **Real-time Synchronization**: No event-driven updates between processes
- **Complex Reply Queuing**: Simple immediate tracking, no retry mechanisms for tracking failures
- **Multi-User Reply Coordination**: Single-agent reply tracking only

## 3. Proposed Architecture

The architecture extends existing storage patterns by adding comment reply tracking methods to the `AbstractSymbolStorage` interface. This leverages the established dependency injection pattern where `CodebaseTools` receives storage instances via constructor injection.

**Key Architectural Decisions**:
- **Extend Existing Abstractions**: Add methods to `AbstractSymbolStorage` rather than creating separate storage layer
- **Repository-Scoped Databases**: Each repository worker maintains its own comment tracking in existing symbol database
- **Direct Integration**: Modify `execute_post_pr_reply` and `execute_get_pr_comments` functions to call storage methods
- **Consistent Error Handling**: Reuse existing retry patterns and SQLite error handling from `symbol_storage.py`

**Data Flow**:
```
github_post_pr_reply() → Success → symbol_storage.record_comment_reply()
github_get_pr_comments() → symbol_storage.get_replied_comment_ids() → filter comments → return filtered list
```

## 4. Detailed Design

### 4.1 Extended Abstract Base Class

**File**: [`symbol_storage.py`](file:///Users/mstriebeck/Code/github-agent/symbol_storage.py#L64)

```python
class AbstractSymbolStorage(ABC):
    # ... existing methods ...

    @abstractmethod
    def record_comment_reply(self, comment_id: int, pr_number: int, repository_id: str) -> None:
        """Record that a comment has been replied to."""
        pass

    @abstractmethod
    def get_replied_comment_ids(self, pr_number: int, repository_id: str) -> set[int]:
        """Get comment IDs that have been replied to for a specific PR."""
        pass

    @abstractmethod
    def is_comment_replied(self, comment_id: int, repository_id: str) -> bool:
        """Check if a specific comment has been replied to."""
        pass
```

### 4.2 SQLite Implementation Extension

**File**: [`symbol_storage.py`](file:///Users/mstriebeck/Code/github-agent/symbol_storage.py#L250)

**Schema Extension**:
```sql
CREATE TABLE IF NOT EXISTS comment_replies (
    comment_id INTEGER NOT NULL,
    pr_number INTEGER NOT NULL,
    repository_id TEXT NOT NULL,
    replied_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (comment_id, repository_id),
    FOREIGN KEY (repository_id) REFERENCES repositories(id)
);

CREATE INDEX IF NOT EXISTS idx_comment_replies_pr 
ON comment_replies(repository_id, pr_number);
```

**Implementation Methods**:
```python
class SQLiteSymbolStorage(AbstractSymbolStorage):
    # ... existing implementation ...

    def record_comment_reply(self, comment_id: int, pr_number: int, repository_id: str) -> None:
        """Record that a comment has been replied to."""
        query = """
        INSERT OR REPLACE INTO comment_replies 
        (comment_id, pr_number, repository_id, replied_at)
        VALUES (?, ?, ?, datetime('now'))
        """
        self._execute_with_retry(query, (comment_id, pr_number, repository_id))
        logger.info(f"Recorded reply to comment {comment_id} in PR {pr_number} for repo {repository_id}")

    def get_replied_comment_ids(self, pr_number: int, repository_id: str) -> set[int]:
        """Get comment IDs that have been replied to for a specific PR."""
        query = """
        SELECT comment_id FROM comment_replies 
        WHERE pr_number = ? AND repository_id = ?
        """
        with self._get_connection() as conn:
            cursor = conn.execute(query, (pr_number, repository_id))
            return {row[0] for row in cursor.fetchall()}

    def is_comment_replied(self, comment_id: int, repository_id: str) -> bool:
        """Check if a specific comment has been replied to."""
        query = """
        SELECT 1 FROM comment_replies 
        WHERE comment_id = ? AND repository_id = ? LIMIT 1
        """
        with self._get_connection() as conn:
            cursor = conn.execute(query, (comment_id, repository_id))
            return cursor.fetchone() is not None
```

### 4.3 GitHub Tools Integration

**File**: [`github_tools.py`](file:///Users/mstriebeck/Code/github-agent/github_tools.py)

**Modified Function Signatures**:
```python
async def execute_post_pr_reply(
    repo_name: str, 
    comment_id: int, 
    message: str,
    symbol_storage: AbstractSymbolStorage = None
) -> str:
    """Reply to a PR comment and record the reply."""
    # ... existing implementation until successful reply ...
    
    if reply_resp.status_code in [200, 201]:
        # Record successful reply
        if symbol_storage:
            try:
                symbol_storage.record_comment_reply(comment_id, pr_number, context.repo_name)
            except Exception as e:
                logger.warning(f"Failed to record comment reply tracking: {e}")
        
        return json.dumps({
            "success": True,
            "method": "direct_reply",
            "repo": context.repo_name,
            "comment_id": reply_resp.json()["id"],
            "url": reply_resp.json()["html_url"],
            "reply_tracked": symbol_storage is not None
        })

async def execute_get_pr_comments(
    repo_name: str, 
    pr_number: int,
    symbol_storage: AbstractSymbolStorage = None
) -> str:
    """Get PR comments, excluding already-replied comments."""
    # ... existing implementation until comment collection ...
    
    # Filter out replied comments
    if symbol_storage:
        try:
            replied_ids = symbol_storage.get_replied_comment_ids(pr_number, context.repo_name)
            review_comments = [c for c in review_comments if c["id"] not in replied_ids]
            issue_comments = [c for c in issue_comments if c["id"] not in replied_ids]
            logger.info(f"Filtered out {len(replied_ids)} already-replied comments")
        except Exception as e:
            logger.warning(f"Failed to filter replied comments: {e}")
    
    # ... rest of existing implementation ...
```

### 4.4 Worker Process Integration

**File**: [`mcp_worker.py`](file:///Users/mstriebeck/Code/github-agent/mcp_worker.py)

**Modified Tool Handler Registration**:
```python
# Add symbol_storage parameter to GitHub tool handlers
TOOL_HANDLERS = {
    "github_get_pr_comments": lambda repo_name, pr_number: 
        execute_get_pr_comments(repo_name, pr_number, worker_symbol_storage),
    "github_post_pr_reply": lambda repo_name, comment_id, message:
        execute_post_pr_reply(repo_name, comment_id, message, worker_symbol_storage),
    # ... existing handlers ...
}
```

### 4.5 Error Handling and Resilience

**Exception Handling Pattern**:
```python
def record_comment_reply(self, comment_id: int, pr_number: int, repository_id: str) -> None:
    """Record comment reply with comprehensive error handling."""
    try:
        query = """INSERT OR REPLACE INTO comment_replies ..."""
        self._execute_with_retry(query, (comment_id, pr_number, repository_id))
    except sqlite3.DatabaseError as e:
        logger.error(f"Database error recording comment reply: {e}")
        raise
    except sqlite3.Error as e:
        logger.error(f"SQLite error recording comment reply: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error recording comment reply: {e}")
        raise
```

**Graceful Degradation**:
- If comment tracking fails, GitHub operations continue normally
- Warning logs indicate tracking failures without breaking functionality
- Reply filtering skipped if storage unavailable

## 5. Alternatives Considered

### 5.1 Separate Comment Storage Service
**Considered**: Creating `AbstractCommentStorage` with `SQLiteCommentStorage` implementation
**Rejected**: Violates existing dependency injection patterns and adds unnecessary abstraction layers for simple feature

### 5.2 JSON File Storage
**Considered**: Using JSON files for comment tracking similar to repository configuration
**Rejected**: Inconsistent with existing SQLite patterns and lacks query performance for filtering operations

### 5.3 External Database
**Considered**: PostgreSQL or shared database for comment tracking
**Rejected**: Violates existing repository isolation architecture and adds operational complexity

### 5.4 Event-Driven Architecture
**Considered**: Decorator pattern with `@track_comment_replies` for loose coupling
**Rejected**: Over-engineering for simple requirement; direct integration sufficient for current needs

## 6. Testing / Validation

### 6.1 Mock Extension

**File**: [`tests/mocks/mock_symbol_storage.py`](file:///Users/mstriebeck/Code/github-agent/tests/mocks/mock_symbol_storage.py)

```python
class MockSymbolStorage(AbstractSymbolStorage):
    def __init__(self):
        # ... existing initialization ...
        self.replied_comments: dict[tuple[int, str], set[int]] = {}  # (pr_number, repo_id) -> comment_ids

    def record_comment_reply(self, comment_id: int, pr_number: int, repository_id: str) -> None:
        key = (pr_number, repository_id)
        if key not in self.replied_comments:
            self.replied_comments[key] = set()
        self.replied_comments[key].add(comment_id)

    def get_replied_comment_ids(self, pr_number: int, repository_id: str) -> set[int]:
        return self.replied_comments.get((pr_number, repository_id), set())

    def is_comment_replied(self, comment_id: int, repository_id: str) -> bool:
        for (pr_num, repo_id), comment_ids in self.replied_comments.items():
            if repo_id == repository_id and comment_id in comment_ids:
                return True
        return False
```

### 6.2 Unit Test Specifications

**File**: [`tests/test_symbol_storage.py`](file:///Users/mstriebeck/Code/github-agent/tests/test_symbol_storage.py)

```python
def test_record_comment_reply_success():
    """Test successful comment reply recording."""
    storage = SQLiteSymbolStorage(":memory:")
    storage.create_schema()
    
    storage.record_comment_reply(123, 456, "test-repo")
    assert storage.is_comment_replied(123, "test-repo")

def test_get_replied_comment_ids_filters_by_pr():
    """Test comment ID retrieval filtered by PR number."""
    storage = SQLiteSymbolStorage(":memory:")
    storage.create_schema()
    
    storage.record_comment_reply(123, 456, "test-repo")
    storage.record_comment_reply(789, 999, "test-repo")
    
    replied_ids = storage.get_replied_comment_ids(456, "test-repo")
    assert replied_ids == {123}

def test_comment_reply_repository_isolation():
    """Test comment replies are isolated by repository."""
    storage = SQLiteSymbolStorage(":memory:")
    storage.create_schema()
    
    storage.record_comment_reply(123, 456, "repo-a")
    storage.record_comment_reply(123, 456, "repo-b")
    
    assert storage.is_comment_replied(123, "repo-a")
    assert storage.is_comment_replied(123, "repo-b")
    assert storage.get_replied_comment_ids(456, "repo-a") == {123}
    assert storage.get_replied_comment_ids(456, "repo-b") == {123}
```

### 6.3 Integration Test Specifications

**File**: [`tests/test_github_tools_integration.py`](file:///Users/mstriebeck/Code/github-agent/tests/test_github_tools_integration.py)

```python
@pytest.mark.asyncio
async def test_post_reply_records_comment_tracking():
    """Test that posting a reply records comment tracking."""
    mock_storage = MockSymbolStorage()
    
    # Mock successful GitHub API response
    with patch('requests.post') as mock_post:
        mock_post.return_value.status_code = 201
        mock_post.return_value.json.return_value = {"id": 999, "html_url": "test-url"}
        
        result = await execute_post_pr_reply("test-repo", 123, "test message", mock_storage)
        
    assert '"reply_tracked": true' in result
    assert mock_storage.is_comment_replied(123, "test-repo")

@pytest.mark.asyncio 
async def test_get_comments_filters_replied():
    """Test that getting comments filters out replied ones."""
    mock_storage = MockSymbolStorage()
    mock_storage.record_comment_reply(123, 456, "test-repo")
    
    # Mock GitHub API responses
    with patch('requests.get') as mock_get:
        # Setup mock responses for PR details and comments
        mock_get.side_effect = [
            Mock(status_code=200, json=lambda: {"review_comments_url": "test-url", "number": 456}),
            Mock(status_code=200, json=lambda: [{"id": 123, "body": "replied"}, {"id": 789, "body": "new"}])
        ]
        
        result = await execute_get_pr_comments("test-repo", 456, mock_storage)
        
    # Should only include unreplied comment (789)
    result_data = json.loads(result)
    comment_ids = [c["id"] for c in result_data["review_comments"]]
    assert 123 not in comment_ids
    assert 789 in comment_ids
```

## 7. Migration / Deployment & Rollout

### 7.1 Database Schema Migration

**Migration Script** (added to [`SQLiteSymbolStorage.create_schema()`](file:///Users/mstriebeck/Code/github-agent/symbol_storage.py#L250)):
```python
def create_schema(self) -> None:
    """Create database schema including comment reply tracking."""
    # ... existing schema creation ...
    
    # Add comment reply tracking table
    self._execute_with_retry("""
        CREATE TABLE IF NOT EXISTS comment_replies (
            comment_id INTEGER NOT NULL,
            pr_number INTEGER NOT NULL,
            repository_id TEXT NOT NULL,
            replied_at TEXT NOT NULL DEFAULT (datetime('now')),
            PRIMARY KEY (comment_id, repository_id)
        )
    """, ())
    
    self._execute_with_retry("""
        CREATE INDEX IF NOT EXISTS idx_comment_replies_pr 
        ON comment_replies(repository_id, pr_number)
    """, ())
```

### 7.2 Deployment Steps

1. **Phase 1: Schema Update**
   - Deploy updated `symbol_storage.py` with new methods
   - Existing databases automatically get new tables on startup
   - No data migration needed (clean start)

2. **Phase 2: Tool Integration**  
   - Deploy updated `github_tools.py` with tracking calls
   - Deploy updated `mcp_worker.py` with parameter passing
   - Backward compatible - tools work without storage parameter

3. **Phase 3: Validation**
   - Monitor logs for comment tracking success/failure rates
   - Verify database table creation in existing repositories
   - Test comment filtering in development environment

### 7.3 Rollback Plan

**Immediate Rollback**: 
- Remove `symbol_storage` parameters from tool handler registration
- Comment tracking gracefully degrades to no-op
- No data corruption risk

**Full Rollback**:
- Revert GitHub tools functions to original implementations
- `comment_replies` table remains harmless in database
- No impact on existing symbol storage functionality

## Appendix

### Conflict Resolutions

**Abstraction Level Conflict**: Resolved by extending existing `AbstractSymbolStorage` rather than creating new abstractions, balancing consistency with simplicity.

**Integration Approach Conflict**: Resolved by direct integration with graceful degradation, prioritizing immediate functionality over loose coupling for this simple feature.

**Testing Scope Conflict**: Resolved by extending existing test files rather than creating comprehensive separate test suite, matching codebase's lean testing approach.

**Development Methodology Conflict**: Resolved by implementation-first approach with immediate test coverage, leveraging existing testing infrastructure.

### Implementation Checklist

- [ ] Extend `AbstractSymbolStorage` with comment methods
- [ ] Implement methods in `SQLiteSymbolStorage` 
- [ ] Add schema migration to `create_schema()`
- [ ] Modify `execute_post_pr_reply` function
- [ ] Modify `execute_get_pr_comments` function  
- [ ] Update worker tool handler registration
- [ ] Extend `MockSymbolStorage` for testing
- [ ] Add unit tests to existing test file
- [ ] Add integration tests for GitHub workflow
- [ ] Update documentation and logging

### Performance Considerations

**Query Performance**: Composite index on `(repository_id, pr_number)` supports efficient filtering
**Storage Overhead**: Minimal - 24 bytes per replied comment
**Memory Impact**: Comment ID sets cached in memory during filtering operations
**Concurrency**: SQLite WAL mode handles concurrent reads during comment filtering