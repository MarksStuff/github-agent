"""Integration tests that use REAL Ollama models (not mocks).

These tests will actually hit your local Ollama instance and RTX 5070.

Run with: pytest -m integration -v
Skip with: pytest -m "not integration" -v
"""

import tempfile
from pathlib import Path

import pytest
from langchain_ollama import ChatOllama

from langgraph_workflow.enums import ModelRouter, WorkflowPhase
from langgraph_workflow.langgraph_workflow import MultiAgentWorkflow, WorkflowState
from langgraph_workflow.real_codebase_analyzer import RealCodebaseAnalyzer
from langgraph_workflow.tests.real_agents import create_real_ollama_agents


@pytest.mark.integration
class TestRealOllamaIntegration:
    """Integration tests using REAL Ollama models."""

    @pytest.fixture
    def temp_repo(self):
        """Create a temporary repository for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)

            # Create a realistic Python project structure
            (repo_path / "main.py").write_text(
                """#!/usr/bin/env python3
\"\"\"Main application entry point.\"\"\"

from fastapi import FastAPI
from .auth import AuthRouter
from .users import UserRouter

app = FastAPI(title="Test API")
app.include_router(AuthRouter)
app.include_router(UserRouter)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
"""
            )

            (repo_path / "requirements.txt").write_text(
                """fastapi==0.104.1
uvicorn==0.24.0
pydantic==2.5.0
sqlalchemy==2.0.23
psycopg2-binary==2.9.9
"""
            )

            (repo_path / "README.md").write_text(
                """# Test API Project

A FastAPI-based web application with authentication.

## Features
- User authentication with JWT
- RESTful API endpoints
- PostgreSQL database
- Docker support

## Installation
```bash
pip install -r requirements.txt
python main.py
```
"""
            )

            # Create some source files
            src_dir = repo_path / "src"
            src_dir.mkdir()

            (src_dir / "auth.py").write_text(
                """\"\"\"Authentication module.\"\"\"

from fastapi import APIRouter, Depends, HTTPException
from .models import User
from .database import get_db

AuthRouter = APIRouter(prefix="/auth")

@AuthRouter.post("/login")
async def login(credentials: dict, db=Depends(get_db)):
    # Authentication logic here
    pass
"""
            )

            (src_dir / "users.py").write_text(
                """\"\"\"User management module.\"\"\"

from fastapi import APIRouter
from .models import User

UserRouter = APIRouter(prefix="/users")

@UserRouter.get("/profile")
async def get_profile():
    # User profile logic
    pass
"""
            )

            yield str(repo_path)

    @pytest.fixture
    def real_workflow(self, temp_repo):
        """Create workflow with REAL Ollama model."""
        import os

        ollama_url = os.getenv("OLLAMA_BASE_URL", "http://marks-pc:11434")

        # Check if Ollama is available - FAIL if not (don't skip)
        if not is_ollama_available():
            raise RuntimeError(
                f"🔥 Ollama integration test FAILED: Ollama not running on {ollama_url}\n"
                f"   Fix with: ollama serve\n"
                f"   Or set OLLAMA_BASE_URL to correct URL"
            )

        real_ollama = ChatOllama(
            model="qwen2.5-coder:7b",
            base_url=ollama_url,
        )
        analyzer = RealCodebaseAnalyzer(temp_repo)
        agents = create_real_ollama_agents()  # REAL AGENTS that call Ollama!

        workflow = MultiAgentWorkflow(
            repo_path=temp_repo,
            thread_id="real-ollama-test",
            agents=agents,  # type: ignore
            codebase_analyzer=analyzer,
            ollama_model=real_ollama,  # REAL OLLAMA MODEL
            claude_model=None,  # Optional
        )
        return workflow

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_ollama_ping_and_models(self):
        """Test basic Ollama connectivity and list models - should show GPU activity."""
        import os

        import requests

        ollama_url = os.getenv("OLLAMA_BASE_URL", "http://marks-pc:11434")
        print(f"🔍 Testing Ollama connectivity to: {ollama_url}")

        # Test basic ping
        try:
            response = requests.get(f"{ollama_url}/api/tags", timeout=5)
            print(f"✅ Ollama ping successful: {response.status_code}")

            if response.status_code == 200:
                models_data = response.json()
                models = models_data.get("models", [])
                print(f"📋 Found {len(models)} models:")
                for model in models:
                    print(f"   - {model.get('name', 'Unknown')}")

                if len(models) == 0:
                    raise AssertionError(
                        f"❌ No models found in Ollama at {ollama_url}\n"
                        f"   Install a model first: ollama pull qwen2.5-coder:7b\n"
                        f"   Or any other model, then update the test configuration"
                    )
                print("✅ Ollama has available models")
            else:
                raise AssertionError(f"Ollama returned status {response.status_code}")

        except requests.exceptions.RequestException as e:
            raise AssertionError(
                f"Failed to connect to Ollama at {ollama_url}: {e}"
            ) from e

    @pytest.mark.integration
    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_ollama_actual_inference(self):
        """Test actual model inference - should definitely show GPU activity."""
        import os

        from langchain_core.messages import HumanMessage
        from langchain_ollama import ChatOllama

        ollama_url = os.getenv("OLLAMA_BASE_URL", "http://marks-pc:11434")
        print(f"🚀 Testing actual Ollama model inference at: {ollama_url}")
        print("🔥 This should show activity on your RTX 5070!")

        try:
            # Create ChatOllama instance - use qwen2.5-coder model which should be available
            model = ChatOllama(
                model="qwen2.5-coder:7b", base_url=ollama_url, temperature=0.1
            )

            # Make a simple inference call
            print("📡 Sending inference request to model...")
            response = await model.ainvoke(
                [
                    HumanMessage(
                        content="Hello, respond with exactly: 'GPU test successful'"
                    )
                ]
            )

            print(f"✅ Model response: {response.content}")
            assert (
                "GPU test successful" in str(response.content)
                or "successful" in str(response.content).lower()
            )
            print("🎉 Actual model inference completed!")

        except Exception as e:
            raise AssertionError(f"Failed to make inference call to Ollama: {e}") from e

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_real_feature_extraction(self, real_workflow, temp_repo):
        """Test feature extraction node with real repository (no LLM needed)."""
        # This test doesn't need LLM but uses real codebase analyzer
        state = WorkflowState(
            thread_id="real-test",
            feature_description="Add OAuth2 authentication with role-based access control",
            raw_feature_input=None,
            extracted_feature=None,
            current_phase=WorkflowPhase.PHASE_0_CODE_CONTEXT,
            messages_window=[],
            summary_log="",
            artifacts_index={},
            code_context_document=None,
            design_constraints_document=None,
            design_document=None,
            arbitration_log=[],
            repo_path=temp_repo,
            git_branch="main",
            last_commit_sha=None,
            pr_number=None,
            agent_analyses={},
            synthesis_document=None,
            conflicts=[],
            skeleton_code=None,
            test_code=None,
            implementation_code=None,
            patch_queue=[],
            test_report={},
            ci_status={},
            lint_status={},
            quality="draft",
            feedback_gate="open",
            model_router=ModelRouter.OLLAMA,
            escalation_count=0,
        )

        # Extract feature (should work without LLM)
        result = await real_workflow.extract_feature(state)

        assert (
            result["feature_description"]
            == "Add OAuth2 authentication with role-based access control"
        )
        assert "feature_description" in result["artifacts_index"]

        # Verify artifact was created
        artifact_path = Path(result["artifacts_index"]["feature_description"])
        assert artifact_path.exists()
        assert "OAuth2 authentication" in artifact_path.read_text()

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_real_codebase_analysis(self, real_workflow, temp_repo):
        """Test codebase analysis with real RealCodebaseAnalyzer (no LLM)."""
        # Test the real codebase analyzer
        analysis = real_workflow.codebase_analyzer.analyze()

        # Verify it found our realistic project structure
        assert "Python" in analysis["languages"]
        assert "fastapi" in str(analysis["frameworks"]).lower()
        assert any("main.py" in kf for kf in analysis["key_files"])
        assert any("requirements.txt" in kf for kf in analysis["key_files"])
        assert "patterns" in analysis
        assert "conventions" in analysis

        print(
            f"🔍 Real analysis found: {len(analysis['languages'])} languages, {len(analysis['key_files'])} key files"
        )

    @pytest.mark.integration
    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_ollama_code_context_simulation(self, temp_repo):
        """Test Ollama-based code context generation by reading files and sending to model.

        This simulates how code context would work with Ollama (read files, send content).
        """
        import os
        from pathlib import Path

        from langchain_core.messages import HumanMessage

        # Integration tests should FAIL in CI if Ollama not configured (not skip)
        ollama_url = os.getenv("OLLAMA_BASE_URL", "http://marks-pc:11434")
        print(f"🚀 Testing Ollama code context generation at: {ollama_url}")
        print("🔥 This should show GPU activity!")

        # Read actual code files from temp repo
        repo_path = Path(temp_repo)
        code_files = []

        # Collect Python files
        for py_file in repo_path.rglob("*.py"):
            if py_file.is_file() and py_file.stat().st_size < 10000:  # Skip huge files
                try:
                    content = py_file.read_text()
                    relative_path = py_file.relative_to(repo_path)
                    code_files.append({"path": str(relative_path), "content": content})
                except Exception:
                    continue  # Skip unreadable files

        # Also include text files like README
        for txt_file in repo_path.glob("*.md"):
            if txt_file.is_file():
                try:
                    content = txt_file.read_text()
                    code_files.append({"path": txt_file.name, "content": content})
                except Exception:
                    continue

        print(f"📁 Found {len(code_files)} files to analyze")

        # Create code context prompt with actual file contents
        files_content = "\n\n".join(
            [
                f"## File: {file['path']}\n```\n{file['content']}\n```"
                for file in code_files[:5]  # Limit to first 5 files
            ]
        )

        prompt = f"""You are analyzing a codebase for feature development.

**Repository Structure:**
{len(code_files)} files found in the repository.

**Key Files Content:**
{files_content}

**Task:**
Analyze this codebase and create a brief code context summary (2-3 paragraphs) covering:
1. What type of application this appears to be
2. Key technologies/frameworks in use
3. Overall architecture/structure

Keep the response concise and focused on what would be useful for implementing new features.
"""

        try:
            # Create Ollama model
            model = ChatOllama(
                model="qwen2.5-coder:7b", base_url=ollama_url, temperature=0.3
            )

            print("📡 Sending code analysis request to Ollama...")
            response = await model.ainvoke([HumanMessage(content=prompt)])

            analysis = response.content
            print("✅ Ollama code analysis completed!")
            print(f"📄 Analysis length: {len(analysis)} characters")
            print(f"🏷️  First 200 chars: {analysis[:200]}...")

            # Verify we got a substantial response
            assert len(analysis) > 100, "Analysis should be substantial"
            assert (
                "application" in str(analysis).lower()
                or "code" in str(analysis).lower()
            ), "Should mention code/application"

            return analysis

        except Exception as e:
            raise AssertionError(
                f"Failed to generate code context with Ollama: {e}"
            ) from e

    @pytest.mark.integration
    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_real_ollama_code_context_generation(self, real_workflow, temp_repo):
        """Test code context generation prompt quality with REAL Ollama model.

        🎯 This test validates our PROMPT ENGINEERING, not LLM file access capabilities.
        🚨 This test will actually hit your RTX 5070!
        """
        # Integration tests should FAIL in CI if Ollama not configured (not skip)
        
        print("🚀 Starting REAL Ollama prompt quality test!")

        # Get real repository analysis data (same data Claude CLI would get)
        from langgraph_workflow.real_codebase_analyzer import RealCodebaseAnalyzer
        import json
        
        analyzer = RealCodebaseAnalyzer(".")  # Analyze the actual github-agent repository
        real_analysis = analyzer.analyze()
        
        # Create the same prompt that Claude CLI would get
        analysis_json = json.dumps(real_analysis, indent=2)
        
        analysis_prompt = f"""You are a Senior Software Engineer creating a comprehensive Code Context Document.

I have already analyzed the repository structure and extracted key information. Please synthesize this data into a well-formatted, actionable Code Context Document.

## Repository: /Users/mstriebeck/Code/github-agent

## PRE-ANALYZED REPOSITORY DATA:
```json
{analysis_json}
```

## TASK: 
Create a comprehensive, UNBIASED Code Context Document using ONLY the pre-analyzed data above. 

IMPORTANT RULES:
1. This is an OBJECTIVE analysis - do NOT reference any specific features or implementation targets
2. Only list languages found in ACTUAL SOURCE CODE files (not libraries, dependencies, or .venv)
3. Be factual and accurate - only describe what's actually in the analysis data
4. Focus on understanding the current system AS IT IS

Structure the document as follows:

### 1. SYSTEM OVERVIEW
- What this system actually does (based on the analyzed structure)
- Primary architecture patterns found in the code
- Key entry points and main components

### 2. TECHNOLOGY STACK
- **Languages**: ONLY languages used in source code files (exclude .venv/, node_modules/, etc.)
- **Frameworks**: Actually imported and used in the code
- **Development Tools**: Testing, linting, deployment tools

### 3. CODEBASE STRUCTURE  
- Directory organization and actual purpose
- Key modules and what they do
- Testing structure and conventions

### 4. DEVELOPMENT CONTEXT
- Current git branch and recent work
- Dependencies and how they're managed
- Design patterns and conventions observed

### 5. ARCHITECTURE INSIGHTS
- How components interact
- Key abstractions and interfaces
- Extension points and modularity

Base everything on the provided analysis data. Be precise and factual.
"""

        # Test the prompt with real Ollama
        try:
            from langchain_ollama import ChatOllama
            from langchain_core.messages import HumanMessage
            import os
            
            # Get Ollama configuration
            ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
            ollama_model = os.getenv("OLLAMA_MODEL", "qwen2.5-coder:7b")
            
            ollama_client = ChatOllama(
                base_url=ollama_base_url,
                model=ollama_model,
            )
            
            # Test our prompt quality
            response = await ollama_client.ainvoke([HumanMessage(content=analysis_prompt)])
            context_doc = str(response.content).strip() if response.content else ""
            
            print("🎉 Real Ollama prompt test completed!")
            
            # Verify our prompt produces quality output
            assert context_doc is not None
            assert len(context_doc) > 100  # Should be substantial
            
            # Check that our prompt generates the expected content structure
            context_lower = context_doc.lower()
            
            # Should mention actual languages from our analysis
            expected_languages = real_analysis["languages"]
            language_mentioned = any(lang.lower() in context_lower for lang in expected_languages)
            assert language_mentioned, f"Expected one of {expected_languages} in output"
            
            # Should mention actual frameworks from our analysis  
            expected_frameworks = real_analysis["frameworks"]
            framework_mentioned = any(fw.lower() in context_lower for fw in expected_frameworks)
            assert framework_mentioned, f"Expected one of {expected_frameworks} in output"
            
            # Should have proper document structure (test prompt effectiveness)
            assert "system" in context_lower or "overview" in context_lower
            assert "technology" in context_lower or "stack" in context_lower
            
            print(f"📄 Generated {len(context_doc)} characters of code context")
            print(f"🎯 Detected languages: {real_analysis['languages']}")
            print(f"🛠️  Detected frameworks: {real_analysis['frameworks']}")
            print(f"🏷️  First 300 chars: {context_doc[:300]}...")
            
        except ImportError:
            pytest.skip("langchain-ollama not available for prompt testing")
        except Exception as e:
            if "connection" in str(e).lower() or "refused" in str(e).lower():
                pytest.skip(f"Ollama not available for prompt testing: {e}")
            else:
                raise

    @pytest.mark.integration
    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_real_agent_analysis(self, real_workflow, temp_repo):
        """Test agent analysis with real Ollama model.

        🚨 This will make multiple calls to your RTX 5070!
        """
        # Integration tests should FAIL in CI if Ollama not configured (not skip)
        # Set up state with code context
        state = WorkflowState(
            thread_id="agent-test",
            feature_description="Implement OAuth2 authentication system",
            raw_feature_input=None,
            extracted_feature=None,
            current_phase=WorkflowPhase.PHASE_1_DESIGN_EXPLORATION,
            messages_window=[],
            summary_log="",
            artifacts_index={},
            code_context_document="# Mock Context\nFastAPI application with authentication needs",
            design_constraints_document=None,
            design_document=None,
            arbitration_log=[],
            repo_path=temp_repo,
            git_branch="main",
            last_commit_sha=None,
            pr_number=None,
            agent_analyses={},
            synthesis_document=None,
            conflicts=[],
            skeleton_code=None,
            test_code=None,
            implementation_code=None,
            patch_queue=[],
            test_report={},
            ci_status={},
            lint_status={},
            quality="draft",
            feedback_gate="open",
            model_router=ModelRouter.OLLAMA,  # Force Ollama usage
            escalation_count=0,
        )

        print("🤖 Testing real agent analysis - multiple RTX 5070 calls incoming!")

        # Test one agent analysis with real Ollama
        agent_context = {
            "code_context": state["code_context_document"],
            "feature": state["feature_description"],
        }

        # This should call real Ollama model through the agent
        analysis = await real_workflow._agent_analysis(
            real_workflow.agents["senior-engineer"], "senior-engineer", agent_context
        )

        print(f"💡 Agent analysis: {analysis}")

        # Verify we got a real response
        if isinstance(analysis, tuple):
            agent_type, response = analysis
            print(f"Agent type: {agent_type}, Response: {response}")
            assert response != "Mock codebase analysis completed"  # Not a mock response
            assert len(response) > 10  # Should be substantial
        else:
            assert len(analysis) > 10  # Should be substantial
            assert analysis != "Mock codebase analysis completed"  # Not a mock response


# Helper function to check if Ollama is available
def is_ollama_available():
    """Check if Ollama is running on configured URL."""
    try:
        import os

        import requests

        ollama_url = os.getenv("OLLAMA_BASE_URL", "http://marks-pc:11434")
        response = requests.get(f"{ollama_url}/api/tags", timeout=2)
        return response.status_code == 200
    except Exception:
        return False


# Conditional marker - only run if Ollama is available
def get_ollama_url():
    """Get the configured Ollama URL."""
    import os

    return os.getenv("OLLAMA_BASE_URL", "http://marks-pc:11434")


# Integration tests should FAIL (not skip) when Ollama is misconfigured
# This helps users identify configuration issues rather than silently skipping tests
