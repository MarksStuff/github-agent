"""Demonstration of the Enhanced Declarative Workflow System.

This script shows how the new declarative node configuration system works
with integrated standard workflows for code quality and PR feedback.
"""

import asyncio
import logging
from pathlib import Path

from ..enhanced_workflow import create_enhanced_workflow
from ..enums import WorkflowStep

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class MockAgent:
    """Mock agent for demonstration."""

    def __init__(self, name: str):
        self.name = name

    async def analyze(self, context: dict) -> str:
        """Mock analysis method."""
        await asyncio.sleep(0.1)  # Simulate processing
        return f"Mock analysis from {self.name}: {context.get('task', 'general')}"


class MockCodebaseAnalyzer:
    """Mock codebase analyzer for demonstration."""

    def __init__(self, repo_path: str):
        self.repo_path = repo_path

    def analyze(self) -> dict:
        """Mock codebase analysis."""
        return {
            "languages": ["Python"],
            "frameworks": ["LangGraph", "FastAPI"],
            "key_files": ["main.py", "requirements.txt"],
            "patterns": ["Factory pattern", "Dependency injection"],
            "conventions": ["PEP 8", "Type hints"],
        }


class MockGitHubIntegration:
    """Mock GitHub integration for demonstration."""

    def __init__(self):
        self.comments = []
        self.replies = []

    async def get_pr_comments(self, pr_number: int, since=None) -> list[dict]:
        """Mock get PR comments."""
        # Simulate some PR comments
        if pr_number == 123:
            return [
                {
                    "id": 1,
                    "body": "Please add more error handling to the core logic",
                    "user": "reviewer1",
                    "created_at": "2024-01-01T10:00:00Z",
                },
                {
                    "id": 2,
                    "body": "Consider using async/await for better performance",
                    "user": "reviewer2",
                    "created_at": "2024-01-01T11:00:00Z",
                },
            ]
        return []

    async def reply_to_comment(self, comment_id: int, message: str):
        """Mock reply to PR comment."""
        self.replies.append(
            {
                "comment_id": comment_id,
                "message": message,
                "timestamp": "2024-01-01T12:00:00Z",
            }
        )
        logger.info(f"📝 Mock reply to comment #{comment_id}: {message[:50]}...")


async def demo_node_configuration():
    """Demonstrate individual node configurations."""

    logger.info("🎯 Demonstrating Node Configuration System")
    logger.info("=" * 60)

    # Create mock workflow to access node definitions
    workflow = create_enhanced_workflow(
        repo_path=".",
        agents={"mock": MockAgent("demo")},
        codebase_analyzer=MockCodebaseAnalyzer("."),
        github_integration=MockGitHubIntegration(),
    )

    # Show all nodes
    logger.info("\n📋 All Configured Nodes:")
    nodes_summary = workflow.list_all_nodes()

    print(f"\n🏗️  Total Nodes: {nodes_summary['total_nodes']}")
    print(
        f"✨ Workflow Features: {', '.join(nodes_summary['workflow_features'].keys())}"
    )

    # Show detailed configuration for each node
    for step_name, node_info in nodes_summary["nodes"].items():
        print(f"\n📌 {step_name.upper()}")
        print(f"   Description: {node_info['description']}")
        print(f"   Agents: {', '.join(node_info['agents'])}")
        print(f"   Model Router: {node_info['model_router']}")
        print(f"   Output Location: {node_info['output_location']}")
        print("   Standard Workflows:")
        print(
            f"      - Code Quality Checks: {'✅' if node_info['standard_workflows']['code_changes'] else '❌'}"
        )
        print(
            f"      - PR Feedback Integration: {'✅' if node_info['standard_workflows']['pr_feedback'] else '❌'}"
        )

    # Show detailed node status
    logger.info("\n🔍 Detailed Node Configurations:")

    for step in [WorkflowStep.EXTRACT_CODE_CONTEXT, WorkflowStep.PARALLEL_DEVELOPMENT]:
        status = await workflow.get_node_status(step)
        print(f"\n🎛️  {step.value.upper()} Configuration:")
        print(f"   Needs Code Access: {status['config']['needs_code_access']}")
        print(f"   Model Preference: {status['config']['model_preference']}")
        print(f"   Agents: {', '.join(status['config']['agents'])}")
        print(
            f"   Code Quality Checks: {', '.join(status['config']['pre_commit_checks'])}"
        )
        print(f"   Prompt Template: {status['prompt_template_length']} characters")
        print(f"   Agent Customizations: {status['agent_customizations']} agents")


async def demo_workflow_execution():
    """Demonstrate complete workflow execution."""

    logger.info("\n" + "=" * 60)
    logger.info("🚀 Demonstrating Complete Workflow Execution")
    logger.info("=" * 60)

    # Create demo environment
    demo_repo = Path("./demo_repo")
    demo_repo.mkdir(exist_ok=True)

    # Create mock dependencies
    agents = {
        "senior-engineer": MockAgent("Senior Engineer"),
        "architect": MockAgent("Architect"),
        "fast-coder": MockAgent("Fast Coder"),
        "test-first": MockAgent("Test-First Engineer"),
    }

    codebase_analyzer = MockCodebaseAnalyzer(str(demo_repo))
    github_integration = MockGitHubIntegration()

    # Create enhanced workflow
    workflow = create_enhanced_workflow(
        repo_path=str(demo_repo),
        agents=agents,
        codebase_analyzer=codebase_analyzer,
        github_integration=github_integration,
        thread_id="demo-workflow",
    )

    logger.info("🎯 Running workflow for demo feature...")

    try:
        # Execute the workflow
        result = await workflow.run_workflow(
            feature_description="Add user authentication with OAuth2 support",
            pr_number=123,  # Enable PR feedback integration
            git_branch="feature/oauth2-auth",
            raw_feature_input="Implement OAuth2 authentication system",
        )

        logger.info("\n✅ Workflow execution completed!")

        # Show results
        print("\n📊 Workflow Results:")
        print(f"   Feature: {result.get('feature_description')}")
        print(f"   Final Phase: {result.get('current_phase')}")
        print(f"   Quality Status: {result.get('quality')}")
        print(f"   PR Number: {result.get('pr_number')}")

        # Show artifacts created
        artifacts = result.get("artifacts_index", {})
        if artifacts:
            print(f"\n📄 Artifacts Created ({len(artifacts)}):")
            for name, path in artifacts.items():
                print(f"      - {name}: {Path(path).name}")

        # Show PR feedback processing
        pr_feedback = result.get("pr_feedback_applied")
        if pr_feedback:
            print("\n📝 PR Feedback Processed:")
            for feedback_id, outcome in pr_feedback.items():
                print(f"      - Feedback {feedback_id}: {outcome}")

        # Show GitHub replies sent
        if github_integration.replies:
            print(f"\n💬 GitHub Replies Sent ({len(github_integration.replies)}):")
            for reply in github_integration.replies:
                print(
                    f"      - Comment #{reply['comment_id']}: {reply['message'][:50]}..."
                )

    except Exception as e:
        logger.error(f"❌ Workflow execution failed: {e}")
        raise

    finally:
        # Cleanup demo repo
        import shutil

        if demo_repo.exists():
            shutil.rmtree(demo_repo)


async def demo_standard_workflows():
    """Demonstrate standard workflow integration."""

    logger.info("\n" + "=" * 60)
    logger.info("🔧 Demonstrating Standard Workflow Integration")
    logger.info("=" * 60)

    from ..enums import AgentType, ModelRouter
    from ..node_config import CodeQualityCheck, NodeConfig, StandardWorkflows

    # Create a node config with standard workflows
    demo_config = NodeConfig(
        needs_code_access=True,
        model_preference=ModelRouter.CLAUDE_CODE,
        agents=[AgentType.SENIOR_ENGINEER],
        requires_code_changes=True,
        requires_pr_feedback=True,
        pre_commit_checks=[CodeQualityCheck.LINT, CodeQualityCheck.TEST],
        lint_commands=["echo 'Running lint check...'", "echo 'Lint passed!'"],
        test_commands=["echo 'Running tests...'", "echo 'All tests passed!'"],
        pr_feedback_prompt="Process this feedback: {comments}",
        pr_reply_template="✅ Addressed: {outcome} at {timestamp}",
    )

    logger.info("🧪 Testing Code Quality Workflow:")

    # Test code quality checks
    quality_result = await StandardWorkflows.run_code_quality_checks(
        demo_config, repo_path=".", changed_files=["demo_file.py"]
    )

    print(f"   Overall Success: {'✅' if quality_result.overall_success else '❌'}")
    print(f"   Lint Results: {len(quality_result.lint_results)} checks")
    print(f"   Test Results: {len(quality_result.test_results)} checks")

    for i, lint_result in enumerate(quality_result.lint_results):
        status = "✅" if lint_result.succeeded else "❌"
        print(f"      Lint {i+1}: {status} {lint_result.command}")

    for i, test_result in enumerate(quality_result.test_results):
        status = "✅" if test_result.succeeded else "❌"
        print(f"      Test {i+1}: {status} {test_result.command}")

    logger.info("\n💬 Testing PR Feedback Workflow:")

    # Create mock GitHub integration
    mock_github = MockGitHubIntegration()

    # Test PR feedback workflow
    pr_result = await StandardWorkflows.handle_pr_feedback_workflow(
        demo_config, pr_number=123, github_integration=mock_github, last_check_time=None
    )

    print(f"   Has Feedback: {'✅' if pr_result.has_feedback else '❌'}")
    print(f"   Comments Processed: {pr_result.comments_processed}")
    print(f"   Changes Made: {len(pr_result.changes_made)}")

    if mock_github.replies:
        print(f"   Replies Sent: {len(mock_github.replies)}")
        for reply in mock_github.replies:
            print(f"      → Comment #{reply['comment_id']}: Reply sent")


async def main():
    """Run all demonstrations."""

    print("🎭 Enhanced Declarative Workflow System Demo")
    print("=" * 60)

    try:
        # Demo 1: Node Configuration
        await demo_node_configuration()

        # Demo 2: Workflow Execution
        await demo_workflow_execution()

        # Demo 3: Standard Workflows
        await demo_standard_workflows()

        print("\n🎉 All demonstrations completed successfully!")
        print("\n💡 Key Benefits Demonstrated:")
        print("   ✅ Declarative node configuration with separate files")
        print("   ✅ Automatic code quality checks (lint/test)")
        print("   ✅ Integrated PR feedback processing and replies")
        print("   ✅ Transparent model selection logic")
        print("   ✅ PR number inclusion in artifact paths")
        print("   ✅ Agent-specific prompt customizations")
        print("   ✅ Composable standard workflow components")

    except Exception as e:
        logger.error(f"❌ Demo failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
