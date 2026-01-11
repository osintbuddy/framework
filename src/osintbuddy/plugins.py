"""OSINTBuddy Plugin System.

This module provides the core plugin infrastructure including:
- Plugin base class for entity definitions
- Transform decorator for defining transforms
- Registry for plugin and transform management
- Plugin loading from filesystem
"""
from __future__ import annotations

import os
import importlib
import importlib.util
import inspect
import sys
import glob
import json
import functools
from typing import Any, TypedDict, ClassVar, NewType, TypeAlias, TYPE_CHECKING
from packaging.version import Version, InvalidVersion
from packaging.specifiers import SpecifierSet, InvalidSpecifier
from collections import defaultdict
from collections.abc import Callable, Awaitable
from pydantic import BaseModel, ConfigDict

from osintbuddy.elements.base import BaseElement
from osintbuddy.errors import PluginError, ErrorCode
from osintbuddy.utils import to_snake_case
from osintbuddy.results import normalize_result
from osintbuddy.messages import TransformResponse

if TYPE_CHECKING:
    from osintbuddy.settings import TransformSetting
    from osintbuddy.sets import TransformSet
    from osintbuddy.types import FieldType

E = NewType('E', BaseElement)


class TransformPayload(BaseModel):
    """Payload passed to transform functions.

    Contains the entity data with snake_case field names.
    """
    model_config = ConfigDict(extra="allow", frozen=False, populate_by_name=True, arbitrary_types_allowed=True)

    def get_field(self, label: str) -> Any:
        """Get a field value by label (snake_case)."""
        return getattr(self, to_snake_case(label), None)

    def get_typed_field(self, field_type: str) -> Any:
        """Get the first field matching a field_type.

        This is used for type-based transform matching where
        transforms declare what field types they accept.
        """
        # This would need entity metadata to work properly
        # For now, return None - will be enhanced when entity
        # metadata is passed through
        return None


class TransformMeta(TypedDict, total=False):
    """Metadata about a transform function."""
    label: str
    icon: str
    edge_label: str
    entity_transform: str
    entity_version: str
    deps: list[str]
    settings: list['TransformSetting']
    transform_set: 'TransformSet'
    accepts: list[str]
    produces: list[str]


class UILabel(TypedDict):
    """UI metadata for a plugin."""
    label: str
    description: str
    author: str


class Registry(type):
    """Metaclass & central registry for plugins and transforms.

    Class Attributes:
        plugins: Map of entity_id -> Plugin subclass
        labels: List of all registered plugin labels
        ui_labels: List of UI metadata for all plugins
        transforms_map: Map of entity_id -> list of (SpecifierSet, {transform_label -> fn})
    """
    plugins: ClassVar[dict[str, type['Plugin']]] = {}
    labels: ClassVar[list[str]] = []
    ui_labels: ClassVar[list[UILabel]] = []
    transforms_map: ClassVar[dict[str, list[tuple[SpecifierSet, dict[str, Callable]]]]] = defaultdict(list)

    def __init__(cls, name: str, bases: tuple, attrs: dict):
        """Register Plugin subclasses automatically."""
        if name != 'Plugin' and issubclass(cls, Plugin):
            label = cls.label.strip()
            if cls.show_in_ui and label:
                author = cls.author
                if isinstance(author, list):
                    author = ', '.join(author)
                Registry.ui_labels.append({
                    'label': label,
                    'description': cls.description if cls.description else "Description not available.",
                    'author': author if author else "Author not provided.",
                })
            Registry.labels.append(label)
            Registry.plugins[to_snake_case(label)] = cls

    @classmethod
    async def get_entity(cls, plugin_label: str) -> type['Plugin']:
        """Get a plugin class by label.

        Accepts:
          - 'cse_result' (snake_case)
          - 'CSE Result' (display label)
          - 'cse_result@1.0.0' (versioned)
        """
        if not plugin_label:
            raise PluginError("Empty plugin_label passed to Registry.get_entity", ErrorCode.INVALID_INPUT)

        # Strip version specifier if present
        if "@" in plugin_label:
            plugin_label = plugin_label.split("@", 1)[0]

        key = to_snake_case(plugin_label)
        plugin = cls.plugins.get(key)
        if plugin:
            return plugin
        raise PluginError(f"{plugin_label} plugin not found! Make sure it's loaded...", ErrorCode.PLUGIN_NOT_FOUND)

    @classmethod
    def register_transform(
        cls,
        entity_id: str,
        version_spec: str,
        transform_label: str,
        fn: Callable
    ) -> None:
        """Register a transform for an entity.

        Args:
            entity_id: The entity this transform targets
            version_spec: Version specifier (e.g., ">=1.0,<2.0")
            transform_label: Human-readable transform name
            fn: The transform function
        """
        if not entity_id or not transform_label:
            raise PluginError("register_transform requires entity_id and transform_label", ErrorCode.INVALID_INPUT)

        try:
            spec = SpecifierSet(version_spec)
        except InvalidSpecifier:
            try:
                Version(version_spec)
                spec = SpecifierSet(f"=={version_spec}")
            except InvalidVersion:
                raise PluginError(
                    f"Invalid version specifier '{version_spec}' for transform {transform_label}",
                    ErrorCode.INVALID_VERSION
                )

        # Collision detection
        for existing_spec, mapping in cls.transforms_map.get(entity_id, []):
            if transform_label in mapping:
                try:
                    existing_exact = next((s for s in str(existing_spec).split(',') if s.strip().startswith('==')), None)
                    new_exact = next((s for s in str(spec).split(',') if s.strip().startswith('==')), None)
                    if existing_exact and new_exact:
                        if existing_exact == new_exact:
                            raise PluginError(
                                f"Transform collision: '{transform_label}' already registered for {entity_id} spec {existing_spec}",
                                ErrorCode.TRANSFORM_COLLISION
                            )
                    else:
                        raise PluginError(
                            f"Transform collision: '{transform_label}' already registered for {entity_id} with overlapping version spec '{existing_spec}'",
                            ErrorCode.TRANSFORM_COLLISION
                        )
                except PluginError:
                    raise

        # Try to merge with existing identical spec bucket
        for i, (existing_spec, mapping) in enumerate(cls.transforms_map.get(entity_id, [])):
            if str(existing_spec) == str(spec):
                if transform_label in mapping:
                    raise PluginError(
                        f"Transform '{transform_label}' already registered for {entity_id}@{version_spec}",
                        ErrorCode.TRANSFORM_COLLISION
                    )
                mapping[transform_label] = fn
                return

        # Append new bucket
        cls.transforms_map[entity_id].append((spec, {transform_label: fn}))

    @classmethod
    def find_transforms(cls, entity_id: str, entity_version: str) -> dict[str, Callable]:
        """Find all transforms matching an entity version.

        Args:
            entity_id: The entity identifier
            entity_version: The entity version string

        Returns:
            Dict mapping transform_label -> transform function
        """
        if entity_id not in cls.transforms_map:
            return {}
        try:
            ver = Version(entity_version)
        except InvalidVersion:
            return {}

        result: dict[str, Callable] = {}
        for specset, mapping in cls.transforms_map.get(entity_id, []):
            if ver in specset:
                result.update(mapping)
        return result

    @classmethod
    def get_transforms_by_set(cls, set_name: str) -> list[Callable]:
        """Get all transforms belonging to a transform set.

        Args:
            set_name: Name of the transform set

        Returns:
            List of transform functions in the set
        """
        result = []
        for entity_id, buckets in cls.transforms_map.items():
            for specset, mapping in buckets:
                for label, fn in mapping.items():
                    transform_set = getattr(fn, 'transform_set', None)
                    if transform_set and transform_set.name == set_name:
                        result.append(fn)
        return result


ElementsLayout: TypeAlias = list[BaseElement | list[BaseElement]]


class Plugin(object, metaclass=Registry):
    """Base class for OSINTBuddy entity plugins.

    Subclass this to define new entity types. Entities define:
    - Metadata (label, description, icon, color)
    - Elements (form fields for user input)
    - Transforms (operations that can be performed on the entity)

    Example:
        class EmailEntity(Plugin):
            version = "1.0.0"
            label = "Email Address"
            description = "An email address entity"
            icon = "mail"
            color = "#3B82F6"
            category = "Identity"

            elements = [
                TextInput(label="Email", field_type=FieldType.EMAIL),
            ]
    """
    # Required
    version: str

    # Identity (optional override for entity_id, defaults to snake_case label)
    entity_id: str | None = None

    # Metadata
    label: str = ''
    description: str = ''
    author: str | list[str] = 'Unknown'
    icon: str = 'atom-2'
    color: str = '#145070'

    # Organization
    category: str = ''
    tags: list[str] = []

    # UI visibility
    show_in_ui: bool = True
    show_option: bool = True  # Deprecated, use show_in_ui

    # Plugin-level dependencies (installed on plugin load)
    deps: list[str] = []

    # Elements definition
    elements: ElementsLayout = []

    def __init__(self):
        """Initialize plugin instance and discover transforms."""
        transforms = self.__class__.__dict__.values()
        self.transforms: dict[str, Callable] = {}
        self.transform_labels: list[dict[str, str]] = []

        for func in transforms:
            if hasattr(func, 'label'):
                key = to_snake_case(func.label)
                self.transforms[key] = func

                raw_edge = getattr(func, 'edge_label', None)
                edge_label = raw_edge if raw_edge and raw_edge.strip() else func.label

                self.transform_labels.append({
                    'label': func.label,
                    'icon': getattr(func, 'icon', 'atom-2'),
                    'edge_label': edge_label,
                })

    def __call__(self):
        return self.create()

    @staticmethod
    def __map_element_labels(element: dict, **kwargs) -> dict:
        """Map element labels to provided values."""
        label = to_snake_case(element['label'])
        for element_key in kwargs.keys():
            if element_key == label:
                if isinstance(kwargs[label], str):
                    element['value'] = kwargs[label]
                elif isinstance(kwargs[label], dict):
                    for t in kwargs[label]:
                        element[t] = kwargs[label][t]
        return element

    @classmethod
    def blueprint(cls, **kwargs) -> dict[str, Any]:
        """Generate a blueprint dict for this entity.

        Args:
            **kwargs: Values to populate into elements by label

        Returns:
            Dict with label, color, icon, elements, and metadata
        """
        metaentity: dict[str, Any] = {
            'label': cls.label,
            'color': cls.color,
            'icon': cls.icon,
            'elements': [],
        }

        # Add optional metadata
        if cls.category:
            metaentity['category'] = cls.category
        if cls.tags:
            metaentity['tags'] = cls.tags

        for element in cls.elements:
            if isinstance(element, list):
                metaentity['elements'].append([
                    cls.__map_element_labels(elm.to_dict(), **kwargs)
                    for elm in element
                ])
            else:
                element_row = cls.__map_element_labels(element.to_dict(), **kwargs)
                metaentity['elements'].append(element_row)

        return metaentity

    @classmethod
    def create(cls, **kwargs) -> dict[str, Any]:
        """Create an entity instance dict."""
        kwargs['label'] = cls.label
        return kwargs

    async def run(self, transform_type: str, entity: dict | str, cfg: dict | None = None) -> Any:
        """Execute a transform on an entity.

        Args:
            transform_type: The transform label (snake_case or display)
            entity: Entity data as dict or JSON string
            cfg: Optional configuration dict

        Returns:
            Normalized list of result entities
        """
        transform_type = to_snake_case(transform_type)
        if isinstance(entity, str):
            entity = json.loads(entity)

        entity_id = entity.pop('id')
        data = entity.pop("data")
        entity_label = data.pop("label")
        entity = {
            to_snake_case(k): v for k, v in data.items()
        }
        entity["id"] = entity_id
        entity["label"] = entity_label

        # Resolve transforms for this entity version
        entity_key = self.entity_id or to_snake_case(self.label)
        transforms_for_version = Registry.find_transforms(entity_key, getattr(self, 'version', '0'))
        if transform_type not in transforms_for_version:
            raise PluginError(
                f"Transform '{transform_type}' not found for {entity_key}@{getattr(self, 'version', '0')}",
                ErrorCode.TRANSFORM_NOT_FOUND
            )

        try:
            if self.transforms and self.transforms.get(transform_type):
                transform_fn = transforms_for_version[transform_type]

                # Handle dependencies
                deps = getattr(transform_fn, 'deps', None)
                if deps:
                    from osintbuddy.deps import ensure_deps
                    ensure_deps(tuple(deps))

                # Handle settings
                settings = getattr(transform_fn, 'settings', None)
                if settings:
                    from osintbuddy.settings import get_settings_manager
                    manager = get_settings_manager()
                    cfg = manager.build_config(
                        transform_fn.label,
                        settings,
                        cfg
                    )
                    errors = manager.validate_config(settings, cfg or {})
                    if errors:
                        raise PluginError(f"Config validation failed: {errors}", ErrorCode.CONFIG_INVALID)

                sig = inspect.signature(transform_fn)
                if 'cfg' in sig.parameters:
                    result = await transform_fn(
                        entity=TransformPayload(**entity),
                        cfg=cfg
                    )
                else:
                    result = await transform_fn(
                        entity=TransformPayload(**entity),
                    )

                edge_label = getattr(transform_fn, 'edge_label', transform_type)

                # Handle TransformResponse with messages
                if isinstance(result, TransformResponse):
                    normalized = normalize_result(result.entities, default_edge_label=edge_label)
                    return {
                        "entities": normalized,
                        "messages": [m.to_dict() for m in result.messages],
                        "metadata": result.metadata
                    }

                return normalize_result(result, default_edge_label=edge_label)
        except PluginError:
            raise
        except Exception as e:
            raise PluginError(f"Transform failed: {e}", ErrorCode.TRANSFORM_FAILED)

    @staticmethod
    def _map_element(transform_map: dict, element: dict):
        """Map element data for transform input."""
        label = to_snake_case(element.pop('label', None))
        transform_map[label] = {}
        element_type = element.pop('type', None)
        element.pop('icon', None)
        element.pop('placeholder', None)
        element.pop('style', None)
        element.pop('options', None)
        for k, v in element.items():
            if (isinstance(v, str) and len(element.values()) == 1) or element_type == 'dropdown':
                transform_map[label] = v
            else:
                transform_map[label][k] = v

    @classmethod
    def get_field_types(cls) -> dict[str, str]:
        """Get a mapping of element labels to their field types.

        Returns:
            Dict mapping snake_case labels to field_type values
        """
        field_types = {}
        for element in cls.elements:
            if isinstance(element, list):
                for elm in element:
                    elm_dict = elm.to_dict()
                    if 'field_type' in elm_dict:
                        field_types[to_snake_case(elm_dict['label'])] = elm_dict['field_type']
            else:
                elm_dict = element.to_dict()
                if 'field_type' in elm_dict:
                    field_types[to_snake_case(elm_dict['label'])] = elm_dict['field_type']
        return field_types


def load_plugins_fs(plugins_path: str = "plugins", package: str = "osintbuddy.transforms") -> dict[str, type[Plugin]]:
    """Load plugins from filesystem.

    Loads:
    - Entity plugins from {plugins_path}/entities/*.py
    - Transform scripts from {plugins_path}/transforms/*.py

    Args:
        plugins_path: Base path to plugins directory
        package: Package name for transform modules

    Returns:
        Dict of loaded plugins (entity_id -> Plugin class)
    """
    entity_files = glob.glob(f'{plugins_path}/entities/*.py')
    transform_scripts = glob.glob(f'{plugins_path}/transforms/*.py')

    # Load entity plugins
    for entity_path in entity_files:
        mod_name = entity_path.replace('.py', '').replace('plugins/', '').replace('entities/', '')
        spec = importlib.util.spec_from_file_location(mod_name, entity_path)
        if spec is not None and spec.loader is not None:
            module = importlib.util.module_from_spec(spec)
            sys.modules[mod_name] = module
            spec.loader.exec_module(module)

            # Install plugin-level deps and register transforms
            for name in dir(module):
                obj = getattr(module, name)
                if isinstance(obj, type) and issubclass(obj, Plugin) and obj is not Plugin:
                    if hasattr(obj, 'deps') and obj.deps:
                        from osintbuddy.deps import ensure_deps
                        ensure_deps(tuple(obj.deps))
                # Also register transforms defined in entity files
                elif callable(obj) and hasattr(obj, 'entity_transform') and hasattr(obj, 'entity_version'):
                    tlabel = to_snake_case(getattr(obj, 'label'))
                    entity_id = getattr(obj, 'entity_transform')
                    version_spec = getattr(obj, 'entity_version')
                    Registry.register_transform(entity_id, version_spec, tlabel, obj)

    # Load transform scripts
    for script in transform_scripts:
        base = os.path.splitext(os.path.basename(script))[0]
        script_mod_name = f"plugins.transforms.{base}"
        spec = importlib.util.spec_from_file_location(script_mod_name, script)
        if spec is not None and spec.loader is not None:
            module = importlib.util.module_from_spec(spec)
            module.__package__ = "plugins.transforms"
            sys.modules[script_mod_name] = module
            spec.loader.exec_module(module)

            # Register transforms found in the module
            for name in dir(module):
                obj = getattr(module, name)
                if callable(obj) and hasattr(obj, 'entity_transform') and hasattr(obj, 'entity_version'):
                    tlabel = to_snake_case(getattr(obj, 'label'))
                    entity_id = getattr(obj, 'entity_transform')
                    version_spec = getattr(obj, 'entity_version')
                    Registry.register_transform(entity_id, version_spec, tlabel, obj)

    return Registry.plugins


def transform(
    target: str,
    label: str,
    icon: str = 'list',
    edge_label: str = '',
    deps: list[str] | None = None,
    settings: list['TransformSetting'] | None = None,
    transform_set: 'TransformSet' | None = None,
    accepts: list[str] | None = None,
    produces: list[str] | None = None,
) -> Callable[[Callable], Callable]:
    """Decorator to define a transform for an entity.

    Args:
        target: Target entity in format "entity_id@version_spec"
        label: Human-readable transform name
        icon: Icon identifier for UI
        edge_label: Label for edges created by this transform
        deps: List of pip dependencies to install before running
        settings: List of TransformSetting declarations
        transform_set: TransformSet this belongs to
        accepts: List of field types this transform accepts (for type-based matching)
        produces: List of field types this transform produces

    Returns:
        Decorated transform function

    Example:
        @transform(
            target="website@>=1.0.0",
            label="Screenshot",
            icon="camera",
            deps=["playwright"],
            settings=[TransformSetting(name="api_key", required=True)]
        )
        async def screenshot(entity: TransformPayload, cfg: dict):
            ...
    """
    target_parts = target.split("@")
    if len(target_parts) != 2:
        raise PluginError(
            "Transform `target` must be `entity_id@version_spec`! e.g. `cse_result@1.0.0`",
            ErrorCode.INVALID_INPUT
        )
    entity_transform = target_parts[0]
    entity_version = target_parts[1]

    def decorator_transform(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(entity: Any, **kwargs: Any) -> Any:
            # Install dependencies if specified
            if deps:
                from osintbuddy.deps import ensure_deps
                ensure_deps(tuple(deps))
            return await func(entity=entity, **kwargs)

        # Attach metadata to wrapper
        wrapper.label = label
        wrapper.icon = icon
        wrapper.edge_label = edge_label
        wrapper.entity_transform = entity_transform
        wrapper.entity_version = entity_version
        wrapper.deps = deps or []
        wrapper.settings = settings or []
        wrapper.transform_set = transform_set
        wrapper.accepts = accepts or []
        wrapper.produces = produces or []

        return wrapper

    return decorator_transform
