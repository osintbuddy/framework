from __future__ import annotations

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata

block_cipher = None

ROOT = Path(SPECPATH).resolve().parent.parent
SRC = ROOT / "framework" / "src"


def safe_collect_submodules(package_name: str) -> list[str]:
    try:
        return collect_submodules(package_name)
    except Exception:
        return []


def safe_collect_data_files(package_name: str) -> list[tuple[str, str]]:
    try:
        return collect_data_files(package_name)
    except Exception:
        return []


def safe_copy_metadata(package_name: str) -> list[tuple[str, str]]:
    try:
        return copy_metadata(package_name)
    except Exception:
        return []


hiddenimports = sorted(
    set(
        safe_collect_submodules("pip")
        + safe_collect_submodules("setuptools")
        + safe_collect_submodules("wheel")
        + safe_collect_submodules("playwright")
    )
)

datas = (
    safe_collect_data_files("playwright")
    + safe_copy_metadata("pip")
    + safe_copy_metadata("setuptools")
    + safe_copy_metadata("wheel")
    + safe_copy_metadata("playwright")
)

a = Analysis(
    [str(SRC / "osintbuddy" / "ipc_worker.py")],
    pathex=[str(SRC)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="osib-worker",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name="osib-runtime",
)
