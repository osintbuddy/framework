"""Structured CLI output for OSINTBuddy.

This module provides utilities for emitting structured output from the CLI,
making it easier for the Electron app to parse results reliably.

Output Format:
    Results are wrapped with delimiters for reliable parsing:

    ---OSIB_JSON_START---
    {"entities": [...], "messages": [...]}
    ---OSIB_JSON_END---

    Progress updates:
    ---OSIB_PROGRESS---{"message": "Scanning...", "percent": 50}

    Errors:
    ---OSIB_ERROR_START---
    {"error": "message", "code": "ERROR_CODE"}
    ---OSIB_ERROR_END---
"""
from __future__ import annotations

import json
import sys
from typing import Any, Callable


# Output delimiters
JSON_START = "---OSIB_JSON_START---"
JSON_END = "---OSIB_JSON_END---"
ERROR_START = "---OSIB_ERROR_START---"
ERROR_END = "---OSIB_ERROR_END---"
PROGRESS_PREFIX = "---OSIB_PROGRESS---"

_progress_callback: Callable[[dict[str, Any]], None] | None = None


def set_progress_callback(callback: Callable[[dict[str, Any]], None] | None) -> None:
    """Register a callback to receive progress events."""
    global _progress_callback
    _progress_callback = callback


def emit_result(data: Any) -> None:
    """Emit a structured JSON result.

    Args:
        data: Data to serialize and emit
    """
    print(JSON_START, file=sys.stdout)
    json.dump(data, sys.stdout)
    print(f"\n{JSON_END}", file=sys.stdout)
    sys.stdout.flush()


def emit_error(error: str, code: str = "UNKNOWN", details: dict[str, Any] | None = None) -> None:
    """Emit a structured error.

    Args:
        error: Error message
        code: Error code for programmatic handling
        details: Optional additional error details
    """
    error_data = {
        "error": error,
        "code": code,
    }
    if details:
        error_data["details"] = details

    print(ERROR_START, file=sys.stdout)
    json.dump(error_data, sys.stdout)
    print(f"\n{ERROR_END}", file=sys.stdout)
    sys.stdout.flush()


def emit_progress(message: str, percent: int = -1, stage: str = "") -> None:
    """Emit a progress update.

    Args:
        message: Progress message
        percent: Progress percentage (0-100, -1 for indeterminate)
        stage: Optional stage identifier
    """
    progress_data = {
        "message": message,
        "percent": percent,
    }
    if stage:
        progress_data["stage"] = stage

    if _progress_callback:
        try:
            _progress_callback(progress_data)
        except Exception:
            pass

    print(f"{PROGRESS_PREFIX}{json.dumps(progress_data)}", file=sys.stderr)


def emit_json(data: Any, pretty: bool = False) -> None:
    """Emit plain JSON without delimiters (legacy mode).

    Args:
        data: Data to serialize
        pretty: If True, pretty-print the JSON
    """
    if pretty:
        print(json.dumps(data, indent=2))
    else:
        print(json.dumps(data))


class ProgressEmitter:
    """Context manager for emitting progress during long operations.

    Example:
        with ProgressEmitter("Scanning") as progress:
            progress.update("Starting...", 0)
            # ... do work
            progress.update("Processing...", 50)
            # ... do more work
            progress.update("Finishing...", 90)
    """

    def __init__(self, stage: str = ""):
        self.stage = stage
        self._last_percent = -1

    def __enter__(self) -> 'ProgressEmitter':
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type is None:
            self.complete()

    def update(self, message: str, percent: int = -1) -> None:
        """Emit a progress update.

        Args:
            message: Progress message
            percent: Progress percentage (0-100)
        """
        self._last_percent = percent
        emit_progress(message, percent, self.stage)

    def complete(self, message: str = "Complete") -> None:
        """Emit completion (100%).

        Args:
            message: Completion message
        """
        emit_progress(message, 100, self.stage)

    def increment(self, message: str, amount: int = 10) -> None:
        """Increment progress by an amount.

        Args:
            message: Progress message
            amount: Amount to increment
        """
        new_percent = min(100, max(0, self._last_percent + amount))
        self.update(message, new_percent)
