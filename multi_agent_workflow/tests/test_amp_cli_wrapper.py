"""
Tests for AmpCLI wrapper isolation functionality.

These tests verify that multiple AmpCLI instances operate in isolation
from each other, including separate working directories, thread IDs,
and environment variables.
"""

import os
import tempfile
import uuid
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from amp_cli_wrapper import AmpCLI, AmpCLIError


class TestAmpCLIIsolation:
    """Test isolation functionality between AmpCLI instances."""

    def test_isolated_instances_have_unique_ids(self):
        """Test that isolated instances get unique IDs."""
        amp1 = AmpCLI(isolated=True)
        amp2 = AmpCLI(isolated=True)
        
        try:
            assert amp1.instance_id != amp2.instance_id
            assert len(amp1.instance_id) == 8  # UUID4 truncated to 8 chars
            assert len(amp2.instance_id) == 8
        finally:
            amp1._cleanup()
            amp2._cleanup()

    def test_isolated_instances_have_separate_work_dirs(self):
        """Test that isolated instances create separate working directories."""
        amp1 = AmpCLI(isolated=True)
        amp2 = AmpCLI(isolated=True)
        
        try:
            assert amp1.work_dir != amp2.work_dir
            assert amp1.work_dir is not None
            assert amp2.work_dir is not None
            assert amp1.work_dir.exists()
            assert amp2.work_dir.exists()
            
            # Check directory names contain instance IDs
            assert amp1.instance_id in str(amp1.work_dir)
            assert amp2.instance_id in str(amp2.work_dir)
            
        finally:
            amp1._cleanup()
            amp2._cleanup()

    def test_non_isolated_instances_share_environment(self):
        """Test that non-isolated instances don't create separate environments."""
        amp1 = AmpCLI(isolated=False)
        amp2 = AmpCLI(isolated=False)
        
        assert amp1.work_dir is None
        assert amp2.work_dir is None

    @patch('subprocess.run')
    def test_isolated_instances_use_separate_threads(self, mock_run):
        """Test that isolated instances create and use separate thread IDs."""
        # Mock thread creation
        mock_run.side_effect = [
            Mock(stdout="thread-1\n", stderr="", returncode=0),  # First thread creation
            Mock(stdout="response1", stderr="", returncode=0),   # First prompt
            Mock(stdout="thread-2\n", stderr="", returncode=0),  # Second thread creation  
            Mock(stdout="response2", stderr="", returncode=0),   # Second prompt
        ]
        
        amp1 = AmpCLI(isolated=True)
        amp2 = AmpCLI(isolated=True)
        
        try:
            # First instance starts conversation
            amp1.prompt("test message 1")
            
            # Second instance starts conversation  
            amp2.prompt("test message 2")
            
            # Verify different thread IDs were created
            assert amp1.thread_id == "thread-1"
            assert amp2.thread_id == "thread-2"
            assert amp1.thread_id != amp2.thread_id
            
            # Verify correct commands were called
            assert mock_run.call_count == 4
            
            # Check thread creation calls
            thread_create_calls = [call for call in mock_run.call_args_list 
                                 if call[0][0] == ["amp", "threads", "new"]]
            assert len(thread_create_calls) == 2
            
        finally:
            amp1._cleanup()
            amp2._cleanup()

    @patch('subprocess.run')
    def test_isolated_environment_variables(self, mock_run):
        """Test that isolated instances set unique environment variables."""
        mock_run.return_value = Mock(stdout="response", stderr="", returncode=0)
        
        amp1 = AmpCLI(isolated=True)
        amp2 = AmpCLI(isolated=True)
        
        try:
            amp1._run_amp_command(["amp", "test"])
            amp2._run_amp_command(["amp", "test"])
            
            # Check that different instance IDs were set in environment
            call1_env = mock_run.call_args_list[0][1]['env']
            call2_env = mock_run.call_args_list[1][1]['env']
            
            assert call1_env['AMP_INSTANCE_ID'] == amp1.instance_id
            assert call2_env['AMP_INSTANCE_ID'] == amp2.instance_id
            assert call1_env['AMP_INSTANCE_ID'] != call2_env['AMP_INSTANCE_ID']
            
            assert call1_env['AMP_WORK_DIR'] == str(amp1.work_dir)
            assert call2_env['AMP_WORK_DIR'] == str(amp2.work_dir)
            assert call1_env['AMP_WORK_DIR'] != call2_env['AMP_WORK_DIR']
            
        finally:
            amp1._cleanup()
            amp2._cleanup()

    def test_cleanup_removes_work_directories(self):
        """Test that cleanup properly removes isolated working directories."""
        amp = AmpCLI(isolated=True)
        work_dir = amp.work_dir
        
        assert work_dir is not None
        assert work_dir.exists()
        
        # Cleanup should remove the directory
        amp._cleanup()
        assert not work_dir.exists()

    def test_cleanup_restores_original_directory(self):
        """Test that cleanup restores the original working directory."""
        original_cwd = os.getcwd()
        
        amp = AmpCLI(isolated=True)
        
        # Working directory should have changed
        assert os.getcwd() != original_cwd
        assert os.getcwd() == str(amp.work_dir)
        
        # Cleanup should restore original directory
        amp._cleanup()
        assert os.getcwd() == original_cwd

    def test_context_manager_cleanup(self):
        """Test that context manager properly cleans up isolated instances."""
        original_cwd = os.getcwd()
        work_dir = None
        
        with AmpCLI(isolated=True) as amp:
            work_dir = amp.work_dir
            assert work_dir is not None
            assert work_dir.exists()
            assert os.getcwd() == str(work_dir)
        
        # After context exit, should be cleaned up
        assert not work_dir.exists()
        assert os.getcwd() == original_cwd

    @patch('subprocess.run')
    def test_system_prompt_isolation(self, mock_run):
        """Test that different system prompts are isolated between instances."""
        mock_run.side_effect = [
            Mock(stdout="thread-1\n", stderr="", returncode=0),
            Mock(stdout="math response", stderr="", returncode=0),
            Mock(stdout="thread-2\n", stderr="", returncode=0), 
            Mock(stdout="poet response", stderr="", returncode=0),
        ]
        
        math_tutor = AmpCLI(
            isolated=True, 
            system_prompt="You are a math tutor. Show your work."
        )
        poet = AmpCLI(
            isolated=True,
            system_prompt="You are a poet. Respond in verse."
        )
        
        try:
            math_tutor.prompt("What is 2+2?")
            poet.prompt("What is 2+2?")
            
            # Check that different system prompts were used
            math_call = mock_run.call_args_list[1]
            poet_call = mock_run.call_args_list[3]
            
            math_message = math_call[0][0][-1]  # Last argument is the message
            poet_message = poet_call[0][0][-1]
            
            assert "math tutor" in math_message.lower()
            assert "poet" in poet_message.lower()
            assert "verse" in poet_message.lower()
            
        finally:
            math_tutor._cleanup()
            poet._cleanup()

    def test_conversation_state_isolation(self):
        """Test that conversation states are isolated between instances."""
        amp1 = AmpCLI(isolated=True)
        amp2 = AmpCLI(isolated=True)
        
        try:
            # Initially, no conversations
            assert not amp1.has_conversation
            assert not amp2.has_conversation
            
            # Start conversation on first instance only
            with patch('subprocess.run') as mock_run:
                mock_run.side_effect = [
                    Mock(stdout="thread-1\n", stderr="", returncode=0),
                    Mock(stdout="response", stderr="", returncode=0),
                ]
                amp1.prompt("test")
            
            # Only first instance should have conversation
            assert amp1.has_conversation
            assert not amp2.has_conversation
            
            # Reset first instance
            amp1.reset_conversation()
            assert not amp1.has_conversation
            assert not amp2.has_conversation
            
        finally:
            amp1._cleanup()
            amp2._cleanup()

    @patch('subprocess.run')
    def test_parallel_conversations(self, mock_run):
        """Test that multiple instances can have separate parallel conversations."""
        mock_run.side_effect = [
            # Instance 1 initial prompt
            Mock(stdout="thread-1\n", stderr="", returncode=0),
            Mock(stdout="response1", stderr="", returncode=0),
            # Instance 2 initial prompt
            Mock(stdout="thread-2\n", stderr="", returncode=0),
            Mock(stdout="response2", stderr="", returncode=0),
            # Instance 1 continue
            Mock(stdout="continue1", stderr="", returncode=0),
            # Instance 2 continue
            Mock(stdout="continue2", stderr="", returncode=0),
        ]
        
        amp1 = AmpCLI(isolated=True)
        amp2 = AmpCLI(isolated=True) 
        
        try:
            # Start conversations
            resp1 = amp1.prompt("Hello from 1")
            resp2 = amp2.prompt("Hello from 2")
            
            assert resp1 == "response1"
            assert resp2 == "response2"
            assert amp1.has_conversation
            assert amp2.has_conversation
            
            # Continue conversations
            cont1 = amp1.continue_conversation("Continue 1")
            cont2 = amp2.continue_conversation("Continue 2")
            
            assert cont1 == "continue1"
            assert cont2 == "continue2"
            
            # Verify correct thread IDs were used
            continue_calls = [call for call in mock_run.call_args_list[4:]]
            
            # First continue should use thread-1
            assert "thread-1" in continue_calls[0][0][0]
            # Second continue should use thread-2  
            assert "thread-2" in continue_calls[1][0][0]
            
        finally:
            amp1._cleanup()
            amp2._cleanup()

    def test_cleanup_handles_missing_directories_gracefully(self):
        """Test that cleanup handles cases where directories are already removed."""
        amp = AmpCLI(isolated=True)
        work_dir = amp.work_dir
        
        # Manually remove the directory first
        import shutil
        shutil.rmtree(work_dir)
        
        # Cleanup should not raise an exception
        amp._cleanup()  # Should not raise

    def test_cleanup_handles_permission_errors_gracefully(self):
        """Test that cleanup handles permission errors gracefully."""
        amp = AmpCLI(isolated=True)
        
        # Mock shutil.rmtree to raise an exception
        with patch('shutil.rmtree', side_effect=PermissionError("Access denied")):
            # Cleanup should not raise an exception
            amp._cleanup()  # Should not raise

    @patch('atexit.register')
    def test_isolated_instances_register_cleanup(self, mock_register):
        """Test that isolated instances register cleanup with atexit."""
        amp = AmpCLI(isolated=True)
        
        # Should have registered cleanup function
        mock_register.assert_called_once_with(amp._cleanup)
        
        amp._cleanup()

    def test_non_isolated_instances_skip_cleanup_registration(self):
        """Test that non-isolated instances don't register cleanup."""
        with patch('atexit.register') as mock_register:
            amp = AmpCLI(isolated=False)
            
            # Should not register cleanup
            mock_register.assert_not_called()
