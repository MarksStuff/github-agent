"""Enums for the LangGraph workflow."""

from enum import Enum


class AgentType(str, Enum):
    """Agent types in the workflow."""

    TEST_FIRST = "test-first"
    FAST_CODER = "fast-coder"
    SENIOR_ENGINEER = "senior-engineer"
    ARCHITECT = "architect"


class ModelRouter(str, Enum):
    """Model routing decisions."""

    OLLAMA = "ollama"
    CLAUDE_CODE = "claude_code"


class WorkflowPhase(str, Enum):
    """Workflow phases."""

    PHASE_0_CODE_CONTEXT = "phase_0_code_context"
    PHASE_1_DESIGN_EXPLORATION = "phase_1_design_exploration"
    PHASE_1_SYNTHESIS = "phase_1_synthesis"
    PHASE_1_CODE_INVESTIGATION = "phase_1_code_investigation"
    PHASE_1_HUMAN_REVIEW = "phase_1_human_review"
    PHASE_2_DESIGN_DOCUMENT = "phase_2_design_document"
    PHASE_3_SKELETON = "phase_3_skeleton"
    PHASE_3_PARALLEL_DEV = "phase_3_parallel_dev"
    PHASE_3_RECONCILIATION = "phase_3_reconciliation"
    PHASE_3_COMPONENT_TESTS = "phase_3_component_tests"
    PHASE_3_INTEGRATION_TESTS = "phase_3_integration_tests"
    PHASE_3_REFINEMENT = "phase_3_refinement"


class WorkflowStep(str, Enum):
    """Individual workflow steps/nodes."""
    
    # Phase 0: Feature and Code Context
    EXTRACT_FEATURE = "extract_feature"
    EXTRACT_CODE_CONTEXT = "extract_code_context"
    
    # Phase 1: Design
    PARALLEL_DESIGN_EXPLORATION = "parallel_design_exploration"
    ARCHITECT_SYNTHESIS = "architect_synthesis"
    CODE_INVESTIGATION = "code_investigation"
    HUMAN_REVIEW = "human_review"
    
    # Phase 2: Design Document
    CREATE_DESIGN_DOCUMENT = "create_design_document"
    ITERATE_DESIGN_DOCUMENT = "iterate_design_document"
    FINALIZE_DESIGN_DOCUMENT = "finalize_design_document"
    
    # Phase 3: Implementation
    CREATE_SKELETON = "create_skeleton"
    PARALLEL_DEVELOPMENT = "parallel_development"
    RECONCILIATION = "reconciliation"
    
    # Phase 4: Verification
    COMPONENT_TESTS = "component_tests"
    INTEGRATION_TESTS = "integration_tests"
    REFINEMENT = "refinement"
    
    # Phase 5: Deployment (not in step list but in graph)
    PUSH_TO_GITHUB = "push_to_github"
    WAIT_FOR_CI = "wait_for_ci"
    APPLY_PATCHES = "apply_patches"
