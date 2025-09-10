"""Command-line interface for the LangGraph workflow."""

import argparse
import asyncio
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

# Add parent directory for imports
sys.path.append(str(Path(__file__).parent.parent))

from langgraph_workflow.graph import WorkflowGraph
from langgraph_workflow.routing.model_router import ModelRouter
from langgraph_workflow.utils.artifacts import ArtifactManager
from langgraph_workflow.utils.validators import StateValidator

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class LangGraphCLI:
    """Command-line interface for LangGraph workflow operations."""

    def __init__(self):
        """Initialize CLI with configuration."""
        self.repo_path = os.getenv("REPO_PATH", os.getcwd())
        self.repo_name = self._detect_repo_name()
        self.checkpointer_path = os.getenv(
            "LANGGRAPH_DB_PATH", ".langgraph_checkpoints/agent_state.db"
        )

        # Initialize components
        self.workflow_graph = None
        self.model_router = None
        self.artifact_manager = None

    def _detect_repo_name(self) -> str:
        """Detect repository name from git configuration."""
        try:
            import subprocess

            # Change to repo directory and get remote URL
            result = subprocess.run(
                ["git", "config", "--get", "remote.origin.url"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True,
            )

            remote_url = result.stdout.strip()

            # Parse different URL formats
            if remote_url.startswith("git@github.com"):
                # SSH format: git@github.com:owner/repo.git or git@github.com-alias:owner/repo.git
                if ":" in remote_url:
                    _, repo_part = remote_url.split(":", 1)
                    repo_name = repo_part.replace(".git", "")
                else:
                    raise ValueError("Could not parse SSH URL format")
            elif "github.com" in remote_url:
                # HTTPS format: https://github.com/owner/repo.git
                repo_name = remote_url.split("github.com/")[-1].replace(".git", "")
            else:
                raise ValueError(f"Unsupported remote URL format: {remote_url}")

            # Validate format
            if "/" not in repo_name:
                raise ValueError(f"Invalid repo name format: {repo_name}")

            logger.info(f"Detected repository: {repo_name}")
            return repo_name

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to get git remote URL: {e}")
            logger.error(f"Make sure {self.repo_path} is a valid git repository")
            raise ValueError(
                f"Repository path {self.repo_path} is not a git repository or has no remote"
            )
        except Exception as e:
            logger.error(f"Failed to detect repository name: {e}")
            raise ValueError(
                f"Could not determine repository name from {self.repo_path}"
            )

    def _extract_feature_from_prd(
        self, prd_file: Path, feature_name: str
    ) -> tuple[str, str]:
        """Extract feature from PRD document.

        Args:
            prd_file: Path to PRD file
            feature_name: Name of feature to extract

        Returns:
            Tuple of (task_spec, feature_display_name)
        """
        if not prd_file.exists():
            raise FileNotFoundError(f"PRD file not found: {prd_file}")

        print(f"Reading PRD from: {prd_file}")
        with open(prd_file, encoding="utf-8") as f:
            prd_content = f.read()

        print(f"Extracting feature: {feature_name}")

        # Initialize workflow graph to get senior engineer
        if not self.workflow_graph:
            await self.initialize()

        # Create a simple extraction context
        extraction_context = {"prd_extraction": True}

        extraction_prompt = f"""Extract the complete feature description for "{feature_name}" from the following PRD document.

PRD Document:
{prd_content}

Instructions:
1. Find the section that describes the feature "{feature_name}"
2. Extract ALL relevant information about this feature including:
   - Feature name and description
   - Requirements and specifications
   - Acceptance criteria
   - Technical constraints
   - Implementation details
   - Dependencies
   - Any other relevant information

Return ONLY the extracted feature content in a clear, structured format.
If the feature "{feature_name}" is not found in the PRD, respond with "FEATURE_NOT_FOUND".
"""

        # Use senior engineer to extract
        senior_engineer = self.workflow_graph.agent_nodes.orchestrator.agents[
            "senior_engineer"
        ]
        result = senior_engineer.persona.ask(extraction_prompt)

        if "FEATURE_NOT_FOUND" in result:
            raise ValueError(f"Feature '{feature_name}' not found in PRD")

        # Create formatted task spec
        task_spec = f"""# Feature: {feature_name}
(Extracted from PRD: {prd_file.name})

{result}"""

        print(f"✅ Successfully extracted feature: {feature_name}")
        return task_spec, feature_name

    async def initialize(self):
        """Initialize workflow components."""
        try:
            # Ensure checkpoint directory exists
            checkpoint_dir = Path(self.checkpointer_path).parent
            checkpoint_dir.mkdir(parents=True, exist_ok=True)

            # Initialize components
            self.workflow_graph = WorkflowGraph(
                self.repo_name, self.repo_path, self.checkpointer_path
            )
            self.model_router = ModelRouter()
            self.artifact_manager = ArtifactManager(self.repo_path)

            logger.info(f"Initialized LangGraph CLI for {self.repo_name}")

        except Exception as e:
            logger.error(f"Failed to initialize CLI: {e}")
            raise e

    async def cmd_start(self, args):
        """Start a new workflow."""
        if not self.workflow_graph:
            await self.initialize()

        # Validate arguments (similar to step1_analysis.py)
        if args.prd_file and not args.feature:
            print("Error: --feature is required when using --prd-file")
            return 1
        if args.feature and not args.prd_file:
            print("Error: --prd-file is required when using --feature")
            return 1
        if args.prd_file and args.task_file:
            print("Error: Cannot use both task_file and --prd-file")
            return 1

        # Get task specification and feature name
        feature_name = None

        if args.prd_file:
            # Extract feature from PRD
            try:
                prd_file = Path(args.prd_file)
                task_spec, feature_name = await self._extract_feature_from_prd(
                    prd_file, args.feature
                )
            except Exception as e:
                print(f"❌ PRD extraction failed: {e}")
                return 1

        elif args.task_file:
            # Read from task file
            task_file = Path(args.task_file)
            if not task_file.exists():
                print(f"Error: Task file not found: {task_file}")
                return 1
            task_spec = task_file.read_text(encoding="utf-8")
            feature_name = args.feature_name

        else:
            # Interactive input
            print("Enter task specification (end with empty line):")
            lines = []
            while True:
                try:
                    line = input()
                    if not line:
                        break
                    lines.append(line)
                except EOFError:
                    break
            task_spec = "\n".join(lines)
            feature_name = args.feature_name

        if not task_spec.strip():
            print("Error: Empty task specification")
            return 1

        if not feature_name:
            print("Error: Feature name is required")
            return 1

        # Generate thread ID if not provided
        thread_id = (
            args.thread_id or f"workflow-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        )

        print(f"Starting workflow: {thread_id}")
        print(f"Repository: {self.repo_name}")
        print(f"Feature: {feature_name}")
        print(f"Task length: {len(task_spec)} characters")

        try:
            result = await self.workflow_graph.run_workflow(
                thread_id=thread_id, task_spec=task_spec, feature_name=feature_name
            )

            if result["status"] == "completed":
                print("✅ Workflow completed successfully!")
                print(f"Thread ID: {result['thread_id']}")
            else:
                print(f"❌ Workflow failed: {result.get('error')}")
                return 1

        except Exception as e:
            print(f"❌ Workflow execution failed: {e}")
            logger.exception("Workflow execution failed")
            return 1

    async def cmd_resume(self, args):
        """Resume a paused workflow."""
        if not self.workflow_graph:
            await self.initialize()

        print(f"Resuming workflow: {args.thread_id}")

        try:
            result = await self.workflow_graph.resume_workflow(args.thread_id)

            if result["status"] == "resumed":
                print("✅ Workflow resumed successfully!")
                print(f"Thread ID: {result['thread_id']}")
            else:
                print(f"❌ Resume failed: {result.get('error')}")
                return 1

        except Exception as e:
            print(f"❌ Resume failed: {e}")
            logger.exception("Resume failed")
            return 1

    async def cmd_status(self, args):
        """Get workflow status."""
        if not self.workflow_graph:
            await self.initialize()

        state = self.workflow_graph.get_workflow_state(args.thread_id)

        if not state:
            print(f"❌ Workflow not found: {args.thread_id}")
            return 1

        # Display status
        current_phase = state.get("current_phase", "unknown")
        if hasattr(current_phase, "value"):
            current_phase = current_phase.value

        print(f"Workflow Status: {args.thread_id}")
        print(f"  Phase: {current_phase}")
        print(f"  Feature: {state.get('feature_name', 'Unknown')}")
        print(f"  PR: #{state.get('pr_number', 'None')}")
        print(f"  Quality: {state.get('quality_state', 'Unknown')}")
        print(f"  Retry Count: {state.get('retry_count', 0)}")
        print(f"  Paused: {state.get('paused_for_review', False)}")

        # Show recent messages
        messages = state.get("messages_window", [])
        if messages:
            print("\nRecent Messages:")
            for msg in messages[-3:]:
                role = msg.get("role", "system")
                content = msg.get("content", "")[:100]
                print(f"  {role}: {content}")

        # Show artifacts
        artifacts = state.get("artifacts_index", {})
        if artifacts:
            print(f"\nArtifacts ({len(artifacts)}):")
            for name, path in artifacts.items():
                print(f"  {name}: {path}")

    async def cmd_list(self, args):
        """List all workflow threads."""
        if not self.workflow_graph:
            await self.initialize()

        threads = self.workflow_graph.list_threads()

        if not threads:
            print("No workflow threads found.")
            return

        print(f"Workflow Threads ({len(threads)}):")
        print("-" * 60)

        for thread in threads:
            print(f"  {thread['thread_id']}")
            print(f"    Status: {thread.get('status', 'unknown')}")
            print(f"    Phase: {thread.get('current_phase', 'unknown')}")
            print(f"    Updated: {thread.get('last_updated', 'unknown')}")
            print()

    async def cmd_validate(self, args):
        """Validate workflow state."""
        if not self.workflow_graph:
            await self.initialize()

        state = self.workflow_graph.get_workflow_state(args.thread_id)

        if not state:
            print(f"❌ Workflow not found: {args.thread_id}")
            return 1

        # Run validation
        summary = StateValidator.get_validation_summary(state)

        print(f"Validation Report: {args.thread_id}")
        print(f"  Overall Valid: {summary['overall_valid']}")
        print(f"  Total Errors: {summary['total_errors']}")
        print()

        # Show check details
        for check_name, check_result in summary["checks"].items():
            status = "✅" if check_result["valid"] else "❌"
            print(f"  {status} {check_name}: {check_result['error_count']} errors")

            if not check_result["valid"] and args.verbose:
                for error in check_result["errors"]:
                    print(f"    - {error}")

        if not summary["overall_valid"]:
            return 1

    async def cmd_artifacts(self, args):
        """Manage workflow artifacts."""
        if not self.artifact_manager:
            await self.initialize()

        if args.artifacts_action == "list":
            artifacts = self.artifact_manager.list_artifacts(args.thread_id, args.type)

            if not artifacts:
                print(f"No artifacts found for thread: {args.thread_id}")
                return

            print(f"Artifacts for {args.thread_id}:")
            print("-" * 60)

            for artifact in artifacts:
                print(f"  {artifact['artifact_type']}/{artifact['filename']}")
                print(f"    Size: {artifact['size_bytes']} bytes")
                print(f"    Modified: {artifact['modified_at']}")
                if args.verbose and artifact.get("metadata"):
                    print(f"    Metadata: {artifact['metadata']}")
                print()

        elif args.artifacts_action == "export":
            export_path = args.export_path or f"{args.thread_id}_artifacts.zip"
            exported_path = self.artifact_manager.export_artifacts(
                args.thread_id, export_path
            )
            print(f"✅ Exported artifacts to: {exported_path}")

        elif args.artifacts_action == "cleanup":
            self.artifact_manager.cleanup_thread(
                args.thread_id, keep_final_artifacts=args.keep_final
            )
            print(f"✅ Cleaned up artifacts for: {args.thread_id}")

        elif args.artifacts_action == "stats":
            stats = self.artifact_manager.get_storage_stats()

            print("Artifact Storage Statistics:")
            print(f"  Total Threads: {stats['total_threads']}")
            print(f"  Total Artifacts: {stats['total_artifacts']}")
            print(f"  Total Size: {stats['total_size_bytes']} bytes")
            print(f"  Oldest Thread: {stats['oldest_thread']}")
            print(f"  Newest Thread: {stats['newest_thread']}")
            print()

            print("By Type:")
            for artifact_type, count in stats["artifact_types"].items():
                print(f"  {artifact_type}: {count}")

    async def cmd_models(self, args):
        """Manage model connections."""
        if not self.model_router:
            await self.initialize()

        if args.models_action == "test":
            print("Testing model connections...")
            results = await self.model_router.test_connections()

            for model_name, result in results.items():
                status = result["status"]
                if status == "connected":
                    print(f"✅ {model_name}: {result['response']}")
                elif status == "failed":
                    print(f"❌ {model_name}: {result['error']}")
                else:
                    print(f"⚠️  {model_name}: {status}")

        elif args.models_action == "stats":
            stats = self.model_router.get_model_stats()

            print("Model Router Configuration:")
            print(f"  Ollama Available: {stats['ollama_available']}")
            print(f"  Claude Available: {stats['claude_available']}")
            print(f"  Ollama URL: {stats['ollama_url']}")
            print(f"  Escalation Threshold: {stats['escalation_threshold']}")
            print()

            print("Routing Config:")
            for key, value in stats["routing_config"].items():
                print(f"  {key}: {value}")


def create_parser():
    """Create argument parser."""
    parser = argparse.ArgumentParser(
        description="LangGraph Multi-Agent Workflow CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Start command
    start_parser = subparsers.add_parser("start", help="Start new workflow")
    start_parser.add_argument("feature_name", help="Feature name")
    start_parser.add_argument("--task-file", help="Task specification file")
    start_parser.add_argument("--thread-id", help="Custom thread ID")

    # Resume command
    resume_parser = subparsers.add_parser("resume", help="Resume paused workflow")
    resume_parser.add_argument("thread_id", help="Thread ID to resume")

    # Status command
    status_parser = subparsers.add_parser("status", help="Get workflow status")
    status_parser.add_argument("thread_id", help="Thread ID to check")

    # List command
    list_parser = subparsers.add_parser("list", help="List all workflows")

    # Validate command
    validate_parser = subparsers.add_parser("validate", help="Validate workflow state")
    validate_parser.add_argument("thread_id", help="Thread ID to validate")

    # Artifacts command
    artifacts_parser = subparsers.add_parser("artifacts", help="Manage artifacts")
    artifacts_parser.add_argument(
        "artifacts_action",
        choices=["list", "export", "cleanup", "stats"],
        help="Artifacts action",
    )
    artifacts_parser.add_argument("--thread-id", help="Thread ID")
    artifacts_parser.add_argument("--type", help="Artifact type filter")
    artifacts_parser.add_argument("--export-path", help="Export file path")
    artifacts_parser.add_argument(
        "--keep-final", action="store_true", help="Keep final artifacts during cleanup"
    )

    # Models command
    models_parser = subparsers.add_parser("models", help="Manage model connections")
    models_parser.add_argument(
        "models_action", choices=["test", "stats"], help="Models action"
    )

    return parser


async def main():
    """Main CLI entry point."""
    parser = create_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    # Set up logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Create CLI instance
    cli = LangGraphCLI()

    try:
        # Route to appropriate command
        command_func = getattr(cli, f"cmd_{args.command}")
        return await command_func(args)

    except KeyboardInterrupt:
        print("\n⚠️  Operation cancelled by user")
        return 1
    except Exception as e:
        print(f"❌ Command failed: {e}")
        logger.exception("Command execution failed")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
