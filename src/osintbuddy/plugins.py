import os, importlib, inspect, sys, glob, json, types
import importlib.util
from typing import Any, TypedDict, ClassVar, NewType, TypeAlias, Type, Protocol

from collections import defaultdict
from collections.abc import Callable, Awaitable
from pydantic import BaseModel, ConfigDict
from transfunctions import (
    transfunction,
    sync_context,
    async_context,
    generator_context,
)
from osintbuddy.elements.base import BaseElement
from osintbuddy.errors import PluginError
from osintbuddy.utils import to_snake_case

E = NewType('E', BaseElement)

class Vertex(BaseModel):
    model_config = ConfigDict(extra="allow", frozen=False, populate_by_name=True, arbitrary_types_allowed=True)


class TransformFunction(Protocol):
    label: str
    icon: str
    edge_label: str
    def __call__(self, entity: Vertex, **kwargs: Any) -> Awaitable[Any]: ...


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
    plugins: ClassVar[dict[str, type['Plugin']]] = {}
    labels: ClassVar[list[str]] = []
    ui_labels: ClassVar[list[UILabel]] = []

    def __init__(cls, name, bases, attrs):
        """
        Initializes the Registry metaclass by adding the plugin class
        and its label if it is a valid plugin.
        """
        if name != 'Plugin' and issubclass(cls, Plugin):
            label = cls.label.strip()

            if cls.is_available and label:
                if isinstance(cls.author, list):
                    cls.author = ', '.join(cls.author)
                Registry.ui_labels.append({
                    'label': label,
                    'description': cls.description if cls.description != None else "Description not available.",
                    'author': cls.author if cls.author != None else "Author not provided.",
                })
            Registry.labels.append(label)
            Registry.plugins[to_snake_case(label)] = cls

    @classmethod
    async def get_plugin(cls, plugin_label: str) -> Any:
        """
        Returns the corresponding plugin class for a given plugin_label or
        'None' if not found.

        :param plugin_label: The label of the plugin to be returned.
        :return: The plugin class or None if not found.
        """
        plugin =  cls.plugins.get(plugin_label)
        if plugin:
            return plugin
        raise PluginError(f"{plugin_label} plugin not found! Make sure it's loaded...")


    @classmethod
    def get_plug(cls, plugin_label: str) -> Any:
        """
        Returns the corresponding plugin class for a given plugin_label or
        'None' if not found.

        :param plugin_label: The label of the plugin to be returned.
        :return: The plugin class or None if not found.
        """
        plugin =  cls.plugins.get(plugin_label)
        if plugin:
            return plugin
        raise PluginError(f"{plugin_label} plugin not found! Make sure it's loaded...")


ElementsLayout: TypeAlias = list[BaseElement | list[BaseElement]]

class Plugin(object, metaclass=Registry):
    """
    OBPlugin is the base class for all plugin classes in this application.
    It provides the required structure and methods for a plugin.
    """
    elements: ElementsLayout = list()
    color: str = '#145070'
    label: str = ''
    icon: str = 'atom-2'
    is_available = True

    author = ''
    description = ''

    def __init__(self):
        transforms = self.__class__.__dict__.values()
        self.transforms: dict[str, TransformFunction] = {
            to_snake_case(func.label): func for func in transforms if hasattr(func, 'label')
        }
        self.transform_labels = [
            {
                'label': func.label,
                'icon': func.icon if hasattr(func, 'icon') else 'atom-2',
            } for func in transforms
            if hasattr(func, 'label')
        ]

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
        Generate and return a dictionary representing the plugins ui entity.
        Includes label, name, color, icon, and a list of all elements
        for the entity/plugin.
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
        Generate and return a dictionary representing the plugins ui entity.
        Includes label, name, color, icon, and a list of all elements
        for the entity/plugin.
        """
        kwargs['label'] = cls.label
        return kwargs

    # TODO: rename use to cfg
    async def run_transform(self, transform_type: str, entity, cfg: dict | None = None) -> Any:
        """ Return output from a function accepting node data.
            The function will be called with a single argument, the node data
            from when a node context menu action is taken - and should return
            a list of Nodes.
            None if the plugin doesn't provide a transform
            for the transform_type.
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

        if self.transforms and self.transforms[transform_type]:
            try:
                transform_fn = self.transforms[transform_type]
                sig = inspect.signature(transform_fn)
                if 'cfg' in sig.parameters:
                    result = await transform_fn(
                        self=self,
                        entity=Vertex(**entity),
                        cfg=cfg
                    )
                else:
                    result = await transform_fn(
                        self=self,
                        entity=Vertex(**entity),
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
            except (Exception, PluginError) as e:
                raise e
                # exc_type, exc_obj, exc_tb = sys.exc_info()
                # fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                # raise OBPluginError(f"Unhandled plugin error! {exc_type}\nPlease see {fname} on line no. {exc_tb.tb_lineno}\n{e}")
        return None

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


# https://stackoverflow.com/a/7548190
def load_plugin_str(
    mod_name: str,
    plugin_code: str,
):
    """
    Load plugins from a string of code

    :param module_name: The desired module name of the plugin.
    :param plugin_code: The code of the plugin.
    :return:
    """
    # spec = importlib.util.spec_from_file_location('my_module', '/paht/to/my_module')
    # module = importlib.util.module_from_spec(spec)
    # spec.loader.exec_module(module)
    new_mod = types.ModuleType(mod_name)
    exec(plugin_code, new_mod.__dict__)
    return Registry.plugins


def load_plugins_fs(plugins_path: str = "plugins"):
    """
    Loads plugins from the filesystem ./plugins/*.py directory

    :return: list of plugins sourced from the filesystem
    """
    entities = glob.glob(f'{plugins_path}/*.py')
    for entity in entities:
        mod_name = entity.replace('.py', '').replace('plugins/', '')
        spec = importlib.util.spec_from_file_location(mod_name, f"{entity}")
        if spec is not None and spec.loader is not None:
            module = importlib.util.module_from_spec(spec)
            sys.modules[mod_name] = module
            spec.loader.exec_module(module)
    return Registry.plugins


def transform(label: str, icon: str = 'list', edge_label: str = 'transformed_to') -> Callable[[Callable], TransformFunction]:
    """
    A decorator add transforms to an osintbuddy plugin.

    Usage:
    @transform(label=<label_text>, icon=<tabler_react_icon_name>)
    def transform_to_ip(self, node, **kwargs):
        # Method implementation

    :param label: str, A string representing the label for the transform
        method, which can be utilized for displaying in the context menu.
    :param icon: str, Optional icon name, representing the icon associated
        displayed by the transform label. Default is "list".
    :return: A decorator for the plugin transform method.
    """
    def decorator_transform(func: Callable, edge_label: str = edge_label) -> TransformFunction:
        async def wrapper(self: Any, entity: Any, **kwargs: Any) -> Any:
            print(entity, kwargs)
            return await func(self=self, entity=entity, **kwargs)
        
        # Use setattr to avoid type checker issues with dynamic attribute assignment
        setattr(wrapper, 'label', label)
        setattr(wrapper, 'icon', icon)
        setattr(wrapper, 'edge_label', edge_label)
        
        return wrapper  # type: ignore[return-value]
    return decorator_transform
