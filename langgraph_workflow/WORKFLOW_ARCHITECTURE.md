# LangGraph Workflow Architecture

## File Structure and Purpose

### Core Production Files

#### 1. **`langgraph_workflow.py`** - Legacy/Original Workflow
- **Purpose**: Original multi-agent workflow implementation
- **Status**: Legacy - can be deprecated in favor of enhanced workflow
- **Contains**: 
  - `MultiAgentWorkflow` class with hardcoded node implementations
  - Direct node method implementations
  - Basic workflow structure without declarative configuration

#### 2. **`enhanced_workflow.py`** - New Declarative Workflow System
- **Purpose**: Modern declarative workflow with configurable nodes
- **Status**: Production-ready replacement for langgraph_workflow.py
- **Contains**:
  - `EnhancedMultiAgentWorkflow` class with declarative node system
  - Standard workflow integration (code quality, PR feedback)
  - Automatic quality gates and GitHub integration
  - Factory function `create_enhanced_workflow()`

#### 3. **`node_config.py`** - Configuration Framework
- **Purpose**: Core configuration system for declarative nodes
- **Status**: Production - required by enhanced_workflow.py
- **Contains**:
  - `NodeConfig` dataclass for declarative configuration
  - `StandardWorkflows` for code quality and PR feedback
  - Configuration validation and helper functions

#### 4. **`nodes/`** - Node Definitions Directory
- **Purpose**: Individual node configurations and implementations
- **Status**: Production - contains declarative node definitions
- **Files**:
  - `extract_code_context.py` - Code analysis node
  - `parallel_design_exploration.py` - Multi-agent design exploration
  - `create_design_document.py` - Design document creation with PR feedback
  - `parallel_development.py` - Implementation with full quality integration

### Supporting Files

#### 5. **`enums.py`** - Type Definitions
- **Purpose**: Shared enums and constants
- **Status**: Production - required by both workflows

#### 6. **`interfaces.py`** - Abstract Interfaces
- **Purpose**: Interface definitions for dependency injection
- **Status**: Production - required for proper abstraction

#### 7. **`config.py`** - Environment Configuration
- **Purpose**: Environment variable loading and configuration
- **Status**: Production - required for Ollama/GitHub integration

### Demo and Documentation

#### 8. **`demo/`** - Demonstration Code
- **Purpose**: Examples and demonstrations (NOT production code)
- **Files**:
  - `demo_enhanced_workflow.py` - Complete system demonstration
  - `__init__.py` - Package marker

#### 9. **Documentation Files**
- `ENHANCED_WORKFLOW_SUMMARY.md` - Implementation summary
- `WORKFLOW_ARCHITECTURE.md` - This file

## Recommended Migration Path

### Phase 1: Transition (Current)
- Keep both `langgraph_workflow.py` and `enhanced_workflow.py`
- Use `enhanced_workflow.py` for new development
- Gradually migrate existing usage to enhanced workflow

### Phase 2: Deprecation
- Mark `langgraph_workflow.py` as deprecated
- Update all imports to use `enhanced_workflow.py`
- Add deprecation warnings to old workflow

### Phase 3: Cleanup
- Remove `langgraph_workflow.py` entirely
- Rename `enhanced_workflow.py` to `workflow.py` (optional)
- Update all documentation and examples

## Import Recommendations

### For New Code (Recommended)
```python
from langgraph_workflow.enhanced_workflow import create_enhanced_workflow
from langgraph_workflow.node_config import NodeConfig, StandardWorkflows
from langgraph_workflow.enums import WorkflowStep, AgentType, ModelRouter
```

### For Legacy Code (Deprecated)
```python
from langgraph_workflow.langgraph_workflow import MultiAgentWorkflow
```

## Key Differences

| Feature | `langgraph_workflow.py` | `enhanced_workflow.py` |
|---------|------------------------|------------------------|
| Configuration | Hardcoded in methods | Declarative in separate files |
| Code Quality | Manual | Automatic integration |
| PR Feedback | Manual | Automatic integration |
| Model Selection | Complex logic | Simple declarative rules |
| Extensibility | Requires code changes | Configuration-driven |
| Maintainability | Coupled implementation | Clean separation |
| Testing | Harder to test nodes | Easy to test configurations |

## Decision: Which Files to Keep

### **Keep for Production**
1. ✅ `enhanced_workflow.py` - Primary workflow system
2. ✅ `node_config.py` - Configuration framework
3. ✅ `nodes/` directory - Node definitions
4. ✅ `enums.py` - Type definitions
5. ✅ `interfaces.py` - Abstract interfaces
6. ✅ `config.py` - Environment configuration

### **Deprecate/Remove**
1. ❌ `langgraph_workflow.py` - Replace with enhanced_workflow.py
2. ❌ Any other legacy workflow files

### **Keep for Development**
1. ✅ `demo/` directory - Examples and demonstrations
2. ✅ Documentation files

## Conclusion

The enhanced workflow system (`enhanced_workflow.py` + `node_config.py` + `nodes/`) should replace the legacy `langgraph_workflow.py`. The new system provides:

- **Declarative configuration** instead of hardcoded implementations
- **Automatic standard workflows** for code quality and PR feedback
- **Better maintainability** with clear separation of concerns
- **Enhanced extensibility** through configuration-driven design

The legacy workflow can be safely deprecated and eventually removed once all usage is migrated to the enhanced system.