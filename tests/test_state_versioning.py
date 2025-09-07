#!/usr/bin/env python3
"""Tests for state versioning and migration system."""

import json
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from multi_agent_workflow.state_versioning import (
    CURRENT_STATE_VERSION,
    RollbackPoint,
    StateChecksum,
    StateMigrationRegistry,
    StateRollbackManager,
)
from multi_agent_workflow.workflow_state import (
    StageStatus,
    WorkflowInputs,
    WorkflowState,
)


class TestStateMigrationRegistry(unittest.TestCase):
    """Test state migration registry functionality."""

    def setUp(self):
        """Set up test environment."""
        self.registry = StateMigrationRegistry()

    def test_initialize_versions(self):
        """Test that default versions are registered."""
        self.assertIn("1.0.0", self.registry.versions)
        self.assertIn("2.0.0", self.registry.versions)

        v1 = self.registry.get_version("1.0.0")
        self.assertEqual(v1.description, "Initial workflow state schema")

        v2 = self.registry.get_version("2.0.0")
        self.assertIsNotNone(v2.migration_fn)

    def test_get_migration_path(self):
        """Test getting migration path between versions."""
        # Test no migration needed
        path = self.registry.get_migration_path("1.0.0", "1.0.0")
        self.assertEqual(path, [])

        # Test forward migration
        path = self.registry.get_migration_path("1.0.0", "2.0.0")
        self.assertEqual(len(path), 1)
        self.assertEqual(path[0].version, "2.0.0")

        # Test invalid version
        path = self.registry.get_migration_path("1.0.0", "99.0.0")
        self.assertEqual(path, [])

    def test_migrate_1_0_to_2_0(self):
        """Test migration from v1.0.0 to v2.0.0."""
        # Create v1.0.0 state data
        v1_data = {
            "workflow_id": "test_workflow",
            "created_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
            "stages": {"test_stage": {"name": "test_stage", "status": "completed"}},
        }

        # Migrate to v2.0.0
        v2_data = self.registry.migrate(v1_data, "2.0.0")

        # Check new fields added
        self.assertEqual(v2_data["version"], "2.0.0")
        self.assertIn("state_checksum", v2_data)
        self.assertIn("rollback_history", v2_data)
        self.assertIn("stage_dependencies", v2_data)

        # Check stage enhancements
        stage = v2_data["stages"]["test_stage"]
        self.assertIn("checksum", stage)
        self.assertIn("retry_count", stage)
        self.assertIn("dependencies", stage)

    def test_calculate_state_checksum(self):
        """Test state checksum calculation."""
        state_data = {
            "workflow_id": "test",
            "stages": {},
            "updated_at": "2025-01-01T00:00:00",  # This should be excluded
        }

        checksum1 = self.registry._calculate_state_checksum(state_data)
        self.assertEqual(len(checksum1), 64)  # SHA256 hex length

        # Same data should produce same checksum
        checksum2 = self.registry._calculate_state_checksum(state_data)
        self.assertEqual(checksum1, checksum2)

        # Different data should produce different checksum
        state_data["workflow_id"] = "different"
        checksum3 = self.registry._calculate_state_checksum(state_data)
        self.assertNotEqual(checksum1, checksum3)


class TestStateChecksum(unittest.TestCase):
    """Test state checksum utilities."""

    def test_calculate_stage_checksum(self):
        """Test stage checksum calculation."""
        stage_data = {
            "name": "test_stage",
            "status": "completed",
            "output_files": ["file1.txt", "file2.txt"],
            "metrics": {"duration": 10.5},
        }

        checksum = StateChecksum.calculate_stage_checksum(stage_data)
        self.assertEqual(len(checksum), 64)

        # Order of output files shouldn't matter (they're sorted)
        stage_data["output_files"] = ["file2.txt", "file1.txt"]
        checksum2 = StateChecksum.calculate_stage_checksum(stage_data)
        self.assertEqual(checksum, checksum2)

    def test_calculate_workflow_checksum(self):
        """Test workflow checksum calculation."""
        workflow_data = {
            "workflow_id": "test_workflow",
            "inputs_checksum": "abc123",
            "stages": {
                "stage1": {"name": "stage1", "status": "completed"},
                "stage2": {"name": "stage2", "status": "pending"},
            },
        }

        checksum = StateChecksum.calculate_workflow_checksum(workflow_data)
        self.assertEqual(len(checksum), 64)

        # Changing stage should change checksum
        workflow_data["stages"]["stage1"]["status"] = "failed"
        checksum2 = StateChecksum.calculate_workflow_checksum(workflow_data)
        self.assertNotEqual(checksum, checksum2)

    def test_verify_integrity(self):
        """Test state integrity verification."""
        # Create state with checksum
        registry = StateMigrationRegistry()
        state_data = {"workflow_id": "test", "stages": {}}
        state_data["state_checksum"] = registry._calculate_state_checksum(state_data)

        # Verify valid state
        is_valid, error = StateChecksum.verify_integrity(state_data)
        self.assertTrue(is_valid)
        self.assertIsNone(error)

        # Corrupt the state
        state_data["workflow_id"] = "corrupted"
        is_valid, error = StateChecksum.verify_integrity(state_data)
        self.assertFalse(is_valid)
        self.assertIn("Checksum mismatch", error)


class TestRollbackPoint(unittest.TestCase):
    """Test rollback point functionality."""

    def test_rollback_point_serialization(self):
        """Test rollback point to/from dict conversion."""
        point = RollbackPoint(
            timestamp=datetime.now(UTC),
            stage_name="test_stage",
            stage_status="completed",
            state_checksum="abc123def456",
            description="Test rollback point",
        )

        # Convert to dict
        data = point.to_dict()
        self.assertIn("timestamp", data)
        self.assertEqual(data["stage_name"], "test_stage")
        self.assertEqual(data["description"], "Test rollback point")

        # Convert back from dict
        restored = RollbackPoint.from_dict(data)
        self.assertEqual(restored.stage_name, point.stage_name)
        self.assertEqual(restored.state_checksum, point.state_checksum)


class TestStateRollbackManager(unittest.TestCase):
    """Test state rollback manager functionality."""

    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.state_dir = Path(self.temp_dir) / "rollback"
        self.manager = StateRollbackManager(self.state_dir)

    def test_create_rollback_point(self):
        """Test creating a rollback point."""
        workflow_state = {
            "workflow_id": "test_workflow",
            "current_stage": "stage1",
            "updated_at": datetime.now(UTC).isoformat(),
            "stages": {},
        }

        point = self.manager.create_rollback_point(workflow_state, "Test checkpoint")

        self.assertEqual(point.description, "Test checkpoint")
        self.assertEqual(point.stage_name, "stage1")
        self.assertIsNotNone(point.state_checksum)

        # Check snapshot file was created
        snapshot_files = list(self.state_dir.glob("test_workflow_*.json"))
        self.assertEqual(len(snapshot_files), 1)

    def test_list_rollback_points(self):
        """Test listing rollback points."""
        workflow_id = "test_workflow"

        # Create multiple rollback points
        for i in range(3):
            state = {
                "workflow_id": workflow_id,
                "current_stage": f"stage{i}",
                "updated_at": datetime.now(UTC).isoformat(),
                "stages": {},
            }
            self.manager.create_rollback_point(state, f"Checkpoint {i}")

        # List rollback points
        points = self.manager.list_rollback_points(workflow_id)
        self.assertEqual(len(points), 3)

        # Should be sorted by timestamp (most recent first)
        timestamps = [p.timestamp for p in points]
        self.assertEqual(timestamps, sorted(timestamps, reverse=True))

    def test_restore_from_rollback(self):
        """Test restoring from a rollback point."""
        workflow_id = "test_workflow"
        original_state = {
            "workflow_id": workflow_id,
            "current_stage": "original_stage",
            "updated_at": datetime.now(UTC).isoformat(),
            "test_data": "original_value",
            "stages": {},
        }

        # Create rollback point
        point = self.manager.create_rollback_point(original_state, "Test restore")
        checksum_prefix = point.state_checksum[:8]

        # Restore from rollback
        restored_state = self.manager.restore_from_rollback(
            workflow_id, checksum_prefix
        )

        self.assertIsNotNone(restored_state)
        self.assertEqual(restored_state["workflow_id"], workflow_id)
        self.assertEqual(restored_state["current_stage"], "original_stage")
        self.assertEqual(restored_state["test_data"], "original_value")
        self.assertIn("restored_from", restored_state)

    def test_cleanup_old_rollbacks(self):
        """Test cleaning up old rollback points."""
        workflow_id = "test_workflow"

        # Create 15 rollback points
        for i in range(15):
            state = {
                "workflow_id": workflow_id,
                "current_stage": f"stage{i}",
                "updated_at": datetime.now(UTC).isoformat(),
                "stages": {},
            }
            self.manager.create_rollback_point(state, f"Checkpoint {i}")

        # Should have 15 snapshots
        snapshots = list(self.state_dir.glob(f"{workflow_id}_*.json"))
        self.assertEqual(len(snapshots), 15)

        # Cleanup, keeping only 5
        self.manager.cleanup_old_rollbacks(workflow_id, keep_count=5)

        # Should have only 5 snapshots remaining
        snapshots = list(self.state_dir.glob(f"{workflow_id}_*.json"))
        self.assertEqual(len(snapshots), 5)


class TestWorkflowStateWithVersioning(unittest.TestCase):
    """Test WorkflowState integration with versioning."""

    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.state_file = Path(self.temp_dir) / "test_state.json"

    def test_save_with_version_and_checksum(self):
        """Test saving workflow state with version and checksum."""
        workflow = WorkflowState("test_workflow", self.state_file)
        inputs = WorkflowInputs("Test project")
        workflow.set_inputs(inputs)

        # Start and complete a stage
        workflow.start_stage("requirements_analysis")
        workflow.complete_stage(
            "requirements_analysis", ["file1.txt"], {"duration": 5.0}
        )

        # Save state
        workflow.save()

        # Load saved state and check versioning fields
        with open(self.state_file) as f:
            saved_data = json.load(f)

        self.assertEqual(saved_data["version"], CURRENT_STATE_VERSION)
        self.assertIn("state_checksum", saved_data)
        self.assertIn("rollback_history", saved_data)
        self.assertIn("stage_dependencies", saved_data)

    def test_load_with_migration(self):
        """Test loading old version state with migration."""
        # Create v1.0.0 state file
        v1_state = {
            "workflow_id": "test_workflow",
            "created_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
            "inputs": {"project_description": "Test"},
            "stages": {
                "requirements_analysis": {
                    "name": "requirements_analysis",
                    "status": "completed",
                    "started_at": datetime.now(UTC).isoformat(),
                    "completed_at": datetime.now(UTC).isoformat(),
                    "output_files": [],
                    "metrics": {},
                }
            },
        }

        with open(self.state_file, "w") as f:
            json.dump(v1_state, f)

        # Load state (should trigger migration)
        workflow = WorkflowState.load("test_workflow", self.state_file)

        self.assertIsNotNone(workflow)
        self.assertEqual(workflow.version, CURRENT_STATE_VERSION)

        # Check new fields are present (checksums are only calculated on completion)
        stage = workflow.stages["requirements_analysis"]
        self.assertIsNone(stage.checksum)  # Not calculated during migration
        self.assertEqual(stage.retry_count, 0)
        self.assertEqual(stage.dependencies, [])

    def test_rollback_to_checkpoint(self):
        """Test rolling back to a checkpoint."""
        workflow = WorkflowState("test_workflow", self.state_file)
        inputs = WorkflowInputs("Test project")
        workflow.set_inputs(inputs)

        # Complete first stage
        workflow.start_stage("requirements_analysis")
        workflow.complete_stage("requirements_analysis")
        workflow.save()

        # Get checksum for rollback
        if workflow.list_rollback_points():
            points = workflow.list_rollback_points()
            checkpoint = points[0]["state_checksum"][:8]

            # Make more changes
            workflow.start_stage("architecture_design")
            workflow.fail_stage("architecture_design", "Test failure")
            workflow.save()

            # Rollback to checkpoint
            success = workflow.rollback_to_checkpoint(checkpoint)
            self.assertTrue(success)

            # Check state was restored
            self.assertEqual(
                workflow.stages["architecture_design"].status, StageStatus.PENDING
            )


if __name__ == "__main__":
    unittest.main()
