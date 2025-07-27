# Comment Reply Persistence Feature - Implementation Design Document

## 1. Core Classes and Interfaces

### Abstract Base Layer
```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List, Protocol

@dataclass(frozen=True)
class CommentReplyOutcome:
    """Value object capturing reply attempt results"""
    original_comment_id: str
    pr_id: str
    reply_comment_id: Optional[str]
    fallback_comment_id: Optional[str] 
    timestamp: datetime
    success: bool
    error_message: Optional[str] = None

class CommentTracker(ABC):
    """Abstract interface for comment reply tracking"""
    
    @abstractmethod
    def mark_replied(self, outcome: CommentReplyOutcome) -> bool:
        """Record reply attempt outcome. Returns True if successfully persisted."""
        pass
    
    @abstractmethod
    def has_been_processed(self, comment_id: str) -> bool:
        """Check if comment has been replied to or processed."""
        pass
    
    @abstractmethod
    def get_unprocessed_comments(self, pr_id: str) -> List[str]:
        """Get comment IDs that haven't been processed for given PR."""
        pass
```

### Concrete Implementation
```python
import sqlite3
from pathlib import Path

class SQLiteCommentTracker(CommentTracker):
    """SQLite-based persistence for comment reply tracking"""
    
    def __init__(self, db_path: str = "comment_tracking.db"):
        self.db_path = Path(db_path)
        self._init_database()
    
    def _init_database(self) -> None:
        """Initialize database schema if not exists"""
        # Implementation details in Database Schema section
        
    def mark_replied(self, outcome: CommentReplyOutcome) -> bool:
        """Record reply attempt with transaction safety"""
        # Implementation details in Implementation Sequence
        
    def has_been_processed(self, comment_id: str) -> bool:
        """Query processing status with caching"""
        # Implementation details in Implementation Sequence
        
    def get_unprocessed_comments(self, pr_id: str) -> List[str]:
        """Efficient query for batch processing"""
        # Implementation details in Implementation Sequence

class CommentReplyProcessor:
    """Main orchestrator for comment reply logic"""
    
    def __init__(self, tracker: CommentTracker, github_service):
        self.tracker = tracker
        self.github_service = github_service
    
    def process_pr_comments(self, pr_id: str, comments: List[dict]) -> List[CommentReplyOutcome]:
        """Process all comments in a PR, attempting replies where appropriate"""
        outcomes = []
        for comment in comments:
            if not self.tracker.has_been_processed(comment['id']):
                outcome = self._attempt_reply(comment, pr_id)
                self.tracker.mark_replied(outcome)
                outcomes.append(outcome)
        return outcomes
    
    def _attempt_reply(self, comment: dict, pr_id: str) -> CommentReplyOutcome:
        """Attempt to reply to a single comment with fallback handling"""
        # Implementation details in Implementation Sequence
```

## 2. Database Schema

### Table Definitions
```sql
-- Core tracking table
CREATE TABLE comment_replies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    original_comment_id TEXT NOT NULL,
    pr_id TEXT NOT NULL,
    reply_comment_id TEXT,
    fallback_comment_id TEXT,
    timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    success BOOLEAN NOT NULL,
    error_message TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(original_comment_id)
);

-- Performance indexes
CREATE INDEX idx_comment_replies_pr_id ON comment_replies(pr_id);
CREATE INDEX idx_comment_replies_timestamp ON comment_replies(timestamp);
CREATE INDEX idx_comment_replies_success ON comment_replies(success);

-- Composite index for common query pattern
CREATE INDEX idx_pr_unprocessed ON comment_replies(pr_id, success) 
WHERE success = 1;
```

### Sample Queries
```sql
-- Check if comment processed
SELECT COUNT(*) FROM comment_replies 
WHERE original_comment_id = ?;

-- Get unprocessed comments for PR
SELECT original_comment_id FROM comment_replies 
WHERE pr_id = ? AND success = 0;

-- Insert new reply tracking
INSERT INTO comment_replies 
(original_comment_id, pr_id, reply_comment_id, success, error_message) 
VALUES (?, ?, ?, ?, ?);

-- Get recent activity for monitoring
SELECT pr_id, COUNT(*) as reply_count, 
       SUM(CASE WHEN success THEN 1 ELSE 0 END) as success_count
FROM comment_replies 
WHERE timestamp > datetime('now', '-1 day')
GROUP BY pr_id;
```

## 3. Integration Specifications

### GitHub Tools Modification
**File**: `github_tools.py`
**Function**: `github_post_pr_reply` (estimated line ~180-200)

```python
# MODIFY EXISTING FUNCTION SIGNATURE
def github_post_pr_reply(
    pr_id: str, 
    reply_text: str, 
    comment_id: str,
    tracker: Optional[CommentTracker] = None  # ADD THIS PARAMETER
) -> dict:
    """Post reply to PR comment with optional tracking"""
    
    # EXISTING CODE REMAINS
    result = github_api_call(...)
    
    # ADD TRACKING LOGIC BEFORE RETURN
    if tracker:
        outcome = CommentReplyOutcome(
            original_comment_id=comment_id,
            pr_id=pr_id,
            reply_comment_id=result.get('id'),
            fallback_comment_id=None,
            timestamp=datetime.now(),
            success=result.get('id') is not None
        )
        tracker.mark_replied(outcome)
    
    return result
```

### Main Comment Processing Integration
**File**: `comment_processor.py` (create new) or modify existing handler

```python
# ADD TO EXISTING COMMENT PROCESSING FUNCTION
def process_pr_comments_with_tracking(pr_id: str):
    """Enhanced comment processing with reply tracking"""
    
    # Initialize tracker (add to existing setup)
    tracker = SQLiteCommentTracker()
    processor = CommentReplyProcessor(tracker, github_service)
    
    # Get comments (existing logic)
    comments = github_get_pr_comments(pr_id)
    
    # Process with tracking (NEW)
    outcomes = processor.process_pr_comments(pr_id, comments)
    
    # Log results (NEW)
    successful_replies = [o for o in outcomes if o.success]
    logger.info(f"Processed {len(outcomes)} comments, {len(successful_replies)} successful replies")
```

### Configuration Integration
**File**: `config.py`
**Add tracking configuration**:

```python
# ADD TO EXISTING CONFIG CLASS
class Config:
    # ... existing config ...
    
    # Comment tracking settings
    COMMENT_TRACKING_ENABLED: bool = True
    COMMENT_TRACKING_DB_PATH: str = "data/comment_tracking.db"
    COMMENT_TRACKING_BATCH_SIZE: int = 50
```

## 4. Implementation Sequence

### Day 1: Core Foundation (4-6 hours)
**Step 1**: Create base abstractions
- File: `comment_tracking/base.py`
- Implement: `CommentReplyOutcome`, `CommentTracker` abstract class
- Test: Basic value object validation

**Step 2**: Implement SQLite tracker
- File: `comment_tracking/sqlite_tracker.py` 
- Implement: `SQLiteCommentTracker` with database initialization
- Test: Database creation and basic CRUD operations

**Step 3**: Basic integration test
- File: `tests/test_comment_tracking_integration.py`
- Test: End-to-end reply attempt with tracking
- Verify: Database persistence works

### Day 2: GitHub Integration (3-4 hours)
**Step 4**: Modify GitHub tools
- File: `github_tools.py` 
- Modify: `github_post_pr_reply` function signature and logic
- Test: Backward compatibility maintained

**Step 5**: Create comment processor
- File: `comment_tracking/processor.py`
- Implement: `CommentReplyProcessor` class
- Test: Batch comment processing logic

**Step 6**: Integration with existing workflows
- Files: Main comment processing entry points
- Modify: Add tracker initialization and usage
- Test: Existing functionality unaffected

### Day 3: Comprehensive Testing (4-5 hours)
**Step 7**: Fallback scenario testing
- File: `tests/test_fallback_scenarios.py`
- Test: Reply failure → fallback comment → tracking
- Verify: All outcomes properly recorded

**Step 8**: Performance and edge case testing
- File: `tests/test_comment_tracking_performance.py`
- Test: Large PR processing, concurrent access
- Verify: Performance within acceptable bounds

**Step 9**: Error handling and recovery
- File: `tests/test_error_scenarios.py`
- Test: Database failures, API failures, partial failures
- Verify: System gracefully handles errors

## 5. Testing Requirements

### Unit Test Classes
```python
class TestCommentReplyOutcome:
    """Test value object behavior"""
    def test_immutable_properties(self): ...
    def test_validation_rules(self): ...

class TestSQLiteCommentTracker:
    """Test persistence layer"""
    def test_mark_replied_success(self): ...
    def test_mark_replied_failure(self): ...
    def test_has_been_processed_existing(self): ...
    def test_has_been_processed_missing(self): ...
    def test_get_unprocessed_comments_empty_pr(self): ...
    def test_get_unprocessed_comments_mixed_status(self): ...
    def test_database_transaction_rollback(self): ...

class TestCommentReplyProcessor:
    """Test orchestration logic"""
    def test_process_pr_comments_all_new(self): ...
    def test_process_pr_comments_some_processed(self): ...
    def test_process_pr_comments_github_api_failure(self): ...
```

### Integration Test Scenarios
```python
class TestCommentTrackingIntegration:
    """End-to-end testing"""
    
    def test_fallback_comment_detection_prevents_loops(self):
        """Critical scenario: Reply fails → creates comment → detects as own comment → no infinite loop"""
        
    def test_concurrent_pr_processing(self):
        """Concurrent processing of same PR doesn't create duplicate replies"""
        
    def test_database_recovery_after_corruption(self):
        """System recovers gracefully from database issues"""
        
    def test_large_pr_performance(self):
        """Processing PR with 500+ comments completes within 30 seconds"""
```

### Critical Edge Cases
- **Empty comment ID handling**: Ensure system doesn't crash on null/empty IDs
- **Database lock contention**: Multiple processes accessing same database
- **GitHub API rate limiting**: Graceful handling when API calls fail
- **Partial failure recovery**: Some comments processed, others fail
- **Schema migration**: Upgrading database schema without data loss

## 6. Technical Decisions

### Persistence Technology: SQLite
**Decision**: Use SQLite for persistence layer
**Rationale**: 
- Zero configuration deployment
- ACID transactions for consistency
- Built-in Python support
- Sufficient performance for expected scale (< 1000 comments/day)
- Easy backup and migration

**Alternative considered**: JSON file storage
**Rejected because**: No transaction support, poor concurrent access, no query optimization

### Design Pattern: Repository Pattern
**Decision**: Use Repository pattern with dependency injection
**Rationale**: 
- Clean separation between business logic and persistence
- Easy testing with mock repositories
- Future migration to different storage systems
- Clear interface contracts

### Error Handling Strategy: Graceful Degradation
**Decision**: Never fail comment processing due to tracking failures
**Implementation**:
```python
try:
    tracker.mark_replied(outcome)
except Exception as e:
    logger.warning(f"Tracking failed for comment {comment_id}: {e}")
    # Continue processing other comments
```

### Transaction Boundaries: Per-Comment
**Decision**: Each comment reply attempt is atomic
**Rationale**: Allows partial success in batch operations, simpler error recovery

### Performance Optimization: Lazy Loading
**Decision**: Initialize database connection on first use
**Implementation**: Database connection created in `_init_database()` called from first method use

### Configuration: Environment-Based
**Decision**: Database path and settings configurable via environment variables
**Implementation**:
```python
DB_PATH = os.getenv('COMMENT_TRACKING_DB_PATH', 'comment_tracking.db')
```

### Logging Strategy: Structured Logging
**Decision**: Use structured logging for monitoring and debugging
**Implementation**:
```python
logger.info("comment_reply_tracked", extra={
    'comment_id': comment_id,
    'pr_id': pr_id,
    'success': outcome.success,
    'processing_time_ms': elapsed_ms
})
```

This design document provides the specific technical blueprint needed for implementation while balancing the competing concerns of simplicity (Developer) and comprehensive design (Senior Engineer). The three-day implementation sequence allows for iterative development with continuous validation.