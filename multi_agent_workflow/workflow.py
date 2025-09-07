#!/usr/bin/env python3
"""
Enhanced Multi-Agent Workflow Orchestrator

This is the main entry point for the enhanced workflow system that provides:
- Idempotent execution (can resume from any failure point)
- Beautiful progress visualization
- GitHub integration for feedback loops
- State persistence across runs

Usage:
    python workflow.py start "Build a todo app with authentication"
    python workflow.py resume workflow_20241201_143022
    python workflow.py status workflow_20241201_143022
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import Any, Optional

try:
    # Try relative import first (when used as module)
    from .workflow_state import (
        StageStatus,
        WorkflowInputs,
        WorkflowState,
        generate_workflow_id,
    )
    from .output_manager import WorkflowProgressDisplay, workflow_logger
except ImportError:
    # Fallback to direct import (when run as standalone script)
    from workflow_state import (
        StageStatus,
        WorkflowInputs,
        WorkflowState,
        generate_workflow_id,
    )
    from output_manager import WorkflowProgressDisplay, workflow_logger

# Initialize progress display and logger (rich logging will be set up by output_manager)
progress_display = WorkflowProgressDisplay()
logger = workflow_logger


class WorkflowStageExecutor:
    """Base class for workflow stage execution."""

    def __init__(self, stage_name: str, description: str):
        self.stage_name = stage_name
        self.description = description
        self.logger = logging.getLogger(f"stage.{stage_name}")

    def execute(self, state: WorkflowState, inputs: WorkflowInputs) -> dict[str, Any]:
        """
        Execute this stage of the workflow.

        Args:
            state: Current workflow state
            inputs: Workflow input parameters

        Returns:
            Dictionary containing stage results including:
            - output_files: List of files created
            - metrics: Dictionary of stage metrics
            - next_actions: Optional list of follow-up actions
        """
        raise NotImplementedError("Subclasses must implement execute()")

    def can_skip(self, state: WorkflowState, inputs: WorkflowInputs) -> bool:
        """
        Check if this stage can be skipped (already completed successfully).

        Args:
            state: Current workflow state
            inputs: Workflow input parameters

        Returns:
            True if stage can be skipped, False otherwise
        """
        stage = state.get_stage(self.stage_name)
        return stage and stage.status == StageStatus.COMPLETED

    def validate_inputs(self, inputs: WorkflowInputs) -> list[str]:
        """
        Validate inputs for this stage.

        Args:
            inputs: Workflow input parameters

        Returns:
            List of validation error messages (empty if valid)
        """
        return []  # Default: no validation errors


class RequirementsAnalysisStage(WorkflowStageExecutor):
    """Stage 1: Analyze requirements and create initial specifications."""

    def __init__(self):
        super().__init__(
            "requirements_analysis",
            "Analyze project requirements and create specifications",
        )

    def execute(self, state: WorkflowState, inputs: WorkflowInputs) -> dict[str, Any]:
        """Execute requirements analysis."""
        self.logger.info("Starting requirements analysis...")

        # TODO: In future implementation, this would call the existing
        # multi_agent_workflow/step1_analysis.py script

        # For now, create a placeholder implementation
        self.logger.info(f"Analyzing project: {inputs.project_description}")

        # Simulate some work
        import time

        time.sleep(1)

        # Create output files (placeholder)
        output_files = ["requirements.md", "user_stories.md", "acceptance_criteria.md"]

        metrics = {
            "analysis_duration": 1.0,
            "requirements_identified": 8,
            "user_stories_created": 12,
            "acceptance_criteria_count": 24,
        }

        self.logger.info("Requirements analysis completed successfully")

        return {
            "output_files": output_files,
            "metrics": metrics,
            "next_actions": ["Review requirements with stakeholders"],
        }

    def validate_inputs(self, inputs: WorkflowInputs) -> list[str]:
        """Validate inputs for requirements analysis."""
        errors = []

        if (
            not inputs.project_description
            or len(inputs.project_description.strip()) < 10
        ):
            errors.append("Project description must be at least 10 characters long")

        return errors


class ArchitectureDesignStage(WorkflowStageExecutor):
    """Stage 2: Create architecture and design documents."""

    def __init__(self):
        super().__init__(
            "architecture_design",
            "Design system architecture and create technical specifications",
        )

    def execute(self, state: WorkflowState, inputs: WorkflowInputs) -> dict[str, Any]:
        """Execute architecture design."""
        self.logger.info("Starting architecture design...")

        # TODO: In future implementation, this would call the existing
        # multi_agent_workflow/step2_create_design_document.py script

        self.logger.info("Creating system architecture...")

        # Simulate work
        import time

        time.sleep(1.5)

        output_files = [
            "architecture_design.md",
            "system_components.md",
            "data_models.md",
            "api_specifications.md",
        ]

        metrics = {
            "design_duration": 1.5,
            "components_designed": 6,
            "apis_specified": 15,
            "data_models_created": 8,
        }

        self.logger.info("Architecture design completed successfully")

        return {
            "output_files": output_files,
            "metrics": metrics,
            "next_actions": ["Review architecture with technical team"],
        }


class ImplementationPlanStage(WorkflowStageExecutor):
    """Stage 3: Create detailed implementation plan."""

    def __init__(self):
        super().__init__(
            "implementation_plan",
            "Create detailed implementation plan and task breakdown",
        )

    def execute(self, state: WorkflowState, inputs: WorkflowInputs) -> dict[str, Any]:
        """Execute implementation planning."""
        self.logger.info("Starting implementation planning...")

        # TODO: In future implementation, this would call the existing
        # multi_agent_workflow/step3_finalize_design_document.py script

        self.logger.info("Creating implementation plan...")

        # Simulate work
        import time

        time.sleep(1)

        output_files = [
            "implementation_plan.md",
            "development_phases.md",
            "task_breakdown.md",
            "technology_stack.md",
        ]

        metrics = {
            "planning_duration": 1.0,
            "phases_planned": 4,
            "tasks_identified": 45,
            "technologies_selected": 12,
        }

        self.logger.info("Implementation planning completed successfully")

        return {
            "output_files": output_files,
            "metrics": metrics,
            "next_actions": ["Begin development phase"],
        }


class CodeGenerationStage(WorkflowStageExecutor):
    """Stage 4: Generate code based on design and plan."""

    def __init__(self):
        super().__init__(
            "code_generation",
            "Generate application code based on design specifications",
        )

    def execute(self, state: WorkflowState, inputs: WorkflowInputs) -> dict[str, Any]:
        """Execute code generation."""
        self.logger.info("Starting code generation...")

        # TODO: In future implementation, this would call the existing
        # multi_agent_workflow/step4_implementation.py script

        self.logger.info("Generating application code...")

        # Simulate work
        import time

        time.sleep(2)

        output_files = [
            "src/main.py",
            "src/models.py",
            "src/views.py",
            "src/utils.py",
            "requirements.txt",
            "README.md",
        ]

        metrics = {
            "generation_duration": 2.0,
            "files_created": len(output_files),
            "lines_of_code": 1250,
            "functions_implemented": 35,
            "classes_created": 8,
        }

        self.logger.info("Code generation completed successfully")

        return {
            "output_files": output_files,
            "metrics": metrics,
            "next_actions": ["Run initial tests", "Review generated code"],
        }


class TestingSetupStage(WorkflowStageExecutor):
    """Stage 5: Set up testing framework and initial tests."""

    def __init__(self):
        super().__init__(
            "testing_setup", "Set up testing framework and create initial test cases"
        )

    def execute(self, state: WorkflowState, inputs: WorkflowInputs) -> dict[str, Any]:
        """Execute testing setup."""
        self.logger.info("Starting testing setup...")

        self.logger.info("Setting up test framework...")

        # Simulate work
        import time

        time.sleep(1)

        output_files = [
            "tests/test_main.py",
            "tests/test_models.py",
            "tests/test_views.py",
            "tests/conftest.py",
            "pytest.ini",
        ]

        metrics = {
            "setup_duration": 1.0,
            "test_files_created": len(output_files),
            "test_cases_written": 28,
            "coverage_target": 85,
        }

        self.logger.info("Testing setup completed successfully")

        return {
            "output_files": output_files,
            "metrics": metrics,
            "next_actions": ["Run test suite", "Set up CI/CD pipeline"],
        }


class DocumentationStage(WorkflowStageExecutor):
    """Stage 6: Generate comprehensive documentation."""

    def __init__(self):
        super().__init__("documentation", "Generate user and developer documentation")

    def execute(self, state: WorkflowState, inputs: WorkflowInputs) -> dict[str, Any]:
        """Execute documentation generation."""
        self.logger.info("Starting documentation generation...")

        self.logger.info("Creating documentation...")

        # Simulate work
        import time

        time.sleep(1)

        output_files = [
            "docs/README.md",
            "docs/installation.md",
            "docs/user_guide.md",
            "docs/api_reference.md",
            "docs/deployment.md",
        ]

        metrics = {
            "documentation_duration": 1.0,
            "documents_created": len(output_files),
            "pages_written": 25,
            "code_examples": 15,
        }

        self.logger.info("Documentation generation completed successfully")

        return {
            "output_files": output_files,
            "metrics": metrics,
            "next_actions": ["Review documentation", "Publish to documentation site"],
        }


class WorkflowOrchestrator:
    """Main workflow orchestrator that manages stage execution."""

    def __init__(self):
        self.logger = workflow_logger
        self.display = progress_display
        # Initialize stage executors
        self.stages = {
            "requirements_analysis": RequirementsAnalysisStage(),
            "architecture_design": ArchitectureDesignStage(),
            "implementation_plan": ImplementationPlanStage(),
            "code_generation": CodeGenerationStage(),
            "testing_setup": TestingSetupStage(),
            "documentation": DocumentationStage(),
        }

    def start_workflow(
        self,
        project_description: str,
        config_overrides: Optional[dict[str, Any]] = None,
        template_name: Optional[str] = None,
        from_stage: Optional[str] = None,
        to_stage: Optional[str] = None,
    ) -> str:
        """
        Start a new workflow.

        Args:
            project_description: Description of the project to build
            config_overrides: Optional configuration overrides
            template_name: Optional template to use
            from_stage: Optional stage to start from (default: first stage)
            to_stage: Optional stage to stop at (default: last stage)

        Returns:
            Workflow ID of the started workflow
        """
        # Generate new workflow ID
        workflow_id = generate_workflow_id()
        self.logger.info(f"Starting new workflow: {workflow_id}")

        # Create workflow state
        state = WorkflowState(workflow_id)

        # Set inputs
        inputs = WorkflowInputs(
            project_description=project_description,
            config_overrides=config_overrides or {},
            template_name=template_name,
        )
        state.set_inputs(inputs)

        # Save initial state
        state.save()
        
        # Display initial workflow status
        self.display.display_workflow_status(state, project_description)
        
        # Execute workflow
        return self._execute_workflow(state, inputs, from_stage, to_stage)

    def resume_workflow(
        self,
        workflow_id: str,
        from_stage: Optional[str] = None,
        to_stage: Optional[str] = None,
    ) -> str:
        """
        Resume an existing workflow.

        Args:
            workflow_id: ID of workflow to resume
            from_stage: Optional stage to start from (default: next incomplete stage)
            to_stage: Optional stage to stop at (default: last stage)

        Returns:
            Workflow ID of the resumed workflow
        """
        self.logger.info(f"Resuming workflow: {workflow_id}")

        # Load existing state
        state = WorkflowState.load(workflow_id)
        if not state:
            raise ValueError(f"Workflow {workflow_id} not found or could not be loaded")

        if not state.can_resume():
            self.logger.info("Workflow is already complete")
            return workflow_id

        # Get inputs from state
        if not state.inputs:
            raise ValueError("Workflow state does not contain input parameters")

        inputs = state.inputs

        # Execute workflow from resume point
        return self._execute_workflow(state, inputs, from_stage, to_stage)

    def get_workflow_status(self, workflow_id: str) -> dict[str, Any]:
        """
        Get status of a workflow.

        Args:
            workflow_id: ID of workflow to check

        Returns:
            Dictionary containing workflow status information
        """
        state = WorkflowState.load(workflow_id)
        if not state:
            return {"error": f"Workflow {workflow_id} not found"}

        return state.get_summary()

    def list_workflows(self) -> list[dict[str, Any]]:
        """
        List all available workflows.

        Returns:
            List of workflow summaries
        """
        # Look for state files in the state directory
        workflow_dir = Path(__file__).parent / "state"
        if not workflow_dir.exists():
            return []

        workflows = []
        for state_file in workflow_dir.glob("*_state.json"):
            # Extract workflow ID from filename
            workflow_id = state_file.stem.replace("_state", "")

            # Load and get summary
            state = WorkflowState.load(workflow_id, state_file)
            if state:
                workflows.append(state.get_summary())

        # Sort by creation date (newest first)
        workflows.sort(key=lambda w: w.get("created_at", ""), reverse=True)
        return workflows

    def _execute_workflow(
        self,
        state: WorkflowState,
        inputs: WorkflowInputs,
        from_stage: Optional[str] = None,
        to_stage: Optional[str] = None,
    ) -> str:
        """
        Execute the workflow pipeline.

        Args:
            state: Workflow state
            inputs: Workflow inputs
            from_stage: Optional stage to start from
            to_stage: Optional stage to stop at

        Returns:
            Workflow ID
        """
        # Determine stages to execute
        stage_names = list(self.stages.keys())

        if from_stage:
            if from_stage not in stage_names:
                raise ValueError(f"Unknown stage: {from_stage}")
            start_idx = stage_names.index(from_stage)
        else:
            # Find first incomplete stage
            start_idx = 0
            for i, stage_name in enumerate(stage_names):
                stage_obj = self.stages[stage_name]
                if not stage_obj.can_skip(state, inputs):
                    start_idx = i
                    break

        if to_stage:
            if to_stage not in stage_names:
                raise ValueError(f"Unknown stage: {to_stage}")
            end_idx = stage_names.index(to_stage) + 1
        else:
            end_idx = len(stage_names)

        stages_to_execute = stage_names[start_idx:end_idx]

        self.logger.info(f"Executing stages: {stages_to_execute}")

        # Execute each stage
        for stage_name in stages_to_execute:
            stage_executor = self.stages[stage_name]

            # Check if stage can be skipped
            if stage_executor.can_skip(state, inputs):
                self.logger.info(f"Skipping completed stage: {stage_name}")
                continue

            # Validate inputs for this stage
            validation_errors = stage_executor.validate_inputs(inputs)
            if validation_errors:
                error_msg = f"Input validation failed for {stage_name}: {'; '.join(validation_errors)}"
                self.logger.error(error_msg)
                state.fail_stage(stage_name, error_msg)
                state.save()
                raise ValueError(error_msg)

            try:
                # Start stage
                state.start_stage(stage_name)
                state.save()
                
                # Show beautiful stage start display
                self.display.show_stage_start(stage_name, stage_executor.description)
                self.logger.stage_start(stage_name, stage_executor.description)
                # Execute stage
                result = stage_executor.execute(state, inputs)

                # Complete stage
                stage = state.get_stage(stage_name)
                duration = None
                if stage and stage.started_at:
                    from datetime import datetime
                    duration = (datetime.utcnow() - stage.started_at.replace(tzinfo=None)).total_seconds()
                
                state.complete_stage(
                    stage_name,
                    output_files=result.get("output_files", []),
                    metrics=result.get("metrics", {}),
                )
                state.save()
                
                # Show beautiful stage completion display
                self.display.show_stage_complete(stage_name, result)
                self.logger.stage_complete(stage_name, duration)
                
                # Update workflow status display
                self.display.display_workflow_status(state, inputs.project_description)
                
            except Exception as e:
                error_msg = f"Stage {stage_name} failed: {str(e)}"
                self.display.show_stage_failure(stage_name, error_msg)
                self.logger.stage_failed(stage_name, str(e))
                state.fail_stage(stage_name, error_msg)
                state.save()
                raise

        # Check if workflow is complete
        if state.is_workflow_complete():
            self.display.show_workflow_complete(state)
            self.logger.success(f"Workflow {state.workflow_id} completed successfully!")
        else:
            self.logger.info(f"Workflow {state.workflow_id} partially completed - can be resumed later")
        
        return state.workflow_id


def main():
    """Main entry point for the workflow CLI."""
    parser = argparse.ArgumentParser(
        description="Enhanced Multi-Agent Workflow System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start a new workflow
  python workflow.py start "Build a todo app with user authentication"

  # Start with specific stages
  python workflow.py start "Build a chat app" --from-stage architecture_design --to-stage implementation_plan

  # Resume an existing workflow
  python workflow.py resume workflow_20241201_143022

  # Check workflow status
  python workflow.py status workflow_20241201_143022

  # List all workflows
  python workflow.py list
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Start command
    start_parser = subparsers.add_parser("start", help="Start a new workflow")
    start_parser.add_argument("description", help="Project description")
    start_parser.add_argument("--template", help="Template to use")
    start_parser.add_argument("--from-stage", help="Stage to start from")
    start_parser.add_argument("--to-stage", help="Stage to stop at")
    start_parser.add_argument("--config", help="Configuration overrides (JSON)")

    # Resume command
    resume_parser = subparsers.add_parser("resume", help="Resume an existing workflow")
    resume_parser.add_argument("workflow_id", help="Workflow ID to resume")
    resume_parser.add_argument("--from-stage", help="Stage to start from")
    resume_parser.add_argument("--to-stage", help="Stage to stop at")

    # Status command
    status_parser = subparsers.add_parser("status", help="Check workflow status")
    status_parser.add_argument("workflow_id", help="Workflow ID to check")

    # List command
    list_parser = subparsers.add_parser("list", help="List all workflows")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Create orchestrator
    orchestrator = WorkflowOrchestrator()

    try:
        if args.command == "start":
            # Parse config if provided
            config_overrides = None
            if args.config:
                import json

                config_overrides = json.loads(args.config)

            # Start workflow
            workflow_id = orchestrator.start_workflow(
                project_description=args.description,
                config_overrides=config_overrides,
                template_name=args.template,
                from_stage=args.from_stage,
                to_stage=args.to_stage,
            )

            print(f"✅ Workflow started successfully: {workflow_id}")

        elif args.command == "resume":
            # Resume workflow
            workflow_id = orchestrator.resume_workflow(
                workflow_id=args.workflow_id,
                from_stage=args.from_stage,
                to_stage=args.to_stage,
            )

            print(f"✅ Workflow resumed successfully: {workflow_id}")

        elif args.command == "status":
            # Get status using beautiful display
            try:
                state = WorkflowState.load(args.workflow_id)
                if not state:
                    orchestrator.display.show_error(f"Workflow {args.workflow_id} not found")
                    sys.exit(1)
                
                # Display beautiful status
                project_desc = state.inputs.project_description if state.inputs else "Multi-Agent Project"
                orchestrator.display.display_workflow_status(state, project_desc)
                
            except Exception as e:
                orchestrator.display.show_error(f"Failed to load workflow status: {e}")
                sys.exit(1)
        elif args.command == "list":
            # List workflows
            workflows = orchestrator.list_workflows()

            if not workflows:
                print("No workflows found")
            else:
                print(f"📋 Found {len(workflows)} workflows:")
                print()
                for workflow in workflows:
                    status_icon = "✅" if workflow["is_complete"] else "🔄"
                    print(f"{status_icon} {workflow['workflow_id']}")
                    print(
                        f"   Progress: {workflow['progress_percent']:.1f}% ({workflow['completed_stages']}/{workflow['total_stages']} stages)"
                    )
                    print(f"   Created: {workflow['created_at']}")
                    print()

    except Exception as e:
        logger.error(f"Command failed: {e}")
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
