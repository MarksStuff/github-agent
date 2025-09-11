"""Mock implementation of tool nodes for testing."""

from datetime import datetime

from langgraph_workflow.interfaces.tool_interface import ToolNodesInterface
from langgraph_workflow.state import QualityState, WorkflowState


class MockToolNodes(ToolNodesInterface):
    """Mock implementation of tool nodes for testing."""

    def __init__(self, repo_path: str):
        """Initialize mock tool nodes."""
        self.repo_path = repo_path
        self.call_log = []  # Track method calls for verification
        self.test_failure_count = 0  # Control test failure simulation

    async def run_tests(self, state: WorkflowState) -> dict:
        """Mock test execution."""
        self.call_log.append("run_tests")
        
        # Simulate test results based on current state
        retry_count = state.get("retry_count", 0)
        
        # Fail first few attempts, then succeed
        if retry_count < 2 and self.test_failure_count < 2:
            test_passed = False
            self.test_failure_count += 1
            return_code = 1
            stderr = "Test failed: MockTest.test_feature failed"
            failed_tests = ["test_feature"]
        else:
            test_passed = True
            return_code = 0
            stderr = ""
            failed_tests = []
        
        state["test_results"] = {
            "returncode": return_code,
            "stdout": "Mock test output",
            "stderr": stderr,
            "passed": test_passed,
            "timestamp": datetime.now().isoformat(),
            "failed_tests": failed_tests,
            "summary": {"duration": 1.5, "tests": 10, "failures": len(failed_tests)}
        }
        
        # Update quality state
        state["quality_state"] = QualityState.OK if test_passed else QualityState.FAIL
        
        return state

    async def run_linter(self, state: WorkflowState) -> dict:
        """Mock linter execution."""
        self.call_log.append("run_linter")
        
        # Mock clean linter results
        state["lint_status"] = {
            "returncode": 0,
            "findings": [],
            "error_count": 0,
            "warning_count": 0,
            "passed": True,
            "timestamp": datetime.now().isoformat()
        }
        
        return state

    async def run_formatter(self, state: WorkflowState) -> dict:
        """Mock formatter execution."""
        self.call_log.append("run_formatter")
        
        # Mock formatter results
        format_status = {
            "returncode": 0,
            "stdout": "All files formatted",
            "stderr": "",
            "changed_files": ["main.py", "test_main.py"],
            "files_changed": 2,
            "timestamp": datetime.now().isoformat()
        }
        
        if "lint_status" not in state:
            state["lint_status"] = {}
        state["lint_status"]["format_applied"] = format_status
        
        return state

    async def apply_patch(self, state: WorkflowState, patch_content: str, target_file: str) -> dict:
        """Mock patch application."""
        self.call_log.append(f"apply_patch: {target_file}")
        
        # Mock successful patch application
        state["messages_window"].append({
            "role": "patch",
            "content": f"Applied patch to {target_file}",
            "success": True
        })
        
        return state

    async def check_ci_status(self, state: WorkflowState) -> dict:
        """Mock CI status check."""
        self.call_log.append("check_ci_status")
        
        pr_number = state.get("pr_number")
        if pr_number:
            # Mock CI status - passes after some time
            retry_count = state.get("retry_count", 0)
            
            if retry_count < 1:
                # Initially in progress
                ci_status = {
                    "checks": [
                        {"name": "test", "status": "in_progress", "conclusion": None},
                        {"name": "lint", "status": "completed", "conclusion": "success"}
                    ],
                    "all_passed": False,
                    "in_progress": True,
                    "timestamp": datetime.now().isoformat()
                }
            else:
                # Eventually all pass
                ci_status = {
                    "checks": [
                        {"name": "test", "status": "completed", "conclusion": "success"},
                        {"name": "lint", "status": "completed", "conclusion": "success"}
                    ],
                    "all_passed": True,
                    "in_progress": False,
                    "timestamp": datetime.now().isoformat()
                }
            
            state["ci_status"] = ci_status
        
        return state