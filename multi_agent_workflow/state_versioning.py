#!/usr/bin/env python3
"""
State Versioning and Migration System for Enhanced Multi-Agent Workflow

This module provides versioning and migration capabilities for workflow states,
ensuring backward compatibility and data integrity across version updates.
"""

import hashlib
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# Current state schema version
CURRENT_STATE_VERSION = "2.0.0"


@dataclass
class StateVersion:
    """Represents a state schema version with migration capabilities."""

    version: str
    description: str
    introduced_at: datetime
    migration_fn: Callable[[dict], dict] | None = None

    def __str__(self) -> str:
        return f"{self.version}: {self.description}"


class StateMigrationRegistry:
    """Registry for state schema versions and migration functions."""

    def __init__(self):
        self.versions: dict[str, StateVersion] = {}
        self._initialize_versions()

    def _initialize_versions(self):
        """Initialize known state versions and their migration functions."""

        # Version 1.0.0 - Initial state schema
        self.register_version(
            StateVersion(
                version="1.0.0",
                description="Initial workflow state schema",
                introduced_at=datetime(2025, 1, 1, tzinfo=UTC),
                migration_fn=None,  # Base version, no migration needed
            )
        )

        # Version 2.0.0 - Enhanced with checksums and rollback history
        self.register_version(
            StateVersion(
                version="2.0.0",
                description="Added state checksums, rollback history, and stage dependencies",
                introduced_at=datetime(2025, 1, 7, tzinfo=UTC),
                migration_fn=self._migrate_1_0_to_2_0,
            )
        )

    def register_version(self, version: StateVersion):
        """Register a new state version."""
        self.versions[version.version] = version
        logger.debug(f"Registered state version: {version}")

    def _migrate_1_0_to_2_0(self, state_data: dict) -> dict:
        """Migrate state from version 1.0.0 to 2.0.0."""
        logger.info("Migrating state from v1.0.0 to v2.0.0")

        # Add new fields introduced in v2.0.0
        state_data["version"] = "2.0.0"
        state_data["state_checksum"] = self._calculate_state_checksum(state_data)
        state_data["rollback_history"] = []
        state_data["stage_dependencies"] = {}

        # Enhance stage data with new fields
        for stage_name, stage_data in state_data.get("stages", {}).items():
            if "checksum" not in stage_data:
                stage_data["checksum"] = None
            if "retry_count" not in stage_data:
                stage_data["retry_count"] = 0
            if "dependencies" not in stage_data:
                stage_data["dependencies"] = []

        return state_data

    def _calculate_state_checksum(self, state_data: dict) -> str:
        """Calculate a checksum for the entire state data."""
        # Create a canonical representation (exclude volatile fields)
        canonical_data = {
            k: v
            for k, v in state_data.items()
            if k not in ["updated_at", "state_checksum", "version"]
        }

        json_str = json.dumps(canonical_data, sort_keys=True, default=str)
        return hashlib.sha256(json_str.encode("utf-8")).hexdigest()

    def get_version(self, version_str: str) -> StateVersion | None:
        """Get a specific version by its version string."""
        return self.versions.get(version_str)

    def get_migration_path(
        self, from_version: str, to_version: str
    ) -> list[StateVersion]:
        """Get the sequence of migrations needed to upgrade from one version to another."""
        if from_version == to_version:
            return []

        # Simple linear migration path for now (can be enhanced for complex graphs)
        versions = sorted(self.versions.keys())

        try:
            from_idx = versions.index(from_version)
            to_idx = versions.index(to_version)
        except ValueError as e:
            logger.error(f"Invalid version in migration path: {e}")
            return []

        if from_idx > to_idx:
            logger.error(f"Cannot downgrade from {from_version} to {to_version}")
            return []

        # Return versions that need to be applied in sequence
        migration_path = []
        for i in range(from_idx + 1, to_idx + 1):
            version = self.versions[versions[i]]
            if version.migration_fn:
                migration_path.append(version)

        return migration_path

    def migrate(
        self, state_data: dict, target_version: str = CURRENT_STATE_VERSION
    ) -> dict:
        """
        Migrate state data to the target version.

        Args:
            state_data: Current state data dictionary
            target_version: Target version to migrate to

        Returns:
            Migrated state data
        """
        current_version = state_data.get("version", "1.0.0")

        if current_version == target_version:
            logger.info(f"State already at version {target_version}")
            return state_data

        migration_path = self.get_migration_path(current_version, target_version)

        if not migration_path:
            logger.warning(
                f"No migration path from {current_version} to {target_version}"
            )
            return state_data

        logger.info(f"Migrating state from {current_version} to {target_version}")

        # Apply migrations in sequence
        migrated_data = state_data.copy()
        for version in migration_path:
            logger.info(f"Applying migration: {version}")
            if version.migration_fn:
                migrated_data = version.migration_fn(migrated_data)

        logger.info(f"Migration complete: {current_version} -> {target_version}")
        return migrated_data


class StateChecksum:
    """Utilities for calculating and verifying state checksums."""

    @staticmethod
    def calculate_stage_checksum(stage_data: dict) -> str:
        """Calculate checksum for a single stage."""
        # Include only deterministic fields
        canonical = {
            "name": stage_data.get("name"),
            "status": stage_data.get("status"),
            "output_files": sorted(stage_data.get("output_files", [])),
            "metrics": stage_data.get("metrics", {}),
        }

        json_str = json.dumps(canonical, sort_keys=True)
        return hashlib.sha256(json_str.encode("utf-8")).hexdigest()

    @staticmethod
    def calculate_workflow_checksum(workflow_data: dict) -> str:
        """Calculate checksum for entire workflow state."""
        # Build canonical representation
        canonical = {
            "workflow_id": workflow_data.get("workflow_id"),
            "inputs_checksum": workflow_data.get("inputs_checksum"),
            "stages": {},
        }

        # Add stage checksums
        for stage_name, stage_data in workflow_data.get("stages", {}).items():
            canonical["stages"][stage_name] = StateChecksum.calculate_stage_checksum(
                stage_data
            )

        json_str = json.dumps(canonical, sort_keys=True)
        return hashlib.sha256(json_str.encode("utf-8")).hexdigest()

    @staticmethod
    def verify_integrity(state_data: dict) -> tuple[bool, str | None]:
        """
        Verify the integrity of state data using checksums.

        Returns:
            Tuple of (is_valid, error_message)
        """
        stored_checksum = state_data.get("state_checksum")

        if not stored_checksum:
            return True, None  # No checksum to verify (older version)

        # Calculate current checksum
        registry = StateMigrationRegistry()
        calculated_checksum = registry._calculate_state_checksum(state_data)

        if stored_checksum != calculated_checksum:
            return (
                False,
                f"Checksum mismatch: expected {stored_checksum[:8]}..., got {calculated_checksum[:8]}...",
            )

        return True, None


@dataclass
class RollbackPoint:
    """Represents a point in workflow history that can be rolled back to."""

    timestamp: datetime
    stage_name: str
    stage_status: str
    state_checksum: str
    description: str

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "stage_name": self.stage_name,
            "stage_status": self.stage_status,
            "state_checksum": self.state_checksum,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RollbackPoint":
        """Create from dictionary."""
        return cls(
            timestamp=datetime.fromisoformat(data["timestamp"]),
            stage_name=data["stage_name"],
            stage_status=data["stage_status"],
            state_checksum=data["state_checksum"],
            description=data["description"],
        )


class StateRollbackManager:
    """Manages rollback points and state restoration."""

    def __init__(self, state_dir: Path | None = None):
        """
        Initialize rollback manager.

        Args:
            state_dir: Directory for storing rollback snapshots
        """
        if state_dir:
            self.state_dir = state_dir
        else:
            self.state_dir = Path(__file__).parent / "state" / "rollback"

        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.rollback_history: list[RollbackPoint] = []

    def create_rollback_point(
        self, workflow_state: dict, description: str
    ) -> RollbackPoint:
        """
        Create a rollback point from current state.

        Args:
            workflow_state: Current workflow state dictionary
            description: Human-readable description of this rollback point

        Returns:
            Created rollback point
        """
        # Calculate state checksum (add timestamp to avoid identical checksums)
        timestamp = datetime.now(UTC)
        state_with_timestamp = workflow_state.copy()
        state_with_timestamp["_rollback_timestamp"] = timestamp.isoformat()
        checksum = StateChecksum.calculate_workflow_checksum(state_with_timestamp)

        # Create rollback point
        rollback_point = RollbackPoint(
            timestamp=timestamp,
            stage_name=workflow_state.get("current_stage", "unknown"),
            stage_status="snapshot",
            state_checksum=checksum,
            description=description,
        )

        # Save snapshot to file (use both checksum and timestamp to ensure uniqueness)
        timestamp_str = timestamp.strftime("%Y%m%d_%H%M%S_%f")
        snapshot_file = (
            self.state_dir
            / f"{workflow_state['workflow_id']}_{checksum[:8]}_{timestamp_str}.json"
        )
        with open(snapshot_file, "w") as f:
            json.dump(workflow_state, f, indent=2, default=str)

        # Add to history
        self.rollback_history.append(rollback_point)

        logger.info(
            f"Created rollback point: {description} (checksum: {checksum[:8]}...)"
        )
        return rollback_point

    def list_rollback_points(self, workflow_id: str) -> list[RollbackPoint]:
        """List available rollback points for a workflow."""
        points = []

        # Scan rollback directory for snapshots
        pattern = f"{workflow_id}_*.json"
        for snapshot_file in self.state_dir.glob(pattern):
            try:
                with open(snapshot_file) as f:
                    data = json.load(f)

                # Extract checksum from filename (first 8 chars after workflow_id_)
                filename = snapshot_file.stem  # Remove .json extension
                if filename.startswith(f"{workflow_id}_"):
                    # Remove workflow_id_ prefix
                    remainder = filename[len(workflow_id) + 1 :]
                    # Checksum is the first 8 chars after workflow_id_
                    checksum = remainder[:8]
                else:
                    checksum = "unknown"

                # Extract rollback point info from snapshot
                point = RollbackPoint(
                    timestamp=datetime.fromisoformat(data["updated_at"]),
                    stage_name=data.get("current_stage", "unknown"),
                    stage_status="snapshot",
                    state_checksum=checksum,
                    description=f"Snapshot from {data['updated_at'][:19]}",
                )
                points.append(point)

            except Exception as e:
                logger.warning(
                    f"Failed to load rollback point from {snapshot_file}: {e}"
                )

        return sorted(points, key=lambda p: p.timestamp, reverse=True)

    def restore_from_rollback(self, workflow_id: str, checksum: str) -> dict | None:
        """
        Restore workflow state from a rollback point.

        Args:
            workflow_id: Workflow ID
            checksum: Checksum of the rollback point (can be partial, first 8 chars)

        Returns:
            Restored state dictionary or None if not found
        """
        # Find matching snapshot file - checksum is at position 1 in filename format
        # Format: {workflow_id}_{checksum}_{timestamp}.json
        matching_files = []
        for snapshot_file in self.state_dir.glob(f"{workflow_id}_*.json"):
            # Extract just the checksum part (position 1)
            filename = snapshot_file.stem  # Remove .json extension
            if filename.startswith(f"{workflow_id}_"):
                # Remove workflow_id_ prefix
                remainder = filename[len(workflow_id) + 1 :]
                # Checksum is the first 8 chars after workflow_id_
                file_checksum = remainder[:8]
                if file_checksum.startswith(checksum):
                    matching_files.append(snapshot_file)

        if not matching_files:
            logger.error(
                f"No rollback point found for {workflow_id} with checksum {checksum}"
            )
            return None

        if len(matching_files) > 1:
            logger.warning(
                f"Multiple rollback points match {checksum}, using most recent"
            )
            matching_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)

        snapshot_file = matching_files[0]

        try:
            with open(snapshot_file) as f:
                state_data = json.load(f)

            logger.info(f"Restored state from rollback point: {snapshot_file.name}")

            # Update restoration metadata
            state_data["restored_from"] = {
                "checksum": checksum,
                "timestamp": datetime.now(UTC).isoformat(),
                "file": snapshot_file.name,
            }

            return state_data

        except Exception as e:
            logger.error(f"Failed to restore from {snapshot_file}: {e}")
            return None

    def cleanup_old_rollbacks(self, workflow_id: str, keep_count: int = 10):
        """
        Clean up old rollback points, keeping only the most recent ones.

        Args:
            workflow_id: Workflow ID
            keep_count: Number of most recent rollbacks to keep
        """
        pattern = f"{workflow_id}_*.json"
        snapshots = list(self.state_dir.glob(pattern))

        if len(snapshots) <= keep_count:
            return

        # Sort by modification time (most recent first)
        snapshots.sort(key=lambda f: f.stat().st_mtime, reverse=True)

        # Delete old snapshots
        deleted_count = 0
        for snapshot in snapshots[keep_count:]:
            try:
                snapshot.unlink()
                deleted_count += 1
                logger.info(f"Deleted old rollback: {snapshot.name}")
            except Exception as e:
                logger.warning(f"Failed to delete {snapshot}: {e}")

        logger.info(
            f"Cleaned up {deleted_count} old rollback points, kept {len(snapshots[:keep_count])}"
        )


# Singleton instances for easy import
migration_registry = StateMigrationRegistry()
rollback_manager = StateRollbackManager()
