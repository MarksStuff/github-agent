"""Artifact management for workflow outputs."""

import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class ArtifactManager:
    """Manages workflow artifacts (designs, code, reports) on filesystem."""

    def __init__(self, repo_path: str, artifacts_dir: str = ".workflow/artifacts"):
        """Initialize artifact manager.

        Args:
            repo_path: Repository root path
            artifacts_dir: Relative path for artifacts storage
        """
        self.repo_path = Path(repo_path)
        self.artifacts_root = self.repo_path / artifacts_dir
        self.artifacts_root.mkdir(parents=True, exist_ok=True)

        logger.info(f"Artifact manager initialized at {self.artifacts_root}")

    def get_thread_dir(self, thread_id: str, feature_name: str = None) -> Path:
        """Get or create directory for a specific thread with feature-based organization.

        Args:
            thread_id: Thread identifier
            feature_name: Feature name to create feature-based subdirectory

        Returns:
            Path to thread-specific directory organized by feature
        """
        if feature_name:
            # Create feature-based subdirectory using sanitized feature name
            sanitized_feature = self._sanitize_feature_name(feature_name)
            thread_dir = self.artifacts_root / sanitized_feature / thread_id
        else:
            # Fall back to thread-only organization for backward compatibility
            thread_dir = self.artifacts_root / thread_id
        
        thread_dir.mkdir(parents=True, exist_ok=True)
        return thread_dir
    
    def _sanitize_feature_name(self, feature_name: str) -> str:
        """Sanitize feature name for use as directory name.
        
        Args:
            feature_name: Raw feature name
            
        Returns:
            Sanitized directory name
        """
        import re
        
        # Convert to lowercase and replace spaces/special chars with hyphens
        sanitized = re.sub(r'[^a-zA-Z0-9\s-]', '', feature_name.lower())
        sanitized = re.sub(r'\s+', '-', sanitized)
        sanitized = re.sub(r'-+', '-', sanitized)  # Remove multiple consecutive hyphens
        sanitized = sanitized.strip('-')  # Remove leading/trailing hyphens
        
        # Limit length and ensure it's not empty
        if not sanitized:
            sanitized = "unknown-feature"
        elif len(sanitized) > 50:
            sanitized = sanitized[:50].rstrip('-')
            
        return sanitized

    def save_artifact(
        self,
        thread_id: str,
        artifact_type: str,
        filename: str,
        content: str,
        metadata: Optional[dict] = None,
        feature_name: str = None,
    ) -> Path:
        """Save an artifact to the filesystem.

        Args:
            thread_id: Thread identifier
            artifact_type: Type of artifact (analysis, design, code, tests, etc.)
            filename: Name of the file
            content: Artifact content
            metadata: Optional metadata to store
            feature_name: Feature name for organization (optional for backward compatibility)

        Returns:
            Path to saved artifact
        """
        # Create type-specific subdirectory with feature organization
        type_dir = self.get_thread_dir(thread_id, feature_name) / artifact_type
        type_dir.mkdir(parents=True, exist_ok=True)

        # Save main content
        artifact_path = type_dir / filename
        with open(artifact_path, "w", encoding="utf-8") as f:
            f.write(content)

        # Save metadata if provided
        if metadata:
            metadata_path = type_dir / f"{filename}.meta.json"
            metadata_with_timestamp = {
                **metadata,
                "created_at": datetime.now().isoformat(),
                "thread_id": thread_id,
                "artifact_type": artifact_type,
                "filename": filename,
                "size_bytes": len(content.encode("utf-8")),
            }

            with open(metadata_path, "w", encoding="utf-8") as f:
                json.dump(metadata_with_timestamp, f, indent=2)

        logger.info(f"Saved artifact: {artifact_path}")
        return artifact_path

    def load_artifact(
        self, thread_id: str, artifact_type: str, filename: str, feature_name: str = None
    ) -> Optional[str]:
        """Load an artifact from the filesystem.

        Args:
            thread_id: Thread identifier
            artifact_type: Type of artifact
            filename: Name of the file
            feature_name: Feature name for organization (optional for backward compatibility)

        Returns:
            Artifact content or None if not found
        """
        artifact_path = self.get_thread_dir(thread_id, feature_name) / artifact_type / filename

        if not artifact_path.exists():
            logger.warning(f"Artifact not found: {artifact_path}")
            return None

        try:
            with open(artifact_path, encoding="utf-8") as f:
                content = f.read()

            logger.info(f"Loaded artifact: {artifact_path}")
            return content

        except Exception as e:
            logger.error(f"Failed to load artifact {artifact_path}: {e}")
            return None

    def load_artifact_metadata(
        self, thread_id: str, artifact_type: str, filename: str, feature_name: str = None
    ) -> Optional[dict]:
        """Load artifact metadata.

        Args:
            thread_id: Thread identifier
            artifact_type: Type of artifact
            filename: Name of the file
            feature_name: Feature name for organization (optional for backward compatibility)

        Returns:
            Metadata dict or None if not found
        """
        metadata_path = (
            self.get_thread_dir(thread_id, feature_name) / artifact_type / f"{filename}.meta.json"
        )

        if not metadata_path.exists():
            return None

        try:
            with open(metadata_path, encoding="utf-8") as f:
                metadata = json.load(f)
            return metadata

        except Exception as e:
            logger.error(f"Failed to load metadata {metadata_path}: {e}")
            return None

    def list_artifacts(
        self, thread_id: str, artifact_type: Optional[str] = None, feature_name: str = None
    ) -> list[dict]:
        """List all artifacts for a thread.

        Args:
            thread_id: Thread identifier
            artifact_type: Optional type filter
            feature_name: Feature name for organization (optional for backward compatibility)

        Returns:
            List of artifact information
        """
        thread_dir = self.get_thread_dir(thread_id, feature_name)

        if not thread_dir.exists():
            return []

        artifacts = []

        # Search in specific type or all types
        search_dirs = (
            [thread_dir / artifact_type]
            if artifact_type
            else list(thread_dir.iterdir())
        )

        for type_dir in search_dirs:
            if not type_dir.is_dir():
                continue

            for artifact_file in type_dir.iterdir():
                if artifact_file.suffix == ".json" and artifact_file.name.endswith(
                    ".meta.json"
                ):
                    continue  # Skip metadata files

                # Get file info
                artifact_info = {
                    "thread_id": thread_id,
                    "artifact_type": type_dir.name,
                    "filename": artifact_file.name,
                    "path": str(artifact_file.relative_to(self.repo_path)),
                    "size_bytes": artifact_file.stat().st_size,
                    "modified_at": datetime.fromtimestamp(
                        artifact_file.stat().st_mtime
                    ).isoformat(),
                }

                # Add metadata if available
                metadata = self.load_artifact_metadata(
                    thread_id, type_dir.name, artifact_file.name
                )
                if metadata:
                    artifact_info["metadata"] = metadata

                artifacts.append(artifact_info)

        return sorted(artifacts, key=lambda x: x["modified_at"], reverse=True)

    def create_artifact_index(self, thread_id: str, feature_name: str = None) -> dict[str, str]:
        """Create an index of all artifacts for a thread.

        Args:
            thread_id: Thread identifier
            feature_name: Feature name for organization (optional for backward compatibility)

        Returns:
            Dictionary mapping artifact keys to paths
        """
        artifacts = self.list_artifacts(thread_id, feature_name=feature_name)

        index = {}
        for artifact in artifacts:
            # Create readable key
            key = f"{artifact['artifact_type']}:{artifact['filename']}"
            # Remove extension for cleaner keys
            if key.endswith(".md") or key.endswith(".py") or key.endswith(".json"):
                key = key.rsplit(".", 1)[0]

            index[key] = artifact["path"]

        return index

    def compress_old_artifacts(self, thread_id: str, keep_latest: int = 5) -> None:
        """Compress old artifacts to save space.

        Args:
            thread_id: Thread identifier
            keep_latest: Number of latest artifacts to keep uncompressed
        """
        artifacts = self.list_artifacts(thread_id)

        # Group by type
        by_type = {}
        for artifact in artifacts:
            artifact_type = artifact["artifact_type"]
            if artifact_type not in by_type:
                by_type[artifact_type] = []
            by_type[artifact_type].append(artifact)

        # Compress old artifacts by type
        for artifact_type, type_artifacts in by_type.items():
            if len(type_artifacts) <= keep_latest:
                continue

            # Sort by modification time (newest first)
            type_artifacts.sort(key=lambda x: x["modified_at"], reverse=True)

            # Compress older artifacts
            to_compress = type_artifacts[keep_latest:]

            for artifact in to_compress:
                artifact_path = Path(artifact["path"])
                if artifact_path.exists() and not artifact_path.suffix == ".gz":
                    try:
                        # Create compressed version
                        import gzip

                        compressed_path = artifact_path.with_suffix(
                            artifact_path.suffix + ".gz"
                        )

                        with open(artifact_path, "rb") as f_in:
                            with gzip.open(compressed_path, "wb") as f_out:
                                shutil.copyfileobj(f_in, f_out)

                        # Remove original
                        artifact_path.unlink()

                        logger.info(f"Compressed artifact: {compressed_path}")

                    except Exception as e:
                        logger.error(f"Failed to compress {artifact_path}: {e}")

    def cleanup_thread(self, thread_id: str, keep_final_artifacts: bool = True) -> None:
        """Clean up artifacts for a completed thread.

        Args:
            thread_id: Thread identifier
            keep_final_artifacts: Whether to keep final design/implementation
        """
        thread_dir = self.get_thread_dir(thread_id)

        if not thread_dir.exists():
            logger.warning(f"Thread directory not found: {thread_dir}")
            return

        if keep_final_artifacts:
            # Keep only final artifacts
            keep_types = {"design", "code", "tests"}

            for type_dir in thread_dir.iterdir():
                if type_dir.is_dir() and type_dir.name not in keep_types:
                    try:
                        shutil.rmtree(type_dir)
                        logger.info(f"Cleaned up artifact type: {type_dir}")
                    except Exception as e:
                        logger.error(f"Failed to clean up {type_dir}: {e}")
        else:
            # Remove entire thread directory
            try:
                shutil.rmtree(thread_dir)
                logger.info(f"Cleaned up thread: {thread_id}")
            except Exception as e:
                logger.error(f"Failed to clean up thread {thread_id}: {e}")

    def export_artifacts(self, thread_id: str, export_path: str) -> Path:
        """Export all artifacts for a thread to a ZIP file.

        Args:
            thread_id: Thread identifier
            export_path: Path for the ZIP file

        Returns:
            Path to created ZIP file
        """
        import zipfile

        thread_dir = self.get_thread_dir(thread_id)
        export_path = Path(export_path)

        # Create ZIP file
        with zipfile.ZipFile(export_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            # Add all files from thread directory
            for file_path in thread_dir.rglob("*"):
                if file_path.is_file():
                    # Create relative path within ZIP
                    arc_name = file_path.relative_to(thread_dir)
                    zipf.write(file_path, arc_name)

        logger.info(f"Exported artifacts to: {export_path}")
        return export_path

    def get_storage_stats(self) -> dict:
        """Get storage statistics for the artifact system.

        Returns:
            Dictionary with storage information
        """
        stats = {
            "total_threads": 0,
            "total_artifacts": 0,
            "total_size_bytes": 0,
            "artifact_types": {},
            "oldest_thread": None,
            "newest_thread": None,
        }

        if not self.artifacts_root.exists():
            return stats

        thread_dirs = [d for d in self.artifacts_root.iterdir() if d.is_dir()]
        stats["total_threads"] = len(thread_dirs)

        thread_times = []

        for thread_dir in thread_dirs:
            thread_time = thread_dir.stat().st_mtime
            thread_times.append((thread_dir.name, thread_time))

            # Count artifacts and sizes
            for artifact_file in thread_dir.rglob("*"):
                if artifact_file.is_file() and not artifact_file.name.endswith(
                    ".meta.json"
                ):
                    stats["total_artifacts"] += 1
                    stats["total_size_bytes"] += artifact_file.stat().st_size

                    # Count by type
                    artifact_type = artifact_file.parent.name
                    if artifact_type not in stats["artifact_types"]:
                        stats["artifact_types"][artifact_type] = 0
                    stats["artifact_types"][artifact_type] += 1

        # Find oldest and newest threads
        if thread_times:
            thread_times.sort(key=lambda x: x[1])
            stats["oldest_thread"] = thread_times[0][0]
            stats["newest_thread"] = thread_times[-1][0]

        return stats
