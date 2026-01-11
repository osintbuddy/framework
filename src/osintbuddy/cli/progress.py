"""Progress display utilities for OSINTBuddy CLI."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, Any

from rich.console import Group
from rich.live import Live
from rich.text import Text
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

from osintbuddy.cli.console import console


SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]


@dataclass
class Step:
    """A step in a multi-step process."""

    name: str
    hint: str = ""
    outputs: list[str] = field(default_factory=list)
    tick_count: int = 20


def _progress_bar(percent: int, width: int = 20) -> str:
    """Generate an ASCII progress bar."""
    filled = int(width * percent / 100)
    return "[" + "█" * filled + "░" * (width - filled) + "]"


def _render(lines: list[str], active_line: str | None = None) -> Group:
    """Render lines as a Group."""
    renderables = [Text.from_markup(line) for line in lines]
    if active_line:
        renderables.append(Text.from_markup(active_line))
    return Group(*renderables)


class StepRunner:
    """Runner for animated multi-step operations."""

    def __init__(self, speed: float = 1.0):
        """Initialize step runner.

        Args:
            speed: Animation speed multiplier (lower = faster)
        """
        self.speed = speed
        self.lines: list[str] = []

    def type_command(self, live: Live, prompt: str, command: str) -> None:
        """Animate typing a command."""
        typed = ""
        for ch in command:
            typed += ch
            live.update(_render(self.lines, f"{prompt}{typed}"))
            time.sleep(0.015 * self.speed)
        self.lines.append(f"{prompt}{command}")

    def run_step(self, live: Live, step: Step) -> None:
        """Run an animated step with progress bar."""
        reveal_every = max(1, step.tick_count // max(1, len(step.outputs)))
        out_idx = 0
        start = time.time()

        for tick in range(step.tick_count):
            percent = int(100 * (tick + 1) / step.tick_count)
            spinner = SPINNER_FRAMES[tick % len(SPINNER_FRAMES)]
            bar = _progress_bar(percent)

            active = (
                f"[cyan]>> {step.name}[/] {spinner} {bar} "
                f"[yellow]{percent}%[/] [dim]{step.hint}[/]"
            )

            if (tick + 1) % reveal_every == 0 and out_idx < len(step.outputs):
                self.lines.append(f"   [dim]-[/] {step.outputs[out_idx]}")
                out_idx += 1

            live.update(_render(self.lines, active))
            time.sleep(0.03 * self.speed)

        elapsed_ms = int((time.time() - start) * 1000)
        self.lines.append(f"[green]>> {step.name}[/] [success]OK[/] [dim]{elapsed_ms}ms[/]")

    def run_steps(self, steps: list[Step], header_lines: list[str] | None = None) -> None:
        """Run multiple steps with animation."""
        self.lines = header_lines or []

        with Live(_render(self.lines), console=console, refresh_per_second=20) as live:
            for step in steps:
                self.run_step(live, step)
                self.lines.append("")

            live.update(_render(self.lines))
            time.sleep(0.3 * self.speed)


class TransformProgress:
    """Progress display for transform execution."""

    def __init__(self, transform_label: str):
        self.transform_label = transform_label
        self.progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(bar_width=30),
            TaskProgressColumn(),
            console=console,
        )
        self.task_id = None

    def __enter__(self) -> "TransformProgress":
        self.progress.start()
        self.task_id = self.progress.add_task(
            f"[cyan]Running {self.transform_label}[/]",
            total=100,
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type is None:
            self.progress.update(self.task_id, completed=100)
        self.progress.stop()

    def update(self, message: str, percent: int) -> None:
        """Update progress."""
        self.progress.update(
            self.task_id,
            description=f"[cyan]{message}[/]",
            completed=percent,
        )


class PluginLoadProgress:
    """Progress display for plugin loading."""

    def __init__(self):
        self.progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        )

    def __enter__(self) -> "PluginLoadProgress":
        self.progress.start()
        self.task = self.progress.add_task("[cyan]Loading plugins...[/]")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.progress.stop()

    def update(self, message: str) -> None:
        """Update status message."""
        self.progress.update(self.task, description=f"[cyan]{message}[/]")

    def complete(self, entity_count: int, transform_count: int) -> None:
        """Mark as complete."""
        self.progress.update(
            self.task,
            description=f"[green]Loaded {entity_count} entities, {transform_count} transforms[/]",
        )
