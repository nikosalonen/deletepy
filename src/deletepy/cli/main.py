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
def find_social_ids(input_file: Path, env: str) -> None:
    """Find users by social media IDs from identities."""
    handler = OperationHandler()
    handler.handle_find_social_ids(input_file, env)


@cli.group()
def users() -> None:
    """User management operations."""
    pass


@users.command()
@click.argument("input_file", type=click.Path(exists=True, path_type=Path))
@click.argument("env", type=click.Choice(["dev", "prod"]), default="dev")
def block(input_file: Path, env: str) -> None:
    """Block the specified users."""
    handler = OperationHandler()
    handler.handle_user_operations(input_file, env, "block")


@users.command()
@click.argument("input_file", type=click.Path(exists=True, path_type=Path))
@click.argument("env", type=click.Choice(["dev", "prod"]), default="dev")
def delete(input_file: Path, env: str) -> None:
    """Delete the specified users."""
    handler = OperationHandler()
    handler.handle_user_operations(input_file, env, "delete")


@users.command()
@click.argument("input_file", type=click.Path(exists=True, path_type=Path))
@click.argument("env", type=click.Choice(["dev", "prod"]), default="dev")
def revoke_grants_only(input_file: Path, env: str) -> None:
    """Revoke grants and sessions for the specified users."""
    handler = OperationHandler()
    handler.handle_user_operations(input_file, env, "revoke-grants-only")


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
