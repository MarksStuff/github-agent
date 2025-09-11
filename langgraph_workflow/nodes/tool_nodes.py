"""Tool execution nodes for local operations."""

import json
import logging
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from langgraph_workflow.interfaces.tool_interface import ToolNodesInterface
from langgraph_workflow.state import QualityState, WorkflowState

logger = logging.getLogger(__name__)


class ToolNodes(ToolNodesInterface):
    """Local tool execution nodes."""

    def __init__(self, repo_path: str):
        """Initialize tool nodes with repository path."""
        self.repo_path = Path(repo_path)

    async def run_tests(self, state: WorkflowState) -> dict:
        """Execute tests and parse results."""
        logger.info("Running tests")

        try:
            # Run pytest with detailed output
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pytest",
                    "-xvs",
                    "--tb=short",
                    "--json-report",
                    "--json-report-file=/tmp/test_report.json",
                ],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=300,
            )

            # Parse results
            test_results = {
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "passed": result.returncode == 0,
                "timestamp": datetime.now().isoformat(),
            }

            # Try to parse JSON report if available
            json_report_path = Path("/tmp/test_report.json")
            if json_report_path.exists():
                try:
                    with open(json_report_path) as f:
                        report_data = json.load(f)

                    test_results.update(
                        {
                            "summary": report_data.get("summary", {}),
                            "failed_tests": [
                                test.get("nodeid", "unknown")
                                for test in report_data.get("tests", [])
                                if test.get("outcome") == "failed"
                            ],
                        }
                    )
                except Exception as e:
                    logger.warning(f"Could not parse JSON test report: {e}")

            # Update state
            state["test_results"] = test_results

            # Update quality state
            if test_results["passed"]:
                state["quality_state"] = QualityState.OK
                logger.info("All tests passed")
            else:
                state["quality_state"] = QualityState.FAIL
                logger.warning(
                    f"Tests failed with {len(test_results.get('failed_tests', []))} failures"
                )

            # Add to messages
            status = "PASSED" if test_results["passed"] else "FAILED"
            state["messages_window"].append(
                {
                    "role": "pytest",
                    "content": f"Test run: {status}",
                    "details": {
                        "failed_count": len(test_results.get("failed_tests", [])),
                        "total_time": test_results.get("summary", {}).get(
                            "duration", 0
                        ),
                    },
                }
            )

        except subprocess.TimeoutExpired:
            logger.error("Test execution timed out")
            state["test_results"] = {
                "returncode": -1,
                "stdout": "",
                "stderr": "Test execution timed out after 300 seconds",
                "passed": False,
                "timestamp": datetime.now().isoformat(),
            }
            state["quality_state"] = QualityState.FAIL

        except Exception as e:
            logger.error(f"Test execution failed: {e}")
            state["test_results"] = {
                "returncode": -1,
                "stdout": "",
                "stderr": str(e),
                "passed": False,
                "timestamp": datetime.now().isoformat(),
            }
            state["quality_state"] = QualityState.FAIL

        return state

    async def run_linter(self, state: WorkflowState) -> dict:
        """Execute linter and parse results."""
        logger.info("Running linter")

        try:
            # Run ruff check with JSON output
            result = subprocess.run(
                [sys.executable, "-m", "ruff", "check", "--output-format=json", "."],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
            )

            # Parse lint results
            lint_findings = []
            if result.stdout:
                try:
                    findings = json.loads(result.stdout)
                    lint_findings = findings
                except json.JSONDecodeError:
                    # Fallback for non-JSON output
                    lint_findings = [
                        {"message": line}
                        for line in result.stdout.split("\n")
                        if line.strip()
                    ]

            lint_status = {
                "returncode": result.returncode,
                "findings": lint_findings,
                "error_count": len(
                    [f for f in lint_findings if f.get("level") == "error"]
                ),
                "warning_count": len(
                    [f for f in lint_findings if f.get("level") == "warning"]
                ),
                "passed": result.returncode == 0,
                "timestamp": datetime.now().isoformat(),
            }

            state["lint_status"] = lint_status

            # Add to messages
            status = "CLEAN" if lint_status["passed"] else "ISSUES"
            state["messages_window"].append(
                {
                    "role": "ruff",
                    "content": f"Lint check: {status}",
                    "details": {
                        "errors": lint_status["error_count"],
                        "warnings": lint_status["warning_count"],
                    },
                }
            )

            logger.info(
                f"Lint check completed: {lint_status['error_count']} errors, {lint_status['warning_count']} warnings"
            )

        except Exception as e:
            logger.error(f"Linter execution failed: {e}")
            state["lint_status"] = {
                "returncode": -1,
                "findings": [],
                "error_count": 1,
                "warning_count": 0,
                "passed": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }

        return state

    async def run_formatter(self, state: WorkflowState) -> dict:
        """Execute formatter and auto-fix issues."""
        logger.info("Running formatter")

        try:
            # Run ruff format
            result = subprocess.run(
                [sys.executable, "-m", "ruff", "format", "."],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
            )

            # Check what was changed
            git_result = subprocess.run(
                ["git", "diff", "--name-only"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
            )

            changed_files = (
                git_result.stdout.strip().split("\n")
                if git_result.stdout.strip()
                else []
            )

            format_status = {
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "changed_files": changed_files,
                "files_changed": len(changed_files),
                "timestamp": datetime.now().isoformat(),
            }

            # Update lint status in state
            if "lint_status" not in state:
                state["lint_status"] = {}
            state["lint_status"]["format_applied"] = format_status

            # Add to messages
            state["messages_window"].append(
                {
                    "role": "ruff",
                    "content": f"Format applied to {len(changed_files)} files",
                }
            )

            logger.info(f"Formatter completed: {len(changed_files)} files changed")

        except Exception as e:
            logger.error(f"Formatter execution failed: {e}")
            format_status = {
                "returncode": -1,
                "error": str(e),
                "changed_files": [],
                "files_changed": 0,
                "timestamp": datetime.now().isoformat(),
            }

            if "lint_status" not in state:
                state["lint_status"] = {}
            state["lint_status"]["format_applied"] = format_status

        return state

    async def apply_patch(
        self, state: WorkflowState, patch_content: str, target_file: str
    ) -> dict:
        """Apply a unified diff patch to a file."""
        logger.info(f"Applying patch to {target_file}")

        try:
            # Write patch to temporary file
            patch_file = self.repo_path / ".tmp_patch"
            with open(patch_file, "w") as f:
                f.write(patch_content)

            # Apply patch using git apply
            result = subprocess.run(
                ["git", "apply", "--check", str(patch_file)],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                # Patch can be applied, do it
                subprocess.run(
                    ["git", "apply", str(patch_file)], cwd=self.repo_path, check=True
                )

                logger.info(f"Patch applied successfully to {target_file}")

                state["messages_window"].append(
                    {"role": "patch", "content": f"Applied patch to {target_file}"}
                )
            else:
                logger.error(f"Patch validation failed: {result.stderr}")
                state["messages_window"].append(
                    {
                        "role": "patch",
                        "content": f"Patch validation failed for {target_file}: {result.stderr}",
                        "error": True,
                    }
                )

            # Clean up
            patch_file.unlink(missing_ok=True)

        except Exception as e:
            logger.error(f"Patch application failed: {e}")
            state["messages_window"].append(
                {
                    "role": "system",
                    "content": f"Patch application failed: {e!s}",
                    "error": True,
                }
            )

        return state

    async def check_ci_status(self, state: WorkflowState) -> dict:
        """Check CI/CD status using GitHub CLI."""
        logger.info("Checking CI status")

        pr_number = state.get("pr_number")
        if not pr_number:
            logger.info("No PR number available for CI check")
            return state

        try:
            # Use gh CLI to check status
            result = subprocess.run(
                [
                    "gh",
                    "pr",
                    "checks",
                    str(pr_number),
                    "--json",
                    "name,status,conclusion",
                ],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                checks_data = json.loads(result.stdout)

                ci_status = {
                    "checks": checks_data,
                    "all_passed": all(
                        check.get("conclusion") == "success" for check in checks_data
                    ),
                    "in_progress": any(
                        check.get("status") == "in_progress" for check in checks_data
                    ),
                    "timestamp": datetime.now().isoformat(),
                }

                state["ci_status"] = ci_status

                # Add to messages
                status = (
                    "PASSED"
                    if ci_status["all_passed"]
                    else "IN_PROGRESS"
                    if ci_status["in_progress"]
                    else "FAILED"
                )
                state["messages_window"].append(
                    {
                        "role": "ci",
                        "content": f"CI status: {status}",
                        "details": {
                            "checks_count": len(checks_data),
                            "passed_count": len(
                                [
                                    c
                                    for c in checks_data
                                    if c.get("conclusion") == "success"
                                ]
                            ),
                        },
                    }
                )

                logger.info(f"CI status checked: {len(checks_data)} checks")

            else:
                logger.error(f"CI status check failed: {result.stderr}")

        except Exception as e:
            logger.error(f"CI status check failed: {e}")
            state["messages_window"].append(
                {
                    "role": "system",
                    "content": f"CI status check failed: {e!s}",
                    "error": True,
                }
            )

        return state
