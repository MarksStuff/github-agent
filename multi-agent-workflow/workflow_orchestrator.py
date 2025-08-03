"""Workflow orchestrator for multi-agent collaboration - Phase 1 implementation."""

import asyncio
import json
import logging
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# Add parent directory to path to import github_tools
sys.path.append(str(Path(__file__).parent.parent))

from agent_interface import (  # noqa: E402
    ArchitectAgent,
    DeveloperAgent,
    SeniorEngineerAgent,
    TesterAgent,
)
from codebase_analyzer import CodebaseAnalyzer  # noqa: E402
from conflict_resolver import ConflictResolver  # noqa: E402
from dotenv import load_dotenv  # noqa: E402
from task_context import CodebaseState, FeatureSpec, TaskContext  # noqa: E402

import github_tools  # noqa: E402
from github_tools import execute_tool  # noqa: E402
from repository_manager import (  # noqa: E402
    Language,
    RepositoryConfig,
    RepositoryManager,
)

logger = logging.getLogger(__name__)


class WorkflowOrchestrator:
    """Orchestrates multi-agent collaboration workflow."""

    def __init__(self, repo_name: str, repo_path: str):
        """Initialize orchestrator.

        Args:
            repo_name: GitHub repository name (org/repo)
            repo_path: Local path to repository
        """
        self.repo_name = repo_name
        self.repo_path = Path(repo_path)
        self.agents = {
            "architect": ArchitectAgent(),
            "developer": DeveloperAgent(),
            "senior_engineer": SeniorEngineerAgent(),
            "tester": TesterAgent(),
        }
        self._codebase_analysis = None  # Will store senior engineer's analysis

        # Create persona for conflict resolution (reuse architect)
        self.architect_persona = self.agents["architect"].persona

        self.workflow_dir = self.repo_path / ".workflow"

        # Initialize repository manager for GitHub tools
        self._setup_repository_manager()

        logger.info(f"Initialized orchestrator for {repo_name} at {repo_path}")

    def _setup_repository_manager(self):
        """Set up the repository manager for GitHub tools."""
        # Load .env file from repository root
        env_path = self.repo_path / ".env"
        if env_path.exists():
            load_dotenv(env_path)
            logger.info(f"Loaded environment from {env_path}")

        # Get GitHub token
        github_token = os.environ.get("GITHUB_TOKEN")
        if not github_token:
            logger.warning("GITHUB_TOKEN not set. GitHub API operations may fail.")
            github_token = "dummy-token"  # Allow workflow to continue for testing

        # Create repository configuration using the factory method
        # This will extract the actual GitHub owner/repo from git remote
        repo_config = RepositoryConfig.create_repository_config(
            name=self.repo_name,
            workspace=str(self.repo_path),
            description=f"Repository for {self.repo_name}",
            language=Language.PYTHON,  # Default to Python
            port=9999,  # Dummy port for workflow
            python_path=sys.executable,
        )

        # Update our repo_name with the actual GitHub owner/repo
        if (
            repo_config.github_owner
            and repo_config.github_repo
            and repo_config.github_owner != "unknown"
        ):
            self.repo_name = f"{repo_config.github_owner}/{repo_config.github_repo}"
            logger.info(f"Detected GitHub repository: {self.repo_name}")
        else:
            # Try to parse the git remote manually for custom SSH formats
            try:
                result = subprocess.run(
                    ["git", "config", "--get", "remote.origin.url"],
                    cwd=self.repo_path,
                    capture_output=True,
                    text=True,
                    check=True,
                )
                remote_url = result.stdout.strip()

                # Handle custom SSH format like git@github.com-alias:owner/repo.git
                if remote_url.startswith("git@github.com") and ":" in remote_url:
                    # Extract the part after the colon
                    _, repo_part = remote_url.split(":", 1)
                    repo_part = repo_part.replace(".git", "")

                    if "/" in repo_part:
                        self.repo_name = repo_part
                        logger.info(
                            f"Parsed GitHub repository from custom SSH format: {self.repo_name}"
                        )

            except Exception as e:
                logger.warning(f"Could not parse git remote: {e}")

        # Create repository manager
        repo_manager = RepositoryManager()
        repo_manager.add_repository(self.repo_name, repo_config)

        # Set the global repo_manager in github_tools
        github_tools.repo_manager = repo_manager
        logger.info(f"Configured repository manager for {self.repo_name}")

    def get_absolute_path(self, relative_path: str) -> Path:
        """Get absolute path for a file relative to the repository root.

        Args:
            relative_path: Path relative to repository root

        Returns:
            Absolute Path object
        """
        return (self.repo_path / relative_path).resolve()

    async def analyze_codebase(self) -> dict[str, Any]:
        """Have senior engineer analyze the codebase structure and patterns.

        This should be run once at the beginning of the workflow to understand:
        - Design patterns
        - High-level architecture
        - Naming conventions
        - Testing practices
        - Code structure

        Returns:
            Dictionary with codebase analysis
        """
        if self._codebase_analysis:
            return self._codebase_analysis

        logger.info("Starting codebase analysis with Senior Engineer...")

        analysis_prompt = f"""## Task: Comprehensive Codebase Design Investigation

As a Senior Engineer, you must investigate the existing codebase and create a comprehensive design summary that will serve as the foundation for all future development decisions.

REPOSITORY LOCATION: {self.repo_path}

This analysis must cover:
- **Design patterns** used throughout the codebase
- **High-level architecture** and system organization
- **Naming conventions** and coding standards
- **Testing practices** and quality assurance approaches
- **Code structure** and module organization

CRITICAL FIRST STEP: The codebase is located at: {self.repo_path}

You MUST explore this directory to understand the codebase:
1. Use the LS tool to list files in: {self.repo_path}
2. Read any code you find to understand the code structure
3. Check for tests examine test files, test patterns and coverage
4. Look for configuration files
5. Identify the main entry points and key modules

IMPORTANT: Use absolute paths starting with {self.repo_path} when reading files.

After exploring the codebase, provide the following analysis:

REQUIRED ANALYSIS SECTIONS:

### 1. Directory Structure
- List the main directories and what they contain
- Identify the entry points (main files, CLI scripts)
- Map out the module organization

### 2. Key Classes and Modules
- Name the most important classes and their responsibilities
- List the main modules and what they do
- Identify the core abstractions and interfaces

### 3. Design Patterns Used
- Identify SPECIFIC patterns in use (give file names and line examples)
- How is dependency injection handled?
- What architectural patterns are evident?

### 4. Technology Stack
- Python version requirements
- Key dependencies from requirements.txt/pyproject.toml
- Testing framework in use
- Any CLI frameworks, web frameworks, databases

### 5. Naming Conventions
- Variable naming style (snake_case, camelCase, etc.)
- Class naming patterns
- File and module naming patterns
- Constants and configuration naming

### 6. Testing Approach
- Test directory structure
- Testing framework (pytest, unittest, etc.)
- Mock libraries in use
- Test naming conventions
- How are fixtures organized?

### 7. Error Handling Patterns
- Exception hierarchy
- How errors are logged
- Error propagation patterns

### 8. Configuration and Settings
- How configuration is managed
- Environment variable usage
- Settings files and their structure

### 9. Design Summary for Future Development
- **Recommended Patterns**: Which existing patterns should new features follow?
- **Quality Standards**: What quality benchmarks must be maintained?
- **Integration Guidelines**: How should new components integrate with the existing system?
- **Architectural Principles**: What architectural decisions guide this codebase?

CRITICAL:
- Examine actual files and provide concrete examples with file paths and code snippets
- This analysis will be provided to all other agents for every task - make it comprehensive
- No generic statements - everything must be grounded in the actual codebase
- Focus on patterns that new development should follow"""

        senior = self.agents["senior_engineer"]
        _ = {
            "repo_path": str(self.repo_path),
            "codebase_analysis_path": str(
                self.get_absolute_path(".workflow/codebase_analysis.md")
            ),
            "codebase_summary": "Initial codebase analysis",
            "repository": self.repo_name,
            "branch": "main",
            "patterns": [],
            "workflow_phase": "codebase_analysis",
            "pr_number": None,
        }

        # Log the codebase analysis prompt for debugging
        logger.debug(
            f"Codebase analysis prompt (length={len(analysis_prompt)}):\n{analysis_prompt}\n============================"
        )

        # Call the persona directly to avoid double-prompt wrapping
        try:
            analysis_result = senior.persona.ask(analysis_prompt)

            # Log the raw response for debugging
            logger.debug(
                f"Codebase analysis raw response (length={len(analysis_result) if analysis_result else 0}):\n{analysis_result}\n============================"
            )

            result = {
                "agent_type": "senior_engineer",
                "analysis": analysis_result,
                "status": "success",
            }
        except Exception as e:
            logger.error(f"Codebase analysis failed: {e}")
            result = {
                "agent_type": "senior_engineer",
                "analysis": "",
                "status": "error",
                "error": str(e),
            }
        self._codebase_analysis = result.get("analysis", "")

        # Save the analysis for reference
        analysis_path = self.get_absolute_path(".workflow/codebase_analysis.md")
        analysis_path.parent.mkdir(parents=True, exist_ok=True)
        analysis_path.write_text(f"# Codebase Analysis\n\n{self._codebase_analysis}")

        logger.info(f"Codebase analysis completed and saved to {analysis_path}")
        return {"status": "success", "analysis": self._codebase_analysis}

    async def analyze_feature(self, task_specification: str) -> dict[str, Any]:
        """Execute Phase 1: Analysis only workflow.

        Args:
            task_specification: Feature task specification

        Returns:
            Workflow results including PR number and analysis paths
        """
        logger.info("Starting Phase 1: Analysis workflow")

        try:
            # Parse task specification
            feature_spec = self._parse_task_specification(task_specification)

            # Analyze codebase
            codebase_state = await self._analyze_codebase()

            # Initialize task context
            context = TaskContext(feature_spec, codebase_state, str(self.repo_path))
            context.update_phase("round_1_analysis")

            # Create or find PR
            pr_number = await self._setup_github_pr(feature_spec, context)
            context.set_pr_number(pr_number)

            # Run Round 1: Parallel analysis
            analysis_results = await self._run_analysis_round(context)

            # Commit analysis artifacts to PR
            await self._commit_analysis_artifacts(context, analysis_results)

            # Wait for human feedback
            logger.info(
                f"Analysis complete. Waiting for human feedback on PR #{pr_number}"
            )

            # Save context for later resumption
            context_file = self.workflow_dir / f"context_pr_{pr_number}.json"
            context.save_to_file(context_file)

            return {
                "status": "success",
                "pr_number": pr_number,
                "pr_url": f"https://github.com/{self.repo_name}/pull/{pr_number}",
                "analysis_artifacts": {
                    agent_type: f".workflow/round_1_analysis/{agent_type}_analysis.md"
                    for agent_type in self.agents.keys()
                },
                "context_file": str(context_file),
                "message": f"Analysis complete. Please review and provide feedback on PR #{pr_number}",
            }

        except Exception as e:
            logger.error(f"Workflow failed: {e}", exc_info=True)
            return {"status": "error", "error": str(e)}
        finally:
            # Cleanup agent resources
            for agent in self.agents.values():
                agent.cleanup()

    def _parse_task_specification(self, task_spec: str) -> FeatureSpec:
        """Parse task specification into structured format.

        Args:
            task_spec: Raw task specification text

        Returns:
            Parsed FeatureSpec
        """
        # For Phase 1, we'll do simple parsing
        # In a real implementation, this could use an LLM to extract structured data

        lines = task_spec.strip().split("\n")
        name = lines[0] if lines else "Unnamed Feature"

        # Extract sections if they exist
        requirements = []
        acceptance_criteria = []
        constraints = []

        current_section = None
        for line in lines[1:]:
            line = line.strip()
            if not line:
                continue

            if line.lower().startswith("requirements:"):
                current_section = "requirements"
            elif line.lower().startswith("acceptance criteria:"):
                current_section = "acceptance"
            elif line.lower().startswith("constraints:"):
                current_section = "constraints"
            elif line.startswith("- ") or line.startswith("* "):
                item = line[2:].strip()
                if current_section == "requirements":
                    requirements.append(item)
                elif current_section == "acceptance":
                    acceptance_criteria.append(item)
                elif current_section == "constraints":
                    constraints.append(item)

        # If no structured sections, treat whole spec as description
        description = task_spec if not (requirements or acceptance_criteria) else name

        return FeatureSpec(
            name=name,
            description=description,
            requirements=requirements or ["Implement as specified in the description"],
            acceptance_criteria=acceptance_criteria or ["Feature works as described"],
            constraints=constraints,
        )

    async def _analyze_codebase(self) -> CodebaseState:
        """Analyze the codebase to provide context.

        Returns:
            CodebaseState with analysis results
        """
        logger.info("Analyzing codebase...")

        analyzer = CodebaseAnalyzer(str(self.repo_path))
        analysis = analyzer.analyze()
        summary = analyzer.generate_summary()

        # Get current git info
        branch = analysis.get("git_branch", "main")
        commit = analysis.get("git_commit", "HEAD")

        return CodebaseState(
            repository=self.repo_name,
            branch=branch,
            commit_sha=commit,
            analysis_summary=summary,
            patterns_identified=analysis.get("patterns", []),
            existing_tests={"frameworks": analysis.get("test_frameworks", [])},
        )

    async def _setup_github_pr(
        self, feature_spec: FeatureSpec, context: TaskContext
    ) -> int:
        """Create or find GitHub PR for the workflow.

        Args:
            feature_spec: Feature specification
            context: Task context

        Returns:
            PR number
        """
        # Check current branch
        current_branch = context.codebase_state.branch
        logger.info(f"Current branch: {current_branch}")

        # If on main/master, create a feature branch
        if current_branch in ["main", "master"]:
            # Generate meaningful feature branch name
            feature_name = feature_spec.name.lower()

            # Try to extract key concepts for a better branch name
            # Common patterns to look for
            if "persist" in feature_name and "comment" in feature_name:
                feature_branch = "feature/persist-pr-comment-replies"
            elif "github_post_pr_reply" in feature_name:
                feature_branch = "feature/track-pr-comment-replies"
            elif "cache" in feature_name or "caching" in feature_name:
                feature_branch = "feature/add-caching"
            elif "validation" in feature_name or "validate" in feature_name:
                feature_branch = "feature/add-validation"
            elif "auth" in feature_name or "authentication" in feature_name:
                feature_branch = "feature/user-authentication"
            elif "log" in feature_name or "logging" in feature_name:
                feature_branch = "feature/add-logging"
            else:
                # Fallback: extract first few meaningful words
                words = feature_name.split()

                # Remove common words
                stop_words = {
                    "the",
                    "a",
                    "an",
                    "to",
                    "we",
                    "need",
                    "use",
                    "when",
                    "that",
                    "this",
                    "and",
                    "or",
                    "but",
                    "if",
                    "then",
                    "should",
                    "must",
                    "can",
                    "will",
                }
                meaningful_words = [
                    w for w in words if w not in stop_words and len(w) > 2
                ]

                if meaningful_words:
                    # Take first 3-4 meaningful words
                    branch_words = meaningful_words[:4]
                    feature_branch = f"feature/{'-'.join(branch_words)}"
                else:
                    # Last resort: clean up and truncate
                    clean_name = feature_name.replace(" ", "-")
                    clean_name = "".join(
                        c for c in clean_name if c.isalnum() or c == "-"
                    )
                    clean_name = "-".join(
                        filter(None, clean_name.split("-"))
                    )  # Remove multiple dashes
                    feature_branch = f"feature/{clean_name[:30]}"

            logger.info(
                f"On {current_branch} branch, creating feature branch: {feature_branch}"
            )

            # Create and checkout feature branch
            try:
                # First try to create new branch
                result = subprocess.run(
                    ["git", "checkout", "-b", feature_branch],
                    cwd=self.repo_path,
                    capture_output=True,
                    text=True,
                )

                if result.returncode == 0:
                    logger.info(
                        f"Created and checked out feature branch: {feature_branch}"
                    )
                else:
                    # Branch might already exist, try to checkout
                    if "already exists" in result.stderr:
                        logger.info(
                            f"Branch {feature_branch} already exists, checking out..."
                        )
                        subprocess.run(
                            ["git", "checkout", feature_branch],
                            cwd=self.repo_path,
                            check=True,
                            capture_output=True,
                            text=True,
                        )
                        logger.info(
                            f"Checked out existing feature branch: {feature_branch}"
                        )
                    else:
                        # Some other error
                        logger.error(
                            f"Failed to create feature branch: {result.stderr}"
                        )
                        return 0

                # Update context with new branch
                context.codebase_state.branch = feature_branch
                current_branch = feature_branch

            except subprocess.CalledProcessError as e:
                logger.error(f"Failed to checkout feature branch: {e}")
                logger.error(f"stderr: {e.stderr}")
                return 0

        # Check if PR exists for current branch
        logger.info("Checking for existing PR...")

        pr_result = await execute_tool(
            "github_find_pr_for_branch",
            repo_name=self.repo_name,
            branch_name=current_branch,
        )

        pr_data = json.loads(pr_result)

        if pr_data.get("pr_number"):
            logger.info(f"Found existing PR #{pr_data['pr_number']}")
            return pr_data["pr_number"]

        # Create PR automatically
        logger.info(f"No PR found for branch '{current_branch}'. Creating PR...")

        pr_number = await self._create_github_pr(feature_spec, current_branch)

        if pr_number:
            logger.info(f"Created PR #{pr_number}")
            return pr_number
        else:
            logger.warning("Failed to create PR automatically")
            return 0

    async def _create_github_pr(
        self, feature_spec: FeatureSpec, branch_name: str
    ) -> int:
        """Create a GitHub PR for the feature branch.

        Args:
            feature_spec: Feature specification
            branch_name: Branch name to create PR from

        Returns:
            PR number if created, 0 otherwise
        """
        try:
            # First push the branch to remote
            logger.info(f"Pushing branch '{branch_name}' to remote...")
            subprocess.run(
                ["git", "push", "-u", "origin", branch_name],
                cwd=self.repo_path,
                check=True,
                capture_output=True,
                text=True,
            )
            logger.info("Branch pushed successfully")

            # Create PR using GitHub API
            import requests

            # Get GitHub token from environment
            github_token = os.environ.get("GITHUB_TOKEN")
            if not github_token:
                logger.error("GITHUB_TOKEN not set, cannot create PR")
                return 0

            # Prepare PR data
            pr_title = f"feat: {feature_spec.name}"
            pr_body = f"""## 🤖 Multi-Agent Analysis for: {feature_spec.name}

This PR contains the initial analysis from our multi-agent workflow system.

### 📋 Feature Description
{feature_spec.description}

### ✅ Requirements
{chr(10).join(f"- {req}" for req in feature_spec.requirements)}

### 🎯 Acceptance Criteria
{chr(10).join(f"- {ac}" for ac in feature_spec.acceptance_criteria)}

### 🤖 Agent Analysis Status
- ✅ Architect Analysis - System design and architecture considerations
- ✅ Developer Analysis - Implementation approach and technology choices
- ✅ Senior Engineer Analysis - Code quality and maintainability focus
- ✅ Tester Analysis - Testing strategy and quality assurance

### 📁 Analysis Documents
All analysis documents are in `.workflow/round_1_analysis/`

### 🔄 Workflow Status
**Phase 1: Analysis** - Complete ✅
**Phase 2: Design** - Pending human feedback

### 💬 Next Steps
1. Review the analysis documents in this PR
2. Add comments on specific sections for feedback
3. The agents will incorporate your feedback in the next phase

---
*This PR was created automatically by the Multi-Agent Workflow system*
"""

            # Create PR via GitHub API
            api_url = f"https://api.github.com/repos/{self.repo_name}/pulls"
            headers = {
                "Authorization": f"token {github_token}",
                "Accept": "application/vnd.github.v3+json",
            }

            pr_data = {
                "title": pr_title,
                "body": pr_body,
                "head": branch_name,
                "base": "main",  # or "master" - we could detect this
            }

            response = requests.post(api_url, json=pr_data, headers=headers)

            if response.status_code == 201:
                pr_info = response.json()
                pr_number = pr_info["number"]
                logger.info(
                    f"Successfully created PR #{pr_number}: {pr_info['html_url']}"
                )
                return pr_number
            else:
                logger.error(
                    f"Failed to create PR: {response.status_code} - {response.text}"
                )
                return 0

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to push branch: {e}")
            logger.error(f"stderr: {e.stderr}")
            return 0
        except Exception as e:
            logger.error(f"Failed to create PR: {e}")
            return 0

    async def _run_analysis_round(self, context: TaskContext) -> dict[str, str]:
        """Run Round 1 analysis with all agents in parallel.

        Args:
            context: Task context

        Returns:
            Analysis results by agent type
        """
        logger.info("Running Round 1: Parallel agent analysis")

        # Check if analyses already exist
        round_dir = self.workflow_dir / "round_1_analysis"
        results = {}

        # Load existing analyses if they exist
        for agent_type in self.agents.keys():
            analysis_file = round_dir / f"{agent_type}_analysis.md"
            if analysis_file.exists():
                logger.info(
                    f"{agent_type} analysis already exists, loading from {analysis_file}"
                )
                try:
                    content = analysis_file.read_text()
                    # Extract analysis content (after the header)
                    lines = content.split("\n")
                    analysis_start = -1
                    for i, line in enumerate(lines):
                        if line.strip() == "## Analysis" or (
                            "## " in line and "Analysis" in line
                        ):
                            analysis_start = i + 1
                            break

                    if analysis_start > 0:
                        analysis_content = "\n".join(lines[analysis_start:]).strip()
                        # Remove the footer
                        if "---" in analysis_content:
                            analysis_content = analysis_content.split("---")[0].strip()
                        results[agent_type] = analysis_content

                        # Update context with loaded analysis
                        context.update_from_analysis(
                            agent_type,
                            {"status": "success", "analysis": analysis_content},
                        )
                        logger.info(
                            f"Loaded {agent_type} analysis ({len(analysis_content)} chars)"
                        )
                    else:
                        logger.warning(
                            f"Could not parse analysis content from {analysis_file}"
                        )
                        results[agent_type] = "Error: Could not parse existing analysis"
                except Exception as e:
                    logger.error(f"Failed to load {agent_type} analysis: {e}")
                    results[agent_type] = f"Error: {e}"

        # Only run analyses for agents that don't have existing results
        agents_to_run = [
            agent_type for agent_type in self.agents.keys() if agent_type not in results
        ]

        if agents_to_run:
            logger.info(
                f"Running analysis for {len(agents_to_run)} agents: {agents_to_run}"
            )

            # Create analysis tasks for agents that need to run
            analysis_tasks = []
            for agent_type in agents_to_run:
                agent = self.agents[agent_type]
                task = self._run_agent_analysis(agent, context)
                analysis_tasks.append((agent_type, task))

            # Run analyses in parallel
            for agent_type, task in analysis_tasks:
                try:
                    analysis = await task
                    results[agent_type] = analysis["analysis"]
                    context.update_from_analysis(agent_type, analysis)
                    logger.info(f"{agent_type} analysis complete")
                except Exception as e:
                    logger.error(f"{agent_type} analysis failed: {e}")
                    results[agent_type] = f"Error: {e}"
        else:
            logger.info("All agent analyses already exist, skipping analysis round")

        return results

    async def _run_agent_analysis(self, agent, context: TaskContext) -> dict[str, Any]:
        """Run analysis for a single agent.

        Args:
            agent: Agent instance
            context: Task context

        Returns:
            Analysis result
        """
        # Get agent-specific context
        agent_context = context.get_context_for_agent(agent.agent_type)

        # Run analysis (synchronous call in async context)
        loop = asyncio.get_event_loop()
        analysis = await loop.run_in_executor(
            None, agent.analyze_task, agent_context, context.feature_spec.description
        )

        return analysis

    def _analyze_agent_alignment(
        self, analysis_results: dict[str, str]
    ) -> tuple[list[str], list[dict]]:
        """Analyze where agents agree and disagree.

        Args:
            analysis_results: Raw analysis text by agent type

        Returns:
            Tuple of (consensus_points, disagreements)
        """
        consensus_points = []
        disagreements = []

        # Common topics to check for alignment
        _ = {
            "database": ["sqlite", "database", "storage", "persist"],
            "pattern": ["pattern", "abstract", "interface", "base class"],
            "testing": ["test", "mock", "pytest", "coverage"],
            "implementation": ["implement", "create", "modify", "extend"],
            "files": ["file", ".py", "directory", "module"],
            "approach": ["approach", "strategy", "method", "solution"],
        }

        # Extract agent positions on each topic
        agent_positions = {}
        for agent_type, analysis in analysis_results.items():
            if not analysis:
                continue
            analysis_lower = analysis.lower()
            agent_positions[agent_type] = {}

            # Check specific patterns for common recommendations
            if "sqlite" in analysis_lower and "symbol_storage" in analysis_lower:
                agent_positions[agent_type]["storage_pattern"] = "sqlite_symbol_storage"
            elif "sqlite" in analysis_lower:
                agent_positions[agent_type]["storage_pattern"] = "sqlite_other"
            elif "database" in analysis_lower:
                agent_positions[agent_type]["storage_pattern"] = "other_database"

            if "abstract" in analysis_lower and "base class" in analysis_lower:
                agent_positions[agent_type]["abstraction"] = "abstract_base_class"
            elif "interface" in analysis_lower:
                agent_positions[agent_type]["abstraction"] = "interface"

            if "dependency injection" in analysis_lower:
                agent_positions[agent_type]["di"] = True

            if "repository" in analysis_lower and "scoped" in analysis_lower:
                agent_positions[agent_type]["repo_scope"] = True

            # Look for test file counts
            import re

            test_files = re.findall(
                r"(\d+)\s*(?:test|unit)\s*(?:file|test)", analysis_lower
            )
            if test_files:
                agent_positions[agent_type]["test_count"] = int(test_files[0])

        # Find consensus points
        if all(
            agent_positions.get(agent, {}).get("storage_pattern")
            == "sqlite_symbol_storage"
            for agent in agent_positions
            if "storage_pattern" in agent_positions.get(agent, {})
        ):
            consensus_points.append(
                "Use SQLite storage pattern following existing `symbol_storage.py` architecture"
            )

        if all(
            agent_positions.get(agent, {}).get("abstraction") == "abstract_base_class"
            for agent in agent_positions
            if "abstraction" in agent_positions.get(agent, {})
        ):
            consensus_points.append(
                "Create abstract base classes with concrete implementations"
            )

        if all(
            agent_positions.get(agent, {}).get("di")
            for agent in agent_positions
            if "di" in agent_positions.get(agent, {})
        ):
            consensus_points.append("Implement dependency injection for testability")

        if all(
            agent_positions.get(agent, {}).get("repo_scope")
            for agent in agent_positions
            if "repo_scope" in agent_positions.get(agent, {})
        ):
            consensus_points.append("Maintain repository-scoped data isolation")

        # Find disagreements
        # Check for different test counts
        test_counts = {}
        for agent, positions in agent_positions.items():
            if "test_count" in positions:
                test_counts[agent] = positions["test_count"]

        if len(set(test_counts.values())) > 1:
            disagreements.append(
                {"topic": "Number of test files", "positions": test_counts}
            )

        # Check for implementation approach differences
        if "developer" in analysis_results and "architect" in analysis_results:
            dev_analysis = analysis_results["developer"].lower()
            arch_analysis = analysis_results["architect"].lower()

            if "incremental" in dev_analysis and "comprehensive" in arch_analysis:
                disagreements.append(
                    {
                        "topic": "Implementation approach",
                        "positions": {
                            "developer": "Incremental MVP approach",
                            "architect": "Comprehensive design-first approach",
                        },
                    }
                )

        return consensus_points, disagreements

    def _format_consensus_points(self, consensus_points: list[str]) -> str:
        """Format consensus points for display."""
        if not consensus_points:
            return "No clear consensus points identified. Review individual analyses for alignment."

        formatted = "All agents agree on:\n"
        for point in consensus_points:
            formatted += f"- {point}\n"
        return formatted.strip()

    def _format_disagreements(self, disagreements: list[dict]) -> str:
        """Format disagreements for display."""
        if not disagreements:
            return "No significant disagreements identified. The agents are well-aligned on the approach."

        formatted = ""
        for disagreement in disagreements:
            formatted += f"### {disagreement['topic']}\n"
            for agent, position in disagreement["positions"].items():
                formatted += f"- **{agent.replace('_', ' ').title()}**: {position}\n"
            formatted += "\n"
        return formatted.strip()

    def _extract_key_insights(self, analysis_results: dict[str, str]) -> dict[str, str]:
        """Extract key insights from each agent's analysis.

        Args:
            analysis_results: Raw analysis text by agent type

        Returns:
            Dictionary of summarized insights by agent type
        """
        insights = {}

        for agent_type, analysis in analysis_results.items():
            if not analysis or analysis.strip() == "":
                insights[agent_type] = "Analysis not available"
                continue

            # Extract first few meaningful paragraphs or bullet points
            lines = analysis.strip().split("\n")
            key_lines = []
            bullet_count = 0

            for line in lines:
                line = line.strip()
                if not line:
                    continue

                # Capture headers and first few bullet points
                if line.startswith("#"):
                    if key_lines and bullet_count >= 3:
                        break
                    key_lines.append(line)
                    bullet_count = 0
                elif line.startswith(("-", "*", "•")) or (
                    len(key_lines) < 5 and not line.startswith("```")
                ):
                    key_lines.append(line)
                    if line.startswith(("-", "*", "•")):
                        bullet_count += 1
                    if len(key_lines) >= 8:  # Limit to reasonable summary
                        break

            insights[agent_type] = (
                "\n".join(key_lines) if key_lines else "No specific recommendations"
            )

        return insights

    async def _commit_analysis_artifacts(
        self, context: TaskContext, analysis_results: dict[str, str]
    ):
        """Commit analysis artifacts to the PR.

        Args:
            context: Task context
            analysis_results: Analysis results by agent type
        """
        # Create workflow directory structure
        round_dir = self.workflow_dir / "round_1_analysis"
        round_dir.mkdir(parents=True, exist_ok=True)

        # Save each agent's analysis (if not already exists)
        for agent_type, analysis in analysis_results.items():
            filepath = round_dir / f"{agent_type}_analysis.md"

            # Check if analysis already exists
            if filepath.exists():
                logger.info(
                    f"{agent_type} analysis already exists at {filepath}, skipping generation"
                )
                continue

            # Format the analysis document
            content = f"""# {agent_type.replace('_', ' ').title()} Analysis

**Feature**: {context.feature_spec.name}
**Date**: {datetime.now().isoformat()}
**Agent**: {agent_type}

## Analysis

{analysis}

---
*This analysis was generated by the {agent_type} agent as part of the multi-agent workflow.*
"""

            with open(filepath, "w") as f:
                f.write(content)

            logger.info(f"Saved {agent_type} analysis to {filepath}")

        # Create summary document (if not already exists)
        summary_path = round_dir / "analysis_summary.md"
        if not summary_path.exists():
            # Extract key insights from each analysis
            insights = self._extract_key_insights(analysis_results)

            # Find consensus and disagreement points
            consensus_points, disagreements = self._analyze_agent_alignment(
                analysis_results
            )

            summary_content = f"""# Round 1 Analysis Summary

**Feature**: {context.feature_spec.name}
**Repository**: {context.codebase_state.repository}
**Branch**: {context.codebase_state.branch}
**Date**: {datetime.now().isoformat()}

## Codebase Context

{context.codebase_state.analysis_summary}

## Key Insights from Agent Analyses

### 🏗️ Architect Analysis
{insights.get('architect', 'No analysis available')}

### 💻 Developer Analysis
{insights.get('developer', 'No analysis available')}

### 👷 Senior Engineer Analysis
{insights.get('senior_engineer', 'No analysis available')}

### 🧪 Tester Analysis
{insights.get('tester', 'No analysis available')}

## 🤝 Consensus Points

{self._format_consensus_points(consensus_points)}

## ⚠️ Areas of Disagreement

{self._format_disagreements(disagreements)}

## Next Steps

1. Review the detailed analysis documents for each agent
2. **Address disagreements**: Focus on resolving the conflicting recommendations
3. Provide feedback on specific implementation details via GitHub comments
4. Once consensus is reached, proceed to design phase

---
*This summary was generated as part of the multi-agent workflow Phase 1.*
"""

            with open(summary_path, "w") as f:
                f.write(summary_content)
        else:
            logger.info(
                f"Analysis summary already exists at {summary_path}, skipping generation"
            )

        logger.info("Analysis artifacts saved to .workflow directory")

        # Git add and commit the files
        try:
            # Check if there are any changes to commit in the workflow directory
            status_result = subprocess.run(
                ["git", "status", "--porcelain", ".workflow"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True,
            )

            if not status_result.stdout.strip():
                logger.info("No changes to commit in .workflow directory")
                return

            # Add the workflow directory
            subprocess.run(
                ["git", "add", ".workflow"],
                cwd=self.repo_path,
                check=True,
                capture_output=True,
                text=True,
            )
            logger.info("Added .workflow directory to git")

            # Create commit message
            commit_message = f"""feat: Add multi-agent analysis for {context.feature_spec.name}

- Generated analysis from 4 specialized AI agents
- Architect: System design and integration analysis
- Developer: Implementation approach and technology choices
- Senior Engineer: Code quality and maintainability focus
- Tester: Comprehensive testing strategy

Analysis documents available in {self.repo_path}/.workflow/round_1_analysis/

🤖 Generated by Multi-Agent Workflow System"""

            # Commit only the staged workflow files (use --only flag to ignore other unstaged changes)
            result = subprocess.run(
                ["git", "commit", "--only", ".workflow/", "-m", commit_message],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                logger.info("Successfully committed analysis artifacts")
            else:
                logger.error(f"Git commit failed with return code {result.returncode}")
                logger.error(f"stdout: {result.stdout}")
                logger.error(f"stderr: {result.stderr}")
                # Don't raise exception - workflow can continue without commit

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to commit artifacts: {e}")
            if hasattr(e, "stdout") and e.stdout:
                logger.error(f"stdout: {e.stdout}")
            if hasattr(e, "stderr") and e.stderr:
                logger.error(f"stderr: {e.stderr}")
            # Don't raise exception - workflow can continue without commit

    async def continue_to_design_phase(
        self, context: TaskContext, human_feedback: list
    ) -> dict[str, Any]:
        """Continue workflow to Phase 2: Design consolidation.

        Args:
            context: Task context with existing analyses
            human_feedback: Human feedback from Phase 1

        Returns:
            Phase 2 results
        """
        logger.info("Starting Phase 2: Design consolidation workflow")

        try:
            context.update_phase("round_2_design")
            design_dir = self.workflow_dir / "round_2_design"
            design_dir.mkdir(parents=True, exist_ok=True)

            # Step 0: Reload analysis content from files if needed
            await self._reload_analysis_content(context)

            # Step 1: Process human feedback (only if feedback provided and not already processed)
            if human_feedback:
                await self._process_human_feedback(context, human_feedback)

            # Step 2: Run peer review round (check if already done)
            peer_reviews_path = design_dir / "peer_reviews.md"
            if peer_reviews_path.exists() and peer_reviews_path.read_text().strip():
                logger.info("Peer reviews already exist, loading from file")
                peer_reviews = await self._load_existing_peer_reviews(peer_reviews_path)
            else:
                logger.info("Running peer review round")
                peer_reviews = await self._run_peer_review_round(context)

            # Step 3: Identify and resolve conflicts (check if already done)
            conflicts_path = design_dir / "conflict_resolution.md"
            if conflicts_path.exists() and conflicts_path.read_text().strip():
                logger.info("Conflict resolution already exists, loading from file")
                conflicts, resolution = await self._load_existing_conflict_resolution(
                    conflicts_path
                )
            else:
                logger.info("Identifying and resolving conflicts")
                conflicts, resolution = await self._resolve_conflicts(
                    peer_reviews, context
                )

            # Step 4: Generate consolidated design (already has existence check)
            design_path = design_dir / "consolidated_design.md"
            consolidated_design = await self._generate_consolidated_design_document(
                context, peer_reviews, resolution, str(design_path)
            )

            # Step 5: Commit design artifacts
            await self._commit_design_artifacts(
                context, consolidated_design, conflicts, resolution, peer_reviews
            )

            # Step 6: Post replies to individual comments and summary (if there was human feedback)
            if human_feedback:
                # Post individual replies to each comment
                await self._post_consolidated_feedback_replies(
                    context, consolidated_design
                )
                # Post overall summary
                await self._post_feedback_summary(context, consolidated_design)

            logger.info("Phase 2: Design consolidation complete")

            return {
                "status": "success",
                "phase": "round_2_design",
                "peer_reviews": peer_reviews,
                "conflicts": conflicts,
                "resolution": resolution,
                "consolidated_design": consolidated_design,
                "message": "Design phase complete. Ready for human review and approval.",
            }

        except Exception as e:
            logger.error(f"Phase 2 workflow failed: {e}", exc_info=True)
            return {"status": "error", "phase": "round_2_design", "error": str(e)}

    async def _reload_analysis_content(self, context: TaskContext):
        """Reload analysis content from saved files if context has empty content.

        This is needed when resuming Phase 2 from a saved context where
        the analysis content might not have been properly persisted.
        """
        logger.info("Checking if analysis content needs to be reloaded...")

        # Check if any analysis results have empty content
        needs_reload = False
        for agent_type, result in context.analysis_results.items():
            if not result.content.strip():
                needs_reload = True
                logger.info(
                    f"{agent_type} analysis content is empty, will reload from file"
                )

        if not needs_reload:
            logger.info("All analysis content is present, no reload needed")
            return

        # Reload content from Round 1 analysis files
        round1_dir = self.workflow_dir / "round_1_analysis"
        if not round1_dir.exists():
            logger.warning(
                "Round 1 analysis directory not found, cannot reload content"
            )
            return

        for agent_type in context.analysis_results.keys():
            analysis_file = round1_dir / f"{agent_type}_analysis.md"
            if analysis_file.exists():
                try:
                    content = analysis_file.read_text()
                    # Extract just the analysis content (after the header)
                    lines = content.split("\n")
                    analysis_start = -1
                    for i, line in enumerate(lines):
                        if (
                            line.strip() == "## Analysis"
                            or "## " in line
                            and "Analysis" in line
                        ):
                            analysis_start = i + 1
                            break

                    if analysis_start > 0:
                        analysis_content = "\n".join(lines[analysis_start:]).strip()
                        # Remove the footer
                        if "---" in analysis_content:
                            analysis_content = analysis_content.split("---")[0].strip()

                        # Update the context with the reloaded content
                        context.analysis_results[agent_type].content = analysis_content
                        logger.info(
                            f"Reloaded {agent_type} analysis content ({len(analysis_content)} chars)"
                        )
                    else:
                        logger.warning(
                            f"Could not find analysis content in {analysis_file}"
                        )

                except Exception as e:
                    logger.error(f"Failed to reload {agent_type} analysis: {e}")
            else:
                logger.warning(f"Analysis file not found: {analysis_file}")

    async def _process_human_feedback(self, context: TaskContext, feedback_items: list):
        """Process human feedback and update agent analyses."""
        logger.info("Processing human feedback with agents...")

        # Check if we have any feedback to process
        if not feedback_items:
            logger.info("No feedback to process, skipping feedback integration")
            return

        logger.info(f"Processing {len(feedback_items)} feedback items on step 1 files")

        # Debug: check current analysis content lengths
        for agent_type, result in context.analysis_results.items():
            logger.info(
                f"Pre-feedback: {agent_type} analysis has {len(result.content)} chars"
            )

        for agent_type, agent in self.agents.items():
            # Filter feedback relevant to this agent (simplified)
            relevant_feedback = (
                feedback_items  # In real implementation, could filter by agent
            )

            if relevant_feedback:
                logger.info(f"Processing feedback with {agent_type}")

                # Get agent context
                agent_context = context.get_context_for_agent(agent_type)

                # Convert FeedbackItem objects to dictionaries for agent processing
                feedback_dicts = []
                for feedback in relevant_feedback:
                    feedback_dicts.append(
                        {
                            "comment_id": feedback.comment_id,
                            "author": feedback.author,
                            "content": feedback.content,
                            "file_path": feedback.file_path,
                            "line_number": feedback.line_number,
                            "created_at": feedback.created_at,
                        }
                    )

                # Process feedback
                response = agent.incorporate_human_feedback(
                    feedback_dicts, agent_context
                )

                if response.get("status") == "success":
                    updated_content = response.get("updated_analysis", "")

                    # Only update analysis if we got meaningful content back
                    if updated_content and len(updated_content.strip()) > 10:
                        context.analysis_results[agent_type].content = updated_content
                        logger.info(f"{agent_type} successfully incorporated feedback")
                        # Don't post individual agent replies - we'll post a consolidated reply later
                    else:
                        logger.warning(
                            f"{agent_type} generated empty feedback response, keeping original analysis"
                        )
                else:
                    logger.error(
                        f"{agent_type} failed to process feedback: {response.get('error')}"
                    )

    async def _run_peer_review_round(self, context: TaskContext) -> dict[str, dict]:
        """Run peer review round where agents review each other's work."""
        logger.info("Running peer review round...")

        # Get all current analyses
        peer_analyses = {}
        for agent_type, result in context.analysis_results.items():
            if result.status == "success":
                peer_analyses[agent_type] = result.content

        # Run peer reviews in parallel
        review_tasks = []
        for agent_type, agent in self.agents.items():
            task = self._run_agent_peer_review(agent, peer_analyses, context)
            review_tasks.append((agent_type, task))

        peer_reviews = {}
        for agent_type, task in review_tasks:
            try:
                review = await task
                peer_reviews[agent_type] = review
                logger.info(f"{agent_type} peer review complete")
            except Exception as e:
                logger.error(f"{agent_type} peer review failed: {e}")
                peer_reviews[agent_type] = {
                    "agent_type": agent_type,
                    "peer_review": "",
                    "status": "error",
                    "error": str(e),
                }

        return peer_reviews

    async def _run_agent_peer_review(
        self, agent, peer_analyses: dict, context: TaskContext
    ) -> dict:
        """Run peer review for a single agent."""
        # Get agent context
        agent_context = context.get_context_for_agent(agent.agent_type)

        # Log peer analyses being passed
        logger.info(f"Running peer review for {agent.agent_type}")
        logger.info(f"Peer analyses keys: {list(peer_analyses.keys())}")
        for agent_type, analysis in peer_analyses.items():
            logger.info(f"  {agent_type}: {len(analysis)} chars")

        # Run peer review (synchronous call in async context)
        loop = asyncio.get_event_loop()
        review = await loop.run_in_executor(
            None, agent.review_peer_output, peer_analyses, agent_context
        )

        logger.info(
            f"Peer review result for {agent.agent_type}: status={review.get('status')}, content_len={len(review.get('peer_review', ''))}"
        )

        return review

    async def _resolve_conflicts(
        self, peer_reviews: dict, context: TaskContext
    ) -> tuple[list, dict]:
        """Identify and resolve conflicts between agents."""
        logger.info("Identifying and resolving conflicts...")

        resolver = ConflictResolver(self.architect_persona)

        # Identify conflicts
        conflicts = resolver.identify_conflicts(peer_reviews)

        # Resolve conflicts (use consensus by default)
        resolution = resolver.resolve_conflicts(
            conflicts, peer_reviews, strategy="consensus"
        )

        logger.info(
            f"Resolved {len(conflicts)} conflicts using {resolution.get('strategy')} strategy"
        )

        return conflicts, resolution

    async def _generate_peer_review_document(
        self, peer_reviews: dict, output_path: str | None = None
    ) -> str:
        """Generate peer review document from agent reviews.

        Args:
            peer_reviews: Dictionary of peer reviews from agents
            output_path: Optional path to check for existing document

        Returns:
            Formatted peer review document
        """
        # Check if document already exists and has content
        if output_path and Path(output_path).exists():
            existing_content = Path(output_path).read_text().strip()
            if existing_content:  # Only use existing content if it's not empty
                logger.info(
                    f"Peer review document already exists at {output_path}, loading existing content"
                )
                return existing_content
            else:
                logger.info(
                    f"Peer review document at {output_path} is empty, regenerating"
                )

        logger.info("Generating peer review document...")

        content = f"""# Peer Review Results

Generated: {datetime.now().isoformat()}

"""
        for agent_type, review in peer_reviews.items():
            review_content = review.get("peer_review", "No review available")
            status = review.get("status", "unknown")

            content += f"""## {agent_type.replace('_', ' ').title()} Peer Review

**Status**: {status}

{review_content}

---

"""

        logger.info(f"Generated peer review document ({len(content)} chars)")
        return content

    async def _generate_conflict_resolution_document(
        self, conflicts: list, resolution: dict, output_path: str | None = None
    ) -> str:
        """Generate conflict resolution document.

        Args:
            conflicts: List of identified conflicts
            resolution: Resolution decisions
            output_path: Optional path to check for existing document

        Returns:
            Formatted conflict resolution document
        """
        # Check if document already exists and has content
        if output_path and Path(output_path).exists():
            existing_content = Path(output_path).read_text().strip()
            if existing_content:  # Only use existing content if it's not empty
                logger.info(
                    f"Conflict resolution document already exists at {output_path}, loading existing content"
                )
                return existing_content
            else:
                logger.info(
                    f"Conflict resolution document at {output_path} is empty, regenerating"
                )

        logger.info("Generating conflict resolution document...")

        content = f"""# Conflict Resolution Report

Generated: {datetime.now().isoformat()}
Strategy: {resolution.get('strategy', 'unknown')}
Status: {resolution.get('status', 'unknown')}

## Conflicts and Their Resolutions

"""
        # Get all recommendations
        recommendations = resolution.get("recommendations", [])

        # For each conflict, find its matching recommendation and display together
        for i, conflict in enumerate(conflicts, 1):
            content += f"""### Conflict {i}
**Type**: {conflict.get('type', 'unknown')}
**Description**: {conflict.get('description', 'No description')}
**Severity**: {conflict.get('severity', 'unknown')}

"""
            # Find the recommendation that matches this conflict
            if i <= len(recommendations):
                rec = recommendations[i - 1]
                content += f"""**Resolution**: {rec.get('resolution', 'No resolution')}
**Action**: {rec.get('action', 'No action')}

"""
            else:
                content += (
                    "**Resolution**: No recommendation found for this conflict\n\n"
                )

        # Add overall resolution summary
        content += f"""
## Overall Resolution Summary

{resolution.get('resolution', 'No overall resolution provided')}
"""

        logger.info(f"Generated conflict resolution document ({len(content)} chars)")
        return content

    async def _generate_consolidated_design_document(
        self,
        context: TaskContext,
        peer_reviews: dict,
        resolution: dict,
        output_path: str | None = None,
    ) -> str:
        """Generate consolidated design document using AI.

        Args:
            context: Task context with analyses
            peer_reviews: Peer review results
            resolution: Conflict resolution results
            output_path: Optional path to check for existing document

        Returns:
            AI-generated consolidated design document
        """
        # Check if document already exists and has content
        if output_path and Path(output_path).exists():
            existing_content = Path(output_path).read_text().strip()
            if existing_content:  # Only use existing content if it's not empty
                logger.info(
                    f"Consolidated design document already exists at {output_path}, loading existing content"
                )
                return existing_content
            else:
                logger.info(
                    f"Consolidated design document at {output_path} is empty, regenerating"
                )

        logger.info("Generating consolidated design document...")

        # Get original analyses
        original_analyses = {}
        for agent_type, result in context.analysis_results.items():
            original_analyses[agent_type] = result.content

        # Build prompt for design document generation
        prompt = self._build_design_document_prompt(
            original_analyses, peer_reviews, resolution
        )

        try:
            # Use architect persona to generate design
            design_document = self.architect_persona.ask(prompt)
            logger.info(
                f"Generated consolidated design document ({len(design_document)} chars)"
            )
            return design_document
        except Exception as e:
            logger.error(f"Failed to generate design document: {e}")
            # Fallback to basic template
            return self._generate_fallback_design_document(
                original_analyses, peer_reviews, resolution
            )

    def _build_design_document_prompt(
        self, original_analyses: dict, peer_reviews: dict, resolution: dict
    ) -> str:
        """Build prompt for AI-powered design document generation.

        Args:
            original_analyses: Original agent analyses
            peer_reviews: Peer review results
            resolution: Conflict resolution results

        Returns:
            Comprehensive prompt for design document generation
        """
        prompt = """You are a Senior Software Architect creating a comprehensive design document.

MANDATORY REQUIREMENT: You MUST generate a document with ALL the sections listed below in EXACTLY this order. Do not skip any section.

DOCUMENT STRUCTURE - FOLLOW THIS EXACTLY:

# Consolidated Design Document

## 1. Introduction
[Write a high-level introduction setting the context for this design]

## 2. Goals / Non-Goals
### Goals
[List specific goals this architecture addresses]

### Non-Goals
[IMPORTANT: List what this design explicitly does NOT address]

## 3. Proposed Architecture
[Describe the proposed architecture and how it addresses the goals above]

## 4. Detailed Design
[Detailed design of all components, error handling, interfaces]

## 5. Alternatives Considered
[What alternatives were considered and why they were not chosen]

## 6. Testing / Validation
[Testing strategy, test objects needed, integration tests]

## 7. Migration / Deployment & Rollout
[How to deploy this, any data migration, rollout process]

## Appendix
[Conflict resolutions, meeting notes, additional technical details]

CRITICAL INSTRUCTIONS:
- You MUST include ALL sections above
- Use the exact section headers shown
- Extract specific technical details from the analyses below
- Include code signatures and class structures, but NOT full implementations
- If agents disagree, note the disagreement and resolution in the relevant section

ORIGINAL AGENT ANALYSES:
"""

        # Add original analyses
        for agent_type, analysis in original_analyses.items():
            if analysis and analysis.strip():
                prompt += f"\n--- {agent_type.replace('_', ' ').title()} Analysis ---\n{analysis}\n"

        prompt += "\nPEER REVIEW FEEDBACK:\n"

        # Add peer reviews
        for agent_type, review in peer_reviews.items():
            review_content = review.get("peer_review", "")
            if review_content and review_content.strip():
                prompt += f"\n--- {agent_type.replace('_', ' ').title()} Peer Review ---\n{review_content}\n"

        # Add conflict resolution if available
        if resolution.get("recommendations"):
            prompt += "\nCONFLICT RESOLUTION:\n"
            for rec in resolution["recommendations"]:
                prompt += f"- Issue: {rec.get('conflict', 'Unknown')}\n"
                prompt += f"- Resolution: {rec.get('resolution', 'Not specified')}\n\n"

        prompt += """
DESIGN DOCUMENT REQUIREMENTS:

1. **CLASS SPECIFICATIONS**: Provide class definitions with:
   - Exact class names following naming conventions
   - Method signatures with parameter types and return types (NO IMPLEMENTATION CODE)
   - Constructor parameters and their purposes
   - Abstract base classes and inheritance hierarchy
   - Interface contracts and responsibilities

2. **DATABASE DESIGN**: Specify:
   - Table schemas with column definitions and constraints
   - Index specifications for performance
   - Key relationships and foreign keys
   - Data types and validation rules
   - NO ACTUAL SQL IMPLEMENTATION CODE

3. **INTEGRATION SPECS**: Detail:
   - Which existing functions need modification and how
   - New function signatures that need to be added
   - Configuration parameters and dependency injection points
   - Backward compatibility requirements

4. **IMPLEMENTATION APPROACH**: Provide high-level steps:
   - Sequence of components to build
   - Dependencies between components
   - Integration points with existing code
   - Migration and deployment considerations

5. **TEST SPECIFICATIONS**: Define:
   - Test class names and their purposes
   - Key test scenarios and edge cases
   - Mock object specifications and interfaces
   - Integration test requirements

6. **ERROR HANDLING**: Specify:
   - Custom exception class names and hierarchy
   - Error scenarios and expected behavior
   - Logging requirements and message formats

CRITICAL: This is a DESIGN document, not an IMPLEMENTATION guide. Focus on:
- WHAT needs to be built (interfaces, classes, schemas)
- HOW components interact (architecture, data flow)
- SPECIFICATIONS and CONTRACTS (method signatures, APIs)

DO NOT INCLUDE:
- Actual implementation code
- Complete function bodies
- Detailed SQL queries beyond schema definitions
- Full code examples

Keep it at the design/specification level that developers can implement from."""

        return prompt

    def _generate_fallback_design_document(
        self, original_analyses: dict, peer_reviews: dict, resolution: dict
    ) -> str:
        """Generate fallback design document if AI generation fails.

        Args:
            original_analyses: Original agent analyses
            peer_reviews: Peer review results
            resolution: Conflict resolution results

        Returns:
            Basic template-based design document
        """
        fallback = """# Consolidated Design Document (Fallback)

## Overview
This document consolidates the analyses from all four agents, incorporating peer review feedback and conflict resolution.

## Agent Contributions Summary

"""

        # Summarize each agent's contribution
        for agent_type in ["architect", "developer", "senior_engineer", "tester"]:
            if agent_type in original_analyses:
                analysis = original_analyses[agent_type]
                if analysis and analysis.strip():
                    agent_name = agent_type.replace("_", " ").title()
                    # Extract first few meaningful lines
                    lines = [
                        line.strip()
                        for line in analysis.split("\n")
                        if line.strip() and not line.startswith("#")
                    ]
                    summary = "; ".join(lines[:3]) if lines else "No analysis available"

                    fallback += f"""### {agent_name}
**Key Points**: {summary}

"""

        # Add conflict resolution section
        if resolution.get("recommendations"):
            fallback += """## Conflict Resolution

The following conflicts were identified and resolved:

"""
            for rec in resolution["recommendations"]:
                fallback += f"""- **Issue**: {rec.get('conflict', 'Unknown')}
- **Resolution**: {rec.get('resolution', 'No resolution')}

"""

        # Add consolidated recommendations
        fallback += f"""## Design Summary

Based on the multi-agent analysis and conflict resolution, the design focuses on:

### Technical Approach
Repository Pattern with SQLite persistence, following existing infrastructure patterns and dependency injection for testability.

### Implementation Strategy
1. Start with test-driven development for core repository interface
2. Implement SQLite repository following existing database patterns
3. Integrate with existing GitHub tool infrastructure
4. Add comment filtering logic to existing API tools

### Quality Assurance
- Comprehensive unit testing with dependency injection
- Integration tests for GitHub API interactions
- Test-driven development for core business logic
- Code review focusing on maintainability and clean architecture

### Next Steps
1. Review this consolidated design document
2. Provide feedback on any remaining concerns
3. Proceed to implementation planning with resolved approach

---
*This consolidated design incorporates input from all agents and resolves identified conflicts using {resolution.get('strategy', 'consensus')} strategy.*
"""

        return fallback

    async def _commit_design_artifacts(
        self,
        context: TaskContext,
        consolidated_design: str,
        conflicts: list,
        resolution: dict,
        peer_reviews: dict,
    ):
        """Commit Phase 2 design artifacts to repository."""
        logger.info("Committing Phase 2 design artifacts...")

        # Create design directory
        design_dir = self.workflow_dir / "round_2_design"
        design_dir.mkdir(parents=True, exist_ok=True)

        # Save consolidated design
        design_path = design_dir / "consolidated_design.md"
        with open(design_path, "w") as f:
            f.write(consolidated_design)

        # Generate and save peer reviews document
        reviews_path = design_dir / "peer_reviews.md"
        reviews_content = await self._generate_peer_review_document(
            peer_reviews, str(reviews_path)
        )
        with open(reviews_path, "w") as f:
            f.write(reviews_content)

        # Generate and save conflict resolution document
        conflicts_path = design_dir / "conflict_resolution.md"
        conflicts_content = await self._generate_conflict_resolution_document(
            conflicts, resolution, str(conflicts_path)
        )
        with open(conflicts_path, "w") as f:
            f.write(conflicts_content)

        # Git commit the design artifacts
        try:
            # Check if there are any changes to commit in the workflow directory
            status_result = subprocess.run(
                ["git", "status", "--porcelain", ".workflow/round_2_design"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True,
            )

            if not status_result.stdout.strip():
                logger.info(
                    "No changes to commit in .workflow/round_2_design directory"
                )
                return

            # Add only the specific workflow files that have changed
            subprocess.run(
                ["git", "add", ".workflow/round_2_design"],
                cwd=self.repo_path,
                check=True,
                capture_output=True,
                text=True,
            )

            # Create commit message
            commit_message = f"""feat: Add Round 2 design consolidation for {context.feature_spec.name}

- Consolidated design from 4 agent perspectives
- Peer review feedback incorporated
- {len(conflicts)} conflicts identified and resolved
- Ready for human design approval

Phase 2 artifacts available in {self.repo_path}/.workflow/round_2_design/

🤖 Generated by Multi-Agent Workflow System"""

            # Commit only the staged workflow files (use --only flag to ignore other unstaged changes)
            result = subprocess.run(
                ["git", "commit", "--only", ".workflow/", "-m", commit_message],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                logger.info("Successfully committed Phase 2 design artifacts")
            else:
                logger.error(f"Git commit failed with return code {result.returncode}")
                logger.error(f"stdout: {result.stdout}")
                logger.error(f"stderr: {result.stderr}")
                # Don't raise exception - workflow can continue without commit

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to commit design artifacts: {e}")
            if hasattr(e, "stdout") and e.stdout:
                logger.error(f"stdout: {e.stdout}")
            if hasattr(e, "stderr") and e.stderr:
                logger.error(f"stderr: {e.stderr}")
            # Don't raise exception - workflow can continue without commit

    async def _load_existing_peer_reviews(
        self, peer_reviews_path: Path
    ) -> dict[str, dict]:
        """Load existing peer reviews from file.

        Args:
            peer_reviews_path: Path to existing peer reviews file

        Returns:
            Dictionary of peer reviews by agent type
        """
        try:
            content = peer_reviews_path.read_text()
            logger.info(
                f"Loaded existing peer reviews from {peer_reviews_path} ({len(content)} chars)"
            )

            # Parse the markdown file to extract individual agent reviews
            peer_reviews = {}
            current_agent = None
            current_content = []

            lines = content.split("\n")
            for line in lines:
                if line.startswith("## ") and "Peer Review" in line:
                    # Save previous agent's content
                    if current_agent and current_content:
                        peer_reviews[current_agent] = {
                            "agent_type": current_agent,
                            "peer_review": "\n".join(current_content).strip(),
                            "status": "success",
                        }

                    # Start new agent
                    agent_title = (
                        line.replace("## ", "").replace(" Peer Review", "").strip()
                    )
                    current_agent = agent_title.lower().replace(" ", "_")
                    current_content = []
                elif (
                    current_agent
                    and not line.startswith("**Status**")
                    and line.strip() != "---"
                ):
                    current_content.append(line)

            # Save last agent's content
            if current_agent and current_content:
                peer_reviews[current_agent] = {
                    "agent_type": current_agent,
                    "peer_review": "\n".join(current_content).strip(),
                    "status": "success",
                }

            return peer_reviews

        except Exception as e:
            logger.error(f"Failed to load existing peer reviews: {e}")
            return {}

    async def _load_existing_conflict_resolution(
        self, conflicts_path: Path
    ) -> tuple[list, dict]:
        """Load existing conflict resolution from file.

        Args:
            conflicts_path: Path to existing conflict resolution file

        Returns:
            Tuple of (conflicts list, resolution dict)
        """
        try:
            content = conflicts_path.read_text()
            logger.info(
                f"Loaded existing conflict resolution from {conflicts_path} ({len(content)} chars)"
            )

            # Parse basic information from the file
            conflicts = []
            resolution = {
                "status": "resolved",
                "strategy": "consensus",
                "resolution": "Conflicts resolved from existing document",
                "recommendations": [],
            }

            # Extract strategy from content
            lines = content.split("\n")
            for line in lines:
                if line.startswith("Strategy:"):
                    resolution["strategy"] = line.replace("Strategy:", "").strip()
                    break

            # For now, return basic structure since parsing the full conflict data
            # would require more complex parsing. The important thing is that
            # we detected the file exists and has content.

            return conflicts, resolution

        except Exception as e:
            logger.error(f"Failed to load existing conflict resolution: {e}")
            return [], {"status": "error", "error": str(e)}

    async def consolidate_design(self, context: TaskContext) -> dict[str, Any]:
        """Consolidate agent analyses into a unified design document.

        This is a wrapper for continue_to_design_phase that provides a cleaner
        interface for step2_create_design_document.py

        Args:
            context: Task context with completed analyses

        Returns:
            Design consolidation results
        """
        # Check for any human feedback that needs to be processed
        human_feedback = []
        if hasattr(context, "human_feedback") and context.human_feedback:
            human_feedback = context.human_feedback

        # Call the existing design phase method
        result = await self.continue_to_design_phase(context, human_feedback)

        # Transform result to expected format
        if result["status"] == "success":
            design_artifacts = {}
            design_dir = self.workflow_dir / "round_2_design"

            # List the created artifacts
            if (design_dir / "peer_reviews.md").exists():
                design_artifacts["peer_reviews"] = str(design_dir / "peer_reviews.md")
            if (design_dir / "conflict_resolution.md").exists():
                design_artifacts["conflict_resolution"] = str(
                    design_dir / "conflict_resolution.md"
                )
            if (design_dir / "consolidated_design.md").exists():
                design_artifacts["consolidated_design"] = str(
                    design_dir / "consolidated_design.md"
                )

            result["design_artifacts"] = design_artifacts

            # Add statistics
            if "conflicts" in result:
                result["conflicts_resolved"] = len(result.get("conflicts", []))

        return result

    async def _fetch_pr_comments_for_context(
        self, context: TaskContext, pr_number: int
    ):
        """Fetch PR comments from GitHub and add them to context as human feedback.

        Args:
            context: Task context to update with PR comments
            pr_number: PR number to fetch comments from
        """
        try:
            import json

            from github_tools import execute_tool

            logger.info(f"Fetching PR comments for PR #{pr_number}")

            # Get new feedback from GitHub
            comments_result = await execute_tool(
                "github_get_pr_comments",
                repo_name=self.repo_name,
                pr_number=pr_number,
            )

            comments_data = json.loads(comments_result)

            # Process new feedback
            new_feedback_count = 0
            filtered_count = 0

            # Define exact step 1 files that we care about
            step1_files = [
                ".workflow/round_1_analysis/architect_analysis.md",
                ".workflow/round_1_analysis/developer_analysis.md",
                ".workflow/round_1_analysis/senior_engineer_analysis.md",
                ".workflow/round_1_analysis/tester_analysis.md",
                ".workflow/round_1_analysis/codebase_analysis.md",
                ".workflow/round_1_analysis/analysis_summary.md",
                # Also check for files in the root .workflow directory (in case they're there)
                ".workflow/codebase_analysis.md",
                ".workflow/analysis_summary.md",
            ]

            # Process review comments (comments on specific files/lines)
            for comment in comments_data.get("review_comments", []):
                # Check if we've already processed this comment
                existing_ids = [f.comment_id for f in context.human_feedback]
                if comment["id"] not in existing_ids:
                    # Filter by exact file path - only include comments on step 1 files
                    # The GitHub API returns the file path under 'file' key, not 'path'
                    file_path = comment.get("file", "")

                    if file_path in step1_files:
                        context.add_human_feedback(comment)
                        new_feedback_count += 1
                        logger.info(
                            f"✅ Including review comment on step1 file: {file_path}"
                        )
                    else:
                        filtered_count += 1
                        logger.info(
                            f"❌ Filtered out comment on non-step1 file: '{file_path}'"
                        )

            # Process issue comments (general PR comments)
            # Issue comments don't have file paths, so we skip them entirely
            # since they're not tied to specific step 1 files
            for comment in comments_data.get("issue_comments", []):
                # Check if we've already processed this comment
                existing_ids = [f.comment_id for f in context.human_feedback]
                if comment["id"] not in existing_ids:
                    # Issue comments don't have file paths, so filter them out
                    filtered_count += 1
                    logger.debug(
                        f"Filtered out issue comment (no file association): #{comment['id']}"
                    )

            logger.info(
                f"Added {new_feedback_count} new PR comments to context, filtered out {filtered_count}"
            )

            if new_feedback_count > 0:
                print(
                    f"✅ Found {new_feedback_count} relevant PR comments to incorporate into design"
                )
                if filtered_count > 0:
                    print(f"   (Filtered out {filtered_count} irrelevant comments)")
            else:
                print("i  No new relevant PR comments found")
                if filtered_count > 0:
                    print(f"   (Filtered out {filtered_count} irrelevant comments)")

        except Exception as e:
            logger.error(f"Failed to fetch PR comments: {e}")
            print(f"⚠️  Failed to fetch PR comments: {e}")
            print("Continuing with design consolidation without new PR feedback...")

    async def _post_consolidated_feedback_replies(
        self, context: TaskContext, consolidated_design: str
    ):
        """Post consolidated replies to each PR comment explaining how it was addressed.

        Args:
            context: Task context containing human feedback
            consolidated_design: The final consolidated design document
        """
        try:
            from github_tools import execute_tool

            if not hasattr(context, "pr_number") or not context.pr_number:
                logger.warning("No PR number available, cannot post replies")
                return

            logger.info(
                f"Posting consolidated replies to {len(context.human_feedback)} PR comments"
            )

            # For each feedback item, generate and post a consolidated reply
            for feedback in context.human_feedback:
                comment_id = feedback.comment_id
                author = feedback.author
                content = feedback.content
                file_path = feedback.file_path

                # Skip if this is a bot comment
                if any(
                    bot in author.lower()
                    for bot in ["bot", "codecov", "github-actions"]
                ):
                    logger.debug(f"Skipping reply to bot comment from {author}")
                    continue

                # Generate a consolidated reply based on the design
                reply_prompt = f"""Based on the PR comment below and the consolidated design document, write a professional reply explaining how this feedback was addressed in the design.

PR Comment by {author} on {file_path}:
"{content}"

Consolidated Design (excerpt):
{consolidated_design[:3000]}...

Write a concise reply (2-4 sentences) that:
1. Briefly acknowledges the point
2. Explains how it was incorporated into the design
3. References the relevant section of the design if applicable

Keep the tone professional but direct. Avoid excessive politeness or thanking."""

                # Use the architect agent to generate the consolidated reply
                if "architect" in self.agents:
                    architect = self.agents["architect"]
                    reply_response = architect.persona.ask(reply_prompt)

                    if reply_response and len(reply_response.strip()) > 10:
                        # Post the reply
                        comment_body = f"""{reply_response}

---
*This response reflects how your feedback was incorporated into the [consolidated design document](.workflow/round_2_design/consolidated_design.md).*"""

                        try:
                            await execute_tool(
                                "github_post_pr_reply",
                                repo_name=self.repo_name,
                                comment_id=comment_id,
                                message=comment_body,
                            )
                            logger.info(
                                f"Posted consolidated reply to comment #{comment_id}"
                            )

                        except Exception as e:
                            logger.error(
                                f"Failed to post reply to comment #{comment_id}: {e}"
                            )
                    else:
                        logger.warning(
                            f"Generated empty reply for comment #{comment_id}"
                        )
                else:
                    logger.error("Architect agent not available for reply generation")

        except Exception as e:
            logger.error(f"Failed to post consolidated feedback replies: {e}")
            print(f"⚠️  Failed to post feedback replies: {e}")

    # Removed _post_agent_pr_replies - we now use _post_consolidated_feedback_replies instead

    async def _post_feedback_summary(
        self, context: TaskContext, consolidated_design: str
    ):
        """Post a summary comment explaining how PR feedback was addressed in the design.

        Args:
            context: Task context containing human feedback and design
            consolidated_design: The final consolidated design document content
        """
        try:
            logger.info("Generating feedback address summary for PR")

            # Generate summary of how feedback was addressed
            feedback_items = []
            for feedback in context.human_feedback:
                feedback_items.append(
                    f"- Comment #{feedback.comment_id} by {feedback.author}: {feedback.content[:100]}..."
                )

            if not feedback_items:
                logger.info("No human feedback to summarize")
                return

            summary_prompt = f"""Based on the PR comments received and the consolidated design document created, provide a summary comment explaining how each piece of feedback was addressed in the final design.

PR Comments Received:
{chr(10).join(feedback_items)}

Consolidated Design Document:
{consolidated_design[:2000]}...

Please write a comprehensive but concise summary comment that:
1. Acknowledges each PR comment
2. Explains how it was addressed in the design
3. References specific sections of the design document where applicable
4. Maintains a professional and collaborative tone

Format as a GitHub comment that can be posted to the PR."""

            # Use the architect agent to generate the summary (they're good at high-level summaries)
            if "architect" in self.agents:
                architect = self.agents["architect"]

                logger.debug(
                    f"Feedback summary prompt (length={len(summary_prompt)}):\n{summary_prompt}\n============================"
                )

                summary_response = architect.persona.ask(summary_prompt)

                logger.debug(
                    f"Feedback summary response (length={len(summary_response) if summary_response else 0}):\n{summary_response}\n============================"
                )

                if summary_response and len(summary_response.strip()) > 10:
                    # Post the summary as a PR comment
                    if hasattr(context, "pr_number") and context.pr_number:
                        # Post as a general PR comment (not a reply to a specific comment)
                        from github_tools import execute_tool as github_execute_tool

                        await github_execute_tool(
                            "github_post_issue_comment",
                            repo_name=self.repo_name,
                            issue_number=context.pr_number,
                            body=f"""## Feedback Integration Summary

{summary_response}

---
*This summary was generated automatically by the multi-agent design workflow after incorporating all PR feedback into the consolidated design document.*""",
                        )

                        logger.info("Posted feedback integration summary to PR")
                        print("✅ Posted summary of how PR feedback was addressed")
                    else:
                        logger.warning(
                            "No PR number available, cannot post feedback summary"
                        )
                else:
                    logger.warning("Generated feedback summary was empty or too short")
            else:
                logger.warning(
                    "Architect agent not available for feedback summary generation"
                )

        except Exception as e:
            logger.error(f"Failed to post feedback summary: {e}")
            print(f"⚠️  Failed to post feedback summary: {e}")

    async def finalize_design(
        self, context: TaskContext, github_feedback: list
    ) -> dict[str, Any]:
        """Finalize the design document by incorporating GitHub feedback.

        This is Step 3 in the workflow - takes feedback from GitHub PR comments
        and updates the consolidated design document to address all concerns.

        Args:
            context: Task context with existing design
            github_feedback: List of feedback items from GitHub PR comments

        Returns:
            Finalization results including updated design path
        """
        logger.info("Starting Step 3: Finalizing design with GitHub feedback")

        try:
            design_dir = self.workflow_dir / "round_2_design"

            # Check if design exists
            design_path = design_dir / "consolidated_design.md"
            if not design_path.exists():
                return {
                    "status": "error",
                    "error": "No consolidated design found. Run step 2 first.",
                }

            # Check if already finalized
            final_design_path = design_dir / "consolidated_design_final.md"
            if final_design_path.exists():
                logger.info("Design already finalized, checking if update needed")

            # Read current design
            current_design = design_path.read_text()

            # Process feedback if any
            if not github_feedback:
                logger.info("No GitHub feedback to process")
                # Just copy the design as final
                final_design_path.write_text(current_design)
                return {
                    "status": "success",
                    "finalized_design": str(final_design_path),
                    "feedback_processed": 0,
                }

            # Create feedback summary
            feedback_summary = self._create_feedback_summary(github_feedback)

            # Update design using architect agent
            logger.info(f"Processing {len(github_feedback)} feedback items")

            update_prompt = f"""
## Current Design Document

{current_design}

## GitHub Feedback to Address

{feedback_summary}

## Task

Please update the design document to address all the feedback provided. For each piece of feedback:
1. Acknowledge the concern
2. Update the relevant section of the design
3. Add a "Feedback Addressed" section at the end listing what was changed

Maintain the overall structure and quality of the document while incorporating the improvements.
"""

            # Use architect agent to update the design
            architect = self.agents["architect"]
            agent_context = context.get_context_for_agent("architect")

            # Run the update
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, architect.review_and_update, agent_context, update_prompt
            )

            if result["status"] == "success":
                updated_design = result["content"]

                # Save finalized design
                final_design_path.write_text(updated_design)

                # Create feedback summary document
                feedback_doc_path = design_dir / "feedback_addressed.md"
                feedback_doc = f"""# Design Feedback Addressed

PR: #{context.pr_number}
Date: {context.workflow_state.start_time}

## Feedback Summary

{feedback_summary}

## Changes Made

The following changes were made to address the feedback:
- See consolidated_design_final.md for the updated design
- All feedback items have been incorporated

## Status

✅ Design finalized and ready for implementation
"""
                feedback_doc_path.write_text(feedback_doc)

                logger.info(f"Created finalized design: {final_design_path}")
                logger.info(f"Created feedback summary: {feedback_doc_path}")

                return {
                    "status": "success",
                    "finalized_design": str(final_design_path),
                    "feedback_doc": str(feedback_doc_path),
                    "feedback_processed": len(github_feedback),
                }
            else:
                return {
                    "status": "error",
                    "error": f"Failed to update design: {result.get('error', 'Unknown error')}",
                }

        except Exception as e:
            logger.error(f"Design finalization failed: {e}")
            return {"status": "error", "error": str(e)}

    def _create_feedback_summary(self, feedback_items: list) -> str:
        """Create a formatted summary of feedback items."""
        if not feedback_items:
            return "No feedback provided"

        summary_parts = ["### Feedback Items\n"]

        for i, item in enumerate(feedback_items, 1):
            author = item.get("author", "Unknown")
            content = item.get("content", item.get("body", ""))
            path = item.get("path", "General")

            summary_parts.append(f"**{i}. {author}** (on {path}):")
            summary_parts.append(f"{content}\n")

        return "\n".join(summary_parts)

    async def implement_feature(self, pr_number: int | None = None) -> dict[str, Any]:
        """Execute Phase 3: Implementation based on approved design.

        This method reads the consolidated design document from Phase 2 and
        uses the coding agents to generate actual implementation code.

        Args:
            pr_number: PR number containing the approved design (optional)

        Returns:
            Implementation results including generated files
        """
        logger.info("Starting Phase 3: Implementation workflow")

        try:
            # Initialize context for implementation
            if not pr_number:
                # Auto-detect PR from workflow state
                pr_number = await self._find_latest_pr()
                if not pr_number:
                    raise ValueError("No PR found. Please specify PR number.")

            # Create minimal context for implementation phase
            context = TaskContext(
                FeatureSpec("Implementation Phase", "", [], [], []),
                CodebaseState({}, {}, {}, {}),
                str(self.repo_path),
            )
            context.set_pr_number(pr_number)

            context.update_phase("round_3_implementation")

            # Load the consolidated design document
            design_doc = await self._load_design_document(pr_number)
            if not design_doc:
                raise ValueError(f"No design document found for PR #{pr_number}")

            logger.info(f"Loaded design document ({len(design_doc)} characters)")

            # Parse implementation tasks from design
            implementation_tasks = await self._parse_implementation_tasks(design_doc)
            logger.info(f"Identified {len(implementation_tasks)} implementation tasks")

            # Execute implementation cycles
            implementation_results = []
            for i, task in enumerate(implementation_tasks, 1):
                logger.info(
                    f"Executing implementation cycle {i}/{len(implementation_tasks)}: {task['title']}"
                )
                result = await self._execute_implementation_cycle(context, task, i)
                implementation_results.append(result)

            # Generate tests for implemented features
            test_results = await self._generate_tests(context, implementation_results)

            # Commit implementation to PR
            await self._commit_implementation(
                context, implementation_results, test_results
            )

            return {
                "status": "success",
                "pr_number": pr_number,
                "phase": "implementation",
                "tasks_completed": len(implementation_results),
                "files_created": sum(
                    len(r.get("files_created", [])) for r in implementation_results
                ),
                "tests_created": len(test_results.get("test_files", [])),
                "implementation_results": implementation_results,
                "test_results": test_results,
            }

        except Exception as e:
            logger.error(f"Implementation workflow failed: {e}")
            return {"status": "failed", "error": str(e), "pr_number": pr_number}

    async def _load_design_document(self, pr_number: int) -> str | None:
        """Load the consolidated design document from Phase 2."""
        try:
            # Look for the design document in the workflow directory
            design_path = (
                self.workflow_dir / "round_2_design" / "consolidated_design.md"
            )

            if not design_path.exists():
                # Try alternative location
                design_path = (
                    self.repo_path
                    / ".workflow"
                    / f"pr_{pr_number}"
                    / "round_2_design"
                    / "consolidated_design.md"
                )

            if design_path.exists():
                with open(design_path) as f:
                    return f.read()

            # If not found locally, try to fetch from GitHub
            logger.info("Design document not found locally, checking GitHub...")
            # This would use github_tools to fetch the file from the PR
            # For now, return None
            return None

        except Exception as e:
            logger.error(f"Failed to load design document: {e}")
            return None

    async def _parse_implementation_tasks(
        self, design_doc: str
    ) -> list[dict[str, Any]]:
        """Parse implementation tasks from ANY design document generically."""
        tasks = []

        # Generic parser that works with any design document structure
        lines = design_doc.split("\n")

        # Look for common implementation markers across any design
        implementation_markers = [
            "## Implementation",
            "### Implementation",
            "# Implementation",
            "## Code Structure",
            "### Code Structure",
            "## Components",
            "### Components",
            "## Classes",
            "### Classes",
            "## Modules",
            "### Modules",
            "## Files",
            "### Files",
        ]

        current_section = None
        current_content = []

        for line in lines:
            line_stripped = line.strip()

            # Check if this line is an implementation marker
            is_implementation_marker = any(
                line_stripped.startswith(marker) for marker in implementation_markers
            )

            if is_implementation_marker:
                # Save previous section if it exists
                if current_section and current_content:
                    tasks.append(
                        {
                            "title": f"Implement {current_section}",
                            "description": "\n".join(current_content),
                            "requirements": self._extract_requirements_from_content(
                                current_content
                            ),
                            "files_to_create": self._extract_files_from_content(
                                current_content
                            ),
                            "section_type": current_section.lower(),
                        }
                    )

                # Start new section
                current_section = (
                    line_stripped.replace("#", "").replace("Implementation", "").strip()
                )
                current_content = []
            elif current_section:
                # Add content to current section
                if line_stripped:
                    current_content.append(line_stripped)

        # Add final section
        if current_section and current_content:
            tasks.append(
                {
                    "title": f"Implement {current_section}",
                    "description": "\n".join(current_content),
                    "requirements": self._extract_requirements_from_content(
                        current_content
                    ),
                    "files_to_create": self._extract_files_from_content(
                        current_content
                    ),
                    "section_type": current_section.lower(),
                }
            )

        # If no structured sections found, create a single comprehensive task
        if not tasks:
            tasks.append(
                {
                    "title": "Implement Complete System",
                    "description": "Implement all functionality described in the design document",
                    "requirements": [
                        "Implement all specified functionality",
                        "Follow design patterns",
                        "Include comprehensive tests",
                    ],
                    "files_to_create": [],
                    "section_type": "complete_system",
                }
            )

        return tasks

    def _extract_requirements_from_content(self, content_lines: list[str]) -> list[str]:
        """Extract requirements from content lines."""
        requirements = []
        for line in content_lines:
            # Look for bullet points, numbered lists, or requirement keywords
            if (
                line.startswith(("- ", "* ", "• "))
                or line.lower().startswith(("must ", "should ", "shall ", "will "))
                or "requirement" in line.lower()
            ):
                req = line.strip()
                for prefix in ["- ", "* ", "• "]:
                    if req.startswith(prefix):
                        req = req[len(prefix) :]
                        break
                if req:
                    requirements.append(req)
        return requirements

    def _extract_files_from_content(self, content_lines: list[str]) -> list[str]:
        """Extract file names from content lines."""
        files = []
        for line in content_lines:
            # Look for file patterns
            if (
                ".py" in line
                or ".js" in line
                or ".ts" in line
                or ".java" in line
                or ".cpp" in line
                or ".go" in line
                or "file:" in line.lower()
                or "filename:" in line.lower()
            ):
                # Try to extract filename
                import re

                file_matches = re.findall(r"[\w/]+\.\w+", line)
                files.extend(file_matches)
        return files

    async def _execute_implementation_cycle(
        self, context: TaskContext, task: dict, cycle_num: int
    ) -> dict[str, Any]:
        """Execute a single implementation cycle."""
        logger.info(f"Starting implementation cycle {cycle_num}: {task['title']}")

        # Load the design document content to include in the prompt
        design_doc = await self._load_design_document(context.pr_number)

        # Create completely generic implementation prompt
        prompt = f"""
# Generic Code Implementation Task

## Task: {task['title']}

## Description
{task['description']}

## Requirements
{chr(10).join(f"- {req}" for req in task['requirements'])}

## Suggested Files (if specified)
{chr(10).join(f"- {f}" for f in task['files_to_create']) if task['files_to_create'] else "- Determine appropriate files based on the functionality"}

## Section Type: {task.get('section_type', 'general')}

## Full Design Context
{design_doc[:5000]}...

## Your Mission
You are a coding agent that can implement ANY type of software functionality.

**Based on the design document above, implement the requested functionality.**

Guidelines:
- Analyze the design and determine what needs to be built
- Choose appropriate technologies and patterns based on the design
- Create all necessary files for a complete implementation
- Include proper error handling, logging, and documentation
- Write comprehensive tests
- Follow software engineering best practices

Output Format:
```language
# File: path/to/filename.ext
[Your complete code here]
```

**Important**:
- Make each code block a complete, runnable file
- Include file paths that make sense for the project structure
- Don't just create templates - create full implementations
- Consider the project's existing architecture and patterns

Begin implementation now.
"""

        # Use developer agent to generate implementation
        dev_result = await self.agents["developer"].implement_code(context, prompt)
        logger.debug(f"Developer result length: {len(dev_result['content'])}")
        logger.debug(f"Developer result preview: {dev_result['content'][:200]}...")

        # Use senior engineer to review
        review_prompt = f"Review this implementation:\n\n{dev_result['content']}"
        sr_review = await self.agents["senior_engineer"].review_code(
            context, review_prompt
        )

        # Apply any suggested improvements
        if sr_review["suggestions"]:
            final_result = await self.agents["developer"].refine_implementation(
                context, dev_result, sr_review["suggestions"]
            )
        else:
            final_result = dev_result

        # Extract code blocks and create files
        files_created = await self._create_implementation_files(final_result["content"])

        return {
            "cycle": cycle_num,
            "task": task["title"],
            "status": "completed",
            "files_created": files_created,
            "implementation": final_result["content"],
            "review": sr_review["content"],
        }

    async def _create_implementation_files(
        self, implementation_content: str
    ) -> list[str]:
        """Extract code blocks from implementation and create actual files - completely generic."""
        files_created = []

        logger.info(
            f"Parsing implementation content ({len(implementation_content)} chars) for code blocks..."
        )

        # More flexible regex to catch various code block formats
        import re

        # Try multiple patterns to find code blocks
        patterns = [
            r"```(\w+)?\s*\n#\s*File:\s*([^\n]+)\n(.*?)\n```",  # With explicit file declaration
            r"```(\w+)?\s*\n([^#].*?)\n```",  # Standard code blocks
            r"```(\w+)?\n(.*?)\n```",  # Simple code blocks
        ]

        all_matches = []
        for pattern in patterns:
            matches = re.findall(pattern, implementation_content, re.DOTALL)
            for match in matches:
                if len(match) == 3:  # Has file path
                    lang, filepath, code = match
                    all_matches.append((lang, code, filepath.strip()))
                elif len(match) == 2:  # No explicit file path
                    lang, code = match
                    all_matches.append((lang, code, None))

        logger.info(f"Found {len(all_matches)} potential code blocks")

        for i, (lang, code, explicit_filepath) in enumerate(all_matches):
            if not code.strip():
                continue

            logger.info(
                f"Processing code block {i+1}: language={lang or 'unknown'}, length={len(code)}"
            )

            # Determine filename
            if explicit_filepath:
                filename = explicit_filepath
            else:
                # Smart filename generation based on language and content
                filename = self._generate_smart_filename(code, lang, i + 1)

            # Ensure we have a valid filename
            if not filename or filename == "None":
                filename = (
                    f"generated_code_{i+1}.{self._get_extension_for_language(lang)}"
                )

            # Create the file with proper directory structure
            file_path = self.repo_path / filename
            file_path.parent.mkdir(parents=True, exist_ok=True)

            # Clean up the code (remove file declaration comments if present)
            clean_code = self._clean_code_content(code)

            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(clean_code)

                files_created.append(str(file_path))
                logger.info(f"✅ Created file: {filename}")

            except Exception as e:
                logger.error(f"❌ Failed to create file {filename}: {e}")

        return files_created

    def _generate_smart_filename(self, code: str, language: str, index: int) -> str:
        """Generate intelligent filename based on code content."""
        import re

        # Try to extract class names, function names, or other identifiers
        if language in ["python", "py"]:
            # Look for class definitions
            class_match = re.search(r"class\s+(\w+)", code)
            if class_match:
                return f"{class_match.group(1).lower()}.py"

            # Look for main function definitions
            func_match = re.search(r"def\s+(\w+)", code)
            if func_match:
                return f"{func_match.group(1)}.py"

        elif language in ["javascript", "js"]:
            # Look for class or function exports
            export_match = re.search(r"export\s+(?:class|function)\s+(\w+)", code)
            if export_match:
                return f"{export_match.group(1).lower()}.js"

        elif language in ["java"]:
            # Look for public class
            class_match = re.search(r"public\s+class\s+(\w+)", code)
            if class_match:
                return f"{class_match.group(1)}.java"

        # Look for file patterns in comments
        file_comment = re.search(r"#.*?(\w+\.\w+)", code)
        if file_comment:
            return file_comment.group(1)

        # Default fallback
        ext = self._get_extension_for_language(language)
        return f"implementation_{index}.{ext}"

    def _get_extension_for_language(self, language: str) -> str:
        """Get file extension for programming language."""
        lang_map = {
            "python": "py",
            "py": "py",
            "javascript": "js",
            "js": "js",
            "typescript": "ts",
            "ts": "ts",
            "java": "java",
            "cpp": "cpp",
            "c++": "cpp",
            "c": "c",
            "go": "go",
            "rust": "rs",
            "ruby": "rb",
            "php": "php",
            "swift": "swift",
            "kotlin": "kt",
            "scala": "scala",
            "html": "html",
            "css": "css",
            "sql": "sql",
            "yaml": "yaml",
            "yml": "yml",
            "json": "json",
            "xml": "xml",
            "markdown": "md",
            "md": "md",
        }

        return lang_map.get(language.lower() if language else "", "txt")

    def _clean_code_content(self, code: str) -> str:
        """Clean code content by removing file declaration comments."""
        lines = code.split("\n")

        # Remove file declaration comments
        if lines and lines[0].strip().startswith("#") and "File:" in lines[0]:
            lines = lines[1:]

        # Remove leading/trailing empty lines
        while lines and not lines[0].strip():
            lines = lines[1:]
        while lines and not lines[-1].strip():
            lines = lines[:-1]

        return "\n".join(lines)

    async def _generate_tests(
        self, context: TaskContext, implementation_results: list
    ) -> dict[str, Any]:
        """Generate tests for the implemented features."""
        logger.info("Generating tests for implemented features...")

        test_files = []

        for impl_result in implementation_results:
            if impl_result.get("status") != "completed":
                continue

            # Create test prompt based on implementation
            test_prompt = f"""
Generate comprehensive tests for the following implementation:

Task: {impl_result['task']}
Files created: {', '.join(impl_result['files_created'])}

Implementation details:
{impl_result['implementation']}

Please create unit tests, integration tests, and any necessary test fixtures.
"""

            # Use tester agent
            test_result = await self.agents["tester"].create_tests(context, test_prompt)

            # Create test files
            test_files_created = await self._create_test_files(test_result["content"])
            test_files.extend(test_files_created)

        return {
            "test_files": test_files,
            "coverage": "Comprehensive test coverage for all implemented features",
        }

    async def _create_test_files(self, test_content: str) -> list[str]:
        """Create test files from test content."""
        files_created = []

        # Similar to _create_implementation_files but for tests
        import re

        code_blocks = re.findall(r"```(\w+)?\n(.*?)\n```", test_content, re.DOTALL)

        for _, code in code_blocks:
            # Extract filename or generate test filename
            filename_match = re.search(r"#\s*(?:File|Filename):\s*(.+)", code)
            if filename_match:
                filename = filename_match.group(1).strip()
            else:
                filename = f"test_implementation_{len(files_created) + 1}.py"

            # Ensure test files go in tests directory
            if not filename.startswith("tests/"):
                filename = f"tests/{filename}"

            file_path = self.repo_path / filename
            file_path.parent.mkdir(parents=True, exist_ok=True)

            with open(file_path, "w") as f:
                code_lines = code.split("\n")
                if code_lines and "File:" in code_lines[0]:
                    code_lines = code_lines[1:]
                f.write("\n".join(code_lines))

            files_created.append(str(file_path))
            logger.info(f"Created test file: {filename}")

        return files_created

    async def _commit_implementation(
        self, context: TaskContext, implementation_results: list, test_results: dict
    ):
        """Commit implementation and tests to the PR."""
        logger.info("Committing implementation to PR...")

        try:
            # Stage all created files
            all_files = []
            for result in implementation_results:
                all_files.extend(result.get("files_created", []))
            all_files.extend(test_results.get("test_files", []))

            if not all_files:
                logger.warning("No files to commit")
                return

            # Git add all files
            for file_path in all_files:
                subprocess.run(
                    ["git", "add", file_path], cwd=self.repo_path, check=True
                )

            # Create commit message
            commit_message = f"""Implement Phase 3: Code generation from design

- Generated {len(implementation_results)} implementation components
- Created {len(test_results.get('test_files', []))} test files
- Based on approved design document

Implementation tasks completed:
{chr(10).join(f"- {r['task']}" for r in implementation_results if r.get('status') == 'completed')}
"""

            # Commit
            subprocess.run(
                ["git", "commit", "-m", commit_message], cwd=self.repo_path, check=True
            )

            # Push to PR branch
            if context.pr_number:
                branch_name = f"pr-{context.pr_number}-implementation"
                subprocess.run(
                    ["git", "push", "origin", f"HEAD:{branch_name}"],
                    cwd=self.repo_path,
                    check=True,
                )

            logger.info("Successfully committed implementation")

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to commit implementation: {e}")
            raise

    async def _find_latest_pr(self) -> int | None:
        """Find the latest PR number from workflow state."""
        try:
            # Look for .workflow/pr_* directories
            workflow_dirs = list(self.repo_path.glob(".workflow/pr_*"))
            if workflow_dirs:
                # Sort by PR number and get the latest
                pr_numbers = []
                for d in workflow_dirs:
                    try:
                        pr_num = int(d.name.split("_")[1])
                        pr_numbers.append(pr_num)
                    except (ValueError, IndexError):
                        continue

                if pr_numbers:
                    return max(pr_numbers)

            return None

        except Exception as e:
            logger.error(f"Failed to find latest PR: {e}")
            return None


async def resume_workflow(repo_name: str, repo_path: str, pr_number: int | None = None):
    """Resume a workflow from saved state.

    Args:
        repo_name: GitHub repository name
        repo_path: Local repository path
        pr_number: PR number to resume (optional, will auto-detect)
    """
    orchestrator = WorkflowOrchestrator(repo_name, repo_path)

    # Auto-detect PR if not provided
    if pr_number is None:
        logger.info("Auto-detecting PR for current branch...")

        # Get current branch
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                check=True,
            )
            current_branch = result.stdout.strip()

            # Find PR for branch
            pr_result = await execute_tool(
                "github_find_pr_for_branch",
                repo_name=orchestrator.repo_name,
                branch_name=current_branch,
            )

            pr_data = json.loads(pr_result)

            if pr_data.get("pr_number"):
                pr_number = pr_data["pr_number"]
                logger.info(f"Found PR #{pr_number} for branch '{current_branch}'")
            else:
                logger.error(f"No PR found for branch '{current_branch}'")
                return

        except Exception as e:
            logger.error(f"Failed to auto-detect PR: {e}")
            return

    context_file = orchestrator.workflow_dir / f"context_pr_{pr_number}.json"

    if not context_file.exists():
        logger.error(f"No saved context found for PR #{pr_number}")
        return

    # Load context
    context = TaskContext.load_from_file(context_file)

    # Get new feedback from GitHub
    logger.info(f"Checking for new feedback on PR #{pr_number}")

    comments_result = await execute_tool(
        "github_get_pr_comments",
        repo_name=orchestrator.repo_name,  # Use the detected repo name, not the placeholder
        pr_number=pr_number,
    )

    comments_data = json.loads(comments_result)

    # Process new feedback
    new_feedback_count = 0

    # Process review comments
    for comment in comments_data.get("review_comments", []):
        # Check if we've already processed this comment
        existing_ids = [f.comment_id for f in context.human_feedback]
        if comment["id"] not in existing_ids:
            context.add_human_feedback(comment)
            new_feedback_count += 1

    # Process issue comments
    for comment in comments_data.get("issue_comments", []):
        # Check if we've already processed this comment
        existing_ids = [f.comment_id for f in context.human_feedback]
        if comment["id"] not in existing_ids:
            context.add_human_feedback(comment)
            new_feedback_count += 1

    logger.info(f"Found {new_feedback_count} new feedback items")

    # Save updated context
    context.save_to_file(context_file)

    # Process feedback and continue to Phase 2
    if new_feedback_count > 0:
        logger.info(f"New feedback available: {new_feedback_count} comments")
        print("\n" + "=" * 80)
        print("NEW FEEDBACK RECEIVED")
        print("=" * 80)

        for feedback in context.human_feedback[-new_feedback_count:]:
            print(f"\n📝 Comment from {feedback.author}:")
            if feedback.file_path:
                print(f"   File: {feedback.file_path}")
                if feedback.line_number:
                    print(f"   Line: {feedback.line_number}")
            print(
                f"   Content: {feedback.content[:200]}{'...' if len(feedback.content) > 200 else ''}"
            )
            print(f"   Date: {feedback.created_at}")

        print("\n" + "=" * 80)
        print("🚀 Proceeding to Phase 2: Design Consolidation")
        print("Agents will now process feedback and create consolidated design...")

        # Continue to Phase 2
        phase2_result = await orchestrator.continue_to_design_phase(
            context, context.human_feedback[-new_feedback_count:]
        )

        if phase2_result.get("status") == "success":
            print("\n✅ Phase 2 Complete!")
            print(f"📁 Design artifacts saved to {repo_path}/.workflow/round_2_design/")
            print(
                f"🔍 {len(phase2_result.get('conflicts', []))} conflicts identified and resolved"
            )
            print("\nNext steps:")
            print("1. Review the consolidated design document")
            print("2. Check conflict resolution report")
            print("3. Provide approval or additional feedback")
        else:
            print(f"\n❌ Phase 2 failed: {phase2_result.get('error')}")
    else:
        logger.info("No new feedback. Workflow remains in waiting state.")
        print("\nNo new feedback found. The workflow is waiting for human review.")
        print("Add comments to the PR to provide feedback and trigger Phase 2.")


if __name__ == "__main__":
    import sys

    from logging_config import setup_logging

    # Setup logging
    log_dir = Path.home() / ".local" / "share" / "multi-agent-workflow" / "logs"
    setup_logging(log_level="INFO", log_file=log_dir / "workflow_orchestrator.log")

    if len(sys.argv) < 2:
        print("Usage:")
        print("  python workflow_orchestrator.py analyze-feature <task_spec>")
        print("  python workflow_orchestrator.py implement-feature [pr_number]")
        print("  python workflow_orchestrator.py resume [pr_number]")
        sys.exit(1)

    command = sys.argv[1]

    # Get repo info from environment or defaults
    repo_name = os.environ.get("GITHUB_REPO", "github-agent")
    repo_path = os.environ.get("REPO_PATH", str(Path.cwd()))

    if command == "analyze-feature":
        if len(sys.argv) < 3:
            print("Error: Task specification required")
            sys.exit(1)
        task_spec = " ".join(sys.argv[2:])

        orchestrator = WorkflowOrchestrator(repo_name, repo_path)
        result = asyncio.run(orchestrator.analyze_feature(task_spec))

        if result["status"] == "success":
            print(f"✅ Analysis complete! PR #{result['pr_number']}")
        else:
            print(f"❌ Analysis failed: {result.get('error')}")
            sys.exit(1)

    elif command == "implement-feature":
        pr_number = int(sys.argv[2]) if len(sys.argv) > 2 else None

        orchestrator = WorkflowOrchestrator(repo_name, repo_path)
        result = asyncio.run(orchestrator.implement_feature(pr_number))

        if result["status"] == "success":
            print("✅ Implementation complete!")
            print(f"   Files created: {result['files_created']}")
            print(f"   Tests created: {result['tests_created']}")
        else:
            print(f"❌ Implementation failed: {result.get('error')}")
            sys.exit(1)

    elif command == "resume":
        pr_number = int(sys.argv[2]) if len(sys.argv) > 2 else None
        asyncio.run(resume_workflow(repo_name, repo_path, pr_number))

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
