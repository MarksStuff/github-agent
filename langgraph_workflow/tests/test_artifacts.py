"""Tests for artifact management."""

import json
import tempfile
from pathlib import Path

import pytest

from langgraph_workflow.utils.artifacts import ArtifactManager


class TestArtifactManager:
    """Test artifact manager functionality."""

    @pytest.fixture
    def temp_repo(self):
        """Create a temporary repository directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.fixture
    def artifact_manager(self, temp_repo):
        """Create an artifact manager instance."""
        return ArtifactManager(str(temp_repo))

    def test_initialization(self, temp_repo):
        """Test artifact manager initialization."""
        manager = ArtifactManager(str(temp_repo))

        assert manager.repo_path == temp_repo
        assert manager.artifacts_root == temp_repo / ".workflow/artifacts"
        assert manager.artifacts_root.exists()

    def test_get_thread_dir(self, artifact_manager):
        """Test thread directory creation."""
        thread_dir = artifact_manager.get_thread_dir("test-thread")

        assert thread_dir.exists()
        assert thread_dir.name == "test-thread"
        assert thread_dir.parent == artifact_manager.artifacts_root

    def test_save_artifact(self, artifact_manager):
        """Test saving an artifact."""
        content = "Test artifact content"
        metadata = {"author": "test", "version": "1.0"}

        path = artifact_manager.save_artifact(
            thread_id="thread-1",
            artifact_type="analysis",
            filename="test.md",
            content=content,
            metadata=metadata,
        )

        assert path.exists()
        assert path.read_text() == content

        # Check metadata
        metadata_path = path.parent / "test.md.meta.json"
        assert metadata_path.exists()

        saved_metadata = json.loads(metadata_path.read_text())
        assert saved_metadata["author"] == "test"
        assert saved_metadata["version"] == "1.0"
        assert saved_metadata["thread_id"] == "thread-1"
        assert saved_metadata["artifact_type"] == "analysis"
        assert saved_metadata["filename"] == "test.md"
        assert "created_at" in saved_metadata
        assert saved_metadata["size_bytes"] == len(content.encode("utf-8"))

    def test_load_artifact(self, artifact_manager):
        """Test loading an artifact."""
        content = "Test content to load"
        artifact_manager.save_artifact(
            thread_id="thread-1",
            artifact_type="design",
            filename="design.md",
            content=content,
        )

        loaded = artifact_manager.load_artifact("thread-1", "design", "design.md")
        assert loaded == content

    def test_load_nonexistent_artifact(self, artifact_manager):
        """Test loading a non-existent artifact."""
        loaded = artifact_manager.load_artifact("thread-1", "missing", "file.txt")
        assert loaded is None

    def test_load_artifact_metadata(self, artifact_manager):
        """Test loading artifact metadata."""
        metadata = {"key": "value"}
        artifact_manager.save_artifact(
            thread_id="thread-1",
            artifact_type="code",
            filename="main.py",
            content="code",
            metadata=metadata,
        )

        loaded_metadata = artifact_manager.load_artifact_metadata(
            "thread-1", "code", "main.py"
        )
        assert loaded_metadata is not None
        assert loaded_metadata["key"] == "value"

    def test_list_artifacts(self, artifact_manager):
        """Test listing artifacts."""
        # Save multiple artifacts
        artifact_manager.save_artifact(
            "thread-1", "analysis", "analysis.md", "Analysis content"
        )
        artifact_manager.save_artifact(
            "thread-1", "design", "design.md", "Design content"
        )
        artifact_manager.save_artifact("thread-1", "code", "main.py", "Code content")

        # List all artifacts
        artifacts = artifact_manager.list_artifacts("thread-1")
        assert len(artifacts) == 3

        # Check artifact info
        filenames = [a["filename"] for a in artifacts]
        assert "analysis.md" in filenames
        assert "design.md" in filenames
        assert "main.py" in filenames

        # List filtered by type
        code_artifacts = artifact_manager.list_artifacts("thread-1", "code")
        assert len(code_artifacts) == 1
        assert code_artifacts[0]["filename"] == "main.py"

    def test_create_artifact_index(self, artifact_manager):
        """Test creating artifact index."""
        artifact_manager.save_artifact(
            "thread-1", "analysis", "codebase_analysis.md", "Analysis"
        )
        artifact_manager.save_artifact(
            "thread-1", "design", "consolidated_design.md", "Design"
        )
        artifact_manager.save_artifact("thread-1", "code", "implementation.py", "Code")

        index = artifact_manager.create_artifact_index("thread-1")

        assert "analysis:codebase_analysis" in index
        assert "design:consolidated_design" in index
        assert "code:implementation" in index

        # Check paths are relative
        for key, path in index.items():
            assert not Path(path).is_absolute()
            assert ".workflow/artifacts" in path

    def test_cleanup_thread_keep_final(self, artifact_manager):
        """Test cleaning up thread artifacts while keeping final ones."""
        # Create artifacts of different types
        artifact_manager.save_artifact("thread-1", "analysis", "analysis.md", "content")
        artifact_manager.save_artifact("thread-1", "design", "design.md", "content")
        artifact_manager.save_artifact("thread-1", "code", "main.py", "content")
        artifact_manager.save_artifact("thread-1", "tests", "test.py", "content")
        artifact_manager.save_artifact("thread-1", "temp", "temp.txt", "content")

        # Cleanup keeping final artifacts
        artifact_manager.cleanup_thread("thread-1", keep_final_artifacts=True)

        # Check that only final types are kept
        thread_dir = artifact_manager.get_thread_dir("thread-1")
        remaining_dirs = [d.name for d in thread_dir.iterdir() if d.is_dir()]

        assert "design" in remaining_dirs
        assert "code" in remaining_dirs
        assert "tests" in remaining_dirs
        assert "analysis" not in remaining_dirs
        assert "temp" not in remaining_dirs

    def test_cleanup_thread_remove_all(self, artifact_manager):
        """Test cleaning up all thread artifacts."""
        artifact_manager.save_artifact("thread-1", "analysis", "analysis.md", "content")
        artifact_manager.save_artifact("thread-1", "design", "design.md", "content")

        thread_dir = artifact_manager.get_thread_dir("thread-1")
        assert thread_dir.exists()

        # Cleanup removing everything
        artifact_manager.cleanup_thread("thread-1", keep_final_artifacts=False)

        assert not thread_dir.exists()

    def test_export_artifacts(self, artifact_manager, temp_repo):
        """Test exporting artifacts to ZIP."""
        # Create some artifacts
        artifact_manager.save_artifact(
            "thread-1", "analysis", "analysis.md", "Analysis"
        )
        artifact_manager.save_artifact("thread-1", "design", "design.md", "Design")
        artifact_manager.save_artifact("thread-1", "code", "main.py", "Code")

        # Export to ZIP
        export_path = temp_repo / "export.zip"
        result_path = artifact_manager.export_artifacts("thread-1", str(export_path))

        assert result_path == export_path
        assert export_path.exists()

        # Verify ZIP contents
        import zipfile

        with zipfile.ZipFile(export_path, "r") as zipf:
            namelist = zipf.namelist()
            assert any("analysis.md" in name for name in namelist)
            assert any("design.md" in name for name in namelist)
            assert any("main.py" in name for name in namelist)

    def test_get_storage_stats(self, artifact_manager):
        """Test getting storage statistics."""
        # Create artifacts for multiple threads
        artifact_manager.save_artifact("thread-1", "analysis", "a1.md", "content" * 100)
        artifact_manager.save_artifact("thread-1", "design", "d1.md", "content" * 50)
        artifact_manager.save_artifact("thread-2", "code", "main.py", "content" * 200)

        stats = artifact_manager.get_storage_stats()

        assert stats["total_threads"] == 2
        assert stats["total_artifacts"] == 3
        assert stats["total_size_bytes"] > 0
        assert stats["artifact_types"]["analysis"] == 1
        assert stats["artifact_types"]["design"] == 1
        assert stats["artifact_types"]["code"] == 1
        assert stats["oldest_thread"] in ["thread-1", "thread-2"]
        assert stats["newest_thread"] in ["thread-1", "thread-2"]

    def test_compress_old_artifacts(self, artifact_manager):
        """Test compressing old artifacts."""
        # Create multiple artifacts of the same type
        for i in range(10):
            artifact_manager.save_artifact(
                "thread-1", "analysis", f"analysis_{i}.md", f"Content {i}"
            )

        # Compress old artifacts (keep latest 5)
        artifact_manager.compress_old_artifacts("thread-1", keep_latest=5)

        # Check that older artifacts are compressed
        thread_dir = artifact_manager.get_thread_dir("thread-1")
        analysis_dir = thread_dir / "analysis"

        compressed_count = len(list(analysis_dir.glob("*.gz")))
        uncompressed_count = len(
            [f for f in analysis_dir.glob("*.md") if not f.name.endswith(".meta.json")]
        )

        # Should have 5 uncompressed and 5 compressed
        assert uncompressed_count == 5
        assert compressed_count == 5
