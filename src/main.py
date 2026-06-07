"""TierFlow CLI entrypoint."""

import json
import os

import click
from dotenv import load_dotenv

from src.config.models import ModelConfigManager
from src.orchestration import ConfigurableOrchestrator
from src.utils.logger import get_logger

load_dotenv()

logger = get_logger(__name__)

DEFAULT_MODEL_CONFIG = "config/models.yaml"


@click.group()
def cli():
    """TierFlow — two-tier agent workflow system."""


@cli.command()
@click.argument("task")
@click.option("--model-config", "model_config", default=DEFAULT_MODEL_CONFIG, help="Model configuration file")
@click.option("--max-iterations", default=10, type=int, help="Maximum workflow iterations")
@click.option("--daemon", is_flag=True, help="Run continuously for long-running operation")
def run(task: str, model_config: str, max_iterations: int, daemon: bool):
    """Run a workflow for the given TASK."""
    if not os.path.exists(model_config):
        click.echo(f"Model config not found: {model_config}, using defaults")
        model_config = None

    orchestrator = ConfigurableOrchestrator(model_config_path=model_config)

    try:
        models = orchestrator._get_models_used()
        click.echo("Models in use:")
        click.echo(f"  planner:      {models['planner']}")
        click.echo(f"  orchestrator: {models['orchestrator']}")
        click.echo(f"  reviewer:     {models['reviewer']}")
        click.echo(f"  executor:     {', '.join(models['executor_chain'])}")
        click.echo()

        result = orchestrator.execute_workflow(task, max_iterations=max_iterations)

        click.echo(f"\nWorkflow {result['workflow_id']}")
        click.echo(f"Status:     {result['status']}")
        click.echo(f"Iterations: {result['iterations']}")
        if "decision" in result:
            m = result["decision"]["metrics"]
            click.echo(
                f"Scores:     overall={m['overall']:.2f} correctness={m['correctness']:.2f} "
                f"completeness={m['completeness']:.2f} quality={m['quality']:.2f}"
            )
        click.echo("\nResults:")
        for r in result.get("results", []):
            if r.get("result"):
                preview = r["result"][:500]
                click.echo(f"\n[{r.get('executor', '?')}] {r['subtask']}")
                click.echo(preview)
            else:
                click.echo(f"\n[FAILED] {r.get('subtask')}: {r.get('error')}")
    finally:
        orchestrator.close()


@cli.command()
@click.argument("workflow_id")
@click.option("--model-config", "model_config", default=DEFAULT_MODEL_CONFIG)
def status(workflow_id: str, model_config: str):
    """Show status for a workflow by WORKFLOW_ID."""
    orchestrator = ConfigurableOrchestrator(
        model_config_path=model_config if os.path.exists(model_config) else None
    )
    try:
        wf = orchestrator.state_manager.get_workflow(workflow_id)
        if not wf:
            click.echo(f"Workflow not found: {workflow_id}")
            return
        click.echo(f"Workflow:   {wf.workflow_id}")
        click.echo(f"Status:     {wf.status}")
        click.echo(f"Iterations: {wf.current_iteration}/{wf.max_iterations}")
        click.echo(f"Task:       {wf.original_task}")
    finally:
        orchestrator.close()


@cli.command()
@click.option("--model-config", "model_config", default=DEFAULT_MODEL_CONFIG)
def metrics(model_config: str):
    """Show API client metrics."""
    orchestrator = ConfigurableOrchestrator(
        model_config_path=model_config if os.path.exists(model_config) else None
    )
    try:
        click.echo(json.dumps(orchestrator.get_metrics(), indent=2))
    finally:
        orchestrator.close()


@cli.command()
@click.option("--config", default=DEFAULT_MODEL_CONFIG, help="Model configuration file")
def list_models(config: str):
    """List all configured models."""
    try:
        model_config_manager = ModelConfigManager(config)
    except Exception:
        model_config_manager = ModelConfigManager()

    click.echo("Configured Models:\n")

    for model_name, model_config in model_config_manager.models.items():
        click.echo(f"  {model_name}")
        click.echo(f"    Provider: {model_config.provider.value}")
        click.echo(f"    Priority: {model_config.priority}")
        click.echo(f"    Enabled: {model_config.enabled}")
        click.echo(f"    Permissions:")
        click.echo(f"      - Plan: {model_config.permissions.can_plan}")
        click.echo(f"      - Execute: {model_config.permissions.can_execute}")
        click.echo(f"      - Review: {model_config.permissions.can_review}")
        click.echo(f"      - Evaluate: {model_config.permissions.can_evaluate}")
        click.echo(f"    Rate Limit: {model_config.permissions.rate_limit}/min")
        click.echo(f"    Cost: ${model_config.cost_per_1k_tokens}/1k tokens")
        click.echo()

    click.echo("\nRole Configurations:\n")

    for role, role_config in model_config_manager.role_configs.items():
        click.echo(f"  {role.value}:")
        click.echo(f"    Primary: {role_config.primary_model}")
        click.echo(f"    Fallbacks: {', '.join(role_config.fallback_models)}")
        click.echo(f"    Auto Fallback: {role_config.auto_fallback}")
        click.echo()


@cli.command()
@click.option("--config", default=DEFAULT_MODEL_CONFIG, help="Model configuration file")
@click.option("--output", default="config/models_export.yaml", help="Output file")
def export_config(config: str, output: str):
    """Export current model configuration."""
    try:
        model_config_manager = ModelConfigManager(config)
    except Exception:
        model_config_manager = ModelConfigManager()

    model_config_manager.save_to_file(output)
    click.echo(f"Configuration exported to {output}")


if __name__ == "__main__":
    cli()
