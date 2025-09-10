# Stateful Multi‑Agent Coding with **LangGraph Local Server + Studio**
**Hybrid routing (Ollama on RTX 5070 + Claude Code), Git‑based rollback, durable memory, and CI/PR feedback loops**

> This document is a practical blueprint for running a stateful, multi‑agent coding workflow using **LangGraph Local Server + Studio**, with **SQLite** persistence, **GitHub‑driven review**, and **hybrid model routing** (local **Ollama** for drafts/tests; **Claude Code** for high‑stakes steps). It’s written to be dropped into your repo as `docs/agentic-workflow.md` or similar.

---

## 0) Goals & Design Principles

- **Durable state without context bloat.** Use LangGraph checkpointers (SQLite) to store *agent state* (messages window, decision log, artifacts index), not raw transcripts. Agents send only compact windows + summaries to models.
- **Git is the source of truth for code.** LangGraph rewinds *state*; **Git** rewinds *files*. Always commit changes with SHAs written to the graph state.
- **Hybrid model routing.** Fast/cheap work (drafting, tests, quick refactors) → **Ollama** on your RTX 5070. Escalations and complex reasoning → **Claude Code**.
- **Deterministic side effects.** Nodes are designed to be idempotent and checkpoint‑aware (commit SHAs, patch IDs, workspace paths).
- **Human‑in‑the‑loop via GitHub.** Agents push branches, open/update PRs, and then **pause**. You review in GitHub UI; your MCP server reads comments/checks; agents resume to address feedback.

---

## 1) Quick Start: Local Server + Studio

> **You control the server**: your Python process loads the graph, enables a local API for threads/checkpoints, and lets **Studio** attach for visualization, time‑travel, and branching.

1. **Install dependencies**
   ```bash
   python -m venv .venv && source .venv/bin/activate
   pip install -U langgraph langgraph-checkpoint-sqlite langchain-ollama langchain-anthropic
   # Optional: any HTTP client SDKs you use inside tool nodes (e.g., requests, httpx)
   ```

2. **Set keys & model services**
   ```bash
   # Local models on the RTX 5070
   ollama serve
   ollama pull qwen2.5-coder:7b
   ollama pull llama3.1
   # Cloud model
   export ANTHROPIC_API_KEY=...   # for Claude (including Claude Code)
   ```

3. **Run your Local Graph Server**
   - Create a small Python entrypoint that:
     - builds the graph,
     - configures a **SQLite** checkpointer (e.g., `agent_state.db`),
     - exposes a simple HTTP interface (or uses the LangGraph server helper) for Studio + local tools,
     - logs the **graph id** and **thread ids**.
   - Start it with `python agents/server.py` (or your chosen script).

4. **Open LangGraph Studio**
   - Point Studio at your local server.
   - Use **threads** to start/rerun flows, **time‑travel** to earlier checkpoints, **branch** for A/B fixes, and inspect state fields live.

> **Thread IDs:** Use a meaningful, stable ID per work unit, e.g. `thread_id = "pr-1234"` or `"issue-42"`. This ties the whole history, decisions, and artifacts to a Git reference you already use.

---

## 2) State Model (keep prompts small, memory durable)

Design the **graph state** so prompts stay short while the full memory persists in SQLite:

```text
S = {
  messages_window:    [ChatMessage],   # last few turns only; everything else is summarized
  summary_log:        str,             # rolling summary of decisions/constraints (append-only)
  artifacts_index:    { key -> path }, # docs, patches, reports, diffs created on disk
  repo:               str,             # absolute path to workspace
  thread_id:          str,             # PR/issue identifier for durability & Git integration
  git_branch:         str,             # working branch name (e.g., feature/pr-1234)
  last_commit_sha:    str,             # SHA after the most recent apply
  patch_queue:        [path],          # staged unified diffs waiting for apply
  test_report_digest: { ... },         # compact parsed test results (pass/fail, counts, names)
  ci_status:          { state, checks },
  lint_status:        { state, findings },
  feedback_gate:      "open"|"hold",   # pause node for review feedback
  quality:            "draft"|"ok"|"fail"
}
```

**Key ideas**
- Keep **`messages_window`** short (e.g., last 5–10 turns). Everything else goes into **`summary_log`** (updated by a “summarize” node when message size grows).
- **`artifacts_index`** stores *paths* to files (diffs, reports, design docs), not raw blobs. Prompts reference *digests*, not full files.
- **`last_commit_sha`** and **`git_branch`** let you *recreate the exact repo state* when you time‑travel.

---

## 3) Git‑Based Rollback (code memory)

Rewind in LangGraph restores **state**, not files. Use Git to make file changes reproducible:

1. **Per‑thread branch/worktree**
   - Create a branch like `feature/pr-1234` or a **git worktree** at `workspaces/pr-1234`.
   - Write the workspace path into `state.repo` and branch name into `state.git_branch`.

2. **Apply changes via patches**
   - In “implement” nodes, produce a **unified diff** (artifact) and have an “apply” tool node:
     - apply the patch to `state.repo`,
     - run `git add -A && git commit -m "agent: <summary>"`,
     - store the new **`last_commit_sha`** in state,
     - index the patch in `artifacts_index` (e.g., `patches/2025-09-09T08-15Z.diff`).

3. **Rewind flow**
   - When you time‑travel to an earlier checkpoint, the next node should:
     - `git fetch && git checkout <last_commit_sha>` (or create a new branch from it),
     - verify clean status before proceeding (idempotent apply).

4. **Safety rails**
   - Allowlist the workspace root; reject edits outside it.
   - Add CI guardrails: **diff size** ≤ N lines; no writes to `/secrets`, `/home`, etc.
   - Add a **static interrupt** before “apply” to surface a preview diff in Studio/GitHub, resume only on approval.

---

## 4) Hybrid Model Routing (Ollama vs. Claude Code)

- Model choice is **per node**:
  - **Developer/Tester/Formatter** → **Ollama** (e.g., `qwen2.5-coder:7b` or `llama3.1`) for fast, cheap steps.
  - **Reviewer/Fixer/Architect** → **Claude Code** for complex reasoning or large refactors.
- **Conditional edges** implement the policy:
  - If `quality == "fail"` → escalate to Claude.
  - If `diff_size > threshold` or `files_touched > K` → escalate to Claude.
  - If **two failing test cycles** locally → escalate to Claude.

**Claude Code integration**
- Wrap your **Claude Code CLI** as a tool node. Inputs: prompt, repo path, optional file list. Outputs: summary + patch; raw edits are persisted to disk and committed by the apply node.
- Keep CLI outputs out of the prompt; store the **patch** on disk, insert a **brief digest** into `messages_window` + `summary_log`.

---

## 5) Documents, History, and Referencing

Agents will produce design docs, READMEs, ADRs, diffs, test reports. Don’t stuff these into prompts.

**Layout (suggested)**
```
<repo>/
  agents/
    artifacts/<thread_id>/
      patches/
      reports/
      docs/
      logs/
    decisions/<thread_id>.md     # append-only decisions and constraints
  ...
```

**Indexing strategy**
- Every time a node produces an artifact, write it under `artifacts/<thread_id>/...` and record it in `state.artifacts_index`:
  ```text
  artifacts_index = {
    "patch:health-endpoint": "agents/artifacts/pr-1234/patches/health.diff",
    "report:tests:2025-09-09T08:15": "agents/artifacts/pr-1234/reports/pytest_0815.txt",
    "doc:ADR-001": "agents/artifacts/pr-1234/docs/ADR-001-health-endpoint.md"
  }
  ```
- Add a tiny **digest** (3–10 lines) into `summary_log` (e.g., “Created ADR-001… key decisions: …”). Prompts cite the digest and path, not the entire doc.

---

## 6) SQLite Persistence (durable agent memory)

- Use **`langgraph-checkpoint-sqlite`** during development.
- One DB file per repo/environment is fine (e.g., `agent_state.db` at project root).
- **Threading model**: one **`thread_id`** per PR/issue. All resuming, branching, and history attach to this ID.
- For production scale, swap SQLite for Postgres/Redis later; the graph logic stays the same.

---

## 7) Local Execution: Tests, Lint, Format

Tool nodes execute your local commands. Keep them **idempotent** and **quiet**:

- **Tests** (example): `pytest -q` (or your stack’s runner). Parse output into `state.test_report_digest`:
  ```text
  test_report_digest = {
    "passed": 132, "failed": 2, "errors": 0,
    "failed_tests": ["tests/api/test_health.py::test_200", ...]
  }
  ```
- **Lint/Format**: `ruff check --output-format=json`, `black --check`. Parse minimal JSON digests into `state.lint_status`.
- **Never** send full logs to models. Save logs under `artifacts/<thread_id>/logs` and put only a tiny summary in prompts.

**Gating pattern**
1) Generate patch → 2) apply → 3) run tests → 4) if pass, push; if fail, **local fix loop** (Ollama) → escalate to Claude only if necessary.

---

## 8) Feedback Loop via GitHub (reviews & MCP server)

**Objective:** After a push, **pause** until you (human) review on GitHub. Your MCP server will expose read‑only endpoints for comments and checks.

**Flow**
1. **Push**: create/force‑push the branch to origin (`feature/pr-1234`), open/update a PR. Store the PR number in state (`state.pr_number`).
2. **Pause for feedback**: set `state.feedback_gate = "hold"`; trigger a **static interrupt** named `await_feedback`.
3. **Review in GitHub UI**: leave comments/suggested changes.
4. **Resume**: a small polling loop (or a Studio resume) calls your MCP server:
   - `mcp.get_pr_comments(pr_number, since=last_seen)` → updates `state.summary_log` and `artifacts_index` (e.g., store a `comments.json` artifact).
   - Optionally classify comments into actionable items; enqueue tasks into `patch_queue`.
5. **Act**: nodes generate patches addressing comments, apply, re‑run tests, push updates, and re‑enter the feedback gate until resolved.

**Why MCP?** You already have it. Keep GitHub access centralized; nodes talk to MCP, not directly to GitHub.

---

## 9) Waiting for CI (lint/test) and Fixing Failures

After pushing, **wait** until GitHub runs linters/tests. Then fetch status and logs via your MCP server.

**Pattern**
1. **Push branch**.
2. **Poll MCP**:
   - `mcp.get_check_runs(pr_number)` → list of checks with `status`/`conclusion`/`details_url`.
   - If any `in_progress` → sleep/backoff and poll again.
3. **On failure**:
   - `mcp.get_check_log(pr_number, check_id)` → store full logs under `artifacts/.../logs/ci_<id>.txt`.
   - Parse a compact **digest** (`state.ci_status`) and feed back into routing:
     - If lint fails → run **formatter/linter fix** node (local Ollama).
     - If tests fail → run **fix tests** node (local first; escalate to Claude if repeated).

4. **Stop criteria**:
   - All checks `conclusion == "success"` → mark `quality="ok"` and clear `feedback_gate`.

**Failure loops**
- Limit local fix attempts (e.g., 2). On the 3rd failure or >N lines changed, escalate to **Claude Code reviewer**.

---

## 10) Interrupts & Human‑in‑the‑Loop

Use **static interrupts** to create deterministic “stop‑and‑assert” points:
- `await_feedback` (after push, before next iteration).
- `preview_apply` (before mutating workspace; present diff).
- `pre_escalate` (before calling Claude; confirm the cost is warranted).

These pauses let you review state in Studio, ensure guardrails (e.g., diff size), and resume with confidence.

---

## 11) Operational Policies (recommended defaults)

- **Routing thresholds**:
  - `diff_size_lines > 300` → escalate to Claude.
  - `files_touched > 10` → escalate.
  - ≥ 2 consecutive local test failures on the same area → escalate.
- **Prompt discipline**: “code/doc only” outputs; avoid prose doodles.
- **Context budgets**: keep `messages_window` under ~6–10 items; summarize early.
- **Caching**: semantic cache keyed on (task, file set, summary hash). Cache only *finalized* node outputs.
- **Backoff/limits**: at most 1–2 concurrent cloud calls; exponential backoff on 429.
- **Safety**: path allowlists; secret scan before commit; redact tokens/logs before storing in artifacts.

---

## 12) Day‑1 Bring‑up Checklist

- [ ] Ollama serving; `qwen2.5-coder:7b` returns code quickly on a local draft task.
- [ ] Claude Code CLI reachable; one successful “review/fix” call end‑to‑end.
- [ ] SQLite file (`agent_state.db`) created and growing with checkpoints.
- [ ] A thread (`pr-XXXX`) can stop, resume, and **time‑travel** from Studio.
- [ ] Git branch per thread; each apply creates a commit; `last_commit_sha` always set.
- [ ] Push → wait → MCP polls checks → surfaces failures → local fix → push again.
- [ ] Static interrupt **await_feedback** pauses until you finish reviewing in GitHub UI.

---

## 13) Appendix — Environment & Config

**Environment variables**
```
ANTHROPIC_API_KEY=...
OLLAMA_BASE_URL=http://127.0.0.1:11434
AGENT_DB=agent_state.db
REPO_ROOT=/abs/path/to/workspace
```

**Model map (conceptual)**
```yaml
models:
  developer: ollama:qwen2.5-coder:7b
  tester:    ollama:llama3.1
  reviewer:  anthropic:claude-3-7-sonnet-latest   # or Claude Code via CLI tool node
```

**Node responsibilities (example)**
- **planner** (Claude): produce DESIGN.md + small task list.
- **developer** (Ollama): produce minimal patch/diff for a task.
- **apply** (tool): apply patch, commit, update `last_commit_sha`.
- **tests** (tool): run unit/integration tests; parse digest.
- **router** (rule): OK → push → `await_feedback`; FAIL → local fix → escalate on thresholds.
- **reviewer/fixer** (Claude Code): targeted fixes for stubborn failures; new patch.
- **summarize** (Ollama): refresh `summary_log` when messages window grows.
- **ci_waiter** (tool+MCP): poll PR checks until all pass; store CI digests; trigger fixes if needed.
- **feedback_ingest** (tool+MCP): fetch PR comments; convert to actionable tasks; queue patches.


---

### TL;DR

- **LangGraph** keeps **agent state** durable (SQLite checkpoints) so prompts stay small.
- **Git** keeps **code state** durable (commits per apply) so rewind is deterministic.
- **Ollama** handles the noisy, iterative steps locally; **Claude Code** is reserved for high‑value escalations.
- **GitHub/MCP** drives the feedback loop: push, wait for checks, ingest comments, fix, repeat—fully observable in **Studio** with time‑travel and branching.
