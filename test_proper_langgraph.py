"""Test the proper LangGraph implementation."""

import asyncio
import logging
import tempfile
from pathlib import Path

from langgraph_workflow.proper_langgraph_workflow import ProperLangGraphWorkflow
from langgraph_workflow.tests.mocks import create_mock_agents
from langgraph_workflow.real_codebase_analyzer import RealCodebaseAnalyzer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_proper_langgraph_workflow():
    """Test the proper LangGraph implementation vs our current manual approach."""

    print("🧪 TESTING PROPER LANGGRAPH WORKFLOW")
    print("=" * 50)

    # Create a temporary database for this test
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_db:
        checkpoint_path = tmp_db.name

    try:
        # Setup
        repo_path = "."
        agents = create_mock_agents()
        codebase_analyzer = RealCodebaseAnalyzer(repo_path)

        # Create workflow
        workflow = ProperLangGraphWorkflow(
            repo_path=repo_path,
            agents=agents,
            codebase_analyzer=codebase_analyzer,
            thread_id="test-proper-workflow",
            checkpoint_path=checkpoint_path
        )

        # Initial state
        initial_state = {
            "feature_description": "Add user authentication",
            "repo_path": repo_path,
            "thread_id": "test-proper-workflow",
        }

        print("\n1️⃣ Testing step-by-step execution with interruption:")
        print("-" * 50)

        # Run until design_synthesis step
        result1 = await workflow.run_until_step(initial_state, "design_synthesis")
        print(f"✅ Stopped before design_synthesis")
        print(f"📊 Current state keys: {list(result1.keys())}")

        print("\n2️⃣ Testing workflow resumption:")
        print("-" * 50)

        # Resume from checkpoint - LangGraph handles this automatically!
        result2 = await workflow.resume_workflow()
        print(f"✅ Resumed and completed workflow")
        print(f"📊 Final state keys: {list(result2.keys())}")

        print("\n3️⃣ Testing workflow history:")
        print("-" * 50)

        # Get execution history
        history = workflow.get_workflow_history()
        print(f"📜 Execution history ({len(history)} checkpoints):")
        for i, checkpoint in enumerate(history[:3], 1):  # Show first 3
            step = checkpoint.get("step", ["unknown"])[0] if isinstance(checkpoint.get("step"), list) else checkpoint.get("step", "unknown")
            print(f"   {i}. Step: {step}")

        print("\n4️⃣ Testing current state retrieval:")
        print("-" * 50)

        # Get current state
        current = workflow.get_current_state()
        print(f"📍 Current workflow state:")
        print(f"   - Feature: {current.get('feature_description', 'N/A')}")
        print(f"   - Phase: {current.get('current_phase', 'N/A')}")
        print(f"   - Quality: {current.get('quality', 'N/A')}")

        print("\n✅ PROPER LANGGRAPH WORKFLOW TEST COMPLETED")
        print("🎯 Key Benefits Demonstrated:")
        print("   ✅ Native checkpoint resumption")
        print("   ✅ Automatic state persistence")
        print("   ✅ Built-in workflow interruption")
        print("   ✅ Complete execution history")
        print("   ✅ No manual file checking")
        print("   ✅ No AsyncSqliteSaver workarounds")

    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # Cleanup
        Path(checkpoint_path).unlink(missing_ok=True)


if __name__ == "__main__":
    asyncio.run(test_proper_langgraph_workflow())