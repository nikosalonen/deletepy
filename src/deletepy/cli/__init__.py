"""CLI module for Auth0 user management."""

from .csv_commands import handle_csv_command, parse_csv_args, print_csv_usage
from .csv_commands import main as csv_main
from .validators import (
    validate_args,
    validate_connection_type,
    validate_environment,
    validate_file_path_argument,
    validate_operation,
    validate_user_id_list,
)

__all__ = [
    # CSV commands
    "csv_main",
    "parse_csv_args",
    "print_csv_usage",
    "handle_csv_command",
    # Validators
    "validate_args",
    "validate_connection_type",
    "validate_environment",
    "validate_file_path_argument",
    "validate_operation",
    "validate_user_id_list",
]
