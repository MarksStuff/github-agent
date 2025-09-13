"""Tests for startup validation functionality."""

import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import requests

from langgraph_workflow.startup_validation import (
    check_mock_mode,
    print_validation_results,
    run_startup_validation,
    validate_data_directories,
    validate_environment_variables,
    validate_ollama_connection,
    validate_required_models,
)


class TestValidateEnvironmentVariables:
    """Test environment variable validation."""

    def test_valid_anthropic_key(self):
        """Test with valid Anthropic API key."""
        with patch.dict(
            os.environ, {"ANTHROPIC_API_KEY": "sk-ant-123456789"}, clear=True
        ):
            result = validate_environment_variables()
            assert result["services"]["anthropic"] is True
            assert len(result["warnings"]) == 1  # Only GitHub warning

    def test_invalid_anthropic_key_format(self):
        """Test with invalid Anthropic API key format."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "invalid-key"}):
            result = validate_environment_variables()
            assert result["services"]["anthropic"] is False
            assert any(
                "ANTHROPIC_API_KEY not set or invalid format" in w
                for w in result["warnings"]
            )

    def test_missing_anthropic_key(self):
        """Test with missing Anthropic API key."""
        with patch.dict(os.environ, {}, clear=True):
            result = validate_environment_variables()
            assert result["services"]["anthropic"] is False
            assert any(
                "ANTHROPIC_API_KEY not set or invalid format" in w
                for w in result["warnings"]
            )

    def test_valid_github_token_ghp(self):
        """Test with valid GitHub token (ghp_ format)."""
        with patch.dict(os.environ, {"GITHUB_TOKEN": "ghp_123456789"}):
            result = validate_environment_variables()
            assert result["services"]["github"] is True

    def test_valid_github_token_pat(self):
        """Test with valid GitHub token (github_pat_ format)."""
        with patch.dict(os.environ, {"GITHUB_TOKEN": "github_pat_123456789"}):
            result = validate_environment_variables()
            assert result["services"]["github"] is True

    def test_invalid_github_token(self):
        """Test with invalid GitHub token format."""
        with patch.dict(os.environ, {"GITHUB_TOKEN": "invalid-token"}):
            result = validate_environment_variables()
            assert result["services"]["github"] is False
            assert any(
                "GITHUB_TOKEN not set or invalid format" in w
                for w in result["warnings"]
            )

    def test_all_valid_services(self):
        """Test with all valid environment variables."""
        with patch.dict(
            os.environ,
            {"ANTHROPIC_API_KEY": "sk-ant-123456789", "GITHUB_TOKEN": "ghp_123456789"},
        ):
            result = validate_environment_variables()
            assert result["services"]["anthropic"] is True
            assert result["services"]["github"] is True
            assert len(result["warnings"]) == 0


class TestValidateOllamaConnection:
    """Test Ollama connection validation."""

    @patch("requests.get")
    def test_ollama_connection_success(self, mock_get):
        """Test successful Ollama connection."""
        # Mock version endpoint
        version_response = Mock()
        version_response.status_code = 200
        version_response.json.return_value = {"version": "0.1.0"}

        # Mock models endpoint
        models_response = Mock()
        models_response.status_code = 200
        models_response.json.return_value = {
            "models": [{"name": "qwen2.5-coder:7b"}, {"name": "llama3.1:latest"}]
        }

        mock_get.side_effect = [version_response, models_response]

        result = validate_ollama_connection()

        assert result["valid"] is True
        assert result["version"] == "0.1.0"
        assert "qwen2.5-coder:7b" in result["models"]
        assert "llama3.1:latest" in result["models"]
        assert result["error"] is None

    @patch("requests.get")
    def test_ollama_connection_failure(self, mock_get):
        """Test failed Ollama connection."""
        mock_get.side_effect = requests.exceptions.ConnectionError("Connection refused")

        result = validate_ollama_connection()

        assert result["valid"] is False
        assert "Cannot connect to Ollama" in result["error"]

    @patch("requests.get")
    def test_ollama_timeout(self, mock_get):
        """Test Ollama connection timeout."""
        mock_get.side_effect = requests.exceptions.Timeout("Timeout")

        result = validate_ollama_connection()

        assert result["valid"] is False
        assert "Timeout connecting to Ollama" in result["error"]

    @patch("requests.get")
    def test_ollama_http_error(self, mock_get):
        """Test Ollama HTTP error response."""
        response = Mock()
        response.status_code = 500
        response.text = "Internal Server Error"
        mock_get.return_value = response

        result = validate_ollama_connection()

        assert result["valid"] is False
        assert "HTTP 500" in result["error"]

    @patch("requests.get")
    def test_ollama_custom_url(self, mock_get):
        """Test Ollama with custom URL."""
        version_response = Mock()
        version_response.status_code = 200
        version_response.json.return_value = {"version": "0.1.0"}

        models_response = Mock()
        models_response.status_code = 200
        models_response.json.return_value = {"models": []}

        mock_get.side_effect = [version_response, models_response]

        with patch.dict(os.environ, {"OLLAMA_BASE_URL": "http://custom:8080"}):
            result = validate_ollama_connection()

        assert result["url"] == "http://custom:8080"
        assert result["valid"] is True

        # Verify the correct URLs were called
        expected_calls = [
            ("http://custom:8080/api/version",),
            ("http://custom:8080/api/tags",),
        ]
        actual_calls = [call[0] for call in mock_get.call_args_list]
        assert actual_calls == expected_calls


class TestValidateRequiredModels:
    """Test required models validation."""

    def test_all_models_available(self):
        """Test when all required models are available."""
        ollama_results = {
            "models": ["qwen2.5-coder:7b", "llama3.1:latest", "other-model:v1"]
        }

        result = validate_required_models(ollama_results)

        assert result["valid"] is True
        assert len(result["missing_models"]) == 0

    def test_partial_match_models(self):
        """Test when models match partially (e.g., llama3.1:latest matches llama3.1)."""
        ollama_results = {"models": ["qwen2.5-coder:7b", "llama3.1:latest"]}

        result = validate_required_models(ollama_results)

        assert result["valid"] is True
        assert len(result["missing_models"]) == 0

    def test_missing_models(self):
        """Test when some required models are missing."""
        ollama_results = {"models": ["some-other-model:v1"]}

        result = validate_required_models(ollama_results)

        assert result["valid"] is False
        assert "qwen2.5-coder:7b" in result["missing_models"]
        assert "llama3.1" in result["missing_models"]

    def test_empty_models_list(self):
        """Test when no models are available."""
        ollama_results: dict[str, list[str]] = {"models": []}

        result = validate_required_models(ollama_results)

        assert result["valid"] is False
        assert len(result["missing_models"]) == 2

    def test_missing_models_key(self):
        """Test when models key is missing from ollama_results."""
        ollama_results: dict[str, list[str]] = {}

        result = validate_required_models(ollama_results)

        assert result["valid"] is False
        assert len(result["missing_models"]) == 2


class TestValidateDataDirectories:
    """Test data directories validation."""

    @patch("langgraph_workflow.config.get_checkpoint_path")
    @patch("langgraph_workflow.config.get_artifacts_path")
    def test_successful_directory_creation(
        self, mock_get_artifacts, mock_get_checkpoint
    ):
        """Test successful directory creation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Mock the config functions to return test paths
            mock_get_checkpoint.return_value = str(
                temp_path / "checkpoints" / "test.db"
            )
            mock_get_artifacts.return_value = temp_path / "artifacts"

            result = validate_data_directories()

            assert result["valid"] is True
            assert len(result["errors"]) == 0
            assert "checkpoints" in result["directories"]
            assert "artifacts" in result["directories"]

    @patch("langgraph_workflow.config.get_checkpoint_path")
    @patch("langgraph_workflow.config.get_artifacts_path")
    def test_directory_creation_failure(self, mock_get_artifacts, mock_get_checkpoint):
        """Test directory creation failure."""
        # Use an invalid path that should cause permission errors
        invalid_path = "/root/invalid/path"

        mock_get_checkpoint.return_value = f"{invalid_path}/test.db"
        mock_get_artifacts.return_value = Path(invalid_path)

        result = validate_data_directories()

        assert result["valid"] is False
        assert len(result["errors"]) > 0
        assert any(
            "Cannot create data directories" in error for error in result["errors"]
        )


class TestRunStartupValidation:
    """Test complete startup validation."""

    @patch("langgraph_workflow.startup_validation.validate_data_directories")
    @patch("langgraph_workflow.startup_validation.validate_ollama_connection")
    @patch("langgraph_workflow.startup_validation.validate_environment_variables")
    def test_all_validations_pass(self, mock_env, mock_ollama, mock_dirs):
        """Test when all validations pass."""
        # Setup successful responses
        mock_env.return_value = {
            "services": {"anthropic": True, "github": True},
            "warnings": [],
        }
        mock_ollama.return_value = {
            "valid": True,
            "models": ["qwen2.5-coder:7b", "llama3.1:latest"],
        }
        mock_dirs.return_value = {
            "valid": True,
            "directories": {
                "checkpoints": "/tmp/checkpoints",
                "artifacts": "/tmp/artifacts",
            },
            "errors": [],
        }

        result = run_startup_validation(verbose=False)

        assert result["overall_valid"] is True
        assert result["models"]["valid"] is True

    @patch("langgraph_workflow.startup_validation.validate_data_directories")
    @patch("langgraph_workflow.startup_validation.validate_ollama_connection")
    @patch("langgraph_workflow.startup_validation.validate_environment_variables")
    def test_directory_failure_makes_overall_invalid(
        self, mock_env, mock_ollama, mock_dirs
    ):
        """Test that directory failures make overall validation fail."""
        mock_env.return_value = {
            "services": {"anthropic": True, "github": True},
            "warnings": [],
        }
        mock_ollama.return_value = {"valid": True, "models": []}
        mock_dirs.return_value = {
            "valid": False,
            "directories": {},
            "errors": ["Permission denied"],
        }

        result = run_startup_validation(verbose=False)

        assert result["overall_valid"] is False

    @patch("langgraph_workflow.startup_validation.validate_data_directories")
    @patch("langgraph_workflow.startup_validation.validate_ollama_connection")
    @patch("langgraph_workflow.startup_validation.validate_environment_variables")
    def test_ollama_failure_does_not_break_overall(
        self, mock_env, mock_ollama, mock_dirs
    ):
        """Test that Ollama failures don't break overall validation (non-critical)."""
        mock_env.return_value = {
            "services": {"anthropic": True, "github": True},
            "warnings": [],
        }
        mock_ollama.return_value = {"valid": False, "error": "Connection failed"}
        mock_dirs.return_value = {"valid": True, "directories": {}, "errors": []}

        result = run_startup_validation(verbose=False)

        # Ollama failure should not make overall validation fail
        assert result["overall_valid"] is True
        assert result["models"]["valid"] is False

    @patch("langgraph_workflow.startup_validation.validate_data_directories")
    @patch("langgraph_workflow.startup_validation.validate_ollama_connection")
    @patch("langgraph_workflow.startup_validation.validate_environment_variables")
    def test_recommendations_generation(self, mock_env, mock_ollama, mock_dirs):
        """Test that appropriate recommendations are generated."""
        mock_env.return_value = {
            "services": {"anthropic": False, "github": False},
            "warnings": ["Missing keys"],
        }
        mock_ollama.return_value = {"valid": False, "error": "Connection failed"}
        mock_dirs.return_value = {"valid": True, "directories": {}, "errors": []}

        result = run_startup_validation(verbose=False)

        recommendations = result["recommendations"]
        assert any("ANTHROPIC_API_KEY" in rec for rec in recommendations)
        assert any("GITHUB_TOKEN" in rec for rec in recommendations)
        assert any("ollama serve" in rec for rec in recommendations)

    @patch("langgraph_workflow.startup_validation.print_validation_results")
    @patch("langgraph_workflow.startup_validation.validate_data_directories")
    @patch("langgraph_workflow.startup_validation.validate_ollama_connection")
    @patch("langgraph_workflow.startup_validation.validate_environment_variables")
    def test_verbose_mode_calls_print(
        self, mock_env, mock_ollama, mock_dirs, mock_print
    ):
        """Test that verbose mode calls print function."""
        mock_env.return_value = {
            "services": {"anthropic": True, "github": True},
            "warnings": [],
        }
        mock_ollama.return_value = {"valid": True, "models": []}
        mock_dirs.return_value = {"valid": True, "directories": {}, "errors": []}

        run_startup_validation(verbose=True)

        mock_print.assert_called_once()


class TestCheckMockMode:
    """Test mock mode detection."""

    def test_mock_mode_true(self):
        """Test when mock mode is enabled."""
        with patch.dict(os.environ, {"USE_MOCK_DEPENDENCIES": "true"}):
            assert check_mock_mode() is True

    def test_mock_mode_false(self):
        """Test when mock mode is disabled."""
        with patch.dict(os.environ, {"USE_MOCK_DEPENDENCIES": "false"}):
            assert check_mock_mode() is False

    def test_mock_mode_not_set(self):
        """Test when mock mode environment variable is not set."""
        with patch.dict(os.environ, {}, clear=True):
            assert check_mock_mode() is False

    def test_mock_mode_case_insensitive(self):
        """Test that mock mode detection is case insensitive."""
        with patch.dict(os.environ, {"USE_MOCK_DEPENDENCIES": "TRUE"}):
            assert check_mock_mode() is True

        with patch.dict(os.environ, {"USE_MOCK_DEPENDENCIES": "True"}):
            assert check_mock_mode() is True


class TestPrintValidationResults:
    """Test validation results printing."""

    @patch("builtins.print")
    def test_print_successful_validation(self, mock_print):
        """Test printing successful validation results."""
        results = {
            "overall_valid": True,
            "environment": {"services": {"anthropic": True, "github": True}},
            "ollama": {
                "valid": True,
                "url": "http://localhost:11434",
                "version": "0.1.0",
                "models": ["qwen2.5-coder:7b", "llama3.1:latest"],
            },
            "models": {"valid": True, "missing_models": []},
            "directories": {
                "valid": True,
                "directories": {
                    "checkpoints": "/tmp/checkpoints",
                    "artifacts": "/tmp/artifacts",
                },
            },
            "recommendations": [],
        }

        print_validation_results(results)

        # Verify that print was called (basic check)
        assert mock_print.called

        # Check for key content in the printed output
        printed_calls = [
            str(call[0][0]) if call[0] else ""
            for call in mock_print.call_args_list
            if call[0]
        ]
        printed_text = " ".join(printed_calls)
        assert "✅ Overall Status: READY" in printed_text or any(
            "READY" in call for call in printed_calls
        )
        assert "Connected:" in printed_text or any(
            "Connected" in call for call in printed_calls
        )

    @patch("builtins.print")
    def test_print_failed_validation(self, mock_print):
        """Test printing failed validation results."""
        results = {
            "overall_valid": False,
            "environment": {"services": {"anthropic": False, "github": False}},
            "ollama": {"valid": False, "error": "Connection failed"},
            "models": {"valid": False, "missing_models": ["qwen2.5-coder:7b"]},
            "directories": {"valid": False, "errors": ["Permission denied"]},
            "recommendations": ["Set ANTHROPIC_API_KEY", "Start Ollama service"],
        }

        print_validation_results(results)

        # Verify that print was called
        assert mock_print.called

        # Check for key failure content
        printed_calls = [
            str(call[0][0]) if call[0] else ""
            for call in mock_print.call_args_list
            if call[0]
        ]
        printed_text = " ".join(printed_calls)
        assert "NOT READY" in printed_text or any(
            "NOT READY" in call for call in printed_calls
        )
        assert "Connection failed" in printed_text or any(
            "Connection failed" in call for call in printed_calls
        )
        assert "ANTHROPIC_API_KEY" in printed_text or any(
            "ANTHROPIC_API_KEY" in call for call in printed_calls
        )


# Integration test
class TestStartupValidationIntegration:
    """Integration tests for startup validation."""

    def test_real_validation_without_services(self):
        """Test real validation when services are not available."""
        # Clear environment variables
        with patch.dict(os.environ, {}, clear=True):
            result = run_startup_validation(verbose=False)

            # Should still have valid overall status if directories work
            # (since service failures are non-critical)
            assert isinstance(result["overall_valid"], bool)
            assert "environment" in result
            assert "ollama" in result
            assert "directories" in result
            assert "recommendations" in result
