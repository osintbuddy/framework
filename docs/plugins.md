# Plugins & Entities

Entities are the nodes in your OSINTBuddy graph. Each entity type is defined as a `Plugin` subclass that specifies its metadata, form fields, and behavior.

## The Plugin Class

Every entity inherits from `Plugin`:

```python
from osintbuddy import Plugin
from osintbuddy.elements import TextInput, CopyText
from osintbuddy.types import FieldType


class PersonEntity(Plugin):
    version = "1.0.0"
    label = "Person"
    description = "A person of interest in an investigation"
    author = "Your Name"
    icon = "user"
    color = "#8B5CF6"
    category = "Identity"
    tags = ["person", "identity", "human"]
    show_in_ui = True
    deps = []

    elements = [
        TextInput(label="Full Name", icon="user", field_type=FieldType.PERSON_NAME),
        [
            TextInput(label="First Name", width=6),
            TextInput(label="Last Name", width=6),
        ],
        CopyText(label="Notes"),
    ]
```

## Plugin Attributes

### Required Attributes

| Attribute  | Type   | Description                               |
| ---------- | ------ | ----------------------------------------- |
| `version`  | `str`  | Semantic version (e.g., "1.0.0", "2.1.0") |
| `label`    | `str`  | Display name shown in the UI              |
| `elements` | `list` | Form field definitions                    |

### Optional Attributes

| Attribute     | Type               | Default        | Description                        |
| ------------- | ------------------ | -------------- | ---------------------------------- |
| `entity_id`   | `str`              | Auto-generated | Override the entity identifier     |
| `description` | `str`              | `""`           | Long description for documentation |
| `author`      | `str \| list[str]` | `""`           | Plugin author(s)                   |
| `icon`        | `str`              | `"atom-2"`     | Icon identifier                    |
| `color`       | `str`              | `"#145070"`    | Hex color code                     |
| `category`    | `str`              | `""`           | UI grouping category               |
| `tags`        | `list[str]`        | `[]`           | Searchable tags                    |
| `show_in_ui`  | `bool`             | `True`         | Show in entity picker dialog       |
| `deps`        | `list[str]`        | `[]`           | Plugin-level Python dependencies   |

## Entity Identification

Each entity gets a unique identifier based on its label:

```python
class IPAddress(Plugin):
    label = "IP Address"  # entity_id becomes "ip_address"
```

You can override this:

```python
class IPAddress(Plugin):
    entity_id = "ipv4"  # Explicit ID
    label = "IP Address"
```

The full entity identifier includes the version:

```
ip_address@1.0.0
```

## Automatic Registration

Plugins are automatically registered when their class is defined. The `Registry` metaclass handles this:

```python
from osintbuddy import Registry

# List all registered plugins
for label, plugin_class in Registry.plugins.items():
    print(f"{label}: {plugin_class.version}")

# Get a specific plugin
EmailPlugin = Registry.get_entity("email")

# Also works with snake_case
EmailPlugin = Registry.get_entity("email_address")

# Or versioned ID
EmailPlugin = Registry.get_entity("email@1.0.0")
```

## Elements Layout

Elements define the form fields for your entity. They can be arranged in rows:

```python
elements = [
    # Single element takes full width
    TextInput(label="Full Name"),

    # Multiple elements in a row (grid-based)
    [
        TextInput(label="First", width=6),  # Half width
        TextInput(label="Last", width=6),   # Half width
    ],

    # Three columns
    [
        TextInput(label="City", width=4),
        TextInput(label="State", width=4),
        TextInput(label="Country", width=4),
    ],
]
```

Width is based on a 12-column grid (similar to Bootstrap).

## Creating Entity Instances

Use `blueprint()` to generate entity data:

```python
# Get the entity definition with optional field values
data = PersonEntity.blueprint(
    full_name="John Doe",
    first_name="John",
    last_name="Doe",
)

# Returns a dict suitable for graph storage
{
    "label": "Person",
    "entity_id": "person",
    "version": "1.0.0",
    "data": {
        "full_name": "John Doe",
        "first_name": "John",
        "last_name": "Doe",
    },
    "elements": [...],
    # ... other metadata
}
```

Use `create()` for a simpler dict:

```python
data = PersonEntity.create(full_name="John Doe")
# Simpler output for basic use cases
```

## Versioning

Semantic versioning enables transform compatibility:

```python
class EmailEntity(Plugin):
    version = "1.0.0"  # Initial version
    label = "Email"
    elements = [
        TextInput(label="Email"),
    ]


class EmailEntityV2(Plugin):
    version = "2.0.0"  # Breaking change
    entity_id = "email"  # Same entity, new version
    label = "Email"
    elements = [
        TextInput(label="Email"),
        TextInput(label="Display Name"),  # New field
    ]
```

Transforms target version ranges:

```python
# Works with v1.x.x only
@transform(target="email@>=1.0.0,<2.0.0", label="V1 Transform")

# Works with v2.x.x and above
@transform(target="email@>=2.0.0", label="V2 Transform")

# Works with any version
@transform(target="email", label="Universal Transform")
```

## Field Types

Add semantic types to enable type-based transform matching:

```python
from osintbuddy.types import FieldType

elements = [
    TextInput(label="Email", field_type=FieldType.EMAIL),
    TextInput(label="Phone", field_type=FieldType.PHONE),
    TextInput(label="IP", field_type=FieldType.IP_ADDRESS),
]
```

This allows transforms to work with any entity that has a matching field type. See [Field Types](types.md) for the complete list.

## Dependencies

Specify Python packages required by your entity:

```python
class GeoEntity(Plugin):
    version = "1.0.0"
    label = "Location"
    deps = ["geopy>=2.0.0", "folium"]  # Auto-installed when loaded

    elements = [
        TextInput(label="Latitude", field_type=FieldType.LATITUDE),
        TextInput(label="Longitude", field_type=FieldType.LONGITUDE),
    ]
```

Dependencies are installed automatically via pip when the plugin is loaded.

## Hidden Entities

Some entities should not appear in the entity picker (e.g., result-only entities):

```python
class SearchResult(Plugin):
    version = "1.0.0"
    label = "Search Result"
    show_in_ui = False  # Hidden from picker

    elements = [
        Title(label="Title"),
        CopyText(label="URL"),
        Text(label="Snippet"),
    ]
```

## Categories and Tags

Organize entities for discoverability:

```python
class BitcoinAddress(Plugin):
    version = "1.0.0"
    label = "Bitcoin Address"
    category = "Cryptocurrency"
    tags = ["bitcoin", "btc", "crypto", "blockchain", "wallet"]

    elements = [
        TextInput(label="Address", field_type=FieldType.BITCOIN_ADDRESS),
        CopyText(label="Balance"),
    ]
```

## JSON Entity Definition

Entities can also be defined in JSON and compiled to Python:

```json
{
  "label": "Email",
  "version": "1.0.0",
  "color": "#3B82F6",
  "icon": "mail",
  "category": "Identity",
  "tags": ["email", "identity"],
  "elements": [
    {
      "type": "text",
      "label": "Email",
      "icon": "mail",
      "field_type": "email"
    },
    {
      "type": "copy_text",
      "label": "Domain"
    }
  ]
}
```

Compile to Python:

```bash
ob compile email.json -O entities/email.py
```

Or programmatically:

```python
from osintbuddy import compile_file

compile_file("email.json", "entities/email.py", version="1.0.0")
```

## Complete Example

```python
from osintbuddy import Plugin
from osintbuddy.elements import TextInput, TextAreaInput, CopyText, Title, Image
from osintbuddy.types import FieldType


class SocialProfile(Plugin):
    """A social media profile entity."""

    version = "1.0.0"
    label = "Social Profile"
    description = "A social media account or profile"
    author = ["OSIB Team", "Contributors"]
    icon = "brand-twitter"
    color = "#1DA1F2"
    category = "Social Media"
    tags = ["social", "profile", "account", "twitter", "facebook", "instagram"]
    show_in_ui = True
    deps = []

    elements = [
        # Profile header
        [
            Image(label="Avatar", width=3),
            Title(label="Display Name", width=9),
        ],

        # Identity fields
        [
            TextInput(
                label="Username",
                icon="at",
                field_type=FieldType.USERNAME,
                width=6
            ),
            TextInput(
                label="Platform",
                icon="brand-twitter",
                field_type=FieldType.SOCIAL_PLATFORM,
                width=6
            ),
        ],

        # URLs
        CopyText(label="Profile URL", field_type=FieldType.URL),

        # Bio/description
        TextAreaInput(label="Bio", field_type=FieldType.TEXT),

        # Additional data
        [
            TextInput(label="Followers", width=4),
            TextInput(label="Following", width=4),
            TextInput(label="Posts", width=4),
        ],
    ]
```

## Loading Plugin Resources

If your plugin needs a local JSON or text file (for dropdown options, templates, etc.),
load it relative to the plugin module:

```python
from osintbuddy import Plugin, read_resource_json
from osintbuddy.elements import DropdownInput

options = read_resource_json(__file__, "cses.json", default=[])

class GoogleCSESearch(Plugin):
    elements = [
        DropdownInput(label="CSE Categories", options=options),
    ]
```

## Next Steps

- [Transforms](transforms.md) - Create operations on your entities
- [Elements](elements.md) - All available form elements
- [Field Types](types.md) - Type system for semantic matching
