from __future__ import annotations

from pathlib import Path

import osintbuddy.ob as ob


def test_init_cmd_skips_scaffold_and_overwrites_when_user_declines(tmp_path, monkeypatch):
    (tmp_path / "entities").mkdir()
    (tmp_path / "transforms").mkdir()
    (tmp_path / "entities" / "existing.py").write_text("class Existing: pass\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# Existing\n", encoding="utf-8")
    (tmp_path / "manifest.json").write_text("{}", encoding="utf-8")

    prompts: list[str] = []
    responses = iter(["n", "n", "n"])

    monkeypatch.setattr(ob, "resolve_plugins_root", lambda plugins_path=None: tmp_path)
    monkeypatch.setattr(ob, "ensure_local_git_repo", lambda path: False)
    monkeypatch.setattr("builtins.input", lambda prompt: prompts.append(prompt) or next(responses))
    inspected: list[dict[str, object]] = []

    def fake_inspect_repo(**kwargs):
        inspected.append(kwargs)
        return {"repo_root": tmp_path}

    monkeypatch.setattr(ob, "inspect_repo", fake_inspect_repo)

    scaffold_calls: list[Path] = []
    manifest_calls: list[object] = []
    readme_calls: list[object] = []

    monkeypatch.setattr(ob, "scaffold_default_repo_files", lambda plugins_root: scaffold_calls.append(plugins_root) or [])
    monkeypatch.setattr(ob, "write_manifest", lambda *args, **kwargs: manifest_calls.append((args, kwargs)))
    monkeypatch.setattr(ob, "write_readme", lambda *args, **kwargs: readme_calls.append((args, kwargs)))

    result = ob.init_cmd(interactive=True)

    assert result == {}
    assert scaffold_calls == []
    assert manifest_calls == []
    assert readme_calls == []
    assert inspected == [{"plugins_path": None, "include_hashes": True, "repo_root": tmp_path}]
    assert prompts == [
        "Existing plugins detected. `ob sync` is safer for updates. Would you like generic example entities and a generic transform created anyway? (y/n) ",
        "Existing manifest.json detected. `ob sync` is safer for updates. Would you like to overwrite it anyway? (y/n) ",
        "Existing README.md detected. `ob sync` is safer for updates. Would you like to overwrite it anyway? (y/n) ",
    ]


def test_init_cmd_scaffolds_before_manifest_when_user_confirms(tmp_path, monkeypatch):
    (tmp_path / "entities").mkdir()
    (tmp_path / "transforms").mkdir()
    (tmp_path / "entities" / "existing.py").write_text("class Existing: pass\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# Existing\n", encoding="utf-8")
    (tmp_path / "manifest.json").write_text("{}", encoding="utf-8")

    responses = iter(["y", "y", "y"])
    order: list[str] = []

    monkeypatch.setattr(ob, "resolve_plugins_root", lambda plugins_path=None: tmp_path)
    monkeypatch.setattr(ob, "ensure_local_git_repo", lambda path: order.append("git") or True)
    monkeypatch.setattr("builtins.input", lambda prompt: next(responses))

    def fake_scaffold(plugins_root, repo_root=None):
        order.append("scaffold")
        assert repo_root == tmp_path
        return [plugins_root / "entities" / "generic_search.py"]

    def fake_inspect_repo(**kwargs):
        order.append("inspect")
        assert kwargs["repo_root"] == tmp_path
        return {
            "repo_root": tmp_path,
            "entities": [],
            "transforms": [],
            "file_hashes": {},
        }

    def fake_write_manifest(snapshot, **kwargs):
        order.append("manifest")
        return tmp_path / "manifest.json", {"entities": [], "transforms": [], "file_hashes": {}}

    def fake_write_readme(snapshot, **kwargs):
        order.append("readme")
        return tmp_path / "README.md", "# Generated\n"

    monkeypatch.setattr(ob, "scaffold_default_repo_files", fake_scaffold)
    monkeypatch.setattr(ob, "inspect_repo", fake_inspect_repo)
    monkeypatch.setattr(ob, "write_manifest", fake_write_manifest)
    monkeypatch.setattr(ob, "write_readme", fake_write_readme)

    ob.init_cmd(interactive=True)

    assert order == ["git", "scaffold", "inspect", "manifest", "readme"]


def test_init_cmd_initializes_local_git_repo_before_inspection(tmp_path, monkeypatch):
    order: list[str] = []

    monkeypatch.setattr(ob, "resolve_plugins_root", lambda plugins_path=None: tmp_path)
    monkeypatch.setattr(ob, "ensure_local_git_repo", lambda path: order.append("git") or True)
    monkeypatch.setattr(
        ob,
        "scaffold_default_repo_files",
        lambda plugins_root, repo_root=None: order.append("scaffold") or [],
    )

    def fake_inspect_repo(**kwargs):
        order.append("inspect")
        assert kwargs["repo_root"] == tmp_path
        return {
            "repo_root": tmp_path,
            "entities": [],
            "transforms": [],
            "file_hashes": {},
        }

    monkeypatch.setattr(
        ob,
        "inspect_repo",
        fake_inspect_repo,
    )
    monkeypatch.setattr(
        ob,
        "write_manifest",
        lambda snapshot, **kwargs: order.append("manifest") or (tmp_path / "manifest.json", {"entities": [], "transforms": [], "file_hashes": {}}),
    )
    monkeypatch.setattr(
        ob,
        "write_readme",
        lambda snapshot, **kwargs: order.append("readme") or (tmp_path / "README.md", "# Generated\n"),
    )

    ob.init_cmd(interactive=False)

    assert order == ["git", "scaffold", "inspect", "manifest", "readme"]
