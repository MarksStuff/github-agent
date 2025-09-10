"""Model routing logic for hybrid Ollama/Claude execution."""

import asyncio
import logging
import os
from typing import Optional

from langchain_anthropic import ChatAnthropic
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage

from langgraph_workflow.state import WorkflowState, AgentType, should_escalate

logger = logging.getLogger(__name__)

class ModelRouter:
    """Routes tasks to appropriate models based on complexity and agent type."""
    
    def __init__(self, ollama_host: Optional[str] = None):
        """Initialize model router with remote Ollama support.
        
        Args:
            ollama_host: Remote Ollama URL (e.g., "http://windows-machine:11434")
        """
        # Support remote Ollama instance
        ollama_url = ollama_host or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        
        # Initialize clients
        try:
            self.ollama_client = ChatOllama(
                base_url=ollama_url,
                model="qwen2.5-coder:7b",
                temperature=0.1
            )
            logger.info(f"Initialized Ollama client at {ollama_url}")
        except Exception as e:
            logger.error(f"Failed to initialize Ollama client: {e}")
            self.ollama_client = None
        
        # Initialize Claude client
        anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        if anthropic_key:
            self.claude_client = ChatAnthropic(
                anthropic_api_key=anthropic_key,
                model="claude-3-opus-20240229",
                temperature=0.1
            )
            logger.info("Initialized Claude client")
        else:
            logger.warning("ANTHROPIC_API_KEY not set, Claude unavailable")
            self.claude_client = None
        
        # Model routing configuration
        self.escalation_threshold = int(os.getenv("MODEL_ROUTER_ESCALATION_THRESHOLD", "2"))
        self.diff_size_limit = int(os.getenv("MODEL_ROUTER_DIFF_SIZE_LIMIT", "300"))
        self.files_limit = int(os.getenv("MODEL_ROUTER_FILES_LIMIT", "10"))
        
    def should_escalate_to_claude(self, state: WorkflowState, agent_type: AgentType) -> bool:
        """Determine if task should escalate to Claude.
        
        Args:
            state: Current workflow state
            agent_type: Type of agent making the request
            
        Returns:
            True if should use Claude, False for local Ollama
        """
        # Force Claude if explicitly requested
        if state.get("escalation_needed", False):
            return True
        
        # Always use Claude for certain phases
        finalization_phases = ["finalization", "pr_review"]
        if state.get("current_phase") in finalization_phases:
            return True
        
        # Escalate based on retry count
        if state.get("retry_count", 0) >= self.escalation_threshold:
            return True
        
        # Escalate for complex tasks
        design_conflicts = len(state.get("design_conflicts", []))
        if design_conflicts > 5:
            return True
        
        # Escalate for Senior Engineer and Architect on complex analysis
        complex_agents = [AgentType.SENIOR_ENGINEER, AgentType.ARCHITECT]
        if agent_type in complex_agents and state.get("current_phase") == "analysis":
            return True
        
        # Check diff size and file count (if available)
        implementation_files = len(state.get("implementation_code", {}))
        if implementation_files > self.files_limit:
            return True
        
        # Default to local for Developer and Tester
        return False
    
    async def call_model(self, prompt: str, state: WorkflowState, agent_type: AgentType) -> str:
        """Route to appropriate model based on agent and state.
        
        Args:
            prompt: The prompt to send
            state: Current workflow state
            agent_type: Type of agent making the request
            
        Returns:
            Model response text
        """
        use_claude = self.should_escalate_to_claude(state, agent_type)
        
        # Log routing decision
        model_name = "Claude" if use_claude else "Ollama"
        logger.info(f"Routing {agent_type.value} request to {model_name}")
        
        try:
            if use_claude and self.claude_client:
                return await self._call_claude(prompt, state, agent_type)
            elif self.ollama_client:
                return await self._call_ollama(prompt, state, agent_type)
            else:
                # Fallback
                logger.warning("No available models, using fallback")
                return self._fallback_response(prompt, agent_type)
                
        except Exception as e:
            logger.error(f"Model call failed: {e}")
            # Try fallback to other model
            if use_claude and self.ollama_client:
                logger.info("Claude failed, falling back to Ollama")
                return await self._call_ollama(prompt, state, agent_type)
            elif not use_claude and self.claude_client:
                logger.info("Ollama failed, escalating to Claude")
                return await self._call_claude(prompt, state, agent_type)
            else:
                raise e
    
    async def _call_claude(self, prompt: str, state: WorkflowState, agent_type: AgentType) -> str:
        """Call Claude API with retries and error handling."""
        max_retries = 3
        base_delay = 1
        
        for attempt in range(max_retries):
            try:
                # Add context for Claude
                contextual_prompt = self._add_context_for_claude(prompt, state, agent_type)
                
                message = HumanMessage(content=contextual_prompt)
                response = await self.claude_client.ainvoke([message])
                
                # Extract content from response
                if hasattr(response, 'content'):
                    return response.content
                elif isinstance(response, str):
                    return response
                else:
                    return str(response)
                    
            except Exception as e:
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    logger.warning(f"Claude attempt {attempt + 1} failed: {e}, retrying in {delay}s")
                    await asyncio.sleep(delay)
                else:
                    raise e
    
    async def _call_ollama(self, prompt: str, state: WorkflowState, agent_type: AgentType) -> str:
        """Call Ollama with local model."""
        # Add context for local model
        contextual_prompt = self._add_context_for_ollama(prompt, state, agent_type)
        
        message = HumanMessage(content=contextual_prompt)
        response = await self.ollama_client.ainvoke([message])
        
        # Extract content from response
        if hasattr(response, 'content'):
            return response.content
        elif isinstance(response, str):
            return response
        else:
            return str(response)
    
    def _add_context_for_claude(self, prompt: str, state: WorkflowState, agent_type: AgentType) -> str:
        """Add rich context for Claude's better reasoning."""
        context_parts = [
            f"You are a {agent_type.value.replace('_', ' ').title()} in a multi-agent software development workflow.",
            f"Current Phase: {state.get('current_phase', 'unknown')}",
            f"Feature: {state.get('feature_name', 'Unknown')}",
            f"Repository: {state.get('repo_name', 'Unknown')}",
        ]
        
        # Add relevant context based on phase
        if state.get("retry_count", 0) > 0:
            context_parts.append(f"This is retry attempt #{state['retry_count']} - previous approaches failed.")
        
        if state.get("design_conflicts"):
            context_parts.append(f"There are {len(state['design_conflicts'])} design conflicts to resolve.")
        
        # Add recent messages for context
        recent_messages = state.get("messages_window", [])[-3:]
        if recent_messages:
            context_parts.append("Recent workflow context:")
            for msg in recent_messages:
                role = msg.get("role", "system")
                content = msg.get("content", "")[:100]
                context_parts.append(f"  {role}: {content}")
        
        context_header = "\n".join(context_parts)
        
        return f"""{context_header}

{prompt}

Please provide a thorough, high-quality response that addresses the specific requirements above."""
    
    def _add_context_for_ollama(self, prompt: str, state: WorkflowState, agent_type: AgentType) -> str:
        """Add minimal context for local Ollama model."""
        return f"""You are a {agent_type.value.replace('_', ' ').title()} working on: {state.get('feature_name', 'a software feature')}.

{prompt}

Provide a concise, practical response focused on the task requirements."""
    
    def _fallback_response(self, prompt: str, agent_type: AgentType) -> str:
        """Provide a fallback response when no models are available."""
        logger.warning("Using fallback response - no models available")
        
        fallback_responses = {
            AgentType.ARCHITECT: "Architecture analysis pending - model unavailable. Please review manually.",
            AgentType.DEVELOPER: "Implementation analysis pending - model unavailable. Please implement manually.",
            AgentType.SENIOR_ENGINEER: "Code quality review pending - model unavailable. Please review manually.",
            AgentType.TESTER: "Test strategy analysis pending - model unavailable. Please create tests manually."
        }
        
        return fallback_responses.get(
            agent_type, 
            "Analysis pending - model unavailable. Manual intervention required."
        )
    
    def get_model_stats(self) -> dict:
        """Get statistics about model availability and usage."""
        return {
            "ollama_available": self.ollama_client is not None,
            "claude_available": self.claude_client is not None,
            "ollama_url": os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
            "escalation_threshold": self.escalation_threshold,
            "routing_config": {
                "diff_size_limit": self.diff_size_limit,
                "files_limit": self.files_limit,
            }
        }
    
    async def test_connections(self) -> dict:
        """Test connections to both Ollama and Claude."""
        results = {}
        
        # Test Ollama
        if self.ollama_client:
            try:
                test_message = HumanMessage(content="Test connection. Respond with 'OK'.")
                response = await asyncio.wait_for(
                    self.ollama_client.ainvoke([test_message]), 
                    timeout=30
                )
                results["ollama"] = {
                    "status": "connected",
                    "response": str(response.content)[:50] if hasattr(response, 'content') else str(response)[:50]
                }
            except Exception as e:
                results["ollama"] = {
                    "status": "failed",
                    "error": str(e)
                }
        else:
            results["ollama"] = {
                "status": "not_configured"
            }
        
        # Test Claude
        if self.claude_client:
            try:
                test_message = HumanMessage(content="Test connection. Respond with 'OK'.")
                response = await asyncio.wait_for(
                    self.claude_client.ainvoke([test_message]), 
                    timeout=30
                )
                results["claude"] = {
                    "status": "connected",
                    "response": str(response.content)[:50] if hasattr(response, 'content') else str(response)[:50]
                }
            except Exception as e:
                results["claude"] = {
                    "status": "failed",
                    "error": str(e)
                }
        else:
            results["claude"] = {
                "status": "not_configured"
            }
        
        return results