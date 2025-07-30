# Consolidated Design Document

## 1. Introduction

This design document outlines the implementation of GitHub PR comment reply tracking for the github-agent codebase. The feature ensures that when the `github_post_pr_reply` tool is used, we persist which comments we replied to and filter subsequent `github_get_pr_comments` calls to exclude already-replied comments.

The solution integrates with the existing [`github_tools.py`](file:///Users/mstriebeck/Code/github-agent/github_tools.py) architecture while maintaining consistency with established patterns from [`symbol_storage.py`](file:///Users/mstriebeck/Code/github-agent/symbol_storage.py) and the master-worker process isolation model.

## 2. Goals / Non-Goals

### Goals
- **Persistent tracking**: Store which PR comments have received replies across agent restarts
- **Automatic filtering**: Exclude already-replied comments from `github_get_pr_comments` results
- **Repository isolation**: Each repository worker maintains separate comment tracking state
- **Performance**: Sub-100ms comment filtering for PR comment lists up to 1000 comments
- **Backward compatibility**: No breaking changes to existing GitHub tool APIs
- **Architectural consistency**: Follow existing [`SQLiteSymbolStorage`](file:///Users/mstriebeck/Code/github-agent/symbol_storage.py#L124) patterns

### Non-Goals
- **Cross-repository comment tracking**: Comments are scoped to individual repositories
- **Historical comment analysis**: Only tracks replies made by this agent instance
- **Real-time comment synchronization**: No webhook or polling for external comment updates
- **Comment content storage**: Only stores comment IDs and reply timestamps
- **Multi-agent coordination**: No distributed locking or state sharing between agent instances

## 3. Proposed Architecture

The architecture implements a **phased storage approach** with **repository-scoped tracking**:

**Phase 1 (Week 1)**: `FileCommentTracker` using JSON persistence for rapid prototyping and validation
**Phase 2 (Week 3)**: `SQLiteCommentTracker` using database storage for production scale and consistency

Both implementations follow the **Abstract Factory pattern** established by [`AbstractSymbolStorage`](file:///Users/mstriebeck/Code/github-agent/symbol_storage.py#L64), enabling seamless migration between storage backends.

**Integration points**:
- [`github_tools.py`](file:///Users/mstriebeck/Code/github-agent/github_tools.py#L2030): Modify `execute_post_pr_reply` to record replies
- [`github_tools.py`](file:///Users/mstriebeck/Code/github-agent/github_tools.py#L2029): Modify `execute_get_pr_comments` to filter replied comments
- [`mcp_worker.py`](file:///Users/mstriebeck/Code/github-agent/mcp_worker.py#L254): Initialize comment tracker alongside symbol storage

## 4. Detailed Design

### 4.1 Abstract Base Class

```python
# File: comment_tracker.py
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Set, List
from dataclasses import dataclass

@dataclass
class CommentReply:
    comment_id: str
    pr_number: int
    replied_at: datetime
    repository_name: str

class AbstractCommentTracker(ABC):
    """Abstract interface for tracking PR comment replies."""
    
    @abstractmethod
    async def mark_comment_replied(self, comment_id: str, pr_number: int, repository_name: str) -> None:
        """Mark a comment as replied to with current timestamp."""
        pass
    
    @abstractmethod
    async def get_replied_comment_ids(self, pr_number: int, repository_name: str) -> Set[str]:
        """Get set of comment IDs that have been replied to for a specific PR."""
        pass
    
    @abstractmethod
    async def has_replied_to_comment(self, comment_id: str) -> bool:
        """Check if a specific comment has been replied to."""
        pass
    
    @abstractmethod
    async def get_reply_history(self, repository_name: str, since: datetime = None) -> List[CommentReply]:
        """Get reply history for a repository, optionally since a date."""
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """Verify the comment tracker is accessible and functional."""
        pass
```

### 4.2 File-Based Implementation (Phase 1)

```python
# File: comment_tracker.py (continued)
import json
import aiofiles
from pathlib import Path

class FileCommentTracker(AbstractCommentTracker):
    """JSON file-based comment tracking for rapid prototyping."""
    
    def __init__(self, storage_path: str | Path, max_retries: int = 3, retry_delay: float = 0.1):
        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._ensure_storage_file()
    
    def _ensure_storage_file(self) -> None:
        if not self.storage_path.exists():
            with open(self.storage_path, 'w') as f:
                json.dump({"replies": []}, f)
    
    async def mark_comment_replied(self, comment_id: str, pr_number: int, repository_name: str) -> None:
        async with aiofiles.open(self.storage_path, 'r') as f:
            data = json.loads(await f.read())
        
        reply_record = {
            "comment_id": comment_id,
            "pr_number": pr_number,
            "replied_at": datetime.now().isoformat(),
            "repository_name": repository_name
        }
        data["replies"].append(reply_record)
        
        async with aiofiles.open(self.storage_path, 'w') as f:
            await f.write(json.dumps(data, indent=2))
    
    async def get_replied_comment_ids(self, pr_number: int, repository_name: str) -> Set[str]:
        async with aiofiles.open(self.storage_path, 'r') as f:
            data = json.loads(await f.read())
        
        return {
            reply["comment_id"] 
            for reply in data["replies"] 
            if reply["pr_number"] == pr_number and reply["repository_name"] == repository_name
        }
```

### 4.3 SQLite Implementation (Phase 2)

```python
# File: comment_tracker.py (continued)
import sqlite3
import threading
from pathlib import Path

class SQLiteCommentTracker(AbstractCommentTracker):
    """SQLite-based comment tracking following SQLiteSymbolStorage patterns."""
    
    def __init__(self, db_path: str | Path, max_retries: int = 3, retry_delay: float = 0.1):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection: sqlite3.Connection | None = None
        self._connection_lock = threading.Lock()
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.create_schema()
    
    def create_schema(self) -> None:
        """Create comment_replies table with indexes."""
        conn = self._get_connection()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS comment_replies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                comment_id TEXT NOT NULL,
                pr_number INTEGER NOT NULL,
                repository_name TEXT NOT NULL,
                replied_at TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(comment_id, repository_name)
            )
        """)
        
        # Performance indexes
        conn.execute("CREATE INDEX IF NOT EXISTS idx_pr_repo ON comment_replies(pr_number, repository_name)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_comment_id ON comment_replies(comment_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_repo_date ON comment_replies(repository_name, replied_at)")
        conn.commit()
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection with retry logic matching SQLiteSymbolStorage."""
        with self._connection_lock:
            if self._connection is None:
                self._connection = sqlite3.connect(str(self.db_path))
                self._connection.row_factory = sqlite3.Row
            return self._connection
    
    async def mark_comment_replied(self, comment_id: str, pr_number: int, repository_name: str) -> None:
        conn = self._get_connection()
        conn.execute("""
            INSERT OR REPLACE INTO comment_replies 
            (comment_id, pr_number, repository_name, replied_at)
            VALUES (?, ?, ?, ?)
        """, (comment_id, pr_number, repository_name, datetime.now().isoformat()))
        conn.commit()
    
    async def get_replied_comment_ids(self, pr_number: int, repository_name: str) -> Set[str]:
        conn = self._get_connection()
        cursor = conn.execute("""
            SELECT comment_id FROM comment_replies 
            WHERE pr_number = ? AND repository_name = ?
        """, (pr_number, repository_name))
        return {row["comment_id"] for row in cursor.fetchall()}
```

### 4.4 GitHub Tools Integration

```python
# File: github_tools.py - Modifications to existing functions

# Global comment tracker (set by worker)
comment_tracker: AbstractCommentTracker | None = None

# Modify execute_post_pr_reply function (around line 2030)
async def execute_post_pr_reply(repo_name: str, comment_id: str, message: str) -> str:
    """Reply to a PR comment and track the reply."""
    try:
        # ... existing GitHub API reply logic ...
        
        # NEW: Track the reply
        if comment_tracker:
            # Extract PR number from comment context
            pr_number = await _get_pr_number_for_comment(repo_name, comment_id)
            await comment_tracker.mark_comment_replied(comment_id, pr_number, repo_name)
            logger.info(f"Tracked reply to comment {comment_id} in PR {pr_number}")
        
        return json.dumps({
            "success": True,
            "comment_id": comment_id,
            "message": "Reply posted and tracked successfully"
        })
    except Exception as e:
        logger.error(f"Failed to post PR reply: {e}", exc_info=True)
        return json.dumps({"error": f"Failed to post PR reply: {e}"})

# Modify execute_get_pr_comments function (around line 2029)
async def execute_get_pr_comments(repo_name: str, pr_number: int, include_replied: bool = False) -> str:
    """Get PR comments, optionally filtering out already-replied comments."""
    try:
        # ... existing GitHub API comment fetching logic ...
        
        # NEW: Filter replied comments if requested
        if not include_replied and comment_tracker:
            replied_ids = await comment_tracker.get_replied_comment_ids(pr_number, repo_name)
            comments = [c for c in comments if str(c.id) not in replied_ids]
            logger.info(f"Filtered {len(replied_ids)} replied comments from PR {pr_number}")
        
        return json.dumps({
            "comments": [{"id": c.id, "body": c.body, "user": c.user.login} for c in comments],
            "total_comments": len(comments),
            "replied_comments_filtered": len(replied_ids) if not include_replied else 0
        })
    except Exception as e:
        logger.error(f"Failed to get PR comments: {e}", exc_info=True)
        return json.dumps({"error": f"Failed to get PR comments: {e}"})
```

### 4.5 Worker Process Integration

```python
# File: mcp_worker.py - Add comment tracker initialization

class WorkerManager:
    def __init__(self, ...):
        # ... existing initialization ...
        
        # NEW: Initialize comment tracker alongside symbol storage
        comment_db_path = str(self.db_path).replace('.db', '_comments.db')
        
        # Phase 1: File-based tracker
        if GITHUB_AGENT_DEV_MODE:
            self.comment_tracker = FileCommentTracker(
                storage_path=comment_db_path.replace('.db', '_comments.json')
            )
        else:
            # Phase 2: SQLite tracker
            self.comment_tracker = SQLiteCommentTracker(comment_db_path)
        
        # Set global reference for github_tools.py
        import github_tools
        github_tools.comment_tracker = self.comment_tracker
```

## 5. Alternatives Considered

### 5.1 Single SQLite Implementation
**Considered**: Implement only SQLiteCommentTracker from the start
**Rejected**: Developer peer review emphasized rapid prototyping value; JSON approach enables 30-minute MVP validation

### 5.2 Composition-Based Retry Pattern
**Considered**: Extract retry logic into separate RetryManager class as suggested by Senior Engineer
**Rejected**: Architect peer review identified this violates existing [`SQLiteSymbolStorage`](file:///Users/mstriebeck/Code/github-agent/symbol_storage.py#L127) patterns; retry logic embedded in storage constructor

### 5.3 In-Memory-Only Tracking
**Considered**: Store replied comment IDs only in worker process memory
**Rejected**: Loses tracking state across agent restarts; fails persistence requirement

### 5.4 GitHub API Comment Reactions
**Considered**: Use GitHub API reactions (👍, 🎯) to mark replied comments
**Rejected**: Pollutes PR comment interface; requires additional API calls; external visibility of internal state

## 6. Testing / Validation

### 6.1 Unit Test Structure

```python
# File: tests/test_comment_tracker.py

class TestAbstractCommentTracker:
    """Test suite for AbstractCommentTracker interface compliance."""
    
    async def test_mark_comment_replied_persists(self, tracker: AbstractCommentTracker):
        await tracker.mark_comment_replied("123", 456, "test-repo")
        replied_ids = await tracker.get_replied_comment_ids(456, "test-repo")
        assert "123" in replied_ids
    
    async def test_filter_excludes_replied_comments(self, tracker: AbstractCommentTracker):
        # Setup: Mark comment as replied
        await tracker.mark_comment_replied("replied-123", 789, "test-repo")
        
        # Test: Verify filtering logic
        all_comment_ids = {"replied-123", "new-456", "new-789"}
        replied_ids = await tracker.get_replied_comment_ids(789, "test-repo")
        filtered_ids = all_comment_ids - replied_ids
        
        assert "replied-123" not in filtered_ids
        assert "new-456" in filtered_ids

class TestFileCommentTracker(TestAbstractCommentTracker):
    @pytest.fixture
    async def tracker(self, tmp_path):
        return FileCommentTracker(tmp_path / "test_comments.json")

class TestSQLiteCommentTracker(TestAbstractCommentTracker):
    @pytest.fixture  
    async def tracker(self, tmp_path):
        return SQLiteCommentTracker(tmp_path / "test_comments.db")
```

### 6.2 Integration Test Scenarios

```python
# File: tests/test_github_comment_integration.py

class TestGitHubCommentIntegration:
    """Integration tests for GitHub comment tracking workflow."""
    
    async def test_post_reply_tracks_comment(self, mock_github_api, comment_tracker):
        # Setup: Mock GitHub API responses
        mock_github_api.setup_pr_comment("test-comment-123", pr_number=456)
        
        # Execute: Post reply through github_tools
        result = await execute_post_pr_reply("test-repo", "test-comment-123", "Test reply")
        
        # Verify: Comment is tracked
        replied_ids = await comment_tracker.get_replied_comment_ids(456, "test-repo")
        assert "test-comment-123" in replied_ids
    
    async def test_get_comments_filters_replied(self, mock_github_api, comment_tracker):
        # Setup: Pre-populate replied comment
        await comment_tracker.mark_comment_replied("old-comment", 789, "test-repo")
        mock_github_api.setup_pr_comments(789, ["old-comment", "new-comment"])
        
        # Execute: Get comments with filtering
        result = await execute_get_pr_comments("test-repo", 789, include_replied=False)
        data = json.loads(result)
        
        # Verify: Only new comments returned
        comment_ids = [c["id"] for c in data["comments"]]
        assert "old-comment" not in comment_ids
        assert "new-comment" in comment_ids
```

### 6.3 Performance Validation

```python
# File: tests/test_comment_tracker_performance.py

class TestCommentTrackerPerformance:
    async def test_filter_performance_1000_comments(self, tracker):
        # Setup: 1000 replied comments
        for i in range(1000):
            await tracker.mark_comment_replied(f"comment-{i}", 123, "large-repo")
        
        # Measure: Filter query performance
        start_time = time.time()
        replied_ids = await tracker.get_replied_comment_ids(123, "large-repo")
        duration = time.time() - start_time
        
        # Verify: Sub-100ms performance
        assert len(replied_ids) == 1000
        assert duration < 0.1  # 100ms threshold
```

## 7. Migration / Deployment & Rollout

### 7.1 Phase 1 Deployment (Week 1)

**Day 1**: Core Implementation
1. Create `comment_tracker.py` with `AbstractCommentTracker` and `FileCommentTracker`
2. Add basic integration to [`github_tools.py`](file:///Users/mstriebeck/Code/github-agent/github_tools.py)
3. Update [`mcp_worker.py`](file:///Users/mstriebeck/Code/github-agent/mcp_worker.py) initialization

**Day 2**: Testing & Integration
1. Implement unit tests for `FileCommentTracker`
2. Add integration tests with mock GitHub API
3. Test with single PR comment workflow

**Day 3**: Validation
1. Deploy to development environment
2. Test with real GitHub PR data
3. Validate performance with 10-50 comments

### 7.2 Phase 2 Migration (Week 3)

**Migration Strategy**: Zero-downtime transition from FileCommentTracker to SQLiteCommentTracker

```python
# File: comment_tracker_migration.py

async def migrate_file_to_sqlite(file_path: Path, db_path: Path) -> None:
    """Migrate JSON file data to SQLite database."""
    file_tracker = FileCommentTracker(file_path)
    sqlite_tracker = SQLiteCommentTracker(db_path)
    
    # Read all replies from JSON file
    async with aiofiles.open(file_path, 'r') as f:
        data = json.loads(await f.read())
    
    # Migrate each reply to SQLite
    for reply in data["replies"]:
        await sqlite_tracker.mark_comment_replied(
            reply["comment_id"],
            reply["pr_number"], 
            reply["repository_name"]
        )
    
    logger.info(f"Migrated {len(data['replies'])} comment replies to SQLite")
```

**Rollout Steps**:
1. Deploy SQLiteCommentTracker implementation
2. Run migration script for each repository worker
3. Update worker configuration to use SQLite tracker
4. Validate migrated data integrity
5. Remove FileCommentTracker code

### 7.3 Rollback Plan

**Immediate Rollback**: Disable comment tracking while preserving existing functionality
```python
# Emergency rollback: Set comment_tracker = None in worker
github_tools.comment_tracker = None
```

**Data Recovery**: JSON files provide backup for SQLite corruption
```python
# Restore from JSON backup if SQLite database corrupted
backup_tracker = FileCommentTracker(backup_path)
await migrate_file_to_sqlite(backup_path, new_db_path)
```

## Appendix

### A.1 Conflict Resolutions

**Storage Technology Conflict (SQLite vs JSON)**:
- **Resolution**: Phased approach - FileCommentTracker (Week 1) → SQLiteCommentTracker (Week 3)
- **Decision Point**: 1000 comments or 2-week mark based on performance metrics
- **Rationale**: Enables rapid prototyping while maintaining upgrade path to production-scale storage

**Development Methodology Conflict (Test-First vs Implementation-First)**:
- **Resolution**: Iterative approach - Day 1: Core + basic tests, Day 2: Integration, Day 3: Comprehensive testing
- **Priority Tests**: `test_mark_replied_persists()`, `test_fallback_comment_tracked()`, `test_filter_excludes_replied()`
- **Rationale**: Balances rapid development with quality assurance

**Architectural Consistency Conflict**:
- **Resolution**: Follow [`SQLiteSymbolStorage`](file:///Users/mstriebeck/Code/github-agent/symbol_storage.py#L124) constructor pattern exactly
- **Implementation**: Both FileCommentTracker and SQLiteCommentTracker use `(storage_path, max_retries, retry_delay)` signature
- **Rationale**: Maintains codebase consistency while supporting multiple storage backends

### A.2 Performance Benchmarks

**Target Metrics**:
- Comment filtering: <100ms for 1000 comments
- Reply tracking: <50ms per comment
- Storage size: <1MB per 10,000 tracked replies
- Memory usage: <10MB additional per worker process

**Monitoring Points**:
- SQLite query performance on `idx_pr_repo` index
- JSON file size growth rate
- Worker process memory usage
- Comment tracking success rate

### A.3 Database Schema Evolution

**Version 1** (Initial):
```sql
CREATE TABLE comment_replies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    comment_id TEXT NOT NULL,
    pr_number INTEGER NOT NULL,
    repository_name TEXT NOT NULL,
    replied_at TEXT NOT NULL
);
```

**Version 2** (Future enhancement):
```sql
-- Add columns for reply context and metadata
ALTER TABLE comment_replies ADD COLUMN reply_message_preview TEXT;
ALTER TABLE comment_replies ADD COLUMN github_user TEXT;
ALTER TABLE comment_replies ADD COLUMN reply_github_id TEXT;
```