# LangGraph Migration Design Document
**Migrating Multi-Agent Workflow from Custom Orchestration to LangGraph**

## Executive Summary

This document outlines the concrete design and implementation plan for migrating the current multi-agent workflow system from a custom orchestration solution to LangGraph. The migration will preserve all existing functionality while adding stateful execution, time-travel debugging, and improved observability through LangGraph Studio.

## Current System Analysis

### Architecture Overview
The current system implements a 4-step workflow:
1. **Step 1**: Multi-agent analysis of feature requirements
2. **Step 2**: Consolidation into unified design document
3. **Step 3**: Finalization with GitHub PR feedback integration
4. **Step 4**: Enhanced implementation with test-driven development

### Key Components
- **WorkflowOrchestrator**: Central coordinator managing agent interactions
- **Agent Types**: Architect, Developer, Senior Engineer, Tester
- **Task Context**: Shared state management via JSON files
- **GitHub Integration**: PR creation, comment fetching, CI/CD interaction
- **CLI Wrappers**: Support for both Claude Code and Amp CLIs

### Current Pain Points
- **State Management**: JSON files in `.workflow/` directory - fragile and hard to version
- **No Checkpointing**: Cannot pause/resume mid-execution cleanly
- **Limited Observability**: Debugging requires extensive logging
- **No Time-Travel**: Cannot rewind to earlier states for debugging
- **Monolithic Steps**: Each step script is a complete execution unit

## LangGraph Architecture Design

### Core Concepts Mapping

| Current System | LangGraph Equivalent |
|---------------|---------------------|
| WorkflowOrchestrator | StateGraph + Nodes |
| Agent Interfaces | Tool Nodes with LLM calls |
| Task Context (JSON) | Graph State (TypedDict) |
| Step Scripts | Graph Execution with Checkpoints |
| `.workflow/` files | SQLite Checkpointer + Artifacts |
| PR State Management | Durable State Fields |

### State Schema Design

```python
from typing import TypedDict, List, Dict, Optional
from enum import Enum
from langgraph.graph import StateGraph

class WorkflowPhase(Enum):
    ANALYSIS = "analysis"
    DESIGN = "design"
    FINALIZATION = "finalization"
    IMPLEMENTATION = "implementation"

class AgentType(Enum):
    ARCHITECT = "architect"
    DEVELOPER = "developer"
    SENIOR_ENGINEER = "senior_engineer"
    TESTER = "tester"

class QualityState(Enum):
    DRAFT = "draft"
    OK = "ok"
    FAIL = "fail"

class FeedbackGate(Enum):
    OPEN = "open"
    HOLD = "hold"

class WorkflowState(TypedDict):
    # Core workflow tracking
    thread_id: str  # e.g., "pr-123" or "issue-456"
    current_phase: WorkflowPhase
    pr_number: Optional[int]
    
    # Task specification
    task_spec: str
    feature_name: str
    prd_source: Optional[str]  # If extracted from PRD
    
    # Repository context
    repo_name: str  # e.g., "owner/repo"
    repo_path: str  # Absolute path to workspace
    git_branch: str
    last_commit_sha: str
    
    # Agent outputs (compact)
    messages_window: List[Dict]  # Last 5-10 messages only
    summary_log: str  # Rolling summary of decisions
    
    # Analysis artifacts
    codebase_analysis: Dict  # Senior engineer's analysis
    agent_analyses: Dict[AgentType, str]  # Each agent's analysis
    
    # Design artifacts
    design_conflicts: List[Dict]  # Identified conflicts
    consolidated_design: str  # Unified design document
    finalized_design: Optional[str]  # After feedback incorporation
    
    # Implementation artifacts
    skeleton_code: Dict[str, str]  # File path -> skeleton content
    test_code: Dict[str, str]  # File path -> test content
    implementation_code: Dict[str, str]  # File path -> implementation
    
    # Quality gates
    test_results: Dict  # Compact test report
    lint_status: Dict  # Lint findings
    ci_status: Dict  # CI/CD check status
    quality_state: QualityState
    
    # Feedback management
    pr_comments: List[Dict]  # GitHub PR comments
    feedback_addressed: Dict[str, bool]  # Comment ID -> addressed
    feedback_gate: FeedbackGate
    
    # Artifact index (paths only, not content)
    artifacts_index: Dict[str, str]
    
    # Execution control
    retry_count: int
    escalation_needed: bool
    paused_for_review: bool
```

### Node Architecture

```python
# Node definitions following current agent pattern
class AgentNodes:
    """Collection of agent nodes for the workflow graph."""
    
    @staticmethod
    async def analyze_codebase(state: WorkflowState) -> Dict:
        """Senior Engineer analyzes codebase structure."""
        # Wraps current SeniorEngineerAgent.analyze_codebase()
        
    @staticmethod
    async def analyze_feature(state: WorkflowState) -> Dict:
        """All agents analyze the feature in parallel."""
        # Parallelizes current Round 1 analysis
        
    @staticmethod
    async def consolidate_design(state: WorkflowState) -> Dict:
        """Agents review and consolidate into unified design."""
        # Implements current Round 2 workflow
        
    @staticmethod
    async def incorporate_feedback(state: WorkflowState) -> Dict:
        """Process GitHub PR feedback and update design."""
        # Replaces step3_finalize_design_document.py
        
    @staticmethod
    async def create_skeleton(state: WorkflowState) -> Dict:
        """Architect creates implementation skeleton."""
        # From step4 enhanced implementation
        
    @staticmethod
    async def create_tests(state: WorkflowState) -> Dict:
        """Tester creates comprehensive test suite."""
        
    @staticmethod
    async def implement_code(state: WorkflowState) -> Dict:
        """Developer implements based on skeleton and design."""
        
    @staticmethod
    async def run_tests(state: WorkflowState) -> Dict:
        """Execute tests and capture results."""
        
    @staticmethod
    async def fix_failures(state: WorkflowState) -> Dict:
        """Fix test/lint failures (with escalation logic)."""
```

### GitHub Integration via MCP Tools

```python
class GitNodes:
    """GitHub operations using existing github_tools.py MCP integration."""
    
    @staticmethod
    async def push_branch_and_pr(state: WorkflowState) -> Dict:
        """Push branch and create/update PR using MCP tools."""
        from github_tools import execute_tool
        
        # Push current branch
        result = await execute_tool(
            "git_push",
            {"repository_id": state["repo_name"]}
        )
        
        # Create or update PR
        pr_result = await execute_tool(
            "github_create_pr",
            {
                "repository_id": state["repo_name"],
                "title": f"Implementation: {state['feature_name']}",
                "body": state["consolidated_design"],
                "branch": state["git_branch"]
            }
        )
        
        return {"pr_number": pr_result["pr_number"]}
    
    @staticmethod
    async def fetch_pr_comments(state: WorkflowState) -> Dict:
        """Fetch PR comments using MCP tools."""
        from github_tools import execute_get_pr_comments
        
        comments = await execute_get_pr_comments(
            repo_name=state["repo_name"],
            pr_number=state["pr_number"]
        )
        
        return {"pr_comments": comments}
```

### Graph Definition

```python
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver

def create_workflow_graph() -> StateGraph:
    """Create the complete multi-agent workflow graph."""
    
    graph = StateGraph(WorkflowState)
    
    # Add nodes
    graph.add_node("analyze_codebase", AgentNodes.analyze_codebase)
    graph.add_node("analyze_feature", AgentNodes.analyze_feature)
    graph.add_node("consolidate_design", AgentNodes.consolidate_design)
    graph.add_node("push_to_github", GitNodes.push_branch_and_pr)
    graph.add_node("await_feedback", InterruptNodes.wait_for_review)
    graph.add_node("fetch_feedback", GitNodes.fetch_pr_comments)
    graph.add_node("incorporate_feedback", AgentNodes.incorporate_feedback)
    graph.add_node("create_skeleton", AgentNodes.create_skeleton)
    graph.add_node("create_tests", AgentNodes.create_tests)
    graph.add_node("implement_code", AgentNodes.implement_code)
    graph.add_node("run_tests", AgentNodes.run_tests)
    graph.add_node("fix_failures", AgentNodes.fix_failures)
    graph.add_node("final_push", GitNodes.push_implementation)
    
    # Define edges (workflow flow)
    graph.set_entry_point("analyze_codebase")
    
    graph.add_edge("analyze_codebase", "analyze_feature")
    graph.add_edge("analyze_feature", "consolidate_design")
    graph.add_edge("consolidate_design", "push_to_github")
    graph.add_edge("push_to_github", "await_feedback")
    graph.add_edge("await_feedback", "fetch_feedback")
    
    # Conditional routing based on feedback
    graph.add_conditional_edges(
        "fetch_feedback",
        lambda state: "incorporate_feedback" if state["pr_comments"] else "create_skeleton",
        {
            "incorporate_feedback": "incorporate_feedback",
            "create_skeleton": "create_skeleton"
        }
    )
    
    graph.add_edge("incorporate_feedback", "push_to_github")
    graph.add_edge("create_skeleton", "create_tests")
    graph.add_edge("create_tests", "implement_code")
    graph.add_edge("implement_code", "run_tests")
    
    # Test result routing
    graph.add_conditional_edges(
        "run_tests",
        lambda state: "fix_failures" if state["quality_state"] == QualityState.FAIL else "final_push",
        {
            "fix_failures": "fix_failures",
            "final_push": "final_push"
        }
    )
    
    # Fix retry loop with escalation
    graph.add_conditional_edges(
        "fix_failures",
        lambda state: "run_tests" if state["retry_count"] < 3 else "escalate",
        {
            "run_tests": "run_tests",
            "escalate": "escalate_to_claude"
        }
    )
    
    graph.add_edge("final_push", END)
    
    return graph

# Initialize with SQLite checkpointing
checkpointer = SqliteSaver.from_conn_string("agent_state.db")
graph = create_workflow_graph()
app = graph.compile(checkpointer=checkpointer)
```

### Model Routing Strategy

```python
class ModelRouter:
    """Routes tasks to appropriate models based on complexity."""
    
    def __init__(self, ollama_host: str = None):
        # Support remote Ollama instance (e.g., Windows machine)
        ollama_url = ollama_host or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.ollama_client = Ollama(base_url=ollama_url)
        self.claude_client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        
    def should_escalate(self, state: WorkflowState) -> bool:
        """Determine if task should escalate to Claude."""
        return any([
            state["retry_count"] >= 2,
            state["escalation_needed"],
            len(state["design_conflicts"]) > 5,
            state["current_phase"] == WorkflowPhase.FINALIZATION
        ])
    
    async def call_model(self, prompt: str, state: WorkflowState, 
                         agent_type: str) -> str:
        """Route to appropriate model based on agent and state."""
        
        if agent_type in [AgentType.DEVELOPER, AgentType.TESTER] and not self.should_escalate(state):
            # Use local Ollama for routine tasks
            return await self.ollama_client.chat(
                model="qwen2.5-coder:7b",
                messages=[{"role": "user", "content": prompt}]
            )
        else:
            # Use Claude for complex reasoning
            return await self.claude_client.messages.create(
                model="claude-3-opus-20240229",
                messages=[{"role": "user", "content": prompt}]
            )
```

## Migration Implementation Plan

### Phase 1: Foundation (Week 1)
1. Set up LangGraph environment and dependencies
2. Create state schema and basic graph structure
3. Implement SQLite checkpointing
4. Create wrapper nodes for existing agent interfaces
5. Build local development server for LangGraph Studio

### Phase 2: Core Workflow (Week 2)
1. Migrate Step 1 (analysis) to graph nodes
2. Migrate Step 2 (design consolidation) 
3. Implement interrupt nodes for human review
4. Add GitHub integration nodes (PR, comments)
5. Test end-to-end analysis → design flow

### Phase 3: Implementation Flow (Week 3)
1. Migrate Step 3 (feedback incorporation)
2. Migrate Step 4 (enhanced implementation)
3. Add test execution and fixing nodes
4. Implement model routing logic
5. Add retry and escalation patterns

### Phase 4: Observability & Polish (Week 4)
1. Integrate LangGraph Studio for debugging
2. Add comprehensive state inspection
3. Implement time-travel and branching
4. Create monitoring dashboards
5. Performance optimization

## Task List for Implementation

### Setup Tasks
- [ ] Install LangGraph and dependencies (`pip install langgraph langgraph-checkpoint-sqlite`)
- [ ] Set up Ollama with qwen2.5-coder model
- [ ] Configure Anthropic API keys
- [ ] Create project structure for LangGraph components

### State Management
- [ ] Define WorkflowState TypedDict with all fields
- [ ] Create state validation utilities
- [ ] Implement artifact storage strategy (filesystem + index)
- [ ] Build state migration from existing JSON context

### Node Implementation
- [ ] Create AgentNodes class with all agent methods
- [ ] Wrap existing agent interfaces (ArchitectAgent, etc.)
- [ ] Create GitNodes for GitHub operations
- [ ] Build InterruptNodes for human review gates
- [ ] Implement ToolNodes for local execution (tests, lint)

### Graph Construction
- [ ] Define main workflow graph structure
- [ ] Add all nodes to graph
- [ ] Configure edges and conditional routing
- [ ] Set up checkpointing with SQLite
- [ ] Create graph compilation and initialization

### Model Integration
- [ ] Implement ModelRouter class
- [ ] Configure Ollama client for local models
- [ ] Set up Claude client for escalations
- [ ] Create escalation decision logic
- [ ] Add model call wrappers with retry logic

### GitHub Integration
- [ ] Port MCP server integration for PR operations
- [ ] Create comment fetching and parsing nodes
- [ ] Implement PR creation and update logic
- [ ] Add CI/CD status checking
- [ ] Build feedback incorporation workflow

### Testing Infrastructure
- [ ] Create test execution node
- [ ] Parse test results into state
- [ ] Implement failure analysis logic
- [ ] Build fix generation and application
- [ ] Add retry loops with limits

### Observability
- [ ] Set up LangGraph Studio server
- [ ] Configure thread ID strategy
- [ ] Implement state inspection endpoints
- [ ] Add logging and metrics
- [ ] Create debugging utilities

### Migration Scripts
- [ ] Create script to convert existing workflow to LangGraph
- [ ] Build backward compatibility layer
- [ ] Implement gradual migration strategy
- [ ] Add rollback capabilities
- [ ] Create comparison testing framework

### Documentation
- [ ] Write user guide for new workflow
- [ ] Document state schema and fields
- [ ] Create troubleshooting guide
- [ ] Add examples and tutorials
- [ ] Update README with new architecture

## Benefits of Migration

### Immediate Benefits
- **Checkpointing**: Pause/resume at any point
- **Observability**: Visual debugging in Studio
- **State Management**: Durable, versioned state
- **Time Travel**: Rewind and replay workflows
- **Parallel Execution**: Better resource utilization

### Long-term Benefits
- **Scalability**: Easier to add new agents/steps
- **Maintainability**: Cleaner separation of concerns
- **Extensibility**: Plugin architecture for new tools
- **Performance**: Optimized execution with caching
- **Reliability**: Automatic retry and recovery

## Risk Mitigation

### Technical Risks
- **Learning Curve**: Team needs LangGraph training
  - *Mitigation*: Gradual migration, extensive documentation
  
- **State Migration**: Converting existing workflows
  - *Mitigation*: Compatibility layer, parallel running

- **Performance**: Potential overhead from checkpointing
  - *Mitigation*: Optimize checkpoint frequency, use async

### Operational Risks
- **Debugging Complexity**: New tools and interfaces
  - *Mitigation*: Comprehensive logging, Studio training

- **Integration Issues**: GitHub API changes
  - *Mitigation*: Abstract GitHub operations, add retries

## Success Metrics

- All 4 workflow steps successfully migrated
- Checkpoint/resume working for all phases
- Time-travel debugging operational
- 50% reduction in debugging time
- Zero regression in functionality
- Improved execution speed with parallel agents

## Conclusion

This migration from custom orchestration to LangGraph will modernize the multi-agent workflow system while preserving all existing functionality. The phased approach ensures minimal disruption while delivering immediate benefits through checkpointing and observability. The investment in this migration will pay dividends through improved developer experience, easier maintenance, and a foundation for future enhancements.