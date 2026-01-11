"""Console configuration for OSINTBuddy CLI."""
from __future__ import annotations

from rich.console import Console
from rich.theme import Theme

# Custom theme for OSINTBuddy
OSIB_THEME = Theme({
    "info": "cyan",
    "warning": "yellow",
    "error": "bold red",
    "success": "bold green",
    "debug": "dim",
    "header": "bold cyan",
    "entity": "bold blue",
    "transform": "bold magenta",
    "version": "dim cyan",
    "path": "dim",
    "highlight": "bold white",
    "muted": "dim white",
    "progress.bar": "cyan",
    "progress.percentage": "yellow",
    "step.pending": "dim",
    "step.running": "cyan",
    "step.complete": "green",
    "step.failed": "red",
})

# Main console for stdout
console = Console(theme=OSIB_THEME, highlight=True)

# Error console for stderr
err_console = Console(theme=OSIB_THEME, stderr=True, highlight=True)
