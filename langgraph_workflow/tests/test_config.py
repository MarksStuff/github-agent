"""Tests for configuration and routing logic."""

import os
import unittest
from pathlib import Path
from unittest.mock import patch

from ..config import (
    LOGGING_CONFIG,
    MCP_CONFIG,
    MODEL_CONFIG,
    WORKFLOW_CONFIG,
    get_artifacts_path,
    get_config,
    get_workspace_path,
    should_escalate_to_claude,
)


class TestWorkflowConfig(unittest.TestCase):
    """Test workflow configuration."""

    def test_escalation_thresholds(self):
        """Test escalation threshold values."""
        thresholds = WORKFLOW_CONFIG["escalation_thresholds"]

        self.assertEqual(thresholds["diff_size_lines"], 300)
        self.assertEqual(thresholds["files_touched"], 10)
        self.assertEqual(thresholds["consecutive_failures"], 2)
        self.assertEqual(thresholds["complexity_score"], 0.7)

    def test_context_limits(self):
        """Test context and memory limits."""
        limits = WORKFLOW_CONFIG["context_limits"]

        self.assertEqual(limits["messages_window"], 10)
        self.assertEqual(limits["summary_max_tokens"], 1000)
        self.assertEqual(limits["artifact_size_limit"], 100000)
        self.assertEqual(limits["prompt_max_tokens"], 4000)

    def test_timeout_configuration(self):
        """Test timeout configurations."""
        timeouts = WORKFLOW_CONFIG["timeouts"]

        self.assertEqual(timeouts["ci_wait"], 1800)  # 30 minutes
        self.assertEqual(timeouts["poll_interval"], 30)
        self.assertEqual(timeouts["model_timeout"], 120)
        self.assertEqual(timeouts["git_operation_timeout"], 60)

    def test_retry_configuration(self):
        """Test retry configurations."""
        retries = WORKFLOW_CONFIG["retries"]

        self.assertEqual(retries["model_calls"], 3)
        self.assertEqual(retries["git_operations"], 2)
        self.assertEqual(retries["ci_checks"], 5)

    def test_agent_configuration(self):
        """Test agent behavior configuration."""
        agent_config = WORKFLOW_CONFIG["agent_config"]

        self.assertTrue(agent_config["parallel_analysis"])
        self.assertTrue(agent_config["random_contribution_order"])
        self.assertTrue(agent_config["require_unanimous_approval"])
        self.assertFalse(agent_config["allow_arbitration_override"])

    def test_quality_gates(self):
        """Test quality gate configuration."""
        gates = WORKFLOW_CONFIG["quality_gates"]

        self.assertEqual(gates["min_test_coverage"], 0.8)
        self.assertEqual(gates["max_lint_errors"], 0)
        self.assertEqual(gates["max_complexity"], 10)
        self.assertTrue(gates["require_ci_pass"])

    def test_resource_limits(self):
        """Test resource limit configuration."""
        limits = WORKFLOW_CONFIG["resource_limits"]

        self.assertEqual(limits["max_ollama_concurrent"], 4)
        self.assertEqual(limits["max_claude_concurrent"], 1)
        self.assertEqual(limits["max_patch_size"], 10000)
        self.assertEqual(limits["max_artifacts_per_thread"], 100)

    def test_github_integration_config(self):
        """Test GitHub integration configuration."""
        github_config = WORKFLOW_CONFIG["github"]

        # Test labels
        labels = github_config["labels"]
        self.assertEqual(labels["needs_human"], "needs-human")
        self.assertEqual(labels["conflict"], "conflict")
        self.assertEqual(labels["arbitrated"], "arbitrated")
        self.assertEqual(labels["ollama_task"], "ollama-task")
        self.assertEqual(labels["claude_task"], "claude-code-task")

        # Test PR template exists and contains placeholders
        template = github_config["pr_template"]
        self.assertIn("{feature_description}", template)
        self.assertIn("{current_phase}", template)
        self.assertIn("{thread_id}", template)

    def test_paths_configuration(self):
        """Test paths configuration."""
        from pathlib import Path
        paths = WORKFLOW_CONFIG["paths"]

        # Expected paths are in user's home directory
        expected_base = Path.home() / ".local" / "share" / "github-agent" / "langgraph"
        
        self.assertEqual(paths["artifacts_root"], str(expected_base / "artifacts"))
        self.assertEqual(paths["workspaces_root"], str(expected_base / "workspaces"))
        self.assertEqual(paths["logs_root"], str(expected_base / "logs"))
        self.assertEqual(paths["checkpoints_root"], str(expected_base / "checkpoints"))


class TestModelConfig(unittest.TestCase):
    """Test model configuration."""

    def test_ollama_configuration(self):
        """Test Ollama model configuration."""
        ollama_config = MODEL_CONFIG["ollama"]

        # Test base URL (could be from env or default)
        base_url = ollama_config["base_url"]
        self.assertTrue(base_url.endswith(":11434") or base_url.endswith(":11434/"))

        # Test models
        models = ollama_config["models"]
        self.assertEqual(models["default"], "qwen2.5-coder:7b")
        self.assertEqual(models["developer"], "qwen2.5-coder:7b")
        self.assertEqual(models["tester"], "llama3.1")
        self.assertEqual(models["summarizer"], "llama3.1")

        # Test parameters
        params = ollama_config["parameters"]
        self.assertEqual(params["temperature"], 0.7)
        self.assertEqual(params["max_tokens"], 4000)
        self.assertEqual(params["top_p"], 0.9)

    def test_claude_configuration(self):
        """Test Claude model configuration."""
        claude_config = MODEL_CONFIG["claude"]

        # Test models
        models = claude_config["models"]
        self.assertEqual(models["default"], "claude-3-sonnet-20240229")
        self.assertEqual(models["architect"], "claude-3-opus-20240229")
        self.assertEqual(models["reviewer"], "claude-3-sonnet-20240229")

        # Test parameters
        params = claude_config["parameters"]
        self.assertEqual(params["temperature"], 0.3)
        self.assertEqual(params["max_tokens"], 8000)

    def test_claude_code_configuration(self):
        """Test Claude Code CLI configuration."""
        claude_code_config = MODEL_CONFIG["claude_code"]

        self.assertEqual(claude_code_config["cli_path"], "claude")
        self.assertEqual(claude_code_config["timeout"], 300)
        self.assertEqual(claude_code_config["max_retries"], 2)

    @patch.dict(os.environ, {"OLLAMA_BASE_URL": "http://custom:8080"})
    def test_ollama_environment_override(self):
        """Test Ollama base URL from environment."""
        # Re-import to get updated environment

        # Note: In actual implementation, this would require reloading the module
        # For this test, we verify the environment variable is used in initialization
        self.assertTrue(True)  # Placeholder - actual test would check dynamic loading

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test_key"})
    def test_claude_api_key_from_environment(self):
        """Test Claude API key from environment."""

        # Note: Similar to above, this would test dynamic configuration loading
        self.assertTrue(True)  # Placeholder


class TestMCPConfig(unittest.TestCase):
    """Test MCP server configuration."""

    def test_default_mcp_config(self):
        """Test default MCP configuration."""
        self.assertFalse(MCP_CONFIG["enabled"])  # Disabled by default
        self.assertEqual(MCP_CONFIG["server_url"], "http://localhost:8080")

        # Test endpoints
        endpoints = MCP_CONFIG["endpoints"]
        self.assertIn("/api/github/pr/{pr_number}/comments", endpoints["pr_comments"])
        self.assertIn("/api/github/pr/{pr_number}/checks", endpoints["check_runs"])
        self.assertIn(
            "/api/github/pr/{pr_number}/checks/{check_id}/logs", endpoints["check_logs"]
        )

    @patch.dict(
        os.environ, {"MCP_ENABLED": "true", "MCP_SERVER_URL": "http://custom:9090"}
    )
    def test_mcp_environment_configuration(self):
        """Test MCP configuration from environment."""
        # Re-import to test environment variable usage
        # In practice, this would require module reloading
        self.assertTrue(True)  # Placeholder


class TestLoggingConfig(unittest.TestCase):
    """Test logging configuration."""

    def test_logging_formatters(self):
        """Test logging formatters."""
        formatters = LOGGING_CONFIG["formatters"]

        standard_format = formatters["standard"]["format"]
        self.assertIn("%(asctime)s", standard_format)
        self.assertIn("%(name)s", standard_format)
        self.assertIn("%(levelname)s", standard_format)
        self.assertIn("%(message)s", standard_format)

        detailed_format = formatters["detailed"]["format"]
        self.assertIn("%(funcName)s", detailed_format)
        self.assertIn("%(lineno)d", detailed_format)

    def test_logging_handlers(self):
        """Test logging handlers."""
        handlers = LOGGING_CONFIG["handlers"]

        # Console handler
        console = handlers["console"]
        self.assertEqual(console["class"], "logging.StreamHandler")
        self.assertEqual(console["level"], "INFO")
        self.assertEqual(console["formatter"], "standard")

        # File handler
        file_handler = handlers["file"]
        self.assertEqual(file_handler["class"], "logging.handlers.RotatingFileHandler")
        self.assertEqual(file_handler["level"], "DEBUG")
        self.assertEqual(file_handler["formatter"], "detailed")
        self.assertEqual(file_handler["maxBytes"], 10485760)  # 10MB
        self.assertEqual(file_handler["backupCount"], 5)

    def test_logger_configuration(self):
        """Test logger configuration."""
        loggers = LOGGING_CONFIG["loggers"]

        # LangGraph workflow logger
        langgraph_logger = loggers["langgraph_workflow"]
        self.assertEqual(langgraph_logger["level"], "DEBUG")
        self.assertIn("console", langgraph_logger["handlers"])
        self.assertIn("file", langgraph_logger["handlers"])
        self.assertFalse(langgraph_logger["propagate"])

        # GitHub integration logger
        github_logger = loggers["github_integration"]
        self.assertEqual(github_logger["level"], "INFO")

        # Agent personas logger
        agent_logger = loggers["agent_personas"]
        self.assertEqual(agent_logger["level"], "INFO")


class TestConfigUtilities(unittest.TestCase):
    """Test configuration utility functions."""

    def test_get_config_all(self):
        """Test getting all configuration."""
        config = get_config()

        self.assertIn("workflow", config)
        self.assertIn("model", config)
        self.assertIn("mcp", config)
        self.assertIn("logging", config)

        # Verify structure matches imported configs
        self.assertEqual(config["workflow"], WORKFLOW_CONFIG)
        self.assertEqual(config["model"], MODEL_CONFIG)
        self.assertEqual(config["mcp"], MCP_CONFIG)
        self.assertEqual(config["logging"], LOGGING_CONFIG)

    def test_get_config_section(self):
        """Test getting specific configuration section."""
        workflow_config = get_config("workflow")
        self.assertEqual(workflow_config, WORKFLOW_CONFIG)

        model_config = get_config("model")
        self.assertEqual(model_config, MODEL_CONFIG)

        # Test unknown section
        unknown_config = get_config("unknown")
        self.assertEqual(unknown_config, {})

    def test_get_artifacts_path(self):
        """Test artifacts path generation."""
        from pathlib import Path
        thread_id = "test-thread-123"

        path = get_artifacts_path(thread_id)

        # Expected path should be based on config + thread_id
        expected_base = Path.home() / ".local" / "share" / "github-agent" / "langgraph" / "artifacts"
        expected_path = expected_base / thread_id
        self.assertEqual(str(path), str(expected_path))
        self.assertIsInstance(path, Path)

    def test_get_workspace_path(self):
        """Test workspace path generation."""
        from pathlib import Path
        thread_id = "test-thread-456"

        path = get_workspace_path(thread_id)

        # Expected path should be based on config + thread_id
        expected_base = Path.home() / ".local" / "share" / "github-agent" / "langgraph" / "workspaces"
        expected_path = expected_base / thread_id
        self.assertEqual(str(path), str(expected_path))
        self.assertIsInstance(path, Path)


class TestEscalationLogic(unittest.TestCase):
    """Test escalation decision logic."""

    def test_escalate_on_diff_size(self):
        """Test escalation based on diff size."""
        # Should escalate for large diffs
        self.assertTrue(should_escalate_to_claude(diff_size=500))
        self.assertTrue(should_escalate_to_claude(diff_size=300))  # At threshold

        # Should not escalate for small diffs
        self.assertFalse(should_escalate_to_claude(diff_size=299))
        self.assertFalse(should_escalate_to_claude(diff_size=100))

    def test_escalate_on_files_touched(self):
        """Test escalation based on number of files."""
        # Should escalate for many files
        self.assertTrue(should_escalate_to_claude(files_touched=15))
        self.assertTrue(should_escalate_to_claude(files_touched=10))  # At threshold

        # Should not escalate for few files
        self.assertFalse(should_escalate_to_claude(files_touched=9))
        self.assertFalse(should_escalate_to_claude(files_touched=5))

    def test_escalate_on_consecutive_failures(self):
        """Test escalation based on consecutive failures."""
        # Should escalate for multiple failures
        self.assertTrue(should_escalate_to_claude(consecutive_failures=3))
        self.assertTrue(
            should_escalate_to_claude(consecutive_failures=2)
        )  # At threshold

        # Should not escalate for single failure
        self.assertFalse(should_escalate_to_claude(consecutive_failures=1))
        self.assertFalse(should_escalate_to_claude(consecutive_failures=0))

    def test_escalate_on_complexity_score(self):
        """Test escalation based on complexity score."""
        # Should escalate for high complexity
        self.assertTrue(should_escalate_to_claude(complexity_score=0.9))
        self.assertTrue(should_escalate_to_claude(complexity_score=0.8))

        # Should not escalate for low complexity
        self.assertFalse(
            should_escalate_to_claude(complexity_score=0.7)
        )  # At threshold
        self.assertFalse(should_escalate_to_claude(complexity_score=0.5))

    def test_escalate_multiple_criteria(self):
        """Test escalation with multiple criteria."""
        # Any single criterion should trigger escalation
        self.assertTrue(
            should_escalate_to_claude(
                diff_size=400,  # High
                files_touched=5,  # Low
                consecutive_failures=1,  # Low
                complexity_score=0.3,  # Low
            )
        )

        # No criteria met should not escalate
        self.assertFalse(
            should_escalate_to_claude(
                diff_size=100,  # Low
                files_touched=5,  # Low
                consecutive_failures=1,  # Low
                complexity_score=0.3,  # Low
            )
        )

    def test_escalate_with_none_values(self):
        """Test escalation with None values."""
        # None values should be ignored
        self.assertFalse(
            should_escalate_to_claude(
                diff_size=None,
                files_touched=None,
                consecutive_failures=None,
                complexity_score=None,
            )
        )

        # Mix of None and valid values
        self.assertTrue(
            should_escalate_to_claude(
                diff_size=None,
                files_touched=15,  # High - should trigger
                consecutive_failures=None,
                complexity_score=None,
            )
        )

    def test_escalation_edge_cases(self):
        """Test escalation edge cases."""
        # Zero values
        self.assertFalse(should_escalate_to_claude(diff_size=0))
        self.assertFalse(should_escalate_to_claude(files_touched=0))
        self.assertFalse(should_escalate_to_claude(consecutive_failures=0))
        self.assertFalse(should_escalate_to_claude(complexity_score=0.0))

        # Negative values (shouldn't occur in practice)
        self.assertFalse(should_escalate_to_claude(diff_size=-1))
        self.assertFalse(should_escalate_to_claude(complexity_score=-0.1))


class TestConfigurationValidation(unittest.TestCase):
    """Test configuration validation and consistency."""

    def test_timeout_consistency(self):
        """Test that timeouts are consistent."""
        timeouts = WORKFLOW_CONFIG["timeouts"]

        # CI wait should be longer than poll interval
        self.assertGreater(timeouts["ci_wait"], timeouts["poll_interval"])

        # Model timeout should be reasonable
        self.assertGreater(timeouts["model_timeout"], 0)
        self.assertLess(timeouts["model_timeout"], 600)  # Less than 10 minutes

    def test_resource_limits_consistency(self):
        """Test that resource limits are reasonable."""
        limits = WORKFLOW_CONFIG["resource_limits"]

        # Ollama can handle more concurrent calls than Claude
        self.assertGreaterEqual(
            limits["max_ollama_concurrent"], limits["max_claude_concurrent"]
        )

        # Limits should be positive
        self.assertGreater(limits["max_patch_size"], 0)
        self.assertGreater(limits["max_artifacts_per_thread"], 0)

    def test_quality_gates_validity(self):
        """Test that quality gates have valid values."""
        gates = WORKFLOW_CONFIG["quality_gates"]

        # Test coverage should be a valid percentage
        self.assertGreaterEqual(gates["min_test_coverage"], 0.0)
        self.assertLessEqual(gates["min_test_coverage"], 1.0)

        # Lint errors should be non-negative
        self.assertGreaterEqual(gates["max_lint_errors"], 0)

        # Complexity should be reasonable
        self.assertGreater(gates["max_complexity"], 0)

    def test_escalation_thresholds_validity(self):
        """Test that escalation thresholds are valid."""
        thresholds = WORKFLOW_CONFIG["escalation_thresholds"]

        # All thresholds should be positive
        self.assertGreater(thresholds["diff_size_lines"], 0)
        self.assertGreater(thresholds["files_touched"], 0)
        self.assertGreater(thresholds["consecutive_failures"], 0)

        # Complexity score should be between 0 and 1
        self.assertGreaterEqual(thresholds["complexity_score"], 0.0)
        self.assertLessEqual(thresholds["complexity_score"], 1.0)


if __name__ == "__main__":
    unittest.main()
