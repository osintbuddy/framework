#!/usr/bin/env python3
"""OSINTBuddy plugins CLI

This script contains the commands needed to manage an OSINTBuddy Plugins service.

Commands:
    ob start                    Start the FastAPI microservice
    ob init                     Load initial osintbuddy entities
    ob transform <payload>      Run a transform
    ob entities                 List all entities
    ob transforms -L <label>    List transforms for an entity
    ob ls plugins               List all plugins
    ob entities json            Full entity JSON for UI
    ob blueprints [-L <label>]  Get entity blueprints
    ob compile <json> [-O out]  Compile JSON entity to Python
    ob compile dir <dir>        Batch compile directory
"""
from __future__ import annotations

import asyncio
import inspect
import json
import os
import sys
from argparse import ArgumentParser, RawDescriptionHelpFormatter
from datetime import datetime, timezone
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.traceback import install as install_traceback

from osintbuddy import Registry, __version__, load_plugins_fs
from osintbuddy.plugins import TransformPayload
from osintbuddy.utils import to_snake_case
from osintbuddy.results import normalize_result
from osintbuddy.output import emit_result, emit_error, emit_progress, emit_json
from osintbuddy.errors import PluginError, ErrorCode
from osintbuddy.cli.console import console, err_console, OSIB_THEME
from osintbuddy.cli.display import (
    print_banner,
    print_error,
    print_success,
    print_warning,
    print_info,
    print_entities_table,
    print_transforms_table,
)
from osintbuddy.cli.progress import (
    Step,
    StepRunner,
    TransformProgress,
    PluginLoadProgress,
)
from osintbuddy.cli.logging import setup_logging, get_logger

# Install rich traceback handler for beautiful error display
install_traceback(show_locals=True, console=err_console)

# Setup logging
log = setup_logging()

DEFAULT_ENTITIES = [
    "cse_result.py",
    "cse_search.py",
    "dns.py",
    "google_cache_result.py",
    "google_cache_search.py",
    "google_result.py",
    "google_search.py",
    "ip.py",
    "ip_geolocation.py",
    "subdomain.py",
    "telegram_websearch.py",
    "url.py",
    "username.py",
    "username_profile.py",
    "whois.py",
    "website.py"
]




def load_git_entities() -> None:
    """Download default entities from GitHub."""
    import httpx

    plugins_dir = Path("./plugins")
    if not plugins_dir.is_dir():
        log.info("Creating ./plugins directory")
        plugins_dir.mkdir(parents=True, exist_ok=True)

    with httpx.Client() as client:
        for entity in DEFAULT_ENTITIES:
            entity_path = plugins_dir / entity
            if not entity_path.exists():
                log.info(f"Downloading: {entity}")
                try:
                    resp = client.get(
                        f"https://raw.githubusercontent.com/osintbuddy/entities/refs/heads/main/{entity}"
                    )
                    resp.raise_for_status()
                    entity_path.write_text(resp.text)
                except httpx.HTTPError as e:
                    log.warning(f"Failed to download {entity}: {e}")


def init_entities() -> None:
    """Initialize default entities."""
    print_banner(show_session=False)

    steps = [
        Step(
            name="init workspace",
            hint="setting up plugins directory",
            outputs=["./plugins directory ready"],
            tick_count=15,
        ),
        Step(
            name="fetch entities",
            hint="downloading from github",
            outputs=[
                f"downloading {len(DEFAULT_ENTITIES)} entities",
                "entities cached locally",
            ],
            tick_count=25,
        ),
    ]

    runner = StepRunner(speed=0.8)
    runner.run_steps(steps, header_lines=["[info]Initializing OSINTBuddy entities...[/]", ""])

    load_git_entities()
    print_success(f"Loaded {len(DEFAULT_ENTITIES)} default entities to ./plugins/")


def printjson(value) -> None:
    """Legacy JSON output (for backwards compatibility)."""
    print(json.dumps(value))


def prepare_run(plugins_path: str | None = None) -> dict:
    """Prepare registry for a run by loading plugins."""
    if plugins_path is None:
        plugins_path = os.getcwd() + '/plugins'

    Registry.labels.clear()
    Registry.plugins.clear()
    Registry.ui_labels.clear()
    if hasattr(Registry, "transforms_map"):
        Registry.transforms_map.clear()

    return load_plugins_fs(plugins_path)


async def run_transform(
    plugins_path: str,
    source: str,
    settings=None,
    cfg: str | None = None,
    structured: bool = False,
    interactive: bool = True,
) -> None:
    """Run a transform on an entity.

    Args:
        plugins_path: Path to plugins directory
        source: JSON payload with entity and transform info
        settings: Optional settings
        cfg: Optional config JSON string
        structured: If True, use structured output with delimiters
        interactive: If True, show animated progress
    """
    output_fn = emit_result if structured else printjson
    error_fn = emit_error if structured else lambda e, c, d=None: printjson({"error": e, "code": c})

    try:
        src = json.loads(source)
    except json.JSONDecodeError as e:
        error_fn(f"Invalid JSON payload: {e}", ErrorCode.INVALID_INPUT.value)
        if interactive:
            print_error("Invalid JSON payload", code="INVALID_INPUT", details={"error": str(e)})
            console.print()
            console.print("[muted]Expected format:[/]")
            console.print(Syntax(
                '{"label": "email", "transform": "extract_domain", "data": {"email": "user@example.com"}}',
                "json",
                theme="monokai",
            ))
        return

    try:
        with PluginLoadProgress() as progress:
            progress.update("Loading plugins...")
            prepare_run(plugins_path)
            entity_count = len(Registry.plugins)
            transform_count = sum(
                len(m) for buckets in Registry.transforms_map.values() for _, m in buckets
            )
            progress.complete(entity_count, transform_count)

        # Support both flat and nested payload formats
        # Flat: {"label": "...", "transform": "...", "data": {...}}
        # Nested: {"entity": {"transform": "...", "data": {"label": "...", ...}}}
        if "entity" in src:
            # Legacy nested format
            entity_payload = src.pop("entity")
            transform_label = entity_payload.pop("transform")
            source_entity_label = entity_payload.get("data", {}).get("label")
        else:
            # Flat format (preferred)
            transform_label = src.pop("transform", None)
            source_entity_label = src.pop("label", None)
            entity_payload = {"data": {"label": source_entity_label, **src.get("data", {})}}

        if not transform_label:
            error_fn("Missing transform in payload", ErrorCode.INVALID_INPUT.value)
            if interactive:
                print_error("Missing transform", code="INVALID_INPUT")
            return

        if not source_entity_label:
            error_fn("Missing entity label in payload", ErrorCode.INVALID_INPUT.value)
            if interactive:
                print_error("Missing entity label", code="INVALID_INPUT")
            return

        snake_label = to_snake_case(source_entity_label)
        plugin_cls = await Registry.get_entity(snake_label)
        if plugin_cls is None:
            error_fn(f"Plugin not found: {snake_label}", ErrorCode.PLUGIN_NOT_FOUND.value)
            if interactive:
                print_error(f"Plugin not found: {snake_label}", code="PLUGIN_NOT_FOUND")
            return

        # Find transforms for plugin
        entity_id = getattr(plugin_cls, "entity_id", None) or to_snake_case(plugin_cls.label)
        entity_version = getattr(plugin_cls, "version", "0")
        mapping = Registry.find_transforms(entity_id, entity_version)

        tkey = to_snake_case(transform_label)
        transform_fn = mapping.get(tkey)
        if transform_fn is None:
            error_fn(f"Transform not found: {transform_label}", ErrorCode.TRANSFORM_NOT_FOUND.value)
            if interactive:
                print_error(
                    f"Transform not found: {transform_label}",
                    code="TRANSFORM_NOT_FOUND",
                    details={"entity": entity_id, "version": entity_version},
                )
                console.print()
                console.print("[muted]Available transforms:[/]")
                for t_label in mapping.keys():
                    console.print(f"  [transform]- {t_label}[/]")
            return

        # Prepare entity argument
        entity_dict = entity_payload
        entity_data = entity_dict.get("data", {})
        entity_arg = TransformPayload(**{
            **{to_snake_case(k): v for k, v in entity_data.items()},
            "id": entity_dict.get("id"),
            "label": entity_data.get("label")
        })

        # Parse cfg if provided
        cfg_obj = None
        if cfg:
            try:
                cfg_obj = json.loads(cfg)
            except json.JSONDecodeError:
                cfg_obj = cfg

        # Handle dependencies
        deps = getattr(transform_fn, 'deps', None)
        if deps:
            if structured:
                emit_progress("Installing dependencies...", 20)
            if interactive:
                print_info(f"Installing dependencies: {', '.join(deps)}")
            from osintbuddy.deps import ensure_deps
            ensure_deps(tuple(deps))

        # Execute transform
        plugin_instance = plugin_cls()
        sig = inspect.signature(transform_fn)
        kwargs = {}
        if "cfg" in sig.parameters:
            kwargs["cfg"] = cfg_obj

        if structured:
            emit_progress(f"Running transform: {transform_label}", 50)

        if interactive:
            with TransformProgress(transform_label) as progress:
                progress.update(f"Executing {transform_label}...", 30)
                try:
                    result = await transform_fn(self=plugin_instance, entity=entity_arg, **kwargs)
                except TypeError:
                    result = await transform_fn(entity=entity_arg, **kwargs)
                progress.update("Normalizing results...", 80)
        else:
            try:
                result = await transform_fn(self=plugin_instance, entity=entity_arg, **kwargs)
            except TypeError:
                result = await transform_fn(entity=entity_arg, **kwargs)

        # Normalize result
        edge_label = getattr(transform_fn, "edge_label", tkey)
        normalized = normalize_result(result, default_edge_label=edge_label)

        if structured:
            emit_progress("Complete", 100)

        output_fn(normalized)

        if interactive:
            result_count = len(normalized) if isinstance(normalized, list) else 1
            print_success(f"Transform complete: {result_count} result(s)")

    except PluginError as e:
        error_fn(str(e), e.code.value if hasattr(e.code, 'value') else str(e.code))
        if interactive:
            print_error(str(e), code=str(e.code))
    except Exception as e:
        error_fn(str(e), ErrorCode.UNKNOWN.value)
        if interactive:
            print_error(str(e), code="UNKNOWN", show_traceback=True)


async def list_transforms(
    label: str,
    plugins_path: str | None = None,
    interactive: bool = True,
) -> list[dict]:
    """List transforms available for an entity."""
    prepare_run(plugins_path)

    if not label:
        printjson([])
        return []

    snake_label = to_snake_case(label)
    plugin_cls = await Registry.get_entity(snake_label)
    if plugin_cls is None:
        printjson([])
        if interactive:
            print_warning(f"Entity not found: {label}")
        return []

    entity_id = getattr(plugin_cls, "entity_id", None) or to_snake_case(plugin_cls.label)
    entity_version = getattr(plugin_cls, "version", "0")
    mapping = Registry.find_transforms(entity_id, entity_version)

    if not mapping:
        printjson([])
        if interactive:
            print_info(f"No transforms registered for {label}")
        return []

    transforms = []
    for fn in mapping.values():
        transform_info = {
            "label": getattr(fn, "label", "unknown"),
            "icon": getattr(fn, "icon", "list"),
            "edge_label": getattr(fn, "edge_label", getattr(fn, "label", "unknown")),
        }
        if deps := getattr(fn, "deps", None):
            transform_info["deps"] = deps
        if accepts := getattr(fn, "accepts", None):
            transform_info["accepts"] = accepts
        if produces := getattr(fn, "produces", None):
            transform_info["produces"] = produces
        if settings := getattr(fn, "settings", None):
            transform_info["settings"] = [
                {"name": s.name, "display_name": s.display_name, "required": s.required}
                for s in settings
            ]
        transforms.append(transform_info)

    printjson(transforms)

    if interactive:
        print_transforms_table(transforms, entity_label=label)

    return transforms


def list_plugins(plugins_path: str | None = None, interactive: bool = True) -> None:
    """List all loaded plugins."""
    plugins = prepare_run(plugins_path)
    loaded_plugins = [to_snake_case(p.label) for p in plugins.values()]
    printjson(loaded_plugins)

    if interactive:
        console.print()
        console.print(f"[info]Loaded {len(loaded_plugins)} plugins[/]")
        for plugin in loaded_plugins:
            console.print(f"  [entity]- {plugin}[/]")


def list_entities(plugins_path: str | None = None, interactive: bool = True) -> None:
    """Return a lightweight list of entities."""
    prepare_run(plugins_path)
    plugins = []

    for plugin in Registry.plugins.values():
        path = f"{sys.modules[plugin.__module__].__file__}"
        with open(path, "r") as fh:
            source = fh.read()
        last_file_edit = datetime.utcfromtimestamp(
            os.path.getmtime(path)
        ).strftime('%Y-%m-%d %H:%M:%S')
        plugins.append(dict(
            label=getattr(plugin, 'label', 'unknown'),
            author=getattr(plugin, 'author', 'Unknown author'),
            description=getattr(plugin, 'description', 'No description found...'),
            source=source,
            last_edit=last_file_edit,
        ))

    printjson(plugins)

    if interactive:
        print_entities_table(plugins)


def entities_json(plugins_path: str | None = None) -> None:
    """Dump full entity information as JSON suitable for UI display."""
    def iso8601(ts: float) -> str:
        return datetime.fromtimestamp(ts, tz=timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

    prepare_run(plugins_path)
    results = []

    for plugin_cls in Registry.plugins.values():
        module_file = f"{sys.modules[plugin_cls.__module__].__file__}"
        try:
            with open(module_file, 'r') as fh:
                source = fh.read()
        except Exception:
            source = None
        try:
            stat = os.stat(module_file)
            ctime = iso8601(stat.st_ctime)
            mtime = iso8601(stat.st_mtime)
        except Exception:
            ctime = None
            mtime = None

        label = getattr(plugin_cls, 'label', 'unknown')
        entity_id = getattr(plugin_cls, 'entity_id', None) or to_snake_case(label)
        version = getattr(plugin_cls, 'version', '0')
        author = getattr(plugin_cls, 'author', 'Unknown author')
        description = getattr(plugin_cls, 'description', 'No description found...')
        category = getattr(plugin_cls, 'category', '')
        tags = getattr(plugin_cls, 'tags', [])

        try:
            blueprint = plugin_cls.blueprint()
        except Exception:
            blueprint = None

        mapping = Registry.find_transforms(entity_id, version) or {}
        transforms = []
        for fn in mapping.values():
            transforms.append({
                'label': getattr(fn, 'label', 'unknown'),
                'icon': getattr(fn, 'icon', 'list'),
                'edge_label': getattr(fn, 'edge_label', getattr(fn, 'label', 'unknown')),
            })

        results.append({
            'id': entity_id,
            'label': label,
            'description': description,
            'author': author,
            'category': category,
            'tags': tags,
            'source': source,
            'source_path': module_file,
            'ctime': ctime,
            'mtime': mtime,
            'blueprint': blueprint,
            'transforms': transforms,
        })

    payload = {
        'entities': results,
        'favorites': [],
    }
    printjson(payload)


async def get_blueprints(
    label: str | None = None,
    plugins_path: str | None = None,
) -> dict:
    """Get entity blueprints."""
    blueprints = {}
    prepare_run(plugins_path)

    if label is None:
        plugins = [
            await Registry.get_entity(to_snake_case(lbl))
            for lbl in Registry.labels
        ]
        for entity in plugins:
            blueprint = entity.blueprint()
            blueprints[blueprint.get('label')] = blueprint
        printjson(blueprints)
        return blueprints

    plugin = await Registry.get_entity(label)
    blueprint = plugin.blueprint() if plugin else []
    printjson(blueprint)
    return blueprint


def compile_entity_cmd(
    json_path: str,
    output_path: str | None = None,
    version: str = "1.0.0",
    interactive: bool = True,
) -> None:
    """Compile a JSON entity definition to Python."""
    from osintbuddy.compiler import compile_file

    if interactive:
        print_info(f"Compiling: {json_path}")

    code = compile_file(json_path, output_path, version)

    if output_path:
        if interactive:
            print_success(f"Compiled to: {output_path}")
        else:
            print(f"Compiled to: {output_path}")
    else:
        print(code)


def compile_directory_cmd(
    json_dir: str,
    output_dir: str | None = None,
    version: str = "1.0.0",
    interactive: bool = True,
) -> None:
    """Compile all JSON entities in a directory."""
    from osintbuddy.compiler import compile_directory

    if interactive:
        print_info(f"Compiling directory: {json_dir}")

    results = compile_directory(json_dir, output_dir, version)

    if interactive:
        print_success(f"Compiled {len(results)} entities")
        for name in results:
            console.print(f"  [entity]- {name}[/]")
    else:
        print(f"Compiled {len(results)} entities")
        for name in results:
            print(f"  - {name}")


commands = {
    "init": init_entities,
    "transform": run_transform,
    "transforms": list_transforms,
    "entities": list_entities,
    "entities json": entities_json,
    "blueprints": get_blueprints,
    "plugins": list_plugins,
    "compile": compile_entity_cmd,
    "compile dir": compile_directory_cmd,
}


def main() -> None:
    """Main CLI entry point."""
    parser = ArgumentParser(
        description="OSINTBuddy Plugins CLI",
        formatter_class=RawDescriptionHelpFormatter,
        epilog="""
Examples:
  ob init                               Download the default OSINTBuddy entities
  ob entities                           List all entities
  ob transforms -L email                List transforms for email entity
  ob transform '{"entity": {...}}'      Run a transform
  ob compile entity.json -O entity.py   Compile JSON to Python
        """,
    )
    parser.add_argument('command', type=str, nargs="*", help="Command to run")
    parser.add_argument('-P', '--plugins', type=str, nargs="*", help="Plugins directory path")
    parser.add_argument('-L', '--label', type=str, nargs="*", help="Entity label")
    parser.add_argument('-C', '--config', type=str, help="Config JSON for transform")
    parser.add_argument('-O', '--output', type=str, help="Output path for compile")
    parser.add_argument('-V', '--version', type=str, default="1.0.0", help="Version for compiled entity")
    parser.add_argument('--structured', action='store_true', help="Use structured output with delimiters")
    parser.add_argument('--no-interactive', action='store_true', help="Disable interactive output")
    parser.add_argument('--quiet', '-q', action='store_true', help="Minimal output")
    parser.add_argument('-e', '--entities', action='store_true', help="List entities")
    parser.add_argument('-t', '--transforms', action='store_true', help="List transforms")

    args = parser.parse_args()

    if args.entities and args.transforms:
        print_error("Choose one of --entities or --transforms", code="INVALID_ARGUMENTS")
        sys.exit(1)

    if not args.command and not args.entities and not args.transforms:
        print_banner(show_session=False)
        parser.print_help()
        return
    payload = None
    compile_path = None
    compile_dir_path = None

    if args.entities:
        cmd_fn_key = "entities"
    elif args.transforms:
        cmd_fn_key = "transforms"
    else:
        cmd_parts = args.command or []
        if cmd_parts and cmd_parts[0] == "compile":
            if len(cmd_parts) >= 3 and cmd_parts[1] == "dir":
                compile_dir_path = cmd_parts[2]
            elif len(cmd_parts) >= 2:
                compile_path = cmd_parts[1]
        if cmd_parts and cmd_parts[0] == "transform":
            cmd_fn_key = "transform"
            if len(cmd_parts) >= 2:
                payload = cmd_parts[1]
        elif len(cmd_parts) >= 2 and ' '.join(cmd_parts[:2]) in commands:
            cmd_fn_key = ' '.join(cmd_parts[:2])
        elif cmd_parts:
            cmd_fn_key = cmd_parts[0]
        else:
            cmd_fn_key = ""

    command = commands.get(cmd_fn_key)

    interactive = not args.no_interactive and not args.quiet

    if command is None:
        print_error(f"Unknown command: {cmd_fn_key}", code="INVALID_COMMAND")
        console.print()
        console.print("[muted]Available commands:[/]")
        for cmd in commands.keys():
            console.print(f"  [info]ob {cmd}[/]")
        sys.exit(1)

    plugins_path = args.plugins[0] if args.plugins else None
    label = args.label if args.label is None else args.label[0]

    if cmd_fn_key == "transform":
        if not payload:
            print_error("Missing transform payload", code="MISSING_ARGUMENT")
            sys.exit(1)
        asyncio.run(command(
            plugins_path=plugins_path,
            source=payload,
            cfg=args.config,
            structured=args.structured,
            interactive=interactive,
        ))
    elif cmd_fn_key == "plugins":
        command(plugins_path=plugins_path, interactive=interactive)
    elif cmd_fn_key == "entities":
        command(plugins_path=plugins_path, interactive=interactive)
    elif cmd_fn_key == "entities json":
        command(plugins_path=plugins_path)
    elif cmd_fn_key == "transforms":
        if not label:
            print_error("Missing entity label (-L)", code="MISSING_ARGUMENT")
            sys.exit(1)
        asyncio.run(command(label=label, plugins_path=plugins_path, interactive=interactive))
    elif cmd_fn_key == "blueprints":
        asyncio.run(command(plugins_path=plugins_path, label=label))
    elif cmd_fn_key == "compile dir":
        if compile_dir_path:
            compile_directory_cmd(compile_dir_path, args.output, args.version, interactive)
        else:
            print_error("compile dir requires a directory path", code="MISSING_ARGUMENT")
            sys.exit(1)
    elif cmd_fn_key == "compile":
        if compile_path:
            compile_entity_cmd(compile_path, args.output, args.version, interactive)
        else:
            print_error("compile requires a JSON path", code="MISSING_ARGUMENT")
            sys.exit(1)
    else:
        command()


if __name__ == '__main__':
    main()
