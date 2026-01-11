"""Logging configuration for OSINTBuddy CLI."""
from __future__ import annotations

import logging
import sys
from typing import Any

from rich.logging import RichHandler
from rich.console import Console

from osintbuddy.cli.console import err_console


class OSIBLogHandler(RichHandler):
    """Custom Rich log handler with OSINTBuddy styling."""

    def __init__(
        self,
        *,
        show_time: bool = True,
        show_path: bool = False,
        **kwargs,
    ):
        super().__init__(
            console=err_console,
            show_time=show_time,
            show_path=show_path,
            rich_tracebacks=True,
            tracebacks_show_locals=True,
            markup=True,
            **kwargs,
        )


def setup_logging(
    level: int = logging.INFO,
    *,
    show_path: bool = False,
    show_time: bool = True,
) -> logging.Logger:
    """Set up logging with Rich formatting.

    Args:
        level: Logging level
        show_path: Show source file path in logs
        show_time: Show timestamp in logs

    Returns:
        Configured logger
    """
    # Remove any existing handlers
    root = logging.getLogger()
    for handler in root.handlers[:]:
        root.removeHandler(handler)

    # Configure Rich handler
    handler = OSIBLogHandler(
        show_path=show_path,
        show_time=show_time,
    )
    handler.setLevel(level)

    # Set format
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[handler],
    )

    return logging.getLogger("osintbuddy")


def get_logger(name: str = "osintbuddy") -> logging.Logger:
    """Get a logger instance.

    Args:
        name: Logger name

    Returns:
        Logger instance
    """
    return logging.getLogger(name)


class LogCapture:
    """Context manager to capture log output."""

    def __init__(self, logger_name: str = "osintbuddy"):
        self.logger_name = logger_name
        self.records: list[logging.LogRecord] = []
        self._handler: logging.Handler | None = None

    def __enter__(self) -> "LogCapture":
        class CaptureHandler(logging.Handler):
            def __init__(self, records: list):
                super().__init__()
                self.records = records

            def emit(self, record: logging.LogRecord) -> None:
                self.records.append(record)

        self._handler = CaptureHandler(self.records)
        logging.getLogger(self.logger_name).addHandler(self._handler)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._handler:
            logging.getLogger(self.logger_name).removeHandler(self._handler)

    def get_messages(self, level: int | None = None) -> list[str]:
        """Get captured messages.

        Args:
            level: Filter by level (None = all)

        Returns:
            List of message strings
        """
        records = self.records
        if level is not None:
            records = [r for r in records if r.levelno == level]
        return [r.getMessage() for r in records]
