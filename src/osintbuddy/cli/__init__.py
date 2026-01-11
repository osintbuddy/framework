"""OSINTBuddy CLI package.

Provides a modern, animated CLI experience using Rich.
"""
from osintbuddy.cli.console import console, err_console
from osintbuddy.cli.display import (
    print_banner,
    print_error,
    print_success,
    print_warning,
    print_info,
    print_debug,
)
from osintbuddy.cli.progress import StepRunner, Step
from osintbuddy.cli.logging import setup_logging, get_logger

__all__ = [
    "console",
    "err_console",
    "print_banner",
    "print_error",
    "print_success",
    "print_warning",
    "print_info",
    "print_debug",
    "StepRunner",
    "Step",
    "setup_logging",
    "get_logger",
]
