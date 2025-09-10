# Claude Code: Multi-Agent Setup & Python Wrapper (Sync)

This guide shows how to mirror your Sourcegraph CLI multi-agent workflow with **Claude Code**—including **separate, persistent context per agent**, a **code/docs-only output style**, and a **simple synchronous Python wrapper**.

---

## Prerequisites

- Node 18+ and `npm`
- Python 3.10+
- Claude Code CLI (installs via npm)
- (Optional) `orjson` Python package for fast JSON (falls back to stdlib `json`)

```bash
npm i -g @anthropic-ai/claude-code
pip install orjson
```

> Tip: Set `ANTHROPIC_API_KEY` in your shell environment if your CLI needs it.

---

## 1) Define Subagents (separate context per agent)

Create per-agent prompt files under `.claude/agents/`. Each file names the agent, describes its domain, and constrains output to **code or Markdown**. Claude Code treats subagents as separate contexts.

```bash
mkdir -p .claude/agents
```

**Fast-Iterating Developer**

```md
# .claude/agents/fast-iterating-developer.md
---
name: fast-iterating-developer
description: Rapid implementer. Use PROACTIVELY for quick, incremental code changes and scaffolding. Prefer minimal diffs.
tools: Read, Edit, Write, Grep, Glob, Bash
---

You are the Fast-Iterating Developer.
Constraints:
- Always respond with code diffs or full files in fenced blocks. Avoid prose unless a brief 1–2 line note is essential.
- Prefer smallest viable change that passes tests.
- If tests exist, run them and fix failures; if not, write smoke tests first.
- Preserve style/formatting and keep commits cohesive.
```

**Test-Conscious Developer**

```md
# .claude/agents/test-conscious-developer.md
---
name: test-conscious-developer
description: Testing specialist. Use PROACTIVELY to add/adjust tests before/with changes; ensure failing test first.
tools: Read, Edit, Write, Grep, Glob, Bash
---

You are the Test-Conscious Developer.
Policy:
- Add/modify tests that capture the new/changed behavior.
- Run tests; if failing, implement the minimal fix; re-run to green.
- Output only code or Markdown test plans; keep narrative terse (≤2 lines).
```

**Senior Engineer**

```md
# .claude/agents/senior-engineer.md
---
name: senior-engineer
description: Senior Engineer for design, refactors, and tradeoffs. Use when tasks span modules or require design docs.
tools: Read, Edit, Write, Grep, Glob, Bash
---

You are the Senior Engineer.
Deliverables:
- For non-trivial work, first output a concise DESIGN.md (scope, risks, and step plan).
- Then produce code changes in small, verifiable steps.
- Keep output to code or Markdown docs. No long essays.
```

**Architect**

```md
# .claude/agents/architect.md
---
name: architect
description: Architect for architecture docs, interfaces, boundaries, and risks. Use for cross-cutting concerns.
tools: Read, Write, Grep, Glob
---

You are the Architect.
Deliverables:
- Output only Markdown docs (ADR/ARCHITECTURE.md) and interface sketches.
- Specify invariants, error budgets, and testability hooks.
- Avoid code except for interface skeletons where vital.
```

---

## 2) Enforce “Code or Docs Only” with an Output Style

Create a custom style and switch to it per session using `/output-style code-or-docs`.

```bash
mkdir -p .claude/output-styles
```

```md
# .claude/output-styles/code-or-docs.md
---
name: code-or-docs
description: Force responses to be either code blocks or Markdown documents; no chatty prose.
---
# Code-or-Docs Only

- Default to code blocks or full Markdown documents.
- Keep any explanatory text to ≤2 lines, or inline as comments.
- Prefer minimal diffs and test-first changes when practical.
```

---

## 3) (Optional) Tiny Hook to Remind Code/Docs Only

Add a user-prompt hook that injects a one-liner reminder on each turn.

```bash
mkdir -p .claude/hooks
```

```python
# .claude/hooks/code_only_guard.py
#!/usr/bin/env python3
import json
print(json.dumps({
  "hookSpecificOutput": {
    "hookEventName": "UserPromptSubmit",
    "additionalContext": "Reminder: respond with code blocks or concise Markdown docs; minimize chatter."
  }
}))
```

```json
// .claude/settings.local.json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "hooks": [
          { "type": "command", "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/code_only_guard.py" }
        ]
      }
    ]
  }
}
```

---

## 4) Shared Memory File (Project-Wide Norms)

Keep stable build/test commands and conventions in `CLAUDE.md` so agents can reference them.

```md
# CLAUDE.md
# Project Memory
- Build: `make build`
- Test: `make test`
- Lint: `make lint`

# Conventions
- 2-space indent, no trailing whitespace.
- Add tests before code when changing behavior.

# Imports for extra context
See @README and @CONTRIBUTING.md.
```

---

## 5) Convenience Slash Commands

Quick routes to the specific subagent you want.

```bash
mkdir -p .claude/commands/eng
```

```md
# .claude/commands/eng/dev.md
Use the fast-iterating-developer subagent to: $ARGUMENTS
```

```md
# .claude/commands/eng/test.md
Use the test-conscious-developer subagent to: $ARGUMENTS
```

```md
# .claude/commands/eng/swe.md
Use the senior-engineer subagent to: $ARGUMENTS
```

```md
# .claude/commands/eng/arch.md
Use the architect subagent to: $ARGUMENTS
```

---

## 6) Interactive Usage (Terminal REPL)

1. Start the REPL:
   ```bash
   claude
   ```
2. Set style (per project, once per session):
   ```
   /output-style code-or-docs
   ```
3. Invoke subagents:
   ```
   /eng/dev Implement a --dry-run flag for cli/sync.py; show code changes.
   /eng/test Add failing tests for the new --dry-run behavior; then fix.
   /eng/swe Plan a safe refactor; produce concise DESIGN.md then first step.
   /eng/arch Draft ADR for adopting Qdrant; risks and rollback.
   ```

> Each subagent keeps its **own context window**, so their memories do not bleed into each other.

---

## 7) Headless (Non-interactive) Examples

```bash
# One-shot, JSON output:
claude -p "Use the test-conscious-developer subagent to add failing tests for parsing edge cases; then fix."   --output-format json

# Persistent session (capture session_id from JSON once, then --resume):
SID=$(claude -p "Start parser hardening session" --output-format json | jq -r '.session_id')
claude -p --resume "$SID" "Use the fast-iterating-developer subagent to implement minimal fix."
claude -p --resume "$SID" "Use the senior-engineer subagent to author DESIGN.md for future extensions."
```

---

## 8) Python Wrapper (Synchronous, Separate Context per Agent)

Drop this file into your repo as `claude_agents.py`. It provides a simple **blocking** `Agent.run(task)` method and **persistent**, isolated context per agent by storing/reusing the CLI `session_id` under `~/.claude_agents_sessions.json`.

```python
# claude_agents.py
# Prereqs (once):
#   pip install orjson
#   npm install -g @anthropic-ai/claude-code
#
# What you get:
#   - Agent.run(task) -> str  # synchronous
#   - Each Agent has its own persistent Claude Code session (isolated context)
#   - Context survives process restarts via a small ~/.claude_agents_sessions.json
#   - Agents biased to emit code/Markdown only (via append_system_prompt)

import json
import os
import shlex
import subprocess
from pathlib import Path

try:
    import orjson as _json  # faster if available
    def _loads(s: str): return _json.loads(s)
    def _dumps(o) -> str: return _json.dumps(o).decode("utf-8")
except Exception:
    def _loads(s: str): return json.loads(s)
    def _dumps(o) -> str: return json.dumps(o)

_SESS_FILE = Path.home() / ".claude_agents_sessions.json"

_CODE_OR_DOCS_APPEND = """
Respond ONLY with:
- Code blocks (for code changes, diffs, or full files), or
- Concise Markdown documents.
Keep any prose to ≤2 short lines or inline code comments. Prefer minimal diffs and test-first changes when behavior changes.
"""

_DEFAULT_PERMISSION_MODE = "acceptEdits"  # auto-accept edits; still prompts for shell unless you change it

def _read_sessions():
    if _SESS_FILE.exists():
        try: return _loads(_SESS_FILE.read_text())
        except Exception: return {}
    return {}

def _write_sessions(data):
    tmp = str(_SESS_FILE) + ".tmp"
    Path(tmp).write_text(_dumps(data))
    os.replace(tmp, _SESS_FILE)

class Agent:
    """
    A simple, synchronous wrapper around Claude Code headless mode.
    Each Agent has an independent session (isolated context).
    """
    def __init__(
        self,
        name: str,
        system_prompt: str,
        cwd: str | os.PathLike | None = None,
        permission_mode: str = _DEFAULT_PERMISSION_MODE,
        append_system_prompt: str | None = _CODE_OR_DOCS_APPEND,
        model: str | None = None,
    ):
        self.name = name
        self.cwd = str(cwd) if cwd else None
        self.permission_mode = permission_mode
        self.system_prompt = system_prompt.strip()
        self.append_system_prompt = (append_system_prompt or "").strip()
        self.model = model
        self._session_id = _read_sessions().get(self._key(), None)

    # public API (synchronous)
    def run(self, task: str, max_turns: int | None = None, extra_args: list[str] | None = None) -> str:
        """
        Invoke the agent synchronously; returns final text (code/doc).
        Maintains this agent's own context across invocations.
        """
        if self._session_id is None:
            self._session_id = self._bootstrap_session()
            sessions = _read_sessions()
            sessions[self._key()] = self._session_id
            _write_sessions(sessions)

        cmd = ["claude", "-p", task, "--output-format", "json"]
        if self.cwd:               cmd += ["--cwd", self.cwd]
        if self.model:             cmd += ["--model", self.model]
        if max_turns is not None:  cmd += ["--max-turns", str(max_turns)]
        if self.permission_mode:   cmd += ["--permission-mode", self.permission_mode]
        if self.append_system_prompt:
            cmd += ["--append-system-prompt", self._combined_append_prompt()]
        cmd += ["--resume", self._session_id]
        if extra_args:             cmd += list(extra_args)

        out = subprocess.run(cmd, capture_output=True, text=True)
        if out.returncode != 0:
            raise RuntimeError(f"[{self.name}] Claude CLI error ({out.returncode}): {out.stderr.strip()}")

        payload = _loads(out.stdout)
        return payload.get("result", "").strip()

    # helpers
    def _key(self) -> str:
        return f"{self.name}::{self.cwd or os.getcwd()}"

    def _combined_append_prompt(self) -> str:
        parts = [f"You are the {self.name}.\n{self.system_prompt}"]
        if self.append_system_prompt:
            parts.append(self.append_system_prompt)
        return "\n\n".join(parts)

    def _bootstrap_session(self) -> str:
        seed = f"Initialize a new dedicated session for agent '{self.name}'. Acknowledge with one short line."
        cmd = ["claude", "-p", seed, "--output-format", "json"]
        if self.cwd:             cmd += ["--cwd", self.cwd]
        if self.model:           cmd += ["--model", self.model]
        if self.permission_mode: cmd += ["--permission-mode", self.permission_mode]
        if self.append_system_prompt:
            cmd += ["--append-system-prompt", self._combined_append_prompt()]

        out = subprocess.run(cmd, capture_output=True, text=True)
        if out.returncode != 0:
            raise RuntimeError(f"[{self.name}] bootstrap error: {out.stderr.strip()}")
        payload = _loads(out.stdout)
        sid = payload.get("session_id")
        if not sid:
            raise RuntimeError(f"[{self.name}] no session_id in bootstrap response")
        return sid


# ---- Example setup with your four agents ----

def make_default_agents(repo_root: str | os.PathLike):
    root = str(repo_root)
    return {
        "Fast-Iterating Developer": Agent(
            name="Fast-Iterating Developer",
            cwd=root,
            system_prompt=(
                "Rapid implementer for incremental changes.\n"
                "- Prefer the smallest viable change that passes tests.\n"
                "- Keep commits cohesive.\n"
                "- When tests fail, fix minimally."
            ),
        ),
        "Test-Conscious Developer": Agent(
            name="Test-Conscious Developer",
            cwd=root,
            system_prompt=(
                "Testing specialist.\n"
                "- Write/adjust tests to capture intended behavior BEFORE code changes.\n"
                "- Run tests; if failing, implement minimal fix; re-run to green."
            ),
        ),
        "Senior Engineer": Agent(
            name="Senior Engineer",
            cwd=root,
            system_prompt=(
                "Senior engineer for non-trivial changes.\n"
                "- First produce a concise DESIGN.md (scope, risks, plan).\n"
                "- Then implement in small, verifiable steps."
            ),
        ),
        "Architect": Agent(
            name="Architect",
            cwd=root,
            system_prompt=(
                "Architect for cross-cutting designs.\n"
                "- Output ADRs/ARCHITECTURE.md and interface sketches.\n"
                "- Avoid code except necessary interface skeletons."
            ),
        ),
    }


# ---- Minimal demo (run directly) ----
if __name__ == "__main__":
    agents = make_default_agents(repo_root=".")
    dev = agents["Fast-Iterating Developer"]
    print(dev.run("Add a --dry-run flag to cli/sync.py and update usage docs; show the code changes."))
```

**Usage in your repo:**

```python
from claude_agents import make_default_agents

agents = make_default_agents(".")
dev = agents["Fast-Iterating Developer"]
tests = agents["Test-Conscious Developer"]

print(tests.run("Add failing tests for the new --dry-run behavior in cli/sync.py, then implement the minimal fix."))
print(dev.run("Refactor the argument parser to support --dry-run consistently across subcommands; show diffs."))
```

---

## 9) Notes & Toggles

- **Permission modes**: `acceptEdits` (default here) auto-applies editor changes but will still ask for shell tool permission. For fully headless pipelines you *can* add `extra_args=["--dangerously-skip-permissions"]` (risky; prefer safer modes).
- **Model selection**: Pass `model="claude-3.7-sonnet"` (or your chosen version) into `Agent(...)`.
- **Isolation guarantees**: Each `Agent` stores its own `session_id` and a unique key includes `name + cwd`. Using different `cwd` values allows per-repo isolation.
- **Resetting context**: Delete the entry from `~/.claude_agents_sessions.json` or instantiate a new `Agent` with a distinct name/key.
- **Subagents you already defined**: You can request them explicitly in tasks (e.g., “Use the senior-engineer subagent to …”) to leverage their separate internal context.

---

## 10) Quick Checklist

- [ ] `.claude/agents/*` created
- [ ] `.claude/output-styles/code-or-docs.md` added
- [ ] (Optional) `.claude/hooks/code_only_guard.py` and `.claude/settings.local.json` added
- [ ] `CLAUDE.md` with build/test norms added
- [ ] Slash commands `/eng/*` created
- [ ] `claude_agents.py` added to repo
- [ ] `claude` REPL: run `/output-style code-or-docs` once per session

You're ready to run multiple **separate, persistent** Claude Code agents—interactively or from Python—while keeping outputs clean and code-focused.
