# Pre-Commit Scripts Configuration

This document describes how to configure pre-commit scripts in your `repositories.json` file to ensure code quality and consistency before commits.

## Overview

Pre-commit scripts are automatically executed in sequence before any git commit operations. This ensures that code meets quality standards and passes all checks before being committed to the repository.

## Configuration

Pre-commit scripts are configured in the `repositories.json` file under the `pre_commit_scripts` array for each repository.

### Schema

```json
{
  "repositories": {
    "your-repo": {
      "workspace": "/path/to/repo",
      "port": 8081,
      "language": "python",
      "python_path": "/path/to/python",
      "pre_commit_scripts": [
        {
          "name": "script-name",
          "script": "command-to-run",
          "description": "What this script does",
          "required": true,
          "timeout": 300
        }
      ]
    }
  }
}
```

### Script Properties

| Property | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `name` | string | ✅ Yes | - | Human-readable name for the script |
| `script` | string | ✅ Yes | - | Command to execute (relative to repo root or absolute) |
| `description` | string | ❌ No | - | Optional description of what the script does |
| `required` | boolean | ❌ No | `true` | Whether script must pass for commit to proceed |
| `timeout` | integer | ❌ No | `300` | Timeout in seconds (1-∞) |

## Example Configurations

### Python Repository (github-agent)

```json
{
  "repositories": {
    "github-agent": {
      "workspace": "/Users/user/Code/github-agent",
      "port": 8081,
      "language": "python",
      "python_path": "/Users/user/Code/github-agent/.venv/bin/python",
      "lsp_server": "pylsp",
      "pre_commit_scripts": [
        {
          "name": "ruff-autofix",
          "script": "scripts/ruff-autofix.sh",
          "description": "Auto-format Python code using ruff",
          "required": true,
          "timeout": 120
        },
        {
          "name": "code-checks",
          "script": "scripts/run-code-checks.sh", 
          "description": "Run linting checks (ignore bandit warnings)",
          "required": true,
          "timeout": 180
        },
        {
          "name": "pytest",
          "script": "pytest",
          "description": "Run all tests to ensure functionality",
          "required": true,
          "timeout": 300
        }
      ]
    }
  }
}
```

### Node.js Repository

```json
{
  "repositories": {
    "node-api": {
      "workspace": "/Users/user/Code/node-api",
      "port": 8082,
      "language": "javascript",
      "python_path": "/usr/bin/python3",
      "pre_commit_scripts": [
        {
          "name": "eslint-fix",
          "script": "npm run lint:fix",
          "description": "Auto-fix ESLint issues",
          "required": true,
          "timeout": 60
        },
        {
          "name": "prettier",
          "script": "npm run format",
          "description": "Format code with Prettier", 
          "required": true,
          "timeout": 30
        },
        {
          "name": "tests",
          "script": "npm test",
          "description": "Run Jest test suite",
          "required": true,
          "timeout": 240
        }
      ]
    }
  }
}
```

## Execution Behavior

### Script Execution Order

Scripts are executed in the order they appear in the `pre_commit_scripts` array:

1. **Sequential Execution**: Scripts run one after another, not in parallel
2. **Early Termination**: If a required script fails, subsequent scripts are skipped
3. **Working Directory**: All scripts execute from the repository workspace directory

### Required vs Optional Scripts

- **Required Scripts** (`"required": true`):
  - Must complete successfully (exit code 0)
  - Failure blocks the commit
  - Default behavior if not specified

- **Optional Scripts** (`"required": false`):
  - Allowed to fail without blocking commit
  - Useful for informational scripts or best-effort checks

### Timeout Handling

- Scripts that exceed their timeout are terminated
- Timeout failures are treated the same as script failures
- Default timeout is 300 seconds (5 minutes)

## Common Script Patterns

### Python Projects

```json
[
  {
    "name": "format",
    "script": "black .",
    "description": "Format Python code with Black"
  },
  {
    "name": "lint", 
    "script": "ruff check .",
    "description": "Check code with ruff linter"
  },
  {
    "name": "type-check",
    "script": "mypy .",
    "description": "Type checking with mypy"
  },
  {
    "name": "test",
    "script": "pytest",
    "description": "Run test suite"
  }
]
```

### JavaScript/TypeScript Projects

```json
[
  {
    "name": "lint-fix",
    "script": "eslint --fix .",
    "description": "Fix ESLint issues"
  },
  {
    "name": "format",
    "script": "prettier --write .",
    "description": "Format with Prettier"
  },
  {
    "name": "type-check",
    "script": "tsc --noEmit",
    "description": "TypeScript type checking"
  },
  {
    "name": "test",
    "script": "npm test",
    "description": "Run test suite"
  }
]
```

### Rust Projects

```json
[
  {
    "name": "format",
    "script": "cargo fmt",
    "description": "Format Rust code"
  },
  {
    "name": "clippy",
    "script": "cargo clippy -- -D warnings",
    "description": "Lint with Clippy"
  },
  {
    "name": "test",
    "script": "cargo test",
    "description": "Run Rust tests"
  }
]
```

## Integration with Multi-Agent Workflow

The pre-commit scripts configuration integrates with the multi-agent workflow system:

1. **Phase 2 Implementation**: When agents generate code, pre-commit scripts ensure quality
2. **Git Commit Logic**: The enhanced git commit logic runs these scripts before committing
3. **Failure Handling**: Script failures are logged and reported to the human reviewer
4. **Resumption**: Failed commits can be resumed after fixing issues

## Best Practices

### Script Design

1. **Idempotent**: Scripts should be safe to run multiple times
2. **Fast**: Keep execution time reasonable (< 5 minutes total)
3. **Clear Output**: Provide clear success/failure messages
4. **Exit Codes**: Use proper exit codes (0 = success, non-zero = failure)

### Configuration Tips

1. **Order Matters**: Put fast, formatting scripts first (auto-fix issues)
2. **Reasonable Timeouts**: Set appropriate timeouts for each script type
3. **Required vs Optional**: Mark critical scripts as required
4. **Clear Descriptions**: Help team members understand what each script does

### Repository Structure

Ensure your repository has the necessary script files and configuration:

```
your-repo/
├── scripts/
│   ├── ruff-autofix.sh
│   └── run-code-checks.sh
├── pyproject.toml      # Tool configuration
├── pytest.ini         # Test configuration
└── repositories.json   # Pre-commit script configuration
```

## Troubleshooting

### Common Issues

1. **Script Not Found**: Ensure script paths are correct relative to workspace
2. **Permission Denied**: Make sure script files are executable (`chmod +x`)
3. **Timeout Issues**: Increase timeout for slow scripts or optimize performance
4. **Environment Issues**: Ensure scripts run in correct virtual environment

### Debugging

- Check script execution manually from repository workspace
- Verify all dependencies are installed
- Review script output logs for specific error messages
- Test with shorter timeouts to identify slow scripts

## Migration Guide

### From Manual Process

If you currently run these scripts manually before commits:

1. Add your existing scripts to `pre_commit_scripts` configuration
2. Test the configuration with a test commit
3. Remove manual script execution from your workflow

### From Git Hooks

If you use git pre-commit hooks:

1. Move hook logic to separate script files
2. Configure those scripts in `repositories.json`
3. Remove or disable git hooks
4. Test to ensure equivalent functionality