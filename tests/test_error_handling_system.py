#!/usr/bin/env python3
"""Tests for error handling framework."""

import tempfile
import unittest
from datetime import UTC, datetime
from unittest.mock import patch

from multi_agent_workflow.error_handling import (
    ErrorCategory,
    ErrorContext,
    ErrorRecoveryManager,
    ErrorSeverity,
    NetworkError,
    RecoveryStrategy,
    RetryableError,
    StageExecutionError,
    TimeoutError,
    ValidationError,
    WorkflowError,
    with_error_handling,
)
from multi_agent_workflow.workflow_state import (
    StageStatus,
    WorkflowInputs,
    WorkflowState,
)


class TestErrorContext(unittest.TestCase):
    """Test ErrorContext functionality."""

    def test_error_context_creation(self):
        """Test creating error context."""
        context = ErrorContext(
            error_id="test_error_1",
            timestamp=datetime.now(UTC),
            stage_name="test_stage",
            workflow_id="test_workflow",
            error_type="ValueError",
            error_message="Test error message",
            error_details="Detailed traceback",
            severity=ErrorSeverity.HIGH,
            category=ErrorCategory.VALIDATION,
            recovery_strategy=RecoveryStrategy.RETRY,
        )

        self.assertEqual(context.error_id, "test_error_1")
        self.assertEqual(context.stage_name, "test_stage")
        self.assertEqual(context.severity, ErrorSeverity.HIGH)
        self.assertEqual(context.category, ErrorCategory.VALIDATION)
        self.assertEqual(context.recovery_strategy, RecoveryStrategy.RETRY)

    def test_error_context_serialization(self):
        """Test error context serialization."""
        context = ErrorContext(
            error_id="test_error_1",
            timestamp=datetime.now(UTC),
            stage_name="test_stage",
            workflow_id="test_workflow",
            error_type="ValueError",
            error_message="Test error message",
            error_details="Detailed traceback",
            severity=ErrorSeverity.HIGH,
            category=ErrorCategory.VALIDATION,
            recovery_strategy=RecoveryStrategy.RETRY,
        )

        # Convert to dict
        data = context.to_dict()
        self.assertIn("error_id", data)
        self.assertIn("timestamp", data)
        self.assertEqual(data["severity"], "high")
        self.assertEqual(data["category"], "validation")

        # Convert back from dict
        restored = ErrorContext.from_dict(data)
        self.assertEqual(restored.error_id, context.error_id)
        self.assertEqual(restored.severity, context.severity)
        self.assertEqual(restored.category, context.category)


class TestWorkflowErrors(unittest.TestCase):
    """Test workflow error classes."""

    def test_workflow_error_base(self):
        """Test base WorkflowError class."""
        error = WorkflowError(
            "Test error",
            category=ErrorCategory.NETWORK,
            severity=ErrorSeverity.MEDIUM,
            recovery_strategy=RecoveryStrategy.RETRY,
        )

        self.assertEqual(str(error), "Test error")
        self.assertEqual(error.category, ErrorCategory.NETWORK)
        self.assertEqual(error.severity, ErrorSeverity.MEDIUM)
        self.assertEqual(error.recovery_strategy, RecoveryStrategy.RETRY)

    def test_stage_execution_error(self):
        """Test StageExecutionError class."""
        error = StageExecutionError("Stage failed", "test_stage")
        self.assertEqual(error.stage_name, "test_stage")
        self.assertEqual(error.category, ErrorCategory.STAGE_EXECUTION)

    def test_network_error(self):
        """Test NetworkError class."""
        error = NetworkError("Connection failed")
        self.assertEqual(error.category, ErrorCategory.NETWORK)

    def test_timeout_error(self):
        """Test TimeoutError class."""
        error = TimeoutError("Operation timed out", timeout_duration=30.0)
        self.assertEqual(error.timeout_duration, 30.0)
        self.assertEqual(error.category, ErrorCategory.TIMEOUT)

    def test_retryable_error(self):
        """Test RetryableError class."""
        error = RetryableError("Temporary failure", max_retries=5)
        self.assertEqual(error.max_retries, 5)
        self.assertEqual(error.recovery_strategy, RecoveryStrategy.RETRY)


class TestErrorRecoveryManager(unittest.TestCase):
    """Test ErrorRecoveryManager functionality."""

    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.manager = ErrorRecoveryManager()
        self.workflow_state = WorkflowState("test_workflow")
        inputs = WorkflowInputs("Test project")
        self.workflow_state.set_inputs(inputs)

    def test_error_categorization(self):
        """Test automatic error categorization."""
        # Network error
        network_error = Exception("Connection timeout occurred")
        category = self.manager._categorize_error(network_error)
        self.assertEqual(category, ErrorCategory.NETWORK)

        # File error
        file_error = Exception("File not found: /path/to/file")
        category = self.manager._categorize_error(file_error)
        self.assertEqual(category, ErrorCategory.FILESYSTEM)

        # Validation error
        validation_error = Exception("Invalid input provided")
        category = self.manager._categorize_error(validation_error)
        self.assertEqual(category, ErrorCategory.VALIDATION)

    def test_severity_assessment(self):
        """Test error severity assessment."""
        # Critical error
        critical_error = Exception("Critical system failure")
        severity = self.manager._assess_severity(critical_error, "test_stage")
        self.assertEqual(severity, ErrorSeverity.CRITICAL)

        # Security error
        security_error = Exception("Authentication failed")
        severity = self.manager._assess_severity(security_error, "test_stage")
        self.assertEqual(severity, ErrorSeverity.HIGH)

        # Warning
        warning_error = Exception("Deprecated API warning")
        severity = self.manager._assess_severity(warning_error, "test_stage")
        self.assertEqual(severity, ErrorSeverity.LOW)

    def test_recovery_strategy_determination(self):
        """Test recovery strategy determination."""
        # Network error should be retryable
        strategy = self.manager._determine_recovery_strategy(
            NetworkError("Connection failed"), ErrorCategory.NETWORK
        )
        self.assertEqual(strategy, RecoveryStrategy.RETRY)

        # Validation error should require manual intervention
        strategy = self.manager._determine_recovery_strategy(
            ValidationError("Invalid data", "field"), ErrorCategory.VALIDATION
        )
        self.assertEqual(strategy, RecoveryStrategy.MANUAL)

    def test_handle_retryable_error(self):
        """Test handling retryable errors."""
        error = NetworkError("Connection failed")

        with patch.object(self.manager, "_log_error"):
            error_context = self.manager.handle_error(
                error, "test_stage", self.workflow_state
            )

        self.assertEqual(error_context.category, ErrorCategory.NETWORK)
        self.assertEqual(error_context.recovery_strategy, RecoveryStrategy.RETRY)
        self.assertIn(error_context, self.manager.error_history)

    def test_retry_with_backoff(self):
        """Test retry logic with exponential backoff."""
        error_context = ErrorContext(
            error_id="test_error",
            timestamp=datetime.now(UTC),
            stage_name="test_stage",
            workflow_id="test_workflow",
            error_type="NetworkError",
            error_message="Connection failed",
            error_details="",
            severity=ErrorSeverity.MEDIUM,
            category=ErrorCategory.NETWORK,
            recovery_strategy=RecoveryStrategy.RETRY,
            max_retries=2,
            base_delay=0.1,  # Small delay for testing
        )

        # First retry should succeed
        with patch("time.sleep") as mock_sleep:
            result = self.manager._retry_with_backoff(
                error_context, self.workflow_state
            )
            self.assertTrue(result)
            mock_sleep.assert_called_with(0.1)  # base_delay * (backoff_multiplier^0)
            self.assertEqual(error_context.retry_count, 1)

        # Second retry should succeed
        with patch("time.sleep") as mock_sleep:
            result = self.manager._retry_with_backoff(
                error_context, self.workflow_state
            )
            self.assertTrue(result)
            mock_sleep.assert_called_with(0.2)  # base_delay * (backoff_multiplier^1)
            self.assertEqual(error_context.retry_count, 2)

        # Third retry should fail (exceeded max_retries)
        result = self.manager._retry_with_backoff(error_context, self.workflow_state)
        self.assertFalse(result)
        self.assertEqual(error_context.retry_count, 2)  # Should not increment

    def test_skip_stage_recovery(self):
        """Test skipping a failed stage."""
        # Start a stage
        self.workflow_state.start_stage("test_stage")

        error_context = ErrorContext(
            error_id="test_error",
            timestamp=datetime.now(UTC),
            stage_name="test_stage",
            workflow_id="test_workflow",
            error_type="SkippableError",
            error_message="Non-critical error",
            error_details="",
            severity=ErrorSeverity.LOW,
            category=ErrorCategory.VALIDATION,
            recovery_strategy=RecoveryStrategy.SKIP,
        )

        result = self.manager._skip_stage(error_context, self.workflow_state)
        self.assertTrue(result)

        # Check that stage was marked as skipped
        stage = self.workflow_state.stages["test_stage"]
        self.assertEqual(stage.status, StageStatus.SKIPPED)
        self.assertIn("Skipped due to error", stage.error_message)

    def test_custom_recovery_handler(self):
        """Test registering custom recovery handlers."""

        # Create a custom handler
        def custom_handler(error_context, workflow_state):
            return True  # Always succeed

        # Register the handler
        self.manager.register_recovery_handler(
            ErrorCategory.EXTERNAL_SERVICE, custom_handler
        )

        # Check that handler was registered
        self.assertIn(ErrorCategory.EXTERNAL_SERVICE, self.manager.recovery_handlers)

        # Test the handler
        error_context = ErrorContext(
            error_id="test_error",
            timestamp=datetime.now(UTC),
            stage_name="test_stage",
            workflow_id="test_workflow",
            error_type="ServiceError",
            error_message="Service unavailable",
            error_details="",
            severity=ErrorSeverity.MEDIUM,
            category=ErrorCategory.EXTERNAL_SERVICE,
            recovery_strategy=RecoveryStrategy.ALTERNATIVE,
        )

        result = self.manager._try_alternative(error_context, self.workflow_state)
        self.assertTrue(result)

    def test_error_statistics(self):
        """Test error statistics collection."""
        # Add some errors to history
        errors = [
            ErrorContext(
                error_id=f"error_{i}",
                timestamp=datetime.now(UTC),
                stage_name="test_stage",
                workflow_id="test_workflow",
                error_type="TestError",
                error_message="Test error",
                error_details="",
                severity=ErrorSeverity.MEDIUM if i % 2 else ErrorSeverity.HIGH,
                category=ErrorCategory.NETWORK if i % 3 else ErrorCategory.VALIDATION,
                recovery_strategy=RecoveryStrategy.RETRY,
            )
            for i in range(5)
        ]

        self.manager.error_history.extend(errors)

        # Get statistics
        stats = self.manager.get_error_statistics()

        self.assertEqual(stats["total_errors"], 5)
        self.assertIn("by_category", stats)
        self.assertIn("by_severity", stats)
        self.assertIn("by_stage", stats)
        self.assertIn("recent_errors", stats)


class TestErrorHandlingDecorator(unittest.TestCase):
    """Test error handling decorator."""

    def setUp(self):
        """Set up test environment."""
        self.workflow_state = WorkflowState("test_workflow")
        inputs = WorkflowInputs("Test project")
        self.workflow_state.set_inputs(inputs)
        self.error_manager = ErrorRecoveryManager()

    def test_decorator_success(self):
        """Test decorator with successful function execution."""

        @with_error_handling(
            "test_stage", self.workflow_state, self.error_manager, max_retries=2
        )
        def test_function():
            return "success"

        result = test_function()
        self.assertEqual(result, "success")

    def test_decorator_retry_success(self):
        """Test decorator with retry on failure then success."""
        call_count = 0

        @with_error_handling(
            "test_stage", self.workflow_state, self.error_manager, max_retries=2
        )
        def test_function():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise RetryableError("Temporary failure")
            return "success"

        with patch.object(self.error_manager, "_retry_with_backoff", return_value=True):
            result = test_function()
            self.assertEqual(result, "success")
            self.assertEqual(call_count, 2)

    def test_decorator_max_retries_exceeded(self):
        """Test decorator when max retries are exceeded."""

        @with_error_handling(
            "test_stage", self.workflow_state, self.error_manager, max_retries=1
        )
        def test_function():
            raise RetryableError("Persistent failure")

        with patch.object(self.error_manager, "_retry_with_backoff", return_value=True):
            with self.assertRaises(RetryableError):
                test_function()

    def test_decorator_non_retryable_error(self):
        """Test decorator with non-retryable error."""

        @with_error_handling(
            "test_stage", self.workflow_state, self.error_manager, max_retries=2
        )
        def test_function():
            raise ValidationError("Invalid input", "field")

        with self.assertRaises(ValidationError):
            test_function()


if __name__ == "__main__":
    unittest.main()
