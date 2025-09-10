"""
Claude Code CLI wrapper that matches the AmpCLI interface.

This wrapper provides the same interface as AmpCLI but uses the Claude Code CLI
instead of Sourcegraph's Amp. It maintains separate persistent sessions for each
agent to provide isolated context.

Usage:
    # Basic usage (same as AmpCLI)
    claude = ClaudeCodeCLI()
    response = claude.ask("what is 2+2?")  # 4
    response = claude.ask("add 5 to that")  # 9

    # With system prompt
    claude = ClaudeCodeCLI(system_prompt="You are a helpful math tutor. Show your work.")
    response = claude.ask("what is 15 + 27?")  # Includes step-by-step explanation

    # Parallel execution with different roles
    tutor = ClaudeCodeCLI(system_prompt="You are a math tutor. Show your work.")
    poet = ClaudeCodeCLI(system_prompt="You are a poet. Respond in verse.")

    # These run in complete isolation with different behaviors
    math_answer = tutor.ask("What is 8 * 7?")   # Shows work
    poem_answer = poet.ask("What is 8 * 7?")    # Responds in verse

    # Context managers for automatic cleanup
    with ClaudeCodeCLI(system_prompt="Be concise.") as claude:
        response = claude.ask("Explain quantum computing")
"""

import json
import os
import subprocess
import uuid
from pathlib import Path
from typing import Any

# Try to use faster JSON library if available
try:
    import orjson as _json

    def _loads(s: str) -> Any:
        return _json.loads(s)

    def _dumps(o: Any) -> str:
        return _json.dumps(o).decode("utf-8")

except ImportError:

    def _loads(s: str) -> Any:
        return json.loads(s)

    def _dumps(o: Any) -> str:
        return json.dumps(o)


# Session storage file
_SESS_FILE = Path.home() / ".claude_code_sessions.json"


def _read_sessions() -> dict[str, str]:
    """Read stored session IDs from file."""
    if _SESS_FILE.exists():
        try:
            return _loads(_SESS_FILE.read_text())
        except Exception:
            return {}
    return {}


def _write_sessions(data: dict[str, str]) -> None:
    """Write session IDs to file atomically."""
    tmp = str(_SESS_FILE) + ".tmp"
    Path(tmp).write_text(_dumps(data))
    os.replace(tmp, _SESS_FILE)


class ClaudeCodeCLIError(Exception):
    """Exception raised for Claude Code CLI errors."""

    pass


class ClaudeCodeCLI:
    """Claude Code CLI wrapper that matches the AmpCLI interface."""

    # Default append prompt to enforce code-focused output
    _CODE_OR_DOCS_APPEND = """
Respond ONLY with:
- Code blocks (for code changes, diffs, or full files), or
- Concise Markdown documents.
Keep any prose to ≤2 short lines or inline code comments. Prefer minimal diffs and test-first changes when behavior changes.
"""

    def __init__(
        self,
        isolated: bool = True,
        system_prompt: str | None = None,
        cwd: str | None = None,
        model: str | None = None,
        permission_mode: str = "acceptEdits",
    ):
        """
        Initialize the Claude Code CLI wrapper.

        Args:
            isolated: If True, creates an isolated session for this instance.
                     This ensures multiple ClaudeCodeCLI instances don't interfere.
            system_prompt: If provided, this will be prepended to every message.
                          Useful for setting context or role instructions.
            cwd: Working directory for Claude Code operations.
            model: Optional model to use (e.g., "claude-3.7-sonnet").
            permission_mode: Permission mode for Claude Code ("acceptEdits" by default).
        """
        self._has_conversation = False
        self._isolated = isolated
        self._system_prompt = system_prompt
        self._instance_id = str(uuid.uuid4())[:8]
        self._session_id: str | None = None
        self._cwd = cwd or os.getcwd()
        self._model = model
        self._permission_mode = permission_mode

        # Create unique key for this instance
        self._session_key = self._make_session_key()

        # Load existing session if available
        if isolated:
            sessions = _read_sessions()
            self._session_id = sessions.get(self._session_key)

    def _make_session_key(self) -> str:
        """Create a unique key for this instance's session."""
        # Include system prompt hash to differentiate agents with different prompts
        prompt_hash = hash(self._system_prompt or "") % 10000
        return f"{self._instance_id}::{self._cwd}::{prompt_hash}"

    def _bootstrap_session(self) -> str:
        """Create a new Claude Code session for this instance."""
        seed = f"Initialize a new dedicated session for agent '{self._instance_id}'. Acknowledge with one short line."

        cmd = ["claude", "-p", seed, "--output-format", "json"]
        if self._model:
            cmd += ["--model", self._model]
        if self._permission_mode:
            cmd += ["--permission-mode", self._permission_mode]

        # Add combined system prompt + code-only append
        if self._system_prompt or self._CODE_OR_DOCS_APPEND:
            combined = self._get_combined_append_prompt()
            cmd += ["--append-system-prompt", combined]

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, check=True, cwd=self._cwd
            )
            payload = _loads(result.stdout)
            sid = payload.get("session_id")
            if not sid:
                raise ClaudeCodeCLIError(
                    f"No session_id in bootstrap response: {result.stdout}"
                )
            return sid
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.strip() if e.stderr else "Unknown error"
            raise ClaudeCodeCLIError(f"Failed to bootstrap session: {error_msg}") from e
        except FileNotFoundError:
            raise ClaudeCodeCLIError(
                "Claude Code CLI not found. Install with: npm i -g @anthropic-ai/claude-code"
            ) from None

    def _get_combined_append_prompt(self) -> str:
        """Get the combined system prompt and code-only append."""
        parts = []
        if self._system_prompt:
            parts.append(f"You are agent {self._instance_id}.\n{self._system_prompt}")
        if self._CODE_OR_DOCS_APPEND:
            parts.append(self._CODE_OR_DOCS_APPEND)
        return "\n\n".join(parts)

    def _ensure_session(self) -> None:
        """Ensure we have a valid session ID."""
        if self._session_id is None:
            self._session_id = self._bootstrap_session()
            # Save session for future use
            if self._isolated:
                sessions = _read_sessions()
                sessions[self._session_key] = self._session_id
                _write_sessions(sessions)

    def _run_claude_command(self, task: str, max_turns: int | None = None) -> str:
        """
        Run a Claude Code command with the given task.

        Args:
            task: The task/prompt to send to Claude Code
            max_turns: Optional maximum number of conversation turns

        Returns:
            The response from Claude Code

        Raises:
            ClaudeCodeCLIError: If the command fails
        """
        self._ensure_session()

        cmd = ["claude", "-p", task, "--output-format", "json"]
        if self._model:
            cmd += ["--model", self._model]
        # Note: Claude Code CLI doesn't have --max-turns option
        if self._permission_mode:
            cmd += ["--permission-mode", self._permission_mode]

        # Add combined system prompt + code-only append
        if self._system_prompt or self._CODE_OR_DOCS_APPEND:
            combined = self._get_combined_append_prompt()
            cmd += ["--append-system-prompt", combined]

        # Resume existing session
        cmd += ["--resume", self._session_id]

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, check=True, cwd=self._cwd
            )
            payload = _loads(result.stdout)
            return payload.get("result", "").strip()
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.strip() if e.stderr else "Unknown error"
            raise ClaudeCodeCLIError(
                f"Claude Code CLI command failed ({e.returncode}): {error_msg}"
            ) from e
        except FileNotFoundError:
            raise ClaudeCodeCLIError(
                "Claude Code CLI not found. Install with: npm i -g @anthropic-ai/claude-code"
            ) from None

    def prompt(self, message: str) -> str:
        """
        Start a new conversation with Claude Code CLI.

        Args:
            message: The prompt to send to Claude Code

        Returns:
            The response from Claude Code

        Raises:
            ClaudeCodeCLIError: If the CLI command fails
        """
        # For Claude Code, we don't need to distinguish between prompt and continue
        # as the session persistence handles this automatically
        response = self._run_claude_command(message)
        self._has_conversation = True
        return response

    def continue_conversation(self, message: str) -> str:
        """
        Continue an existing conversation with Claude Code CLI.

        Args:
            message: The prompt to send to Claude Code

        Returns:
            The response from Claude Code

        Raises:
            ClaudeCodeCLIError: If the CLI command fails
        """
        if not self._has_conversation and not self._session_id:
            raise ClaudeCodeCLIError("No active conversation. Use prompt() first.")

        return self._run_claude_command(message)

    def ask(self, message: str) -> str:
        """
        Ask Claude Code a question, automatically managing the session.

        Args:
            message: The prompt to send to Claude Code

        Returns:
            The response from Claude Code

        Raises:
            ClaudeCodeCLIError: If the CLI command fails
        """
        # Claude Code handles session management internally,
        # so we can just run the command
        response = self._run_claude_command(message)
        self._has_conversation = True
        return response

    def reset_conversation(self) -> None:
        """Reset the conversation state by creating a new session."""
        self._has_conversation = False
        self._session_id = None
        # Remove stored session
        if self._isolated:
            sessions = _read_sessions()
            if self._session_key in sessions:
                del sessions[self._session_key]
                _write_sessions(sessions)

    def _cleanup(self) -> None:
        """Clean up resources (for interface compatibility with AmpCLI)."""
        # Claude Code doesn't need explicit cleanup like Amp's temp directories
        # but we maintain this method for interface compatibility
        pass

    # Properties for interface compatibility with AmpCLI
    @property
    def has_conversation(self) -> bool:
        """Check if there's an active conversation."""
        return self._has_conversation

    @property
    def instance_id(self) -> str:
        """Get the unique instance ID for this ClaudeCodeCLI instance."""
        return self._instance_id

    @property
    def work_dir(self) -> Path | None:
        """Get the working directory (for interface compatibility)."""
        return Path(self._cwd) if self._cwd else None

    @property
    def thread_id(self) -> str | None:
        """Get the session ID (maps to Amp's thread_id for compatibility)."""
        return self._session_id

    @property
    def system_prompt(self) -> str | None:
        """Get the system prompt for this instance."""
        return self._system_prompt

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with cleanup."""
        self._cleanup()


# Alias for drop-in replacement
ClaudeCodeCLIError = ClaudeCodeCLIError


def main():
    """Example usage of the ClaudeCodeCLI wrapper."""

    print("=== Basic Usage ===")
    claude = ClaudeCodeCLI()
    response = claude.ask("what is 2+2?")
    print(f"Basic: {response}")

    print("\n=== With System Prompt ===")
    tutor = ClaudeCodeCLI(
        system_prompt="You are a helpful math tutor. Always show your work step by step."
    )

    try:
        print(f"System prompt: {tutor.system_prompt}")
        print(f"Instance ID: {tutor.instance_id}")

        response1 = tutor.ask("what is 15 + 27?")
        print(f"Tutor: {response1}")

        response2 = tutor.ask("now multiply that by 2")
        print(f"Tutor: {response2}")

    except ClaudeCodeCLIError as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
