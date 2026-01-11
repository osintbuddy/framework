"""Dependency management for OSINTBuddy transforms.

This module provides utilities for declaring and installing transform
dependencies at runtime, enabling transforms to use third-party packages
without requiring them to be pre-installed.

Example usage:
    @transform(
        target="website@1.0.0",
        label="Screenshot",
        deps=["playwright", "pillow>=10.0.0"]
    )
    async def screenshot(entity):
        from playwright.sync_api import sync_playwright
        ...
"""
from __future__ import annotations

import subprocess
import sys
import logging
from functools import lru_cache
from typing import Sequence

logger = logging.getLogger(__name__)


class DependencyError(Exception):
    """Raised when dependency installation fails."""
    pass


def parse_package_name(dep: str) -> str:
    """Extract package name from a dependency specification.

    Args:
        dep: Dependency string like "playwright", "pillow>=10.0.0", "requests[security]"

    Returns:
        The bare package name for import checking
    """
    # Remove version specifiers
    for sep in ('>=', '<=', '==', '!=', '~=', '<', '>'):
        if sep in dep:
            dep = dep.split(sep)[0]
            break

    # Remove extras
    if '[' in dep:
        dep = dep.split('[')[0]

    return dep.strip().replace('-', '_')


def is_package_installed(package_name: str) -> bool:
    """Check if a package is installed and importable.

    Args:
        package_name: The package name to check

    Returns:
        True if the package can be imported
    """
    try:
        __import__(package_name)
        return True
    except ImportError:
        return False


def install_packages(packages: Sequence[str], quiet: bool = True) -> bool:
    """Install packages using pip.

    Args:
        packages: List of package specifications to install
        quiet: If True, suppress pip output

    Returns:
        True if installation succeeded

    Raises:
        DependencyError: If installation fails
    """
    if not packages:
        return True

    cmd = [sys.executable, "-m", "pip", "install"]
    if quiet:
        cmd.append("--quiet")
    cmd.extend(packages)

    try:
        subprocess.check_call(cmd, stdout=subprocess.DEVNULL if quiet else None)
        return True
    except subprocess.CalledProcessError as e:
        raise DependencyError(f"Failed to install packages {packages}: {e}")


@lru_cache(maxsize=256)
def ensure_deps(deps: tuple[str, ...], auto_install: bool = True) -> bool:
    """Ensure dependencies are installed, optionally installing missing ones.

    This function is cached per unique dependency set, so repeated calls
    with the same dependencies are fast.

    Args:
        deps: Tuple of dependency specifications (must be tuple for caching)
        auto_install: If True, automatically install missing packages

    Returns:
        True if all dependencies are available

    Raises:
        DependencyError: If a required package is missing and auto_install is False,
                        or if installation fails

    Example:
        # In a transform wrapper
        if deps:
            ensure_deps(tuple(deps))
    """
    if not deps:
        return True

    missing = []
    for dep in deps:
        pkg_name = parse_package_name(dep)
        if not is_package_installed(pkg_name):
            missing.append(dep)

    if not missing:
        return True

    if not auto_install:
        raise DependencyError(
            f"Missing dependencies: {missing}. "
            "Set auto_install=True or install manually."
        )

    logger.info(f"Installing missing dependencies: {missing}")
    install_packages(missing)

    # Verify installation
    still_missing = []
    for dep in missing:
        pkg_name = parse_package_name(dep)
        if not is_package_installed(pkg_name):
            still_missing.append(dep)

    if still_missing:
        raise DependencyError(f"Failed to install: {still_missing}")

    return True


def check_deps(deps: Sequence[str]) -> tuple[list[str], list[str]]:
    """Check which dependencies are installed vs missing.

    Unlike ensure_deps, this does not install anything - it only checks.

    Args:
        deps: Sequence of dependency specifications to check

    Returns:
        Tuple of (installed, missing) package lists

    Example:
        installed, missing = check_deps(["requests", "playwright"])
        if missing:
            print(f"Missing: {missing}")
    """
    installed = []
    missing = []

    for dep in deps:
        pkg_name = parse_package_name(dep)
        if is_package_installed(pkg_name):
            installed.append(dep)
        else:
            missing.append(dep)

    return installed, missing


def clear_deps_cache() -> None:
    """Clear the dependency check cache.

    Call this if you've manually installed packages and want to
    re-check availability.
    """
    ensure_deps.cache_clear()


def get_cached_deps() -> dict[tuple[str, ...], bool]:
    """Get information about cached dependency checks.

    Returns:
        Cache info from the ensure_deps function
    """
    return ensure_deps.cache_info()._asdict()
