@cli.command()
@click.option("--config", default="config/models.yaml", help="Model configuration file")
def list_models(config: str):
    """List all configured models."""
    try:
        model_config_manager = ModelConfigManager(config)
    except:
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
@click.option("--config", default="config/models.yaml", help="Model configuration file")
@click.option("--output", default="config/models_export.yaml", help="Output file")
def export_config(config: str, output: str):
    """Export current model configuration."""
    try:
        model_config_manager = ModelConfigManager(config)
    except:
        model_config_manager = ModelConfigManager()

    model_config_manager.save_to_file(output)
    click.echo(f"Configuration exported to {output}")


if __name__ == "__main__":
    cli()
