## Appendix

### Conflict Resolutions

**Issue 1: Retry Mechanism Implementation**
- **Conflict**: New retry abstraction vs existing SQLite retry patterns
- **Resolution**: Use existing `_execute_with_retry()` method in `SQLiteSymbolStorage` for comment operations
- **Rationale**: Maintains pattern consistency and reduces complexity

**Issue 2: Development Approach**
- **Conflict**: Architecture-first vs MVP-first implementation
- **Resolution**: Phased implementation starting with core functionality, then comprehensive testing
- **Implementation Order**:
  1. Implement `record_comment_reply()` and `is_comment_replied()` methods
  2. Add GitHub integration hooks
  3. Add comprehensive persistence layer
  4. Complete testing suite

**Issue 3: Storage Architecture**
- **Conflict**: New storage abstraction vs extending existing patterns
- **Resolution**: Extend `AbstractSymbolStorage` with comment methods rather than create parallel storage
- **Rationale**: Maintains architectural integrity and reuses proven infrastructure

**Issue 4: Data Types and Complexity**
- **Conflict**: String dates vs Date objects, simple vs complex implementations
- **Resolution**: Start with string timestamps (matching GitHub API), add Date object parsing later if needed
- **Rationale**: Pragmatic approach that can evolve based on actual requirements

### Implementation Checklist

**Step 1: Database Layer** (Day 1-2)
- [ ] Add `CommentReply` dataclass to `symbol_storage.py`
- [ ] Add abstract methods to `AbstractSymbolStorage`
- [ ] Implement methods in `SQLiteSymbolStorage`
- [ ] Add database schema creation with indexes
- [ ] Test database operations in isolation

**Step 2: GitHub Integration** (Day 3-4)
- [ ] Add `get_symbol_storage_for_repo()` utility function
- [ ] Modify `execute_post_pr_reply()` to record successful replies
- [ ] Add PR number extraction logic from GitHub responses
- [ ] Modify `execute_get_pr_comments()` to filter replied comments
- [ ] Add comprehensive error handling and logging

**Step 3: Testing Infrastructure** (Day 5-6)
- [ ] Enhance `MockSymbolStorage` with comment methods
- [ ] Create unit tests for storage operations
- [ ] Create integration tests for GitHub tools
- [ ] Add performance tests for filtering operations
- [ ] Verify cross-repository isolation

**Step 4: Production Readiness** (Day 7)
- [ ] Add monitoring and metrics collection
- [ ] Verify migration strategy for existing databases
- [ ] Performance testing with realistic comment volumes
- [ ] Documentation updates and deployment procedures

### Technical Specifications

**Database Constraints:**
- `comment_replies.comment_id`: INTEGER NOT NULL (GitHub comment ID)
- `comment_replies.repo_name`: TEXT NOT NULL (repository identifier)
- `comment_replies.pr_number`: INTEGER NOT NULL (PR number)
- `comment_replies.replied_at`: TEXT NOT NULL (ISO 8601 timestamp)
- UNIQUE constraint on (comment_id, repo_name) prevents duplicates

**Performance Targets:**
- Comment reply recording: < 10ms per operation
- Comment filtering: < 50ms for 100 comments
- Database query response: < 5ms for indexed lookups
- Memory usage: < 1MB additional per repository worker

**Error Handling Patterns:**
- Database errors: Log and continue with graceful degradation
- GitHub API failures: Don't record tracking for failed replies
- Storage unavailable: Return unfiltered comments with warning log
- Concurrent access: Use existing SQLite transaction patterns