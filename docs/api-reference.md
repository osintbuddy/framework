# API Reference

Complete reference for the OSINTBuddy plugin framework API.

## Core Classes

### Plugin

Base class for all entity definitions.

```python
from osintbuddy import Plugin

class MyEntity(Plugin):
    version: str                    # Required: semantic version
    label: str                      # Required: display name
    elements: list                  # Required: form elements

    entity_id: str | None = None    # Override auto-generated ID
    description: str = ""           # Long description
    author: str | list[str] = ""    # Author(s)
    icon: str = "atom-2"            # Icon identifier
    color: str = "#145070"          # Hex color
    category: str = ""              # UI grouping
    tags: list[str] = []            # Searchable tags
    show_in_ui: bool = True         # Show in entity picker
    deps: list[str] = []            # Python dependencies
```

#### Methods

##### blueprint(\*\*kwargs) -> dict

Generate entity definition with optional field values.

```python
data = MyEntity.blueprint(field1="value1", field2="value2")
```

##### create(\*\*kwargs) -> dict

Create a simpler entity instance dict.

```python
data = MyEntity.create(field1="value1")
```

##### run(transform_type, entity, cfg=None) -> Any

Execute a transform on an entity.

```python
result = await MyEntity.run("transform_name", entity_data, cfg={})
```

##### get_field_types() -> dict[str, FieldType]

Get mapping of element labels to field types.

```python
types = MyEntity.get_field_types()
# {"email": FieldType.EMAIL, "domain": FieldType.DOMAIN}
```

---

### Registry

Metaclass that manages plugin registration.

```python
from osintbuddy import Registry
```

#### Class Attributes

- `plugins: dict[str, type[Plugin]]` - Registered plugins by label
- `labels: list[str]` - All plugin labels
- `transforms_map: dict[str, list]` - Transform mappings

#### Class Methods

##### get_entity(label: str) -> type[Plugin]

Retrieve a plugin by label, snake_case name, or versioned ID.

```python
EmailPlugin = Registry.get_entity("email")
EmailPlugin = Registry.get_entity("email_address")
EmailPlugin = Registry.get_entity("email@1.0.0")
```

##### find_transforms(entity_id: str, version: str) -> dict[str, Callable]

Get all transforms for an entity version.

```python
transforms = Registry.find_transforms("email", "1.0.0")
# {"extract_domain": <function>, "validate": <function>}
```

##### register_transform(entity_id, version_spec, label, fn) -> None

Register a transform function (called automatically by decorator).

---

### TransformPayload

Pydantic model passed to transform functions.

```python
from osintbuddy import TransformPayload
```

#### Attributes

Entity fields are accessible as snake_case attributes:

```python
entity.email        # Access "Email" field
entity.ip_address   # Access "IP Address" field
```

#### Methods

##### get_field(label: str) -> Any

Get field value by label.

```python
value = entity.get_field("Email")
```

##### get_typed_field(field_type: str) -> Any

Get first field matching the type.

```python
email = entity.get_typed_field("email")
```

---

## Decorators

### transform

Decorator for defining transform functions.

```python
from osintbuddy import transform

@transform(
    target: str,                          # Required: entity@version_spec
    label: str,                           # Required: display name
    icon: str = None,                     # Icon identifier
    edge_label: str = None,               # Default edge label
    deps: list[str] = None,               # Dependencies
    settings: list[TransformSetting] = None,
    transform_set: TransformSet = None,
    accepts: list[str] = None,            # Input field types
    produces: list[str] = None,           # Output field types
)
async def my_transform(entity: TransformPayload, cfg: dict = None):
    ...
```

---

## Result Types

### Entity

Wrapper for transform results with metadata.

```python
from osintbuddy import Entity

Entity(
    data: dict,                   # Required: from Plugin.blueprint()
    edge: Edge = None,            # Custom edge styling
    files: list[File] = [],       # File attachments
    children: list[Entity] = [],  # Nested entities
)
```

### Edge

Custom edge styling.

```python
from osintbuddy import Edge

Edge(
    label: str = "",              # Edge label
    color: str = None,            # Hex color
    style: str = None,            # solid/dashed/dotted
    width: int = None,            # Line width
    animated: bool = False,       # Animation
    properties: dict = {},        # Custom metadata
)
```

### File

File attachment.

```python
from osintbuddy import File

File(
    path: str,                    # Required: absolute file path
    label: str = None,            # Display label
    mime_type: str = None,        # MIME type
    description: str = None,      # Description
)
```

### Subgraph

Complex multi-entity result.

```python
from osintbuddy import Subgraph

Subgraph(
    entities: list[Entity] = [],
    edges: list[tuple[str, str, Edge]] = [],  # (source, target, edge)
)
```

### normalize_result

Normalize various result formats.

```python
from osintbuddy import normalize_result

normalized = normalize_result(result, default_edge_label="related")
# Always returns list of normalized dicts
```

---

## Types

### FieldType

Enum of semantic field types.

```python
from osintbuddy.types import FieldType

FieldType.EMAIL
FieldType.IP_ADDRESS
FieldType.DOMAIN
FieldType.URL
# ... see types.md for complete list
```

### TypedValue

Wrapper for values with explicit type.

```python
from osintbuddy.types import TypedValue

typed = TypedValue(value="user@example.com", field_type=FieldType.EMAIL)
```

### get_field_type

Infer field type from value.

```python
from osintbuddy.types import get_field_type

field_type = get_field_type("192.168.1.1")  # FieldType.IPV4
```

### are_types_compatible

Check type compatibility.

```python
from osintbuddy.types import are_types_compatible

compatible = are_types_compatible(FieldType.IP_ADDRESS, FieldType.IPV4)  # True
```

---

## Elements

### Input Elements

```python
from osintbuddy.elements import (
    TextInput,
    TextAreaInput,
    DropdownInput,
    UploadFileInput,
)

TextInput(label, icon=None, value="", field_type=None, width=12)
TextAreaInput(label, value="", field_type=None, width=12)
DropdownInput(label, options=[], value="", width=12)
UploadFileInput(label, icon=None)
```

### Display Elements

```python
from osintbuddy.elements import (
    Title,
    Text,
    CopyText,
    CopyCode,
    Json,
    Image,
    Video,
    Pdf,
    List,
    Table,
    Empty,
)

Title(label, value="", width=12)
Text(label, value="", icon=None, width=12)
CopyText(label, value="", width=12)
CopyCode(label, value="", width=12)
Json(label, width=12)
Image(label, width=12)
Video(label, width=12)
Pdf(label, width=12)
List(label, width=12)
Table(label, width=12)
Empty(width=12)
```

---

## Settings

### TransformSetting

Configuration option for transforms.

```python
from osintbuddy import TransformSetting
from osintbuddy.settings import SettingType

TransformSetting(
    name: str,                    # Config key
    display_name: str,            # UI label
    setting_type: SettingType,    # Validation type
    default_value: str = "",
    required: bool = False,
    global_setting: bool = False,
    description: str = "",
    popup: bool = False,
)
```

### SettingType

```python
from osintbuddy.settings import SettingType

SettingType.STRING
SettingType.INT
SettingType.FLOAT
SettingType.BOOL
SettingType.URL
SettingType.PASSWORD
SettingType.DATE
SettingType.DATETIME
```

### SettingsManager

Manage persistent settings.

```python
from osintbuddy import get_settings_manager

manager = get_settings_manager()

# Global settings
manager.load_global_settings() -> dict
manager.save_global_settings(settings: dict) -> None

# Transform settings
manager.load_transform_settings(name: str) -> dict
manager.save_transform_settings(name: str, settings: dict) -> None

# Individual settings
manager.get_setting(key: str, global_setting: bool = False, transform_name: str = None) -> str
manager.set_setting(key: str, value: str, global_setting: bool = False, transform_name: str = None) -> None

# Build merged config
manager.build_config(transform_name: str, settings: list, runtime_config: dict = None) -> dict

# Validate config
manager.validate_config(settings: list, config: dict) -> None  # Raises ConfigError
```

---

## Transform Sets

### TransformSet

Group transforms together.

```python
from osintbuddy.sets import TransformSet

MY_SET = TransformSet(
    name: str,
    description: str = "",
    icon: str = "folder",
)
```

### Built-in Sets

```python
from osintbuddy.sets import (
    OSINT_CORE,
    SOCIAL_MEDIA,
    NETWORK,
    IDENTITY,
    THREAT_INTEL,
    DOCUMENTS,
    GEOLOCATION,
    CRYPTOCURRENCY,
)
```

---

## Messages

### UIMessage

User feedback message.

```python
from osintbuddy import UIMessage, MessageType

UIMessage(
    message: str,
    type: MessageType = MessageType.INFO,
    title: str = "",
    details: str = "",
    duration: int = 5000,  # ms, 0 = persistent
)
```

### MessageType

```python
from osintbuddy import MessageType

MessageType.INFO
MessageType.WARNING
MessageType.ERROR
MessageType.DEBUG
MessageType.SUCCESS
```

### TransformResponse

Fluent response builder.

```python
from osintbuddy import TransformResponse

response = TransformResponse()
response.info("Starting...")
response.add_entity(Entity(...))
response.warning("Rate limited")
response.success("Complete")
return response
```

---

## Output

### emit_result

Emit structured result.

```python
from osintbuddy import emit_result

emit_result({"entities": [...], "edges": [...]})
# Outputs:
# ---OSIB_JSON_START---
# {"entities": [...]}
# ---OSIB_JSON_END---
```

### emit_error

Emit structured error.

```python
from osintbuddy import emit_error
from osintbuddy.errors import ErrorCode

emit_error("Failed", ErrorCode.TRANSFORM_FAILED, {"reason": "..."})
```

### emit_progress

Emit progress update.

```python
from osintbuddy import emit_progress

emit_progress("Processing...", percent=50, stage="analysis")
```

### ProgressEmitter

Context manager for progress.

```python
from osintbuddy import ProgressEmitter

with ProgressEmitter("Analysis") as progress:
    progress.update("Starting...", 0)
    progress.increment("Working...", 25)
    progress.complete()
```

---

## Errors

### Exception Hierarchy

```python
from osintbuddy import (
    PluginError,          # Base exception
    PluginWarn,           # Non-fatal warning
    PluginNotFoundError,
    TransformNotFoundError,
    TransformCollisionError,
    DependencyError,
    ConfigError,
    TransformTimeoutError,
    NetworkError,
    RateLimitError,
    AuthError,
)
```

### ErrorCode

```python
from osintbuddy import ErrorCode

ErrorCode.PLUGIN_NOT_FOUND
ErrorCode.PLUGIN_LOAD_ERROR
ErrorCode.TRANSFORM_NOT_FOUND
ErrorCode.TRANSFORM_FAILED
ErrorCode.TRANSFORM_TIMEOUT
ErrorCode.TRANSFORM_COLLISION
ErrorCode.DEPENDENCY_MISSING
ErrorCode.CONFIG_INVALID
ErrorCode.NETWORK_ERROR
ErrorCode.RATE_LIMITED
ErrorCode.AUTH_FAILED
```

### Exception Attributes

```python
try:
    ...
except PluginError as e:
    e.message   # Human-readable message
    e.code      # ErrorCode enum
    e.details   # Additional context dict
    e.to_dict() # JSON-serializable dict
```

---

## Dependencies

### ensure_deps

Ensure packages are installed.

```python
from osintbuddy import ensure_deps

ensure_deps(("requests>=2.0", "beautifulsoup4"))
```

### check_deps

Check if packages are available.

```python
from osintbuddy import check_deps

missing = check_deps(["requests", "httpx"])
```

---

## Compiler

### compile_entity

Compile JSON to Python source.

```python
from osintbuddy import compile_entity

source = compile_entity(json_dict, version="1.0.0")
# or
source = compile_entity(json_string, version="1.0.0")
```

### compile_file

Compile JSON file to Python file.

```python
from osintbuddy import compile_file

compile_file("entity.json", "entity.py", version="1.0.0")
```

### compile_directory

Batch compile directory.

```python
from osintbuddy import compile_directory

compile_directory("json/", "entities/", version="1.0.0")
```

---

## Plugin Loading

### load_plugins_fs

Load plugins from filesystem.

```python
from osintbuddy import load_plugins_fs

load_plugins_fs(
    plugins_path: str,     # Path to plugins directory
    package: str,          # Package name for imports
)
```

The function:

1. Loads entities from `{path}/entities/*.py`
2. Loads transforms from `{path}/transforms/*.py`
3. Installs plugin-level dependencies
4. Registers everything with the Registry

---

## Utilities

Located in `osintbuddy.utils`:

```python
from osintbuddy.utils import (
    to_snake_case,        # "Hello World" -> "hello_world"
    to_camel_case,        # "hello_world" -> "helloWorld"
    slugify,              # "Hello World!" -> "hello-world"
    chunks,               # Split list into chunks
    find_emails,          # Extract emails from text
    to_clean_domain,      # URL -> root domain
    dkeys_to_snake_case,  # Recursive dict key conversion
    get_driver,           # Selenium WebDriver context manager
)
```

---

## Version

```python
from osintbuddy import __version__

print(__version__)  # "1.0.0"
```
