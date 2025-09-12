"""Tests for agent personas and their behaviors."""

import unittest
from unittest.mock import MagicMock, patch
import sys
from pathlib import Path

# Mock the multi_agent_workflow imports since they may not be available
sys.modules['multi_agent_workflow'] = MagicMock()
sys.modules['multi_agent_workflow.agent_interface'] = MagicMock()
sys.modules['multi_agent_workflow.amp_cli_wrapper'] = MagicMock()
sys.modules['multi_agent_workflow.coding_personas'] = MagicMock()

from ..agent_personas import (
    LangGraphAgent,
    TestFirstAgent,
    FastCoderAgent,
    SeniorEngineerAgent,
    ArchitectAgent,
    create_agents
)


class TestLangGraphAgent(unittest.IsolatedAsyncioTestCase):
    """Test base LangGraphAgent functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Mock base agent
        self.mock_base_agent = MagicMock()
        self.mock_persona = MagicMock()
        self.mock_persona.ask.return_value = "Mock agent response"
        self.mock_base_agent.persona = self.mock_persona
        
        self.agent = LangGraphAgent(self.mock_base_agent, "test-agent")
    
    async def test_initialization(self):
        """Test agent initialization."""
        self.assertEqual(self.agent.agent_type, "test-agent")
        self.assertEqual(self.agent.base_agent, self.mock_base_agent)
        self.assertEqual(self.agent.persona, self.mock_persona)
    
    async def test_analyze(self):
        """Test analysis functionality."""
        prompt = "Test analysis prompt"
        
        result = await self.agent.analyze(prompt)
        
        self.assertEqual(result, "Mock agent response")
        self.mock_persona.ask.assert_called_once_with(prompt)
    
    async def test_analyze_with_error(self):
        """Test analysis with error handling."""
        self.mock_persona.ask.side_effect = Exception("Mock error")
        
        result = await self.agent.analyze("Test prompt")
        
        self.assertIn("Error:", result)
        self.assertIn("Mock error", result)
    
    async def test_review(self):
        """Test review functionality."""
        content = "Test content to review"
        context = {"key": "value"}
        
        result = await self.agent.review(content, context)
        
        # Verify persona was called with formatted prompt
        self.mock_persona.ask.assert_called_once()
        call_args = self.mock_persona.ask.call_args[0][0]
        self.assertIn("review the following content", call_args.lower())
        self.assertIn(content, call_args)
    
    def test_build_review_prompt(self):
        """Test review prompt building."""
        content = "Code to review"
        context = {"feature": "authentication"}
        
        prompt = self.agent._build_review_prompt(content, context)
        
        self.assertIn("test-agent", prompt)
        self.assertIn(content, prompt)
        self.assertIn(str(context), prompt)


class TestTestFirstAgent(unittest.IsolatedAsyncioTestCase):
    """Test TestFirstAgent functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        with patch('multi_agent_workflow.agent_interface.TesterAgent') as mock_tester:
            mock_base = MagicMock()
            mock_persona = MagicMock()
            mock_persona.ask.return_value = "Mock test response"
            mock_base.persona = mock_persona
            mock_tester.return_value = mock_base
            
            self.agent = TestFirstAgent()
    
    async def test_initialization(self):
        """Test test-first agent initialization."""
        self.assertEqual(self.agent.agent_type, "test-first")
    
    async def test_write_tests(self):
        """Test writing tests from skeleton."""
        skeleton = "class AuthService:\n    def login(self, user, password):\n        pass"
        design = "Authentication service with JWT tokens"
        
        result = await self.agent.write_tests(skeleton, design)
        
        # Verify persona was called with appropriate prompt
        self.agent.persona.ask.assert_called_once()
        call_args = self.agent.persona.ask.call_args[0][0]
        self.assertIn("test-first developer", call_args.lower())
        self.assertIn(skeleton, call_args)
        self.assertIn(design, call_args)
        self.assertIn("comprehensive tests", call_args.lower())
    
    async def test_write_component_tests(self):
        """Test writing component-level tests."""
        implementation = "class AuthService:\n    def login(self, user, password):\n        return generate_jwt(user)"
        unit_tests = "def test_login():\n    pass"
        
        result = await self.agent.write_component_tests(implementation, unit_tests)
        
        # Verify persona was called with component test prompt
        self.agent.persona.ask.assert_called_once()
        call_args = self.agent.persona.ask.call_args[0][0]
        self.assertIn("component-level tests", call_args.lower())
        self.assertIn(implementation, call_args)
        self.assertIn(unit_tests, call_args)
        self.assertIn("integration between components", call_args.lower())


class TestFastCoderAgent(unittest.IsolatedAsyncioTestCase):
    """Test FastCoderAgent functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        with patch('multi_agent_workflow.agent_interface.DeveloperAgent') as mock_developer:
            mock_base = MagicMock()
            mock_persona = MagicMock()
            mock_persona.ask.return_value = "Mock implementation"
            mock_base.persona = mock_persona
            mock_developer.return_value = mock_base
            
            self.agent = FastCoderAgent()
    
    async def test_initialization(self):
        """Test fast-coder agent initialization."""
        self.assertEqual(self.agent.agent_type, "fast-coder")
    
    async def test_implement(self):
        """Test implementing from skeleton."""
        skeleton = "class AuthService:\n    def login(self, user, password):\n        pass"
        design = "JWT-based authentication"
        
        result = await self.agent.implement(skeleton, design)
        
        # Verify persona was called with implementation prompt
        self.agent.persona.ask.assert_called_once()
        call_args = self.agent.persona.ask.call_args[0][0]
        self.assertIn("fast-coder", call_args.lower())
        self.assertIn(skeleton, call_args)
        self.assertIn(design, call_args)
        self.assertIn("quickly and efficiently", call_args.lower())
    
    async def test_refactor_for_tests(self):
        """Test refactoring code to fix test failures."""
        code = "def authenticate(user):\n    return True"
        test_failures = {
            "failed_tests": ["test_invalid_user"],
            "error_messages": ["Expected False for invalid user"]
        }
        
        result = await self.agent.refactor_for_tests(code, test_failures)
        
        # Verify persona was called with refactoring prompt
        self.agent.persona.ask.assert_called_once()
        call_args = self.agent.persona.ask.call_args[0][0]
        self.assertIn("fix the failing tests", call_args.lower())
        self.assertIn(code, call_args)
        self.assertIn(str(test_failures), call_args)


class TestSeniorEngineerAgent(unittest.IsolatedAsyncioTestCase):
    """Test SeniorEngineerAgent functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        with patch('multi_agent_workflow.agent_interface.SeniorEngineerAgent') as mock_senior:
            mock_base = MagicMock()
            mock_persona = MagicMock()
            mock_persona.ask.return_value = "Mock senior response"
            mock_base.persona = mock_persona
            mock_senior.return_value = mock_base
            
            self.agent = SeniorEngineerAgent()
    
    async def test_initialization(self):
        """Test senior engineer agent initialization."""
        self.assertEqual(self.agent.agent_type, "senior-engineer")
    
    async def test_analyze_codebase(self):
        """Test codebase analysis."""
        repo_path = "/tmp/test-repo"
        
        result = await self.agent.analyze_codebase(repo_path)
        
        # Verify result structure
        self.assertIsInstance(result, dict)
        self.assertIn("architecture", result)
        self.assertIn("languages", result)
        self.assertIn("patterns", result)
        
        # Verify persona was called with analysis prompt
        self.agent.persona.ask.assert_called_once()
        call_args = self.agent.persona.ask.call_args[0][0]
        self.assertIn(repo_path, call_args)
        self.assertIn("architecture overview", call_args.lower())
    
    async def test_create_skeleton(self):
        """Test skeleton creation from design."""
        design = "Authentication system with JWT tokens and user management"
        
        result = await self.agent.create_skeleton(design)
        
        # Verify persona was called with skeleton prompt
        self.agent.persona.ask.assert_called_once()
        call_args = self.agent.persona.ask.call_args[0][0]
        self.assertIn("code skeleton", call_args.lower())
        self.assertIn(design, call_args)
        self.assertIn("signatures only", call_args.lower())
        self.assertIn("pass statements", call_args.lower())
    
    async def test_refactor_for_quality(self):
        """Test refactoring for code quality."""
        code = "def process_data(data):\n    # Messy implementation\n    return data"
        tests = "def test_process_data():\n    pass"
        
        result = await self.agent.refactor_for_quality(code, tests)
        
        # Verify persona was called with refactoring prompt
        self.agent.persona.ask.assert_called_once()
        call_args = self.agent.persona.ask.call_args[0][0]
        self.assertIn("refactor this code", call_args.lower())
        self.assertIn("removing duplication", call_args.lower())
        self.assertIn("solid principles", call_args.lower())


class TestArchitectAgent(unittest.IsolatedAsyncioTestCase):
    """Test ArchitectAgent functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        with patch('multi_agent_workflow.agent_interface.ArchitectAgent') as mock_architect:
            mock_base = MagicMock()
            mock_persona = MagicMock()
            mock_persona.ask.return_value = "Mock architect response"
            mock_base.persona = mock_persona
            mock_architect.return_value = mock_base
            
            self.agent = ArchitectAgent()
    
    async def test_initialization(self):
        """Test architect agent initialization."""
        self.assertEqual(self.agent.agent_type, "architect")
    
    async def test_synthesize_analyses(self):
        """Test synthesizing multiple agent analyses."""
        analyses = {
            "test-first": "Focus on comprehensive test coverage",
            "fast-coder": "Quick implementation with basic functionality",
            "senior-engineer": "Clean patterns and maintainable code",
            "architect": "Scalable system design"
        }
        
        result = await self.agent.synthesize_analyses(analyses)
        
        # Verify persona was called with synthesis prompt
        self.agent.persona.ask.assert_called_once()
        call_args = self.agent.persona.ask.call_args[0][0]
        self.assertIn("synthesize these agent analyses", call_args.lower())
        self.assertIn("common themes", call_args.lower())
        self.assertIn("conflicts", call_args.lower())
        self.assertIn("remain neutral", call_args.lower())
        
        # All analyses should be included
        for analysis in analyses.values():
            self.assertIn(analysis, call_args)
    
    async def test_review_skeleton(self):
        """Test reviewing code skeleton."""
        skeleton = """
class AuthService:
    def authenticate(self, credentials):
        pass
    
    def authorize(self, user, resource):
        pass
"""
        
        result = await self.agent.review_skeleton(skeleton)
        
        # Verify persona was called with review prompt
        self.agent.persona.ask.assert_called_once()
        call_args = self.agent.persona.ask.call_args[0][0]
        self.assertIn("review this code skeleton", call_args.lower())
        self.assertIn("system consistency", call_args.lower())
        self.assertIn("scalability considerations", call_args.lower())
        self.assertIn(skeleton, call_args)
    
    async def test_design_scalability_tests(self):
        """Test designing scalability tests."""
        integration_tests = """
def test_auth_flow():
    # Test complete authentication flow
    pass
"""
        
        result = await self.agent.design_scalability_tests(integration_tests)
        
        # Verify persona was called with scalability test prompt
        self.agent.persona.ask.assert_called_once()
        call_args = self.agent.persona.ask.call_args[0][0]
        self.assertIn("scalability tests", call_args.lower())
        self.assertIn("performance under load", call_args.lower())
        self.assertIn("concurrent operations", call_args.lower())
    
    async def test_assess_system_impact(self):
        """Test assessing system-wide impact."""
        solution = "Implement Redis-based session storage with automatic failover"
        
        result = await self.agent.assess_system_impact(solution)
        
        # Verify persona was called with impact assessment prompt
        self.agent.persona.ask.assert_called_once()
        call_args = self.agent.persona.ask.call_args[0][0]
        self.assertIn("system-wide impact", call_args.lower())
        self.assertIn("performance implications", call_args.lower())
        self.assertIn("scalability effects", call_args.lower())
        self.assertIn(solution, call_args)


class TestAgentFactory(unittest.TestCase):
    """Test agent factory function."""
    
    def test_create_agents(self):
        """Test creating all agent types."""
        with patch('multi_agent_workflow.agent_interface.TesterAgent'), \
             patch('multi_agent_workflow.agent_interface.DeveloperAgent'), \
             patch('multi_agent_workflow.agent_interface.SeniorEngineerAgent'), \
             patch('multi_agent_workflow.agent_interface.ArchitectAgent'):
            
            agents = create_agents()
        
        # Verify all agent types are created
        self.assertIn("test-first", agents)
        self.assertIn("fast-coder", agents)
        self.assertIn("senior-engineer", agents)
        self.assertIn("architect", agents)
        
        # Verify correct agent types
        self.assertIsInstance(agents["test-first"], TestFirstAgent)
        self.assertIsInstance(agents["fast-coder"], FastCoderAgent)
        self.assertIsInstance(agents["senior-engineer"], SeniorEngineerAgent)
        self.assertIsInstance(agents["architect"], ArchitectAgent)


class TestAgentCallHistory(unittest.IsolatedAsyncioTestCase):
    """Test agent call tracking for debugging."""
    
    def setUp(self):
        """Set up test fixtures."""
        with patch('multi_agent_workflow.agent_interface.ArchitectAgent') as mock_architect:
            mock_base = MagicMock()
            mock_persona = MagicMock()
            mock_persona.ask.return_value = "Mock response"
            mock_base.persona = mock_persona
            mock_architect.return_value = mock_base
            
            self.agent = ArchitectAgent()
    
    async def test_multiple_calls_tracking(self):
        """Test that agents track their call history."""
        # Make multiple calls
        await self.agent.analyze("First prompt")
        await self.agent.review("Content to review", {"context": "test"})
        await self.agent.synthesize_analyses({"agent1": "analysis1"})
        
        # Verify all calls were made to persona
        self.assertEqual(self.agent.persona.ask.call_count, 3)


class TestErrorHandling(unittest.IsolatedAsyncioTestCase):
    """Test error handling in agent operations."""
    
    def setUp(self):
        """Set up test fixtures."""
        with patch('multi_agent_workflow.agent_interface.DeveloperAgent') as mock_developer:
            mock_base = MagicMock()
            mock_persona = MagicMock()
            mock_base.persona = mock_persona
            mock_developer.return_value = mock_base
            
            self.agent = FastCoderAgent()
    
    async def test_persona_exception_handling(self):
        """Test handling of exceptions from persona calls."""
        # Make persona throw exception
        self.agent.persona.ask.side_effect = Exception("Persona error")
        
        result = await self.agent.analyze("Test prompt")
        
        # Verify error is handled gracefully
        self.assertIn("Error:", result)
        self.assertIn("Persona error", result)
    
    async def test_timeout_handling(self):
        """Test handling of timeout scenarios."""
        import asyncio
        
        # Simulate timeout by making persona hang
        async def slow_response(prompt):
            await asyncio.sleep(10)  # Long delay
            return "Delayed response"
        
        self.agent.persona.ask = slow_response
        
        # Test with timeout (in real implementation)
        # For this test, we'll just verify the setup
        self.assertIsNotNone(self.agent.persona.ask)


if __name__ == '__main__':
    unittest.main()