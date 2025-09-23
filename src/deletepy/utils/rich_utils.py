"""Rich utilities: shared console, themes, and helpers."""

from __future__ import annotations

from rich.console import Console
from rich.theme import Theme
from rich.traceback import install as rich_traceback_install

_console: Console | None = None


def get_console() -> Console:
    """Return a shared Rich Console instance.

    Creates the console on first use with a pleasant default theme.
    """
    global _console
    if _console is None:
        theme = Theme(
            {
                "info": "cyan",
                "warning": "yellow",
                "error": "red",
                "success": "green",
                "muted": "grey62",
            }
        )
        _console = Console(theme=theme, highlight=False, soft_wrap=False)
    return _console


def install_rich_tracebacks() -> None:
    """Enable rich tracebacks globally for nicer error output."""
    # Avoid excessive locals dumping; wrap long lines; default width detection
    rich_traceback_install(show_locals=False, word_wrap=True, suppress=["click"])
