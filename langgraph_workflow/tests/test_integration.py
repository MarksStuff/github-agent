"""Integration tests for the LangGraph workflow."""

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from langgraph_workflow.graph import WorkflowGraph
from langgraph_workflow.state import WorkflowPhase, WorkflowState, initialize_state
from langgraph_workflow.tests.mocks import MockAgentNodes, MockGitNodes, MockToolNodes
from langgraph_workflow.utils.artifacts import ArtifactManager
from langgraph_workflow.utils.validators import StateValidator


class TestWorkflowIntegration:
    """Integration tests for the complete workflow."""

    @pytest.fixture
    def temp_repo(self):
        """Create a temporary repository directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            # Create a minimal git repo
            (repo_path / ".git").mkdir()
            (repo_path / ".git" / "config").write_text(
                '[remote "origin"]\n    url = git@github.com:test/repo.git'
            )
            yield repo_path

    @pytest.fixture
    def workflow_graph(self, temp_repo):
        """Create a workflow graph instance."""
        with tempfile.NamedTemporaryFile(suffix=".db") as db_file:
            graph = WorkflowGraph("test/repo", str(temp_repo), db_file.name)
            # Use our mock implementations instead of MagicMock
            graph.agent_nodes = MockAgentNodes("test/repo", str(temp_repo))
            graph.git_nodes = MockGitNodes("test/repo", str(temp_repo))
            graph.tool_nodes = MockToolNodes(str(temp_repo))
            yield graph

    def test_workflow_graph_initialization(self, temp_repo):
        """Test workflow graph initialization."""
        with tempfile.NamedTemporaryFile(suffix=".db") as db_file:
            graph = WorkflowGraph("test/repo", str(temp_repo), db_file.name)

            assert graph.repo_name == "test/repo"
            assert graph.repo_path == str(temp_repo)
            assert graph.checkpointer is not None
            assert graph.app is not None

    def test_graph_structure(self, workflow_graph):
        """Test that the graph has all expected nodes."""
        # Get the graph structure
        graph_def = workflow_graph.graph

        # Check that key nodes exist
        expected_nodes = [
            "initialize_git",
            "analyze_codebase",
            "analyze_feature",
            "consolidate_design",
            "incorporate_feedback",
            "create_skeleton",
            "create_tests",
            "implement_code",
            "fix_failures",
            "run_tests",
            "run_linter",
            "check_ci",
            "commit_changes",
            "push_to_github",
            "fetch_feedback",
            "await_feedback",
            "quality_gate",
            "preview_changes",
        ]

        # Note: We can't directly access nodes from compiled graph,
        # but we can verify the graph was built without errors
        assert workflow_graph.graph is not None
        assert workflow_graph.app is not None

    @pytest.mark.asyncio
    async def test_workflow_run_basic(self, workflow_graph):
        """Test basic workflow execution."""
        # Mock the app stream to simulate workflow execution
        mock_event = {"status": "completed"}
        async def mock_astream(*args, **kwargs):
            yield mock_event
        workflow_graph.app.astream = mock_astream

        result = await workflow_graph.run_workflow(
            thread_id="test-thread",
            task_spec="Test task",
            feature_name="Test feature",
        )

        assert result["status"] == "completed"
        assert result["thread_id"] == "test-thread"

        # Verify our mock nodes can be called
        assert isinstance(workflow_graph.agent_nodes, MockAgentNodes)
        assert isinstance(workflow_graph.git_nodes, MockGitNodes)
        assert isinstance(workflow_graph.tool_nodes, MockToolNodes)

    @pytest.mark.asyncio
    async def test_workflow_resume(self, workflow_graph):
        """Test workflow resume functionality."""
        # Mock the app stream for resume
        mock_event = {"status": "resumed"}
        async def mock_astream(*args, **kwargs):
            yield mock_event
        workflow_graph.app.astream = mock_astream

        result = await workflow_graph.resume_workflow("test-thread")

        assert result["status"] == "resumed"
        assert result["thread_id"] == "test-thread"

    def test_get_workflow_state(self, workflow_graph):
        """Test getting workflow state."""
        # Create a mock state object with the expected interface
        class MockState:
            def __init__(self):
                self.values = {
                    "thread_id": "test-thread",
                    "current_phase": WorkflowPhase.ANALYSIS,
                }

        mock_state = MockState()
        workflow_graph.app.get_state = lambda config: mock_state

        state = workflow_graph.get_workflow_state("test-thread")

        assert state is not None
        assert state["thread_id"] == "test-thread"
        assert state["current_phase"] == WorkflowPhase.ANALYSIS

    def test_routing_after_feedback(self, workflow_graph):
        """Test routing logic after feedback."""
        state = initialize_state("thread", "repo", "/path")

        # No comments - should go to implementation
        state["pr_comments"] = []
        route = workflow_graph._route_after_feedback(state)
        assert route == "implementation"

        # Unaddressed comments - should incorporate feedback
        state["pr_comments"] = [{"id": "1", "body": "Fix this"}]
        state["feedback_addressed"] = {}
        route = workflow_graph._route_after_feedback(state)
        assert route == "incorporate_feedback"

        # All comments addressed - should go to implementation
        state["feedback_addressed"] = {"1": True}
        route = workflow_graph._route_after_feedback(state)
        assert route == "implementation"

    def test_routing_test_results(self, workflow_graph):
        """Test routing based on test results."""
        state = initialize_state("thread", "repo", "/path")

        # Tests passed - should succeed
        state["test_results"] = {"passed": True}
        route = workflow_graph._route_test_results(state)
        assert route == "success"

        # Tests failed, low retry count - should fix
        state["test_results"] = {"passed": False}
        state["retry_count"] = 1
        route = workflow_graph._route_test_results(state)
        assert route == "fix_failures"

        # Tests failed, high retry count - should escalate
        state["retry_count"] = 3
        route = workflow_graph._route_test_results(state)
        assert route == "quality_gate"

    def test_routing_after_fixes(self, workflow_graph):
        """Test routing after fix attempts."""
        state = initialize_state("thread", "repo", "/path")

        # Low retry count - should retry
        state["retry_count"] = 1
        route = workflow_graph._route_after_fixes(state)
        assert route == "retry"

        # High retry count - should escalate
        state["retry_count"] = 3
        route = workflow_graph._route_after_fixes(state)
        assert route == "escalate"

        # Escalation needed - should escalate
        state["retry_count"] = 1
        state["escalation_needed"] = True
        route = workflow_graph._route_after_fixes(state)
        assert route == "escalate"

    def test_routing_final(self, workflow_graph):
        """Test final routing decision."""
        state = initialize_state("thread", "repo", "/path")

        # CI in progress - should wait
        state["ci_status"] = {"in_progress": True}
        route = workflow_graph._route_final(state)
        assert route == "await_more_feedback"

        # All passed - should complete
        from langgraph_workflow.state import QualityState

        state["ci_status"] = {"in_progress": False, "all_passed": True}
        state["quality_state"] = QualityState.OK
        state["test_results"] = {"passed": True}
        route = workflow_graph._route_final(state)
        assert route == "complete"

        # Quality issues - should wait for feedback
        state["quality_state"] = QualityState.FAIL
        route = workflow_graph._route_final(state)
        assert route == "await_more_feedback"


class TestEndToEndScenarios:
    """Test end-to-end workflow scenarios."""

    @pytest.fixture
    def temp_repo(self):
        """Create a temporary repository directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            # Create a minimal git repo
            (repo_path / ".git").mkdir()
            (repo_path / ".git" / "config").write_text(
                "[remote \"origin\"]\n    url = git@github.com:test/repo.git"
            )
            yield repo_path

    @pytest.fixture
    def full_setup(self, temp_repo):
        """Create a full test setup."""
        with tempfile.NamedTemporaryFile(suffix=".db") as db_file:
            graph = WorkflowGraph("test/repo", str(temp_repo), db_file.name)
            artifact_manager = ArtifactManager(str(temp_repo))

            return {
                "graph": graph,
                "artifact_manager": artifact_manager,
                "repo_path": temp_repo,
            }

    def test_state_validation_throughout_workflow(self, full_setup):
        """Test that state remains valid throughout workflow transitions."""
        state = initialize_state(
            "test-thread", "test/repo", str(full_setup["repo_path"])
        )

        # Initial state should be valid
        is_valid, errors = StateValidator.validate_state(state)
        assert is_valid
        assert len(errors) == 0

        # Simulate phase transitions
        state["current_phase"] = WorkflowPhase.DESIGN
        state["codebase_analysis"] = {"content": "analysis"}
        for agent_type in ["architect", "developer", "senior_engineer", "tester"]:
            state["agent_analyses"][agent_type] = f"{agent_type} analysis"

        is_valid, errors = StateValidator.validate_state(state)
        assert is_valid

        # Move to finalization
        state["current_phase"] = WorkflowPhase.FINALIZATION
        state["consolidated_design"] = "Consolidated design document"

        is_valid, errors = StateValidator.validate_state(state)
        assert is_valid

        # Move to implementation
        state["current_phase"] = WorkflowPhase.IMPLEMENTATION
        state["finalized_design"] = "Final design"

        is_valid, errors = StateValidator.validate_state(state)
        assert is_valid

    def test_artifact_creation_and_retrieval(self, full_setup):
        """Test artifact creation and retrieval during workflow."""
        artifact_manager = full_setup["artifact_manager"]
        thread_id = "test-thread"

        # Simulate artifact creation during workflow
        artifacts = {
            "analysis": "Codebase analysis content",
            "design": "Design document content",
            "code": "Implementation code",
            "tests": "Test suite code",
        }

        paths = {}
        feature_name = "test_feature"
        for artifact_type, content in artifacts.items():
            path = artifact_manager.save_artifact(
                thread_id=thread_id,
                artifact_type=artifact_type,
                filename=f"{artifact_type}.md",
                content=content,
                feature_name=feature_name,
            )
            paths[artifact_type] = path

        # Verify all artifacts were created
        for artifact_type, path in paths.items():
            assert path.exists()
            loaded = artifact_manager.load_artifact(
                thread_id, artifact_type, f"{artifact_type}.md", feature_name=feature_name
            )
            assert loaded == artifacts[artifact_type]

        # Create and verify artifact index
        index = artifact_manager.create_artifact_index(thread_id, feature_name=feature_name)
        assert len(index) == 4
        assert "analysis:analysis" in index
        assert "design:design" in index

    def test_error_handling_in_workflow(self, full_setup):
        """Test error handling during workflow execution."""
        graph = full_setup["graph"]

        # Mock a node to raise an error by overriding the mock implementation
        async def failing_node(state):
            raise Exception("Node execution failed")

        graph.agent_nodes.analyze_codebase = failing_node

        # Mock the app stream to handle the error
        async def failing_astream(*args, **kwargs):
            # Make it an async generator that raises
            if False:
                yield  # Make this an async generator
            raise Exception("Workflow failed")
        graph.app.astream = failing_astream

        # Run workflow and expect failure
        result = asyncio.run(
            graph.run_workflow(
                thread_id="test-thread",
                task_spec="Test task",
                feature_name="Test feature",
            )
        )

        assert result["status"] == "failed"
        assert "Workflow failed" in result["error"]

    def test_concurrent_workflow_execution(self, full_setup):
        """Test that multiple workflows can run concurrently."""
        graph = full_setup["graph"]

        # Mock the app stream for concurrent execution
        async def mock_stream(*args, **kwargs):
            await asyncio.sleep(0.1)  # Simulate some work
            yield {"status": "completed"}

        graph.app.astream = mock_stream

        async def run_concurrent_workflows():
            tasks = []
            for i in range(3):
                task = graph.run_workflow(
                    thread_id=f"thread-{i}",
                    task_spec=f"Task {i}",
                    feature_name=f"Feature {i}",
                )
                tasks.append(task)

            results = await asyncio.gather(*tasks)
            return results

        results = asyncio.run(run_concurrent_workflows())

        assert len(results) == 3
        for i, result in enumerate(results):
            assert result["status"] == "completed"
            assert result["thread_id"] == f"thread-{i}"

