#!/usr/bin/env python3
"""
Error Handling Framework for Enhanced Multi-Agent Workflow System

This module provides comprehensive exception handling, error recovery strategies,
retry logic with exponential backoff, and error notification systems.
"""

import json
import logging
import time
import traceback
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional

try:
    from .output_manager import workflow_logger
    from .workflow_state import StageStatus, WorkflowState
except ImportError:
    # Fallback for when modules are not available
    from workflow_state import StageStatus, WorkflowState

logger = logging.getLogger(__name__)


class ErrorSeverity(Enum):
    """Severity levels for workflow errors."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """Categories of workflow errors."""

    STAGE_EXECUTION = "stage_execution"
    DEPENDENCY = "dependency"
    RESOURCE = "resource"
    VALIDATION = "validation"
    NETWORK = "network"
    FILESYSTEM = "filesystem"
    AUTHENTICATION = "authentication"
    TIMEOUT = "timeout"
    EXTERNAL_SERVICE = "external_service"
    CONFIGURATION = "configuration"


class RecoveryStrategy(Enum):
    """Recovery strategies for different error types."""

    RETRY = "retry"
    SKIP = "skip"
    ROLLBACK = "rollback"
    ABORT = "abort"
    MANUAL = "manual"
    ALTERNATIVE = "alternative"


@dataclass
class ErrorContext:
    """Context information for an error occurrence."""

    error_id: str
    timestamp: datetime
    stage_name: str
    workflow_id: str
    error_type: str
    error_message: str
    error_details: str
    severity: ErrorSeverity
    category: ErrorCategory
    recovery_strategy: RecoveryStrategy
    retry_count: int = 0
    max_retries: int = 3
    backoff_multiplier: float = 2.0
    base_delay: float = 1.0
    context_data: dict[str, Any] = None

    def __post_init__(self):
        """Initialize default values."""
        if self.context_data is None:
            self.context_data = {}

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "error_id": self.error_id,
            "timestamp": self.timestamp.isoformat(),
            "stage_name": self.stage_name,
            "workflow_id": self.workflow_id,
            "error_type": self.error_type,
            "error_message": self.error_message,
            "error_details": self.error_details,
            "severity": self.severity.value,
            "category": self.category.value,
            "recovery_strategy": self.recovery_strategy.value,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "backoff_multiplier": self.backoff_multiplier,
            "base_delay": self.base_delay,
            "context_data": self.context_data,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ErrorContext":
        """Create from dictionary."""
        return cls(
            error_id=data["error_id"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            stage_name=data["stage_name"],
            workflow_id=data["workflow_id"],
            error_type=data["error_type"],
            error_message=data["error_message"],
            error_details=data["error_details"],
            severity=ErrorSeverity(data["severity"]),
            category=ErrorCategory(data["category"]),
            recovery_strategy=RecoveryStrategy(data["recovery_strategy"]),
            retry_count=data.get("retry_count", 0),
            max_retries=data.get("max_retries", 3),
            backoff_multiplier=data.get("backoff_multiplier", 2.0),
            base_delay=data.get("base_delay", 1.0),
            context_data=data.get("context_data", {}),
        )


class WorkflowError(Exception):
    """Base exception class for workflow errors."""

    def __init__(
        self,
        message: str,
        error_context: Optional[ErrorContext] = None,
        category: ErrorCategory = ErrorCategory.STAGE_EXECUTION,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        recovery_strategy: RecoveryStrategy = RecoveryStrategy.RETRY,
    ):
        super().__init__(message)
        self.message = message
        self.error_context = error_context
        self.category = category
        self.severity = severity
        self.recovery_strategy = recovery_strategy


class StageExecutionError(WorkflowError):
    """Error during stage execution."""

    def __init__(self, message: str, stage_name: str, **kwargs):
        super().__init__(message, category=ErrorCategory.STAGE_EXECUTION, **kwargs)
        self.stage_name = stage_name


class DependencyError(WorkflowError):
    """Error related to missing or failed dependencies."""

    def __init__(self, message: str, dependency_name: str, **kwargs):
        super().__init__(message, category=ErrorCategory.DEPENDENCY, **kwargs)
        self.dependency_name = dependency_name


class ResourceError(WorkflowError):
    """Error related to resource availability or access."""

    def __init__(self, message: str, resource_name: str, **kwargs):
        super().__init__(message, category=ErrorCategory.RESOURCE, **kwargs)
        self.resource_name = resource_name


class ValidationError(WorkflowError):
    """Error during input or output validation."""

    def __init__(self, message: str, validation_field: str, **kwargs):
        super().__init__(message, category=ErrorCategory.VALIDATION, **kwargs)
        self.validation_field = validation_field


class NetworkError(WorkflowError):
    """Error related to network operations."""

    def __init__(self, message: str, **kwargs):
        super().__init__(message, category=ErrorCategory.NETWORK, **kwargs)


class TimeoutError(WorkflowError):
    """Error due to operation timeout."""

    def __init__(self, message: str, timeout_duration: float, **kwargs):
        super().__init__(message, category=ErrorCategory.TIMEOUT, **kwargs)
        self.timeout_duration = timeout_duration


class RetryableError(WorkflowError):
    """Base class for errors that can be retried."""

    def __init__(self, message: str, max_retries: int = 3, **kwargs):
        super().__init__(message, recovery_strategy=RecoveryStrategy.RETRY, **kwargs)
        self.max_retries = max_retries


class NonRetryableError(WorkflowError):
    """Base class for errors that should not be retried."""

    def __init__(self, message: str, **kwargs):
        super().__init__(message, recovery_strategy=RecoveryStrategy.ABORT, **kwargs)


class ErrorRecoveryManager:
    """Manages error recovery strategies and retry logic."""

    def __init__(self):
        """Initialize error recovery manager."""
        self.error_history: list[ErrorContext] = []
        self.recovery_handlers: dict[ErrorCategory, Callable] = {}
        self.error_log_file = Path(__file__).parent / "logs" / "error_log.json"
        self.error_log_file.parent.mkdir(parents=True, exist_ok=True)

        # Register default recovery handlers
        self._register_default_handlers()

    def _register_default_handlers(self):
        """Register default error recovery handlers."""
        self.recovery_handlers = {
            ErrorCategory.NETWORK: self._handle_network_error,
            ErrorCategory.TIMEOUT: self._handle_timeout_error,
            ErrorCategory.RESOURCE: self._handle_resource_error,
            ErrorCategory.DEPENDENCY: self._handle_dependency_error,
            ErrorCategory.EXTERNAL_SERVICE: self._handle_external_service_error,
        }

    def register_recovery_handler(
        self,
        category: ErrorCategory,
        handler: Callable[[ErrorContext, WorkflowState], bool],
    ):
        """
        Register a custom recovery handler for an error category.

        Args:
            category: Error category to handle
            handler: Callable that takes ErrorContext and WorkflowState, returns True if recovery successful
        """
        self.recovery_handlers[category] = handler
        logger.info(f"Registered recovery handler for {category.value} errors")

    def handle_error(
        self,
        error: Exception,
        stage_name: str,
        workflow_state: WorkflowState,
        context_data: Optional[dict[str, Any]] = None,
    ) -> ErrorContext:
        """
        Handle an error that occurred during workflow execution.

        Args:
            error: The exception that occurred
            stage_name: Name of the stage where error occurred
            workflow_state: Current workflow state
            context_data: Additional context data

        Returns:
            ErrorContext object with error details
        """
        # Extract error information
        error_id = f"{workflow_state.workflow_id}_{stage_name}_{int(time.time())}"
        error_type = type(error).__name__
        error_message = str(error)
        error_details = traceback.format_exc()

        # Determine error characteristics
        if isinstance(error, WorkflowError):
            category = error.category
            severity = error.severity
            recovery_strategy = error.recovery_strategy
        else:
            category = self._categorize_error(error)
            severity = self._assess_severity(error, stage_name)
            recovery_strategy = self._determine_recovery_strategy(error, category)

        # Create error context
        error_context = ErrorContext(
            error_id=error_id,
            timestamp=datetime.now(UTC),
            stage_name=stage_name,
            workflow_id=workflow_state.workflow_id,
            error_type=error_type,
            error_message=error_message,
            error_details=error_details,
            severity=severity,
            category=category,
            recovery_strategy=recovery_strategy,
            context_data=context_data or {},
        )

        # Add to error history
        self.error_history.append(error_context)

        # Log the error
        self._log_error(error_context)

        # Attempt recovery
        recovery_successful = self._attempt_recovery(error_context, workflow_state)

        if not recovery_successful:
            logger.error(f"Failed to recover from error {error_id}")

        return error_context

    def _categorize_error(self, error: Exception) -> ErrorCategory:
        """Categorize an error based on its type and message."""
        error_type = type(error).__name__.lower()
        error_message = str(error).lower()

        if "network" in error_message or "connection" in error_message:
            return ErrorCategory.NETWORK
        elif "timeout" in error_message or "timed out" in error_message:
            return ErrorCategory.TIMEOUT
        elif "file" in error_message or "directory" in error_message:
            return ErrorCategory.FILESYSTEM
        elif "permission" in error_message or "access" in error_message:
            return ErrorCategory.RESOURCE
        elif "validation" in error_message or "invalid" in error_message:
            return ErrorCategory.VALIDATION
        elif "dependency" in error_message or "missing" in error_message:
            return ErrorCategory.DEPENDENCY
        elif "auth" in error_message or "credential" in error_message:
            return ErrorCategory.AUTHENTICATION
        elif "config" in error_message or "setting" in error_message:
            return ErrorCategory.CONFIGURATION
        else:
            return ErrorCategory.STAGE_EXECUTION

    def _assess_severity(self, error: Exception, stage_name: str) -> ErrorSeverity:
        """Assess the severity of an error."""
        error_message = str(error).lower()

        # Critical errors
        if any(term in error_message for term in ["critical", "fatal", "corrupt"]):
            return ErrorSeverity.CRITICAL

        # High severity errors
        if any(term in error_message for term in ["security", "auth", "permission"]):
            return ErrorSeverity.HIGH

        # Low severity errors
        if any(term in error_message for term in ["warning", "deprecated", "minor"]):
            return ErrorSeverity.LOW

        # Default to medium severity
        return ErrorSeverity.MEDIUM

    def _determine_recovery_strategy(
        self, error: Exception, category: ErrorCategory
    ) -> RecoveryStrategy:
        """Determine the best recovery strategy for an error."""
        # Network and timeout errors are typically retryable
        if category in [
            ErrorCategory.NETWORK,
            ErrorCategory.TIMEOUT,
            ErrorCategory.EXTERNAL_SERVICE,
        ]:
            return RecoveryStrategy.RETRY

        # Resource errors might be retryable with delay
        if category == ErrorCategory.RESOURCE:
            return RecoveryStrategy.RETRY

        # Validation errors typically need manual intervention
        if category in [ErrorCategory.VALIDATION, ErrorCategory.AUTHENTICATION]:
            return RecoveryStrategy.MANUAL

        # Configuration errors should abort
        if category == ErrorCategory.CONFIGURATION:
            return RecoveryStrategy.ABORT

        # Default to retry for unknown errors
        return RecoveryStrategy.RETRY

    def _attempt_recovery(
        self, error_context: ErrorContext, workflow_state: WorkflowState
    ) -> bool:
        """
        Attempt to recover from an error using the appropriate strategy.

        Returns:
            True if recovery was successful, False otherwise
        """
        strategy = error_context.recovery_strategy

        if strategy == RecoveryStrategy.RETRY:
            return self._retry_with_backoff(error_context, workflow_state)
        elif strategy == RecoveryStrategy.SKIP:
            return self._skip_stage(error_context, workflow_state)
        elif strategy == RecoveryStrategy.ROLLBACK:
            return self._rollback_stage(error_context, workflow_state)
        elif strategy == RecoveryStrategy.ALTERNATIVE:
            return self._try_alternative(error_context, workflow_state)
        elif strategy == RecoveryStrategy.MANUAL:
            return self._request_manual_intervention(error_context, workflow_state)
        elif strategy == RecoveryStrategy.ABORT:
            return self._abort_workflow(error_context, workflow_state)

        return False

    def _retry_with_backoff(
        self, error_context: ErrorContext, workflow_state: WorkflowState
    ) -> bool:
        """
        Implement retry logic with exponential backoff.

        Returns:
            True if retry should be attempted, False if max retries exceeded
        """
        if error_context.retry_count >= error_context.max_retries:
            logger.error(
                f"Max retries ({error_context.max_retries}) exceeded for error {error_context.error_id}"
            )
            return False

        # Calculate backoff delay
        delay = error_context.base_delay * (
            error_context.backoff_multiplier**error_context.retry_count
        )

        logger.info(
            f"Retrying stage {error_context.stage_name} (attempt {error_context.retry_count + 1}/"
            f"{error_context.max_retries}) after {delay:.1f}s delay"
        )

        # Wait for backoff delay
        time.sleep(delay)

        # Increment retry count
        error_context.retry_count += 1

        # Update stage retry count in workflow state
        if error_context.stage_name in workflow_state.stages:
            stage = workflow_state.stages[error_context.stage_name]
            stage.retry_count = error_context.retry_count
            workflow_state.save()

        return True

    def _skip_stage(
        self, error_context: ErrorContext, workflow_state: WorkflowState
    ) -> bool:
        """Skip the failed stage and continue with the next one."""
        logger.info(f"Skipping failed stage: {error_context.stage_name}")

        if error_context.stage_name in workflow_state.stages:
            stage = workflow_state.stages[error_context.stage_name]
            stage.status = StageStatus.SKIPPED
            stage.error_message = f"Skipped due to error: {error_context.error_message}"
            workflow_state.save()

        return True

    def _rollback_stage(
        self, error_context: ErrorContext, workflow_state: WorkflowState
    ) -> bool:
        """Rollback to the previous stage."""
        logger.info(f"Rolling back from failed stage: {error_context.stage_name}")

        try:
            workflow_state.rollback_to_stage(error_context.stage_name)
            workflow_state.save()
            return True
        except Exception as e:
            logger.error(f"Failed to rollback stage {error_context.stage_name}: {e}")
            return False

    def _try_alternative(
        self, error_context: ErrorContext, workflow_state: WorkflowState
    ) -> bool:
        """Try an alternative approach for the failed stage."""
        logger.info(
            f"Attempting alternative approach for stage: {error_context.stage_name}"
        )

        # Check if there's a registered alternative handler
        if error_context.category in self.recovery_handlers:
            handler = self.recovery_handlers[error_context.category]
            return handler(error_context, workflow_state)

        return False

    def _request_manual_intervention(
        self, error_context: ErrorContext, workflow_state: WorkflowState
    ) -> bool:
        """Request manual intervention for the error."""
        logger.warning(
            f"Manual intervention required for stage {error_context.stage_name}: "
            f"{error_context.error_message}"
        )

        # Mark stage as paused for manual intervention
        if error_context.stage_name in workflow_state.stages:
            stage = workflow_state.stages[error_context.stage_name]
            stage.status = StageStatus.PAUSED
            stage.error_message = (
                f"Manual intervention required: {error_context.error_message}"
            )
            workflow_state.save()

        # This would typically trigger notifications to administrators
        self._send_error_notification(error_context)

        return False  # Manual intervention needed

    def _abort_workflow(
        self, error_context: ErrorContext, workflow_state: WorkflowState
    ) -> bool:
        """Abort the entire workflow due to critical error."""
        logger.error(
            f"Aborting workflow due to critical error: {error_context.error_message}"
        )

        # Mark current stage as failed
        if error_context.stage_name in workflow_state.stages:
            stage = workflow_state.stages[error_context.stage_name]
            stage.status = StageStatus.FAILED
            stage.error_message = f"Workflow aborted: {error_context.error_message}"
            workflow_state.save()

        # Send critical error notification
        self._send_error_notification(error_context)

        return False  # Workflow aborted

    # Default recovery handlers
    def _handle_network_error(
        self, error_context: ErrorContext, workflow_state: WorkflowState
    ) -> bool:
        """Handle network-related errors."""
        return self._retry_with_backoff(error_context, workflow_state)

    def _handle_timeout_error(
        self, error_context: ErrorContext, workflow_state: WorkflowState
    ) -> bool:
        """Handle timeout errors."""
        # Increase timeout for next retry
        error_context.base_delay *= 1.5
        return self._retry_with_backoff(error_context, workflow_state)

    def _handle_resource_error(
        self, error_context: ErrorContext, workflow_state: WorkflowState
    ) -> bool:
        """Handle resource availability errors."""
        # Wait longer for resource availability
        error_context.base_delay = max(error_context.base_delay, 5.0)
        return self._retry_with_backoff(error_context, workflow_state)

    def _handle_dependency_error(
        self, error_context: ErrorContext, workflow_state: WorkflowState
    ) -> bool:
        """Handle dependency errors."""
        # Try to skip the stage if dependency is optional
        if "optional" in error_context.error_message.lower():
            return self._skip_stage(error_context, workflow_state)
        else:
            return self._request_manual_intervention(error_context, workflow_state)

    def _handle_external_service_error(
        self, error_context: ErrorContext, workflow_state: WorkflowState
    ) -> bool:
        """Handle external service errors."""
        # Use longer backoff for external services
        error_context.backoff_multiplier = 3.0
        return self._retry_with_backoff(error_context, workflow_state)

    def _log_error(self, error_context: ErrorContext):
        """Log error details to file and console."""
        # Log to console
        logger.error(
            f"Workflow Error [{error_context.error_id}]: {error_context.error_message}"
        )
        logger.error(
            f"Stage: {error_context.stage_name}, Category: {error_context.category.value}"
        )
        logger.error(
            f"Severity: {error_context.severity.value}, Strategy: {error_context.recovery_strategy.value}"
        )

        # Log to file
        try:
            error_data = error_context.to_dict()

            # Read existing errors
            if self.error_log_file.exists():
                with open(self.error_log_file) as f:
                    existing_errors = json.load(f)
            else:
                existing_errors = []

            # Add new error
            existing_errors.append(error_data)

            # Keep only the last 1000 errors
            if len(existing_errors) > 1000:
                existing_errors = existing_errors[-1000:]

            # Write back to file
            with open(self.error_log_file, "w") as f:
                json.dump(existing_errors, f, indent=2, default=str)

        except Exception as e:
            logger.error(f"Failed to write error log: {e}")

    def _send_error_notification(self, error_context: ErrorContext):
        """Send error notification (placeholder for notification system)."""
        # This would integrate with notification systems like email, Slack, etc.
        logger.info(f"Error notification would be sent for {error_context.error_id}")

    def get_error_statistics(self, workflow_id: Optional[str] = None) -> dict[str, Any]:
        """Get error statistics for analysis."""
        errors = self.error_history

        if workflow_id:
            errors = [e for e in errors if e.workflow_id == workflow_id]

        if not errors:
            return {"total_errors": 0}

        # Calculate statistics
        by_category = {}
        by_severity = {}
        by_stage = {}

        for error in errors:
            # By category
            category = error.category.value
            by_category[category] = by_category.get(category, 0) + 1

            # By severity
            severity = error.severity.value
            by_severity[severity] = by_severity.get(severity, 0) + 1

            # By stage
            stage = error.stage_name
            by_stage[stage] = by_stage.get(stage, 0) + 1

        return {
            "total_errors": len(errors),
            "by_category": by_category,
            "by_severity": by_severity,
            "by_stage": by_stage,
            "recent_errors": [e.to_dict() for e in errors[-5:]],  # Last 5 errors
        }


def with_error_handling(
    stage_name: str,
    workflow_state: WorkflowState,
    error_manager: Optional[ErrorRecoveryManager] = None,
    max_retries: int = 3,
    context_data: Optional[dict[str, Any]] = None,
):
    """
    Decorator for adding error handling to stage execution functions.

    Args:
        stage_name: Name of the stage being executed
        workflow_state: Current workflow state
        error_manager: Error recovery manager instance
        max_retries: Maximum number of retry attempts
        context_data: Additional context data for error handling
    """
    if error_manager is None:
        error_manager = ErrorRecoveryManager()

    def decorator(func: Callable):
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    error_context = error_manager.handle_error(
                        e, stage_name, workflow_state, context_data
                    )

                    # If this was the last attempt or recovery failed, re-raise
                    if attempt == max_retries:
                        raise

                    # If recovery suggests not to retry, break
                    if error_context.recovery_strategy in [
                        RecoveryStrategy.ABORT,
                        RecoveryStrategy.MANUAL,
                        RecoveryStrategy.SKIP,
                    ]:
                        raise

            # Should not reach here
            raise RuntimeError(f"Unexpected error in stage {stage_name}")

        return wrapper

    return decorator


# Global error manager instance
error_manager = ErrorRecoveryManager()
