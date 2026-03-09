from __future__ import annotations

import json
import sys
import uuid

import osintbuddy.repo_inspector as repo_inspector
from osintbuddy.repo_inspector import (
    build_manifest,
    build_manifest_id,
    build_readme,
    inspect_repo,
    scaffold_default_repo_files,
    update_readme_content,
)


def write_file(path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def make_plugin_repo(tmp_path):
    write_file(
        tmp_path / "pyproject.toml",
        """
[project]
name = "osintbuddy-plugins-reloaded"
version = "1.0.0"
description = "Default entity and transform collection for OSINTBuddy."
readme = "README.md"
license = {text = "MIT"}
requires-python = ">=3.12"
keywords = ["osint", "plugins", "recon", "web"]

[[project.authors]]
name = "OSIB"

[project.urls]
Homepage = "https://github.com/osintbuddy/plugins"
Repository = "https://github.com/osintbuddy/plugins"
""".strip()
        + "\n",
    )
    write_file(tmp_path / "README.md", "# Placeholder\n")
    write_file(tmp_path / "data" / "lookups.json", json.dumps({"seed": ["example.com"]}, indent=2) + "\n")
    write_file(
        tmp_path / "entities" / "website.py",
        """
from osintbuddy import Plugin
from osintbuddy.elements import TextInput


class Website(Plugin):
    version = "1.0.0"
    label = "Website"
    category = "Web"
    description = "Represents a domain from a website on the internet"
    author = "OSIB"
    color = "#1D1DB899"
    icon = "world-www"
    elements = [
        TextInput(label="Domain", icon="world-www"),
    ]
""".strip()
        + "\n",
    )
    write_file(
        tmp_path / "transforms" / "website_transforms.py",
        """
import socket

from osintbuddy import transform


@transform(target="website@>=1.0.0", label="To IP", icon="building-broadcast-tower")
async def to_ip(entity):
    socket.gethostbyname(entity.domain)
    return []
""".strip()
        + "\n",
    )
    return tmp_path


def add_virtualenv_artifacts(repo_root) -> None:
    write_file(repo_root / "venv" / "pyvenv.cfg", "home = /tmp/python\n")
    venv_bin = repo_root / "venv" / "bin"
    venv_bin.mkdir(parents=True, exist_ok=True)
    try:
        (venv_bin / "python3").symlink_to(sys.executable)
    except OSError:
        write_file(venv_bin / "python3", "#!/usr/bin/env python3\n")
    write_file(venv_bin / "pip", "#!/bin/sh\n")


def test_build_manifest_includes_repo_graph(tmp_path, monkeypatch):
    repo_root = make_plugin_repo(tmp_path)
    monkeypatch.setattr(repo_inspector, "_fetch_latest_app_version", lambda: "9.9.9")
    monkeypatch.setattr(repo_inspector, "get_git_username", lambda repo_path=".": "git-user")
    monkeypatch.setattr(repo_inspector, "uuid4", lambda: uuid.UUID("12345678-1234-5678-1234-567812345678"))

    snapshot = inspect_repo(plugins_path=str(repo_root), include_hashes=True)
    manifest = build_manifest(snapshot, include_hashes=True)

    assert manifest["id"] == "12345678-1234-5678-1234-567812345678-git-user-osintbuddy-plugins-reloaded"
    assert manifest["name"] == "osintbuddy-plugins-reloaded"
    assert manifest["author"] == "git-user"
    assert manifest["repo"] == "osintbuddy/plugins"
    assert manifest["homepage"] == "https://github.com/osintbuddy/plugins"
    assert manifest["license"] == "MIT"
    assert manifest["min_app_version"] == "9.9.9"
    assert "version" not in manifest
    assert "readme" not in manifest
    assert "files" not in manifest
    assert "file_hashes" in manifest
    assert "entities/website.py" in manifest["file_hashes"]
    assert "transforms/website_transforms.py" in manifest["file_hashes"]
    assert "data/lookups.json" in manifest["file_hashes"]
    assert list(manifest.keys()).index("warnings") == list(manifest.keys()).index("license") + 1

    entity = manifest["entities"][0]
    assert entity["id"] == "website@1.0.0"
    assert entity["file"] == "entities/website.py"
    assert entity["module"] == "entities.website"
    assert entity["class"] == "Website"
    assert "elements" not in entity

    transform = manifest["transforms"][0]
    assert transform["id"] == "transforms.website_transforms:to_ip"
    assert transform["target"] == "website@1.0.0"
    assert transform["target_spec"] == "website@>=1.0.0"
    assert transform["function"] == "to_ip"
    assert transform["file"] == "transforms/website_transforms.py"
    assert transform["module"] == "transforms.website_transforms"


def test_inspect_repo_prefers_explicit_repo_root_over_discovered_parent(tmp_path, monkeypatch):
    repo_root = make_plugin_repo(tmp_path / "child")
    parent_root = tmp_path / "parent"
    parent_root.mkdir()

    monkeypatch.setattr(repo_inspector, "find_repo_root", lambda start=None: parent_root)
    monkeypatch.setattr(repo_inspector, "_fetch_latest_app_version", lambda: "9.9.9")
    monkeypatch.setattr(repo_inspector, "get_git_username", lambda repo_path=".": "git-user")

    snapshot = inspect_repo(plugins_path=str(repo_root), include_hashes=True, repo_root=repo_root)

    assert snapshot["repo_root"] == repo_root
    assert "entities/website.py" in snapshot["file_hashes"]
    assert "transforms/website_transforms.py" in snapshot["file_hashes"]
    assert all(not path.startswith("parent") for path in snapshot["file_hashes"])


def test_inspect_repo_hashes_untracked_files_in_fresh_git_repo(tmp_path, monkeypatch):
    from dulwich.repo import Repo

    repo_root = make_plugin_repo(tmp_path)
    Repo.init(str(repo_root))
    add_virtualenv_artifacts(repo_root)

    monkeypatch.setattr(repo_inspector, "_fetch_latest_app_version", lambda: "9.9.9")
    monkeypatch.setattr(repo_inspector, "get_git_username", lambda repo_path=".": "git-user")

    snapshot = inspect_repo(plugins_path=str(repo_root), include_hashes=True, repo_root=repo_root)

    assert snapshot["file_hashes"]
    assert "pyproject.toml" in snapshot["file_hashes"]
    assert "README.md" in snapshot["file_hashes"]
    assert "entities/website.py" in snapshot["file_hashes"]
    assert "transforms/website_transforms.py" in snapshot["file_hashes"]
    assert "data/lookups.json" in snapshot["file_hashes"]
    assert "venv/pyvenv.cfg" not in snapshot["file_hashes"]
    assert "venv/bin/pip" not in snapshot["file_hashes"]
    assert "venv/bin/python3" not in snapshot["file_hashes"]
    assert all(not path.startswith("venv/") for path in snapshot["files"])


def test_build_readme_projects_manifest_metadata(tmp_path, monkeypatch):
    repo_root = make_plugin_repo(tmp_path)
    monkeypatch.setattr(repo_inspector, "_fetch_latest_app_version", lambda: "9.9.9")
    monkeypatch.setattr(repo_inspector, "get_git_username", lambda repo_path=".": "git-user")

    snapshot = inspect_repo(plugins_path=str(repo_root), include_hashes=True)
    readme = build_readme(snapshot)

    assert "# OSIB: Title here..." in readme
    assert "## Available Entities" in readme
    assert "| Website | website@1.0.0 | Web | Represents a domain from a website on the internet | entities/website.py |" in readme
    assert "## Available Transforms" in readme
    assert "| To IP | website@1.0.0 | To IP | transforms/website_transforms.py |" in readme
    assert "## Data Files" in readme
    assert "| data/lookups.json | json | Configuration or structured metadata |" in readme
    assert "## Operational Notes" in readme
    assert "**Detected external dependencies**: None detected" in readme
    assert "**Browser automation**: No browser automation imports detected" in readme
    assert "**Network dependencies**: Transforms appear to use network-facing modules: socket" in readme
    assert "## Additional Notes" in readme
    assert "**Detected external imports**: None" in readme
    assert "**Browser automation imports detected**: None" in readme
    assert "**Network-facing imports detected**: socket" in readme


def test_build_manifest_can_preserve_curated_fields(tmp_path, monkeypatch):
    repo_root = make_plugin_repo(tmp_path)
    monkeypatch.setattr(repo_inspector, "_fetch_latest_app_version", lambda: "9.9.9")
    monkeypatch.setattr(repo_inspector, "get_git_username", lambda repo_path=".": "git-user")

    snapshot = inspect_repo(plugins_path=str(repo_root), include_hashes=True)
    manifest = build_manifest(
        snapshot,
        include_hashes=True,
        preserved_values={
            "id": "existing-id",
            "name": "Curated Name",
            "author": "Curated Author",
            "description": "Curated description",
            "license": "Apache-2.0",
        },
    )

    assert manifest["id"] == "existing-id"
    assert manifest["name"] == "Curated Name"
    assert manifest["author"] == "Curated Author"
    assert manifest["description"] == "Curated description"
    assert manifest["license"] == "Apache-2.0"
    assert "version" not in manifest


def test_update_readme_content_updates_generated_lines_non_destructively(tmp_path, monkeypatch):
    repo_root = make_plugin_repo(tmp_path)
    monkeypatch.setattr(repo_inspector, "_fetch_latest_app_version", lambda: "9.9.9")
    monkeypatch.setattr(repo_inspector, "get_git_username", lambda repo_path=".": "git-user")

    snapshot = inspect_repo(plugins_path=str(repo_root), include_hashes=True)
    existing = """
# Custom Repo

Keep this introduction.

## Available Entities

| Entity | ID | Category | Description | File |
| --- | --- | --- | --- | --- |
| Old Entity | old@1.0.0 | Old | Old description | entities/old.py |

## Available Transforms

| Transform | Target | Description | File |
| --- | --- | --- | --- |
| Old Transform | old@1.0.0 | Old Transform | transforms/old.py |

## Project Structure

```text
old/
  tree.txt
```

## Operational Notes

Detected external dependencies: old-value
Browser automation: old-browser
Network dependencies: old-network

## Additional Notes

Detected external imports not declared in pyproject dependencies: old-extra
Browser automation imports detected: old-browser-note
Network-facing imports detected: old-network-note

More custom text.
""".lstrip()

    updated = update_readme_content(existing, snapshot)

    assert "Keep this introduction." in updated
    assert "More custom text." in updated
    assert "| Website | website@1.0.0 | Web | Represents a domain from a website on the internet | entities/website.py |" in updated
    assert "| To IP | website@1.0.0 | To IP | transforms/website_transforms.py |" in updated
    assert "## Data Files" in updated
    assert "| data/lookups.json | json | Configuration or structured metadata |" in updated
    assert "old/tree.txt" not in updated
    assert "entities/" in updated
    assert "transforms/" in updated
    assert "Detected external dependencies: None detected" in updated
    assert "Browser automation: No browser automation imports detected" in updated
    assert "Network dependencies: Transforms appear to use network-facing modules: socket" in updated
    assert "Detected external imports not declared in pyproject dependencies: None" in updated
    assert "Browser automation imports detected: None" in updated
    assert "Network-facing imports detected: socket" in updated


def test_scaffold_default_repo_files_creates_examples_without_overwriting(tmp_path, monkeypatch):
    repo_root = make_plugin_repo(tmp_path)
    monkeypatch.setattr(repo_inspector, "get_git_username", lambda repo_path=".": "git-user")

    created = scaffold_default_repo_files(repo_root, repo_root=repo_root)

    created_names = {path.relative_to(repo_root).as_posix() for path in created}
    assert created_names == {
        ".gitignore",
        "LICENSE",
        "entities/generic_search.py",
        "entities/generic_result.py",
        "entities/example_data.json",
        "transforms/generic_transform.py",
    }

    license_text = (repo_root / "LICENSE").read_text(encoding="utf-8")
    gitignore_text = (repo_root / ".gitignore").read_text(encoding="utf-8")
    generic_search = (repo_root / "entities" / "generic_search.py").read_text(encoding="utf-8")
    generic_result = (repo_root / "entities" / "generic_result.py").read_text(encoding="utf-8")
    example_data = (repo_root / "entities" / "example_data.json").read_text(encoding="utf-8")
    generic_transform = (repo_root / "transforms" / "generic_transform.py").read_text(encoding="utf-8")

    assert "MIT License" in license_text
    assert "git-user" in license_text
    assert gitignore_text == "entities/__pycache__/\ntransforms/__pycache__/\n"
    assert 'author = "git-user"' in generic_search
    assert 'version = "1"' in generic_search
    assert 'read_resource_json(__file__, "example_data.json", default=[])' in generic_search
    assert 'author = "OSIB"' in generic_result
    assert '"value": "3"' in example_data
    assert 'target="generic_search@>=1"' in generic_transform

    second_run = scaffold_default_repo_files(repo_root, repo_root=repo_root)
    assert second_run == []


def test_build_manifest_id_uses_uuid_author_and_name_slug():
    manifest_id = build_manifest_id("OSINTBuddy Plugins Reloaded", "jerlendds")
    assert str(uuid.UUID(manifest_id[:36])) == manifest_id[:36]
    assert manifest_id.endswith("-jerlendds-osintbuddy-plugins-reloaded")
