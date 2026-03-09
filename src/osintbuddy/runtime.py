"""Runtime helpers for bundled OSINTBuddy workers."""
from __future__ import annotations

import importlib
import logging
import os
import site
import subprocess
import sys
from functools import lru_cache
from pathlib import Path
from typing import Sequence

logger = logging.getLogger(__name__)

_PLAYWRIGHT_PACKAGES = {"playwright", "patchright"}


def is_frozen_runtime() -> bool:
    return bool(getattr(sys, "frozen", False))


@lru_cache(maxsize=1)
def get_runtime_home() -> Path:
    raw_home = os.environ.get("OSINTBUDDY_RUNTIME_HOME", "").strip()
    if raw_home:
        runtime_home = Path(raw_home).expanduser()
    elif is_frozen_runtime():
        runtime_home = Path.home() / ".osintbuddy-runtime"
    else:
        runtime_home = Path.cwd() / ".osintbuddy-runtime"

    runtime_home.mkdir(parents=True, exist_ok=True)
    return runtime_home


@lru_cache(maxsize=1)
def get_dynamic_site_packages_dir() -> Path:
    site_packages_dir = get_runtime_home() / "site-packages"
    site_packages_dir.mkdir(parents=True, exist_ok=True)
    return site_packages_dir


def ensure_runtime_ready() -> Path:
    runtime_home = get_runtime_home()
    site_packages_dir = get_dynamic_site_packages_dir()

    os.environ.setdefault("OSINTBUDDY_RUNTIME_HOME", str(runtime_home))
    os.environ.setdefault("PIP_CACHE_DIR", str(runtime_home / "pip-cache"))
    os.environ.setdefault(
        "PLAYWRIGHT_BROWSERS_PATH",
        str(runtime_home / "playwright"),
    )

    cert_file = get_cert_bundle_path()
    if cert_file is not None:
        os.environ.setdefault("SSL_CERT_FILE", cert_file)
        os.environ.setdefault("REQUESTS_CA_BUNDLE", cert_file)
        os.environ.setdefault("CURL_CA_BUNDLE", cert_file)
        os.environ.setdefault("PIP_CERT", cert_file)

    site.addsitedir(str(site_packages_dir))
    site_path = str(site_packages_dir)
    if site_path not in sys.path:
        sys.path.insert(0, site_path)
    importlib.invalidate_caches()
    return runtime_home


@lru_cache(maxsize=1)
def get_cert_bundle_path() -> str | None:
    for module_name in ("certifi", "pip._vendor.certifi"):
        try:
            module = importlib.import_module(module_name)
        except ImportError:
            continue
        where = getattr(module, "where", None)
        if where is None:
            continue
        cert_path = str(where())
        if cert_path:
            return cert_path
    return None


def _run_embedded_pip(packages: Sequence[str], quiet: bool = True) -> bool:
    from pip._internal.cli.main import main as pip_main

    ensure_runtime_ready()
    args = [
        "install",
        "--disable-pip-version-check",
        "--no-input",
        "--ignore-installed",
        "--use-deprecated=legacy-certs",
        "--upgrade",
        "--target",
        str(get_dynamic_site_packages_dir()),
    ]
    if quiet:
        args.append("--quiet")
    args.extend(packages)

    result = pip_main(args)
    if result != 0:
        raise RuntimeError(f"pip exited with status {result}")

    importlib.invalidate_caches()
    ensure_runtime_ready()
    return True


def install_python_packages(packages: Sequence[str], quiet: bool = True) -> bool:
    if not packages:
        return True

    if is_frozen_runtime():
        return _run_embedded_pip(packages, quiet=quiet)

    cmd = [sys.executable, "-m", "pip", "install"]
    if quiet:
        cmd.append("--quiet")
    cmd.extend(packages)
    subprocess.check_call(cmd, stdout=subprocess.DEVNULL if quiet else None)
    return True


def ensure_playwright_browsers(package_names: Sequence[str]) -> None:
    normalized = {name.replace("_", "-").lower() for name in package_names}
    if not normalized.intersection(_PLAYWRIGHT_PACKAGES):
        return

    runtime_home = ensure_runtime_ready()
    browser_root = Path(
        os.environ.setdefault(
            "PLAYWRIGHT_BROWSERS_PATH",
            str(runtime_home / "playwright"),
        )
    )
    browser_root.mkdir(parents=True, exist_ok=True)
    marker = browser_root / ".osib-browser-install"
    if marker.exists():
        return

    browser_name = os.environ.get("OSINTBUDDY_PLAYWRIGHT_BROWSER", "chromium").strip() or "chromium"

    installer = None
    installer_name = None
    for package_name in ("patchright", "playwright"):
        try:
            installer_module = importlib.import_module(f"{package_name}.__main__")
        except ImportError:
            continue
        installer = getattr(installer_module, "main", None)
        installer_name = package_name
        if installer is not None:
            break

    if installer is None or installer_name is None:
        logger.warning("Playwright requested but no installer module is available.")
        return

    original_argv = sys.argv[:]
    try:
        sys.argv = [installer_name, "install", browser_name]
        result = installer()
    finally:
        sys.argv = original_argv

    if result not in (None, 0):
        raise RuntimeError(f"{installer_name} install exited with status {result}")

    marker.write_text(browser_name, encoding="utf-8")
