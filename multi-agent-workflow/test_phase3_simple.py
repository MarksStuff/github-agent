#!/usr/bin/env python3
"""Quick test of Phase 3 with simple design."""

import asyncio
import sys
from pathlib import Path

# Add the project paths
sys.path.append(str(Path(__file__).parent / "multi-agent-workflow"))
sys.path.append(str(Path(__file__).parent))

from task_context import CodebaseState, FeatureSpec, TaskContext
from workflow_orchestrator import WorkflowOrchestrator


async def test_simple_implementation():
    """Test implementation with a simple design."""

    # Create orchestrator
    orchestrator = WorkflowOrchestrator("test-repo", str(Path.cwd()))

    # Create simple context
    context = TaskContext(
        FeatureSpec("Simple Calculator", "Test implementation", [], [], []),
        CodebaseState({}, {}, {}, {}),
        str(Path.cwd()),
    )
    context.set_pr_number(999)  # Test PR number

    # Simple task
    task = {
        "title": "Create Calculator",
        "description": "Create a simple calculator class with basic operations",
        "requirements": ["Support addition and subtraction", "Include error handling"],
        "files_to_create": ["calculator.py", "test_calculator.py"],
    }

    print("🧪 Testing Phase 3 implementation with simple task...")

    try:
        # Test the implementation cycle
        result = await orchestrator._execute_implementation_cycle(context, task, 1)

        print(f"✅ Task: {result['task']}")
        print(f"✅ Status: {result['status']}")
        print(f"✅ Files created: {len(result['files_created'])}")
        print(f"✅ Implementation length: {len(result['implementation'])}")

        return result

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return None


if __name__ == "__main__":
    result = asyncio.run(test_simple_implementation())
    if result and result["status"] == "completed":
        print("🎉 Phase 3 implementation system is working!")
    else:
        print("💥 Phase 3 implementation system needs debugging")
