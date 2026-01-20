"""IPC worker for OSINTBuddy plugins.

Provides a cross-platform IPC channel over an extra stdio pipe (fd 3).
Stdout/stderr remain free for plugin developer logs.
"""
from __future__ import annotations

import argparse
import asyncio
import inspect
import json
import os
import struct
import sys
from datetime import datetime
from typing import Any, AsyncIterator, Iterator

from osintbuddy import Registry, load_plugins_fs
from osintbuddy.plugins import TransformPayload
from osintbuddy.results import normalize_result
from osintbuddy.output import ProgressEvent, set_progress_callback
from osintbuddy.utils import to_snake_case
from osintbuddy.errors import PluginError, ErrorCode


def _default_plugins_path() -> str:
    return os.environ.get("OSINTBUDDY_PLUGINS_PATH") or os.getcwd() + "/plugins"


class IpcChannel:
    """Length-prefixed JSON messages over a binary stream."""

    def __init__(self, read_fd: int = 0, write_fd: int = 3) -> None:
        self._reader = os.fdopen(read_fd, "rb", buffering=0)
        self._writer = os.fdopen(write_fd, "wb", buffering=0)

    def send(self, message: dict[str, Any]) -> None:
        payload = json.dumps(message).encode("utf-8")
        header = struct.pack(">I", len(payload))
        self._writer.write(header + payload)
        self._writer.flush()

    def recv(self) -> dict[str, Any] | None:
        header = self._reader.read(4)
        if not header:
            return None
        (size,) = struct.unpack(">I", header)
        if size <= 0:
            return None
        body = self._reader.read(size)
        if not body:
            return None
        return json.loads(body.decode("utf-8"))


class ObWorker:
    def __init__(self) -> None:
        self.plugins_path: str | None = None

    def _reset_registry(self) -> None:
        Registry.labels.clear()
        Registry.plugins.clear()
        Registry.ui_labels.clear()
        if hasattr(Registry, "transforms_map"):
            Registry.transforms_map.clear()

    def ensure_plugins(self, plugins_path: str | None = None) -> None:
        path = plugins_path or _default_plugins_path()
        if self.plugins_path == path:
            return
        self._reset_registry()
        load_plugins_fs(path)
        self.plugins_path = path

    def list_entities(self, plugins_path: str | None = None) -> list[dict[str, Any]]:
        self.ensure_plugins(plugins_path)
        results: list[dict[str, Any]] = []
        for plugin in Registry.plugins.values():
            path = f"{sys.modules[plugin.__module__].__file__}"
            with open(path, "r") as fh:
                source = fh.read()
            last_file_edit = datetime.utcfromtimestamp(
                os.path.getmtime(path)
            ).strftime("%Y-%m-%d %H:%M:%S")
            results.append(
                dict(
                    label=getattr(plugin, "label", "unknown"),
                    author=getattr(plugin, "author", "Unknown author"),
                    description=getattr(plugin, "description", "No description found..."),
                    source=source,
                    last_edit=last_file_edit,
                )
            )
        return results

    async def list_transforms(
        self, label: str, plugins_path: str | None = None
    ) -> list[dict[str, Any]]:
        self.ensure_plugins(plugins_path)
        if not label:
            return []
        snake_label = to_snake_case(label)
        plugin_cls = await Registry.get_entity(snake_label)
        if plugin_cls is None:
            return []
        entity_id = getattr(plugin_cls, "entity_id", None) or to_snake_case(plugin_cls.label)
        entity_version = getattr(plugin_cls, "version", "0")
        mapping = Registry.find_transforms(entity_id, entity_version)
        if not mapping:
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
        return transforms

    async def get_blueprints(
        self,
        label: str | None = None,
        plugins_path: str | None = None,
    ) -> dict[str, Any]:
        self.ensure_plugins(plugins_path)
        blueprints: dict[str, Any] = {}
        if label is None:
            plugins = [
                await Registry.get_entity(to_snake_case(lbl))
                for lbl in Registry.labels
            ]
            for entity in plugins:
                blueprint = entity.blueprint()
                blueprints[blueprint.get("label")] = blueprint
            return blueprints
        plugin = await Registry.get_entity(label)
        return plugin.blueprint() if plugin else {}

    async def entities_json(self, plugins_path: str | None = None) -> dict[str, Any]:
        from datetime import datetime, timezone

        def iso8601(ts: float) -> str:
            return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        self.ensure_plugins(plugins_path)
        results = []
        for plugin_cls in Registry.plugins.values():
            module_file = f"{sys.modules[plugin_cls.__module__].__file__}"
            try:
                with open(module_file, "r") as fh:
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
            label = getattr(plugin_cls, "label", "unknown")
            entity_id = getattr(plugin_cls, "entity_id", None) or to_snake_case(label)
            version = getattr(plugin_cls, "version", "0")
            author = getattr(plugin_cls, "author", "Unknown author")
            description = getattr(plugin_cls, "description", "No description found...")
            category = getattr(plugin_cls, "category", "")
            tags = getattr(plugin_cls, "tags", [])
            try:
                blueprint = plugin_cls.blueprint()
            except Exception:
                blueprint = None
            mapping = Registry.find_transforms(entity_id, version) or {}
            transforms = []
            for fn in mapping.values():
                transforms.append(
                    {
                        "label": getattr(fn, "label", "unknown"),
                        "icon": getattr(fn, "icon", "list"),
                        "edge_label": getattr(fn, "edge_label", getattr(fn, "label", "unknown")),
                    }
                )
            results.append(
                {
                    "id": entity_id,
                    "label": label,
                    "description": description,
                    "author": author,
                    "category": category,
                    "tags": tags,
                    "source": source,
                    "source_path": module_file,
                    "ctime": ctime,
                    "mtime": mtime,
                    "blueprint": blueprint,
                    "transforms": transforms,
                }
            )
        return {"entities": results, "favorites": []}

    async def run_transform(
        self,
        source: str | dict[str, Any],
        plugins_path: str | None = None,
        cfg: str | dict[str, Any] | None = None,
    ) -> tuple[str, Any]:
        self.ensure_plugins(plugins_path)
        if isinstance(source, str):
            src = json.loads(source)
        else:
            src = source

        # Support both flat and nested payload formats
        if "entity" in src:
            entity_payload = src.pop("entity")
            transform_label = entity_payload.pop("transform")
            source_entity_label = entity_payload.get("data", {}).get("label")
        else:
            transform_label = src.pop("transform", None)
            source_entity_label = src.pop("label", None)
            entity_payload = {"data": {"label": source_entity_label, **src.get("data", {})}}

        if not transform_label:
            raise PluginError("Missing transform in payload", ErrorCode.INVALID_INPUT.value)
        if not source_entity_label:
            raise PluginError("Missing entity label in payload", ErrorCode.INVALID_INPUT.value)

        snake_label = to_snake_case(source_entity_label)
        plugin_cls = await Registry.get_entity(snake_label)
        if plugin_cls is None:
            raise PluginError(f"Plugin not found: {snake_label}", ErrorCode.PLUGIN_NOT_FOUND.value)

        entity_id = getattr(plugin_cls, "entity_id", None) or to_snake_case(plugin_cls.label)
        entity_version = getattr(plugin_cls, "version", "0")
        mapping = Registry.find_transforms(entity_id, entity_version)

        tkey = to_snake_case(transform_label)
        transform_fn = mapping.get(tkey)
        if transform_fn is None:
            raise PluginError(f"Transform not found: {transform_label}", ErrorCode.TRANSFORM_NOT_FOUND.value)

        entity_dict = entity_payload
        entity_data = entity_dict.get("data", {})
        entity_arg = TransformPayload(
            **{
                **{to_snake_case(k): v for k, v in entity_data.items()},
                "id": entity_dict.get("id"),
                "label": entity_data.get("label"),
            }
        )

        cfg_obj = None
        if cfg:
            try:
                cfg_obj = json.loads(cfg) if isinstance(cfg, str) else cfg
            except json.JSONDecodeError:
                cfg_obj = cfg

        deps = getattr(transform_fn, "deps", None)
        if deps:
            from osintbuddy.deps import ensure_deps
            ensure_deps(tuple(deps))

        plugin_instance = plugin_cls()
        sig = inspect.signature(transform_fn)
        kwargs = {}
        if "cfg" in sig.parameters:
            kwargs["cfg"] = cfg_obj

        if inspect.isasyncgenfunction(transform_fn) or inspect.isgeneratorfunction(transform_fn):
            try:
                result = transform_fn(self=plugin_instance, entity=entity_arg, **kwargs)
            except TypeError:
                result = transform_fn(entity=entity_arg, **kwargs)
        else:
            try:
                result = await transform_fn(self=plugin_instance, entity=entity_arg, **kwargs)
            except TypeError:
                result = await transform_fn(entity=entity_arg, **kwargs)

        edge_label = getattr(transform_fn, "edge_label", tkey)
        return edge_label, result


def _iter_results(value: Any) -> Iterator[Any] | AsyncIterator[Any] | None:
    if inspect.isasyncgen(value):
        return value
    if inspect.isgenerator(value):
        return value
    if hasattr(value, "__aiter__") and not isinstance(value, (list, dict, str)):
        return value  # type: ignore[return-value]
    return None


async def _send_transform_events(
    channel: IpcChannel,
    req_id: str,
    worker: ObWorker,
    source: str | dict[str, Any],
    plugins_path: str | None,
    cfg: str | dict[str, Any] | None,
) -> None:
    count = 0

    def emit(event: str, payload: Any, ok: bool = True) -> None:
        channel.send(
            {
                "id": req_id,
                "type": "transform",
                "event": event,
                "ok": ok,
                "payload": payload,
            }
        )

    def _extract_progress(value: Any) -> dict[str, Any] | None:
        if isinstance(value, ProgressEvent):
            return value.to_payload()
        if isinstance(value, dict) and value.get("_type") == "progress":
            return {k: v for k, v in value.items() if k != "_type"}
        return None

    def _emit_result_chunk(chunk: Any, edge_label: str) -> None:
        nonlocal count
        if isinstance(chunk, (list, tuple)):
            progress_payloads: list[dict[str, Any]] = []
            results: list[Any] = []
            for item in chunk:
                progress = _extract_progress(item)
                if progress is not None:
                    progress_payloads.append(progress)
                else:
                    results.append(item)
            for payload in progress_payloads:
                emit("progress", payload)
            if results:
                normalized = normalize_result(results, default_edge_label=edge_label)
                count += len(normalized)
                emit("result", normalized)
            return

        progress = _extract_progress(chunk)
        if progress is not None:
            emit("progress", progress)
            return

        normalized = normalize_result(chunk, default_edge_label=edge_label)
        count += len(normalized)
        emit("result", normalized)

    def on_progress(progress: dict[str, Any]) -> None:
        emit("progress", progress)

    set_progress_callback(on_progress)
    try:
        emit("progress", {"message": "Starting transform", "percent": 0})
        edge_label, result = await worker.run_transform(
            source=source,
            plugins_path=plugins_path,
            cfg=cfg,
        )

        stream = _iter_results(result)
        if stream is not None:
            if inspect.isasyncgen(stream) or hasattr(stream, "__aiter__"):
                async for chunk in stream:  # type: ignore[misc]
                    _emit_result_chunk(chunk, edge_label)
            else:
                for chunk in stream:  # type: ignore[assignment]
                    _emit_result_chunk(chunk, edge_label)
        else:
            _emit_result_chunk(result, edge_label)

        emit("done", {"count": count})
    finally:
        set_progress_callback(None)


async def _handle_message(channel: IpcChannel, worker: ObWorker, message: dict[str, Any]) -> None:
    req_id = message.get("id")
    msg_type = message.get("type")
    payload = message.get("payload") or {}

    def respond(event: str, payload_obj: Any, ok: bool = True) -> None:
        channel.send(
            {
                "id": req_id,
                "type": msg_type,
                "event": event,
                "ok": ok,
                "payload": payload_obj,
            }
        )

    try:
        if msg_type == "entities":
            data = worker.list_entities(payload.get("pluginsPath"))
            respond("response", data)
        elif msg_type == "transforms":
            label = payload.get("label") or ""
            data = await worker.list_transforms(label, payload.get("pluginsPath"))
            respond("response", data)
        elif msg_type == "blueprints":
            data = await worker.get_blueprints(payload.get("label"), payload.get("pluginsPath"))
            respond("response", data)
        elif msg_type == "entities_json":
            data = await worker.entities_json(payload.get("pluginsPath"))
            respond("response", data)
        elif msg_type == "transform":
            await _send_transform_events(
                channel=channel,
                req_id=req_id,
                worker=worker,
                source=payload.get("source") or payload.get("payload") or payload,
                plugins_path=payload.get("pluginsPath"),
                cfg=payload.get("cfg"),
            )
        else:
            respond("error", {"message": f"Unknown command: {msg_type}"}, ok=False)
    except PluginError as e:
        respond(
            "error",
            {"message": str(e), "code": getattr(e.code, "value", str(e.code))},
            ok=False,
        )
    except Exception as e:
        respond("error", {"message": str(e), "code": ErrorCode.UNKNOWN.value}, ok=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="OSINTBuddy IPC worker")
    parser.add_argument("-P", "--plugins", type=str, help="Plugins directory path")
    args = parser.parse_args()

    worker = ObWorker()
    if args.plugins:
        worker.ensure_plugins(args.plugins)

    channel = IpcChannel()

    while True:
        msg = channel.recv()
        if msg is None:
            break
        asyncio.run(_handle_message(channel, worker, msg))


if __name__ == "__main__":
    main()
