import os, importlib, inspect, sys, glob, json, types
import importlib.util
from typing import Any, TypedDict, ClassVar, NewType, TypeAlias, Type, Protocol, Callable
from packaging.version import Version, InvalidVersion
from packaging.specifiers import SpecifierSet, InvalidSpecifier

from collections import defaultdict
from collections.abc import Callable, Awaitable
from pydantic import BaseModel, ConfigDict

from osintbuddy.elements.base import BaseElement
from osintbuddy.errors import PluginError
from osintbuddy.utils import to_snake_case

E = NewType('E', BaseElement)

class TransformPayload(BaseModel):
    model_config = ConfigDict(extra="allow", frozen=False, populate_by_name=True, arbitrary_types_allowed=True)


class TransformFunction(Protocol):
    label: str
    icon: str
    edge_label: str
    entity_transform: Awaitable[Any]
    entity_version: Version
    
    def __call__(self, entity: TransformPayload, **kwargs: Any) -> Awaitable[Any]: ...


def plugin_results_middleman(f):
    def return_result(r):
        return r
    def yield_result(r):
        for i in r:
            yield i
    def decorator(*a, **kwa):
        if inspect.isgeneratorfunction(f):
            return yield_result(f(*a, **kwa))
        else:
            return return_result(f(*a, **kwa))
    return decorator


class UILabel(TypedDict):
    label: str
    description: str
    author: str


class Registry(type):
    """
    Metaclass & central registry.

    - Registry.plugins: plugin class map (entity_id -> Plugin subclass)
    - Registry.transforms_map: entity_id -> list of (SpecifierSet, { transform_label -> fn })
      We keep multiple buckets (different specifier sets) for a single entity_id.
    """
    plugins: ClassVar[dict[str, type['Plugin']]] = {}
    labels: ClassVar[list[str]] = []
    ui_labels: ClassVar[list[UILabel]] = []
    transforms_map: ClassVar[dict[str, list[tuple[SpecifierSet, dict[str, TransformFunction]]]]] = defaultdict(list)

    def __init__(cls, name, bases, attrs):
        # Register Plugin subclasses (unchanged behavior)
        if name != 'Plugin' and issubclass(cls, Plugin):
            label = cls.label.strip()
            if cls.show_option and label:
                if isinstance(cls.author, list):
                    cls.author = ', '.join(cls.author)
                Registry.ui_labels.append({
                    'label': label,
                    'description': cls.description if cls.description is not None else "Description not available.",
                    'author': cls.author if cls.author is not None else "Author not provided.",
                })
            Registry.labels.append(label)
            Registry.plugins[to_snake_case(label)] = cls

    @classmethod
    async def get_entity(cls, plugin_label: str) -> Any:
        """
        Accepts:
          - 'cse_result'
          - 'CSE Result'
          - 'cse_result@1.0.0'
          - 'CSE Result@>=1.0'
        and normalizes to the registry key (snake_case label).
        """
        if not plugin_label:
            raise PluginError("Empty plugin_label passed to Registry.get_entity")

        # If caller passed "<label>@<version_spec>", strip the @version part.
        if "@" in plugin_label:
            plugin_label = plugin_label.split("@", 1)[0]

        # Normalize to snake_case since Registry.plugins keys use to_snake_case(plugin.label)
        key = to_snake_case(plugin_label)
        plugin = cls.plugins.get(key)
        if plugin:
            return plugin
        raise PluginError(f"{plugin_label} plugin not found! Make sure it's loaded...")

    # -------------------------
    # Transform registration API
    # -------------------------
    @classmethod
    def register_transform(cls, entity_id: str, version_spec: str, transform_label: str, fn: TransformFunction) -> None:
        """
        Register a transform for an entity_id under a version specifier.
        Strict collision policy:
          - If an existing bucket has an overlapping SpecifierSet and already defines transform_label -> raise PluginError.
        """
        # normalize inputs
        if not entity_id or not transform_label:
            raise PluginError("register_transform requires entity_id and transform_label")

        try:
            spec = SpecifierSet(version_spec)
        except InvalidSpecifier:
            # allow a single-version like "1.2.3" as equivalent to "==1.2.3"
            try:
                Version(version_spec)
                spec = SpecifierSet(f"=={version_spec}")
            except InvalidVersion:
                raise PluginError(f"Invalid version specifier '{version_spec}' for transform {transform_label}")

        # collision detection: if any existing SpecifierSet intersects this one and already contains the label -> error
        for existing_spec, mapping in cls.transforms_map.get(entity_id, []):
            # intersection test: check if there exists any candidate version (heuristic)
            # We'll test by checking if there exists a version that satisfies both sets by testing candidate points:
            # - test boundaries present in spec strings (simple heuristic), else conservative: assume overlap and check label
            # Simpler and deterministic: if mapping already has label and spec intersection is non-empty by sampling
            if transform_label in mapping:
                # rough overlap check: test a few candidate versions from existing_spec & spec
                # We'll attempt to find any version string that satisfies both: test a set of candidates derived from specs
                # For strictness, if we cannot safely prove disjointness, treat as overlap.
                # Practical: if either spec contains '==' the check is straightforward.
                try:
                    # if either is an exact spec (==x), check direct membership
                    existing_exact = next((s for s in str(existing_spec).split(',') if s.strip().startswith('==')), None)
                    new_exact = next((s for s in str(spec).split(',') if s.strip().startswith('==')), None)
                    if existing_exact and new_exact:
                        # both exact -> check equality
                        if existing_exact == new_exact:
                            raise PluginError(f"Transform collision: '{transform_label}' already registered for {entity_id} spec {existing_spec}")
                    else:
                        # Conservative: assume overlap (strict policy). If label exists in mapping, error.
                        raise PluginError(f"Transform collision: '{transform_label}' already registered for {entity_id} with overlapping version spec '{existing_spec}'")
                except PluginError:
                    raise
        # no collisions — either bucket exists without the label or there were no intersecting label entries
        # try to merge with an existing identical spec bucket
        for i, (existing_spec, mapping) in enumerate(cls.transforms_map.get(entity_id, [])):
            if str(existing_spec) == str(spec):
                if transform_label in mapping:
                    # duplicate exact registration
                    raise PluginError(f"Transform '{transform_label}' already registered for {entity_id}@{version_spec}")
                mapping[transform_label] = fn
                return

        # otherwise append new bucket
        cls.transforms_map[entity_id].append((spec, {transform_label: fn}))

    @classmethod
    def find_transforms(cls, entity_id: str, entity_version: str) -> dict[str, TransformFunction]:
        """
        Return a mapping of transform_label -> fn for transforms whose specifier matches entity_version.
        Merge strategy: later registrations override earlier registrations for same label (but we prevented overlapping collisions).
        """
        if entity_id not in cls.transforms_map:
            return {}
        try:
            ver = Version(entity_version)
        except InvalidVersion:
            # if version isn't parseable, treat as not found
            return {}

        result: dict[str, TransformFunction] = {}
        for specset, mapping in cls.transforms_map.get(entity_id, []):
            if ver in specset:
                result.update(mapping)
        return result

ElementsLayout: TypeAlias = list[BaseElement | list[BaseElement]]

class Plugin(object, metaclass=Registry):
    """
    OBPlugin is the base class for all plugin classes in this application.
    It provides the required structure and methods for a plugin.
    """
    version: str
    # If None, the entity_id is the label as snakecase
    entity_id: str | None = None

    label: str = ''
    description: str = ''
    author: str = 'Unknown'

    icon: str = 'atom-2'
    color: str = '#145070'
    show_option = True

    elements: ElementsLayout = list()

    def __init__(self):
        transforms = self.__class__.__dict__.values()
        self.transforms: dict[str, TransformFunction] = {}
        self.transform_labels: list[dict[str, str]] = []

        for func in transforms:
            if hasattr(func, 'label'):
                key = to_snake_case(func.label)   # internal lookup key
                self.transforms[key] = func

                raw_edge = getattr(func, 'edge_label', None)
                edge_label = raw_edge if raw_edge and raw_edge.strip() else func.label

                self.transform_labels.append({
                    'label': func.label,                 # human-readable
                    'icon': getattr(func, 'icon', 'atom-2'),
                    'edge_label': edge_label,            # always non-empty
                })

    def __call__(self):
        return self.create()

    @staticmethod
    def __map_element_labels(element: dict, **kwargs):
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
    def blueprint(cls, **kwargs):
        """
  
        """
        metaentity = defaultdict(None)
        metaentity['label'] = cls.label
        metaentity['color'] = cls.color
        metaentity['icon'] = cls.icon
        metaentity['elements'] = []
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
    def create(cls, **kwargs):
        """
       
        """
        kwargs['label'] = cls.label
        return kwargs

    async def run(self, transform_type: str, entity, cfg: dict | None = None) -> Any:
        """ 
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

        # resolve available transforms for this entity_id/version
        entity_key = self.entity_id or to_snake_case(self.label)
        transforms_for_version = Registry.find_transforms(entity_key, getattr(self, 'version', '0'))
        if transform_type not in transforms_for_version:
            raise PluginError(f"Transform '{transform_type}' not found for {entity_key}@{getattr(self, 'version', '0')}")

        try:   
            if self.transforms and self.transforms[transform_type]:

                transform_fn = transforms_for_version[transform_type]
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
                # Pull the declared edge label from the transform function metadata
                edge_label = getattr(transform_fn, 'edge_label', transform_type)

                # Normalize result to a list of dicts and inject edge_label as a string
                if not isinstance(result, list):
                    if isinstance(result, dict):
                        result['edge_label'] = edge_label
                    return [result]
                for n in result:
                    if isinstance(n, dict):
                        n['edge_label'] = edge_label
                return result
        except (PluginError) as e:
            raise e

    @staticmethod
    def _map_element(transform_map: dict, element: dict):
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


def load_plugins_fs(plugins_path: str = "plugins", package="osintbuddy.transforms") -> dict[str, type[Plugin]]:
    """
    Loads plugins from the filesystem ./{plugins_path}/*.py directory

    """
    entity_files = glob.glob(f'{plugins_path}/entities/*.py')
    transform_scripts = glob.glob(f'{plugins_path}/transforms/*.py')
    # print("TRANSFORM FILES: ", transform_scripts)
    for entity_path in entity_files:
        mod_name = entity_path.replace('.py', '').replace('plugins/', '').replace('entities/', '')
        spec = importlib.util.spec_from_file_location(mod_name, f"{entity_path}")
        if spec is not None and spec.loader is not None:
            module = importlib.util.module_from_spec(spec)
            sys.modules[mod_name] = module
            spec.loader.exec_module(module)
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
                    # transform label stored as attribute by decorator
                    tlabel = to_snake_case(getattr(obj, 'label'))
                    entity_id = getattr(obj, 'entity_transform')
                    version_spec = getattr(obj, 'entity_version')
                    Registry.register_transform(entity_id, version_spec, tlabel, obj)
    return Registry.plugins

def transform(target: str, label: str, icon: str = 'list', edge_label: str = '') -> Callable[[Callable], TransformFunction]:
    """
    A decorator add transforms for osintbuddy entities.

    """

    target_entity = target.split("@")
    if len(target_entity) != 2:
        raise Exception("Transform `target` must be `entity_id@version_spec`! e.g. `cse_result@1.0.0`")
    entity_transform = target_entity[0]
    entity_version = target_entity[1] # allow things like ">=1.0,<2.0" or "==1.0.0"

    def decorator_transform(func: Callable) -> TransformFunction:
        async def wrapper(entity: Any, **kwargs: Any) -> Any:
            return await func(entity=entity, **kwargs)
        
        # Use setattr to avoid type checker issues with dynamic attribute assignment
        setattr(wrapper, 'label', label)
        setattr(wrapper, 'icon', icon)
        setattr(wrapper, 'edge_label', edge_label)
        setattr(wrapper, 'entity_transform', entity_transform)
        setattr(wrapper, 'entity_version', entity_version)
        return wrapper  # type: ignore[return-value]
    return decorator_transform
