"""Repository inspection helpers for plugin manifests and README generation."""
from __future__ import annotations

import ast
import functools
import hashlib
import inspect
import json
import os
import re
import sys
import textwrap
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from osintbuddy.cli.display import print_success, print_error 
import httpx

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore

from packaging.specifiers import SpecifierSet
from packaging.version import InvalidVersion, Version

from osintbuddy import __version__, load_plugins_fs
from osintbuddy.plugins import Plugin, Registry
from osintbuddy.utils import to_snake_case


DATA_FILE_EXTENSIONS = {
    ".csv",
    ".json",
    ".jsonl",
    ".ndjson",
    ".tsv",
    ".txt",
    ".yaml",
    ".yml",
}

NETWORK_IMPORT_HINTS = {
    "aiohttp",
    "dns",
    "httpx",
    "requests",
    "socket",
    "urllib",
    "whois",
}

BROWSER_IMPORT_HINTS = {
    "playwright",
    "selenium",
}

DEFAULT_GIT_AUTHOR_MSG = (
    "No git author found - Please configure git on your system: "
    "`git config --global user.name <your_username>`"
)

LATEST_APP_RELEASE_URL = "https://api.github.com/repos/osintbuddy/osintbuddy/releases/latest"
GITHUB_API_HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}

DEFAULT_EXAMPLE_DATA = """[
  {
    "label": "Example label",
    "description": "Some description",
    "value": "1"
  },
  {
    "label": "Example label",
    "description": "Some description",
    "value": "2"
  },
  {
    "label": "Example label",
    "description": "Some description",
    "value": "3"
  }
]
"""


def resolve_plugins_root(plugins_path: str | None = None, cwd: Path | None = None) -> Path:
    """Resolve the plugin root directory.

    Supports both:
    - repo-root/entities + repo-root/transforms
    - repo-root/plugins/entities + repo-root/plugins/transforms
    """
    if plugins_path:
        return Path(plugins_path).expanduser().resolve()

    current = (cwd or Path.cwd()).resolve()
    direct_entities = current / "entities"
    direct_transforms = current / "transforms"
    if direct_entities.is_dir() or direct_transforms.is_dir():
        return current

    nested_plugins = current / "plugins"
    nested_entities = nested_plugins / "entities"
    nested_transforms = nested_plugins / "transforms"
    if nested_entities.is_dir() or nested_transforms.is_dir():
        return nested_plugins

    return current


def has_local_git_repo(path: Path) -> bool:
    """Return True when the directory itself contains a git repository."""
    git_dir = path / ".git"
    return git_dir.is_dir() or git_dir.is_file()


def _discover_dulwich_repo(start: Path):
    """Discover a repository with Dulwich, returning None when unavailable."""
    try:
        from dulwich.repo import Repo

        return Repo.discover(str(start))
    except Exception:
        return None


def ensure_local_git_repo(path: Path) -> bool:
    """Initialize a git repository in the target directory if one does not already exist."""
    if has_local_git_repo(path):
        return False

    try:
        from dulwich.repo import Repo

        path.mkdir(parents=True, exist_ok=True)
        Repo.init(str(path))
        print_success("A git repo was successfully initialized for your plugins!")
        return True
    except Exception:
        print_error("We failed to initialize a git repo for your plugins!")
        return False


def find_repo_root(start: Path | None = None) -> Path:
    """Find the git root for a path, or fall back to the nearest sensible directory."""
    base = (start or Path.cwd()).resolve()

    if has_local_git_repo(base):
        return base

    repo = _discover_dulwich_repo(base)
    if repo is not None:
        repo_path = getattr(repo, "path", None)
        if repo_path:
            if isinstance(repo_path, bytes):
                repo_path = repo_path.decode("utf-8", errors="replace")
            return Path(str(repo_path)).resolve()

    for candidate in [base, *base.parents]:
        if (candidate / ".git").exists():
            return candidate

    return base


def reset_registry() -> None:
    """Reset the global plugin registry before a fresh load."""
    Registry.labels.clear()
    Registry.plugins.clear()
    Registry.ui_labels.clear()
    if hasattr(Registry, "transforms_map"):
        Registry.transforms_map.clear()


def prepare_registry(plugins_root: Path) -> dict[str, type[Plugin]]:
    """Load plugins for inspection."""
    reset_registry()
    return load_plugins_fs(str(plugins_root))


def _relpath(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.resolve().relative_to(root.resolve()).as_posix()


def _module_from_path(path: str) -> str:
    if path.endswith(".py"):
        path = path[:-3]
    return path.replace("/", ".")


def _normalize_author(value: str | list[str] | None) -> str:
    if isinstance(value, list):
        return ", ".join(str(item) for item in value if str(item).strip())
    if value is None:
        return "Unknown"
    text = str(value).strip()
    return text or "Unknown"


def _normalize_category(value: str | list[str] | None) -> str:
    if isinstance(value, list):
        return ", ".join(str(item) for item in value if str(item).strip())
    return str(value or "").strip()


def _slugify_manifest_component(value: str | None) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", str(value or "").strip().lower())
    text = re.sub(r"-{2,}", "-", text).strip("-")
    return text or "unknown"


def build_manifest_id(name: str, author: str) -> str:
    """Build a stable-format manifest id for newly initialized repos."""
    return "-".join([
        str(uuid4()),
        _slugify_manifest_component(author),
        _slugify_manifest_component(name),
    ])


def _decode(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    value = str(value).strip()
    return value or None


def get_git_username(repo_path: str = ".") -> str:
    """Resolve the git username for a repository using Dulwich config handling."""
    try:
        from dulwich.repo import Repo

        repo = Repo.discover(repo_path)
        config_stack = repo.get_config_stack()
        username = _decode(config_stack.get((b"user",), b"name"))
        if username:
            return username
    except Exception:
        pass

    try:
        from dulwich.config import StackedConfig

        username = _decode(StackedConfig.default().get((b"user",), b"name"))
        if username:
            return username
    except Exception:
        pass

    return DEFAULT_GIT_AUTHOR_MSG


def scaffold_default_repo_files(plugins_root: Path, repo_root: Path | None = None) -> list[Path]:
    """Create default example plugin files for a repo without overwriting user files."""
    repo_root = repo_root or find_repo_root(plugins_root)
    entities_dir = plugins_root / "entities"
    transforms_dir = plugins_root / "transforms"
    entities_dir.mkdir(parents=True, exist_ok=True)
    transforms_dir.mkdir(parents=True, exist_ok=True)

    git_username = get_git_username(str(repo_root))
    search_author = json.dumps(git_username)
    license_year = datetime.now().year

    files_to_create: dict[Path, str] = {
        repo_root / "LICENSE": textwrap.dedent(
            f"""\
            MIT License

            Copyright (c) {license_year} {git_username}

            Permission is hereby granted, free of charge, to any person obtaining a copy
            of this software and associated documentation files (the "Software"), to deal
            in the Software without restriction, including without limitation the rights
            to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
            copies of the Software, and to permit persons to whom the Software is
            furnished to do so, subject to the following conditions:

            The above copyright notice and this permission notice shall be included in all
            copies or substantial portions of the Software.

            THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
            IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
            FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
            AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
            LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
            OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
            SOFTWARE.
            """
        ),
        repo_root / ".gitignore": "entities/__pycache__/\ntransforms/__pycache__/\n",
        entities_dir / "generic_search.py": textwrap.dedent(
            f"""\
            from osintbuddy import Plugin, read_resource_json
            from osintbuddy.elements import TextInput, DropdownInput


            cses_db = read_resource_json(__file__, "example_data.json", default=[])


            class GenericSearchExample(Plugin):
                version = "1"
                label = "Generic Search"
                category = "Search"
                description = "A generic entity description..."
                author = {search_author}

                color = "#2c36c266"
                icon = "world-search"

                elements = [
                    TextInput(label="Query", icon="search"),
                    DropdownInput(label="Options", options=cses_db)
                ]
            """
        ),
        entities_dir / "generic_result.py": textwrap.dedent(
            """\
            from osintbuddy.elements import Title, CopyText, Text
            from osintbuddy import Plugin


            class GenericResultExample(Plugin):
                version = "1"

                label = "Generic Result"
                category = "Search"
                color = "#59A12866"
                icon = "brand-google"
                author = "OSIB"
                show_option = False

                elements = [
                    Title(label="data"),
                    Text(label="example"),
                ]
            """
        ),
        entities_dir / "example_data.json": DEFAULT_EXAMPLE_DATA,
        transforms_dir / "generic_transform.py": textwrap.dedent(
            """\
            from osintbuddy import transform, Registry
            from osintbuddy.errors import PluginError


            @transform(
                target="generic_search@>=1",
                label="To generic results",
                icon="search"
            )
            async def to_generic_results(entity):
                if not entity.query or not entity.options:
                    raise PluginError("The Query and Options fields are required to run this transform.")
                generic_result = await Registry.get_entity("generic_result")
                # To return many entities use:
                # entities = []
                # for i in range(5):
                #     entities.append(generic_result.create(
                #         data=f"{i} {entity.query}",
                #         example=f"{i} {entity.options}",
                #     ))
                # return entities

                # Returning a single entity:
                new_entity = generic_result.create(
                    data=entity.query,
                    example=entity.options,
                )
                return new_entity
            """
        ),
    }

    created: list[Path] = []
    for path, content in files_to_create.items():
        if path.exists():
            continue
        path.write_text(content.rstrip() + "\n", encoding="utf-8")
        created.append(path)

    return created


def _read_pyproject(repo_root: Path) -> dict[str, Any]:
    pyproject = repo_root / "pyproject.toml"
    if not pyproject.is_file():
        return {}
    try:
        return tomllib.loads(pyproject.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return {}


def _extract_requirement_name(requirement: str) -> str:
    requirement = requirement.split(";", 1)[0].strip()
    requirement = requirement.split("[", 1)[0].strip()
    match = re.match(r"^[A-Za-z0-9_.-]+", requirement)
    return (match.group(0).lower() if match else requirement.lower()).replace("-", "_")


def _find_version_from_source(repo_root: Path, project_name: str | None = None) -> str | None:
    package_roots = []
    if project_name:
        package_roots.append(project_name.replace("-", "_"))
    package_roots.extend([repo_root.name.replace("-", "_"), "src"])

    candidates: list[Path] = []
    for package_root in package_roots:
        if not package_root:
            continue
        direct = repo_root / package_root / "__init__.py"
        src_pkg = repo_root / "src" / package_root / "__init__.py"
        if direct.is_file():
            candidates.append(direct)
        if src_pkg.is_file():
            candidates.append(src_pkg)

    version_pattern = re.compile(r"""__version__\s*=\s*["']([^"']+)["']""")
    for candidate in candidates:
        try:
            match = version_pattern.search(candidate.read_text(encoding="utf-8"))
        except OSError:
            continue
        if match:
            return match.group(1)
    return None


def _parse_repo_slug(repo_url: str | None) -> str | None:
    if not repo_url:
        return None
    text = repo_url.strip()
    if not text:
        return None
    if text.startswith("git@github.com:"):
        text = text.split(":", 1)[1]
    text = re.sub(r"^https?://github\.com/", "", text)
    text = re.sub(r"\.git$", "", text)
    text = text.strip("/")
    return text or None


def _git_remote_url(repo_root: Path) -> str | None:
    repo = _discover_dulwich_repo(repo_root)
    if repo is None:
        return None

    try:
        config_stack = repo.get_config_stack()
        remote_url = _decode(config_stack.get((b"remote", b"origin"), b"url"))
    except Exception:
        return None

    text = (remote_url or "").strip()
    if not text:
        return None
    if text.startswith("git@github.com:"):
        slug = text.split(":", 1)[1].removesuffix(".git")
        return f"https://github.com/{slug}"
    return text.removesuffix(".git")


@functools.lru_cache(maxsize=1)
def _fetch_latest_app_version() -> str:
    """Fetch the latest OSINTBuddy app version from GitHub releases."""
    try:
        with httpx.Client(timeout=5.0, follow_redirects=True, headers=GITHUB_API_HEADERS) as client:
            response = client.get(LATEST_APP_RELEASE_URL)
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, ValueError, TypeError):
        return __version__

    tag_name = str(payload.get("tag_name", "")).strip()
    if not tag_name:
        return __version__
    return tag_name.lstrip("v")


def _list_repo_files(repo_root: Path) -> list[str]:
    files: set[str] = set()

    repo = _discover_dulwich_repo(repo_root)
    if repo is not None:
        try:
            index = repo.open_index()
            for item in index:
                relative_path = item.decode("utf-8", errors="replace") if isinstance(item, bytes) else str(item)
                if _should_ignore_repo_file(repo_root / relative_path, repo_root):
                    continue
                files.add(relative_path)
        except Exception:
            pass

    for path in repo_root.rglob("*"):
        if not path.is_file():
            continue
        if _should_ignore_repo_file(path, repo_root):
            continue
        files.add(_relpath(path, repo_root))

    return sorted(files)


def _should_ignore_repo_file(path: Path, repo_root: Path) -> bool:
    try:
        relative_parts = path.relative_to(repo_root).parts
    except ValueError:
        relative_parts = path.parts

    if ".git" in relative_parts or "__pycache__" in relative_parts:
        return True

    current = path.parent
    while current != repo_root and current != current.parent:
        if (current / "pyvenv.cfg").is_file():
            return True
        current = current.parent

    return False


def _file_hashes(repo_root: Path, files: list[str]) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for relative_path in files:
        path = repo_root / relative_path
        try:
            payload = path.read_bytes()
        except OSError:
            continue
        hashes[relative_path] = hashlib.sha256(payload).hexdigest()
    return hashes


def _entity_records(repo_root: Path) -> list[dict[str, Any]]:
    entities: list[dict[str, Any]] = []
    for plugin_cls in Registry.plugins.values():
        module_file = inspect.getsourcefile(plugin_cls)
        if not module_file:
            continue
        file_path = Path(module_file).resolve()
        try:
            relative_path = _relpath(file_path, repo_root)
        except ValueError:
            relative_path = file_path.name

        label = getattr(plugin_cls, "label", plugin_cls.__name__)
        entity_key = getattr(plugin_cls, "entity_id", None) or to_snake_case(label)
        version = getattr(plugin_cls, "version", "0.0.0")
        record: dict[str, Any] = {
            "id": f"{entity_key}@{version}",
            "version": version,
            "label": label,
            "category": _normalize_category(getattr(plugin_cls, "category", "")),
            "color": getattr(plugin_cls, "color", "#145070"),
            "icon": getattr(plugin_cls, "icon", "atom-2"),
            "author": _normalize_author(getattr(plugin_cls, "author", "Unknown")),
            "description": getattr(plugin_cls, "description", "") or "",
            "file": relative_path,
            "module": _module_from_path(relative_path),
            "class": plugin_cls.__name__,
        }
        tags = getattr(plugin_cls, "tags", None)
        if tags:
            record["tags"] = tags
        entities.append(record)

    return sorted(entities, key=lambda item: (item["label"].lower(), item["id"]))


def _resolve_transform_target(
    entity_id: str,
    version_spec: str,
    entities: list[dict[str, Any]],
) -> str:
    target_spec = f"{entity_id}@{version_spec}"

    try:
        specifier = SpecifierSet(version_spec)
    except Exception:
        try:
            specifier = SpecifierSet(f"=={version_spec}")
        except Exception:
            return target_spec

    matches: list[str] = []
    for entity in entities:
        if not entity["id"].startswith(f"{entity_id}@"):
            continue
        try:
            version = Version(entity.get("version", "---"))
        except InvalidVersion:
            continue
        if version in specifier:
            matches.append(entity["id"])

    if len(matches) == 1:
        return matches[0]
    return target_spec


def _transform_records(repo_root: Path, entities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    transforms: list[dict[str, Any]] = []
    seen: set[str] = set()

    for buckets in Registry.transforms_map.values():
        for _, mapping in buckets:
            for fn in mapping.values():
                source_fn = inspect.unwrap(fn)
                file_name = inspect.getsourcefile(source_fn)
                if not file_name:
                    continue
                file_path = Path(file_name).resolve()
                try:
                    relative_path = _relpath(file_path, repo_root)
                except ValueError:
                    relative_path = file_path.name

                module_name = _module_from_path(relative_path)
                function_name = source_fn.__name__
                transform_id = f"{module_name}:{function_name}"
                if transform_id in seen:
                    continue
                seen.add(transform_id)

                entity_transform = getattr(fn, "entity_transform", "")
                entity_version = getattr(fn, "entity_version", "")
                record: dict[str, Any] = {
                    "id": transform_id,
                    "target": _resolve_transform_target(entity_transform, entity_version, entities),
                    "target_spec": f"{entity_transform}@{entity_version}",
                    "label": getattr(fn, "label", function_name),
                    "icon": getattr(fn, "icon", "list"),
                    "function": function_name,
                    "file": relative_path,
                    "module": module_name,
                }
                deps = getattr(fn, "deps", None)
                if deps:
                    record["deps"] = deps
                accepts = getattr(fn, "accepts", None)
                if accepts:
                    record["accepts"] = accepts
                produces = getattr(fn, "produces", None)
                if produces:
                    record["produces"] = produces
                transforms.append(record)

    return sorted(transforms, key=lambda item: (item["file"], item["function"], item["label"].lower()))


def _local_module_roots(repo_root: Path) -> set[str]:
    roots: set[str] = set()
    for path in repo_root.iterdir():
        if path.name.startswith("."):
            continue
        if path.is_dir():
            roots.add(path.name.replace("-", "_"))
        elif path.is_file() and path.suffix == ".py":
            roots.add(path.stem.replace("-", "_"))
    src_dir = repo_root / "src"
    if src_dir.is_dir():
        for path in src_dir.iterdir():
            if path.is_dir():
                roots.add(path.name.replace("-", "_"))
            elif path.is_file() and path.suffix == ".py":
                roots.add(path.stem.replace("-", "_"))
    return roots


def _analyze_imports(repo_root: Path, python_files: list[str], pyproject_data: dict[str, Any]) -> dict[str, Any]:
    local_roots = _local_module_roots(repo_root)
    stdlib = set(getattr(sys, "stdlib_module_names", set()))
    imports_by_file: dict[str, list[str]] = {}
    external_imports: set[str] = set()
    imported_roots: set[str] = set()

    for relative_path in python_files:
        path = repo_root / relative_path
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue

        file_imports: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    file_imports.add(alias.name.split(".", 1)[0])
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    continue
                if node.module:
                    file_imports.add(node.module.split(".", 1)[0])

        imports_by_file[relative_path] = sorted(file_imports)
        imported_roots.update(module_name.replace("-", "_") for module_name in file_imports)
        for module_name in file_imports:
            normalized = module_name.replace("-", "_")
            if normalized in stdlib:
                continue
            if normalized in local_roots:
                continue
            if normalized in {"osintbuddy"}:
                continue
            external_imports.add(normalized)

    project = pyproject_data.get("project", {})
    declared_requirements = list(project.get("dependencies", []))
    for dependency_group in project.get("optional-dependencies", {}).values():
        declared_requirements.extend(dependency_group)
    declared = {_extract_requirement_name(requirement) for requirement in declared_requirements}

    undeclared = sorted(
        module_name for module_name in external_imports
        if module_name not in declared
    )

    browser = sorted(module_name for module_name in external_imports if module_name in BROWSER_IMPORT_HINTS)
    network = sorted(
        module_name for module_name in imported_roots
        if module_name in NETWORK_IMPORT_HINTS or module_name in browser
    )

    return {
        "imports_by_file": imports_by_file,
        "external_dependencies": sorted(external_imports),
        "undeclared_dependencies": undeclared,
        "browser_dependencies": browser,
        "network_dependencies": sorted(set(network)),
    }


def _data_file_records(repo_root: Path, files: list[str]) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    for relative_path in files:
        path = Path(relative_path)
        suffix = path.suffix.lower()
        if suffix not in DATA_FILE_EXTENSIONS:
            continue
        if path.name in {"README.md", "manifest.json", "pyproject.toml"}:
            continue

        file_type = suffix.lstrip(".")
        purpose = "Structured project data"
        parent_text = "/".join(path.parts[:-1]).lower()
        stem = path.stem.lower()

        if "wordlist" in parent_text or "wordlist" in stem:
            purpose = "Wordlist or lookup data"
        elif suffix in {
            ".json", ".yaml", ".yml",
            ".xml", ".toml", ".ini", ".conf", ".properties", ".env",
            ".pkl", ".pickle", ".msgpack", ".bson", ".cbor",
            ".lmdb", ".mdb", ".accdb", ".dbf", ".dat",
        }:
            purpose = "Configuration or structured metadata"
        elif suffix in {
            ".csv", ".tsv",
            ".xlsx", ".xls", ".ods",
            ".parquet", ".feather", ".arrow",
            ".h5", ".hdf5", ".db", ".sqlite"
        }:
            purpose = "Tabular reference data"
        elif suffix in {".ndjson", ".jsonl", ".txt"}:
            purpose = "Reference text data"

        records.append({
            "file": relative_path,
            "type": file_type,
            "purpose": purpose,
        })

    return sorted(records, key=lambda item: item["file"])


def inspect_repo(
    plugins_path: str | None = None,
    include_hashes: bool = True,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Inspect a plugin repository and derive a normalized metadata graph."""
    plugins_root = resolve_plugins_root(plugins_path)
    repo_root = repo_root.resolve() if repo_root is not None else find_repo_root(plugins_root)
    
    pyproject_data = _read_pyproject(repo_root)
    prepare_registry(plugins_root)

    files = _list_repo_files(repo_root)
    entities = _entity_records(repo_root)
    transforms = _transform_records(repo_root, entities)
    python_files = [path for path in files if path.endswith(".py")]
    import_analysis = _analyze_imports(repo_root, python_files, pyproject_data)
    data_files = _data_file_records(repo_root, files)

    project = pyproject_data.get("project", {})
    repo_url = (
        project.get("urls", {}).get("Repository")
        or project.get("urls", {}).get("Source")
        or _git_remote_url(repo_root)
    )
    repo_slug = _parse_repo_slug(repo_url)
    homepage = project.get("urls", {}).get("Homepage") or repo_url
    project_name = project.get("name") or repo_root.name
    project_version = project.get("version") or _find_version_from_source(repo_root, project_name) or "0.1.0"
    primary_author = get_git_username(str(repo_root))

    manifest_path = "manifest.json"
    readme_path = "README.md"

    warnings: list[str] = []
    snapshot: dict[str, Any] = {
        "repo_root": repo_root,
        "plugins_root": plugins_root,
        "metadata": {
            "id": to_snake_case(project_name),
            "name": project_name,
            "author": primary_author,
            "description": project.get("description") or "Describe your OSINTBuddy plugin repository...",
            "version": project_version,
            "repo": repo_slug,
            "repo_url": repo_url,
            "homepage": homepage,
            "license": (
                project.get("license", {}).get("text")
                if isinstance(project.get("license"), dict)
                else project.get("license")
            ) or ("MIT" if (repo_root / "LICENSE").exists() else None),
            "tags": list(project.get("keywords", [])),
            "min_app_version": project.get("min_app_version") or _fetch_latest_app_version(),
        },
        "files": files,
        "file_hashes": _file_hashes(repo_root, files) if include_hashes else {},
        "entities": entities,
        "transforms": transforms,
        "data_files": data_files,
        "import_analysis": import_analysis,
        "warnings": warnings,
        "manifest_path": manifest_path,
        "readme_path": readme_path,
    }
    return snapshot


def build_manifest(
    snapshot: dict[str, Any],
    include_hashes: bool = True,
    preserved_values: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the machine-readable manifest document."""
    metadata = snapshot["metadata"]
    preserved_values = preserved_values or {}
    manifest_author = preserved_values.get("author", metadata["author"])
    manifest_name = preserved_values.get("name", metadata["name"])

    manifest: dict[str, Any] = {
        "id": preserved_values.get("id", build_manifest_id(manifest_name, manifest_author)),
        "name": manifest_name,
        "author": manifest_author,
        "description": preserved_values.get("description", metadata["description"]),
        "repo": metadata.get("repo"),
        "homepage": metadata.get("homepage"),
        "license": preserved_values.get("license", metadata.get("license")),
        "warnings": snapshot["warnings"],
        "tags": metadata.get("tags", []),
        "min_app_version": metadata.get("min_app_version"),
        "entities": snapshot["entities"],
        "transforms": snapshot["transforms"],
    }

    if include_hashes and snapshot.get("file_hashes"):
        file_hashes = dict(snapshot["file_hashes"])
        manifest["file_hashes"] = file_hashes

    return manifest


def _humanize_identifier(value: str) -> str:
    return value.replace("_", " ").strip().title()


def _transform_description(transform: dict[str, Any]) -> str:
    label = transform.get("label", "").strip()
    if label:
        return label
    function_name = transform.get("function", "")
    target = transform.get("target", "")
    target_label = target.split("@", 1)[0].replace("_", " ")
    if function_name.startswith("to_"):
        return f"Converts {target_label} to {_humanize_identifier(function_name[3:]).lower()}"
    return f"Runs {_humanize_identifier(function_name).lower()} on {target_label}"


def _markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def _build_tree(paths: list[str]) -> str:
    tree: dict[str, Any] = {}
    for relative_path in sorted(set(paths)):
        node = tree
        parts = relative_path.split("/")
        for part in parts:
            node = node.setdefault(part, {})

    lines: list[str] = []

    def walk(node: dict[str, Any], depth: int = 0) -> None:
        for key in sorted(node):
            child = node[key]
            indent = "  " * depth
            if child:
                lines.append(f"{indent}{key}/")
                walk(child, depth + 1)
            else:
                lines.append(f"{indent}{key}")

    walk(tree)
    return "\n".join(lines)


def _section_body_pattern(heading: str) -> re.Pattern[str]:
    return re.compile(
        rf"(?ms)^## {re.escape(heading)}\s*\n(.*?)(?=^## |\Z)"
    )


def _replace_or_append_section(content: str, heading: str, body: str) -> str:
    body = body.rstrip()
    replacement = f"## {heading}\n\n{body}\n\n"
    pattern = _section_body_pattern(heading)
    if pattern.search(content):
        return pattern.sub(replacement, content, count=1)
    return content.rstrip() + f"\n\n{replacement}"


def build_readme(snapshot: dict[str, Any]) -> str:
    """Build a human-readable README from the normalized metadata graph."""
    metadata = snapshot["metadata"]
    entities = snapshot["entities"]
    transforms = snapshot["transforms"]
    data_files = snapshot["data_files"]
    import_analysis = snapshot["import_analysis"]

    entity_rows = [
        [
            entity["label"],
            entity["id"],
            entity.get("category") or "",
            entity.get("description") or "",
            entity["file"],
        ]
        for entity in entities
    ]

    transform_rows = [
        [
            transform["label"],
            transform["target"],
            _transform_description(transform),
            transform["file"],
        ]
        for transform in transforms
    ]

    data_rows = [
        [item["file"], item["type"], item["purpose"]]
        for item in data_files
    ]

    tree_paths = [
        path for path in snapshot["files"]
        if path.startswith("entities/") or path.startswith("transforms/")
    ]
    tree_paths.extend(item["file"] for item in data_files)
    for root_file in ("pyproject.toml", snapshot["manifest_path"], snapshot["readme_path"]):
        if root_file not in tree_paths:
            tree_paths.append(root_file)

    framework_link = metadata.get("repo_url") or "https://github.com/osintbuddy/osintbuddy"
    app_link = metadata.get("homepage") or "https://osintbuddy.com"
    external_dependencies = import_analysis["external_dependencies"]
    network_dependencies = import_analysis["network_dependencies"]
    browser_dependencies = import_analysis["browser_dependencies"]
    undeclared_dependencies = import_analysis["undeclared_dependencies"]

    operational_lines = [
        "**Detected external dependencies**: "
        + (", ".join(external_dependencies) if external_dependencies else "None detected"),
    ]

    lines = [
        f"# OSIB: Plugin Repo Title...",
        "",
        metadata["description"],
        "",
        f"- Status: Generated by `ob init`; **review before publishing.**",
        f"- Install / use: Run inside a Python virtual environment where `osintbuddy` is installed, then use `ob init` from the root of this repo and `ob sync` after repo updates.",
        "",
        f"- OSIB: Framework - {framework_link}",
        f"- OSIB: Community Market - {app_link}",
        "",
        "## Available Entities",
        "",
        _markdown_table(
            ["Entity", "ID", "Category", "Description", "File"],
            entity_rows or [["(none)", "", "", "", ""]],
        ),
        "",
        "## Available Transforms",
        "",
        _markdown_table(
            ["Transform", "Target", "Description", "File"],
            transform_rows or [["(none)", "", "", ""]],
        ),
        "",
    ]

    if data_rows:
        lines.extend([
            "## Data Files",
            "",
            _markdown_table(["File", "Type", "Purpose"], data_rows),
            "",
        ])

    lines.extend([
        "## Operational Notes",
        "",
        *operational_lines,
        "",
    ])

    return "\n".join(lines).rstrip() + "\n"


def _build_entities_section(snapshot: dict[str, Any]) -> str:
    entity_rows = [
        [
            entity["label"],
            entity["id"],
            entity.get("category") or "",
            entity.get("description") or "",
            entity["file"],
        ]
        for entity in snapshot["entities"]
    ]
    return _markdown_table(
        ["Entity", "ID", "Category", "Description", "File"],
        entity_rows or [["(none)", "", "", "", ""]],
    )


def _build_transforms_section(snapshot: dict[str, Any]) -> str:
    transform_rows = [
        [
            transform["label"],
            transform["target"],
            _transform_description(transform),
            transform["file"],
        ]
        for transform in snapshot["transforms"]
    ]
    return _markdown_table(
        ["Transform", "Target", "Description", "File"],
        transform_rows or [["(none)", "", "", ""]],
    )


def _build_data_files_section(snapshot: dict[str, Any]) -> str:
    data_rows = [
        [item["file"], item["type"], item["purpose"]]
        for item in snapshot["data_files"]
    ]
    return _markdown_table(
        ["File", "Type", "Purpose"],
        data_rows or [["(none)", "", ""]],
    )


def _build_project_structure_section(snapshot: dict[str, Any]) -> str:
    tree_paths = [
        path for path in snapshot["files"]
        if path.startswith("entities/") or path.startswith("transforms/")
    ]
    tree_paths.extend(item["file"] for item in snapshot["data_files"])
    for root_file in ("pyproject.toml", snapshot["manifest_path"], snapshot["readme_path"]):
        if root_file not in tree_paths:
            tree_paths.append(root_file)
    return "```text\n" + _build_tree(tree_paths) + "\n```"


def _replace_readme_line(content: str, label: str, value: str) -> tuple[str, bool]:
    pattern = re.compile(
        rf"(?m)^[ \t>*-]*\*{{0,2}}{re.escape(label)}\*{{0,2}}:.*$"
    )
    replacement = f"{label}: {value}"
    if pattern.search(content):
        return pattern.sub(replacement, content), True
    return content, False


def _append_lines_under_heading(content: str, heading: str, lines: list[str]) -> str:
    if not lines:
        return content

    heading_pattern = re.compile(rf"(?m)^## {re.escape(heading)}\s*$")
    match = heading_pattern.search(content)
    block = "\n".join(lines)
    if match:
        insert_at = match.end()
        return content[:insert_at] + "\n\n" + block + content[insert_at:]
    return content.rstrip() + f"\n\n## {heading}\n\n{block}\n"


def update_readme_content(existing_readme: str, snapshot: dict[str, Any]) -> str:
    """Update generated metadata lines inside an existing README without replacing other content."""
    import_analysis = snapshot["import_analysis"]
    external_dependencies = import_analysis["external_dependencies"]
    browser_dependencies = import_analysis["browser_dependencies"]
    network_dependencies = import_analysis["network_dependencies"]
    undeclared_dependencies = import_analysis["undeclared_dependencies"]

    operational_updates = {
        "Detected external dependencies": ", ".join(external_dependencies) if external_dependencies else "None detected",
        "Browser automation": "Uses " + ", ".join(browser_dependencies) if browser_dependencies else "No browser automation imports detected",
        "Network dependencies": (
            "Transforms appear to use network-facing modules: " + ", ".join(network_dependencies)
            if network_dependencies
            else "No obvious network-facing imports detected"
        ),
    }
    content = existing_readme
    missing_operational: list[str] = []

    for label, value in operational_updates.items():
        content, replaced = _replace_readme_line(content, label, value)
        if not replaced:
            missing_operational.append(f"{label}: {value}")

    content = _replace_or_append_section(
        content,
        "Available Entities",
        _build_entities_section(snapshot),
    )
    content = _replace_or_append_section(
        content,
        "Available Transforms",
        _build_transforms_section(snapshot),
    )
    content = _replace_or_append_section(
        content,
        "Data Files",
        _build_data_files_section(snapshot),
    )
    content = _append_lines_under_heading(content, "Operational Notes", missing_operational)
    return content.rstrip() + "\n"


def load_existing_manifest(repo_root: Path, manifest_path: str | None = None) -> dict[str, Any]:
    """Load the existing manifest if present."""
    path = Path(manifest_path).expanduser().resolve() if manifest_path else repo_root / "manifest.json"
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def write_manifest(
    snapshot: dict[str, Any],
    output_path: str | None = None,
    include_hashes: bool = True,
    preserved_values: dict[str, Any] | None = None,
) -> tuple[Path, dict[str, Any]]:
    """Write manifest.json to disk."""
    repo_root = snapshot["repo_root"]
    destination = Path(output_path).expanduser().resolve() if output_path else repo_root / "manifest.json"
    local_snapshot = dict(snapshot)
    try:
        local_snapshot["manifest_path"] = _relpath(destination, repo_root)
    except ValueError:
        local_snapshot["manifest_path"] = destination.name
    manifest = build_manifest(
        local_snapshot,
        include_hashes=include_hashes,
        preserved_values=preserved_values,
    )
    destination.write_text(json.dumps(manifest, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    return destination, manifest


def write_readme(snapshot: dict[str, Any], output_path: str | None = None) -> tuple[Path, str]:
    """Write README.md to disk."""
    repo_root = snapshot["repo_root"]
    destination = Path(output_path).expanduser().resolve() if output_path else repo_root / "README.md"
    local_snapshot = dict(snapshot)
    try:
        local_snapshot["readme_path"] = _relpath(destination, repo_root)
    except ValueError:
        local_snapshot["readme_path"] = destination.name
    readme = build_readme(local_snapshot)
    destination.write_text(readme, encoding="utf-8")
    return destination, readme


def sync_readme(snapshot: dict[str, Any], output_path: str | None = None) -> tuple[Path | None, str | None]:
    """Patch generated metadata lines in an existing README without replacing user-written content."""
    repo_root = snapshot["repo_root"]
    destination = Path(output_path).expanduser().resolve() if output_path else repo_root / "README.md"
    if not destination.is_file():
        return None, None

    try:
        existing = destination.read_text(encoding="utf-8")
    except OSError:
        return None, None

    updated = update_readme_content(existing, snapshot)
    destination.write_text(updated, encoding="utf-8")
    return destination, updated
