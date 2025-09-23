"""Click-based CLI entry point for DeletePy Auth0 User Management Tool."""

import sys
from pathlib import Path

import click

from ..core.exceptions import AuthConfigError
from ..utils.display_utils import RED, RESET, YELLOW
from ..utils.rich_utils import install_rich_tracebacks
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
@click.argument("input_file", type=click.Path(exists=True))
@click.argument("env", type=click.Choice(["dev", "prod"]), default="dev")
def check_unblocked(input_file: str, env: str) -> None:
    """Check if specified users are unblocked."""
    handler = OperationHandler()
    handler.handle_check_unblocked(Path(input_file), env)


@cli.command()
@click.argument("input_file", type=click.Path(exists=True))
@click.argument("env", type=click.Choice(["dev", "prod"]), default="dev")
def check_domains(input_file: str, env: str) -> None:
    """Check email domains for the specified users."""
    handler = OperationHandler()
    handler.handle_check_domains(Path(input_file), env)


@cli.command()
@click.argument(
    "input_file",
    type=click.Path(exists=True, file_okay=True, dir_okay=False, readable=True),
)
@click.argument("env", type=click.Choice(["dev", "prod"]), default="dev")
@click.option("--connection", help="Filter by connection type")
def export_last_login(input_file: str, env: str, connection: str | None) -> None:
    """Export user last_login data to CSV."""
    if env == "prod":
        click.confirm(
            "You are about to export user data from production. Continue?",
            abort=True,
        )
    handler = OperationHandler()
    handler.handle_export_last_login(Path(input_file), env, connection)


@cli.command()
@click.argument(
    "input_file",
    type=click.Path(exists=True, file_okay=True, dir_okay=False, readable=True),
)
@click.argument("env", type=click.Choice(["dev", "prod"]), default="dev")
@click.option(
    "--dry-run", is_flag=True, help="Preview what would happen without executing"
)
def unlink_social_ids(input_file: str, env: str, dry_run: bool) -> None:
    """Unlink social identities from Auth0 users and delete detached accounts."""
    if env == "prod" and not dry_run:
        click.confirm(
            "You are about to unlink social identities and delete detached accounts in production. Continue?",
            abort=True,
        )
    handler = OperationHandler()
    handler.handle_unlink_social_ids(Path(input_file), env, dry_run)


@cli.command()
@click.argument(
    "input_file",
    type=click.Path(exists=True),
    default="ids.csv",
)
@click.argument("env", type=click.Choice(["dev", "prod"]), required=False)
@click.option(
    "--output-type",
    type=click.Choice(["username", "email", "user_id"]),
    default="user_id",
    help="Type of output desired",
)
def cleanup_csv(input_file: str, env: str | None, output_type: str) -> None:
    """Process CSV file and extract/convert user identifiers."""
    from ..utils.csv_utils import (
        extract_identifiers_from_csv,
        write_identifiers_to_file,
    )

    try:
        identifiers = extract_identifiers_from_csv(
            filename=str(Path(input_file)), env=env, output_type=output_type
        )
        if identifiers:
            output_file = f"cleaned_{Path(input_file).name}"
            success = write_identifiers_to_file(identifiers, output_file)
            if success:
                click.echo(
                    f"Successfully processed {len(identifiers)} identifiers to {output_file}"
                )
            else:
                click.echo(f"Error writing output file: {output_file}")
                sys.exit(1)
        else:
            click.echo("No identifiers found in input file")
            sys.exit(1)
    except Exception as e:
        click.echo(f"Error processing CSV file: {e}")
        sys.exit(1)


@cli.group()
def users() -> None:
    """User management operations."""


@users.command()
@click.argument(
    "input_file",
    type=click.Path(exists=True, file_okay=True, dir_okay=False, readable=True),
)
@click.argument("env", type=click.Choice(["dev", "prod"]), default="dev")
@click.option(
    "--dry-run", is_flag=True, help="Preview what would happen without executing"
)
def block(input_file: str, env: str, dry_run: bool) -> None:
    """Block the specified users."""
    if env == "prod" and not dry_run:
        click.confirm(
            "You are about to block users in production. Continue?",
            abort=True,
        )
    handler = OperationHandler()
    handler.handle_user_operations(Path(input_file), env, "block", dry_run)


@users.command()
@click.argument(
    "input_file",
    type=click.Path(exists=True, file_okay=True, dir_okay=False, readable=True),
)
@click.argument("env", type=click.Choice(["dev", "prod"]), default="dev")
@click.option(
    "--dry-run", is_flag=True, help="Preview what would happen without executing"
)
def delete(input_file: str, env: str, dry_run: bool) -> None:
    """Delete the specified users."""
    if env == "prod" and not dry_run:
        click.confirm(
            "You are about to delete users in production. Continue?",
            abort=True,
        )
    handler = OperationHandler()
    handler.handle_user_operations(Path(input_file), env, "delete", dry_run)


@users.command()
@click.argument(
    "input_file",
    type=click.Path(exists=True, file_okay=True, dir_okay=False, readable=True),
)
@click.argument("env", type=click.Choice(["dev", "prod"]), default="dev")
@click.option(
    "--dry-run", is_flag=True, help="Preview what would happen without executing"
)
def revoke_grants_only(input_file: str, env: str, dry_run: bool) -> None:
    """Revoke grants and sessions for the specified users."""
    if env == "prod" and not dry_run:
        click.confirm(
            "You are about to revoke grants and sessions in production. Continue?",
            abort=True,
        )
    handler = OperationHandler()
    handler.handle_user_operations(Path(input_file), env, "revoke-grants-only", dry_run)


@cli.group()
def checkpoint() -> None:
    """Checkpoint management operations."""


@checkpoint.command()
@click.option(
    "--operation-type",
    type=click.Choice(
        [
            "export-last-login",
            "batch-delete",
            "batch-block",
            "batch-revoke-grants",
            "social-unlink",
            "check-unblocked",
            "check-domains",
        ]
    ),
    help="Filter by operation type",
)
@click.option(
    "--status",
    type=click.Choice(["active", "completed", "failed", "cancelled"]),
    help="Filter by checkpoint status",
)
@click.option("--env", type=click.Choice(["dev", "prod"]), help="Filter by environment")
@click.option("--details", is_flag=True, help="Show detailed checkpoint information")
def list(
    operation_type: str | None, status: str | None, env: str | None, details: bool
) -> None:
    """List all checkpoints with optional filters."""
    handler = OperationHandler()
    handler.handle_list_checkpoints(operation_type, status, env, details)


@checkpoint.command()
@click.argument("checkpoint_id", type=str)
@click.option(
    "--input-file",
    type=click.Path(exists=True),
    help="Override input file from checkpoint (optional)",
)
def resume(checkpoint_id: str, input_file: str | None) -> None:
    """Resume an operation from a checkpoint."""
    handler = OperationHandler()
    handler.handle_resume_checkpoint(
        checkpoint_id, Path(input_file) if input_file else None
    )


@checkpoint.command()
@click.option(
    "--all", "clean_all", is_flag=True, help="Clean all checkpoints (use with caution)"
)
@click.option("--failed", is_flag=True, help="Clean only failed checkpoints")
@click.option("--completed", is_flag=True, help="Clean all completed checkpoints")
@click.option(
    "--days-old",
    type=int,
    default=30,
    help="Clean checkpoints older than specified days (default: 30)",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Preview what would be cleaned without actually deleting",
)
def clean(
    clean_all: bool, failed: bool, completed: bool, days_old: int, dry_run: bool
) -> None:
    """Clean up old, failed, or completed checkpoints."""
    handler = OperationHandler()
    handler.handle_clean_checkpoints(clean_all, failed, completed, days_old, dry_run)


@checkpoint.command()
@click.argument("checkpoint_id", type=str)
@click.option("--confirm", is_flag=True, help="Skip confirmation prompt")
def delete_checkpoint(checkpoint_id: str, confirm: bool) -> None:
    """Delete a specific checkpoint."""
    handler = OperationHandler()
    handler.handle_delete_checkpoint(checkpoint_id, confirm)


@checkpoint.command()
@click.argument("checkpoint_id", type=str)
def details(checkpoint_id: str) -> None:
    """Show detailed information about a specific checkpoint."""
    handler = OperationHandler()
    handler.handle_checkpoint_details(checkpoint_id)


def main() -> None:
    """Main entry point for the CLI application."""
    try:
        # Enable pretty tracebacks
        install_rich_tracebacks()
        cli()
    except KeyboardInterrupt:
        click.echo(f"\n{YELLOW}Operation interrupted by user.{RESET}")
        sys.exit(0)
    except Exception as e:
        click.echo(f"{RED}Unexpected error: {e}{RESET}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
