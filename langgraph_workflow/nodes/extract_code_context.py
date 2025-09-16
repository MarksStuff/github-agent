"""Extract Code Context Node Definition.

This node analyzes the codebase and creates a comprehensive code context document
that will guide subsequent design and implementation phases.
"""

import logging
from pathlib import Path

from ..enums import AgentType, ArtifactName, ModelRouter
from ..node_config import NodeConfig, NodeDefinition, OutputLocation

logger = logging.getLogger(__name__)

# Node Configuration
extract_code_context_config = NodeConfig(
    # Model selection - needs code access for file reading
    needs_code_access=True,
    model_preference=ModelRouter.CLAUDE_CODE,
    # Agent configuration
    agents=[AgentType.SENIOR_ENGINEER],
    # Prompt template
    prompt_template="""You are a Senior Software Engineer conducting a comprehensive codebase analysis.
You have FULL ACCESS to the repository code. Analyze it thoroughly to create a Code Context Document.

## Repository to Analyze:
{repo_path}

## ANALYSIS METHODOLOGY:

### Phase 1: Code Examination (DO THIS FIRST)
Before making any claims, examine:

1. **Entry Points & Main Files**
   - Locate main.py, index.js, app.py, main.go, or equivalent
   - Identify how the application starts and initializes
   - Trace the execution flow from entry point

2. **Core Business Logic**
   - Find the primary domain models/entities
   - Identify key business operations and workflows
   - Look for service/controller/handler layers

3. **Actual Dependencies Used**
   - Check import statements in source files (not just package.json/requirements.txt)
   - Identify which frameworks are actually instantiated and used
   - Distinguish between installed vs. actually utilized dependencies

4. **Architecture Verification**
   - Examine actual class hierarchies and module dependencies
   - Look at how components communicate (direct calls, events, queues, etc.)
   - Identify real design patterns in the code (not just file naming)

5. **Data Layer Analysis**
   - Find actual database connections and queries
   - Identify ORM usage or raw SQL
   - Look for data models and schemas

### Phase 2: Document Creation

Based on your ACTUAL CODE EXAMINATION, create a Code Context Document with:

## 1. SYSTEM IDENTITY
**What This System Actually Does:**
- Primary purpose (based on core business logic found)
- Problem domain (based on domain models and operations)
- System type (web app/API/CLI tool/library based on entry points)

*Evidence: Quote specific files/classes that prove this*

## 2. ARCHITECTURE REALITY CHECK

**Actual Architecture Pattern:**
Look at the code structure and answer:
- Is this actually MVC? (Show me the Models, Views, Controllers)
- Is this actually microservices? (Show me service boundaries and communication)
- Is this actually event-driven? (Show me event publishers/subscribers)
- Is this actually layered? (Show me the layer boundaries and dependencies)

*Evidence: Reference specific code structures*

**Real Design Patterns Found:**
For each pattern claimed:
- Pattern name
- Where it's implemented (specific files/classes)
- Code example showing the pattern

## 3. TECHNOLOGY STACK - VERIFIED USAGE

**Primary Language(s):**
- Language: [language]
- Actual usage: List 3-5 core files written in this language
- Purpose: What aspects of the system use this language

**Frameworks ACTUALLY IN USE:**
For each framework:
- Framework name
- Initialization/configuration location (specific file:line)
- How it's used (with code example)
- Why it's essential (what breaks if removed)

**Database/Storage:**
- Type (found in connection strings/configs)
- Access method (ORM/driver found in code)
- Schema location or model definitions

## 4. CODE ORGANIZATION ANALYSIS

**Directory Structure Meaning:**
```
src/
├── [directory]/ - {{what you found this contains after examining files}}
├── [directory]/ - {{actual purpose based on code inspection}}
```

**Module Communication Patterns:**
- How do modules actually reference each other?
- What are the dependency directions?
- Are there circular dependencies?

## 5. KEY COMPONENTS AND THEIR ROLES

For each major component found:
- **Component**: [Name]
- **Location**: [Path]
- **Responsibility**: [What it actually does based on its code]
- **Dependencies**: [What it imports/uses]
- **Dependents**: [What uses it]

## 6. INTEGRATION POINTS - VERIFIED

**External Systems:**
- API clients found (with initialization code locations)
- External services called (with example calls)
- Message queues/event buses (with connection code)

**Exposed Interfaces:**
- REST endpoints (with route definitions)
- GraphQL schemas (with resolver locations)
- CLI commands (with command definitions)
- Library exports (with public API surface)

## 7. DATA FLOW ANALYSIS

Trace a typical operation through the system:
1. Entry point: [file:function]
2. Validation: [file:function]
3. Business logic: [file:function]
4. Data access: [file:function]
5. Response: [file:function]

## 8. TESTING REALITY

**Test Coverage:**
- Test files location
- Testing framework (based on imports in test files)
- Types of tests found (unit/integration/e2e)
- Key test examples

## 9. DEVELOPMENT PRACTICES - OBSERVED

Based on code examination:
- **Code Style**: Observed conventions (not just linter configs)
- **Error Handling**: Patterns actually used in code
- **Logging**: Framework and patterns found
- **Configuration**: How config is actually loaded and used

## 10. CRITICAL FINDINGS

**Code Smells/Issues Found:**
- [Issue] in [location]
- [Technical debt] in [component]

**Inconsistencies:**
- Different patterns in [location] vs [location]
- Mixed conventions between [module] and [module]


## VALIDATION CHECKLIST

Before finalizing, verify:
- [ ] Every framework listed is actually imported and used in source code
- [ ] Every pattern claimed has a concrete code example
- [ ] Every component described exists in the repository
- [ ] Architecture description matches actual code structure
- [ ] No languages listed that only appear in config/data files
- [ ] Integration points have actual code implementing them

## IMPORTANT RULES:

1. **NO HALLUCINATION**: Only describe what you can point to in the code
2. **SHOW EVIDENCE**: Every claim must reference specific files/code
3. **ACKNOWLEDGE UNKNOWNS**: If something isn't clear from the code, say so
4. **VERIFY CLAIMS**: Cross-check findings across multiple files
5. **ACTUAL vs INTENDED**: Describe what the code DOES, not what comments say it should do

Remember: You have the actual code. Read it. Don't guess based on file names or metadata.""",
    # Agent customizations
    agent_prompt_customizations={
        AgentType.SENIOR_ENGINEER: """
As a Senior Engineer, focus on:
- Code quality patterns and conventions
- Testing strategies and existing test structure
- Integration points and dependencies
- Performance and scalability considerations
- Security implications for the new feature"""
    },
    # Output configuration
    output_location=OutputLocation.LOCAL,  # Intermediate document
    artifact_names=[ArtifactName.CODE_CONTEXT_DOCUMENT],
    artifact_path_template="{base_path}/pr-{pr_number}/analysis/{artifact_name}.md",
    # Standard workflows - no code changes, no PR feedback needed
    requires_code_changes=False,
    requires_pr_feedback=False,
)


async def extract_code_context_handler(state: dict) -> dict:
    """Extract code context from the repository.

    This handler analyzes the codebase using the configured agent and creates
    a comprehensive code context document.
    """
    from ..enums import WorkflowPhase

    logger.info("🔍 Phase 0: Extracting code context from repository")

    # Update phase
    state["current_phase"] = WorkflowPhase.PHASE_0_CODE_CONTEXT

    # Get repository information
    repo_path = state.get("repo_path", ".")
    feature_description = state.get("feature_description", "")

    # Actually call the agent with the comprehensive prompt
    # Format the prompt with repository path only
    prompt = extract_code_context_config.prompt_template.format(repo_path=repo_path)

    logger.info(
        f"🤖 Calling agent with comprehensive analysis prompt ({len(prompt)} chars)"
    )

    # Call the actual agent based on configuration
    if extract_code_context_config.model_preference == ModelRouter.CLAUDE_CODE:
        # Use Claude Code for code access - MUST succeed, no fallback allowed
        code_context = await _call_claude_code_agent(prompt, repo_path)
    else:
        # This should never happen for code context extraction since we need code access
        raise RuntimeError(
            "Code context extraction requires Claude Code with code access. Ollama cannot access the codebase."
        )

    # Validate that we got a comprehensive analysis, not just a summary
    MIN_CONTEXT_LENGTH = 2000  # Minimum characters for a proper code context document

    if not code_context:
        logger.error("❌ Agent returned None or empty response")
        error_msg = f"Agent failed to provide any analysis for repository: {repo_path}"
        logger.error(f"❌ Analysis failed: {error_msg}")
        raise RuntimeError(f"Code context extraction failed: {error_msg}")

    logger.info(f"📄 Agent analysis completed ({len(code_context)} chars)")

    if len(code_context) < MIN_CONTEXT_LENGTH:
        error_msg = (
            f"Code context document is too short ({len(code_context)} chars, minimum: {MIN_CONTEXT_LENGTH}).\n"
            f"This usually indicates the agent provided only a brief summary instead of comprehensive analysis.\n"
            f"Repository: {repo_path}\n"
            f"Got: {code_context[:500]}..."
        )
        logger.error(f"❌ Insufficient analysis: {error_msg}")
        raise RuntimeError(f"Code context extraction failed: {error_msg}")

    # Store the code context document
    state["code_context_document"] = code_context

    # Create artifact with proper base path
    artifacts_path = Path.home() / ".local/share/github-agent/artifacts"
    artifacts_path.mkdir(parents=True, exist_ok=True)

    pr_number = state.get("pr_number")
    if pr_number:
        artifact_path = (
            artifacts_path / f"pr-{pr_number}" / "analysis" / "code_context_document.md"
        )
    else:
        artifact_path = artifacts_path / "code_context_document.md"

    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(code_context)

    # Update artifacts index
    if "artifacts_index" not in state:
        state["artifacts_index"] = {}
    state["artifacts_index"]["code_context_document"] = str(artifact_path)

    logger.info(f"✅ Code context document created: {artifact_path}")

    return state


async def _call_claude_code_agent(prompt: str, repo_path: str) -> str:
    """Perform comprehensive codebase analysis using Claude CLI.

    This calls the Claude CLI directly with the comprehensive analysis prompt,
    allowing Claude to access and analyze the actual codebase.
    """
    import subprocess

    from ..config import get_claude_cli_path, get_claude_cli_timeout

    try:
        logger.info("🤖 Calling Claude CLI for comprehensive codebase analysis")

        # First, check if Claude CLI is available
        try:
            version_check = subprocess.run(
                [get_claude_cli_path(), "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if version_check.returncode != 0:
                raise RuntimeError(
                    f"Claude CLI version check failed: {version_check.stderr}"
                )

            logger.info(f"Claude CLI available: {version_check.stdout.strip()}")
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            raise RuntimeError(
                f"Claude CLI not available or not responding: {e}"
            ) from e

        # Call Claude CLI with the comprehensive analysis prompt
        claude_result = subprocess.run(
            [get_claude_cli_path()],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=get_claude_cli_timeout(),
            cwd=repo_path,  # Set working directory to repository path
        )

        if claude_result.returncode != 0:
            error_msg = (
                claude_result.stderr.strip()
                if claude_result.stderr
                else "Unknown error"
            )
            raise RuntimeError(
                f"Claude CLI failed with return code {claude_result.returncode}: {error_msg}"
            )

        analysis_result = claude_result.stdout.strip()

        if not analysis_result:
            raise RuntimeError("Claude CLI returned empty analysis")

        logger.info(f"✅ Claude CLI analysis completed ({len(analysis_result)} chars)")
        return analysis_result

    except subprocess.TimeoutExpired as e:
        raise RuntimeError(
            f"Claude CLI analysis timed out after {get_claude_cli_timeout()} seconds"
        ) from e
    except Exception as e:
        logger.error(f"Error calling Claude CLI: {e}")
        raise RuntimeError(f"Claude CLI analysis failed: {e}") from e


# Node Definition
extract_code_context_node = NodeDefinition(
    config=extract_code_context_config,
    handler=extract_code_context_handler,
    description="Analyzes the codebase and creates a comprehensive code context document for feature development",
)
