# Consolidated Design Document

## 1. Introduction

This design document specifies the architecture for GitHub PR comment tracking functionality that persists which comments have been replied to and filters them from subsequent `github_get_pr_comments` calls. The solution addresses human feedback regarding retry mechanism duplication and proper date/time handling while maintaining consistency with the existing codebase's architectural patterns and testing standards.

The design balances immediate delivery needs with long-term maintainability, incorporating lessons from multiple engineering perspectives to create a cohesive solution that integrates seamlessly with the existing GitHub tools infrastructure.

## 2. Goals / Non-Goals

### Goals

- **Comment Reply Persistence**: Track which GitHub PR comments have been replied to across system restarts
- **Filtered Comment Retrieval**: Modify `github_get_pr_comments` to exclude already-replied comments  
- **Retry Mechanism Consolidation**: Eliminate code duplication between storage implementations using composition pattern
- **Type-Safe Date Handling**: Replace string timestamps with proper temporal types for data integrity
- **Architectural Consistency**: Follow existing codebase patterns for storage, testing, and error handling
- **Incremental Migration**: Support phased rollout from simple file storage to database persistence

### Non-Goals

- **Real-time Comment Synchronization**: This design does not address live updates or webhook-based comment tracking
- **Comment Content Analysis**: No sentiment analysis, AI processing, or content-based filtering beyond reply status
- **Multi-Repository Comment Correlation**: Comments are tracked per-repository without cross-repository relationships
- **GitHub API Rate Limit Management**: Existing rate limiting mechanisms remain unchanged
- **Comment Threading Analysis**: Parent-child comment relationships are not modeled beyond GitHub's native structure
- **Audit Trail**: Comment reply history beyond current reply status is not maintained

## 3. Proposed Architecture

The architecture implements a **layered storage abstraction** with **composition-based retry handling** that integrates with the existing `github_tools.py` infrastructure. The design uses **Abstract Base Classes** for testability while supporting multiple persistence backends through dependency injection.

**Core Components**:
- `AbstractCommentStorage`: Interface defining comment persistence operations
- `BaseRetryableStorage`: Shared retry mechanism using composition pattern  
- `FileCommentStorage`: JSON file-based persistence for development/low-volume scenarios
- `SQLiteCommentStorage`: Database persistence for production environments
- `CommentReply`: Domain model representing replied comment with timestamp
- `CommentTrackingService`: High-level service orchestrating storage and GitHub API interactions

**Integration Points**:
- Modified `execute_get_pr_comments()` function filters replied comments
- New `execute_mark_comment_replied()` tool for persistence operations
- Shared retry logic extracted from existing `SQLiteSymbolStorage`
- Mock implementations following existing `tests/mocks/` patterns

**Data Flow**: GitHub API → Comment filtering → Storage persistence → Filtered response

## 4. Detailed Design

### Core Domain Models

```python
@dataclass
class CommentReply:
    """Domain model for a replied comment with timestamp tracking"""
    comment_id: int
    pr_number: int
    replied_at: datetime
    repository_id: str
    
    def to_dict(self) -> dict[str, Any]: ...
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'CommentReply': ...
```

### Storage Abstraction Layer

```python
class AbstractCommentStorage(ABC):
    """Abstract interface for comment reply persistence"""
    
    @abstractmethod
    async def mark_replied(self, comment_reply: CommentReply) -> None: ...
    
    @abstractmethod
    async def is_replied(self, comment_id: int, pr_number: int) -> bool: ...
    
    @abstractmethod
    async def get_replied_comment_ids(self, pr_number: int) -> set[int]: ...
    
    @abstractmethod
    async def cleanup_old_replies(self, days_old: int = 30) -> int: ...
    
    @abstractmethod
    def health_check(self) -> bool: ...
```

### Retry Mechanism Base Class

```python
class BaseRetryableStorage:
    """Shared retry logic using composition pattern"""
    
    def __init__(self, max_retries: int = 3, retry_delay: float = 0.1):
        self.max_retries = max_retries
        self.retry_delay = retry_delay
    
    async def execute_with_retry(self, operation_name: str, operation_func: Callable, *args, **kwargs) -> Any: ...
    
    def _should_retry(self, exception: Exception, attempt: int) -> bool: ...
    
    def _calculate_delay(self, attempt: int) -> float: ...
```

### File-Based Implementation

```python
class FileCommentStorage(BaseRetryableStorage, AbstractCommentStorage):
    """JSON file-based comment storage for development environments"""
    
    def __init__(self, storage_path: Path, max_retries: int = 3):
        super().__init__(max_retries)
        self.storage_path = storage_path
        self._file_lock = asyncio.Lock()
    
    async def mark_replied(self, comment_reply: CommentReply) -> None: ...
    async def is_replied(self, comment_id: int, pr_number: int) -> bool: ...
    async def get_replied_comment_ids(self, pr_number: int) -> set[int]: ...
    async def _load_data(self) -> dict[str, Any]: ...
    async def _save_data(self, data: dict[str, Any]) -> None: ...
```

### Database Implementation

```python
class SQLiteCommentStorage(BaseRetryableStorage, AbstractCommentStorage):
    """SQLite-based comment storage for production environments"""
    
    def __init__(self, db_path: Path, max_retries: int = 3):
        super().__init__(max_retries)
        self.db_path = db_path
        self._connection_pool = None
    
    async def create_schema(self) -> None: ...
    async def mark_replied(self, comment_reply: CommentReply) -> None: ...
    async def is_replied(self, comment_id: int, pr_number: int) -> bool: ...
    async def get_replied_comment_ids(self, pr_number: int) -> set[int]: ...
```

### Database Schema

```sql
CREATE TABLE comment_replies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    comment_id INTEGER NOT NULL,
    pr_number INTEGER NOT NULL,
    repository_id TEXT NOT NULL,
    replied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(comment_id, pr_number, repository_id)
);

CREATE INDEX idx_comment_replies_pr ON comment_replies(pr_number, repository_id);
CREATE INDEX idx_comment_replies_comment ON comment_replies(comment_id);
CREATE INDEX idx_comment_replies_timestamp ON comment_replies(replied_at);
```

### Service Layer

```python
class CommentTrackingService:
    """High-level service for comment tracking operations"""
    
    def __init__(self, storage: AbstractCommentStorage, github_context: AbstractGitHubAPIContext):
        self.storage = storage
        self.github_context = github_context
    
    async def mark_comment_replied(self, comment_id: int, pr_number: int) -> None: ...
    
    async def filter_unreplied_comments(self, comments: list[dict], pr_number: int) -> list[dict]: ...
    
    async def get_reply_statistics(self, pr_number: int) -> dict[str, int]: ...
```

### GitHub Tools Integration

```python
# Modified function signatures in github_tools.py
async def execute_get_pr_comments(repo_name: str, pr_number: int | None = None) -> str:
    """Modified to filter out replied comments using comment storage"""
    # Existing implementation + comment filtering logic

async def execute_mark_comment_replied(repo_name: str, comment_id: int, pr_number: int | None = None) -> str:
    """New tool for marking comments as replied"""
    # Implementation using CommentTrackingService

def get_comment_storage(repo_name: str) -> AbstractCommentStorage:
    """Factory function for comment storage instances"""
    # Returns appropriate storage implementation based on configuration
```

### Configuration and Factory

```python
class CommentStorageConfig:
    storage_type: Literal["file", "sqlite"]
    storage_path: Path
    max_retries: int = 3
    cleanup_days: int = 30

class CommentStorageFactory:
    @staticmethod
    def create_storage(config: CommentStorageConfig) -> AbstractCommentStorage: ...
    
    @staticmethod
    def create_service(storage: AbstractCommentStorage, github_context: AbstractGitHubAPIContext) -> CommentTrackingService: ...
```

### Error Handling

```python
class CommentStorageError(Exception):
    """Base exception for comment storage operations"""

class CommentAlreadyRepliedException(CommentStorageError):
    """Raised when attempting to mark already-replied comment"""

class CommentStorageUnavailableError(CommentStorageError):
    """Raised when storage backend is inaccessible"""

class CommentDataCorruptionError(CommentStorageError):
    """Raised when storage data integrity is compromised"""
```

## 5. Alternatives Considered

### Storage Backend Alternatives

**File-based JSON Storage (Selected for Phase 1)**:
- ✅ Zero configuration, works immediately
- ✅ Human-readable for debugging  
- ✅ Simple backup and migration
- ❌ Limited concurrent access
- ❌ No ACID guarantees

**SQLite Database (Selected for Phase 2)**:
- ✅ ACID compliance and concurrent access
- ✅ Efficient querying and indexing
- ✅ Established patterns in codebase
- ❌ Additional operational complexity
- ❌ Binary format requires tools for inspection

**Redis/In-Memory Cache (Rejected)**:
- ❌ Additional infrastructure dependency
- ❌ Data loss on restart without persistence
- ❌ Overkill for comment tracking volume

### Retry Pattern Alternatives

**Inheritance-based Retry (Rejected)**:
- ❌ Creates complex multiple inheritance hierarchies
- ❌ Violates single responsibility principle
- ❌ Difficult to test retry logic in isolation

**Decorator Pattern (Rejected)**:
- ❌ Less explicit than composition
- ❌ Harder to configure per-storage-type policies
- ❌ Debugging complexity with nested decorators

**Composition with Strategy Pattern (Selected)**:
- ✅ Clear separation of concerns
- ✅ Testable retry logic in isolation  
- ✅ Configurable per storage implementation
- ✅ Follows existing codebase patterns

### Date/Time Handling Alternatives

**String Timestamps (Rejected)**:
- ❌ No type safety or validation
- ❌ Parsing errors and timezone issues
- ❌ Difficult date arithmetic operations

**Native datetime Objects (Selected)**:
- ✅ Built-in type safety and validation
- ✅ JSON serialization support
- ✅ Standard library date operations
- ✅ Familiar to development team

**Custom Timestamp Value Objects (Rejected for Phase 1)**:
- ❌ Premature optimization for current requirements
- ❌ Additional complexity without clear benefits
- ❌ Learning curve for team members

## 6. Testing / Validation

### Test Class Structure

```python
class TestCommentReply(unittest.TestCase):
    """Test domain model serialization and validation"""
    
    def test_to_dict_serialization(self): ...
    def test_from_dict_deserialization(self): ...
    def test_invalid_data_handling(self): ...

class TestBaseRetryableStorage(unittest.TestCase):
    """Test retry mechanism in isolation"""
    
    def test_successful_operation_no_retry(self): ...
    def test_retry_on_transient_failure(self): ...
    def test_max_retries_exceeded(self): ...
    def test_exponential_backoff_timing(self): ...

class TestFileCommentStorage(unittest.TestCase):
    """Test file-based storage implementation"""
    
    def test_mark_replied_persists(self): ...
    def test_is_replied_returns_correct_status(self): ...
    def test_get_replied_comment_ids_filters(self): ...
    def test_concurrent_access_handling(self): ...
    def test_file_corruption_recovery(self): ...

class TestSQLiteCommentStorage(unittest.TestCase):
    """Test database storage implementation"""
    
    def test_schema_creation(self): ...
    def test_mark_replied_database_consistency(self): ...
    def test_cleanup_old_replies(self): ...
    def test_database_connection_retry(self): ...

class TestCommentTrackingService(unittest.TestCase):
    """Test service layer with mocked dependencies"""
    
    def test_filter_unreplied_comments(self): ...
    def test_mark_comment_replied_integration(self): ...
    def test_storage_failure_handling(self): ...
```

### Mock Object Specifications

```python
class MockCommentStorage(AbstractCommentStorage):
    """Mock implementation following tests/mocks/ patterns"""
    
    def __init__(self):
        self.marked_replies: list[CommentReply] = []
        self.should_fail: bool = False
        self._health_status: bool = True
    
    async def mark_replied(self, comment_reply: CommentReply) -> None: ...
    async def is_replied(self, comment_id: int, pr_number: int) -> bool: ...
    def set_failure_mode(self, should_fail: bool) -> None: ...
    def get_marked_replies(self) -> list[CommentReply]: ...

class MockGitHubAPIContext(AbstractGitHubAPIContext):
    """Extended mock for comment tracking scenarios"""
    
    def __init__(self):
        super().__init__()
        self.mock_comments: list[dict] = []
    
    def set_mock_comments(self, comments: list[dict]) -> None: ...
    def add_mock_comment(self, comment_id: int, body: str, author: str) -> None: ...
```

### Integration Test Requirements

- **End-to-End Comment Workflow**: Test complete cycle from GitHub API call through filtering to persistence
- **Storage Migration Testing**: Validate data migration from file to database storage
- **Concurrent Access Testing**: Verify thread safety and data consistency under load
- **GitHub API Integration**: Test with real GitHub API calls in controlled test environment
- **Performance Baseline**: Establish response time benchmarks for comment filtering operations

### Critical Test Scenarios

1. **Comment Persistence Verification**: `test_mark_replied_survives_restart()`
2. **Filtering Accuracy**: `test_filter_excludes_only_replied_comments()`
3. **Retry Mechanism**: `test_storage_failure_retry_recovery()`
4. **Date Handling**: `test_timestamp_serialization_consistency()`
5. **Concurrent Operations**: `test_multiple_threads_mark_different_comments()`

## 7. Migration / Deployment & Rollout

### Phase 1: File-Based Implementation (Week 1-2)

**Deployment Steps**:
1. Deploy `FileCommentStorage` implementation with JSON persistence
2. Add new `execute_mark_comment_replied` tool to `github_tools.py`
3. Modify `execute_get_pr_comments` to use comment filtering
4. Configure file storage in development environments
5. Monitor file size growth and performance metrics

**Rollback Plan**: Remove comment filtering from `execute_get_pr_comments`, revert to original behavior

**Success Criteria**: Comment reply tracking works in development with <100ms response time overhead

### Phase 2: Database Migration (Week 3-4)

**Migration Process**:
1. Deploy `SQLiteCommentStorage` implementation
2. Create data migration utility: `migrate_file_to_database.py`
3. Add configuration option for storage backend selection
4. Migrate existing file data to SQLite schema
5. Switch production instances to database storage

**Data Migration Script**:
```python
class CommentStorageMigrator:
    def __init__(self, file_storage: FileCommentStorage, db_storage: SQLiteCommentStorage): ...
    async def migrate_all_data(self) -> MigrationResult: ...
    async def validate_migration(self) -> ValidationResult: ...
```

**Rollback Plan**: Switch configuration back to file storage, restore from backup files

**Success Criteria**: All historical comment data migrated successfully, <50ms query response times

### Configuration Management

**Environment Variables**:
- `COMMENT_STORAGE_TYPE`: `"file"` or `"sqlite"`
- `COMMENT_STORAGE_PATH`: Path to storage file/database
- `COMMENT_CLEANUP_DAYS`: Days to retain old reply records
- `COMMENT_RETRY_MAX_ATTEMPTS`: Maximum retry attempts for storage operations

**Repository Configuration Extension**:
```json
{
  "comment_tracking": {
    "enabled": true,
    "storage_type": "file",
    "storage_path": "~/.local/share/github-agent/comments",
    "cleanup_interval_days": 30
  }
}
```

### Monitoring and Observability

**Metrics to Track**:
- Comment storage operation latency (mark_replied, is_replied)
- Storage backend health check success rate
- File size growth rate (file storage) / database size (SQLite)
- Comment filtering accuracy and performance impact
- Retry mechanism activation frequency

**Logging Requirements**:
- Storage operation failures with error context
- Migration progress and data validation results
- Performance warnings when response times exceed thresholds
- Cleanup operation statistics and freed storage space

### Production Deployment Checklist

- [ ] All unit tests passing with >95% coverage
- [ ] Integration tests verified against real GitHub API
- [ ] Performance benchmarks meet response time requirements
- [ ] Mock objects implemented following existing patterns
- [ ] Configuration documentation updated
- [ ] Migration scripts tested with production data volumes
- [ ] Rollback procedures validated in staging environment
- [ ] Monitoring dashboards configured for new metrics

## Appendix

### Conflict Resolutions

**Implementation vs Test-First Development**:
- **Resolution**: Implement core functionality first with immediate testability, then expand test coverage iteratively
- **Rationale**: Balances rapid delivery with quality assurance, following existing codebase development patterns

**Abstraction Level Disagreement**:
- **Resolution**: Start with minimal abstraction (file storage) and add complexity only when justified by real requirements
- **Decision Point**: Migrate to database when file storage shows performance degradation or reaches 1000+ comments per repository

**Storage Technology Choice**:
- **Resolution**: Phased approach starting with JSON files, migrating to SQLite based on actual usage metrics
- **Timeline**: Decision point at 2-week mark based on performance data and storage growth patterns

**Testing Strategy Timing**:
- **Resolution**: Priority test coverage for core functionality, expanded integration tests in Phase 2
- **Critical Tests**: 1) `test_mark_replied_persists()` 2) `test_filter_excludes_replied()` 3) `test_storage_retry_recovery()`

### Technical Debt Considerations

**Accepted Technical Debt**:
- File-based storage lacks ACID guarantees (mitigated by migration plan)
- Limited concurrent access in Phase 1 (acceptable for single-user scenarios)
- No audit trail for comment reply history (not required by current use cases)

**Future Enhancement Opportunities**:
- Comment reply analytics and reporting dashboard
- Integration with GitHub webhook events for real-time updates
- Cross-repository comment correlation and insights
- Advanced retry policies (circuit breaker, jitter, custom backoff strategies)

### Dependencies and Prerequisites

**Required Dependencies** (already in codebase):
- `sqlite3`: Database operations
- `json`: File storage serialization  
- `datetime`: Timestamp handling
- `asyncio`: Asynchronous operation support
- `pathlib`: File system operations

**Test Dependencies**:
- `unittest`: Test framework (existing)
- `unittest.mock`: Mock object creation (existing)
- Test fixtures following `tests/fixtures.py` patterns