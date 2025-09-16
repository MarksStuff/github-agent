"""Parallel Development Node Definition.

This node implements the actual feature code using multiple agents working in parallel.
Includes full standard workflow integration: code quality checks and PR feedback.
"""

import asyncio
import logging
from pathlib import Path

from ..enums import AgentType, ArtifactName, ModelRouter
from ..node_config import CodeQualityCheck, NodeConfig, NodeDefinition, OutputLocation

logger = logging.getLogger(__name__)

# Node Configuration
parallel_development_config = NodeConfig(
    # Model selection - needs code access for implementation
    needs_code_access=True,
    model_preference=ModelRouter.CLAUDE_CODE,
    # Multiple agents for parallel development
    agents=[AgentType.SENIOR_ENGINEER, AgentType.FAST_CODER, AgentType.TEST_FIRST],
    # Base prompt template
    prompt_template="""You are implementing a feature as part of a parallel development team.

## Context
**Feature to Implement:** {feature_description}

**Design Document:**
{design_document}

**Code Context:**
{code_context}

**Your Role:** {agent_role}

## Implementation Task
Implement your assigned portion of the feature according to the design document.

### Requirements
1. **Follow Design**: Implement according to the approved design document
2. **Code Quality**: Follow existing code patterns and quality standards
3. **Testing**: Include comprehensive tests for your implementation
4. **Documentation**: Add appropriate code comments and docstrings
5. **Integration**: Ensure your code integrates properly with existing system

### Deliverables
- Working code implementation
- Comprehensive test coverage
- Clear documentation
- Integration with existing codebase patterns

### Guidelines
- Use existing utilities and patterns where possible
- Maintain backward compatibility
- Handle errors gracefully
- Follow security best practices
- Consider performance implications""",
    # Agent-specific customizations
    agent_prompt_customizations={
        AgentType.SENIOR_ENGINEER: """
As the Senior Engineer, you are responsible for:
- Core business logic implementation
- Complex algorithm and data structure design
- Integration with existing system components
- Code architecture and design patterns
- Performance optimization and scalability
- Code review and quality assurance for the team

Focus on creating robust, maintainable code that serves as the foundation for the feature.""",
        AgentType.FAST_CODER: """
As the Fast Coder, you are responsible for:
- Rapid implementation of straightforward components
- Utility functions and helper methods
- Configuration and setup code
- Basic CRUD operations and data handling
- Quick prototyping and proof-of-concept code
- Initial integration scaffolding

Focus on delivering working code quickly while maintaining quality standards.""",
        AgentType.TEST_FIRST: """
As the Test-First Engineer, you are responsible for:
- Comprehensive test suite implementation
- Test-driven development approach
- Mock and fixture creation
- Integration test setup
- Performance and load testing
- Quality assurance and validation

Focus on ensuring the feature is thoroughly tested and meets quality standards.""",
    },
    # Output configuration - goes to repository for review
    output_location=OutputLocation.REPOSITORY,
    artifact_names=[ArtifactName.IMPLEMENTATION_CODE, ArtifactName.TEST_CODE],
    artifact_path_template="{base_path}/pr-{pr_number}/implementation/{artifact_name}",
    # Standard workflows - full integration
    requires_code_changes=True,
    requires_pr_feedback=True,
    # Code quality configuration
    pre_commit_checks=[
        CodeQualityCheck.LINT,
        CodeQualityCheck.TEST,
        CodeQualityCheck.FORMAT,
    ],
    test_commands=[
        "python -m pytest tests/ -v",
        "python -m pytest tests/integration/ -v",
    ],
    lint_commands=["scripts/ruff-autofix.sh", "scripts/run-code-checks.sh"],
    # PR feedback configuration
    pr_feedback_prompt="""Review and address the following implementation feedback from PR comments:

{comments}

Update the implementation to address the feedback while maintaining:
- Code quality and consistency
- Test coverage and reliability
- Performance requirements
- Security considerations
- Integration with existing patterns

Focus on:
- Fixing identified bugs or issues
- Improving code clarity and maintainability
- Addressing performance concerns
- Enhancing test coverage
- Resolving integration problems""",
    pr_reply_template="""✅ Implementation updated based on code review feedback.

**Changes made:** {outcome}

**Code quality status:** All lint and test checks passing ✅
**Updated at:** {timestamp}

The implementation has been revised to address your feedback. All automated quality checks are passing. Please review the updated code and let me know if additional changes are needed.""",
)


async def parallel_development_handler(state: dict) -> dict:
    """Implement the feature using parallel development approach.

    This handler coordinates multiple agents to implement different aspects
    of the feature in parallel, then integrates the results.
    """
    from ..enums import WorkflowPhase

    logger.info("💻 Phase 3: Parallel development implementation")

    # Update phase
    state["current_phase"] = WorkflowPhase.PHASE_3_PARALLEL_DEV

    # Get required context
    feature_description = state.get("feature_description", "")
    design_document = state.get("design_document", "")
    code_context = state.get("code_context_document", "")
    repo_path = state.get("repo_path", ".")

    if not design_document:
        logger.warning(
            "No design document available - proceeding with basic implementation"
        )
        design_document = (
            "Design document not available - implementing based on feature description"
        )

    # Prepare work assignments for parallel development
    work_assignments = {
        AgentType.SENIOR_ENGINEER: "core_logic",
        AgentType.FAST_CODER: "utilities_and_helpers",
        AgentType.TEST_FIRST: "comprehensive_tests",
    }

    # Run parallel development
    logger.info("🚀 Starting parallel development with multiple agents")

    # Execute agents in parallel (mock implementation)
    development_results = {}
    tasks = []

    for agent_type, assignment in work_assignments.items():
        task = _execute_agent_development(
            agent_type,
            assignment,
            {
                "feature_description": feature_description,
                "design_document": design_document,
                "code_context": code_context,
                "agent_role": assignment,
            },
        )
        tasks.append(task)

    # Wait for all agents to complete
    results = await asyncio.gather(*tasks)

    # Combine results
    for i, agent_type in enumerate(work_assignments.keys()):
        development_results[agent_type] = results[i]

    # Integrate the parallel development results
    integrated_implementation = await _integrate_development_results(
        development_results, feature_description, repo_path
    )

    # Store implementation results
    state["implementation_code"] = integrated_implementation["implementation"]
    state["test_code"] = integrated_implementation["tests"]
    state["modified_files"] = integrated_implementation["files_created"]

    # Save artifacts
    repo_path_obj = Path(repo_path)
    pr_number = state.get("pr_number")

    if pr_number:
        artifact_base = repo_path_obj / f"pr-{pr_number}" / "implementation"
    else:
        artifact_base = repo_path_obj / ".local" / "artifacts" / "implementation"

    artifact_base.mkdir(parents=True, exist_ok=True)

    # Save implementation code
    impl_path = artifact_base / "implementation_code.py"
    impl_path.write_text(integrated_implementation["implementation"])

    # Save test code
    test_path = artifact_base / "test_code.py"
    test_path.write_text(integrated_implementation["tests"])

    # Update artifacts index
    if "artifacts_index" not in state:
        state["artifacts_index"] = {}
    state["artifacts_index"]["implementation_code"] = str(impl_path)
    state["artifacts_index"]["test_code"] = str(test_path)

    logger.info("💻 Implementation completed:")
    logger.info(f"   📁 Implementation: {impl_path}")
    logger.info(f"   🧪 Tests: {test_path}")
    logger.info(
        f"   📊 Files created: {len(integrated_implementation['files_created'])}"
    )

    # Mark as ready for quality checks (handled by node config framework)
    state["implementation_ready"] = True

    return state


async def _execute_agent_development(
    agent_type: AgentType, assignment: str, context: dict
) -> dict:
    """Execute development task for a specific agent."""

    logger.info(f"🤖 {agent_type} working on {assignment}")

    # Simulate processing time
    await asyncio.sleep(0.2)

    # Mock agent development (replace with real agent calls)
    if agent_type == AgentType.SENIOR_ENGINEER:
        return await _mock_senior_engineer_implementation(context)
    elif agent_type == AgentType.FAST_CODER:
        return await _mock_fast_coder_implementation(context)
    elif agent_type == AgentType.TEST_FIRST:
        return await _mock_test_first_implementation(context)
    else:
        return {"code": "# No implementation", "files": []}


async def _mock_senior_engineer_implementation(context: dict) -> dict:
    """Mock senior engineer implementation."""

    feature_name = context["feature_description"].lower().replace(" ", "_")

    implementation = f'''"""Core implementation for {context["feature_description"]}."""

import logging
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class {_to_pascal_case(feature_name)}Config:
    """Configuration for {context["feature_description"]}."""
    enabled: bool = True
    timeout: int = 30
    max_retries: int = 3


class {_to_pascal_case(feature_name)}Core:
    """Core business logic for {context["feature_description"]}."""

    def __init__(self, config: {_to_pascal_case(feature_name)}Config):
        self.config = config
        self.logger = logging.getLogger(f"{{__name__}}.{{self.__class__.__name__}}")

    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the main feature logic.

        Args:
            input_data: Input parameters for the feature

        Returns:
            Result of the feature execution

        Raises:
            ValueError: If input data is invalid
            RuntimeError: If execution fails
        """
        if not self.config.enabled:
            raise RuntimeError("Feature is not enabled")

        # Validate input
        validated_input = self._validate_input(input_data)

        try:
            # Core business logic
            result = await self._process_data(validated_input)

            self.logger.info(f"Feature execution completed successfully")
            return {{
                "status": "success",
                "result": result,
                "metadata": {{
                    "processed_at": "timestamp",
                    "version": "1.0.0"
                }}
            }}

        except Exception as e:
            self.logger.error(f"Feature execution failed: {{e}}")
            raise RuntimeError(f"Execution failed: {{e}}") from e

    def _validate_input(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and normalize input data."""
        if not isinstance(input_data, dict):
            raise ValueError("Input data must be a dictionary")

        # Add validation logic here
        return input_data

    async def _process_data(self, data: Dict[str, Any]) -> Any:
        """Process the validated input data."""
        # Implement core business logic here
        self.logger.debug(f"Processing data: {{data}}")

        # Placeholder implementation
        return {{"processed": True, "data": data}}


class {_to_pascal_case(feature_name)}Manager:
    """High-level manager for {context["feature_description"]}."""

    def __init__(self, config: Optional[{_to_pascal_case(feature_name)}Config] = None):
        self.config = config or {_to_pascal_case(feature_name)}Config()
        self.core = {_to_pascal_case(feature_name)}Core(self.config)

    async def run(self, **kwargs) -> Dict[str, Any]:
        """Run the feature with provided parameters."""
        return await self.core.execute(kwargs)

    def is_enabled(self) -> bool:
        """Check if the feature is enabled."""
        return self.config.enabled

    def configure(self, **kwargs) -> None:
        """Update feature configuration."""
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
'''

    return {
        "code": implementation,
        "files": [f"{feature_name}_core.py"],
        "component": "core_logic",
    }


async def _mock_fast_coder_implementation(context: dict) -> dict:
    """Mock fast coder implementation."""

    feature_name = context["feature_description"].lower().replace(" ", "_")

    utilities = f'''"""Utility functions and helpers for {context["feature_description"]}."""

import json
import logging
from typing import Any, Dict, List, Union
from pathlib import Path
from datetime import datetime


def setup_logging(name: str, level: str = "INFO") -> logging.Logger:
    """Set up logging for the feature."""
    logger = logging.getLogger(name)
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(getattr(logging, level.upper()))
    return logger


def load_config(config_path: Union[str, Path]) -> Dict[str, Any]:
    """Load configuration from file."""
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found: {{config_path}}")

    with open(path, 'r') as f:
        if path.suffix.lower() == '.json':
            return json.load(f)
        else:
            # Add support for other formats as needed
            raise ValueError(f"Unsupported config format: {{path.suffix}}")


def save_results(results: Dict[str, Any], output_path: Union[str, Path]) -> None:
    """Save results to file."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, 'w') as f:
        json.dump(results, f, indent=2, default=str)


def validate_environment() -> Dict[str, bool]:
    """Validate the environment for feature execution."""
    checks = {{
        "python_version": True,  # Add actual checks
        "dependencies": True,
        "permissions": True,
        "disk_space": True
    }}

    return checks


class {_to_pascal_case(feature_name)}Utils:
    """Utility class for {context["feature_description"]}."""

    @staticmethod
    def format_output(data: Any) -> str:
        """Format output for display."""
        if isinstance(data, dict):
            return json.dumps(data, indent=2, default=str)
        return str(data)

    @staticmethod
    def generate_id() -> str:
        """Generate a unique identifier."""
        from uuid import uuid4
        return str(uuid4())

    @staticmethod
    def get_timestamp() -> str:
        """Get current timestamp."""
        return datetime.now().isoformat()

    @staticmethod
    def sanitize_input(input_str: str) -> str:
        """Sanitize user input."""
        # Add appropriate sanitization logic
        return input_str.strip()


# Configuration helpers
DEFAULT_CONFIG = {{
    "feature_name": "{feature_name}",
    "version": "1.0.0",
    "debug": False,
    "timeout": 30
}}


def get_default_config() -> Dict[str, Any]:
    """Get default configuration."""
    return DEFAULT_CONFIG.copy()


def merge_configs(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Merge configuration dictionaries."""
    result = base.copy()
    result.update(override)
    return result
'''

    return {
        "code": utilities,
        "files": [f"{feature_name}_utils.py", f"{feature_name}_config.py"],
        "component": "utilities",
    }


async def _mock_test_first_implementation(context: dict) -> dict:
    """Mock test-first implementation."""

    feature_name = context["feature_description"].lower().replace(" ", "_")

    tests = f'''"""Comprehensive tests for {context["feature_description"]}."""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from pathlib import Path
import tempfile
import json

# Import the modules being tested (adjust imports as needed)
# from .{feature_name}_core import {_to_pascal_case(feature_name)}Core, {_to_pascal_case(feature_name)}Config, {_to_pascal_case(feature_name)}Manager
# from .{feature_name}_utils import {_to_pascal_case(feature_name)}Utils, load_config, save_results


class Test{_to_pascal_case(feature_name)}Config:
    """Test configuration class."""

    def test_default_config(self):
        """Test default configuration values."""
        # config = {_to_pascal_case(feature_name)}Config()
        # assert config.enabled is True
        # assert config.timeout == 30
        # assert config.max_retries == 3
        pass

    def test_custom_config(self):
        """Test custom configuration values."""
        # config = {_to_pascal_case(feature_name)}Config(
        #     enabled=False,
        #     timeout=60,
        #     max_retries=5
        # )
        # assert config.enabled is False
        # assert config.timeout == 60
        # assert config.max_retries == 5
        pass


class Test{_to_pascal_case(feature_name)}Core:
    """Test core business logic."""

    @pytest.fixture
    def config(self):
        """Create test configuration."""
        # return {_to_pascal_case(feature_name)}Config()
        pass

    @pytest.fixture
    def core(self, config):
        """Create core instance for testing."""
        # return {_to_pascal_case(feature_name)}Core(config)
        pass

    @pytest.mark.asyncio
    async def test_execute_success(self, core):
        """Test successful execution."""
        # input_data = {{"test": "data"}}
        # result = await core.execute(input_data)
        #
        # assert result["status"] == "success"
        # assert "result" in result
        # assert "metadata" in result
        pass

    @pytest.mark.asyncio
    async def test_execute_invalid_input(self, core):
        """Test execution with invalid input."""
        # with pytest.raises(ValueError, match="Input data must be a dictionary"):
        #     await core.execute("invalid_input")
        pass

    @pytest.mark.asyncio
    async def test_execute_disabled_feature(self, config):
        """Test execution when feature is disabled."""
        # config.enabled = False
        # core = {_to_pascal_case(feature_name)}Core(config)
        #
        # with pytest.raises(RuntimeError, match="Feature is not enabled"):
        #     await core.execute({{"test": "data"}})
        pass

    def test_validate_input_valid(self, core):
        """Test input validation with valid data."""
        # valid_input = {{"key": "value"}}
        # result = core._validate_input(valid_input)
        # assert result == valid_input
        pass

    def test_validate_input_invalid(self, core):
        """Test input validation with invalid data."""
        # with pytest.raises(ValueError):
        #     core._validate_input("not_a_dict")
        pass

    @pytest.mark.asyncio
    async def test_process_data(self, core):
        """Test data processing."""
        # test_data = {{"key": "value"}}
        # result = await core._process_data(test_data)
        #
        # assert result["processed"] is True
        # assert result["data"] == test_data
        pass


class Test{_to_pascal_case(feature_name)}Manager:
    """Test feature manager."""

    @pytest.fixture
    def manager(self):
        """Create manager instance for testing."""
        # return {_to_pascal_case(feature_name)}Manager()
        pass

    @pytest.mark.asyncio
    async def test_run(self, manager):
        """Test manager run method."""
        # result = await manager.run(test="data")
        # assert result["status"] == "success"
        pass

    def test_is_enabled_default(self, manager):
        """Test is_enabled with default config."""
        # assert manager.is_enabled() is True
        pass

    def test_configure(self, manager):
        """Test configuration update."""
        # manager.configure(timeout=60, max_retries=5)
        # assert manager.config.timeout == 60
        # assert manager.config.max_retries == 5
        pass


class Test{_to_pascal_case(feature_name)}Utils:
    """Test utility functions."""

    def test_format_output_dict(self):
        """Test output formatting with dictionary."""
        # data = {{"key": "value", "number": 42}}
        # result = {_to_pascal_case(feature_name)}Utils.format_output(data)
        # assert json.loads(result) == data
        pass

    def test_format_output_string(self):
        """Test output formatting with string."""
        # data = "test string"
        # result = {_to_pascal_case(feature_name)}Utils.format_output(data)
        # assert result == data
        pass

    def test_generate_id(self):
        """Test ID generation."""
        # id1 = {_to_pascal_case(feature_name)}Utils.generate_id()
        # id2 = {_to_pascal_case(feature_name)}Utils.generate_id()
        #
        # assert id1 != id2
        # assert len(id1) == 36  # UUID length
        pass

    def test_get_timestamp(self):
        """Test timestamp generation."""
        # timestamp = {_to_pascal_case(feature_name)}Utils.get_timestamp()
        # assert isinstance(timestamp, str)
        # assert "T" in timestamp  # ISO format
        pass

    def test_sanitize_input(self):
        """Test input sanitization."""
        # result = {_to_pascal_case(feature_name)}Utils.sanitize_input("  test  ")
        # assert result == "test"
        pass


class TestConfigurationHelpers:
    """Test configuration helper functions."""

    def test_load_config_json(self):
        """Test loading JSON configuration."""
        # with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        #     test_config = {{"test": "value"}}
        #     json.dump(test_config, f)
        #     f.flush()
        #
        #     result = load_config(f.name)
        #     assert result == test_config
        #
        #     Path(f.name).unlink()  # Cleanup
        pass

    def test_load_config_not_found(self):
        """Test loading non-existent configuration."""
        # with pytest.raises(FileNotFoundError):
        #     load_config("non_existent_file.json")
        pass

    def test_save_results(self):
        """Test saving results to file."""
        # with tempfile.TemporaryDirectory() as temp_dir:
        #     output_path = Path(temp_dir) / "results.json"
        #     test_data = {{"result": "success", "value": 42}}
        #
        #     save_results(test_data, output_path)
        #
        #     assert output_path.exists()
        #     with open(output_path) as f:
        #         loaded_data = json.load(f)
        #     assert loaded_data == test_data
        pass


# Integration tests
class TestIntegration:
    """Integration tests for the complete feature."""

    @pytest.mark.asyncio
    async def test_end_to_end_workflow(self):
        """Test complete end-to-end workflow."""
        # manager = {_to_pascal_case(feature_name)}Manager()
        #
        # # Test the complete workflow
        # result = await manager.run(
        #     input_data="test",
        #     parameters={{"test": True}}
        # )
        #
        # assert result["status"] == "success"
        # assert "result" in result
        pass

    @pytest.mark.asyncio
    async def test_error_handling_workflow(self):
        """Test error handling in complete workflow."""
        # manager = {_to_pascal_case(feature_name)}Manager()
        #
        # with pytest.raises(ValueError):
        #     await manager.run(invalid_input="data")
        pass


# Performance tests
class TestPerformance:
    """Performance tests for the feature."""

    @pytest.mark.asyncio
    async def test_execution_time(self):
        """Test that execution completes within time limits."""
        # import time
        #
        # manager = {_to_pascal_case(feature_name)}Manager()
        #
        # start_time = time.time()
        # await manager.run(test="data")
        # execution_time = time.time() - start_time
        #
        # assert execution_time < 1.0  # Should complete within 1 second
        pass

    @pytest.mark.asyncio
    async def test_memory_usage(self):
        """Test memory usage remains reasonable."""
        # import psutil
        # import os
        #
        # process = psutil.Process(os.getpid())
        # initial_memory = process.memory_info().rss
        #
        # manager = {_to_pascal_case(feature_name)}Manager()
        # await manager.run(test="data")
        #
        # final_memory = process.memory_info().rss
        # memory_increase = final_memory - initial_memory
        #
        # # Memory increase should be reasonable (less than 10MB for this test)
        # assert memory_increase < 10 * 1024 * 1024
        pass


# Fixtures and test utilities
@pytest.fixture
def sample_input_data():
    """Sample input data for testing."""
    return {{
        "id": "test-123",
        "data": {{"key": "value"}},
        "options": {{"timeout": 30}}
    }}


@pytest.fixture
def expected_output():
    """Expected output structure for testing."""
    return {{
        "status": "success",
        "result": {{}},
        "metadata": {{}}
    }}


# Mock helpers
def create_mock_config(**kwargs):
    """Create mock configuration for testing."""
    defaults = {{
        "enabled": True,
        "timeout": 30,
        "max_retries": 3
    }}
    defaults.update(kwargs)
    return Mock(**defaults)


@pytest.fixture
def mock_external_service():
    """Mock external service for testing."""
    mock = AsyncMock()
    mock.call.return_value = {{"status": "success"}}
    return mock
'''

    return {
        "code": tests,
        "files": [f"test_{feature_name}.py", f"test_{feature_name}_integration.py"],
        "component": "tests",
    }


async def _integrate_development_results(
    development_results: dict, feature_description: str, repo_path: str
) -> dict:
    """Integrate the results from parallel development."""

    logger.info("🔧 Integrating parallel development results")

    # Combine all code components
    implementation_parts = []
    test_parts = []
    files_created = []

    for agent_type, result in development_results.items():
        logger.info(
            f"   📝 Integrating {agent_type} contribution: {result.get('component', 'unknown')}"
        )

        if result.get("component") in ["core_logic", "utilities"]:
            implementation_parts.append(
                f"# {agent_type} contribution\n{result['code']}\n"
            )
        elif result.get("component") == "tests":
            test_parts.append(f"# {agent_type} contribution\n{result['code']}\n")

        files_created.extend(result.get("files", []))

    # Create integrated implementation
    integrated_implementation = f'''"""
Integrated implementation for {feature_description}

This module contains the complete implementation created by parallel development.
Generated by multiple agents working in coordination.
"""

{chr(10).join(implementation_parts)}


# Main interface
def main():
    """Main entry point for the feature."""
    print(f"Feature '{feature_description}' implementation loaded successfully")


if __name__ == "__main__":
    main()
'''

    # Create integrated tests
    integrated_tests = f'''"""
Integrated test suite for {feature_description}

This module contains comprehensive tests created by the test-first approach.
"""

{chr(10).join(test_parts)}


# Test runner
if __name__ == "__main__":
    import pytest
    pytest.main([__file__])
'''

    logger.info(
        f"✅ Integration completed - {len(files_created)} files in implementation"
    )

    return {
        "implementation": integrated_implementation,
        "tests": integrated_tests,
        "files_created": files_created,
    }


def _to_pascal_case(snake_str: str) -> str:
    """Convert snake_case to PascalCase."""
    return "".join(word.capitalize() for word in snake_str.split("_"))


# Node Definition
parallel_development_node = NodeDefinition(
    config=parallel_development_config,
    handler=parallel_development_handler,
    description="Implements the feature using parallel development with multiple agents, includes full code quality and PR feedback integration",
)
