# Getting Started

This guide walks you through installing OSINTBuddy, setting up a plugin project, and creating your first entity and transform.

## Prerequisites

- Python 3.12 or higher
- pip or uv package manager

## Installation

### From PyPI

```bash
pip install osintbuddy
```

### From Source (Development)

```bash
git clone https://github.com/osintbuddy/plugins.git
cd plugins/osib
pip install -e ".[dev]"
```

### Verify Installation

```bash
ob --help
```

You should see the available CLI commands.

## Project Structure

Create a plugin project with the following structure:

```
my-osint-plugins/
├── entities/
│   ├── __init__.py
│   ├── email.py
│   ├── domain.py
│   └── person.py
├── transforms/
│   ├── __init__.py
│   ├── email_transforms.py
│   └── domain_transforms.py
└── __init__.py
```

The framework expects:
- **entities/**: Plugin class definitions (one per entity type)
- **transforms/**: Transform functions decorated with `@transform`

## Your First Entity

Create `entities/email.py`:

```python
from osintbuddy import Plugin
from osintbuddy.elements import TextInput, CopyText
from osintbuddy.types import FieldType


class EmailEntity(Plugin):
    """An email address entity for OSINT investigations."""

    # Required: Semantic version
    version = "1.0.0"

    # Display metadata
    label = "Email"
    description = "An email address to investigate"
    icon = "mail"
    color = "#3B82F6"

    # Organization
    category = "Identity"
    tags = ["email", "identity", "contact"]

    # Form definition
    elements = [
        TextInput(label="Email", icon="mail", field_type=FieldType.EMAIL),
        CopyText(label="Domain"),
        CopyText(label="Username"),
    ]
```

### Key Attributes

| Attribute | Required | Description |
|-----------|----------|-------------|
| `version` | Yes | Semantic version (e.g., "1.0.0") |
| `label` | Yes | Display name in the UI |
| `elements` | Yes | Form fields for the entity |
| `icon` | No | Icon identifier (default: "atom-2") |
| `color` | No | Hex color (default: "#145070") |
| `category` | No | UI grouping category |
| `description` | No | Long description |
| `tags` | No | Searchable tags |
| `show_in_ui` | No | Whether to show in entity picker (default: true) |

## Your First Transform

Create `transforms/email_transforms.py`:

```python
from osintbuddy import transform, Entity, Edge
from entities.email import EmailEntity


# Import your target entity - this would be defined elsewhere
class DomainEntity(Plugin):
    version = "1.0.0"
    label = "Domain"
    elements = [TextInput(label="Domain", field_type=FieldType.DOMAIN)]


@transform(
    target="email@>=1.0.0",
    label="Extract Domain",
    icon="world",
)
async def extract_domain(entity):
    """Extract the domain from an email address."""
    email = entity.email  # Access fields via snake_case attribute

    if not email or "@" not in email:
        return None  # Return None if no result

    parts = email.split("@")
    domain = parts[1]
    username = parts[0]

    return Entity(
        data=DomainEntity.blueprint(domain=domain),
        edge=Edge(label="has domain"),
    )
```

### Transform Basics

- **target**: Entity ID and version spec (e.g., `"email@>=1.0.0"`)
- **label**: Display name in the context menu
- **async**: All transforms must be async functions
- **entity**: A `TransformPayload` with field access via snake_case attributes

## Loading Your Plugins

Use `load_plugins_fs` to load your plugins:

```python
from osintbuddy import load_plugins_fs

# Load from a directory
load_plugins_fs("/path/to/my-osint-plugins", "my_plugins")
```

Or use the CLI with the `-P` flag:

```bash
ob entities -P /path/to/my-osint-plugins
```

## Loading Plugin Resources

If your plugin includes local JSON or text files (like dropdown options),
load them relative to the plugin module:

```python
from osintbuddy import Plugin, read_resource_json
from osintbuddy.elements import DropdownInput

options = read_resource_json(__file__, "options.json", default=[])

class ExamplePlugin(Plugin):
    elements = [
        DropdownInput(label="Options", options=options),
    ]
```

## Running Transforms

### Via CLI

```bash
ob transform '{
  "label": "email",
  "version": "1.0.0",
  "transform": "extract_domain",
  "data": {
    "email": "user@example.com"
  }
}'
```

### Via the Microservice

Start the plugin microservice:

```bash
ob start
```

The service runs on port 42562 and exposes endpoints for the OSINTBuddy application.

## Returning Results

Transforms can return various result types:

### Single Entity

```python
return Entity(
    data=TargetEntity.blueprint(field="value"),
    edge=Edge(label="relationship"),
)
```

### Multiple Entities

```python
return [
    Entity(data=Entity1.blueprint(...)),
    Entity(data=Entity2.blueprint(...)),
]
```

### With Files

```python
return Entity(
    data=Report.blueprint(title="Analysis"),
    files=[File(path="/tmp/report.pdf", label="PDF Report")],
)
```

### Complex Subgraph

```python
return Subgraph(
    entities=[
        Entity(data=Node1.blueprint(...)),
        Entity(data=Node2.blueprint(...)),
    ],
    edges=[
        ("node1_id", "node2_id", Edge(label="connects")),
    ],
)
```

### Backwards Compatibility

Plain dictionaries still work for simple cases:

```python
return TargetEntity.blueprint(field="value")  # Legacy format
```

## Error Handling

Use the structured error types:

```python
from osintbuddy import PluginError, NetworkError, RateLimitError

@transform(target="domain@>=1.0.0", label="DNS Lookup")
async def dns_lookup(entity):
    try:
        result = await perform_dns_lookup(entity.domain)
        return Entity(data=DNSRecord.blueprint(**result))
    except ConnectionError:
        raise NetworkError("Failed to connect to DNS server")
    except TooManyRequests:
        raise RateLimitError("Rate limited by DNS provider")
```

## Next Steps

- [Plugins & Entities](plugins.md) - Deep dive into entity definitions
- [Transforms](transforms.md) - Advanced transform patterns
- [Elements](elements.md) - All available form elements
- [Field Types](types.md) - Type-based matching
- [Settings](settings.md) - Configuration and persistence
- [CLI Reference](cli.md) - Complete CLI documentation
