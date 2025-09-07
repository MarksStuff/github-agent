#!/usr/bin/env python3
"""
CLI script for running the Enhanced Multi-Agent Workflow.

This script provides a user-friendly interface for running the comprehensive
workflow that includes skeleton creation, test development, implementation,
and PR review cycles.
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Add parent directory for imports
sys.path.append(str(Path(__file__).parent.parent))

from enhanced_workflow_orchestrator import EnhancedWorkflowOrchestrator
from task_context import FeatureSpec
from logging_config import setup_logging


def setup_cli_logging(verbose: bool = False):
    """Setup logging for CLI usage."""
    level = logging.DEBUG if verbose else logging.INFO
    
    # Setup basic logging
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('.workflow/workflow.log')
        ]
    )
    
    # Create workflow log directory
    Path('.workflow').mkdir(exist_ok=True)


async def run_new_workflow(args):
    """Run a new workflow from scratch."""
    print(f"🚀 Starting Enhanced Multi-Agent Workflow")
    print(f"Repository: {args.repo_name}")
    print(f"Feature: {args.feature_name}")
    print(f"Description: {args.description}")
    print()
    
    orchestrator = EnhancedWorkflowOrchestrator(args.repo_name, args.repo_path)
    feature_spec = FeatureSpec(args.feature_name, args.description)
    
    try:
        result = await orchestrator.run_enhanced_workflow(feature_spec)
        
        if result.get("paused"):
            print("\n✋ Workflow paused for review")
            print(f"📝 PR created: #{result.get('pr_number')}")
            print("\n📋 Next steps:")
            print("1. Review the PR on GitHub")
            print("2. Add comments and feedback")
            print("3. Run: python run_enhanced_workflow.py --resume")
            
        else:
            print("\n✅ Workflow completed successfully!")
            print(f"Final status: {result.get('status')}")
            
    except Exception as e:
        print(f"\n❌ Workflow failed: {e}")
        sys.exit(1)
    finally:
        orchestrator.cleanup()


async def resume_workflow(args):
    """Resume a paused workflow."""
    print("🔄 Resuming Enhanced Multi-Agent Workflow")
    print(f"Repository: {args.repo_name}")
    print()
    
    orchestrator = EnhancedWorkflowOrchestrator(args.repo_name, args.repo_path)
    feature_spec = FeatureSpec("resumed_workflow", "Resuming paused workflow")
    
    try:
        result = await orchestrator.resume_workflow(feature_spec)
        
        if result.get("paused"):
            print("\n✋ Workflow paused again for review")
            print("\n📋 Next steps:")
            print("1. Review the updated PR on GitHub")
            print("2. Add more comments if needed")
            print("3. Run: python run_enhanced_workflow.py --resume (to continue)")
            
        elif result.get("status") == "completed":
            print("\n🎉 Workflow completed! No more PR comments to address.")
            
        else:
            print(f"\n✅ Workflow step completed: {result}")
            
    except Exception as e:
        print(f"\n❌ Resume failed: {e}")
        sys.exit(1)
    finally:
        orchestrator.cleanup()


def show_workflow_status(args):
    """Show current workflow status."""
    state_file = Path(args.repo_path) / ".workflow" / "workflow_state.json"
    
    if not state_file.exists():
        print("❌ No active workflow found")
        return
    
    try:
        import json
        with open(state_file, 'r') as f:
            state = json.load(f)
        
        print("📊 Current Workflow Status")
        print(f"Phase: {state.get('current_phase')}")
        print(f"Paused: {state.get('is_paused')}")
        print(f"PR Number: {state.get('pr_number', 'Not created')}")
        print(f"Last Updated: {state.get('timestamp')}")
        
        if state.get('current_phase') == 'pr_review' and state.get('is_paused'):
            print("\n💡 Workflow is waiting for PR review")
            print("Run with --resume to continue after reviewing PR")
            
    except Exception as e:
        print(f"❌ Failed to read workflow status: {e}")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Enhanced Multi-Agent Workflow for software development",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start new workflow
  python run_enhanced_workflow.py my-org/my-repo . "User Authentication" "Add JWT-based user auth"
  
  # Resume paused workflow
  python run_enhanced_workflow.py my-org/my-repo . --resume
  
  # Check workflow status
  python run_enhanced_workflow.py my-org/my-repo . --status
  
Workflow Phases:
  1. Design Analysis & Architecture Skeleton
  2. Test Creation & Review
  3. Implementation & Test Validation
  4. PR Review & Response Cycles
        """
    )
    
    # Required arguments
    parser.add_argument("repo_name", help="GitHub repository name (org/repo)")
    parser.add_argument("repo_path", help="Local path to repository")
    
    # Feature specification (for new workflows)
    parser.add_argument("feature_name", nargs='?', help="Name of feature to implement")
    parser.add_argument("description", nargs='?', help="Detailed feature description")
    
    # Operation modes
    parser.add_argument("--resume", action="store_true", help="Resume paused workflow")
    parser.add_argument("--status", action="store_true", help="Show workflow status")
    
    # Options
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")
    parser.add_argument("--log-file", help="Custom log file path")
    
    args = parser.parse_args()
    
    # Setup logging
    setup_cli_logging(args.verbose)
    
    # Validate arguments
    if args.resume and args.status:
        print("❌ Cannot use --resume and --status together")
        sys.exit(1)
    
    if not args.resume and not args.status and not args.feature_name:
        print("❌ Feature name required for new workflow")
        print("Use --help for usage information")
        sys.exit(1)
    
    # Execute based on mode
    if args.status:
        show_workflow_status(args)
    elif args.resume:
        asyncio.run(resume_workflow(args))
    else:
        # Default feature description if not provided
        if not args.description:
            args.description = f"Implement {args.feature_name} feature"
        
        asyncio.run(run_new_workflow(args))


if __name__ == "__main__":
    main()