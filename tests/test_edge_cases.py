"""
Test edge cases and error conditions for the simplified shutdown architecture.
"""


from exit_codes import ShutdownExitCode


class TestHealthMonitoringEdgeCases:
    """Test edge cases for health monitoring."""

    def test_simple_health_monitor_basic_ops(self, monitor_simple, test_logger):
        """Test basic operations of SimpleHealthMonitor."""
        test_logger.info("Testing basic health monitor operations")

        # Test start monitoring
        monitor_simple.start_monitoring()
        assert monitor_simple.is_running()

        # Test stop monitoring
        monitor_simple.stop_monitoring()
        assert not monitor_simple.is_running()

        test_logger.info("Basic health monitor operations test completed")

    def test_simple_health_monitor_double_start(self, monitor_simple, test_logger):
        """Test starting monitoring twice."""
        test_logger.info("Testing double start of health monitor")

        monitor_simple.start_monitoring()
        monitor_simple.start_monitoring()  # Should handle gracefully
        assert monitor_simple.is_running()

        monitor_simple.stop_monitoring()
        assert not monitor_simple.is_running()

        test_logger.info("Double start test completed")


class TestExitCodeEdgeCases:
    """Test edge cases for exit code management."""

    def test_exit_code_manager_creation(self, manager, test_logger):
        """Test basic exit code manager functionality."""
        test_logger.info("Testing exit code manager creation")

        # Should start with clean state
        exit_code = manager.determine_exit_code()
        assert exit_code == ShutdownExitCode.SUCCESS_CLEAN_SHUTDOWN

        test_logger.info(f"Initial exit code: {exit_code}")

    def test_timeout_reporting(self, manager, test_logger):
        """Test timeout reporting."""
        test_logger.info("Testing timeout reporting")

        manager.report_timeout("worker", 30.0)
        exit_code = manager.determine_exit_code()
        assert exit_code == ShutdownExitCode.TIMEOUT_WORKER_SHUTDOWN

        test_logger.info(f"Exit code after timeout: {exit_code}")

    def test_system_error_reporting(self, manager, test_logger):
        """Test system error reporting."""
        test_logger.info("Testing system error reporting")

        manager.report_system_error("signal", Exception("Test error"))
        exit_code = manager.determine_exit_code()
        assert exit_code == ShutdownExitCode.SIGNAL_HANDLER_ERROR

        test_logger.info(f"Exit code after system error: {exit_code}")
