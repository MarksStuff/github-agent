# Generic GitHub PR Review Agent with Pluggable Coding Agent Support

## 🧾 Requirements

### Functional

* Query GitHub for PR review comments tied to the current branch and commit
* Forward them to a coding agent via a standardized interface (e.g., MCP)
* Each comment should be addressed independently by the agent

### Technical

* Local client script that runs inside a Git repo
* MCP-compatible message format
* Contextual information like file path, line number, PR URL, branch, and commit

### Optional Enhancements

* Logging and diagnostics
* State tracking to avoid duplicate handling
* Multi-turn response support for follow-up
* Convert to webhook or GitHub Action once stable

---

## 🏗️ High-Level Architecture

```
Manual Trigger or CLI Tool
       ↓
[GitHub API Fetcher]
       ↓ (Build Payload)
     [Send to Agent (MCP)]
       ↓ (Agent Responds)
    [Optional Output Handling]
```

---

## 🧩 Components

### 1. Local Client Script (Manual Runner)

```python
import os
import subprocess
import requests
import logging
from github_query import fetch_review_comments

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
AGENT_ENDPOINT = os.getenv("AGENT_ENDPOINT", "http://localhost:5001/mcp")
REPO_OWNER = os.getenv("REPO_OWNER")
REPO_NAME = os.getenv("REPO_NAME")

local_commit = subprocess.getoutput("git rev-parse HEAD").strip()
local_branch = subprocess.getoutput("git rev-parse --abbrev-ref HEAD").strip()

logging.info(f"🔍 Branch: {local_branch}, Commit: {local_commit}")

def process_comments():
    comments = fetch_review_comments(REPO_OWNER, REPO_NAME, local_branch, local_commit, GITHUB_TOKEN)
    if not comments:
        logging.info("✅ No comments for current branch/commit.")
        return

    message_list = []
    for c in comments:
        body = c["body"]
        path = c.get("path", "<unknown file>")
        line = c.get("position", 0)
        pr_url = c["pull_request_url"].replace("api.github.com/repos", "github.com").replace("/pulls/", "/pull/")

        logging.info(f"📌 Comment on {path}:{line}: {body.strip()[:80]}...")

        message_list.append({
            "role": "user",
            "content": (
                f"Please address this GitHub PR review comment:\n\n"
                f"> {body}\n\n"
                f"File: `{path}`, line {line}.\n"
                f"PR: {pr_url}\n"
                f"Branch: {local_branch}, Commit: {local_commit}"
            )
        })

    agent_payload = {
        "agent": "generic-agent",
        "messages": message_list
    }

    try:
        res = requests.post(AGENT_ENDPOINT, json=agent_payload)
        logging.info(f"📤 Sent {len(message_list)} comment(s) to agent → status: {res.status_code}")
        logging.debug(res.text)
    except Exception as e:
        logging.error(f"❌ Failed to send payload: {e}")

if __name__ == "__main__":
    process_comments()
```

---

### 2. GitHub Query Logic

```python
import requests
import logging

def fetch_review_comments(repo_owner, repo_name, branch, commit_sha, github_token):
    headers = {"Authorization": f"token {github_token}"}
    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/pulls"
    try:
        prs = requests.get(url, headers=headers).json()
    except Exception as e:
        logging.error(f"❌ Failed to fetch PRs: {e}")
        return []

    comments = []
    for pr in prs:
        if pr.get("head", {}).get("ref") == branch and pr.get("head", {}).get("sha") == commit_sha:
            try:
                comments_url = pr["review_comments_url"]
                comments = requests.get(comments_url, headers=headers).json()
            except Exception as e:
                logging.error(f"❌ Failed to fetch comments: {e}")
            break
    return comments
```

---

## ✅ Future Enhancements

* Convert manual script to webhook
* Authenticated GitHub query
* Persistent ID tracking
* Multi-agent dispatch support
* GitHub Action to collect and forward comment metadata to local agent
* Enhanced logging with file output and severity control
