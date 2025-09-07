#!/usr/bin/env python3
"""
Enhanced CLI Output Manager for Workflow System

Provides beautiful terminal output using the rich library including:
- Progress bars for each stage
- Color-coded status indicators
- Real-time progress updates
- Structured status displays
"""

import logging
from datetime import datetime
from typing import Any

from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

try:
    # Try relative import first (when used as module)
    from .workflow_state import StageStatus, WorkflowState
except ImportError:
    # Fallback to direct import (when run as standalone script)
    from workflow_state import StageStatus, WorkflowState


class WorkflowProgressDisplay:
    """Manages rich terminal output for workflow progress."""

    def __init__(self):
        self.console = Console()
        self.progress = None
        self.live = None
        self.stage_tasks = {}  # Maps stage names to progress task IDs
        self.current_layout = None

        # Status icons and colors
        self.status_icons = {
            StageStatus.PENDING: "⏳",
            StageStatus.RUNNING: "🔄",
            StageStatus.COMPLETED: "✅",
            StageStatus.FAILED: "❌",
            StageStatus.SKIPPED: "⏭️",
            StageStatus.PAUSED: "⏸️",
        }

        self.status_colors = {
            StageStatus.PENDING: "yellow",
            StageStatus.RUNNING: "blue",
            StageStatus.COMPLETED: "green",
            StageStatus.FAILED: "red",
            StageStatus.SKIPPED: "dim",
            StageStatus.PAUSED: "orange3",
        }

    def setup_logging(self, level: int = logging.INFO):
        """Set up rich logging handler."""
        # Remove default handlers
        logging.getLogger().handlers.clear()

        # Add rich handler
        rich_handler = RichHandler(
            console=self.console,
            show_path=False,
            markup=True,
            rich_tracebacks=True,
        )
        rich_handler.setFormatter(logging.Formatter("%(message)s"))

        # Configure root logger
        logging.basicConfig(
            level=level,
            handlers=[rich_handler],
            format="%(message)s",
        )

    def create_workflow_header(self, workflow_id: str, project_desc: str) -> Panel:
        """Create header panel for workflow display."""
        header_text = Text()
        header_text.append("🚀 Enhanced Multi-Agent Workflow\n", style="bold magenta")
        header_text.append(f"Workflow ID: {workflow_id}\n", style="cyan")
        header_text.append(f"Project: {project_desc}", style="white")

        return Panel(
            header_text,
            title="[bold blue]Workflow Status[/bold blue]",
            expand=False,
            border_style="blue",
        )

    def create_stage_progress_table(self, state: WorkflowState) -> Table:
        """Create table showing progress of all stages."""
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Stage", style="white", width=25)
        table.add_column("Status", justify="center", width=10)
        table.add_column("Progress", width=15)
        table.add_column("Duration", justify="right", width=12)
        table.add_column("Output Files", width=20)

        for stage_name, stage in state.stages.items():
            # Status icon and text
            icon = self.status_icons.get(stage.status, "❓")
            status_text = Text(f"{icon} {stage.status.value.title()}")
            status_text.stylize(self.status_colors.get(stage.status, "white"))

            # Progress bar
            if stage.status == StageStatus.COMPLETED:
                progress_text = "[green]████████[/green] 100%"
            elif stage.status == StageStatus.RUNNING:
                progress_text = "[blue]████░░░░[/blue] 50%"  # Approximate
            elif stage.status == StageStatus.FAILED:
                progress_text = "[red]██░░░░░░[/red] Failed"
            elif stage.status == StageStatus.SKIPPED:
                progress_text = "[dim]▓▓▓▓▓▓▓▓[/dim] Skipped"
            elif stage.status == StageStatus.PAUSED:
                progress_text = "[orange3]██⏸️░░░░░[/orange3] Paused"
            else:
                progress_text = "[dim]░░░░░░░░[/dim] 0%"

            # Duration
            duration = ""
            if stage.started_at and stage.completed_at:
                delta = stage.completed_at - stage.started_at
                duration = f"{delta.total_seconds():.1f}s"
            elif stage.started_at:
                delta = datetime.utcnow() - stage.started_at.replace(tzinfo=None)
                duration = f"{delta.total_seconds():.1f}s"

            # Output files
            files_text = ""
            if stage.output_files:
                if len(stage.output_files) <= 2:
                    files_text = ", ".join(stage.output_files)
                else:
                    files_text = (
                        f"{stage.output_files[0]}, ... (+{len(stage.output_files)-1})"
                    )

            table.add_row(
                stage_name.replace("_", " ").title(),
                status_text,
                progress_text,
                duration,
                files_text[:20] + "..." if len(files_text) > 20 else files_text,
            )

        return table

    def create_metrics_panel(self, state: WorkflowState) -> Panel:
        """Create panel showing workflow metrics."""
        summary = state.get_summary()

        metrics_text = Text()
        metrics_text.append("📊 Workflow Metrics\n\n", style="bold cyan")
        metrics_text.append(
            f"Progress: {summary['progress_percent']:.1f}% ", style="white"
        )
        metrics_text.append(
            f"({summary['completed_stages']}/{summary['total_stages']} stages)\n",
            style="dim",
        )
        metrics_text.append("Status: ", style="white")

        if summary["is_complete"]:
            metrics_text.append("Complete ✅\n", style="bold green")
        elif summary["failed_stages"] > 0:
            metrics_text.append("Has Failures ❌\n", style="bold red")
        else:
            metrics_text.append("In Progress 🔄\n", style="bold blue")

        metrics_text.append(f"Created: {summary['created_at'][:19]}\n", style="dim")
        metrics_text.append(f"Updated: {summary['updated_at'][:19]}", style="dim")

        return Panel(
            metrics_text,
            title="[bold cyan]Metrics[/bold cyan]",
            expand=False,
            border_style="cyan",
        )

    def display_workflow_status(self, state: WorkflowState, project_desc: str = None):
        """Display complete workflow status in a beautiful format."""
        self.console.clear()

        # Create header
        header = self.create_workflow_header(
            state.workflow_id, project_desc or "Multi-Agent Project"
        )
        self.console.print(header)
        self.console.print()

        # Create stage progress table
        stage_table = self.create_stage_progress_table(state)
        self.console.print(
            Panel(
                stage_table,
                title="[bold green]Stage Progress[/bold green]",
                border_style="green",
            )
        )
        self.console.print()

        # Create metrics panel
        metrics_panel = self.create_metrics_panel(state)
        self.console.print(metrics_panel)

    def show_stage_start(self, stage_name: str, description: str):
        """Display stage start notification."""
        stage_display = stage_name.replace("_", " ").title()

        panel = Panel(
            f"[bold blue]🚀 Starting Stage: {stage_display}[/bold blue]\n"
            f"[dim]{description}[/dim]",
            border_style="blue",
            expand=False,
        )

        self.console.print()
        self.console.print(panel)
        self.console.print()

    def show_stage_complete(self, stage_name: str, result: dict[str, Any]):
        """Display stage completion notification."""
        stage_display = stage_name.replace("_", " ").title()

        # Create completion summary
        summary_text = f"[bold green]✅ Completed: {stage_display}[/bold green]\n"

        if result.get("output_files"):
            summary_text += f"[dim]Files created: {len(result['output_files'])}[/dim]\n"

        if result.get("metrics"):
            metrics = result["metrics"]
            if "duration" in metrics:
                summary_text += f"[dim]Duration: {metrics['duration']:.1f}s[/dim]\n"

            # Show key metrics
            for key, value in metrics.items():
                if key != "duration":
                    summary_text += (
                        f"[dim]{key.replace('_', ' ').title()}: {value}[/dim]\n"
                    )

        if result.get("next_actions"):
            summary_text += "\n[yellow]Next Actions:[/yellow]\n"
            for action in result["next_actions"]:
                summary_text += f"[dim]• {action}[/dim]\n"

        panel = Panel(summary_text.rstrip(), border_style="green", expand=False)

        self.console.print(panel)
        self.console.print()

    def show_stage_failure(self, stage_name: str, error_message: str):
        """Display stage failure notification."""
        stage_display = stage_name.replace("_", " ").title()

        panel = Panel(
            f"[bold red]❌ Failed: {stage_display}[/bold red]\n"
            f"[dim]{error_message}[/dim]",
            border_style="red",
            expand=False,
        )

        self.console.print(panel)
        self.console.print()

    def show_workflow_complete(self, state: WorkflowState):
        """Display workflow completion celebration."""
        summary = state.get_summary()

        celebration_text = Text()
        celebration_text.append("🎉 WORKFLOW COMPLETED! 🎉\n\n", style="bold green")
        celebration_text.append(
            f"Successfully completed all {summary['total_stages']} stages\n",
            style="white",
        )
        celebration_text.append(
            f"Total time: {summary['updated_at']} - {summary['created_at']}\n",
            style="dim",
        )
        celebration_text.append("Ready for deployment! 🚀", style="bold cyan")

        panel = Panel(
            celebration_text,
            title="[bold green]SUCCESS[/bold green]",
            border_style="green",
            expand=False,
        )

        self.console.print()
        self.console.print(panel)
        self.console.print()

    def show_error(self, message: str):
        """Display error message."""
        self.console.print(f"[bold red]❌ Error: {message}[/bold red]")

    def show_info(self, message: str):
        """Display info message."""
        self.console.print(f"[blue]ℹ️  {message}[/blue]")

    def show_success(self, message: str):
        """Display success message."""
        self.console.print(f"[green]✅ {message}[/green]")


class WorkflowLogger:
    """Enhanced logger with rich formatting for workflow operations."""

    def __init__(self, name: str = "workflow"):
        self.logger = logging.getLogger(name)
        self.display = WorkflowProgressDisplay()

        # Set up rich logging
        self.display.setup_logging()

    def info(self, message: str, extra: dict[str, Any] = None):
        """Log info message with rich formatting."""
        self.logger.info(f"[blue]ℹ️[/blue] {message}", extra=extra)

    def success(self, message: str, extra: dict[str, Any] = None):
        """Log success message with rich formatting."""
        self.logger.info(f"[green]✅[/green] {message}", extra=extra)

    def warning(self, message: str, extra: dict[str, Any] = None):
        """Log warning message with rich formatting."""
        self.logger.warning(f"[yellow]⚠️[/yellow] {message}", extra=extra)

    def error(self, message: str, extra: dict[str, Any] = None):
        """Log error message with rich formatting."""
        self.logger.error(f"[red]❌[/red] {message}", extra=extra)

    def stage_start(self, stage_name: str, description: str):
        """Log stage start with rich formatting."""
        stage_display = stage_name.replace("_", " ").title()
        self.logger.info(
            f"[bold blue]🚀 Starting {stage_display}[/bold blue]: {description}"
        )

    def stage_complete(self, stage_name: str, duration: float = None):
        """Log stage completion with rich formatting."""
        stage_display = stage_name.replace("_", " ").title()
        duration_text = f" ({duration:.1f}s)" if duration else ""
        self.logger.info(
            f"[bold green]✅ Completed {stage_display}[/bold green]{duration_text}"
        )

    def stage_failed(self, stage_name: str, error: str):
        """Log stage failure with rich formatting."""
        stage_display = stage_name.replace("_", " ").title()
        self.logger.error(f"[bold red]❌ Failed {stage_display}[/bold red]: {error}")


# Singleton instances for easy import
progress_display = WorkflowProgressDisplay()
workflow_logger = WorkflowLogger()
