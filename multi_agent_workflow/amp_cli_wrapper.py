"""
Python wrapper for Amp CLI with conversation support, parallel execution isolation, and system prompt support.

Usage:
    # Basic usage
    amp = AmpCLI()
    response = amp.ask("what is 2+2?")  # 4
    response = amp.ask("add 5 to that")  # 9

    # With system prompt
    amp = AmpCLI(system_prompt="You are a helpful math tutor. Show your work.")
    response = amp.ask("what is 15 + 27?")  # Includes step-by-step explanation

    # Parallel execution with different roles
    tutor = AmpCLI(system_prompt="You are a math tutor. Show your work.")
    poet = AmpCLI(system_prompt="You are a poet. Respond in verse.")

    # These run in complete isolation with different behaviors
    math_answer = tutor.ask("What is 8 * 7?")   # Shows work
    poem_answer = poet.ask("What is 8 * 7?")    # Responds in verse

    # Context managers for automatic cleanup
    with AmpCLI(system_prompt="Be concise.") as amp:
        response = amp.ask("Explain quantum computing")
"""

import atexit
import os
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path


class AmpCLIError(Exception):
    """Exception raised for Amp CLI errors."""

    pass


class AmpCLI:
    """Python wrapper for Amp CLI with conversation support and isolation."""

    def __init__(self, isolated: bool = True, system_prompt: str | None = None):
        """
        Initialize the Amp CLI wrapper.

        Args:
            isolated: If True, creates an isolated environment for this instance.
                     This ensures multiple AmpCLI instances don't interfere with each other.
            system_prompt: If provided, this will be prepended to every message sent to Amp.
                          Useful for setting context or role instructions.
        """
        self._has_conversation = False
        self._isolated = isolated
        self._system_prompt = system_prompt
        self._instance_id = str(uuid.uuid4())[:8]
        self._work_dir: Path | None = None
        self._original_cwd: str | None = None
        self._thread_id: str | None = None

        if isolated:
            self._setup_isolation()
            atexit.register(self._cleanup)

    def _create_new_thread(self) -> str:
        """Create a new Amp thread for isolation."""
        try:
            cmd = ["amp", "threads", "new"]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                cwd=self._work_dir if self._work_dir else None,
            )
            thread_id = result.stdout.strip()
            return thread_id
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.strip() if e.stderr else "Unknown error"
            raise AmpCLIError(f"Failed to create new thread: {error_msg}") from e
        except FileNotFoundError:
            raise AmpCLIError(
                "Amp CLI not found. Make sure 'amp' is installed and in PATH."
            ) from None

    def _setup_isolation(self) -> None:
        """Set up isolated environment for this instance."""
        try:
            # Create temporary working directory
            self._work_dir = Path(
                tempfile.mkdtemp(prefix=f"amp_cli_{self._instance_id}_")
            )
            self._original_cwd = os.getcwd()

            # Change to isolated directory
            os.chdir(self._work_dir)

        except Exception as e:
            raise AmpCLIError(f"Failed to setup isolation: {e}") from e

    def _cleanup(self) -> None:
        """Clean up isolated environment."""
        try:
            # Restore original working directory
            if self._original_cwd and os.path.exists(self._original_cwd):
                os.chdir(self._original_cwd)

            # Remove temporary directory
            if self._work_dir and self._work_dir.exists():
                shutil.rmtree(self._work_dir, ignore_errors=True)

        except Exception:
            # Ignore cleanup errors to avoid disrupting the main program
            pass

    def _run_amp_command(self, cmd: list[str]) -> str:
        """
        Run an Amp CLI command with proper isolation.

        Args:
            cmd: Command list to execute

        Returns:
            Command output

        Raises:
            AmpCLIError: If the command fails
        """
        try:
            env = os.environ.copy()

            # Add instance-specific environment variables for additional isolation
            if self._isolated:
                env["AMP_INSTANCE_ID"] = self._instance_id
                env["AMP_WORK_DIR"] = str(self._work_dir)

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                cwd=self._work_dir if self._isolated else None,
                env=env,
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.strip() if e.stderr else "Unknown error"
            raise AmpCLIError(f"Amp CLI command failed: {error_msg}") from e
        except FileNotFoundError:
            raise AmpCLIError(
                "Amp CLI not found. Make sure 'amp' is installed and in PATH."
            ) from None

    def _format_message(self, message: str) -> str:
        """
        Format a message with optional system prompt.

        Args:
            message: The user message

        Returns:
            The formatted message with system prompt prepended if configured
        """
        if self._system_prompt:
            return f"{self._system_prompt}\n\n{message}"
        return message

    def prompt(self, message: str) -> str:
        """
        Start a new conversation with Amp CLI.

        Args:
            message: The prompt to send to Amp

        Returns:
            The response from Amp

        Raises:
            AmpCLIError: If the CLI command fails
        """
        formatted_message = self._format_message(message)

        if self._isolated:
            # Create a new thread for isolated execution
            self._thread_id = self._create_new_thread()
            # Use the created thread for the initial message too
            cmd = [
                "amp",
                "threads",
                "continue",
                self._thread_id,
                "-x",
                formatted_message,
            ]
        else:
            cmd = ["amp", "-x", formatted_message]

        response = self._run_amp_command(cmd)
        self._has_conversation = True
        return response

    def continue_conversation(self, message: str) -> str:
        """
        Continue an existing conversation with Amp CLI.

        Args:
            message: The prompt to send to Amp

        Returns:
            The response from Amp

        Raises:
            AmpCLIError: If the CLI command fails or no conversation exists
        """
        if not self._has_conversation:
            raise AmpCLIError("No active conversation. Use prompt() first.")

        formatted_message = self._format_message(message)

        if self._isolated and self._thread_id:
            cmd = [
                "amp",
                "threads",
                "continue",
                self._thread_id,
                "-x",
                formatted_message,
            ]
        else:
            cmd = ["amp", "threads", "continue", "-x", formatted_message]

        return self._run_amp_command(cmd)

    def ask(self, message: str) -> str:
        """
        Ask Amp a question, automatically choosing initial prompt or continue.

        Args:
            message: The prompt to send to Amp

        Returns:
            The response from Amp

        Raises:
            AmpCLIError: If the CLI command fails
        """
        if self._has_conversation:
            return self.continue_conversation(message)
        else:
            return self.prompt(message)

    def reset_conversation(self) -> None:
        """Reset the conversation state."""
        self._has_conversation = False
        if self._isolated:
            # Create a new thread for the next conversation
            self._thread_id = None

    @property
    def has_conversation(self) -> bool:
        """Check if there's an active conversation."""
        return self._has_conversation

    @property
    def instance_id(self) -> str:
        """Get the unique instance ID for this AmpCLI instance."""
        return self._instance_id

    @property
    def work_dir(self) -> Path | None:
        """Get the isolated working directory (if isolation is enabled)."""
        return self._work_dir

    @property
    def thread_id(self) -> str | None:
        """Get the Amp thread ID for this instance (if isolation is enabled)."""
        return self._thread_id

    @property
    def system_prompt(self) -> str | None:
        """Get the system prompt for this instance."""
        return self._system_prompt

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with cleanup."""
        if self._isolated:
            self._cleanup()


def main():
    """Example usage of the AmpCLI wrapper with system prompt."""

    print("=== Basic Usage ===")
    amp = AmpCLI()
    response = amp.ask("what is 2+2?")
    print(f"Basic: {response}")

    print("\n=== With System Prompt ===")
    tutor = AmpCLI(
        system_prompt="You are a helpful math tutor. Always show your work step by step."
    )

    try:
        print(f"System prompt: {tutor.system_prompt}")
        print(f"Instance ID: {tutor.instance_id}")

        response1 = tutor.ask("what is 15 + 27?")
        print(f"Tutor: {response1}")

        response2 = tutor.ask("now multiply that by 2")
        print(f"Tutor: {response2}")

    except AmpCLIError as e:
        print(f"Error: {e}")
    finally:
        tutor._cleanup()
        amp._cleanup()


if __name__ == "__main__":
    main()
