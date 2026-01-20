"""Display utilities for OSINTBuddy CLI."""
from __future__ import annotations

import random
import time
from typing import Any

from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.syntax import Syntax
from rich.traceback import Traceback

from osintbuddy import __version__
from osintbuddy.cli.console import console, err_console


BANNER = r"""
   ____  _____ _____   _   _ _____   ____            _     _
  / __ \/ ____|_   _| | \ | |_   _| |  _ \          | |   | |
 | |  | | (___  | |   |  \| | | |   | |_) |_   _  __| | __| |_   _
 | |  | |\___ \ | |   | . ` | | |   |  _ <| | | |/ _` |/ _` | | | |
 | |__| |____) || |_  | |\  | | |   | |_) | |_| | (_| | (_| | |_| |
  \____/|_____/_____| |_| \_| |_|   |____/ \__,_|\__,_|\__,_|\__, |
                                                             __/ |
                                                            |___/
"""


def print_banner(show_session: bool = True) -> None:
    """Print the OSINTBuddy banner with session info."""
    console.print(Text(BANNER, style="cyan"))
    console.print(
        f"[header]osintbuddy[/] [version]v{__version__}[/] [success]ready[/]"
    )

    if show_session:
        session_id = f"{random.randint(1000, 9999)}-{random.randint(100, 999)}"
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        console.print(
            f"[muted]session[/] {session_id}  [muted]start[/] {timestamp}"
        )
        console.print("[muted]mode[/] local  [muted]operator[/] cli")
    console.print()


def print_error(
    message: str,
    *,
    code: str | None = None,
    details: dict[str, Any] | None = None,
    show_traceback: bool = False,
) -> None:
    """Print a formatted error message.

    Args:
        message: Error message to display
        code: Optional error code
        details: Optional additional details
        show_traceback: If True, show the full traceback
    """
    error_text = Text()
    error_text.append("ERROR", style="bold red")
    if code:
        error_text.append(f" [{code}]", style="red")
    error_text.append(f": {message}", style="red")

    err_console.print(error_text)

    if details:
        for key, value in details.items():
            err_console.print(f"  [muted]{key}:[/] {value}")

    if show_traceback:
        err_console.print(Traceback(show_locals=True))


def print_syntax_error(
    message: str,
    source: str | None = None,
    line: int | None = None,
    column: int | None = None,
) -> None:
    """Print a syntax-highlighted error with source context."""
    print_error(message)

    if source and line:
        lines = source.split("\n")
        start = max(0, line - 3)
        end = min(len(lines), line + 2)
        context = "\n".join(lines[start:end])

        console.print()
        console.print(
            Syntax(
                context,
                "python",
                line_numbers=True,
                start_line=start + 1,
                highlight_lines={line},
                theme="monokai",
            )
        )


def print_success(message: str) -> None:
    """Print a success message."""
    console.print(f"[success]OK[/] {message}")


def print_warning(message: str) -> None:
    """Print a warning message."""
    console.print(f"[warning]WARN[/] {message}")


def print_info(message: str) -> None:
    """Print an info message."""
    console.print(f"[info]INFO[/] {message}")


def print_debug(message: str) -> None:
    """Print a debug message."""
    console.print(f"[debug]DEBUG[/] {message}")


def print_json_result(data: Any, title: str = "Result") -> None:
    """Print JSON data in a formatted panel."""
    import json
    json_str = json.dumps(data, indent=2)
    syntax = Syntax(json_str, "json", theme="monokai")
    console.print(Panel(syntax, title=title, border_style="cyan"))


def print_entities_table(entities: list[dict]) -> None:
    """Print entities in a formatted table."""
    table = Table(title="Entities", border_style="cyan")
    table.add_column("Label", style="entity")
    table.add_column("Category", style="muted")
    table.add_column("Author", style="muted")
    table.add_column("Description", style="dim", max_width=50)

    for entity in entities:
        author = entity.get("author", "unknown")
        if isinstance(author, list):
            author = ", ".join(author)
        description = entity.get("description", "") or ""
        desc_display = description[:50] + "..." if len(description) > 50 else (description or "-")
        category = entity.get("category", "-")
        if isinstance(category, list):
            category_display = ", ".join(str(cat) for cat in category if cat) or "-"
        else:
            category_display = category or "-"
        table.add_row(
            entity.get("label", "unknown"),
            category_display,
            author or "unknown",
            desc_display,
        )

    console.print(table)


def print_transforms_table(transforms: list[dict], entity_label: str = "") -> None:
    """Print transforms in a formatted table."""
    title = f"Transforms for {entity_label}" if entity_label else "Transforms"
    table = Table(title=title, border_style="magenta")
    table.add_column("Label", style="transform")
    table.add_column("Icon", style="muted")
    table.add_column("Edge Label", style="dim")
    table.add_column("Dependencies", style="dim")

    for transform in transforms:
        deps = ", ".join(transform.get("deps", [])) or "-"
        table.add_row(
            transform.get("label", "unknown"),
            transform.get("icon", "list"),
            transform.get("edge_label", "-"),
            deps,
        )

    console.print(table)
