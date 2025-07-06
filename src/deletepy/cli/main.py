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
def unlink_social_ids(input_file: Path, env: str) -> None:
    """Unlink social identities from Auth0 users and delete detached accounts."""
    handler = OperationHandler()
    handler.handle_unlink_social_ids(input_file, env)


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
@click.option("--validation-level", type=click.Choice(["strict", "standard", "lenient"]), default="standard", help="Validation strictness level")
@click.option("--skip-validation", is_flag=True, help="Skip smart validation checks")
def block(input_file: Path, env: str, validation_level: str, skip_validation: bool) -> None:
    """Block the specified users."""
    handler = OperationHandler()
    handler.handle_user_operations(input_file, env, "block", validation_level, skip_validation)


@users.command()
@click.argument("input_file", type=click.Path(exists=True, path_type=Path))
@click.argument("env", type=click.Choice(["dev", "prod"]), default="dev")
@click.option("--validation-level", type=click.Choice(["strict", "standard", "lenient"]), default="standard", help="Validation strictness level")
@click.option("--skip-validation", is_flag=True, help="Skip smart validation checks")
def delete(input_file: Path, env: str, validation_level: str, skip_validation: bool) -> None:
    """Delete the specified users."""
    handler = OperationHandler()
    handler.handle_user_operations(input_file, env, "delete", validation_level, skip_validation)


@users.command()
@click.argument("input_file", type=click.Path(exists=True, path_type=Path))
@click.argument("env", type=click.Choice(["dev", "prod"]), default="dev")
@click.option("--validation-level", type=click.Choice(["strict", "standard", "lenient"]), default="standard", help="Validation strictness level")
@click.option("--skip-validation", is_flag=True, help="Skip smart validation checks")
def revoke_grants_only(input_file: Path, env: str, validation_level: str, skip_validation: bool) -> None:
    """Revoke grants and sessions for the specified users."""
    handler = OperationHandler()
    handler.handle_user_operations(input_file, env, "revoke-grants-only", validation_level, skip_validation)


@cli.command()
@click.argument("input_file", type=click.Path(exists=True, path_type=Path))
@click.argument("env", type=click.Choice(["dev", "prod"]), default="dev")
@click.argument("operation", type=click.Choice(["block", "delete", "revoke-grants-only"]))
@click.option("--validation-level", type=click.Choice(["strict", "standard", "lenient"]), default="standard", help="Validation strictness level")
def validate(input_file: Path, env: str, operation: str, validation_level: str) -> None:
    """Run validation analysis on user data without executing operations."""
    handler = OperationHandler()
    handler.handle_validation_only(input_file, env, operation, validation_level)


@cli.command(name="auto-fix")
@click.argument("input_file", type=click.Path(exists=True, path_type=Path))
@click.argument("env", type=click.Choice(["dev", "prod"]), default="dev")
@click.argument("operation", type=click.Choice(["block", "delete", "revoke-grants-only"]))
@click.option("--validation-level", type=click.Choice(["strict", "standard", "lenient"]), default="standard", help="Validation strictness level")
def auto_fix(input_file: Path, env: str, operation: str, validation_level: str) -> None:
    """Automatically fix validation issues where possible."""
    handler = OperationHandler()
    handler.handle_auto_fix_validation(input_file, env, operation, validation_level)


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
