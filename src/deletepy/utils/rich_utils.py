"""Rich utilities: shared console, themes, and helpers for pretty output."""

from __future__ import annotations

from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.theme import Theme
from rich.traceback import install as rich_traceback_install

_console: Console | None = None

# Custom theme for consistent styling
DELETEPY_THEME = Theme(
    {
        "info": "cyan",
        "warning": "yellow",
        "error": "bold red",
        "success": "bold green",
        "muted": "grey62",
        "header": "bold blue",
        "user_id": "cyan",
        "operation": "magenta",
        "count": "bold white",
    }
)


def get_console() -> Console:
    """Return a shared Rich Console instance.

    Creates the console on first use with a pleasant default theme.
    """
    global _console
    if _console is None:
        _console = Console(theme=DELETEPY_THEME, highlight=False, soft_wrap=False)
    return _console


def install_rich_tracebacks() -> None:
    """Enable rich tracebacks globally for nicer error output."""
    rich_traceback_install(show_locals=False, word_wrap=True, suppress=["click"])


# =============================================================================
# Styled Output Functions
# =============================================================================


def print_info(message: str) -> None:
    """Print an info message with cyan styling."""
    get_console().print(f"[info]{message}[/info]")


def print_success(message: str) -> None:
    """Print a success message with green styling and checkmark."""
    get_console().print(f"[success]✓[/success] {message}")


def print_warning(message: str) -> None:
    """Print a warning message with yellow styling."""
    get_console().print(f"[warning]⚠ {message}[/warning]")


def print_error(message: str) -> None:
    """Print an error message with red styling."""
    get_console().print(f"[error]✗ {message}[/error]")


def print_header(title: str) -> None:
    """Print a section header with a rule."""
    from rich.rule import Rule

    get_console().print(Rule(f"[header]{title}[/header]"))


# =============================================================================
# Tables and Panels
# =============================================================================


def create_table(
    title: str | None = None,
    columns: list[str] | None = None,
    show_header: bool = True,
    box_style: str = "rounded",
) -> Table:
    """Create a Rich table with consistent styling.

    Args:
        title: Optional table title
        columns: List of column names to add
        show_header: Whether to show column headers
        box_style: Box style (rounded, simple, minimal, etc.)

    Returns:
        Configured Rich Table instance
    """
    from rich import box

    box_map = {
        "rounded": box.ROUNDED,
        "simple": box.SIMPLE,
        "minimal": box.MINIMAL,
        "square": box.SQUARE,
        "heavy": box.HEAVY,
    }

    table = Table(
        title=title,
        show_header=show_header,
        header_style="bold",
        box=box_map.get(box_style, box.ROUNDED),
    )

    if columns:
        for col in columns:
            table.add_column(col)

    return table


def print_table(table: Table) -> None:
    """Print a Rich table to the console."""
    get_console().print(table)


def print_panel(
    content: str,
    title: str | None = None,
    style: str = "info",
    expand: bool = False,
) -> None:
    """Print content in a bordered panel.

    Args:
        content: Text content for the panel
        title: Optional panel title
        style: Border style (info, warning, error, success)
        expand: Whether to expand to full width
    """
    get_console().print(Panel(content, title=title, border_style=style, expand=expand))


def print_dict(data: dict[str, Any], title: str | None = None) -> None:
    """Pretty-print a dictionary as a table.

    Args:
        data: Dictionary to display
        title: Optional title for the table
    """
    table = create_table(title=title, columns=["Key", "Value"])
    for key, value in data.items():
        table.add_row(str(key), str(value))
    print_table(table)


# =============================================================================
# Summary and Stats Display
# =============================================================================


def print_summary(
    title: str,
    stats: dict[str, int | float | str],
    style: str = "success",
) -> None:
    """Print an operation summary with statistics.

    Args:
        title: Summary title
        stats: Dictionary of stat names and values
        style: Panel border style
    """
    lines = []
    for name, value in stats.items():
        if isinstance(value, float):
            lines.append(f"  [muted]{name}:[/muted] [count]{value:.1f}[/count]")
        else:
            lines.append(f"  [muted]{name}:[/muted] [count]{value}[/count]")

    content = "\n".join(lines)
    print_panel(content, title=title, style=style)


def print_operation_result(
    operation: str,
    success_count: int,
    failed_count: int,
    skipped_count: int = 0,
) -> None:
    """Print a standardized operation result summary.

    Args:
        operation: Name of the operation performed
        success_count: Number of successful items
        failed_count: Number of failed items
        skipped_count: Number of skipped items
    """
    total = success_count + failed_count + skipped_count

    table = create_table(title=f"{operation} Results")
    table.add_column("Status", style="bold")
    table.add_column("Count", justify="right")
    table.add_column("Percentage", justify="right")

    if total > 0:
        table.add_row(
            "[success]✓ Success[/success]",
            str(success_count),
            f"{success_count / total * 100:.1f}%",
        )
        if failed_count > 0:
            table.add_row(
                "[error]✗ Failed[/error]",
                str(failed_count),
                f"{failed_count / total * 100:.1f}%",
            )
        if skipped_count > 0:
            table.add_row(
                "[warning]⊘ Skipped[/warning]",
                str(skipped_count),
                f"{skipped_count / total * 100:.1f}%",
            )
        table.add_row("─" * 10, "─" * 5, "─" * 10)
        table.add_row("[bold]Total[/bold]", f"[bold]{total}[/bold]", "100%")

    print_table(table)


# =============================================================================
# User Lists and Items
# =============================================================================


def print_user_list(
    users: list[dict[str, str]],
    title: str = "Users",
    max_display: int = 10,
) -> None:
    """Print a list of users in a formatted table.

    Args:
        users: List of user dicts with 'user_id' and optionally 'email', 'status'
        title: Table title
        max_display: Maximum users to display (shows count if more)
    """
    if not users:
        print_info("No users to display")
        return

    table = create_table(title=f"{title} ({len(users)} total)")
    table.add_column("User ID", style="user_id")
    table.add_column("Email")
    table.add_column("Status")

    for user in users[:max_display]:
        table.add_row(
            user.get("user_id", "N/A"),
            user.get("email", "N/A"),
            user.get("status", ""),
        )

    if len(users) > max_display:
        table.add_row(
            f"[muted]... and {len(users) - max_display} more[/muted]",
            "",
            "",
        )

    print_table(table)
