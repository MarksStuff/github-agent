"""Tests for comment tracking functionality in symbol storage."""

import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from symbol_storage import CommentReply, SQLiteSymbolStorage
from tests.mocks import MockSymbolStorage


class TestCommentReply(unittest.TestCase):
    """Test CommentReply domain model."""

    def test_to_dict_uses_dataclasses_asdict(self):
        """Verify dataclasses.asdict integration with datetime conversion."""
        reply = CommentReply(
            comment_id=123,
            pr_number=45,
            replied_at=datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC),
            repository_id="test/repo",
        )

        result = reply.to_dict()
        expected = {
            "comment_id": 123,
            "pr_number": 45,
            "replied_at": "2024-01-15T10:30:00+00:00",
            "repository_id": "test/repo",
        }
        self.assertEqual(result, expected)

    def test_from_dict_datetime_parsing(self):
        """Verify datetime object creation from ISO string."""
        data = {
            "comment_id": 123,
            "pr_number": 45,
            "replied_at": "2024-01-15T10:30:00+00:00",
            "repository_id": "test/repo",
        }

        reply = CommentReply.from_dict(data)
        expected_dt = datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC)
        self.assertEqual(reply.replied_at, expected_dt)
        self.assertEqual(reply.comment_id, 123)
        self.assertEqual(reply.pr_number, 45)
        self.assertEqual(reply.repository_id, "test/repo")


class TestSQLiteCommentTracking(unittest.TestCase):
    """Test comment tracking functionality in SQLite storage."""

    def setUp(self):
        """Set up test with temporary database."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test_comments.db"
        self.storage = SQLiteSymbolStorage(self.db_path)

    def tearDown(self):
        """Clean up test database."""
        self.storage.close()

    def test_mark_comment_replied(self):
        """Test marking a comment as replied."""
        reply = CommentReply(
            comment_id=123,
            pr_number=45,
            replied_at=datetime.now(UTC),
            repository_id="test/repo",
        )

        self.storage.mark_comment_replied(reply)

        # Verify the comment is marked as replied
        self.assertTrue(self.storage.is_comment_replied(123, 45))
        self.assertFalse(self.storage.is_comment_replied(124, 45))
        self.assertFalse(self.storage.is_comment_replied(123, 46))

    def test_get_replied_comment_ids(self):
        """Test retrieving replied comment IDs for a PR."""
        # Mark multiple comments as replied
        for comment_id in [100, 200, 300]:
            reply = CommentReply(
                comment_id=comment_id,
                pr_number=50,
                replied_at=datetime.now(UTC),
                repository_id="test/repo",
            )
            self.storage.mark_comment_replied(reply)

        # Mark a comment for a different PR
        other_reply = CommentReply(
            comment_id=400,
            pr_number=51,
            replied_at=datetime.now(UTC),
            repository_id="test/repo",
        )
        self.storage.mark_comment_replied(other_reply)

        # Get replied IDs for PR 50
        replied_ids = self.storage.get_replied_comment_ids(50)
        self.assertEqual(replied_ids, {100, 200, 300})

        # Get replied IDs for PR 51
        replied_ids = self.storage.get_replied_comment_ids(51)
        self.assertEqual(replied_ids, {400})

        # Get replied IDs for non-existent PR
        replied_ids = self.storage.get_replied_comment_ids(999)
        self.assertEqual(replied_ids, set())

    def test_cleanup_old_comment_replies(self):
        """Test cleaning up old comment reply records."""
        now = datetime.now(UTC)

        # Create an old comment reply (35 days ago)
        old_reply = CommentReply(
            comment_id=100,
            pr_number=10,
            replied_at=now - timedelta(days=35),
            repository_id="test/repo",
        )
        self.storage.mark_comment_replied(old_reply)

        # Create a recent comment reply
        recent_reply = CommentReply(
            comment_id=200,
            pr_number=20,
            replied_at=now - timedelta(days=5),
            repository_id="test/repo",
        )
        self.storage.mark_comment_replied(recent_reply)

        # Clean up comments older than 30 days
        cleaned = self.storage.cleanup_old_comment_replies(days_old=30)

        # Old comment should be removed
        self.assertFalse(self.storage.is_comment_replied(100, 10))
        # Recent comment should remain
        self.assertTrue(self.storage.is_comment_replied(200, 20))
        # Should have cleaned 1 record
        self.assertEqual(cleaned, 1)


class TestMockCommentTracking(unittest.TestCase):
    """Test comment tracking functionality in mock storage."""

    def setUp(self):
        """Set up test with mock storage."""
        self.storage = MockSymbolStorage()

    def test_mark_and_check_comment_replied(self):
        """Test marking and checking comment replies in mock."""
        reply = CommentReply(
            comment_id=123,
            pr_number=45,
            replied_at=datetime.now(UTC),
            repository_id="test/repo",
        )

        self.storage.mark_comment_replied(reply)

        self.assertTrue(self.storage.is_comment_replied(123, 45))
        self.assertFalse(self.storage.is_comment_replied(124, 45))

    def test_get_replied_comment_ids_mock(self):
        """Test getting replied comment IDs in mock."""
        for comment_id in [100, 200]:
            reply = CommentReply(
                comment_id=comment_id,
                pr_number=50,
                replied_at=datetime.now(UTC),
                repository_id="test/repo",
            )
            self.storage.mark_comment_replied(reply)

        replied_ids = self.storage.get_replied_comment_ids(50)
        self.assertEqual(replied_ids, {100, 200})

    def test_helper_methods(self):
        """Test mock-specific helper methods."""
        reply = CommentReply(
            comment_id=123,
            pr_number=45,
            replied_at=datetime.now(UTC),
            repository_id="test/repo",
        )

        self.storage.mark_comment_replied(reply)

        # Test get_all_comment_replies
        all_replies = self.storage.get_all_comment_replies()
        self.assertEqual(len(all_replies), 1)
        self.assertEqual(all_replies[0].comment_id, 123)

        # Test clear_comment_replies
        self.storage.clear_comment_replies()
        all_replies = self.storage.get_all_comment_replies()
        self.assertEqual(len(all_replies), 0)
        self.assertFalse(self.storage.is_comment_replied(123, 45))

    def test_cleanup_old_replies_mock(self):
        """Test cleanup of old replies in mock storage."""
        now = datetime.now(UTC)

        # Add old reply
        old_reply = CommentReply(
            comment_id=100,
            pr_number=10,
            replied_at=now - timedelta(days=35),
            repository_id="test/repo",
        )
        self.storage.mark_comment_replied(old_reply)

        # Add recent reply
        recent_reply = CommentReply(
            comment_id=200,
            pr_number=20,
            replied_at=now - timedelta(days=5),
            repository_id="test/repo",
        )
        self.storage.mark_comment_replied(recent_reply)

        # Clean up
        cleaned = self.storage.cleanup_old_comment_replies(days_old=30)

        self.assertEqual(cleaned, 1)
        self.assertFalse(self.storage.is_comment_replied(100, 10))
        self.assertTrue(self.storage.is_comment_replied(200, 20))


if __name__ == "__main__":
    unittest.main()
