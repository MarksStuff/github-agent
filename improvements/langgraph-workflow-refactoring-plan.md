# LangGraph Workflow Refactoring Plan

## 🎯 **Executive Summary**

This document outlines a comprehensive refactoring plan for the `langgraph_workflow` module to eliminate code duplication, consolidate constants, and implement a node-based configuration system. The refactoring will improve maintainability, consistency, and extensibility while making it easier to add new workflow steps.

## 🔍 **Current State Analysis**

### **Critical Issues Identified**

#### **1. Constants Duplication**
- **Model Names**: `"qwen3:8b"` appears in 5+ files - make this a constnat
- **URLs**: `"http://localhost:11434"` Ollama URL scattered across codebase - always source this from a config file. it shouldn't even be a constant. 
- **Magic Strings**: `"Claude Code"` for CLI detection, various artifact names - these should all be enums
- **Timeouts**: Different timeout values hardcoded in multiple places

#### **2. Artifact Management Duplication**
- `get_artifacts_path(thread_id)` called repeatedly with same pattern
- `state["artifacts_index"]` manipulation scattered throughout workflow steps
- File writing patterns duplicated for each artifact type:
  ```python
  # This pattern appears 10+ times across workflow
  artifact_path = artifacts_dir / "artifact_name.md"
  artifact_path.write_text(content)
  state["artifacts_index"]["artifact_name"] = str(artifact_path)
  ```

#### **3. Workflow Step Pattern Duplication**
Each workflow method follows identical patterns but with duplicate code:
- **Logging**: Phase entry logging (`logger.info("Phase X: Step Y")`)
- **Model Routing**: Decision logic for Ollama vs Claude CLI
- **State Updates**: Setting phase and updating artifacts index
- **Error Handling**: Try/catch patterns with similar error messages

#### **4. Distributed Node Configuration**
Node characteristics are scattered across methods with no centralized definition:
- **File Access Requirements**: Some nodes need Claude CLI for file access, others can use Ollama
- **Artifact Storage**: Some artifacts go to `~/.local/share/`, others to repository
- **Timeout Requirements**: Different nodes have different timeout needs
- **Input/Output Dependencies**: No clear definition of what each node requires/produces

### **Technical Debt Metrics**
- **Code Duplication**: ~40% of workflow code follows repeated patterns
- **Magic Numbers**: 15+ hardcoded timeouts and thresholds
- **String Literals**: 25+ repeated string constants  
- **Configuration Scatter**: Node behavior defined in 6+ different locations

## 📋 **Detailed Refactoring Plan**

### **Phase 1: Constants Consolidation** ⏱️ *2-3 days*

#### **1.1 Model Constants Centralization**
Create `ModelConstants` class in `config.py`:

```python
@dataclass(frozen=True)
class ModelConstants:
    # Ollama Configuration
    DEFAULT_OLLAMA_MODEL = "qwen3:8b"
    OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    CLAUDE_CLI_DETECTION_STRING = "Claude Code"
    
    # Model Mappings
    AGENT_MODEL_MAP = {
        AgentType.SENIOR_ENGINEER: "qwen3:8b",
        AgentType.ARCHITECT: "qwen3:8b", 
        AgentType.TEST_FIRST: "llama3.1",
        AgentType.FAST_CODER: "llama3.1",
    }
    
    # Timeouts (in seconds)
    CLAUDE_CLI_TIMEOUT = 600  # 10 minutes for file access operations
    OLLAMA_TIMEOUT = 120      # 2 minutes for text generation
    MODEL_VERSION_CHECK_TIMEOUT = 5
```

#### **1.2 Artifact Constants**
```python
@dataclass(frozen=True) 
class ArtifactConstants:
    # Artifact Names (standardized keys for artifacts_index)
    FEATURE_DESCRIPTION = "feature_description"
    CODE_CONTEXT = "code_context"  
    DESIGN_DOCUMENT = "design_document"
    SKELETON_CODE = "skeleton"
    SYNTHESIS = "synthesis"
    
    # File Extensions
    MARKDOWN_EXT = ".md"
    PYTHON_EXT = ".py"
    JSON_EXT = ".json"
    
    # Quality Thresholds
    MIN_CODE_CONTEXT_LENGTH = 2000
    MAX_ARTIFACT_SIZE = 100_000
```

#### **1.3 Path Constants**
```python
@dataclass(frozen=True)
class PathConstants:
    # Base Paths (from existing config)
    ARTIFACTS_ROOT = WORKFLOW_CONFIG["paths"]["artifacts_root"]
    WORKSPACES_ROOT = WORKFLOW_CONFIG["paths"]["workspaces_root"]
    LOGS_ROOT = WORKFLOW_CONFIG["paths"]["logs_root"]
    
    @staticmethod
    def get_artifact_path(thread_id: str, artifact_name: str) -> Path:
        """Centralized artifact path construction."""
        return Path(PathConstants.ARTIFACTS_ROOT) / thread_id / f"{artifact_name}{ArtifactConstants.MARKDOWN_EXT}"
```

### **Phase 2: Node Configuration System** ⏱️ *3-4 days*

#### **2.1 Node Configuration Schema**
```python
@dataclass(frozen=True)
class NodeConfig:
    """Configuration for a workflow node."""
    
    # Identity
    name: str
    phase: WorkflowPhase
    step: WorkflowStep
    
    # Resource Requirements  
    requires_file_access: bool          # True = needs Claude CLI, False = can use Ollama
    model_preference: ModelRouter       # OLLAMA or CLAUDE_CODE
    timeout_seconds: int                # Operation timeout
    
    # Storage Configuration
    artifact_storage: ArtifactStorage   # LOCAL (~/.) vs REPO (./artifacts/)
    
    # Dependencies
    input_requirements: list[str]       # Required state fields
    output_artifacts: list[str]         # Artifacts this node produces
    
    # Behavior
    can_run_parallel: bool = False      # Can run with other nodes
    retry_count: int = 3                # Number of retries on failure
    quality_threshold: int | None = None # Min response length/quality
```

#### **2.2 Artifact Storage Enum**
```python
class ArtifactStorage(str, Enum):
    """Where to store node artifacts."""
    LOCAL = "local"      # ~/.local/share/github-agent/langgraph/artifacts/
    REPOSITORY = "repo"  # ./artifacts/ (for version control)
```

#### **2.3 Node Configuration Registry**
```python
NODE_CONFIGURATIONS: dict[WorkflowStep, NodeConfig] = {
    WorkflowStep.EXTRACT_FEATURE: NodeConfig(
        name="Feature Extraction",
        phase=WorkflowPhase.PHASE_0_CODE_CONTEXT,
        step=WorkflowStep.EXTRACT_FEATURE,
        requires_file_access=False,  # Can use Ollama for text analysis
        model_preference=ModelRouter.OLLAMA,
        timeout_seconds=120,
        artifact_storage=ArtifactStorage.LOCAL,
        input_requirements=["feature_description"],
        output_artifacts=[ArtifactConstants.FEATURE_DESCRIPTION],
    ),
    
    WorkflowStep.EXTRACT_CODE_CONTEXT: NodeConfig(
        name="Code Context Analysis", 
        phase=WorkflowPhase.PHASE_0_CODE_CONTEXT,
        step=WorkflowStep.EXTRACT_CODE_CONTEXT,
        requires_file_access=True,   # MUST use Claude CLI for file access
        model_preference=ModelRouter.CLAUDE_CODE,
        timeout_seconds=600,         # 10 minutes for comprehensive analysis
        artifact_storage=ArtifactStorage.LOCAL,
        input_requirements=["repo_path"],
        output_artifacts=[ArtifactConstants.CODE_CONTEXT],
        quality_threshold=ArtifactConstants.MIN_CODE_CONTEXT_LENGTH,
    ),
    
    # ... Additional node configurations
}
```

### **Phase 3: Base Node Class Implementation** ⏱️ *4-5 days*

#### **3.1 WorkflowNode Base Class**
```python
class WorkflowNode(ABC):
    """Base class for all workflow nodes with configuration-driven behavior."""
    
    def __init__(self, config: NodeConfig, workflow_context: 'MultiAgentWorkflow'):
        self.config = config
        self.workflow = workflow_context
        self.logger = logging.getLogger(f"workflow.{config.step.value}")
        
    async def execute(self, state: WorkflowState) -> WorkflowState:
        """Template method implementing common node execution pattern."""
        
        # 1. Validate inputs
        self._validate_inputs(state)
        
        # 2. Log phase entry
        self.logger.info(f"Phase {self.config.phase.value}: {self.config.name}")
        
        # 3. Update phase
        state["current_phase"] = self.config.phase
        
        # 4. Execute node-specific logic with error handling
        try:
            with asyncio.timeout(self.config.timeout_seconds):
                result_state = await self._execute_core_logic(state)
        except asyncio.TimeoutError:
            raise RuntimeError(f"{self.config.name} timed out after {self.config.timeout_seconds}s")
        except Exception as e:
            self.logger.error(f"{self.config.name} failed: {e}")
            raise
            
        # 5. Handle artifact storage
        await self._store_artifacts(result_state)
        
        # 6. Log completion
        self.logger.info(f"✅ {self.config.name} completed")
        
        return result_state
        
    @abstractmethod
    async def _execute_core_logic(self, state: WorkflowState) -> WorkflowState:
        """Node-specific implementation."""
        pass
        
    def _validate_inputs(self, state: WorkflowState) -> None:
        """Validate required inputs are present."""
        missing = [req for req in self.config.input_requirements if req not in state]
        if missing:
            raise ValueError(f"{self.config.name} missing required inputs: {missing}")
            
    async def _store_artifacts(self, state: WorkflowState) -> None:
        """Store artifacts according to configuration."""
        for artifact_name in self.config.output_artifacts:
            if artifact_name in state.get("_temp_artifacts", {}):
                await self._write_artifact(
                    state, 
                    artifact_name, 
                    state["_temp_artifacts"][artifact_name]
                )
                
    async def _write_artifact(self, state: WorkflowState, name: str, content: str) -> None:
        """Write artifact to configured storage location."""
        if self.config.artifact_storage == ArtifactStorage.LOCAL:
            path = PathConstants.get_artifact_path(state["thread_id"], name)
        else:  # REPOSITORY
            path = Path("./artifacts") / state["thread_id"] / f"{name}.md"
            
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        
        # Update artifacts index
        if "artifacts_index" not in state:
            state["artifacts_index"] = {}
        state["artifacts_index"][name] = str(path)
        
        self.logger.info(f"📁 Stored {name} artifact: {path}")
```

#### **3.2 Concrete Node Implementations**
```python
class FeatureExtractionNode(WorkflowNode):
    """Extracts and processes feature descriptions."""
    
    async def _execute_core_logic(self, state: WorkflowState) -> WorkflowState:
        # Use configuration-driven model selection
        if self.config.requires_file_access:
            content = await self._extract_with_claude_cli(state)
        else:
            content = await self._extract_with_ollama(state) 
            
        # Store in temp artifacts for base class to handle
        state.setdefault("_temp_artifacts", {})[ArtifactConstants.FEATURE_DESCRIPTION] = content
        state["feature_description"] = content
        
        return state

class CodeContextNode(WorkflowNode):
    """Analyzes codebase and generates context document."""
    
    async def _execute_core_logic(self, state: WorkflowState) -> WorkflowState:
        # Configuration enforces Claude CLI requirement
        context_doc = await self._generate_with_claude_cli(state)
        
        # Apply quality threshold check from configuration
        if (self.config.quality_threshold and 
            len(context_doc) < self.config.quality_threshold):
            raise RuntimeError(
                f"Code context below quality threshold: {len(context_doc)} < {self.config.quality_threshold}"
            )
            
        state.setdefault("_temp_artifacts", {})[ArtifactConstants.CODE_CONTEXT] = context_doc
        state["code_context_document"] = context_doc
        
        return state
```

### **Phase 4: Integration and Migration** ⏱️ *3-4 days*

#### **4.1 Workflow Integration**
```python
class MultiAgentWorkflow:
    """Updated workflow using node-based architecture."""
    
    def __init__(self, ...):
        # Initialize nodes from configuration
        self.nodes: dict[WorkflowStep, WorkflowNode] = {}
        for step, config in NODE_CONFIGURATIONS.items():
            node_class = self._get_node_class(step)
            self.nodes[step] = node_class(config, self)
            
    async def extract_feature(self, state: WorkflowState) -> WorkflowState:
        """Delegate to configured node."""
        return await self.nodes[WorkflowStep.EXTRACT_FEATURE].execute(state)
        
    async def extract_code_context(self, state: WorkflowState) -> WorkflowState:
        """Delegate to configured node."""
        return await self.nodes[WorkflowStep.EXTRACT_CODE_CONTEXT].execute(state)
        
    def _get_node_class(self, step: WorkflowStep) -> type[WorkflowNode]:
        """Map workflow steps to node classes."""
        node_classes = {
            WorkflowStep.EXTRACT_FEATURE: FeatureExtractionNode,
            WorkflowStep.EXTRACT_CODE_CONTEXT: CodeContextNode,
            # ... other mappings
        }
        return node_classes[step]
```

#### **4.2 Backward Compatibility**
- Keep existing method signatures during transition
- Add deprecation warnings for direct method calls
- Provide migration utilities for existing state data

### **Phase 5: Advanced Improvements** ⏱️ *2-3 days*

#### **5.1 Configuration Validation**
```python
@dataclass
class NodeConfigValidator:
    """Validates node configurations at startup."""
    
    @staticmethod
    def validate_all_configurations() -> list[str]:
        """Validate all node configurations and return errors."""
        errors = []
        
        for step, config in NODE_CONFIGURATIONS.items():
            errors.extend(NodeConfigValidator._validate_single_config(step, config))
            
        return errors
        
    @staticmethod  
    def _validate_single_config(step: WorkflowStep, config: NodeConfig) -> list[str]:
        """Validate a single node configuration."""
        errors = []
        
        # Check timeout is reasonable
        if config.timeout_seconds > 3600:  # 1 hour
            errors.append(f"{step}: Timeout {config.timeout_seconds}s exceeds maximum")
            
        # Validate file access requirements
        if config.requires_file_access and config.model_preference != ModelRouter.CLAUDE_CODE:
            errors.append(f"{step}: File access requires Claude CLI but prefers {config.model_preference}")
            
        # Check input/output consistency
        if not config.output_artifacts:
            errors.append(f"{step}: Node produces no artifacts")
            
        return errors
```

#### **5.2 Runtime Dependency Checking**
```python
class WorkflowDependencyChecker:
    """Checks workflow step dependencies at runtime."""
    
    @staticmethod
    def check_dependencies(execution_plan: list[WorkflowStep]) -> list[str]:
        """Check if execution plan satisfies all dependencies."""
        errors = []
        available_artifacts = set()
        
        for step in execution_plan:
            config = NODE_CONFIGURATIONS[step]
            
            # Check if required inputs are available
            for requirement in config.input_requirements:
                if requirement not in available_artifacts and requirement not in INITIAL_STATE_FIELDS:
                    errors.append(f"{step} requires {requirement} which is not yet available")
                    
            # Add outputs to available artifacts
            available_artifacts.update(config.output_artifacts)
            
        return errors
```

## 🎯 **Migration Strategy**

### **Incremental Migration Approach**

1. **Phase 1**: Add constants alongside existing code (no breaking changes)
2. **Phase 2**: Implement node configuration system in parallel 
3. **Phase 3**: Create base node class and first few concrete nodes
4. **Phase 4**: Gradually migrate existing methods to use nodes
5. **Phase 5**: Remove deprecated code and add advanced features

### **Testing Strategy**

```python
class TestNodeConfiguration:
    """Comprehensive testing for node system."""
    
    def test_all_nodes_have_valid_configs(self):
        """Ensure all workflow steps have valid configurations."""
        errors = NodeConfigValidator.validate_all_configurations()
        assert not errors, f"Invalid configurations: {errors}"
        
    def test_workflow_dependency_resolution(self):
        """Test that workflow execution plan satisfies dependencies."""
        execution_plan = [step for step in WorkflowStep if step in NODE_CONFIGURATIONS]
        errors = WorkflowDependencyChecker.check_dependencies(execution_plan)
        assert not errors, f"Dependency errors: {errors}"
        
    def test_node_artifact_storage(self):
        """Test artifact storage respects configuration."""
        # Test both LOCAL and REPOSITORY storage modes
        pass
```

## 📊 **Expected Benefits**

### **Quantitative Improvements**
- **Code Duplication**: Reduce from ~40% to <10%
- **Constants**: Eliminate 25+ scattered string literals
- **Configuration Points**: Consolidate from 6+ locations to 1 registry
- **Test Coverage**: Easier testing of individual node behaviors

### **Qualitative Improvements**
- **Maintainability**: Adding new nodes becomes declarative configuration
- **Consistency**: All nodes follow identical patterns for logging, error handling, artifacts
- **Debugging**: Centralized logging and error handling makes issues easier to trace
- **Flexibility**: Can easily change storage locations, model preferences, timeouts
- **Documentation**: Node configurations serve as living documentation

## 🚀 **Implementation Timeline**

| Phase | Duration | Deliverables |
|-------|----------|--------------|
| Phase 1: Constants | 2-3 days | `ModelConstants`, `ArtifactConstants`, `PathConstants` classes |
| Phase 2: Configuration | 3-4 days | `NodeConfig`, `NODE_CONFIGURATIONS` registry |
| Phase 3: Base Node | 4-5 days | `WorkflowNode` base class, first concrete nodes |
| Phase 4: Integration | 3-4 days | Workflow integration, migration utilities |
| Phase 5: Advanced | 2-3 days | Validation, dependency checking, cleanup |

**Total Estimated Time**: 14-19 days

## 🔄 **Risk Mitigation**

### **Technical Risks**
- **Breaking Changes**: Mitigated by incremental migration and backward compatibility
- **Performance Impact**: Node configuration lookup is cached and minimal overhead
- **Testing Complexity**: Comprehensive test suite ensures reliability

### **Timeline Risks** 
- **Scope Creep**: Well-defined phases prevent feature creep
- **Integration Issues**: Early integration testing identifies problems
- **Resource Allocation**: Can be implemented by single developer with review

## 📝 **Success Criteria**

- [ ] Zero code duplication in workflow node patterns
- [ ] All constants centralized in configuration classes
- [ ] New workflow nodes can be added with <50 lines of code
- [ ] 100% test coverage for node system
- [ ] All existing functionality preserved
- [ ] Performance maintained or improved
- [ ] Clear documentation and examples

---

## 🤝 **Next Steps**

1. **Review and Approval**: Stakeholder review of this plan
2. **Phase 1 Kickoff**: Begin constants consolidation 
3. **Incremental Reviews**: Review each phase completion before proceeding
4. **Testing Validation**: Comprehensive testing at each phase
5. **Documentation Updates**: Update README and examples

This refactoring will transform the LangGraph workflow from a monolithic implementation with scattered configuration to a clean, maintainable, node-based architecture that will be much easier to extend and debug.