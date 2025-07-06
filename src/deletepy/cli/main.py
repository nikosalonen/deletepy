"""Click-based CLI entry point for DeletePy Auth0 User Management Tool."""

import sys
from pathlib import Path

import click

from ..core.exceptions import AuthConfigError
from ..utils.display_utils import RED, RESET, YELLOW
from .commands import OperationHandler


@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx: click.Context) -> None:
    """DeletePy - Auth0 User Management Tool for bulk operations."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@cli.command()
@click.argument("env", type=click.Choice(["dev", "prod"]), default="dev")
@click.option("--test-api", is_flag=True, help="Test API access")
def doctor(env: str, test_api: bool) -> None:
    """Test Auth0 credentials and API access."""
    try:
        handler = OperationHandler()
        success = handler.handle_doctor(env, test_api)
        if not success:
            sys.exit(1)
    except AuthConfigError as e:
        click.echo(f"Authentication configuration error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("input_file", type=click.Path(exists=True, path_type=Path))
@click.argument("env", type=click.Choice(["dev", "prod"]), default="dev")
def check_unblocked(input_file: Path, env: str) -> None:
    """Check if specified users are unblocked."""
    handler = OperationHandler()
    handler.handle_check_unblocked(input_file, env)


@cli.command()
@click.argument("input_file", type=click.Path(exists=True, path_type=Path))
@click.argument("env", type=click.Choice(["dev", "prod"]), default="dev")
def check_domains(input_file: Path, env: str) -> None:
    """Check email domains for the specified users."""
    handler = OperationHandler()
    handler.handle_check_domains(input_file, env)


@cli.command()
@click.argument("input_file", type=click.Path(exists=True, path_type=Path))
@click.argument("env", type=click.Choice(["dev", "prod"]), default="dev")
@click.option("--connection", help="Filter by connection type")
def export_last_login(input_file: Path, env: str, connection: str | None) -> None:
    """Export user last_login data to CSV."""
    handler = OperationHandler()
    handler.handle_export_last_login(input_file, env, connection)


@cli.command()
@click.argument("input_file", type=click.Path(exists=True, path_type=Path))
@click.argument("env", type=click.Choice(["dev", "prod"]), default="dev")
@click.option("--dry-run", is_flag=True, help="Preview what would happen without executing")
def unlink_social_ids(input_file: Path, env: str, dry_run: bool) -> None:
    """Unlink social identities from Auth0 users and delete detached accounts."""
    handler = OperationHandler()
    handler.handle_unlink_social_ids(input_file, env, dry_run)


@cli.command()
@click.argument(
    "input_file", type=click.Path(exists=True, path_type=Path), default="ids.csv"
)
@click.argument("env", type=click.Choice(["dev", "prod"]), required=False)
@click.option(
    "--output-type",
    type=click.Choice(["username", "email", "user_id"]),
    default="user_id",
    help="Type of output desired",
)
def cleanup_csv(input_file: Path, env: str | None, output_type: str) -> None:
    """Process CSV file and extract/convert user identifiers."""
    from .csv_commands import process_csv_file

    success = process_csv_file(str(input_file), env, output_type, interactive=True)
    if not success:
        sys.exit(1)


@cli.group()
def users() -> None:
    """User management operations."""
    pass


@users.command()
@click.argument("input_file", type=click.Path(exists=True, path_type=Path))
@click.argument("env", type=click.Choice(["dev", "prod"]), default="dev")
@click.option("--dry-run", is_flag=True, help="Preview what would happen without executing")
@click.option("--no-checkpoint", is_flag=True, help="Disable checkpoint creation for this operation")
def block(input_file: Path, env: str, dry_run: bool, no_checkpoint: bool) -> None:
    """Block the specified users."""
    handler = OperationHandler()
    handler.handle_user_operations(input_file, env, "block", dry_run, checkpoint=not no_checkpoint)


@users.command()
@click.argument("input_file", type=click.Path(exists=True, path_type=Path))
@click.argument("env", type=click.Choice(["dev", "prod"]), default="dev")
@click.option("--dry-run", is_flag=True, help="Preview what would happen without executing")
@click.option("--no-checkpoint", is_flag=True, help="Disable checkpoint creation for this operation")
def delete(input_file: Path, env: str, dry_run: bool, no_checkpoint: bool) -> None:
    """Delete the specified users."""
    handler = OperationHandler()
    handler.handle_user_operations(input_file, env, "delete", dry_run, checkpoint=not no_checkpoint)


@users.command()
@click.argument("input_file", type=click.Path(exists=True, path_type=Path))
@click.argument("env", type=click.Choice(["dev", "prod"]), default="dev")
@click.option("--dry-run", is_flag=True, help="Preview what would happen without executing")
@click.option("--no-checkpoint", is_flag=True, help="Disable checkpoint creation for this operation")
def revoke_grants_only(input_file: Path, env: str, dry_run: bool, no_checkpoint: bool) -> None:
    """Revoke grants and sessions for the specified users."""
    handler = OperationHandler()
    handler.handle_user_operations(input_file, env, "revoke-grants-only", dry_run, checkpoint=not no_checkpoint)


@cli.command()
@click.argument("operation_id", required=True)
@click.option("--env", type=click.Choice(["dev", "prod"]), help="Override environment from checkpoint")
def resume(operation_id: str, env: str | None) -> None:
    """Resume an interrupted operation from checkpoint."""
    handler = OperationHandler()
    handler.handle_resume_operation(operation_id)


@cli.command(name="list-checkpoints")
@click.option("--type", "operation_type", help="Filter by operation type")
def list_checkpoints(operation_type: str | None) -> None:
    """List all available operation checkpoints."""
    handler = OperationHandler()
    handler.handle_list_checkpoints(operation_type)


@cli.command(name="cleanup-checkpoints")
@click.option("--days", default=7, help="Number of days to keep checkpoints (default: 7)")
@click.option("--yes", is_flag=True, help="Skip confirmation prompt")
def cleanup_checkpoints(days: int, yes: bool) -> None:
    """Clean up old checkpoint files."""
    handler = OperationHandler()
    handler.handle_cleanup_checkpoints(days, confirm=not yes)


def main() -> None:
    """Main entry point for the CLI application."""
    try:
        cli()
    except KeyboardInterrupt:
        click.echo(f"\n{YELLOW}Operation interrupted by user.{RESET}")
        sys.exit(0)
    except Exception as e:
        click.echo(f"{RED}Unexpected error: {e}{RESET}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
